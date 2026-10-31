"""Additional authored fixtures exercise the existing CaseStore, not a second ledger."""
import json
from pathlib import Path
import unittest

from open_intelligence import CaseStore, InvalidInput
from tools.evaluation_packet import build_packet

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'evaluation' / 'synthetic_v1' / 'fixture.json'

class EvaluationCaseStoreTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text())
        self.sources = {s['id']: s for s in self.fixture['sources']}
        self.store = CaseStore(':memory:')
        for case in self.fixture['cases']:
            self.store.add_case(case, 'Original fictional evaluation subject')

    def tearDown(self):
        self.store.close()

    def ingest(self, sid):
        source = self.sources[sid]
        raw = source['content'].encode()
        if source['kind'] == 'evidence':
            return self.store.import_synthetic_evidence(raw)
        return self.store.import_report(source['target_case_id'], raw)

    def first_round(self):
        return {s['id']: self.ingest(s['id'])
                for s in build_packet(self.fixture, 'R1')['sources']}

    def test_first_round_preserves_missingness_and_no_invented_administration(self):
        self.first_round()
        a = self.store.state('CASE-IV-A')
        assertions = {r['finding_key']: r for r in a['assertions']}
        self.assertEqual(assertions['marker-x']['certainty'], 'not-assessed')
        self.assertEqual(assertions['exposure']['certainty'], 'not-reported')
        self.assertIn('administration is not documented', assertions['exposure']['quote'])
        self.assertEqual(assertions['metastasis']['certainty'], 'negative')
        b = self.store.state('CASE-IV-B')
        self.assertEqual(next(r['certainty'] for r in b['assertions']
                              if r['finding_key'] == 'marker-x'), 'pending')
        self.assertNotIn('LATER-RESULT-CANARY', json.dumps(a))

    def test_duplicate_wrong_case_and_wrong_specimen_are_contained(self):
        self.first_round()
        before = len(self.store.state('CASE-IV-A')['events'])
        self.assertEqual(self.ingest('S05')['result'], 'duplicate')
        self.assertEqual(len(self.store.state('CASE-IV-A')['events']), before)
        self.assertEqual(self.ingest('S06')['result'], 'quarantined')
        with self.assertRaises(InvalidInput):
            self.ingest('S09')
        self.assertEqual(len(self.store.state('CASE-IV-A')['sources']), 2)
        self.assertEqual(len(self.store.state('CASE-IV-B')['sources']), 1)

    def test_source_amendment_reopens_only_dependent_case_snapshot(self):
        imported = self.first_round()
        qa = self.store.add_question('CASE-IV-A', 'Which authored marker statement is available?')
        qb = self.store.add_question('CASE-IV-B', 'Is a new action justified by the available record?')
        sa = self.store.create_snapshot('CASE-IV-A', qa,
            'Original synthetic marker finding remains unassessed.', [imported['S01']['source_id']])
        sb = self.store.create_snapshot('CASE-IV-B', qb,
            'This synthetic control has a pending result, not evidence of urgency.', [imported['S03']['source_id']])
        self.store.acknowledge_demo_review('CASE-IV-A', sa, 'Demonstration only')
        self.store.acknowledge_demo_review('CASE-IV-B', sb, 'Demonstration only')
        self.ingest('S07')
        self.assertEqual(self.store.state('CASE-IV-A')['snapshots'][0]['state'], 'stale')
        self.assertEqual(self.store.state('CASE-IV-A')['questions'][0]['state'], 'open')
        self.assertEqual(self.store.state('CASE-IV-B')['snapshots'][0]['state'], 'reviewed_in_demo')
        old = self.store.export_markdown('CASE-IV-A', sa)
        self.assertIn('was not tested', old)
        self.assertIn('stale', old)

    def test_conflicting_evidence_revision_invalidates_without_approving_replacement(self):
        imported = self.first_round()
        q = self.store.add_question('CASE-IV-A', 'Does the fictional assay note resolve this question?')
        assessment = self.store.assess_synthetic_evidence('CASE-IV-A', q,
            imported['S04']['evidence_version_id'], 'context', 'unknown',
            'This is fictional context, not evidence of treatment benefit or applicability.')
        sid = self.store.create_snapshot('CASE-IV-A', q,
            'This synthetic source is unappraised and does not justify an action.',
            [imported['S01']['source_id']], [assessment])
        self.ingest('S10')
        state = self.store.state('CASE-IV-A')
        self.assertEqual(next(s['state'] for s in state['snapshots'] if s['id'] == sid), 'stale')
        self.assertEqual(len(state['evidence_assessments']), 1)
        with self.assertRaises(InvalidInput):
            self.store.create_snapshot('CASE-IV-A', q,
                'An old assessment cannot certify the corrected fictional source.',
                [imported['S01']['source_id']], [assessment])

if __name__ == '__main__': unittest.main()
