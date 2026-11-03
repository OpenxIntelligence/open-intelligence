"""Run dependency-free patient presentation regressions in normal repository CI."""
from pathlib import Path
import subprocess
import unittest


class PatientStatusTests(unittest.TestCase):
    def test_patient_and_worklist_status_semantics(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            ['node', '--test', str(root / 'tests' / 'patient_status.test.js')],
            cwd=root, text=True, capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
