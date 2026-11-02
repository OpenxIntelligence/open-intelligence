"""Replay practice fixtures through the existing application, without changing it."""
import json
from pathlib import Path
import tempfile
import unittest

from open_intelligence import CaseStore, InvalidInput
from tools.evaluation_packet import bundle

ROOT = Path(__file__).resolve().parents[1]


class IV01StoreReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'case.sqlite')
        self.packet = json.loads((ROOT / 'validation/iv01/cases.json').read_text())
        for case in self.packet['cases']:
            self.store.add_case(case['id'], case['label'])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def replay(self, stage):
        data = bundle(self.packet, stage)
        sources = {s['id']: s for s in data['sources']}
        outcomes = []
        for receipt in data['receipts']:
            source = sources[receipt['source_id']]
            if source['kind'] == 'report':
                try:
                    result = self.store.import_report(receipt['target_case'], source['text'].encode('utf-8'))
                    outcomes.append(result['result'])
                except InvalidInput:
                    outcomes.append('rejected')
        return outcomes

    def test_t0_missing_is_not_negative_and_order_is_not_administration(self):
        self.assertEqual(self.replay('T0'), ['imported'] * 3)
        state = self.store.state('CASE-EVAL-A')
        findings = {x['finding_key']: x for x in state['assertions']}
        self.assertEqual(findings['marker-q']['certainty'], 'not-reported')
        self.assertIn('does not record administration', findings['procedure']['quote'])
        self.assertEqual(len(state['sources']), 2)

    def test_amendment_stales_existing_review_without_changing_other_case(self):
        self.replay('T0')
        old = next(x for x in self.store.state('CASE-EVAL-A')['sources'] if x['document_id'] == 'EVAL-A-PATH')
        question = self.store.add_question('CASE-EVAL-A', 'What does the fictional marker source establish?')
        snapshot = self.store.create_snapshot('CASE-EVAL-A', question,
                     'Marker Q was not tested in the original fictional source.', [old['id']])
        self.store.acknowledge_demo_review('CASE-EVAL-A', snapshot, 'Unverified practice operator')
        self.replay('T1')
        state = self.store.state('CASE-EVAL-A')
        self.assertEqual(state['snapshots'][0]['state'], 'stale')
        self.assertEqual(state['questions'][0]['state'], 'open')
        self.assertEqual(next(x for x in state['assertions'] if x['finding_key'] == 'marker-q')['certainty'], 'negative')
        self.assertEqual(len(state['quarantines']), 1)
        beta = self.store.state('CASE-EVAL-B')
        self.assertEqual(len(beta['sources']), 1)
        self.assertEqual(next(x for x in beta['assertions'] if x['finding_key'] == 'marker-q')['certainty'], 'not-assessed')

    def test_full_replay_duplicate_and_wrong_specimen_are_not_new_facts(self):
        outcomes = self.replay('T2')
        self.assertEqual(outcomes.count('imported'), 6)
        self.assertEqual(outcomes.count('duplicate'), 1)
        self.assertEqual(outcomes.count('quarantined'), 1)
        self.assertEqual(outcomes.count('rejected'), 1)
        alpha = self.store.state('CASE-EVAL-A')
        versions = [s for s in alpha['sources'] if s['document_id'] == 'EVAL-A-PATH']
        self.assertEqual([s['version'] for s in versions], [1, 2])
        self.assertEqual({s['specimen_id'] for s in versions}, {'EVAL-A-TISSUE'})
        self.assertEqual(len(self.store.state('CASE-EVAL-B')['sources']), 2)


if __name__ == '__main__':
    unittest.main()
