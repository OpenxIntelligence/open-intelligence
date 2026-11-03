"""A manual correction appears as selection history, never a new medical report."""
import hashlib
import unittest

from open_intelligence.changes import changes_since_review
from open_intelligence.mission import build_patient_mission
from open_intelligence.store import CaseStore
from open_intelligence.timeline import case_timeline


class AnnotationProjectionTests(unittest.TestCase):
    def test_changed_selections_reopen_review_without_fabricating_a_source_amendment(self):
        store = CaseStore(':memory:')
        self.addCleanup(store.close)
        store.add_case('CASE-ALPHA', 'Independent fictional projection case')
        raw = b'Independent fictional record\nMarker P was not assessed.\n'
        digest = hashlib.sha256(raw).hexdigest()
        finding = {'key': 'marker-p', 'state': 'negative', 'quote': 'Marker P was not assessed.', 'line': 2}
        source = store.import_document('CASE-ALPHA', raw, 'record.txt',
            {'document_id': 'DOC-ANNOTATED', 'kind': 'pathology', 'event_date': '2026-08-01',
             'issued_at': '2026-08-02', 'manual_transcription_confirmed': True},
            [finding], digest, 'CASE-ALPHA')['source_id']
        question = store.add_question('CASE-ALPHA', 'Which status needs to be checked against the source?')
        snapshot = store.create_snapshot('CASE-ALPHA', question,
            'Independent fictional draft records the earlier selection.', [source])
        store.acknowledge_demo_review('CASE-ALPHA', snapshot, 'Unverified synthetic reviewer')
        store.revise_document_annotations('CASE-ALPHA', source,
            findings=[{**finding, 'state': 'not-assessed'}], expected_revision=1,
            expected_sha256=digest, confirmed_case_id='CASE-ALPHA',
            manual_transcription_confirmed=True, reason='Correct my selection to match the literal passage.')
        before = tuple(store.db.iterdump())
        changes = changes_since_review(store, 'CASE-ALPHA')
        state = store.state('CASE-ALPHA')
        mission = build_patient_mission(state)
        timeline = case_timeline(store, 'CASE-ALPHA')
        self.assertEqual(tuple(store.db.iterdump()), before)
        self.assertEqual(changes['new_sources'], [])
        self.assertEqual(changes['amendments'], [])
        correction = changes['annotation_revisions'][0]
        self.assertEqual((correction['source_id'], correction['version'], correction['annotation_revision']), (source, 1, 2))
        self.assertEqual(correction['invalidated_snapshot_ids'], [snapshot])
        self.assertEqual(changes['stale_investigations'][0]['causes'][0]['cause'], 'annotation_revision')
        self.assertEqual(mission['what_we_know'][0]['annotation_revision'], 2)
        self.assertEqual(mission['what_we_know'][0]['state'], 'not-assessed')
        self.assertEqual(mission['workflow_status'], 'review_required')
        self.assertIn('original document unchanged', str(mission))
        self.assertIn('annotation_revision', str(timeline))
        self.assertEqual(store.source_document('CASE-ALPHA', source)['raw'], raw)


if __name__ == '__main__':
    unittest.main()
