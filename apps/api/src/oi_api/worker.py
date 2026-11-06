"""Execute one bounded Composer run with independently supplied current authority."""
from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
)

from .access import Authentication, DenyAuthentication, SyntheticFileAuthentication, authenticate_token
from .composer_runs import ACTIONS, PostgresComposerRuns, RunLeaseLost
from .config import Settings
from .database import Database
from .registry_context import registry_for_principal


def run_once(settings: Settings, token_provider: Callable[[], str], patient_id: str, case_id: str, *,
             authentication: Authentication | None = None, lease_seconds: int = 30) -> dict:
    """Claim at most one run; return only bounded non-content operational status.

    A process killed after claim leaves a recoverable lease. No request bearer,
    inherited permission list, source text or exception detail is persisted.
    """
    if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
        raise ValueError("Lease duration must be between 1 and 300 seconds")
    provider = authentication if authentication is not None else (
        SyntheticFileAuthentication(settings.access_file) if settings.access_file else DenyAuthentication())

    def fresh():
        current = authenticate_token(token_provider(), provider)
        if (current.purpose != "operations" or patient_id not in current.patient_ids
                or not set(ACTIONS).issubset(current.actions)):
            raise PatientRegistryDenied("Worker scope unavailable")
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
                    raise PatientRegistryDenied("Worker authority changed")
                live = registry_for_principal(connection, current)
                for action in ACTIONS:
                    live._allow(current.actor, patient_id, action, current.purpose)

            runs = PostgresComposerRuns(registry)
            try:
                claim = runs.claim_next(patient_id, case_id, organization=initial.organization,
                                        actor=initial.actor, purpose=initial.purpose,
                                        recheck_authority=recheck, lease_seconds=lease_seconds)
            except (PatientRegistryDenied, HTTPException):
                return {"status": "blocked"}
            if claim is None:
                return {"status": "idle"}
            try:
                runs.complete(claim, recheck_authority=recheck)
                return {"status": "completed", "attempt_count": claim["attempt_count"]}
            except RunLeaseLost:
                return {"status": "fenced", "attempt_count": claim["attempt_count"]}
            except (PatientRegistryDenied, HTTPException):
                reason = "authority_unavailable"
            except PatientRegistryConflict:
                reason = "source_changed"
            except (ValidationError, PatientRegistryError, ValueError):
                reason = "invalid_output"
            except Exception:
                reason = "retryable_failure"
            state = runs.finish_failure(claim, reason_code=reason)
            return {"status": state, "attempt_count": claim["attempt_count"]}
    except Exception:
        # A database failure may leave a claimed lease awaiting recovery. Never
        # assert a rollback, failure transition or completed result we did not see.
        return {"status": "unavailable"}
    finally:
        database.close()


def _token_reader(path: str):
    def read():
        with Path(path).open("rb") as stream:
            raw = stream.read(259)
        if len(raw) > 258:
            raise ValueError("Worker credential unavailable")
        return raw.decode("ascii").rstrip("\r\n")
    return read


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one independently fictional source-question brief.")
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--lease-seconds", type=int, default=30, choices=range(1, 301), metavar="1..300")
    args = parser.parse_args(argv)
    path = os.environ.get("OI_API_WORKER_TOKEN_FILE")
    try:
        if not path:
            result = {"status": "blocked"}
        else:
            result = run_once(Settings.from_env(), _token_reader(path), args.patient, args.case,
                              lease_seconds=args.lease_seconds)
    except Exception:
        result = {"status": "unavailable"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"idle", "completed", "queued", "fenced"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
