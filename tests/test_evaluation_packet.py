"""Tests pin packet boundaries, not clinical correctness or external review."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'evaluation' / 'synthetic_v1' / 'fixture.json'

class PacketTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.evaluation_packet'),
                             'The offline packet projector has not been implemented')
        from tools import evaluation_packet
        self.module = evaluation_packet
        self.data = json.loads(FIXTURE.read_text())

    def test_early_packet_excludes_late_record_even_with_old_event_date(self):
        result = self.module.build_packet(self.data, 'R1')
        ids = {s['id'] for s in result['sources']}
        self.assertEqual(ids, {'S01', 'S02', 'S03', 'S04'})
        encoded = json.dumps(result)
        self.assertNotIn('LATER-RESULT-CANARY', encoded)
        self.assertNotIn('S08', encoded)
        self.assertNotIn('coordinator', encoded)
        self.assertNotIn('expected', encoded)

    def test_later_packet_contains_changes_without_removing_originals(self):
        result = self.module.build_packet(self.data, 'R2')
        self.assertIn('S07', {s['id'] for s in result['sources']})
        self.assertIn('S01', {s['id'] for s in result['sources']})
        self.assertNotIn('S08', {s['id'] for s in result['sources']})
        result = self.module.build_packet(self.data, 'R3')
        self.assertIn('S08', {s['id'] for s in result['sources']})

    def test_cutoff_is_inclusive_and_compares_aware_instants(self):
        data = copy.deepcopy(self.data)
        data['rounds'][0]['cutoff'] = '2026-05-03T08:00:00Z'
        self.assertEqual([s['id'] for s in self.module.build_packet(data, 'R1')['sources']], ['S01'])
        data['rounds'][0]['cutoff'] = '2026-05-03T04:00:00-04:00'
        self.assertEqual([s['id'] for s in self.module.build_packet(data, 'R1')['sources']], ['S01'])

    def test_projection_is_deterministic_and_does_not_mutate_source(self):
        before = copy.deepcopy(self.data)
        first = self.module.build_packet(self.data, 'R3')
        self.assertEqual(first, self.module.build_packet(self.data, 'R3'))
        self.assertEqual(before, self.data)
        self.assertTrue(first['simulation_only'])
        self.assertEqual(first['evaluation_status'], 'not_independently_evaluated')

    def test_source_tampering_rejected_before_projection(self):
        self.data['sources'][0]['content'] += 'TAMPER'
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.module.build_packet(self.data, 'R1')

    def test_naive_or_invalid_timestamps_rejected(self):
        for invalid in ['2026-05-03', '2026-05-03T08:00:00', 'later', None, True]:
            with self.subTest(invalid=invalid):
                data = copy.deepcopy(self.data)
                data['sources'][0]['available_at'] = invalid
                with self.assertRaises(ValueError):
                    self.module.build_packet(data, 'R1')

    def test_unknown_fields_and_duplicate_identifiers_rejected(self):
        variants = []
        data = copy.deepcopy(self.data); data['expected_answers'] = 'DO NOT EMIT'; variants.append(data)
        data = copy.deepcopy(self.data); data['sources'][0]['answer'] = 'DO NOT EMIT'; variants.append(data)
        data = copy.deepcopy(self.data); data['sources'][1]['id'] = data['sources'][0]['id']; variants.append(data)
        data = copy.deepcopy(self.data); data['cases'].append(data['cases'][0]); variants.append(data)
        data = copy.deepcopy(self.data); data['sources'][0]['target_case_id'] = 'CASE-NOT-IN-PACKET'; variants.append(data)
        for data in variants:
            with self.subTest(data=str(data)[:80]), self.assertRaises(ValueError):
                self.module.build_packet(data, 'R1')

    def test_unapproved_authorship_and_unbounded_content_rejected(self):
        for authorship in ['real-records', None, 'publicly-viewable']:
            data = copy.deepcopy(self.data); data['authorship'] = authorship
            with self.assertRaises(ValueError): self.module.validate_fixture(data)
        data = copy.deepcopy(self.data)
        data['sources'][0]['content'] = 'x' * 65537
        data['sources'][0]['sha256'] = hashlib.sha256(data['sources'][0]['content'].encode()).hexdigest()
        with self.assertRaises(ValueError): self.module.validate_fixture(data)

    def test_empty_round_and_unknown_round_are_distinct(self):
        data = copy.deepcopy(self.data)
        data['rounds'].append({'id': 'R0', 'cutoff': '2026-01-01T00:00:00Z'})
        self.assertEqual(self.module.build_packet(data, 'R0')['sources'], [])
        with self.assertRaisesRegex(ValueError, 'round'):
            self.module.build_packet(data, 'NO-ROUND')

    def test_duplicate_delivery_preserves_byte_hash_and_source_line_numbers(self):
        result = self.module.build_packet(self.data, 'R2')
        items = {s['id']: s for s in result['sources']}
        self.assertEqual(items['S01']['sha256'], items['S05']['sha256'])
        self.assertEqual(items['S01']['content'], items['S05']['content'])
        lines = items['S01']['content'].splitlines()
        self.assertEqual(lines[7].split('|')[1], 'not-assessed')

    def test_cli_exports_only_selected_round_and_errors_without_partial_output(self):
        args = [sys.executable, '-m', 'tools.evaluation_packet', str(FIXTURE), '--round', 'R1']
        run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(run.stdout)['round_id'], 'R1')
        bad = subprocess.run(args[:-1] + ['NO-ROUND'], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertEqual(bad.stdout, '')

if __name__ == '__main__': unittest.main()
