"""PostgreSQL storage port for Open Intelligence's FIRST-PARTY PatientRegistry.

B-01b research integration only, not a new identity owner, new patient database,
production authorization, PHI permission, or a clinical signing mechanism.

This class exposes the existing PatientRegistry API and reuses its *exact*
validation, hashing and policy-gate implementation. It replaces SQLite
persistence with explicit parameterized PostgreSQL transactions. Installation
of SQL is managed separately, never performed in request handlers.

The disposable CI connects with database-superuser privileges to exercise the
schema; it does NOT qualify a clinical service DB role or consent policies.
No code should use this class for real persons before those gates are built.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Callable, Iterator

from .patient_registry import (
    PatientRegistry, PatientRegistryConflict, PatientRegistryDenied,
    PatientRegistryError, _digest, _key, _now, PURPOSES,
)


class _ConcurrentRequestWon(Exception):
    """Another transaction committed the same org/request idempotency key."""


class PostgresPatientRegistry:
    """Alternative persistence adapter for the canonical PatientRegistry port.

    ``db`` must be an owned synchronous DB-API connection, tested using
    pg8000==1.31.6 (BSD-3-Clause). Its autocommit setting must be false.
    AuthN/consent must come from a trusted separately qualified policy service.
    This module never opens a network listener and never runs migrations.

    Unlike the original SQLite adapter, callers must use ``transaction()``
    when appending an event alongside an external domain write. Nested or
    implicit event writes without an active transaction are rejected.
    """

    def __init__(self, db: Any, authorizer: Callable[[str,str,str,str],bool] | None = None):
        if getattr(db, "autocommit", None) is not False:
            raise PatientRegistryError("PostgreSQL registry requires non-autocommit connection")
        self.db = db
        self.authorizer = authorizer
        self._transaction_active = False

    def _allow(self, actor: str, subject: str, action: str, purpose: str) -> None:
        # Reuses the original first-party policy/identifier implementation,
        # rather than inventing a second authorization decision.
        PatientRegistry._allow(self, actor, subject, action, purpose)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """One ACID transaction; rollback of any event failure is mandatory."""
        if self._transaction_active:
            raise PatientRegistryError("nested registry transactions are not allowed")
        self._transaction_active = True
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        finally:
            self._transaction_active = False

    def _fetchone(self, sql: str, params: tuple = ()) -> tuple | None:
        cur = self.db.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchone()
        finally:
            cur.close()

    def _fetchall(self, sql: str, params: tuple = ()) -> list[tuple]:
        cur = self.db.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def _execute(self, sql: str, params: tuple = ()) -> int:
        cur = self.db.cursor()
        try:
            cur.execute(sql, params)
            return cur.rowcount
        finally:
            cur.close()

    def require_patient(self, patient_id: str) -> None:
        _key(patient_id, "patient_id")
        if self._transaction_active:
            row = self._fetchone(
                "SELECT status FROM identity.identity_patients WHERE patient_id=%s", (patient_id,)
            )
        else:
            with self.transaction():
                row = self._fetchone(
                    "SELECT status FROM identity.identity_patients WHERE patient_id=%s", (patient_id,)
                )
        if row is None or row[0] != "active":
            raise PatientRegistryDenied("unknown or inactive patient")

    def _write_event(self, patient_id: str, kind: str, details: dict[str, object]) -> None:
        if not self._transaction_active:
            raise PatientRegistryError("domain event requires caller transaction")
        _key(patient_id, "patient_id")
        _key(kind, "event kind")
        for key, value in details.items():
            _key(key, "metadata key")
            if not isinstance(value, (str, int, bool, type(None))):
                raise PatientRegistryError("event metadata must be primitive references")
            if isinstance(value, str) and len(value) > 128:
                raise PatientRegistryError("event metadata must not contain narrative")
        self._execute(
            "INSERT INTO identity.identity_domain_events "
            "(patient_id,event_type,metadata_json,occurred_at) "
            "VALUES (%s,%s,%s::jsonb,%s::timestamptz)",
            (patient_id, kind, json.dumps(details, sort_keys=True), _now()),
        )

    def append_event(self, patient_id: str, kind: str, **details: object) -> None:
        self.require_patient(patient_id)
        self._write_event(patient_id, kind, details)

    def _created_receipt(self, organization: str, request_key: str, digest: str) -> dict:
        """Read after collision, preserving hash and organization semantics."""
        with self.transaction():
            old = self._fetchone(
                "SELECT request_digest,patient_id FROM identity.identity_create_receipts "
                "WHERE origin_org=%s AND request_key=%s", (organization, request_key),
            )
        if old is None:
            raise PatientRegistryConflict("concurrent creation receipt was not committed")
        if old[0] != digest:
            raise PatientRegistryConflict("request key reused with different intent")
        return {"patient_id": old[1], "duplicate": True}

    def create_patient(self, *, organization: str, actor: str, purpose: str,
                       request_key: str) -> dict:
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _key(request_key, "request_key")
        self._allow(actor, organization, "patient_create", purpose)
        fingerprint = _digest({"organization": organization, "actor": actor,
                               "purpose": purpose, "operation": "patient_create"})
        try:
            with self.transaction():
                existing = self._fetchone(
                    "SELECT request_digest,patient_id FROM identity.identity_create_receipts "
                    "WHERE origin_org=%s AND request_key=%s", (organization, request_key),
                )
                if existing is not None:
                    if existing[0] != fingerprint:
                        raise PatientRegistryConflict("request key reused with different intent")
                    return {"patient_id": existing[1], "duplicate": True}
                patient_id = "PAT-" + uuid.uuid4().hex.upper()
                now = _now()
                self._execute(
                    "INSERT INTO identity.identity_patients "
                    "(patient_id,origin_org,created_at,created_by,status,revision) "
                    "VALUES (%s,%s,%s::timestamptz,%s,'active',1)",
                    (patient_id, organization, now, actor),
                )
                inserted = self._fetchone(
                    "INSERT INTO identity.identity_create_receipts "
                    "(origin_org,request_key,request_digest,patient_id,created_at) "
                    "VALUES (%s,%s,%s,%s,%s::timestamptz) "
                    "ON CONFLICT (origin_org,request_key) DO NOTHING RETURNING patient_id",
                    (organization, request_key, fingerprint, patient_id, now),
                )
                if inserted is None:
                    # The speculative patient insert MUST roll back before
                    # reading the winner: never leave an orphaned patient.
                    raise _ConcurrentRequestWon()
                self._write_event(
                    patient_id, "identity.patient.created",
                    {"organization": organization, "actor": actor, "revision": 1},
                )
                return {"patient_id": patient_id, "duplicate": False}
        except _ConcurrentRequestWon:
            return self._created_receipt(organization, request_key, fingerprint)

    def get_patient(self, patient_id: str, *, actor: str, purpose: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        self._allow(actor, patient_id, "patient_read", purpose)
        with self.transaction():
            row = self._fetchone(
                "SELECT patient_id,origin_org,created_at,status,revision "
                "FROM identity.identity_patients WHERE patient_id=%s", (patient_id,),
            )
        if row is None:
            raise PatientRegistryDenied("unknown patient")
        return {
            "patient_id": row[0], "origin_org": row[1],
            "created_at": row[2].isoformat(timespec="seconds") if isinstance(row[2], datetime) else str(row[2]),
            "status": row[3], "revision": row[4],
        }

    def list_patients(self, *, organization: str, actor: str, purpose: str) -> list[dict]:
        organization = _key(organization, "organization")
        self._allow(actor, organization, "patient_list", purpose)
        with self.transaction():
            rows = self._fetchall(
                "SELECT patient_id,status,revision FROM identity.identity_patients "
                "WHERE origin_org=%s ORDER BY created_at,patient_id", (organization,),
            )
        return [dict(zip(("patient_id", "status", "revision"), row)) for row in rows]

    def suspend_patient(self, patient_id: str, *, actor: str, purpose: str,
                        expected_revision: int, request_key: str | None = None,
                        recheck_authority: Callable[[], None] | None = None,
                        prepare_response: Callable[[dict], Any] | None = None):
        patient_id = _key(patient_id, "patient_id")
        self._allow(actor, patient_id, "patient_suspend", purpose)
        if type(expected_revision) is not int or expected_revision < 1:
            raise PatientRegistryError("expected_revision must be positive integer")
        if request_key is not None:
            request_key = _key(request_key, "request_key")
        fingerprint = _digest({"patient_id": patient_id, "actor": actor,
                               "purpose": purpose, "expected_revision": expected_revision})
        with self.transaction():
            # Serialize commands and exact retries on the canonical patient.
            # The immutable journal retains the receipt even after suspension.
            current = self._fetchone(
                "SELECT status,revision FROM identity.identity_patients "
                "WHERE patient_id=%s FOR UPDATE", (patient_id,),
            )
            if current is None:
                raise PatientRegistryDenied("unknown patient")
            self._allow(actor, patient_id, "patient_suspend", purpose)
            if recheck_authority is not None:
                recheck_authority()
            previous = None
            if request_key is not None:
                previous = self._fetchone(
                    "SELECT metadata_json->>'request_digest',metadata_json->>'revision' "
                    "FROM identity.identity_domain_events WHERE patient_id=%s "
                    "AND event_type='identity.patient.suspended' "
                    "AND metadata_json->>'request_key'=%s", (patient_id, request_key),
                )
            if previous is not None:
                if previous[0] != fingerprint:
                    raise PatientRegistryConflict("request key reused with different intent")
                revision = int(previous[1])
                if tuple(current) != ("suspended", revision) or revision != expected_revision + 1:
                    raise PatientRegistryConflict("suspension receipt does not match patient state")
            else:
                if tuple(current) != ("active", expected_revision):
                    raise PatientRegistryConflict("patient state/revision conflict")
                revision = expected_revision + 1
                self._execute(
                    "UPDATE identity.identity_patients SET status='suspended',revision=%s "
                    "WHERE patient_id=%s", (revision, patient_id),
                )
                details = {"actor": actor, "revision": revision}
                if request_key is not None:
                    details.update(request_key=request_key, request_digest=fingerprint,
                                   purpose=purpose)
                self._write_event(patient_id, "identity.patient.suspended", details)
            result = {"patient_id": patient_id, "revision": revision, "status": "suspended"}
            response = prepare_response(result) if prepare_response is not None else result
            if recheck_authority is not None:
                recheck_authority()
            self._allow(actor, patient_id, "patient_suspend", purpose)
            return response
