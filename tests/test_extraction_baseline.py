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
    @staticmethod
    def controlled_pdf(case):
        from open_intelligence.pdf_worker import make_rendition
        value = make_rendition(['\n'.join(p) + '\n' for p in case.pages])
        value.update(sha256=hashlib.sha256(case.raw).hexdigest(), byte_count=len(case.raw),
                     clinical_review='not_performed', filename=case.filename, media_type='application/pdf',
                     extraction_method='pypdf-text-v1', annotation_method='manual-exact-extraction-line-selection')
        return value

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
        self.assertEqual((report['accepted_count'], report['rejected_count']), (8, 8))
        self.assertEqual([r['fixture_id'] for r in report['results']],
                         [f'E{i:02}' for i in range(1, 17)])
        probe = report['layout_probe']
        self.assertEqual((probe['case_count'], probe['measured_count']), (2, 2))
        self.assertEqual(probe['results'][0]['outcome'], 'row_order_preserved')
        self.assertEqual(probe['all_rows_preserved'], probe['preserved_count'] == 2)
        self.assertFalse(report['clinical_validation'])
        self.assertIsNone(report['review_minutes'])

    def test_bad_units_anchors_and_hashes_cannot_pass(self):
        case = self.module.corpus()[2]
        original = self.controlled_pdf(case)
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

    def test_wrong_or_absent_source_attribution_cannot_pass(self):
        for case in (self.module.corpus()[0], self.module.corpus()[2]):
            original = preview_document(case.raw, case.filename)
            self.assertTrue(all(self.module.checks(case, original).values()))
            for field in ('filename', 'media_type', 'extraction_method', 'annotation_method'):
                for missing in (True, False):
                    altered = dict(original)
                    if missing:
                        del altered[field]
                    else:
                        altered[field] = 'unrelated'
                    with self.subTest(case=case.id, field=field, missing=missing):
                        self.assertFalse(all(self.module.checks(case, altered).values()))

    def test_layout_probe_distinguishes_order_loss_content_loss_and_failed_measurement(self):
        from open_intelligence.pdf_worker import make_rendition

        def result_for(text, wrong_identity=False):
            def controlled(raw, name):
                value = preview_document(raw, name)
                value.update(make_rendition([text]))
                if wrong_identity:
                    value['filename'] = 'wrong.pdf'
                return value
            return controlled

        cases = [
            ('Specimen A 2.5 mg/L\nSpecimen B 25 mg/L', False, 'row_order_preserved', 2, True),
            ('Specimen A Specimen B\n2.5 mg/L 25 mg/L', False, 'order_changed', 2, False),
            ('Specimen A 25 mg/L\nSpecimen B 25 mg/L', False, 'cell_content_changed', 2, False),
            ('Specimen A 2.5 mg/L\nSpecimen B 25 mg/L', True, 'error', 0, None),
        ]
        for text, wrong_identity, outcome, measured, verdict in cases:
            probe = self.module.probe_layout(result_for(text, wrong_identity))
            with self.subTest(outcome=outcome):
                self.assertEqual([r['outcome'] for r in probe['results']], [outcome] * 2)
                self.assertEqual(probe['measured_count'], measured)
                self.assertIs(probe['all_rows_preserved'], verdict)
                self.assertNotIn('Specimen', json.dumps(probe))

    def test_strict_layout_command_returns_nonzero_and_still_writes_the_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index, (passed, order, exit_code) in enumerate(
                    ((True, False, 1), (True, True, 0), (False, None, 1))):
                report = {'passed': passed, 'layout_probe': {'all_rows_preserved': order}}
                target = Path(tmp) / f'{index}.json'
                with patch.object(self.module, 'run_suite', return_value=report):
                    self.assertEqual(self.module.main(
                        ['--require-layout-order', '--output', str(target)]), exit_code)
                self.assertEqual(json.loads(target.read_text()), report)

    def test_duplicate_or_missing_contrast_cannot_qualify_even_with_all_intakes_passing(self):
        first, second = self.module.layout_inputs()
        for inputs in ((first, (second[0], first[1])), (first,)):
            with self.subTest(size=len(inputs)), patch.object(self.module, 'layout_inputs', return_value=inputs):
                report = self.module.run_suite()
                self.assertEqual(report['passed_count'], 16)
                self.assertFalse(report['passed'])
                probe = report['layout_probe']
                self.assertEqual((probe['case_count'], probe['measured_count']), (2, 1))
                self.assertEqual(probe['results'][1]['outcome'], 'error')
                self.assertIsNone(probe['all_rows_preserved'])

    def test_missing_or_forged_extractor_cannot_pass_with_recomputed_hash(self):
        from open_intelligence.pdf_worker import canonical_json
        case = self.module.corpus()[2]
        value = self.controlled_pdf(case)
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
