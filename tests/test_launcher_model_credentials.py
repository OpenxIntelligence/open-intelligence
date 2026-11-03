"""Launcher credential handling: model keys are cleared unless Meta live mode is explicitly enabled."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('run_open_intelligence', ROOT / 'run_open_intelligence.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

FAKE = {'META_API_KEY': 'fictional-test-value', 'META_API_OTHER': 'x', 'OPENAI_API_KEY': 'x',
        'ANTHROPIC_API_KEY': 'x', 'PATH': '/usr/bin'}


class LauncherCredentialTests(unittest.TestCase):
    def test_default_clears_every_model_credential(self):
        env = dict(FAKE)
        launcher.clear_model_credentials(env)
        self.assertEqual(env, {'PATH': '/usr/bin'})

    def test_meta_live_keeps_only_the_meta_api_key(self):
        env = dict(FAKE)
        launcher.clear_model_credentials(env, allow_meta_live=True)
        self.assertEqual(env, {'META_API_KEY': 'fictional-test-value', 'PATH': '/usr/bin'})


if __name__ == '__main__':
    unittest.main()
