"""Run the no-personal-case boundary in the ordinary synthetic test suite."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PersonalCaseBoundary(unittest.TestCase):
    def test_retired_entrypoints_and_preserved_synthetic_utilities(self):
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        result = subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/research',
             '-p', 'test_sid_case_data_disabled.py', '-v'],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_retired_clis_cannot_opt_in_or_write_an_output(self):
        for name in ('public_case_intake.py', 'rna_expression_probe.py', 'single_cell_probe.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / 'output.json'
                result = subprocess.run(
                    [sys.executable, str(ROOT/'tools/research'/name), '--live', '--output', str(dest)],
                    cwd=ROOT, capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Retired personal-case runner', result.stderr)
                self.assertFalse(dest.exists())

if __name__ == '__main__':
    unittest.main()
