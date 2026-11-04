"""Engineering baseline integrity; fixtures are independently fictional."""
import copy
import importlib.util
import hashlib
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
        from open_intelligence.pdf_worker import make_rendition
        case = self.module.corpus()[2]
        original = make_rendition(['\n'.join(p) + '\n' for p in case.pages])
        original.update(sha256=hashlib.sha256(case.raw).hexdigest(),
                        byte_count=len(case.raw), clinical_review='not_performed')
        self.assertTrue(all(self.module.checks(case, original).values()))
        for field, expected_check in (('text', 'exact_lines_and_anchors'),
                                      ('page', 'exact_lines_and_anchors'),
                                      ('sha256', 'original_bytes')):
            value = copy.deepcopy(original)
            if field == 'sha256':
                value['sha256'] = '0' * 64
            elif field == 'text':
                value['lines'][2]['text'] = value['lines'][2]['text'].replace('mg/L', 'g/L')
            else:
                value['lines'][0]['page'] = 99
            with self.subTest(field=field):
                self.assertIs(self.module.checks(case, value)[expected_check], False)

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

    def test_missing_or_forged_extractor_cannot_pass_with_recomputed_hash(self):
        from open_intelligence.pdf_worker import make_rendition, canonical_json
        case = self.module.corpus()[2]
        value = make_rendition(['\n'.join(p) + '\n' for p in case.pages])
        value.update(sha256=hashlib.sha256(case.raw).hexdigest(),
                     byte_count=len(case.raw), clinical_review='not_performed')
        self.assertTrue(all(self.module.checks(case, value).values()))
        for identity in (None, {}, [], {'name': 'pypdf', 'version': 'unqualified'}):
            altered = copy.deepcopy(value)
            altered['extractor'] = identity
            payload = {k: altered[k] for k in ('text', 'lines', 'pages', 'page_count', 'extractor')}
            altered['extraction_sha256'] = hashlib.sha256(canonical_json(payload)).hexdigest()
            self.assertFalse(all(self.module.checks(case, altered).values()))

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
