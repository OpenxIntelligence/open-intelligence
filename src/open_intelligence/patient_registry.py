"""Canonical patient reference registry; no PHI or identity proofing.

An existing trusted security service supplies authorizer. This is a first-party
operational identity owner, not real-person verification, a clinical EHR, or
patient consent. Not exposed through the unauthenticated local server.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Callable

OPAQUE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{2,127}\Z")
PURPOSES = frozenset({"care", "operations", "research"})
Authorizer = Callable[[str, str, str, str], bool]


class PatientRegistryError(ValueError):
    pass


class PatientRegistryDenied(PermissionError):
    pass


class PatientRegistryConflict(PatientRegistryError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS identity_patients (
 patient_id TEXT PRIMARY KEY, origin_org TEXT NOT NULL, created_at TEXT NOT NULL,
 created_by TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','suspended')),
 revision INTEGER NOT NULL CHECK(revision>=1)
);
CREATE INDEX IF NOT EXISTS idx_identity_patients_org
 ON identity_patients(origin_org,patient_id);
CREATE TABLE IF NOT EXISTS identity_create_receipts (
 origin_org TEXT NOT NULL, request_key TEXT NOT NULL, request_digest TEXT NOT NULL,
 patient_id TEXT NOT NULL REFERENCES identity_patients(patient_id),
 created_at TEXT NOT NULL, PRIMARY KEY(origin_org,request_key)
);
CREATE TABLE IF NOT EXISTS identity_domain_events (
 id INTEGER PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES identity_patients(patient_id),
 event_type TEXT NOT NULL, metadata_json TEXT NOT NULL, occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_events_patient
 ON identity_domain_events(patient_id,id);
CREATE TRIGGER IF NOT EXISTS identity_create_receipts_immutable_update
BEFORE UPDATE ON identity_create_receipts BEGIN
 SELECT RAISE(ABORT,'identity creation receipts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS identity_create_receipts_immutable_delete
BEFORE DELETE ON identity_create_receipts BEGIN
 SELECT RAISE(ABORT,'identity creation receipts are immutable');
END;
CREATE TRIGGER IF NOT EXISTS identity_events_immutable_update
BEFORE UPDATE ON identity_domain_events BEGIN
 SELECT RAISE(ABORT,'identity events are immutable');
END;
CREATE TRIGGER IF NOT EXISTS identity_events_immutable_delete
BEFORE DELETE ON identity_domain_events BEGIN
 SELECT RAISE(ABORT,'identity events are immutable');
END;
"""


