"""Additional IV-01 coverage using the canonical packet and existing CaseStore.

Synthetic software tests only; human assessment labels are not clinical truth.
"""
import json
from pathlib import Path
import unittest

from open_intelligence import CaseStore, InvalidInput
from tools.evaluation_packet import bundle

ROOT = Path(__file__).resolve().parents[1]


class IV01EvidenceReplayTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((ROOT / 'validation/iv01/cases.json').read_text())
        self.inputs = bundle(self.packet, 'T0')
        self.sources = {s['id']: s for s in self.inputs['sources']}
        self.store = CaseStore(':memory:')
        for case in self.inputs['cases']:
            self.store.add_case(case['id'], case['label'])
        self.report_ids = {}
        self.evidence_ids = {}
        for receipt in self.inputs['receipts']:
            source = self.sources[receipt['source_id']]
            raw = source['text'].encode('utf-8')
            if source['kind'] == 'report':
                result = self.store.import_report(receipt['target_case'], raw)
                self.report_ids[source['id']] = result['source_id']
            else:
                result = self.store.import_synthetic_evidence(raw)
                self.evidence_ids[source['id']] = result['evidence_version_id']

    def tearDown(self):
        self.store.close()

    def test_contradictory_fictional_sources_do_not_auto_create_appraisals(self):
        state = self.store.state('CASE-EVAL-A')
        self.assertEqual(len(state['evidence']), 2)
        self.assertEqual({x['state'] for x in state['evidence']}, {'current'})
        self.assertEqual(state['evidence_assessments'], [])
        self.assertEqual(state['snapshots'], [])
        for sid in ('S004', 'S005'):
            original = self.store.synthetic_evidence_text(self.evidence_ids[sid])
            self.assertEqual(original, self.sources[sid]['text'])
        self.assertIn('did not reproduce', self.store.synthetic_evidence_text(self.evidence_ids['S005']))
        self.assertEqual(self.store.state('CASE-EVAL-B')['evidence_assessments'], [])

    def test_withdrawal_stales_only_linked_case_and_preserves_counterevidence(self):
        qa = self.store.add_question('CASE-EVAL-A', 'What does fictional evidence one support?')
        qb = self.store.add_question('CASE-EVAL-B', 'What does fictional counterevidence leave unresolved?')
        aa = self.store.assess_synthetic_evidence(
            'CASE-EVAL-A', qa, self.evidence_ids['S004'], 'context', 'unknown',
            'Unappraised fictional assay context does not establish clinical benefit.')
        ab = self.store.assess_synthetic_evidence(
            'CASE-EVAL-B', qb, self.evidence_ids['S005'], 'contradicts', 'unknown',
            'This human-labelled fictional contradiction is not an applicability determination.')
        sa = self.store.create_snapshot(
            'CASE-EVAL-A', qa, 'Synthetic assay context remains uncertain and unappraised.',
            [self.report_ids['S001']], [aa])
        sb = self.store.create_snapshot(
            'CASE-EVAL-B', qb, 'Synthetic counterevidence is retained without a treatment conclusion.',
            [self.report_ids['S003']], [ab])
        self.store.acknowledge_demo_review('CASE-EVAL-A', sa, 'Unverified practice operator')
        self.store.acknowledge_demo_review('CASE-EVAL-B', sb, 'Unverified practice operator')
        reason = 'Fictional source retired to test precise dependency invalidation.'
        result = self.store.withdraw_synthetic_evidence(self.evidence_ids['S004'], reason)
        self.assertEqual(result['invalidated_snapshots'], [sa])
        a = self.store.state('CASE-EVAL-A')
        b = self.store.state('CASE-EVAL-B')
        self.assertEqual(a['snapshots'][0]['state'], 'stale')
        self.assertEqual(a['questions'][0]['state'], 'open')
        self.assertEqual(b['snapshots'][0]['state'], 'reviewed_in_demo')
        evidence = {e['id']: e for e in b['evidence']}
        self.assertEqual(evidence[self.evidence_ids['S005']]['state'], 'current')
        self.assertEqual(a['evidence_changes'][0]['reason'], reason)
        self.assertEqual(len(a['evidence_assessments']), 1)
        self.assertEqual(self.store.synthetic_evidence_text(self.evidence_ids['S004']),
                         self.sources['S004']['text'])
        with self.assertRaises(InvalidInput):
            self.store.create_snapshot(
                'CASE-EVAL-A', qa, 'A withdrawn evidence assessment cannot support a new draft.',
                [self.report_ids['S001']], [aa])


if __name__ == '__main__':
    unittest.main()
