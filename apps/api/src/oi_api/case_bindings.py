"""Bounded, fictional patient/source-case reference mapping on canonical H1 registry.

Uses exactly the PostgresPatientRegistry connection, transaction and event owner.
The supplied 'review_ref' is a synthetic test label, not verified human approval;
no actual source record or clinical authority is introduced.
"""
from __future__ import annotations

from datetime import datetime
import json
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key, _digest,
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

    def _identity_table(self):
        return self.registry._fetchone("SELECT to_regclass('coordination.case_source_identities')")[0]

    def _identity_lock(self, organization, system, subject):
        # Also used by primary binding creation. Serialize qualified identities
        # across cases without exposing another patient's identifiers.
        self.registry._fetchone("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (json.dumps([organization, system, subject], separators=(",", ":")),))

    def source_identity(self, patient_id, case_id, *, organization, purpose,
                        identity_id=None):
        """Resolve inside the caller's case lock; never infer from an incoming file."""
        if not self.registry._transaction_active:
            raise PatientRegistryError("Source identity requires caller transaction")
        row = self.registry._fetchone(
            "SELECT source_organization,source_system,source_subject_ref FROM coordination.patient_case_bindings "
            "WHERE case_id=%s AND patient_id=%s AND origin_org=%s AND purpose=%s AND status='active'",
            (case_id, patient_id, organization, purpose))
        if row is None:
            raise PatientRegistryDenied("Source identity unavailable")
        if identity_id is None:
            return tuple(row)
        identity_id = _key(identity_id, "identity_id")
        row = self.registry._fetchone(
            "SELECT source_organization,source_system,source_subject_ref FROM coordination.case_source_identities "
            "WHERE identity_id=%s AND case_id=%s AND purpose=%s AND status='linked'",
            (identity_id, case_id, purpose))
        if row is None:
            raise PatientRegistryDenied("Source identity unavailable")
        return tuple(row)

    def _source_case(self, patient_id, case_id, organization, purpose):
        self._patient(patient_id, organization)
        row = self.registry._fetchone(
            "SELECT patient_id,origin_org,purpose,status FROM coordination.patient_case_bindings "
            "WHERE case_id=%s FOR UPDATE", (case_id,))
        if row is None or tuple(row) != (patient_id, organization, purpose, "active"):
            raise PatientRegistryDenied("Source identity unavailable")

    def check_source_origin(self, case_id, source_organization, source_system, source_subject_ref):
        """Validate immutable custody metadata against this case's source owner."""
        primary = self.registry._fetchone(
            "SELECT source_organization,source_system,source_subject_ref FROM coordination.patient_case_bindings WHERE case_id=%s",
            (case_id,))
        qualified = (source_organization,source_system,source_subject_ref)
        if primary is not None and tuple(primary) == qualified:
            return False
        if self._identity_table() and self.registry._fetchone(
            "SELECT identity_id FROM coordination.case_source_identities WHERE case_id=%s "
            "AND source_organization=%s AND source_system=%s AND source_subject_ref=%s AND status='linked'",
            (case_id,*qualified)) is not None:
            return True
        raise PatientRegistryError("Stored source identity is not linked to this case")

    @staticmethod
    def _identity_view(row):
        keys = ("identity_id", "source_organization", "source_system", "source_subject_ref",
                "review_ref", "created_by", "created_at", "status", "primary_identity")
        result = dict(zip(keys, row))
        result["created_at"] = row[6].isoformat()
        return result

    def list_source_identities(self, patient_id, case_id, *, organization, actor, purpose,
                               prepare_response, recheck_authority):
        with self.registry.transaction():
            self._source_case(patient_id, case_id, organization, purpose)
            rows = self.registry._fetchall(
                "SELECT identity_id,source_organization,source_system,source_subject_ref,review_ref,"
                "created_by,created_at,status,primary_identity FROM coordination.case_source_identities "
                "WHERE case_id=%s ORDER BY created_at,identity_id LIMIT 65", (case_id,))
            if len(rows) > 64:
                raise PatientRegistryError("Source identity history exceeds supported bounds")
            result = prepare_response({"patient_id":patient_id,"case_id":case_id,
                "identities":[self._identity_view(row) for row in rows]})
            recheck_authority()
            self.registry.append_event(patient_id, "identity.source_identities_read", case_id=case_id,
                                       actor=actor, purpose=purpose)
            recheck_authority()
            return result

    def add_source_identity(self, patient_id, case_id, *, organization, actor, purpose,
                            source_organization, source_system, source_subject_ref,
                            review_ref, request_key, prepare_response, recheck_authority):
        patient_id, organization, actor = (_key(patient_id,"patient_id"),
            _key(organization,"organization"),_key(actor,"actor"))
        case_id = _case_id(case_id)
        source_organization, source_system, source_subject_ref, review_ref, request_key = (
            _key(value, name) for name,value in (("source_organization",source_organization),
            ("source_system",source_system),("source_subject_ref",source_subject_ref),
            ("review_ref",review_ref),("request_key",request_key)))
        if request_key == "primary":
            raise PatientRegistryError("Reserved request key")
        digest = _digest({"patient_id":patient_id,"case_id":case_id,"organization":organization,
            "actor":actor,"purpose":purpose,"source_organization":source_organization,
            "source_system":source_system,"source_subject_ref":source_subject_ref,"review_ref":review_ref})
        with self.registry.transaction():
            self._source_case(patient_id,case_id,organization,purpose)
            command = self.registry._fetchone(
                "SELECT identity_id,status,request_digest FROM coordination.case_source_identities "
                "WHERE case_id=%s AND request_key=%s", (case_id,request_key))
            duplicate = command is not None
            if command is not None:
                if command[2] != digest:
                    raise PatientRegistryConflict("Source identity request intent changed")
                identity_id, status = command[:2]
            else:
                count = self.registry._fetchone("SELECT count(*) FROM coordination.case_source_identities WHERE case_id=%s",(case_id,))[0]
                if count >= 64:
                    raise PatientRegistryConflict("Source identity limit reached")
                self._identity_lock(source_organization,source_system,source_subject_ref)
                existing = self.registry._fetchone(
                    "SELECT case_id FROM coordination.case_source_identities WHERE source_organization=%s "
                    "AND source_system=%s AND source_subject_ref=%s AND status='linked'",
                    (source_organization,source_system,source_subject_ref))
                if existing is not None and existing[0] == case_id:
                    raise PatientRegistryConflict("Source identity already linked to this case")
                status = "quarantined" if existing is not None else "linked"
                identity_id = "IDENT-" + uuid.uuid4().hex.upper()
                self.registry._execute(
                    "INSERT INTO coordination.case_source_identities "
                    "(identity_id,case_id,source_organization,source_system,source_subject_ref,review_ref,"
                    "created_by,purpose,status,request_key,request_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (identity_id,case_id,source_organization,source_system,source_subject_ref,review_ref,
                     actor,purpose,status,request_key,digest))
                self.registry.append_event(patient_id, "identity.source_identity_recorded",case_id=case_id,
                    identity_id=identity_id, actor=actor,purpose=purpose,status=status)
            result = prepare_response({"patient_id":patient_id,"case_id":case_id,"identity_id":identity_id,
                "status":status,"duplicate":duplicate,"source_identity_verified":False})
            recheck_authority()
            return result

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
            if self._identity_table():
                self._identity_lock(source_organization, source_system, source_subject_ref)
                if self.registry._fetchone(
                    "SELECT identity_id FROM coordination.case_source_identities WHERE source_organization=%s "
                    "AND source_system=%s AND source_subject_ref=%s AND status='linked'",
                    (source_organization,source_system,source_subject_ref)) is not None:
                    raise PatientRegistryConflict("External source identity already linked")
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
