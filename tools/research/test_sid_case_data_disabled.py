"""No-data safety regression; entirely offline, with invented inputs."""
import tempfile
from pathlib import Path
import unittest
import public_case_intake
import rna_expression_probe
import single_cell_probe

class RetiredDataAccess(unittest.TestCase):
    def test_case_catalog_access_denied(self):
        with self.assertRaises(PermissionError):
            public_case_intake.fetch_catalog()

    def test_rna_access_denied(self):
        with self.assertRaises(PermissionError):
            rna_expression_probe.fetch('https://example.invalid/rna-seq/reprocessed/README.md', 10)

    def test_rna_run_denied_without_network(self):
        with self.assertRaises(PermissionError):
            rna_expression_probe.run()

    def test_single_cell_access_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'never-downloaded'
            with self.assertRaises(PermissionError):
                single_cell_probe.acquire(single_cell_probe.CATALOG_URL, dest, 10)
            self.assertFalse(dest.exists())

if __name__ == '__main__':
    unittest.main()
