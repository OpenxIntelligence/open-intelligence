"""Tests of packaging mechanics, not clinical performance."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'evaluation_packet.py'
PACKET = ROOT / 'validation' / 'iv01' / 'cases.json'


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TOOL.is_file(), 'cutoff-aware packet builder not implemented')
        spec = importlib.util.spec_from_file_location('evaluation_packet', TOOL)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.data = json.loads(PACKET.read_text(encoding='utf-8'))

    def validate(self, value=None):
        return self.module.validate(self.data if value is None else value)

    def test_valid_manifest(self):
        self.validate()
        self.assertEqual(len(self.data['cases']), 2)

    def test_hash_tamper_rejected(self):
        self.data['sources'][0]['text'] += 'alteration'
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.validate()

    def test_naive_receipt_time_rejected(self):
        self.data['receipts'][0]['received_at'] = '2026-01-04T10:00:00'
        with self.assertRaisesRegex(ValueError, 'UTC'):
            self.validate()

    def test_unknown_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cutoff'):
            self.module.bundle(self.data, 'T99')

    def test_future_sources_and_receipts_absent(self):
        result = self.module.bundle(self.data, 'T0')
        self.assertNotIn('S007', [s['id'] for s in result['sources']])
        self.assertNotIn('R007', [s['id'] for s in result['receipts']])
        self.assertNotIn('Amends: EVAL-A-PATH@1', json.dumps(result))
        self.assertEqual(set(result), {'packet_id', 'synthetic', 'status', 'cutoff',
                                       'cases', 'questions', 'sources', 'receipts'})

    def test_late_old_report_not_visible_early(self):
        early = self.module.bundle(self.data, 'T0')
        late = self.module.bundle(self.data, 'T1')
        self.assertNotIn('S006', [s['id'] for s in early['sources']])
        self.assertIn('S006', [s['id'] for s in late['sources']])

    def test_duplicate_receipt_preserved_source_deduplicated(self):
        result = self.module.bundle(self.data, 'T2')
        self.assertEqual(sum(s['id'] == 'S001' for s in result['sources']), 1)
        self.assertEqual(sum(r['source_id'] == 'S001' for r in result['receipts']), 2)

    def test_wrong_case_input_not_silently_repaired(self):
        result = self.module.bundle(self.data, 'T1')
        source = next(s for s in result['sources'] if s['id'] == 'S008')
        receipt = next(r for r in result['receipts'] if r['source_id'] == 'S008')
        self.assertIn('Patient: CASE-EVAL-B', source['text'])
        self.assertEqual(receipt['target_case'], 'CASE-EVAL-A')

    def test_no_input_mutation_and_deterministic_result(self):
        before = copy.deepcopy(self.data)
        first = self.module.bundle(self.data, 'T1')
        self.assertEqual(first, self.module.bundle(self.data, 'T1'))
        self.assertEqual(self.data, before)

    def test_oracle_field_rejected(self):
        self.data['answer_key'] = 'answer must never leave the coordinator'
        with self.assertRaisesRegex(ValueError, 'fields'):
            self.validate()

    def test_missing_source_reference_rejected(self):
        self.data['receipts'][0]['source_id'] = 'MISSING'
        with self.assertRaisesRegex(ValueError, 'source'):
            self.validate()

    def test_duplicate_receipt_id_rejected(self):
        self.data['receipts'][1]['id'] = self.data['receipts'][0]['id']
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.validate()

    def test_unknown_target_case_rejected(self):
        self.data['receipts'][0]['target_case'] = 'NOT-A-CASE'
        with self.assertRaisesRegex(ValueError, 'case'):
            self.validate()

    def test_bad_synthetic_marker_rejected(self):
        self.data['synthetic'] = 'true'
        with self.assertRaisesRegex(ValueError, 'synthetic'):
            self.validate()

    def test_duplicate_source_id_rejected(self):
        self.data['sources'][1]['id'] = self.data['sources'][0]['id']
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.validate()

    def _replace_source_and_rehash(self, source_index, old, new):
        source = self.data['sources'][source_index]
        self.assertIn(old, source['text'])
        source['text'] = source['text'].replace(old, new)
        source['sha256'] = hashlib.sha256(source['text'].encode('utf-8')).hexdigest()

    def test_rejects_report_issued_after_its_receipt(self):
        self._replace_source_and_rehash(0, 'Issued-At: 2026-01-03',
                                        'Issued-At: 2026-01-20')
        with self.assertRaisesRegex(ValueError, 'issued after receipt'):
            self.validate()

    def test_rejects_evidence_issued_after_its_receipt(self):
        self._replace_source_and_rehash(3, 'Issued-At: 2026-01-07',
                                        'Issued-At: 2026-01-20')
        with self.assertRaisesRegex(ValueError, 'issued after receipt'):
            self.validate()

    def test_rejects_unqualified_evidence_rights_even_with_new_hash(self):
        self._replace_source_and_rehash(3, 'Rights: original-synthetic',
                                        'Rights: CC-BY-NC')
        with self.assertRaisesRegex(ValueError, 'rights'):
            self.validate()

    def test_rejects_report_for_undeclared_patient_even_with_new_hash(self):
        self._replace_source_and_rehash(0, 'Patient: CASE-EVAL-A',
                                        'Patient: UNKNOWN-SUBJECT')
        with self.assertRaisesRegex(ValueError, 'declared patient'):
            self.validate()

    def test_rejects_ambiguous_issue_date_headers(self):
        self._replace_source_and_rehash(0, 'Issued-At: 2026-01-03',
                                        'Issued-At: 2026-01-03\nIssued-At: 2026-01-03')
        with self.assertRaisesRegex(ValueError, 'Issued-At'):
            self.validate()

    def test_cli_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'inputs.json'
            command = [sys.executable, str(TOOL), '--packet', str(PACKET),
                       '--cutoff', 'T0', '--output', str(out)]
            one = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(one.returncode, 0, one.stderr)
            before = out.read_bytes()
            two = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(two.returncode, 0)
            self.assertEqual(before, out.read_bytes())
            self.assertNotIn('expected', out.read_text())


if __name__ == '__main__':
    unittest.main()
