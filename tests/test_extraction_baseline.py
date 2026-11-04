"""Engineering baseline integrity; fixtures are independently fictional."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from open_intelligence.document_intake import preview_document
from open_intelligence.store import InvalidInput


class ExtractionBaselineTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.extraction_baseline'),
                             'Executable extraction baseline is missing')
        from tools import extraction_baseline
        self.module = extraction_baseline

    def test_actual_corpus_and_raw_denominators(self):
        report = self.module.run_suite()
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['case_count'], len(report['results']))
        self.assertEqual(report['passed_count'], report['case_count'])
        self.assertGreaterEqual(report['accepted_count'], 4)
        self.assertGreaterEqual(report['rejected_count'], 3)
        self.assertFalse(report['clinical_validation'])
        self.assertIsNone(report['review_minutes'])

    def test_bad_units_anchors_and_hashes_cannot_pass(self):
        for field in ('text', 'page', 'sha256'):
            def corrupt(raw, filename):
                value = copy.deepcopy(preview_document(raw, filename))
                if field == 'sha256':
                    value['sha256'] = '0' * 64
                elif field == 'text':
                    value['lines'][0]['text'] += ' changed'
                elif filename.endswith('.pdf'):
                    value['lines'][0]['page'] = 99
                return value
            with self.subTest(field=field):
                self.assertFalse(self.module.run_suite(adapter=corrupt)['passed'])

    def test_errors_are_counted_without_exception_text(self):
        for error in (RuntimeError('SECRET SENTINEL'),
                      InvalidInput('PDF extraction requires the exact pinned pypdf 6.21.4 installation')):
            def fail(raw, filename):
                raise error
            report = self.module.run_suite(adapter=fail)
            self.assertFalse(report['passed'])
            self.assertEqual(report['passed_count'], 0)
            self.assertEqual(report['error_count'], report['case_count'])
            self.assertNotIn('SECRET SENTINEL', json.dumps(report))

    def test_malformed_outputs_fail_and_do_not_leak(self):
        for value in (None, [], {'text': 'SECRET SENTINEL'}, {'lines': [None]}):
            report = self.module.run_suite(adapter=lambda raw, name: value)
            self.assertFalse(report['passed'])
            self.assertNotIn('SECRET SENTINEL', json.dumps(report))

    def test_metrics_have_only_allowlisted_fields(self):
        report = self.module.run_suite()
        for metric in report['metrics']:
            self.assertEqual(set(metric), {'fixture_id', 'operation', 'outcome', 'duration_ms'})
        text = json.dumps(report['metrics'])
        for forbidden in ('sha256', 'Fictional', '.pdf', 'pending', 'filename', 'exception'):
            self.assertNotIn(forbidden, text)

    def test_invalid_clock_cannot_emit_nonfinite_timing(self):
        for value in (float('nan'), float('inf')):
            report = self.module.run_suite(clock=lambda: value)
            self.assertFalse(report['passed'])
            json.dumps(report, allow_nan=False)

    def test_cli_exclusive_output_and_failure_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'receipt.json'
            with patch.object(self.module, 'run_suite', return_value={'passed': False}):
                self.assertEqual(self.module.main(['--output', str(target)]), 1)
                original = target.read_bytes()
                self.assertEqual(self.module.main(['--output', str(target)]), 2)
                self.assertEqual(target.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
