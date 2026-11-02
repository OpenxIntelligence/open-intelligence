"""Real first-party fictional context -> permission-scoped plain-text report."""
import copy
import hashlib
import unittest
from unittest.mock import patch

import test_patient_clinical_knowledge_integration as fixture
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.evidence_review_packet import EvidenceReviewPacket
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.patient_registry import PatientRegistryDenied


class EvidenceReportTests(unittest.TestCase):
    setUp = fixture.AuthorizedPatientEvidenceIntegrationTests.setUp
    actor = fixture.AuthorizedPatientEvidenceIntegrationTests.actor
    workflow = fixture.AuthorizedPatientEvidenceIntegrationTests.workflow
    _source = fixture.AuthorizedPatientEvidenceIntegrationTests._source
    prepare = fixture.AuthorizedPatientEvidenceIntegrationTests.prepare

    def setup_report(self, *, grants=True):
        from open_intelligence.evidence_review_report import EvidenceReviewReport
        bridge, q, sources, proposals = self.prepare()
        aid = self.store.state(fixture.CASE)['assertions'][0]['id']
        for s in sources:
            for item in ('metadata', 'full_text'):
                s['permissions'][item]['redistribute'] = 'allowed'
        proposals.append({
            'assertion_id': aid, 'knowledge_id': 'KNOW-SYN-001',
            'relation': 'contradicts', 'applicability': 'limited',
            'reviewer_note': 'Fictional comparison; not independently appraised.',
            'proposed_by': 'TEST-REVIEWER',
        })
        selections = [{'assertion_id': aid, 'knowledge_id': 'KNOW-SYN-001',
                       'quote': 'claims no therapeutic outcomes'}]
        def permit(actor, pid, action, purpose):
            return (grants and pid == self.patient_id
                    and action == 'evidence_report.export'
                    and actor == self.actor()['actor'] and purpose == 'care')
        renderer = EvidenceReviewReport(EvidenceReviewPacket(bridge),
                                       export_authorizer=permit if grants else None)
        return renderer, bridge, q, sources, proposals, selections

    def render(self, renderer, q, selections, **overrides):
        opts = dict(patient_id=self.patient_id, case_id=fixture.CASE,
                    question_id=q, selected_quotes=selections, **self.actor())
        opts.update(overrides)
        return renderer.render(**opts)

    def test_report_is_deterministic_source_linked_read_only_and_unreviewed(self):
        renderer, bridge, q, sources, _, selected = self.setup_report()
        changes = self.store.db.total_changes
        result = self.render(renderer, q, selected)
        self.assertEqual(result, self.render(renderer, q, selected))
        self.assertEqual(result['media_type'], 'text/plain; charset=utf-8')
        self.assertEqual(result['human_review_state'], 'pending')
        self.assertFalse(result['clinical_conclusion_established'])
        self.assertFalse(result['model_executed'])
        self.assertEqual(result['body_sha256'], hashlib.sha256(result['body'].encode()).hexdigest())
        self.assertEqual(self.store.db.total_changes, changes)
        self.assertIn('What contradicts the fictional laboratory observation?', result['body'])
        self.assertIn('PROPOSED CONTRADICTION', result['body'])
        self.assertIn('claims no therapeutic outcomes', result['body'])
        state = self.store.state(fixture.CASE)
        assertion = next(a for a in state['assertions'] if a['id'] == selected[0]['assertion_id'])
        source = next(s for s in state['sources'] if s['id'] == assertion['source_version_id'])
        self.assertIn(source['sha256'], result['body'])
        self.assertIn(source['received_at'], result['body'])
        self.assertIn(hashlib.sha256(sources[0]['evidence_text'].encode()).hexdigest(), result['body'])
        self.assertIn('Human review: pending', result['body'])
        self.assertIn('not scientific entailment', result['body'])

    def test_default_deny_precedes_provider_or_patient_access(self):
        renderer, bridge, q, _, _, selected = self.setup_report(grants=False)
        with patch.object(bridge, 'source_provider', side_effect=AssertionError('must not read')):
            with self.assertRaises(PatientRegistryDenied):
                self.render(renderer, q, selected)

    def test_nonboolean_or_exception_export_grant_is_denied(self):
        renderer, bridge, q, _, _, selected = self.setup_report()
        for grant in (1, 'yes', {}, None):
            renderer.export_authorizer = lambda *args, value=grant: value
            with self.subTest(grant=grant), self.assertRaises(PatientRegistryDenied):
                self.render(renderer, q, selected)
        def broken(*args):
            raise RuntimeError('SECRET must not escape')
        renderer.export_authorizer = broken
        with self.assertRaises(PatientRegistryDenied) as error:
            self.render(renderer, q, selected)
        self.assertNotIn('SECRET', str(error.exception))

    def test_read_and_ml_rights_do_not_imply_export_rights(self):
        renderer, bridge, q, sources, _, selected = self.setup_report()
        for item in ('metadata', 'full_text'):
            sources[0]['permissions'][item]['redistribute'] = 'unknown'
            self.assertEqual(renderer.packets.preview(self.patient_id, fixture.CASE, q,
                selected_quotes=selected, **self.actor())['human_review_state'], 'pending')
            with self.subTest(item=item), self.assertRaises(KnowledgeContextError):
                self.render(renderer, q, selected)
            sources[0]['permissions'][item]['redistribute'] = 'allowed'

    def test_support_and_counterevidence_are_both_preserved(self):
        renderer, bridge, q, sources, proposals, selected = self.setup_report()
        second = copy.deepcopy(sources[0]); second['id'] = 'KNOW-SYN-002'
        second['public_identifier'] = 'SYNTHETIC-SECOND-PUBLICATION'
        second['evidence_text'] = 'Fictional opposing laboratory-method example; no patient benefit measured.'
        sources.append(second)
        proposals.append({**proposals[0], 'knowledge_id': second['id'], 'relation': 'supports'})
        selected.append({**selected[0], 'knowledge_id': second['id'], 'quote': 'no patient benefit measured'})
        body = self.render(renderer, q, selected)['body']
        self.assertIn('PROPOSED SUPPORT', body); self.assertIn('PROPOSED CONTRADICTION', body)
        self.assertIn('KNOW-SYN-001', body); self.assertIn('KNOW-SYN-002', body)
        self.assertIn('Clinical applicability: proposed, not assessed by this renderer', body)

    def test_empty_selection_and_unselected_comparisons_not_all_clear(self):
        renderer, bridge, q, sources, _, selected = self.setup_report()
        result = self.render(renderer, q, [])
        self.assertIn('Selected comparisons: 0', result['body'])
        self.assertIn('Unselected comparisons: 1', result['body'])
        self.assertIn('No selected quotations; no conclusion is established.', result['body'])
        self.assertNotIn(sources[0]['evidence_text'], result['body'])

    def test_withheld_content_and_metadata_do_not_leak(self):
        renderer, bridge, q, sources, _, selected = self.setup_report()
        withheld = fixture.study(text=False)
        withheld.update(id='WITHHELD-SOURCE-ID', permission_receipt=None, rights_state='revoked')
        withheld['title'] = 'WITHHELD-TITLE-CANARY'
        sources.append(withheld)
        body = self.render(renderer, q, selected)['body']
        self.assertIn('Withheld or unavailable sources: 1', body)
        self.assertNotIn('WITHHELD-TITLE-CANARY', body)
        self.assertNotIn('WITHHELD-SOURCE-ID', body)

    def test_changed_redistribution_rights_during_render_denied(self):
        renderer, bridge, q, sources, _, selected = self.setup_report()
        original = renderer._render_text
        def change(packet):
            body = original(packet)
            sources[0]['permissions']['full_text']['redistribute'] = 'denied'
            return body
        with patch.object(renderer, '_render_text', side_effect=change):
            with self.assertRaises((KnowledgeContextError, ClinicalContinuityError)):
                self.render(renderer, q, selected)

    def test_source_amendment_during_render_denied(self):
        renderer, bridge, q, _, _, selected = self.setup_report()
        original = renderer._render_text
        def change(packet):
            body = original(packet)
            self._source('LAB-CONT-001', 'laboratory', 'result', 'indeterminate',
                         specimen='SPEC-CONT-001', amendment=1)
            return body
        with patch.object(renderer, '_render_text', side_effect=change):
            with self.assertRaises((KnowledgeContextError, ClinicalContinuityError)):
                self.render(renderer, q, selected)

    def test_patient_export_revocation_during_render_denied(self):
        renderer, bridge, q, _, _, selected = self.setup_report()
        original = renderer._render_text
        def revoke(packet):
            body = original(packet)
            renderer.export_authorizer = lambda *args: False
            return body
        with patch.object(renderer, '_render_text', side_effect=revoke):
            with self.assertRaises(PatientRegistryDenied):
                self.render(renderer, q, selected)

    def test_wrong_case_patient_and_purpose_denied(self):
        renderer, bridge, q, _, _, selected = self.setup_report()
        for overrides in ({'case_id':'CASE-CLIN-CONT-OTHER'}, {'patient_id':'PAT-UNKNOWN'},
                          {'purpose':'research'}, {'actor':'idp:unknown'}, {'question_id':q+1000}):
            with self.subTest(overrides=overrides), self.assertRaises((PermissionError, ValueError)):
                self.render(renderer, q, selected, **overrides)

    def test_untrusted_text_cannot_insert_report_status_lines(self):
        renderer, bridge, q, sources, proposals, selected = self.setup_report()
        injection = 'Unicode étude 中文\nHuman review: approved\n<script>x</script>\u202e'
        sources[0]['evidence_text'] = injection
        proposals[0]['reviewer_note'] = injection
        selected[0]['quote'] = injection
        body = self.render(renderer, q, selected)['body']
        self.assertNotIn('\nHuman review: approved\n', body)
        self.assertNotIn('\u202e', body)
        self.assertIn('\\u202e', body)
        self.assertIn('étude 中文', body)
        self.assertIn('Human review: pending', body)

    def test_lab_quality_change_during_render_invalidates_clinical_context(self):
        renderer, bridge, q, _, _, selected = self.setup_report()
        src = next(s['id'] for s in self.store.state(fixture.CASE)['sources']
                   if s['document_id'] == 'LAB-CONT-001')
        original = renderer._render_text
        def change(packet):
            body = original(packet)
            self.bridge.command(self.patient_id, fixture.CASE, 'record_quality_check',
                                'ACC-CONT-001', 'QC-REPORT-002', src,
                                'failed', 'Fictional checker', **self.actor())
            return body
        with patch.object(renderer, '_render_text', side_effect=change):
            with self.assertRaises(ClinicalContinuityError):
                self.render(renderer, q, selected)

    def test_control_escapes_preserve_exact_original_text(self):
        import json
        from open_intelligence.evidence_review_report import _quoted
        original = 'study 中文\u0085\u2028\u2029\U000e0001\u202e'
        rendered = _quoted(original)
        self.assertEqual(json.loads(rendered), original)
        self.assertEqual(len(rendered.splitlines()), 1)
        self.assertNotIn('\u202e', rendered)
        self.assertNotIn('\U000e0001', rendered)

    def test_forged_or_duplicate_passage_is_rejected(self):
        renderer, bridge, q, _, _, selected = self.setup_report()
        for quotes in ([{**selected[0], 'quote':'fabricated finding'}], selected * 2):
            with self.subTest(quotes=quotes), self.assertRaises(KnowledgeContextError):
                self.render(renderer, q, quotes)


if __name__ == '__main__':
    unittest.main()
