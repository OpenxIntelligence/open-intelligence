"""No-data safety regressions. All payloads and paths are independently invented.

These tests intercept network construction; they never request a patient asset.
Generic parsers remain available solely for the original synthetic fixtures.
"""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import public_case_intake
import rna_expression_probe
import single_cell_probe


class RetiredDataAccess(unittest.TestCase):
    def test_case_catalog_access_denied_before_transport(self):
        with patch.object(public_case_intake, 'build_opener') as transport:
            with self.assertRaises(PermissionError):
                public_case_intake.fetch_catalog()
            transport.assert_not_called()

    def test_catalog_runner_cannot_use_a_replaced_fetcher(self):
        with patch.object(public_case_intake, 'fetch_catalog',
                          side_effect=AssertionError('fetch must not be called')) as fetch:
            with self.assertRaises(PermissionError):
                public_case_intake.run_probe()
            fetch.assert_not_called()

    def test_rna_fetch_denied_before_transport(self):
        with patch.object(rna_expression_probe, 'build_opener',
                          side_effect=AssertionError('network construction attempted')) as transport:
            with self.assertRaises(PermissionError):
                rna_expression_probe.fetch(rna_expression_probe.CATALOG_URL, 1)
            transport.assert_not_called()

    def test_rna_denial_is_not_an_endpoint_allowlist(self):
        with patch.object(rna_expression_probe, 'build_opener') as transport:
            with self.assertRaises(PermissionError):
                rna_expression_probe.fetch('https://example.invalid/not-a-patient', 1)
            transport.assert_not_called()

    def test_rna_runner_cannot_use_a_replaced_fetcher(self):
        with patch.object(rna_expression_probe, 'fetch',
                          side_effect=AssertionError('fetch must not be called')) as fetch:
            with self.assertRaises(PermissionError):
                rna_expression_probe.run()
            fetch.assert_not_called()

    def test_single_cell_access_denied_before_transport_or_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'never-downloaded'
            with patch('urllib.request.build_opener') as transport:
                with self.assertRaises(PermissionError):
                    single_cell_probe.acquire(single_cell_probe.CATALOG_URL, dest, 10)
                transport.assert_not_called()
            self.assertFalse(dest.exists())

    def test_case_specific_local_analysis_denied_before_file_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'nonexistent-original-fixture.h5ad'
            # No real file exists; PermissionError must happen before scientific
            # imports or opening even this non-existent synthetic path.
            with self.assertRaises(PermissionError):
                single_cell_probe.inspect_and_analyze(dest)
            self.assertFalse(dest.exists())

    def test_generic_gct_parser_still_accepts_original_synthetic_input(self):
        data = b'#1.2\n1\t1\nName\tDescription\tINVENTED\nGENE.1\tEXAMPLE\t2\n'
        out = rna_expression_probe.parse_gct(data, 'INVENTED')
        self.assertEqual(out['genes']['GENE.1']['tpm'], 2)

    def test_generic_single_cell_summary_still_accepts_invented_values(self):
        out = single_cell_probe.summarize(
            values=[[0.0], [2.0]], genes=['INVENTED_GENE'],
            samples=['invented', 'invented'], clusters=['0', '0'],
            labels=[None, None])
        self.assertEqual(out['n_cells'], 2)
        self.assertFalse(out['malignancy_established'])

if __name__ == '__main__':
    unittest.main()
