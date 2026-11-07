"""Process one actor-scoped source event using independently supplied authority."""
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os

from fastapi import HTTPException

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError

from .access import Authentication, DenyAuthentication, SyntheticFileAuthentication, authenticate_token
from .composer_runs import ACTIONS, PostgresComposerRuns
from .config import Settings
from .database import Database
from .registry_context import registry_for_principal
from .source_event_delivery import EventLeaseLost, PostgresSourceEventDelivery
from .worker import _token_reader


def _run(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
         authentication: Authentication | None = None, lease_seconds: int = 30,
         inspect_only: bool = False, dead_letters_only: bool = False,
         limit: int = 20, after_event: int = 0,
         recovery_id: str | None = None, expected_revision: int | None = None) -> dict:
    """Claim one bounded batch; never return source text, tokens or exception details."""
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
        raise ValueError("Lease duration must be between 1 and 300 seconds")
    if dead_letters_only:
        PostgresSourceEventDelivery.validate_page(limit, after_event)
    actions = (*ACTIONS, "source_delivery_retry") if recovery_id is not None else ACTIONS
    provider = authentication if authentication is not None else (
        SyntheticFileAuthentication(settings.access_file) if settings.access_file else DenyAuthentication())

    def fresh():
        current = authenticate_token(token_provider(), provider)
        if (current.purpose != "operations" or patient_id not in current.patient_ids
                or not set(actions).issubset(current.actions)):
            raise PatientRegistryDenied("Event worker scope unavailable")
        return current

    try:
        initial = fresh()
    except Exception:
        return {"status": "blocked"}
    database = Database(settings)
    try:
        with database.registry_connection() as connection:
            registry = registry_for_principal(connection, initial)

            def recheck():
                current = fresh()
                if (current.actor, current.organization, current.purpose) != (
                        initial.actor, initial.organization, initial.purpose):
                    raise PatientRegistryDenied("Event worker authority changed")
                live = registry_for_principal(connection, current)
                for action in actions:
                    live._allow(current.actor, patient_id, action, current.purpose)

            deliveries = PostgresComposerRuns(registry).source_events()
            try:
                if recovery_id is not None:
                    return deliveries.retry_failed(
                        patient_id, case_id, organization=initial.organization, actor=initial.actor,
                        purpose=initial.purpose, recheck_authority=recheck,
                        delivery_id=recovery_id, expected_revision=expected_revision)
                if dead_letters_only:
                    return deliveries.dead_letters(
                        patient_id, case_id, organization=initial.organization, actor=initial.actor,
                        purpose=initial.purpose, recheck_authority=recheck,
                        limit=limit, after_event=after_event)
                if inspect_only:
                    return deliveries.inspect(
                        patient_id, case_id, organization=initial.organization, actor=initial.actor,
                        purpose=initial.purpose, recheck_authority=recheck)
                claim = deliveries.claim_next(
                    patient_id, case_id, organization=initial.organization, actor=initial.actor,
                    purpose=initial.purpose, recheck_authority=recheck, lease_seconds=lease_seconds)
            except (PatientRegistryDenied, HTTPException):
                return {"status": "blocked"}
            except PatientRegistryConflict:
                if recovery_id is not None:
                    return {"status": "conflict"}
                raise
            if claim is None:
                return {"status": "idle"}
            if claim["state"] == "dead_letter":
                return {"status": "dead_letter", "attempt_count": claim["attempt_count"]}
            try:
                result = deliveries.deliver(claim, recheck_authority=recheck)
                return {"status": result["status"], "attempt_count": claim["attempt_count"],
                        "invalidated_count": result["invalidated_count"]}
            except EventLeaseLost:
                return {"status": "fenced", "attempt_count": claim["attempt_count"]}
            except (PatientRegistryDenied, HTTPException):
                reason = "authority_unavailable"
            except (PatientRegistryError, ValueError):
                reason = "invalid_event"
            except Exception:
                reason = "retryable_failure"
            state = deliveries.finish_failure(claim, reason_code=reason)
            return {"status": state, "attempt_count": claim["attempt_count"]}
    except Exception:
        # A failed response after commit is uncertain; replay uses the durable
        # receipt. Never claim rollback or successful delivery without evidence.
        return {"status": "unavailable"}
    finally:
        database.close()


def run_once(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
             authentication: Authentication | None = None, lease_seconds: int = 30) -> dict:
    return _run(settings, token_provider, patient_id, case_id,
                authentication=authentication, lease_seconds=lease_seconds)


