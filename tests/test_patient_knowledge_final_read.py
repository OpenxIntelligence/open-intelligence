"""Final provider-read regressions over real first-party synthetic modules.

No network, patient data, clinical conclusions or new domain state. The provider
callback simulates a change becoming visible during its final rights read.
"""
from __future__ import annotations

import unittest

import test_patient_clinical_knowledge_integration as fixture
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.patient_registry import PatientRegistryDenied
from test_clinical_continuity import ACTOR, CASE, report


class FinalKnowledgeReadTests(unittest.TestCase):
    setUp = fixture.AuthorizedPatientEvidenceIntegrationTests.setUp
    actor = fixture.AuthorizedPatientEvidenceIntegrationTests.actor
    workflow = fixture.AuthorizedPatientEvidenceIntegrationTests.workflow
    _source = fixture.AuthorizedPatientEvidenceIntegrationTests._source
    prepare = fixture.AuthorizedPatientEvidenceIntegrationTests.prepare

    def during_final_provider_read(self, bridge, mutation):
        original = bridge.source_provider
        calls = []

        def provider(*args):
            payload = original(*args)
            calls.append(args)
            if len(calls) == 2:
                mutation()
            return payload

        bridge.source_provider = provider
        return calls

    def test_final_provider_read_amendment_denies_old_assertions_then_allows_fresh_retry(self):
        bridge, question, _, _ = self.prepare()
        calls = self.during_final_provider_read(bridge, lambda: self._source(
            'LAB-CONT-001', 'laboratory', 'result', 'indeterminate',
            specimen='SPEC-CONT-001', amendment=1))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertEqual(len(calls), 2)
        latest = bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        lab = next(a for a in latest['knowledge']['patient_assertions']
                   if a['source_document'] == 'LAB-CONT-001')
        self.assertEqual(lab['reported_state'], 'indeterminate')
        self.assertEqual(lab['version'], 2)
        self.assertEqual(latest['review_state'], 'pending_human_evidence_review')
        self.assertFalse(latest['model_execution_authorized'])

    def test_final_provider_read_new_source_denies_incomplete_packet(self):
        bridge, question, _, _ = self.prepare()
        self.during_final_provider_read(bridge, lambda: self._source(
            'LATER-CONT-001', 'clinical', 'reported-goal', 'reported'))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertTrue(any(s['document_id'] == 'LATER-CONT-001'
                            for s in self.store.state(CASE)['sources']))

    def test_final_provider_read_qc_change_denies_old_release_status(self):
        bridge, question, _, _ = self.prepare()
        source_id = next(s['id'] for s in self.store.state(CASE)['sources']
                         if s['document_id'] == 'LAB-CONT-001')
        self.during_final_provider_read(bridge, lambda: self.bridge.command(
            self.patient_id, CASE, 'record_quality_check', 'ACC-CONT-001',
            'QC-FINAL-READ-002', source_id, 'failed', 'Fictional checker',
            **self.actor()))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        fresh = bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        candidate = fresh['clinical_composer']['clinical']['lab_evidence_candidates'][0]
        self.assertEqual(candidate['current_provenance_state'], 'quality_changed_review_required')

    def test_final_provider_read_note_revision_denies_old_clinical_context(self):
        bridge, question, _, _ = self.prepare()
        encounter_id = self.ehr.schedule(
            self.patient_id, 'ENCOUNTER-CONT-001', 'outpatient', '2026-11-02',
            request_key='ENC-REQUEST-001', **self.actor())['encounter_id']
        self.during_final_provider_read(bridge, lambda: self.ehr.write_note(
            self.patient_id, encounter_id, 'NOTE-CONT-001',
            'Revised authored fictional note, not a clinical interpretation.',
            expected_version=1, request_key='NOTE-FINAL-READ-002', **self.actor()))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertEqual(len(self.ehr.note_history(
            self.patient_id, encounter_id, 'NOTE-CONT-001', **self.actor())), 2)

    def test_final_provider_read_binding_revocation_still_denies(self):
        bridge, question, _, _ = self.prepare()
        self.during_final_provider_read(bridge, lambda: self.bridge.revoke_case(
            patient_id=self.patient_id, case_id=CASE, actor=ACTOR, purpose='care',
            reason='Fictional case link revoked during the final evidence read.'))
        with self.assertRaises(PatientRegistryDenied):
            bridge.snapshot(self.patient_id, CASE, question, **self.actor())

    def test_unrelated_case_update_does_not_invalidate_this_patient_packet(self):
        bridge, question, _, _ = self.prepare()
        other = 'CASE-CLIN-CONT-OTHER'
        raw = report('OTHER-FINAL-READ', 'clinical', 'context', 'reported')
        raw = raw.replace(f'Patient: {CASE}'.encode(), f'Patient: {other}'.encode())
        self.during_final_provider_read(bridge, lambda: self.store.import_report(other, raw))
        result = bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertEqual(result['patient_id'], self.patient_id)
        self.assertNotIn('OTHER-FINAL-READ', str(result))
        self.assertEqual(len(self.store.state(other)['sources']), 1)

    def test_stable_final_provider_read_is_read_only_and_not_model_authority(self):
        bridge, question, _, _ = self.prepare()
        calls = self.during_final_provider_read(bridge, lambda: None)
        before = self.store.db.total_changes
        result = bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.store.db.total_changes, before)
        self.assertEqual(result['snapshot_consistency'], 'non_atomic_cross_domain_preflight_only')
        self.assertFalse(result['clinical_conclusion_established'])
        self.assertFalse(result['model_execution_authorized'])
        self.assertNotIn('Unverified fictional clinical note text', str(result))


if __name__ == '__main__':
    unittest.main()
