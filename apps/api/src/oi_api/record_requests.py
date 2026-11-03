"""First-party synthetic PostgreSQL record-acquisition requests.

Uses the source-owned PostgresPatientRegistry transaction and immutable
identity_domain_events ledger. No patient identity or clinical source copy.
Only request/cancellation are possible: H1 has no canonical clinical source
version table yet, so "received" is deliberately not an API action.
"""
from __future__ import annotations

from datetime import datetime
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
    _digest, _key, _now,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

KINDS = frozenset(("clinical", "pathology", "laboratory", "imaging", "molecular", "other"))


def _label(value: str, max_size: int) -> str:
    if (not isinstance(value, str) or not value.strip()
            or len(value.strip()) > max_size
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise PatientRegistryError("Invalid fictional record request")
    return value.strip()


class PostgresRecordRequests:
    """Operational request state keyed to the single canonical patient."""

    def __init__(self, patients: PostgresPatientRegistry):
        if not isinstance(patients, PostgresPatientRegistry):
            raise TypeError("Canonical patient registry required")
        self.patients = patients

    def _active_patient(self, patient_id: str, organization: str) -> None:
        # Row lock prevents a concurrent patient suspension until the command
        # commits; the policy was independently checked at the route boundary.
        row = self.patients._fetchone(
            "SELECT origin_org,status FROM identity.identity_patients "
            "WHERE patient_id=%s FOR SHARE", (patient_id,),
        )
        if row is None or row[0] != organization or row[1] != "active":
            raise PatientRegistryDenied("Patient unavailable")

    def _record(self, row: tuple) -> dict:
        (request_id, patient_id, kind, record_label, provider, status, revision,
         created_at, updated_at) = row
        return {
            "request_id": request_id, "patient_id": patient_id,
            "kind": kind, "record_label": record_label,
            "source_organization": provider, "status": status,
            "revision": revision,
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at),
            "receipt_status": "unavailable_until_canonical_source_contract",
            "external_request_sent": False,
        }

    def list(self, patient_id: str, *, organization: str) -> list[dict]:
        patient_id = _key(patient_id, "patient_id")
        organization = _key(organization, "organization")
        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            rows = self.patients._fetchall(
                "SELECT request_id,patient_id,kind,record_label,source_organization,"
                "status,revision,created_at,updated_at "
                "FROM coordination.record_requests WHERE patient_id=%s AND origin_org=%s "
                "ORDER BY created_at,request_id", (patient_id, organization),
            )
            return [self._record(row) for row in rows]

    def create(self, patient_id: str, *, organization: str, actor: str, purpose: str,
               request_key: str, kind: str, record_label: str,
               source_organization: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _key(request_key, "request_key")
        if type(kind) is not str or kind not in KINDS:
            raise PatientRegistryError("Invalid fictional source category")
        record_label = _label(record_label, 140)
        source_organization = _label(source_organization, 100)
        if purpose not in ("operations", "research"):
            raise PatientRegistryError("Invalid purpose")
        digest = _digest({
            "patient": patient_id, "org": organization, "actor": actor,
            "purpose": purpose, "kind": kind, "record_label": record_label,
            "source_organization": source_organization,
        })
        request_id = "RECORD-" + uuid.uuid4().hex.upper()
        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            row = self.patients._fetchone(
                "INSERT INTO coordination.record_requests "
                "(request_id,patient_id,origin_org,request_key,intent_sha256,kind,"
                "record_label,source_organization,actor,purpose,status,revision) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'requested',1) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING request_id",
                (request_id, patient_id, organization, request_key, digest, kind,
                 record_label, source_organization, actor, purpose),
            )
            if row is None:
                old = self.patients._fetchone(
                    "SELECT request_id,intent_sha256 FROM coordination.record_requests "
                    "WHERE patient_id=%s AND request_key=%s", (patient_id, request_key),
                )
                if old is None or old[1] != digest:
                    raise PatientRegistryConflict("Request key reused with changed intent")
                return {"request_id": old[0], "duplicate": True}
            self.patients.append_event(
                patient_id, "record.request.created",
                request_id=request_id, actor=actor, revision=1,
            )
            return {"request_id": request_id, "duplicate": False}

    def cancel(self, patient_id: str, request_id: str, *,
               organization: str, actor: str, reason: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        request_id = _key(request_id, "request_id")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        reason = _label(reason, 200)
        with self.patients.transaction():
            self._active_patient(patient_id, organization)
            row = self.patients._fetchone(
                "SELECT status,revision FROM coordination.record_requests "
                "WHERE request_id=%s AND patient_id=%s AND origin_org=%s FOR UPDATE",
                (request_id, patient_id, organization),
            )
            if row is None:
                raise PatientRegistryDenied("Record request unavailable")
            if row[0] == "cancelled":
                return {"request_id": request_id, "duplicate": True}
            if row != ("requested", 1):
                raise PatientRegistryConflict("Record request state changed")
            changed = self.patients._fetchone(
                "UPDATE coordination.record_requests SET status='cancelled',revision=2,"
                "cancellation_reason=%s,updated_at=now() "
                "WHERE request_id=%s AND patient_id=%s AND status='requested' "
                "RETURNING request_id", (reason, request_id, patient_id),
            )
            if changed is None:
                raise PatientRegistryConflict("Record request state changed")
            self.patients.append_event(
                patient_id, "record.request.cancelled",
                request_id=request_id, actor=actor, revision=2,
            )
            return {"request_id": request_id, "duplicate": False}
