"""Legacy data entrypoints must fail before network access or output creation.

No external record is fetched. Socket and HTTP boundaries are intercepted even
when this regression is run against the pre-fix implementation.
"""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import public_case_intake as catalog
import rna_expression_probe as rna
import single_cell_probe as cells


class PersonalDataBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.network_attempts = []

        def forbidden(*args, **kwargs):
            self.network_attempts.append(True)
            raise AssertionError('Network access attempted by a retired data entrypoint')

        for target in ('urllib.request.OpenerDirector.open', 'urllib.request.urlopen',
                       'socket.create_connection', 'socket.socket'):
            self.stack.enter_context(patch(target, side_effect=forbidden))
        self.tmp = self.stack.enter_context(tempfile.TemporaryDirectory())

    def test_legacy_clis_cannot_be_enabled_by_old_opt_in_or_output_arguments(self):
        for module, extra in ((catalog, []), (catalog, ['--live']),
                              (rna, []), (cells, [])):
            with self.subTest(module=module.__name__, flags=extra):
                output = Path(self.tmp) / module.__name__ / 'result.json'
                stdout, stderr = io.StringIO(), io.StringIO()
                code, error = None, None
                with patch.object(sys, 'argv', [module.__file__, *extra, '--output', str(output)]), \
                        redirect_stdout(stdout), redirect_stderr(stderr):
                    try:
                        module.main()
                    except SystemExit as exc:
                        code = exc.code
                    except Exception as exc:
                        error = exc
                self.assertIsNone(error, 'Retired CLI must exit with a policy error')
                self.assertEqual(code, 2)
                self.assertIn('disabled', stderr.getvalue().lower())
                self.assertFalse(output.parent.exists(), 'No output or temporary data directory is created')
                self.assertEqual(self.network_attempts, [])

    def test_direct_legacy_calls_fail_before_fetch_or_case_specific_analysis(self):
        destination = Path(self.tmp) / 'source.h5ad'
        attempts = (
            ('catalog fetch', lambda: catalog.fetch_catalog()),
            ('catalog run', lambda: catalog.run_probe()),
            ('RNA fetch', lambda: rna.fetch(getattr(catalog, 'CATALOG_URL', 'https://example.invalid'), 100)),
            ('RNA run', lambda: rna.run()),
            ('cell acquire', lambda: cells.acquire(getattr(cells, 'H5_URL', 'https://example.invalid'), destination, 100)),
            ('case-specific cell analysis', lambda: cells.inspect_and_analyze(destination)),
        )
        for label, call in attempts:
            with self.subTest(entrypoint=label):
                error = None
                try:
                    call()
                except Exception as exc:
                    error = exc
                self.assertIsInstance(error, PermissionError)
                self.assertIn('disabled', str(error).lower())
                self.assertEqual(self.network_attempts, [])
                self.assertFalse(destination.exists())

    def test_no_catalog_url_is_an_authorization_to_download(self):
        for url in (getattr(catalog, 'CATALOG_URL', ''), 'https://example.invalid/catalog.json', ''):
            with self.subTest(url=url), self.assertRaises(PermissionError):
                catalog.validate_fetch_url(url)
        self.assertEqual(self.network_attempts, [])

    def test_module_invocation_returns_the_same_policy_failure(self):
        root = Path(__file__).resolve().parents[2]
        for name in ('public_case_intake', 'rna_expression_probe', 'single_cell_probe'):
            with self.subTest(module=name):
                output = Path(self.tmp) / name / 'module-result.json'
                # Guard the child too, so a future regression cannot fetch data
                # while this test is trying to prove that the entrypoint is retired.
                runner = (
                    'import socket,urllib.request,runpy,sys\n'
                    'def denied(*args,**kwargs): raise AssertionError("network denied by test")\n'
                    'socket.socket=socket.create_connection=denied\n'
                    'urllib.request.urlopen=urllib.request.OpenerDirector.open=denied\n'
                    'sys.argv=sys.argv[1:]\n'
                    'runpy.run_module(sys.argv[0],run_name="__main__")\n'
                )
                result = subprocess.run(
                    [sys.executable, '-c', runner, 'tools.research.' + name, '--live', '--output', str(output)],
                    cwd=root, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertIn('disabled', result.stderr.lower())
                self.assertNotIn('Traceback', result.stderr)
                self.assertFalse(output.parent.exists())


if __name__ == '__main__':
    unittest.main()