def run_bounded(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
                authentication: Authentication | None = None, lease_seconds: int = 30,
                max_batches: int = 20) -> dict:
    """Process a finite backlog without changing identity or retrying a failed batch."""
    if type(max_batches) is not int or not 1 <= max_batches <= 100:
        raise ValueError("Batch budget must be between 1 and 100")
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
        raise ValueError("Lease duration must be between 1 and 300 seconds")
    provider = authentication if authentication is not None else (
        SyntheticFileAuthentication(settings.access_file) if settings.access_file else DenyAuthentication())

    class PinnedAuthentication:
        identity = None

        def authenticate(self, token):
            current = provider.authenticate(token)
            if current is None:
                return None
            identity = (current.actor, current.organization, current.purpose)
            if self.identity is None:
                self.identity = identity
            elif identity != self.identity:
                raise PatientRegistryDenied("Event worker authority changed")
            return current

    pinned = PinnedAuthentication()
    progress = {"batches_attempted": 0, "delivered_batches": 0, "continued_batches": 0}
    for _ in range(max_batches):
        result = run_once(settings, token_provider, patient_id, case_id,
                          authentication=pinned, lease_seconds=lease_seconds)
        progress["batches_attempted"] += 1
        if result["status"] == "delivered":
            progress["delivered_batches"] += 1
        elif result["status"] == "queued" and "invalidated_count" in result:
            # Successful consumer continuation is distinct from delayed retry.
            progress["continued_batches"] += 1
        else:
            return {"status": result["status"], **progress}
    return {"status": "limit_reached", **progress}


def read_status(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
                authentication: Authentication | None = None) -> dict:
    return _run(settings, token_provider, patient_id, case_id,
                authentication=authentication, inspect_only=True)


def read_dead_letters(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
                      authentication: Authentication | None = None, limit: int = 20,
                      after_event: int = 0) -> dict:
    return _run(settings, token_provider, patient_id, case_id, authentication=authentication,
                dead_letters_only=True, limit=limit, after_event=after_event)


def retry_delivery(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
                   delivery_id: str, expected_revision: int, authentication: Authentication | None = None) -> dict:
    PostgresSourceEventDelivery.validate_retry(delivery_id, expected_revision)
    return _run(settings, token_provider, patient_id, case_id, authentication=authentication,
                recovery_id=delivery_id, expected_revision=expected_revision)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deliver one independently fictional source-context event batch.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--retry-delivery", metavar="DELIVERY_ID", help="Requeue one inspected failure")
    parser.add_argument("--expected-revision", type=int)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--drain", action="store_true", help="Process a bounded eligible backlog")
    parser.add_argument("--max-batches", type=int, default=None, choices=range(1, 101), metavar="1..100")
    mode.add_argument("--status", action="store_true", help="Inspect this actor's backlog without claiming work")
    mode.add_argument("--dead-letters", action="store_true", help="Inspect scoped terminal failures")
    parser.add_argument("--limit", type=int, default=None, choices=range(1, 101), metavar="1..100")
    parser.add_argument("--after-event", type=int, default=None)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--lease-seconds", type=int, default=30, choices=range(1, 301), metavar="1..300")
    args = parser.parse_args(argv)
    if (args.retry_delivery is None) != (args.expected_revision is None):
        parser.error("--retry-delivery and --expected-revision must be used together")
    if args.retry_delivery is not None:
        try:
            PostgresSourceEventDelivery.validate_retry(args.retry_delivery, args.expected_revision)
        except ValueError as error:
            parser.error(str(error))
    if not args.drain and args.max_batches is not None:
        parser.error("Batch budget requires --drain")
    if not args.dead_letters and (args.limit is not None or args.after_event is not None):
        parser.error("Pagination options require --dead-letters")
    limit = args.limit if args.limit is not None else 20
    after_event = args.after_event if args.after_event is not None else 0
    try:
        PostgresSourceEventDelivery.validate_page(limit, after_event)
    except ValueError as error:
        parser.error(str(error))
    path = os.environ.get("OI_API_EVENT_WORKER_TOKEN_FILE")
    try:
        if not path:
            result = {"status": "blocked"}
        elif args.retry_delivery is not None:
            result = retry_delivery(Settings.from_env(), _token_reader(path), args.patient, args.case,
                                    delivery_id=args.retry_delivery, expected_revision=args.expected_revision)
        elif args.drain:
            result = run_bounded(Settings.from_env(), _token_reader(path), args.patient, args.case,
                                 lease_seconds=args.lease_seconds,
                                 max_batches=args.max_batches if args.max_batches is not None else 20)
        elif args.dead_letters:
            result = read_dead_letters(Settings.from_env(), _token_reader(path), args.patient, args.case,
                                       limit=limit, after_event=after_event)
        elif args.status:
            result = read_status(Settings.from_env(), _token_reader(path), args.patient, args.case)
        else:
            result = run_once(Settings.from_env(), _token_reader(path), args.patient, args.case,
                              lease_seconds=args.lease_seconds)
    except Exception:
        result = {"status": "unavailable"}
    print(json.dumps(result, sort_keys=True))
    if args.drain:
        return 0 if result["status"] in {"idle", "limit_reached"} else 2
    return 0 if result["status"] in {"idle", "delivered", "queued", "fenced", "observed", "retry_authorized"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
