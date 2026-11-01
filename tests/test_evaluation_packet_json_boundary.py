"""CLI ambiguity regressions for the existing fictional evaluation packager.

Minimal parser-test fixtures only, not new reference cases or clinical evidence.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'evaluation_packet.py'
EARLY = '2026-01-10T12:00:00Z'
LATE = '2026-01-20T12:00:00Z'


def packet_text():
    text = ('OI-SYNTHETIC-REPORT/1\nPatient: CASE-JSON\n'
            'Document: JSON-REPORT\nType: clinical\n'
            'Event-Date: 2026-01-02\nIssued-At: 2026-01-03\n'
            'Finding: note|not-reported|Original fictional parser test only.\n')
    return json.dumps({
        'version': 1, 'packet_id': 'OI-JSON-TEST',
        'project': 'Open Intelligence', 'synthetic': True,
        'status': 'engineering-practice-only', 'reference_code_commit': 'a' * 40,
        'authorship': 'Original fictional parser-test content, not clinical evidence.',
        'cutoffs': {'T0': EARLY},
        'cases': [{'id': 'CASE-JSON', 'label': 'Fictional JSON boundary case'}],
        'questions': ['What source information was received by this cutoff?'],
        'sources': [{'id': 'SOURCE-JSON', 'kind': 'report', 'text': text,
                     'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}],
        'receipts': [{'id': 'RECEIPT-JSON', 'source_id': 'SOURCE-JSON',
                      'target_case': 'CASE-JSON', 'received_at': LATE}],
    })


class PacketJsonBoundaryTests(unittest.TestCase):
    def run_cli(self, text, *, export=True, existing=None):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'packet.json'
            output = Path(tmp) / 'inputs.json'
            manifest.write_text(text, encoding='utf-8')
            if existing is not None:
                output.write_bytes(existing)
            before = manifest.read_bytes()
            command = [sys.executable, str(TOOL), '--packet', str(manifest)]
            if export:
                command += ['--cutoff', 'T0', '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=10, check=False)
            self.assertEqual(manifest.read_bytes(), before, 'input was modified')
            produced = output.read_bytes() if output.exists() else None
            return result, produced

    def assert_ambiguous_rejected(self, text, *, export=True):
        result, output = self.run_cli(text, export=export)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('duplicate JSON key', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIsNone(output, 'ambiguous input created a participant packet')

    def test_conflicting_root_synthetic_flag_rejected(self):
        raw = packet_text().replace('"synthetic": true',
                                    '"synthetic": false, "synthetic": true')
        self.assert_ambiguous_rejected(raw)

    def test_duplicate_cutoff_cannot_include_future_source(self):
        raw = packet_text().replace('"T0": "' + EARLY + '"',
                                    '"T0": "' + EARLY + '", "T0": "' + LATE + '"')
        self.assert_ambiguous_rejected(raw)

    def test_duplicate_receipt_time_cannot_move_future_source_earlier(self):
        raw = packet_text().replace('"received_at": "' + LATE + '"',
                                    '"received_at": "' + LATE + '", "received_at": "' + EARLY + '"')
        self.assert_ambiguous_rejected(raw)

    def test_duplicate_source_hash_does_not_hide_invalid_first_value(self):
        raw = packet_text().replace('"sha256": ', '"sha256": "invalid-first-hash", "sha256": ')
        self.assert_ambiguous_rejected(raw)

    def test_identical_repeated_fields_are_also_ambiguous(self):
        raw = packet_text().replace('"version": 1', '"version": 1, "version": 1')
        self.assert_ambiguous_rejected(raw, export=False)

    def test_escaped_member_name_cannot_hide_duplicate(self):
        raw = packet_text().replace('"synthetic": true',
                                    '"synthetic": false, "synth\\u0065tic": true')
        self.assert_ambiguous_rejected(raw)

    def test_unambiguous_input_preserves_cutoff_and_is_deterministic(self):
        one, first = self.run_cli(packet_text())
        two, second = self.run_cli(packet_text())
        self.assertEqual(one.returncode, 0, one.stderr)
        self.assertEqual(two.returncode, 0, two.stderr)
        self.assertEqual(first, second)
        output = json.loads(first)
        self.assertEqual(output['cutoff'], EARLY)
        self.assertEqual(output['sources'], [])
        self.assertEqual(output['receipts'], [])
        self.assertEqual(output['cases'], [])

    def test_existing_output_not_replaced(self):
        marker = b'Previously frozen participant packet\n'
        result, output = self.run_cli(packet_text(), existing=marker)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output, marker)


if __name__ == '__main__':
    unittest.main()