def _key(raw: object, name: str) -> str:
    if not isinstance(raw, str) or not OPAQUE.fullmatch(raw):
        raise PatientRegistryError(f"{name} must be a bounded opaque identifier")
    return raw


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _digest(parts: dict) -> str:
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class PatientRegistry:
    """First-party patient-ID owner with a trusted external policy dependency.

    require_patient/append_event form a domain-host port compatible with the
    proposed first-party EHR; no client may call these internal methods directly.
    """

    def __init__(self, db: sqlite3.Connection, authorizer: Authorizer | None = None):
        if db.in_transaction:
            raise PatientRegistryError("schema migration requires idle connection")
        self.db = db
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        self.authorizer = authorizer

    def _allow(self, actor: str, subject: str, action: str, purpose: str) -> None:
        _key(actor, "actor")
        _key(subject, "subject")
        if purpose not in PURPOSES:
            raise PatientRegistryDenied("unrecognized purpose")
        try:
            allowed = bool(self.authorizer and self.authorizer(actor, subject, action, purpose))
        except Exception:
            allowed = False
        if not allowed:
            raise PatientRegistryDenied("patient registry access denied")

    def require_patient(self, patient_id: str) -> None:
        """Internal host reference resolution only, NOT client authorization."""
        _key(patient_id, "patient_id")
        row = self.db.execute(
            "SELECT status FROM identity_patients WHERE patient_id=?", (patient_id,)
        ).fetchone()
        if row is None or row[0] != "active":
            raise PatientRegistryDenied("unknown or inactive patient")

    def append_event(self, patient_id: str, kind: str, **details: object) -> None:
        """Internal domain-host event port, no COMMIT, metadata references only."""
        if not self.db.in_transaction:
            raise PatientRegistryError("domain event requires caller transaction")
        self.require_patient(patient_id)
        _key(kind, "event kind")
        for key, value in details.items():
            _key(key, "metadata key")
            if not isinstance(value, (str, int, bool, type(None))):
                raise PatientRegistryError("event metadata must be primitive references")
            if isinstance(value, str) and len(value) > 128:
                raise PatientRegistryError("event metadata must not contain narrative")
        self.db.execute(
            "INSERT INTO identity_domain_events "
            "(patient_id,event_type,metadata_json,occurred_at) VALUES (?,?,?,?)",
            (patient_id, kind, json.dumps(details, sort_keys=True), _now()),
        )

    def create_patient(self, *, organization: str, actor: str, purpose: str,
                       request_key: str) -> dict:
        """Create an opaque patient with organization-scoped idempotency."""
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _key(request_key, "request_key")
        self._allow(actor, organization, "patient_create", purpose)
        fingerprint = _digest({"organization": organization, "actor": actor,
                               "purpose": purpose, "operation": "patient_create"})
        if self.db.in_transaction:
            raise PatientRegistryError("create_patient owns its transaction")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute(
                "SELECT request_digest,patient_id FROM identity_create_receipts "
                "WHERE origin_org=? AND request_key=?", (organization, request_key)
            ).fetchone()
            if old is not None:
                if old[0] != fingerprint:
                    raise PatientRegistryConflict("request key reused with different intent")
                self.db.commit()
                return {"patient_id": old[1], "duplicate": True}
            patient_id = "PAT-" + uuid.uuid4().hex.upper()
            now = _now()
            self.db.execute(
                "INSERT INTO identity_patients VALUES (?,?,?,?,?,?)",
                (patient_id, organization, now, actor, "active", 1),
            )
            self.db.execute(
                "INSERT INTO identity_create_receipts VALUES (?,?,?,?,?)",
                (organization, request_key, fingerprint, patient_id, now),
            )
            self.append_event(
                patient_id, "identity.patient.created",
                organization=organization, actor=actor, revision=1,
            )
            self.db.commit()
            return {"patient_id": patient_id, "duplicate": False}
        except BaseException:
            self.db.rollback()
            raise

    def get_patient(self, patient_id: str, *, actor: str, purpose: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        self._allow(actor, patient_id, "patient_read", purpose)
        row = self.db.execute(
            "SELECT patient_id,origin_org,created_at,status,revision "
            "FROM identity_patients WHERE patient_id=?", (patient_id,)
        ).fetchone()
        if row is None:
            raise PatientRegistryDenied("unknown patient")
        return dict(zip(("patient_id", "origin_org", "created_at", "status", "revision"), row))

    def list_patients(self, *, organization: str, actor: str, purpose: str) -> list[dict]:
        organization = _key(organization, "organization")
        self._allow(actor, organization, "patient_list", purpose)
        rows = self.db.execute(
            "SELECT patient_id,status,revision FROM identity_patients "
            "WHERE origin_org=? ORDER BY created_at,patient_id", (organization,)
        ).fetchall()
        return [dict(zip(("patient_id", "status", "revision"), row)) for row in rows]

    def suspend_patient(self, patient_id: str, *, actor: str, purpose: str,
                        expected_revision: int) -> dict:
        patient_id = _key(patient_id, "patient_id")
        self._allow(actor, patient_id, "patient_suspend", purpose)
        if type(expected_revision) is not int or expected_revision < 1:
            raise PatientRegistryError("expected_revision must be positive integer")
        if self.db.in_transaction:
            raise PatientRegistryError("suspend_patient owns its transaction")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            count = self.db.execute(
                "UPDATE identity_patients SET status='suspended',revision=revision+1 "
                "WHERE patient_id=? AND revision=? AND status='active'",
                (patient_id, expected_revision),
            ).rowcount
            if count != 1:
                raise PatientRegistryConflict("patient state/revision conflict")
            self.db.execute(
                "INSERT INTO identity_domain_events "
                "(patient_id,event_type,metadata_json,occurred_at) VALUES (?,?,?,?)",
                (patient_id, "identity.patient.suspended",
                 json.dumps({"actor": actor, "revision": expected_revision + 1}),
                 _now()),
            )
            self.db.commit()
            return {"patient_id": patient_id, "revision": expected_revision + 1,
                    "status": "suspended"}
        except BaseException:
            self.db.rollback()
            raise
