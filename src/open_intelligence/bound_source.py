"""Synthetic-only, read-only boundary to existing CaseStore originals.

The binding resolver must consult the canonical patient/binding owner.
This adapter does not create identity, bind patients, or grant clinical authority.
PostgreSQL and SQLite do NOT share an atomic transaction.
"""
from dataclasses import dataclass
from hashlib import sha256
from typing import Callable, Mapping, Protocol

class SourceAccessDenied(PermissionError):
    pass

class SourceIntegrityFailure(RuntimeError):
    pass

class Actor(Protocol):
    actor: str
    organization: str
    purpose: str

@dataclass(frozen=True)
class BoundSourceVersion:
    patient_id: str
    case_id: str
    source_store_id: str
    source_version_id: int
    document_id: str
    version: int
    state: str
    sha256: str
    raw: bytes
    kind: str
    event_date: str
    issued_at: str
    received_at: str
    specimen_id: str | None
    supersedes_id: int | None

BindingResolver = Callable[[str, str, str], Mapping[str, object] | None]
AccessDecision = Callable[[Actor, str, str, str], bool]

def read_bound_source(*, patient_id: str, case_id: str, source_version_id: int,
                      source_store_id: str, principal: Actor, store,
                      resolve_binding: BindingResolver,
                      authorize: AccessDecision) -> BoundSourceVersion:
    """Return an exact source original after two independent access checks.

    The trusted resolver verifies canonical patient activity and provides the
    reviewed, active binding with keys patient_id, case_id, source_store_id,
    organization, status. The authorizer separately enforces source_read.
    No caller-selected case or patient ID grants authority. Revocation can
    prevent future requests, not recall bytes already released.
    """
    def permitted() -> bool:
        if not all(isinstance(s, str) and 3 <= len(s) <= 128
                   for s in (patient_id, case_id, source_store_id)):
            return False
        if (principal.purpose != "operations" or not principal.actor
                or not principal.organization):
            return False
        try:
            binding = resolve_binding(patient_id, case_id, source_store_id)
            return bool(binding and binding.get("status") == "active"
                        and binding.get("patient_id") == patient_id
                        and binding.get("case_id") == case_id
                        and binding.get("source_store_id") == source_store_id
                        and binding.get("organization") == principal.organization
                        and authorize(principal, patient_id, case_id, "source_read"))
        except Exception:
            return False

    if type(source_version_id) is not int or source_version_id < 1 or not permitted():
        raise SourceAccessDenied("Source unavailable")
    try:
        row = store.db.execute(
            "SELECT case_id,document_id,version,state,sha256,raw,kind,event_date,"
            "issued_at,received_at,specimen_id,supersedes_id "
            "FROM source_versions WHERE case_id=? AND id=?",
            (case_id, source_version_id),
        ).fetchone()
    except Exception as exc:
        raise SourceIntegrityFailure("Source store unavailable") from exc
    if row is None:
        raise SourceAccessDenied("Source unavailable")
    try:
        raw = bytes(row["raw"])
        digest = sha256(raw).hexdigest()
        if (row["case_id"] != case_id or row["state"] not in ("current", "superseded")
                or digest != row["sha256"] or not raw):
            raise SourceIntegrityFailure("Source integrity mismatch")
        result = BoundSourceVersion(
            patient_id=patient_id, case_id=case_id,
            source_store_id=source_store_id, source_version_id=source_version_id,
            document_id=row["document_id"], version=row["version"],
            state=row["state"], sha256=digest, raw=raw, kind=row["kind"],
            event_date=row["event_date"], issued_at=row["issued_at"],
            received_at=row["received_at"], specimen_id=row["specimen_id"],
            supersedes_id=row["supersedes_id"],
        )
    except SourceIntegrityFailure:
        raise
    except Exception as exc:
        raise SourceIntegrityFailure("Source record malformed") from exc
    if not permitted():
        raise SourceAccessDenied("Source unavailable")
    return result
