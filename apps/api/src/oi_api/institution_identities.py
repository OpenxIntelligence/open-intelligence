"""Qualified identity proposals; the canonical case binding owns patient/purpose."""
from __future__ import annotations
import uuid
from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from .case_bindings import CanonicalCaseBindings, _case_id


class CaseInstitutionIdentities:
    def __init__(self, registry):
        self.registry = registry
        self.bindings = CanonicalCaseBindings(registry)

    def _scope(self, patient_id, case_id, organization, purpose):
        self.bindings._patient(patient_id, organization)
        # Same case lock as source writes. Review cannot race source import or case revoke.
        row = self.registry._fetchone(
            "SELECT 1 FROM coordination.patient_case_bindings WHERE case_id=%s "
            "AND patient_id=%s AND origin_org=%s AND purpose=%s AND status='active' FOR UPDATE",
            (_case_id(case_id), _key(patient_id, 'patient_id'), organization, purpose))
        if row is None:
            raise PatientRegistryDenied('Institution mapping unavailable')

    def _view(self, row):
        return dict(zip(('identity_id', 'source_organization', 'source_system', 'source_subject_ref',
                         'primary_identity', 'status', 'review_ref'), row))

    def _row(self, case_id, identity_id):
        return self.registry._fetchone(
            "SELECT identity_id,source_organization,source_system,source_subject_ref,"
            "primary_identity,status,review_ref FROM coordination.case_source_identities "
            "WHERE case_id=%s AND identity_id=%s", (case_id, identity_id))

    def list(self, patient_id, case_id, *, organization, purpose, prepare_result):
        with self.registry.transaction():
            self._scope(patient_id, case_id, organization, purpose)
            rows = self.registry._fetchall(
                "SELECT identity_id,source_organization,source_system,source_subject_ref,"
                "primary_identity,status,review_ref FROM coordination.case_source_identities "
                "WHERE case_id=%s ORDER BY primary_identity DESC,created_at,identity_id LIMIT 101", (case_id,))
            if len(rows)>100:
                raise PatientRegistryError('Identity list exceeds supported limit')
            return prepare_result({'patient_id': patient_id, 'case_id': case_id,
                                   'identities': [self._view(row) for row in rows]})

    def propose(self, patient_id, case_id, *, organization, purpose, actor, request_key,
                source_organization, source_system, source_subject_ref, prepare_result):
        fields = {name: _key(value, name) for name, value in (
            ('request_key', request_key), ('source_organization', source_organization),
            ('source_system', source_system), ('source_subject_ref', source_subject_ref))}
        if request_key == 'PRIMARY':
            raise PatientRegistryError('Reserved request key')
        intent = _digest({**fields, 'patient_id': patient_id, 'case_id': case_id,
                          'organization': organization, 'purpose': purpose, 'actor': actor})
        with self.registry.transaction():
            self._scope(patient_id, case_id, organization, purpose)
            prior = self.registry._fetchone(
                "SELECT identity_id,request_digest FROM coordination.case_source_identities "
                "WHERE case_id=%s AND request_key=%s", (case_id, request_key))
            if prior:
                if prior[1] != intent:
                    raise PatientRegistryConflict('Identity proposal intent changed')
                return prepare_result({'identity': self._view(self._row(case_id, prior[0])), 'duplicate': True})
            count = self.registry._fetchone(
                "SELECT count(*) FROM coordination.case_source_identities WHERE case_id=%s", (case_id,))[0]
            if count >= 100:
                raise PatientRegistryConflict('Identity review queue is full')
            identity_id = 'IDENTITY-' + uuid.uuid4().hex.upper()
            self.registry._execute(
                "INSERT INTO coordination.case_source_identities "
                "(identity_id,case_id,source_organization,source_system,source_subject_ref,"
                "request_key,request_digest,created_by,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'quarantined')",
                (identity_id, case_id, source_organization, source_system, source_subject_ref,
                 request_key, intent, actor))
            self.registry.append_event(patient_id, 'identity.institution_proposed', case_id=case_id,
                                       identity_id=identity_id, actor=actor, purpose=purpose)
            return prepare_result({'identity': self._view(self._row(case_id, identity_id)), 'duplicate': False})

    def decide(self, patient_id, case_id, identity_id, *, organization, purpose, actor,
               decision, review_ref, prepare_result):
        review_ref = _key(review_ref, 'review_ref')
        if decision not in ('link', 'reject'):
            raise PatientRegistryError('Unsupported identity decision')
        target = 'active' if decision == 'link' else 'rejected'
        with self.registry.transaction():
            self._scope(patient_id, case_id, organization, purpose)
            row = self._row(case_id, identity_id)
            if row is None:
                raise PatientRegistryDenied('Institution mapping unavailable')
            if row[5] != 'quarantined':
                reviewer = self.registry._fetchone(
                    "SELECT reviewed_by FROM coordination.case_source_identities WHERE identity_id=%s", (identity_id,))[0]
                if row[4] or (row[5],row[6],reviewer)!=(target,review_ref,actor):
                    raise PatientRegistryConflict('Identity decision changed')
                return prepare_result({'identity': self._view(row), 'duplicate': True})
            # Global qualified-subject lock serializes competing case decisions without
            # revealing another case/patient. Unique indexes remain the final DB guard.
            if target == 'active':
                self.registry._fetchone('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                    (_digest({'org':row[1],'system':row[2],'subject':row[3]}),))
                conflict = self.registry._fetchone(
                    "SELECT 1 FROM coordination.case_source_identities WHERE status='active' AND "
                    "((source_organization=%s AND source_system=%s AND source_subject_ref=%s) OR "
                    "(case_id=%s AND source_organization=%s AND source_system=%s)) LIMIT 1",
                    (row[1], row[2], row[3], case_id, row[1], row[2]))
                if conflict:
                    raise PatientRegistryConflict('Identity remains quarantined; reviewed linkage conflicts')
            self.registry._execute(
                "UPDATE coordination.case_source_identities SET status=%s,review_ref=%s,"
                "reviewed_by=%s,reviewed_at=now() WHERE identity_id=%s AND status='quarantined'",
                (target, review_ref, actor, identity_id))
            self.registry.append_event(patient_id, 'identity.institution_decided', case_id=case_id,
                identity_id=identity_id, decision=decision, review_ref=review_ref, actor=actor, purpose=purpose)
            return prepare_result({'identity': self._view(self._row(case_id, identity_id)), 'duplicate': False})
