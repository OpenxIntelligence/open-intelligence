"""The normal application suite executes the file-boundary JavaScript contracts."""
import subprocess
import unittest
from pathlib import Path


class CaseIntakeTests(unittest.TestCase):
    def test_original_file_intake_contract(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', '--test', 'tests/test_intake.js'], cwd=root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
