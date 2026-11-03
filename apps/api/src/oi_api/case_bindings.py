"""Bounded, fictional patient/source-case reference mapping on canonical H1 registry.

Uses exactly the PostgresPatientRegistry connection, transaction and event owner.
The supplied 'review_ref' is a synthetic test label, not verified human approval;
no actual source record or clinical authority is introduced.
"""
from __future__ import annotations

from datetime import datetime

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .record_requests import _label, PostgresRecordRequests


def _case_id(raw: object) -> str:
    import re
    if type(raw) is not str or re.fullmatch(r"CASE-[A-Z0-9-]{1,35}", raw) is None:
        raise PatientRegistryError("Invalid fictional case reference")
    return raw


class CanonicalCaseBindings:
    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Existing patient registry required")
        self.registry = registry

    def _patient(self, patient_id: str, organization: str):
        # Use the same active patient and origin check as the request owner;
        # FOR SHARE keeps patient suspension from racing the write transaction.
        PostgresRecordRequests(self.registry)._active_patient(patient_id, organization)

    @staticmethod
    def _view(row: tuple) -> dict:
        (case_id, patient_id, source_organization, source_system, source_subject_ref,
         review_ref, status, revision, created_at, revoked_at) = row
        return {
            "case_id": case_id, "patient_id": patient_id,
            "source_organization": source_organization,
            "source_system": source_system,
            "source_subject_ref": source_subject_ref,
            "review_ref": review_ref, "status": status,
            "revision": revision,
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            "revoked_at": (revoked_at.isoformat() if isinstance(revoked_at, datetime)
                           else str(revoked_at) if revoked_at is not None else None),
            "source_identity_verified": False,
            "clinical_sources_linked": False,
            "clinical_conclusions": False,
        }

    def list(self, patient_id: str, *, organization: str) -> list[dict]:
        patient_id = _key(patient_id, "patient_id")
        organization = _key(organization, "organization")
        with self.registry.transaction():
            self._patient(patient_id, organization)
            rows = self.registry._fetchall(
                "SELECT case_id,patient_id,source_organization,source_system,"
                "source_subject_ref,review_ref,status,revision,created_at,revoked_at "
                "FROM coordination.patient_case_bindings "
                "WHERE patient_id=%s AND origin_org=%s ORDER BY case_id",
                (patient_id, organization),
            )
            return [self._view(row) for row in rows]

    def bind(self, patient_id: str, *, organization: str, actor: str, purpose: str,
             case_id: str, source_organization: str, source_system: str,
             source_subject_ref: str, review_ref: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        case_id = _case_id(case_id)
        source_organization = _key(source_organization, "source_organization")
        source_system = _key(source_system, "source_system")
        source_subject_ref = _key(source_subject_ref, "source_subject_ref")
        review_ref = _key(review_ref, "review_ref")
        if purpose not in ("operations", "research"):
            raise PatientRegistryError("Invalid synthetic mapping purpose")
        with self.registry.transaction():
            self._patient(patient_id, organization)
            current = self.registry._fetchone(
                "SELECT patient_id,origin_org,source_organization,source_system,"
                "source_subject_ref,review_ref,created_by,purpose,status "
                "FROM coordination.patient_case_bindings WHERE case_id=%s",
                (case_id,),
            )
            intent = (patient_id, organization, source_organization, source_system,
                      source_subject_ref, review_ref, actor, purpose)
            if current is not None:
                if tuple(current[:8]) != intent or current[8] != "active":
                    raise PatientRegistryConflict("Case reference is already bound or revoked")
                return {"case_id": case_id, "patient_id": patient_id,
                        "duplicate": True, "source_identity_verified": False}
            # The unique qualified external subject prevents silent many-to-many
            # reuse. Do not infer identity from subject text; this is a fixture.
            inserted = self.registry._fetchone(
                "INSERT INTO coordination.patient_case_bindings "
                "(case_id,patient_id,origin_org,source_organization,source_system,"
                "source_subject_ref,review_ref,created_by,purpose) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING case_id",
                (case_id, *intent),
            )
            if inserted is None:
                # Only a genuine uniqueness collision is a conflict; arbitrary
                # SQL/network failures must propagate to the unavailable path.
                # Re-read after a concurrent identical bind commits.
                conflicting = self.registry._fetchone(
                    "SELECT patient_id,origin_org,source_organization,source_system,"
                    "source_subject_ref,review_ref,created_by,purpose,status "
                    "FROM coordination.patient_case_bindings WHERE case_id=%s",
                    (case_id,),
                )
                if conflicting is not None and tuple(conflicting[:8]) == intent and conflicting[8] == "active":
                    return {"case_id": case_id, "patient_id": patient_id,
                            "duplicate": True, "source_identity_verified": False}
                raise PatientRegistryConflict("Case or external subject is already linked")
            self.registry.append_event(
                patient_id, "identity.case_binding_created",
                case_id=case_id, actor=actor, review_ref=review_ref,
            )
            return {"case_id": case_id, "patient_id": patient_id,
                    "duplicate": False, "source_identity_verified": False}

    def revoke(self, patient_id: str, case_id: str, *,
               organization: str, actor: str, reason: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        reason = _label(reason, 200)
        if len(reason) < 10:
            raise PatientRegistryError("A meaningful revocation reason is required")
        with self.registry.transaction():
            self._patient(patient_id, organization)
            row = self.registry._fetchone(
                "SELECT status,revision FROM coordination.patient_case_bindings "
                "WHERE patient_id=%s AND origin_org=%s AND case_id=%s FOR UPDATE",
                (patient_id, organization, case_id),
            )
            if row is None:
                raise PatientRegistryDenied("Case binding unavailable")
            if row[0] == "revoked":
                return {"case_id": case_id, "patient_id": patient_id,
                        "duplicate": True, "source_identity_verified": False}
            if row[0] != "active" or row[1] != 1:
                raise PatientRegistryConflict("Case binding state changed")
            self.registry._execute(
                "UPDATE coordination.patient_case_bindings "
                "SET status='revoked',revision=2,revoked_at=now(),"
                "revoked_by=%s,revocation_reason=%s "
                "WHERE case_id=%s AND patient_id=%s AND status='active'",
                (actor, reason, case_id, patient_id),
            )
            self.registry.append_event(
                patient_id, "identity.case_binding_revoked",
                case_id=case_id, actor=actor,
            )
            return {"case_id": case_id, "patient_id": patient_id,
                    "duplicate": False, "source_identity_verified": False}
