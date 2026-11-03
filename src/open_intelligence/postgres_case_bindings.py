"""Synthetic reviewed case-link persistence on canonical PostgreSQL."""
from .patient_registry import PatientRegistryDenied, PatientRegistryError, _key
from .postgres_registry import PostgresPatientRegistry


class CaseBindingConflict(PatientRegistryError):
    pass


class PostgresCaseBindings:
    def __init__(self, registry, authorize, verify_source):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL registry required")
        self.registry = registry
        self.authorize = authorize
        self.verify_source = verify_source

    def _gate(self, actor, patient_id, action, purpose):
        _key(actor, "actor")
        _key(patient_id, "patient_id")
        try:
            allowed = purpose == "operations" and self.authorize(
                actor, patient_id, action, purpose) is True
        except Exception:
            allowed = False
        if not allowed:
            raise PatientRegistryDenied("Binding unavailable")

    def _source(self, source_store_id, case_id, organization, system, subject, patient_id):
        try:
            valid = self.verify_source(
                source_store_id, case_id, organization, system, subject, patient_id
            ) is True
        except Exception:
            valid = False
        if not valid:
            raise PatientRegistryDenied("Source identity unavailable")

    def bind(self, *, patient_id, source_store_id, case_id,
             source_organization, source_system, source_subject_ref,
             review_ref, actor, purpose):
        for name, value in {
            "patient_id": patient_id, "source_store_id": source_store_id,
            "case_id": case_id, "source_organization": source_organization,
            "source_system": source_system, "source_subject_ref": source_subject_ref,
            "review_ref": review_ref, "actor": actor,
        }.items():
            _key(value, name)
        self._gate(actor, patient_id, "case_bind", purpose)
        self._source(source_store_id, case_id, source_organization,
                     source_system, source_subject_ref, patient_id)
        with self.registry.transaction():
            self._gate(actor, patient_id, "case_bind", purpose)
            self.registry.require_patient(patient_id)
            self._source(source_store_id, case_id, source_organization,
                         source_system, source_subject_ref, patient_id)
            previous = self.registry._fetchone(
                "SELECT patient_id,source_organization,source_system,"
                "source_subject_ref,review_ref,status "
                "FROM identity.identity_case_bindings "
                "WHERE source_store_id=%s AND case_id=%s FOR UPDATE",
                (source_store_id, case_id))
            signature = (patient_id,source_organization,source_system,
                         source_subject_ref,review_ref)
            if previous is not None:
                if tuple(previous[:5]) != signature or previous[5] != "active":
                    raise CaseBindingConflict("Case cannot be reassigned")
                return dict(patient_id=patient_id,case_id=case_id,
                            source_store_id=source_store_id,duplicate=True)
            inserted = self.registry._fetchone(
                "INSERT INTO identity.identity_case_bindings "
                "(source_store_id,case_id,patient_id,source_organization,"
                "source_system,source_subject_ref,review_ref,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING case_id",
                (source_store_id,case_id,patient_id,source_organization,
                 source_system,source_subject_ref,review_ref,actor))
            if inserted is None:
                raise CaseBindingConflict("Source or case already linked")
            self.registry._write_event(patient_id,"identity.case_binding_created",
                dict(source_store_id=source_store_id,case_id=case_id,
                     review_ref=review_ref,actor=actor))
            return dict(patient_id=patient_id,case_id=case_id,
                        source_store_id=source_store_id,duplicate=False)

    def revoke(self, *, patient_id, source_store_id, case_id,
               actor, purpose, reason):
        for name,value in {"patient_id":patient_id,
                           "source_store_id":source_store_id,
                           "case_id":case_id,"actor":actor}.items():
            _key(value,name)
        if not isinstance(reason,str) or not 10 <= len(reason.strip()) <= 200:
            raise PatientRegistryError("Revocation reason required")
        self._gate(actor,patient_id,"case_revoke",purpose)
        with self.registry.transaction():
            self._gate(actor,patient_id,"case_revoke",purpose)
            self.registry.require_patient(patient_id)
            # Conflicted source identity must never block revocation.
            row=self.registry._fetchone(
                "UPDATE identity.identity_case_bindings SET "
                "status='revoked',revoked_by=%s,revoked_at=now(),"
                "revocation_reason=%s WHERE source_store_id=%s "
                "AND case_id=%s AND patient_id=%s AND status='active' "
                "RETURNING case_id",
                (actor,reason.strip(),source_store_id,case_id,patient_id))
            if row is None:
                raise PatientRegistryDenied("Binding unavailable")
            self.registry._write_event(patient_id,"identity.case_binding_revoked",
                dict(source_store_id=source_store_id,case_id=case_id,actor=actor))

    def resolve(self, *, patient_id, source_store_id, case_id, actor, purpose):
        for name,value in {"patient_id":patient_id,
                           "source_store_id":source_store_id,
                           "case_id":case_id,"actor":actor}.items():
            _key(value,name)
        self._gate(actor,patient_id,"case_read",purpose)
        with self.registry.transaction():
            self.registry.require_patient(patient_id)
            row=self.registry._fetchone(
                "SELECT source_organization,source_system,source_subject_ref,status "
                "FROM identity.identity_case_bindings WHERE patient_id=%s "
                "AND source_store_id=%s AND case_id=%s",
                (patient_id,source_store_id,case_id))
            if row is None or row[3] != "active":
                raise PatientRegistryDenied("Binding unavailable")
            self._source(source_store_id,case_id,row[0],row[1],row[2],patient_id)
            self._gate(actor,patient_id,"case_read",purpose)
            return dict(patient_id=patient_id,case_id=case_id,
                        source_store_id=source_store_id,status="active",
                        source_organization=row[0],source_system=row[1],
                        source_subject_ref=row[2])
