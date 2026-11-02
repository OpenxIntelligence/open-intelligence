"""Downstream quote-review regressions using original clinical/rights owners.

The fourth provider invocation is the last external read in the second
AuthorizedClinicalKnowledge snapshot. No network, model or real patient data.
"""
from __future__ import annotations

import unittest

import test_evidence_quote_review_integration as fixture
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.patient_registry import PatientRegistryDenied
from test_clinical_continuity import ACTOR, CASE, report


class ReviewParentFreshnessTests(unittest.TestCase):
    setUp = fixture.EvidenceQuoteReviewTests.setUp
    actor = fixture.EvidenceQuoteReviewTests.actor
    workflow = fixture.EvidenceQuoteReviewTests.workflow
    _source = fixture.EvidenceQuoteReviewTests._source
    prepare = fixture.EvidenceQuoteReviewTests.prepare
    setup_candidate = fixture.EvidenceQuoteReviewTests.setup_candidate
    quotes = fixture.EvidenceQuoteReviewTests.quotes

    def last_read(self, bridge, mutation):
        original = bridge.source_provider
        calls = []

        def provider(*args):
            payload = original(*args)
            calls.append(args)
            if len(calls) == 4:
                mutation()
            return payload

        bridge.source_provider = provider
        return calls

    def preview(self, obj, question, assertion):
        return obj.preview(self.patient_id, CASE, question,
                           selected_quotes=self.quotes(assertion), **self.actor())

    def test_final_review_read_amendment_rejects_stale_packet_then_refreshes(self):
        obj, bridge, question, _, assertion = self.setup_candidate()
        first = self.preview(obj, question, assertion)
        calls = self.last_read(bridge, lambda: self._source(
            'LAB-CONT-001', 'laboratory', 'result', 'indeterminate',
            specimen='SPEC-CONT-001', amendment=1))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            self.preview(obj, question, assertion)
        self.assertEqual(len(calls), 4)
        refreshed = self.preview(obj, question, assertion)
        self.assertNotEqual(first['composer_context_fingerprint'],
                            refreshed['composer_context_fingerprint'])
        self.assertEqual(refreshed['human_review_state'], 'pending')
        self.assertFalse(refreshed['action_authorized'])

    def test_final_review_read_new_report_cannot_escape_recheck(self):
        obj, bridge, question, _, assertion = self.setup_candidate()
        calls = self.last_read(bridge, lambda: self._source(
            'LATE-REVIEW-REPORT', 'clinical', 'reported-goal', 'reported'))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            self.preview(obj, question, assertion)
        self.assertEqual(len(calls), 4)
        self.assertTrue(any(s['document_id'] == 'LATE-REVIEW-REPORT'
                            for s in self.store.state(CASE)['sources']))

    def test_final_review_read_failed_qc_cannot_return_old_release_context(self):
        obj, bridge, question, _, assertion = self.setup_candidate()
        src = next(s['id'] for s in self.store.state(CASE)['sources']
                   if s['document_id'] == 'LAB-CONT-001')
        calls = self.last_read(bridge, lambda: self.bridge.command(
            self.patient_id, CASE, 'record_quality_check', 'ACC-CONT-001',
            'QC-QUOTE-REVIEW-002', src, 'failed', 'Fictional checker',
            **self.actor()))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            self.preview(obj, question, assertion)
        self.assertEqual(len(calls), 4)
        view = bridge.snapshot(self.patient_id, CASE, question, **self.actor())
        self.assertEqual(view['clinical_composer']['clinical']['lab_evidence_candidates'][0]
                         ['current_provenance_state'], 'quality_changed_review_required')

    def test_final_review_read_note_revision_cannot_return_old_projection(self):
        obj, bridge, question, _, assertion = self.setup_candidate()
        encounter = self.ehr.schedule(
            self.patient_id, 'ENCOUNTER-CONT-001', 'outpatient', '2026-11-02',
            request_key='ENC-REQUEST-001', **self.actor())['encounter_id']
        calls = self.last_read(bridge, lambda: self.ehr.write_note(
            self.patient_id, encounter, 'NOTE-CONT-001',
            'New original fictional note pending independent review.',
            expected_version=1, request_key='QUOTE-REVIEW-NOTE-002', **self.actor()))
        with self.assertRaisesRegex(ClinicalContinuityError, 'changed|stale|diverge'):
            self.preview(obj, question, assertion)
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(self.ehr.note_history(
            self.patient_id, encounter, 'NOTE-CONT-001', **self.actor())), 2)

    def test_final_review_read_binding_revocation_remains_denied(self):
        obj, bridge, question, _, assertion = self.setup_candidate()
        calls = self.last_read(bridge, lambda: self.bridge.revoke_case(
            patient_id=self.patient_id, case_id=CASE, actor=ACTOR, purpose='care',
            reason='Fictional revoked binding during final quote review read.'))
        with self.assertRaises(PatientRegistryDenied):
            self.preview(obj, question, assertion)
        self.assertEqual(len(calls), 4)

    def test_unrelated_case_change_does_not_block_or_leak_into_packet(self):
        obj, bridge, question, _, assertion = self.setup_candidate()
        other = 'CASE-CLIN-CONT-OTHER'
        raw = report('OTHER-QUOTE-REVIEW', 'clinical', 'context', 'reported')
        raw = raw.replace(f'Patient: {CASE}'.encode(), f'Patient: {other}'.encode())
        calls = self.last_read(bridge, lambda: self.store.import_report(other, raw))
        result = self.preview(obj, question, assertion)
        self.assertEqual(len(calls), 4)
        self.assertEqual(result['patient_id'], self.patient_id)
        self.assertNotIn('OTHER-QUOTE-REVIEW', str(result))
        self.assertEqual(len(self.store.state(other)['sources']), 1)

    def test_stable_review_preserves_exact_quote_and_does_not_write_or_authorize(self):
        obj, bridge, question, _, assertion = self.setup_candidate()
        calls = self.last_read(bridge, lambda: None)
        before = self.store.db.total_changes
        result = self.preview(obj, question, assertion)
        self.assertEqual(len(calls), 4)
        self.assertEqual(self.store.db.total_changes, before)
        row = result['quoted_comparisons'][0]
        self.assertEqual(row['external_reference']['exact_quote'], 'claims no therapeutic outcomes')
        self.assertEqual(row['patient_reference']['assertion_id'], assertion)
        self.assertEqual(row['evidence_review_state'], 'unreviewed_proposal')
        self.assertEqual(result['human_review_state'], 'pending')
        self.assertFalse(result['action_authorized'])
        self.assertFalse(result['model_executed'])
        self.assertFalse(result['clinical_conclusion_established'])
        self.assertEqual(result['snapshot_consistency'], 'sequential_preflight_not_cross_system_atomic')


if __name__ == '__main__':
    unittest.main()
