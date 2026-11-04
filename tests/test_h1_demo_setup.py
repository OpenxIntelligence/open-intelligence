"""Operator demo setup must preserve identity and avoid implicit reset/regrant."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/h1_demo.py'


class DemoSetupTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location('h1_demo', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_repeat_setup_keeps_the_same_patient_request_and_project(self):
        demo = self.module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'demo'
            first = demo.load_or_create(directory)
            second = demo.load_or_create(directory)
            self.assertEqual(first, second)
            self.assertEqual((directory / 'state.json').stat().st_mode & 0o777, 0o600)
            self.assertNotIn(first['token'], json.dumps(demo.access_document(first, [])))
            self.assertEqual(demo.access_document(first, [])['credentials'][0]['patient_ids'], [])

    def test_bad_state_is_not_silently_replaced_with_another_demo(self):
        demo = self.module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path = directory / 'state.json'
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                demo.load_or_create(directory)
            self.assertEqual(path.read_text(), '{broken')

    def test_setup_refuses_an_unowned_nonempty_directory(self):
        demo = self.module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / 'keep.txt').write_text('not demo data')
            with self.assertRaises(ValueError):
                demo.load_or_create(directory)
            self.assertFalse((directory / 'state.json').exists())

    def test_demo_grants_are_only_for_its_created_patient(self):
        demo = self.module()
        with tempfile.TemporaryDirectory() as temp:
            state = demo.load_or_create(Path(temp) / 'demo')
            document = demo.access_document(state, ['PAT-' + 'A' * 32])
            grant = document['credentials'][0]
            self.assertEqual(grant['patient_ids'], ['PAT-' + 'A' * 32])
            self.assertEqual(grant['purpose'], 'operations')
            self.assertNotIn('case_binding_revoke', grant['actions'])
            self.assertNotIn('authored_evidence_withdraw', grant['actions'])

    def test_stop_never_removes_volumes_or_selects_another_project(self):
        demo = self.module()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'demo'
            state = demo.load_or_create(directory)
            command = demo.compose_command(state)
            self.assertEqual(command[command.index('--project-name') + 1], state['project'])
            self.assertNotIn('--volumes', command + ['stop'])
            self.assertNotIn('down', command + ['stop'])


if __name__ == '__main__':
    unittest.main()
