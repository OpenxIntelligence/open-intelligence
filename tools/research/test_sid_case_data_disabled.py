"""No-data safety regression; entirely offline, with invented inputs."""
import tempfile
from pathlib import Path
import unittest
import public_case_intake
import single_cell_probe

class RetiredDataAccess(unittest.TestCase):
    def test_case_catalog_access_denied(self):
        with self.assertRaises(PermissionError):
            public_case_intake.fetch_catalog()

    def test_single_cell_access_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'never-downloaded'
            with self.assertRaises(PermissionError):
                single_cell_probe.acquire(single_cell_probe.CATALOG_URL, dest, 10)
            self.assertFalse(dest.exists())

if __name__ == '__main__':
    unittest.main()
