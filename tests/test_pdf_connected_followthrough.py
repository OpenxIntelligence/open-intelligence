"""Cross-domain source-owner acceptance; independently authored fictional text."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from open_intelligence.store import CaseStore
from open_intelligence.patient_report import build_patient_report, render_text


class ReviewedDocumentFollowthroughTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CaseStore(Path(self.temp.name) / 'fictional.sqlite')
        self.addCleanup(lambda: self.store.close())
        self.store.add_case('CASE-PLAIN', 'Independent fictional document case')
        self.store.add_case('CASE-OTHER', 'Unrelated fictional case')

    def test_reviewed_document_and_followthrough_share_original_source_owner(self):
        self.assertTrue(callable(getattr(self.store, 'import_document', None)),
                        'Reviewed ordinary-text/PDF source owner is absent from connected workflow')
        raw = b'Independent fictional record\r\nMarker P was not assessed.\r\n'
        preview = self.store.preview_document('CASE-PLAIN', raw, 'fictional.txt')
        saved = self.store.import_document('CASE-PLAIN', raw, 'fictional.txt',
            metadata={'document_id':'PLAIN-001', 'kind':'pathology', 'event_date':'2026-07-01',
                      'issued_at':'2026-07-02', 'manual_transcription_confirmed':True},
            findings=[{'key':'marker-p', 'state':'not-assessed',
                       'quote':'Marker P was not assessed.', 'line':2}],
            expected_sha256=preview['sha256'], confirmed_case_id='CASE-PLAIN')
        question = self.store.add_question('CASE-PLAIN', 'What does the selected passage establish?')
        task = self.store.create_followthrough_task('CASE-PLAIN', 'Collect review materials',
            actor_label='Fictional author', reason='Prepare the original for independent review.',
            question_id=question, source_version_id=saved['source_id'])
        text = render_text(build_patient_report(self.store.state('CASE-PLAIN')))
        self.assertIn(f'Follow-through task #{task}.', text)
        self.assertIn(hashlib.sha256(raw).hexdigest(), text)
        self.assertEqual(self.store.source_document('CASE-PLAIN', saved['source_id'])['raw'], raw)

    def manual(self, case='CASE-PLAIN', *, amended=False):
        quote = 'Marker P remains pending.' if amended else 'Marker P was not assessed.'
        raw = ('Independent fictional record\r\n' + quote + '\r\n').encode()
        preview = self.store.preview_document(case, raw, 'fictional.txt')
        metadata = {'document_id':'PLAIN-001', 'kind':'pathology', 'event_date':'2026-07-01',
                    'issued_at':'2026-07-02', 'manual_transcription_confirmed':True}
        if amended: metadata['amends_version'] = 1
        saved = self.store.import_document(case, raw, 'fictional.txt', metadata,
            [{'key':'marker-p','state':'pending' if amended else 'not-assessed','quote':quote,'line':2}],
            preview['sha256'], case)
        return raw, saved

    def test_readable_report_preserves_manual_origin_and_review_receipt(self):
        raw, saved = self.manual()
        state = self.store.state('CASE-PLAIN')
        report = build_patient_report(state)
        item = next(s for s in report['sections'] if s['id']=='overview')['items'][0]
        self.assertIn('User-selected classification', item['detail'])
        self.assertNotIn('source states:', item['detail'])
        self.assertIn('not clinically reviewed', item['detail'])
        self.assertIn(state['assertions'][0]['transcription_review_sha256'], item['citation'])
        self.assertIn(hashlib.sha256(raw).hexdigest(), item['citation'])

    def test_knowledge_packet_keeps_manual_provenance_and_rejects_missing_origin(self):
        from copy import deepcopy
        from open_intelligence.knowledge_context import compile_context, KnowledgeContextError
        self.manual()
        state = self.store.state('CASE-PLAIN')
        row = compile_context('CASE-PLAIN', state, [])['patient_assertions'][0]
        self.assertEqual(row.get('classification_origin'), 'user_selected')
        self.assertEqual(row.get('epistemic_kind'), 'manually_transcribed_observation')
        self.assertEqual(row.get('clinical_review'), 'not_performed')
        self.assertEqual(row.get('transcription_review_sha256'), state['assertions'][0]['transcription_review_sha256'])
        for field in ('classification_origin','annotation_method','clinical_review','transcription_review_sha256'):
            bad=deepcopy(state); bad['assertions'][0].pop(field)
            with self.subTest(field=field), self.assertRaises(KnowledgeContextError):
                compile_context('CASE-PLAIN',bad,[])

    def test_readable_report_refuses_incomplete_manual_provenance(self):
        from open_intelligence.store import InvalidInput
        self.manual(); state=self.store.state('CASE-PLAIN')
        state['assertions'][0].pop('transcription_review_sha256')
        with self.assertRaises(InvalidInput): build_patient_report(state)


# Reuse the actual governed source-owner fixture without discovering its tests twice.
import test_evidence_review_report as report_fixture
import test_patient_clinical_knowledge_integration as clinical_fixture

class ReviewedDocumentGovernedReportTests(unittest.TestCase):
    setUp = report_fixture.EvidenceReportTests.setUp
    actor = report_fixture.EvidenceReportTests.actor
    workflow = report_fixture.EvidenceReportTests.workflow
    _source = report_fixture.EvidenceReportTests._source
    prepare = report_fixture.EvidenceReportTests.prepare
    setup_report = report_fixture.EvidenceReportTests.setup_report
    render = report_fixture.EvidenceReportTests.render
    manual = ReviewedDocumentFollowthroughTests.manual

    def test_governed_report_keeps_manual_status_and_exact_original(self):
        renderer,bridge,q,sources,proposals,selected=self.setup_report()
        raw,saved=self.manual(clinical_fixture.CASE)
        observation=next(a for a in self.store.state(clinical_fixture.CASE)['assertions']
                         if a['source_version_id']==saved['source_id'])
        proposals[0]['assertion_id']=observation['id']
        selected[0]['assertion_id']=observation['id']
        packet=renderer.packets.preview(self.patient_id,clinical_fixture.CASE,q,
                                       selected_quotes=selected,**self.actor())
        reference=packet['quoted_comparisons'][0]['patient_reference']
        self.assertEqual(reference.get('classification_origin'),'user_selected')
        self.assertEqual(reference.get('clinical_review'),'not_performed')
        result=self.render(renderer,q,selected)
        self.assertIn('User-selected classification',result['body'])
        self.assertIn(observation['transcription_review_sha256'],result['body'])
        self.assertIn(hashlib.sha256(raw).hexdigest(),result['body'])
        self.manual(clinical_fixture.CASE,amended=True)
        from open_intelligence.knowledge_context import KnowledgeContextError
        from open_intelligence.clinical_continuity import ClinicalContinuityError
        with self.assertRaises((KnowledgeContextError,ClinicalContinuityError)):
            self.render(renderer,q,selected)


def import_pdf(store, case_id, *, amended=False):
    from pdf_fixtures import text_pdf
    quote = 'Marker P remains pending.' if amended else 'Marker P was not assessed.'
    raw = text_pdf([['Independent fictional PDF record.', 'No clinical conclusion.'], [quote]])
    preview = store.preview_document(case_id, raw, 'independent.pdf')
    metadata = {'document_id': 'PDF-CONNECTED', 'kind': 'pathology',
                'event_date': '2026-07-01', 'issued_at': '2026-07-03' if amended else '2026-07-02',
                'manual_transcription_confirmed': True}
    if amended: metadata['amends_version'] = 1
    saved = store.import_document(case_id, raw, 'independent.pdf', metadata,
        [{'key': 'marker-p', 'state': 'pending' if amended else 'not-assessed', 'quote': quote, 'line': 3}],
        expected_sha256=preview['sha256'], confirmed_case_id=case_id,
        expected_extraction_sha256=preview['extraction_sha256'])
    return raw, saved, preview


class PdfConnectedFollowthroughTests(unittest.TestCase):
    setUp = ReviewedDocumentFollowthroughTests.setUp

    def test_pdf_page_provenance_and_task_history_survive_amendment_and_restart(self):
        from open_intelligence import CaseStore
        raw, saved, preview = import_pdf(self.store, 'CASE-PLAIN')
        question = self.store.add_question('CASE-PLAIN', 'Which independently fictional passage needs review?')
        ids = []
        for title in ('Open PDF review preparation', 'Finished PDF review preparation'):
            ids.append(self.store.create_followthrough_task('CASE-PLAIN', title,
                actor_label='Fictional author', reason='Prepare an independent source discussion.',
                source_version_id=saved['source_id'], question_id=question))
        for status in ('assigned', 'acknowledged', 'completed'):
            self.store.update_followthrough_task('CASE-PLAIN', ids[1], status,
                actor_label='Fictional recorder', reason='Record preparation status only.',
                **({'owner_label':'Fictional coordinator'} if status=='assigned' else {}))
        report = build_patient_report(self.store.state('CASE-PLAIN'))
        text = render_text(report)
        for marker in ('Physical PDF page 2', 'extraction line 3', 'page line 1',
                       preview['extraction_sha256'], hashlib.sha256(raw).hexdigest(),
                       'User-selected classification', 'not clinically reviewed'):
            self.assertIn(marker, text)
        tasks = next(s for s in report['sections'] if s['id']=='followthrough')
        self.assertTrue(all('no passage/page anchor is recorded' in x['citation'] for x in tasks['items']))
        import_pdf(self.store, 'CASE-PLAIN', amended=True)
        amended = render_text(build_patient_report(self.store.state('CASE-PLAIN')))
        self.assertIn('linked source amended — recheck is open', amended)
        self.assertIn('this task remains history', amended)
        self.assertEqual(self.store.source_document('CASE-PLAIN', saved['source_id'])['raw'], raw)
        # Reopen the same existing journal, without replaying imports or tasks.
        path = self.store.db.execute('PRAGMA database_list').fetchone()[2]
        self.store.close(); self.store = CaseStore(path); self.addCleanup(self.store.close)
        self.assertEqual(render_text(build_patient_report(self.store.state('CASE-PLAIN'))), amended)
        self.assertNotIn('PDF review preparation', render_text(build_patient_report(self.store.state('CASE-OTHER'))))

    def test_pdf_missing_or_changed_page_provenance_is_rejected_by_both_consumers(self):
        from open_intelligence.knowledge_context import compile_context, KnowledgeContextError
        from open_intelligence.store import InvalidInput
        import_pdf(self.store, 'CASE-PLAIN')
        for field in ('source_page','page_line','page_text_sha256','extraction_sha256','classification_origin'):
            for value in (None, 'forged'):
                snapshot = self.store.state('CASE-PLAIN')
                if value is None: snapshot['assertions'][0].pop(field)
                else: snapshot['assertions'][0][field] = value
                with self.subTest(field=field, value=value):
                    with self.assertRaises(InvalidInput): build_patient_report(snapshot)
                    with self.assertRaises(KnowledgeContextError): compile_context('CASE-PLAIN', snapshot, [])


class PdfGovernedReviewReceiptTests(unittest.TestCase):
    setUp = report_fixture.EvidenceReportTests.setUp
    actor = report_fixture.EvidenceReportTests.actor
    workflow = report_fixture.EvidenceReportTests.workflow
    _source = report_fixture.EvidenceReportTests._source
    prepare = report_fixture.EvidenceReportTests.prepare
    setup_report = report_fixture.EvidenceReportTests.setup_report
    render = report_fixture.EvidenceReportTests.render

    def test_pdf_provenance_binds_governed_report_and_nonterminal_review_receipt(self):
        from open_intelligence.authorized_evidence_review import AuthorizedEvidenceReviewHandoff
        from open_intelligence.evidence_report_handoff import ReportReviewHandoff
        from open_intelligence.evidence_review_report import EvidenceReviewReport
        import test_authorized_evidence_review_handoff as review_fixture
        renderer, bridge, q, sources, proposals, selected = self.setup_report()
        raw, saved, preview = import_pdf(self.store, clinical_fixture.CASE)
        assertion = next(a for a in self.store.state(clinical_fixture.CASE)['assertions']
                         if a['source_version_id']==saved['source_id'])
        evidence_id = self.store.import_synthetic_evidence(review_fixture.ORIGINAL)['evidence_version_id']
        assessment = self.store.assess_synthetic_evidence(clinical_fixture.CASE, q, evidence_id,
            'context', 'limited', 'Independent fictional evidence awaiting review.')
        sources[0].update(id=review_fixture.EVIDENCE_KEY, version='v1', evidence_text=review_fixture.STATEMENT)
        proposals[:] = [{**proposals[0], 'assertion_id':assertion['id'],
                        'knowledge_id':review_fixture.EVIDENCE_KEY, 'relation':'context', 'applicability':'limited'}]
        selected = [{'assertion_id':assertion['id'], 'knowledge_id':review_fixture.EVIDENCE_KEY,
                     'quote':'claims no therapeutic outcomes'}]
        review = AuthorizedEvidenceReviewHandoff(renderer.packets, return_authorizer=lambda a,p,op,purpose:
            a==self.actor()['actor'] and p==self.patient_id and op=='evidence.review_return' and purpose=='care')
        service = ReportReviewHandoff(renderer, review)
        result = service.return_for_review(self.patient_id, clinical_fixture.CASE, q, assessment,
            selected_quotes=selected, reason='Independent fictional review remains necessary.', **self.actor())
        self.assertFalse(result['clinical_signoff'])
        body = result['report']['body']
        self.assertIn('Physical PDF page: 2', body)
        self.assertIn('User-selected classification', body)
        for digest in (preview['extraction_sha256'], preview['sha256'], assertion['page_text_sha256'],
                       assertion['transcription_review_sha256']): self.assertIn(digest, body)
        receipts = self.store.review_queue(clinical_fixture.CASE)['receipts']
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]['action'], 'returned')
        original_receipt = repr(receipts)
        import_pdf(self.store, clinical_fixture.CASE, amended=True)
        with self.assertRaises(ValueError): self.render(renderer, q, selected)
        self.assertEqual(repr(self.store.review_queue(clinical_fixture.CASE)['receipts']), original_receipt)
        self.assertEqual(self.store.source_document(clinical_fixture.CASE, saved['source_id'])['raw'], raw)
