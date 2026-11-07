"""Process one actor-scoped source event using independently supplied authority."""
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os

from fastapi import HTTPException

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError

from .access import Authentication, authentication_for_settings, authenticate_token
from .composer_runs import ACTIONS, PostgresComposerRuns
from .config import Settings
from .database import Database
from .registry_context import registry_for_principal
from .source_event_delivery import EventLeaseLost, PostgresSourceEventDelivery
from .worker import _token_reader


def _run(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
         authentication: Authentication | None = None, lease_seconds: int = 30,
         inspect_only: bool = False, dead_letters_only: bool = False,
         limit: int = 20, after_event: int = 0, recovery: dict | None = None) -> dict:
    """Claim one bounded batch; never return source text, tokens or exception details."""
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
        raise ValueError("Lease duration must be between 1 and 300 seconds")
    if dead_letters_only:
        PostgresSourceEventDelivery.validate_page(limit, after_event)
    if recovery is not None:
        PostgresSourceEventDelivery.validate_recovery(**recovery)
    provider = authentication_for_settings(settings, authentication)

    def fresh():
        current = authenticate_token(token_provider(), provider)
        if (current.purpose != "operations" or patient_id not in current.patient_ids
                or not set(ACTIONS).issubset(current.actions)):
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
                for action in ACTIONS:
                    live._allow(current.actor, patient_id, action, current.purpose)

            deliveries = PostgresComposerRuns(registry).source_events()
            try:
                if recovery is not None:
                    return deliveries.recover(
                        patient_id, case_id, organization=initial.organization, actor=initial.actor,
                        purpose=initial.purpose, recheck_authority=recheck, **recovery)
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
                return {"status": "conflict"}
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


def read_status(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
                authentication: Authentication | None = None) -> dict:
    return _run(settings, token_provider, patient_id, case_id,
                authentication=authentication, inspect_only=True)


def read_dead_letters(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
                      authentication: Authentication | None = None, limit: int = 20,
                      after_event: int = 0) -> dict:
    return _run(settings, token_provider, patient_id, case_id, authentication=authentication,
                dead_letters_only=True, limit=limit, after_event=after_event)


def request_recovery(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
                     delivery_id: str, event_id: int, expected_revision: int,
                     authentication: Authentication | None = None) -> dict:
    return _run(settings, token_provider, patient_id, case_id, authentication=authentication,
                recovery={"delivery_id": delivery_id, "event_id": event_id,
                          "expected_revision": expected_revision})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deliver one independently fictional source-context event batch.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--status", action="store_true", help="Inspect this actor's backlog without claiming work")
    mode.add_argument("--dead-letters", action="store_true", help="Inspect scoped terminal failures")
    mode.add_argument("--recover", metavar="DELIVERY", help="Request recovery of one inspected terminal revision")
    parser.add_argument("--event-id", type=int)
    parser.add_argument("--expected-revision", type=int)
    parser.add_argument("--limit", type=int, default=None, choices=range(1, 101), metavar="1..100")
    parser.add_argument("--after-event", type=int, default=None)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--lease-seconds", type=int, default=30, choices=range(1, 301), metavar="1..300")
    args = parser.parse_args(argv)
    if not args.dead_letters and (args.limit is not None or args.after_event is not None):
        parser.error("Pagination options require --dead-letters")
    if args.recover is not None:
        try:
            PostgresSourceEventDelivery.validate_recovery(args.recover, args.event_id, args.expected_revision)
        except ValueError as error:
            parser.error(str(error))
    elif args.event_id is not None or args.expected_revision is not None:
        parser.error("Event identity and revision options require --recover")
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
        elif args.recover is not None:
            result = request_recovery(Settings.from_env(), _token_reader(path), args.patient, args.case,
                                      delivery_id=args.recover, event_id=args.event_id,
                                      expected_revision=args.expected_revision)
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
    return 0 if result["status"] in {"idle", "delivered", "queued", "fenced", "observed", "recovery_requested"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
