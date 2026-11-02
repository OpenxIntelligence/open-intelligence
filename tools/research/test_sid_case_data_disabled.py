"""Safety regression: no personal data fetch even via a manual entry point.
All inputs are synthetic or literal strings. Tests never perform network calls.
"""
import tempfile
from pathlib import Path
import unittest

import public_case_intake
import rna_expression_probe
import single_cell_probe


class SidDataAccessIsDisabled(unittest.TestCase):
    def test_rna_data_fetch_fails_closed(self):
        with self.assertRaises(PermissionError):
            rna_expression_probe.fetch(rna_expression_probe.CATALOG_URL, 256)

    def test_single_cell_data_fetch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                single_cell_probe.acquire(single_cell_probe.CATALOG_URL,
                                          Path(tmp) / 'not-downloaded', 256)
            self.assertFalse((Path(tmp) / 'not-downloaded').exists())

    def test_public_case_catalog_fetch_fails_closed(self):
        with self.assertRaises(PermissionError):
            public_case_intake.fetch_catalog()


if __name__ == '__main__':
    unittest.main()
