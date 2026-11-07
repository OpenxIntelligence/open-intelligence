"""Process one actor-scoped source event using independently supplied authority."""
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os

from fastapi import HTTPException

from open_intelligence.patient_registry import PatientRegistryDenied, PatientRegistryError

from .access import Authentication, DenyAuthentication, SyntheticFileAuthentication, authenticate_token
from .composer_runs import ACTIONS, PostgresComposerRuns
from .config import Settings
from .database import Database
from .registry_context import registry_for_principal
from .source_event_delivery import EventLeaseLost
from .worker import _token_reader


def _run(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
         authentication: Authentication | None = None, lease_seconds: int = 30,
         inspect_only: bool = False) -> dict:
    """Claim one bounded batch; never return source text, tokens or exception details."""
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
        raise ValueError("Lease duration must be between 1 and 300 seconds")
    provider = authentication if authentication is not None else (
        SyntheticFileAuthentication(settings.access_file) if settings.access_file else DenyAuthentication())

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
                if inspect_only:
                    return deliveries.inspect(
                        patient_id, case_id, organization=initial.organization, actor=initial.actor,
                        purpose=initial.purpose, recheck_authority=recheck)
                claim = deliveries.claim_next(
                    patient_id, case_id, organization=initial.organization, actor=initial.actor,
                    purpose=initial.purpose, recheck_authority=recheck, lease_seconds=lease_seconds)
            except (PatientRegistryDenied, HTTPException):
                return {"status": "blocked"}
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deliver one independently fictional source-context event batch.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--status", action="store_true", help="Inspect this actor's backlog without claiming work")
    parser.add_argument("--patient", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--lease-seconds", type=int, default=30, choices=range(1, 301), metavar="1..300")
    args = parser.parse_args(argv)
    path = os.environ.get("OI_API_EVENT_WORKER_TOKEN_FILE")
    try:
        if not path:
            result = {"status": "blocked"}
        elif args.status:
            result = read_status(Settings.from_env(), _token_reader(path), args.patient, args.case)
        else:
            result = run_once(Settings.from_env(), _token_reader(path), args.patient, args.case,
                              lease_seconds=args.lease_seconds)
    except Exception:
        result = {"status": "unavailable"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"idle", "delivered", "queued", "fenced", "observed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
