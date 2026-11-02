"""Actual synthetic report/receipt integration; no external data or clinical review."""
import hashlib
import json
import unittest
from unittest.mock import patch

import test_authorized_evidence_review_handoff as fixture
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.evidence_review_report import EvidenceReviewReport
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.store import CaseStore, InvalidInput


class ReportReviewHandoffTests(unittest.TestCase):
    setUp = fixture.ReviewHandoffTests.setUp
    actor = fixture.ReviewHandoffTests.actor
    workflow = fixture.ReviewHandoffTests.workflow
    _source = fixture.ReviewHandoffTests._source
    prepare = fixture.ReviewHandoffTests.prepare
    candidate = fixture.ReviewHandoffTests.candidate

    def setup_service(self):
        from open_intelligence.evidence_report_handoff import ReportReviewHandoff
        handoff, q, assessment, sources, quotes = self.candidate()
        for part in ('metadata', 'full_text'):
            sources[0]['permissions'][part]['redistribute'] = 'allowed'
        renderer = EvidenceReviewReport(handoff.packet, export_authorizer=lambda a, p, op, purpose:
            a == self.actor()['actor'] and p == self.patient_id
            and op == 'evidence_report.export' and purpose == 'care')
        return ReportReviewHandoff(renderer, handoff), q, assessment, sources, quotes

    def call(self, service, q, assessment, quotes, **kwargs):
        args = dict(patient_id=self.patient_id, case_id=fixture.CASE,
                    question_id=q, assessment_id=assessment, selected_quotes=quotes,
                    reason='Independent fictional appraisal remains necessary.', **self.actor())
        args.update(kwargs)
        return service.return_for_review(**args)

    def test_nonboolean_review_grant_denies_before_source_access(self):
        handoff, q, assessment, _, quotes = self.candidate()
        for value in (1, 'denied', {'allowed': False}, [False]):
            handoff.return_authorizer = lambda *args, v=value: v
            with self.subTest(value=value), patch.object(handoff.packet.bridge, 'source_provider', wraps=handoff.packet.bridge.source_provider) as provider:
                with self.assertRaises(PermissionError):
                    handoff.return_for_review(self.patient_id, fixture.CASE, q, assessment,
                        selected_quotes=quotes, reason='Fictional independent review is needed.', **self.actor())
                provider.assert_not_called()
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_report_hash_and_current_source_bind_to_existing_atomic_receipt(self):
        service, q, assessment, _, quotes = self.setup_service()
        result = self.call(service, q, assessment, quotes)
        report, receipt = result['report'], result['receipt']
        self.assertEqual(hashlib.sha256(report['body'].encode()).hexdigest(), report['body_sha256'])
        self.assertEqual(receipt['result'], 'returned_for_independent_review')
        self.assertFalse(result['clinical_signoff'])
        self.assertEqual(report['human_review_state'], 'pending')
        queue = self.store.review_queue(fixture.CASE)
        self.assertEqual(len(queue['receipts']), 1)
        self.assertEqual(queue['receipts'][0]['action'], 'returned')
        self.assertTrue(any(i['queue_key'] == receipt['queue_key'] for i in queue['awaiting']))
        event = next(e for e in self.store.state(fixture.CASE)['events']
                     if e['kind'] == 'review_receipt_recorded')
        details = json.loads(event['details'])
        reference = details['prepared_report']
        self.assertEqual(details['receipt_id'], receipt['receipt_id'])
        self.assertEqual(reference['body_sha256'], report['body_sha256'])
        self.assertEqual(reference['packet_sha256'], report['packet_sha256'])
        self.assertEqual(reference['patient_source']['assertion_id'], quotes[0]['assertion_id'])
        self.assertNotIn('claims no therapeutic outcomes', event['details'])
        self.assertNotIn('body', reference)
        self.assertEqual(reference['semantics'], 'prepared_not_delivery_or_approval')
        self.assertEqual(next(i for i in self.store.state(fixture.CASE)['questions'] if i['id']==q)['state'], 'open')

    def test_write_and_export_are_independent_gates(self):
        service, q, a, _, quotes = self.setup_service()
        original_export = service.report.export_authorizer
        service.report.export_authorizer = None
        with self.assertRaises(PermissionError): self.call(service, q, a, quotes)
        service.report.export_authorizer = original_export
        service.review.return_authorizer = None
        with patch.object(service.report, 'render') as render:
            with self.assertRaises(PermissionError): self.call(service, q, a, quotes)
            render.assert_not_called()
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_readable_but_nonredistributable_evidence_creates_no_receipt(self):
        service, q, a, sources, quotes = self.setup_service()
        sources[0]['permissions']['full_text']['redistribute'] = 'denied'
        with self.assertRaises(KnowledgeContextError): self.call(service, q, a, quotes)
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_changed_packet_after_render_cannot_be_relabelled_as_same_report(self):
        service, q, a, sources, quotes = self.setup_service()
        original = service.report.render
        def change(*args, **kwargs):
            report = original(*args, **kwargs)
            sources[0]['public_identifier'] = 'DIFFERENT-FICTIONAL-REFERENCE'
            return report
        with patch.object(service.report, 'render', side_effect=change):
            with self.assertRaises(ClinicalContinuityError): self.call(service, q, a, quotes)
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_selected_patient_amendment_between_preview_and_write_is_denied(self):
        service, q, a, _, quotes = self.setup_service()
        original = self.store.add_review_receipt
        def changed(*args, **kwargs):
            self._source('ORDER-CONT-001', 'clinical', 'order', 'negative', amendment=1)
            return original(*args, **kwargs)
        with patch.object(self.store, 'add_review_receipt', side_effect=changed):
            with self.assertRaises(InvalidInput): self.call(service, q, a, quotes)
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_audit_failure_rolls_back_receipt_and_returns_no_report(self):
        service, q, a, _, quotes = self.setup_service()
        with patch.object(self.store, '_event', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'audit unavailable'):
                self.call(service, q, a, quotes)
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_postwrite_export_revocation_withholds_body_but_retains_preparation(self):
        service, q, a, _, quotes = self.setup_service()
        write = self.store.add_review_receipt
        def revoke(*args, **kwargs):
            receipt = write(*args, **kwargs)
            service.report.export_authorizer = None
            return receipt
        with patch.object(self.store, 'add_review_receipt', side_effect=revoke):
            with self.assertRaises(PermissionError): self.call(service, q, a, quotes)
        receipts = self.store.review_queue(fixture.CASE)['receipts']
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]['action'], 'returned')

    def test_receipt_and_report_hash_survive_reopening_original_store(self):
        service, q, a, _, quotes = self.setup_service()
        result = self.call(service, q, a, quotes)
        reopened = CaseStore(self.store.path)
        try:
            self.assertEqual(reopened.review_queue(fixture.CASE)['receipts'][0]['id'], result['receipt']['receipt_id'])
            event = next(e for e in reopened.state(fixture.CASE)['events'] if e['kind']=='review_receipt_recorded')
            self.assertEqual(json.loads(event['details'])['prepared_report']['body_sha256'], result['report']['body_sha256'])
        finally: reopened.close()

    def test_wrong_question_case_and_actor_create_no_receipt(self):
        service, q, a, _, quotes = self.setup_service()
        for changes in ({'question_id':q+999}, {'case_id':'CASE-CLIN-CONT-OTHER'}, {'actor':'untrusted'}, {'purpose':'research'}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, PermissionError)):
                self.call(service, q, a, quotes, **changes)
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_bad_report_hashes_and_extra_content_are_rejected_by_owner(self):
        service, q, a, _, quotes = self.setup_service()
        before = service.review.preview(self.patient_id, fixture.CASE, q, a, selected_quotes=quotes, **self.actor())
        for bad in ({'body_sha256':'not-a-hash'}, {'body':'must not persist source text'}):
            with self.subTest(bad=bad), self.assertRaises(InvalidInput):
                self.store.add_review_receipt(fixture.CASE,before['queue_key'],'returned',self.actor()['actor'],
                    reason='Independent fictional assessment is needed.', expected_fingerprint=before['queue_fingerprint'],
                    prepared_report=bad)
        self.assertEqual(self.store.review_queue(fixture.CASE)['receipts'], [])

    def test_two_different_packet_owners_cannot_be_combined(self):
        from open_intelligence.evidence_report_handoff import ReportReviewHandoff
        from open_intelligence.evidence_review_packet import EvidenceReviewPacket
        service, q, a, _, quotes = self.setup_service()
        other = EvidenceReviewReport(EvidenceReviewPacket(service.review.packet.bridge), export_authorizer=lambda *args: True)
        with self.assertRaises(ValueError): ReportReviewHandoff(other,service.review)

if __name__ == '__main__': unittest.main()
