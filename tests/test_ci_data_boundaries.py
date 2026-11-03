"""Regression checks for a CI pathway independent of identifiable case data."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "audit_ci_data_boundaries",ROOT/"tools"/"audit_ci_data_boundaries.py")
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class CIDataBoundaryTests(unittest.TestCase):
    def test_current_workflows_never_run_a_known_public_person_data_probe(self):
        self.assertEqual(audit.main(),0)

    def test_guard_rejects_named_person_catalog_download(self):
        sample="run: python tools/research/public_case_intake.py --live --output case.json"
        self.assertTrue(audit.scan_workflow_text(sample,"sample.yml"))

    def test_guard_rejects_bulk_rna_and_cell_matrix_download(self):
        for script in ("rna_expression_probe","single_cell_probe"):
            with self.subTest(script=script):
                sample=f"run: python tools/research/{script}.py --output result.json"
                self.assertTrue(audit.scan_workflow_text(sample,"sample.yml"))

    def test_guard_rejects_known_person_case_endpoint(self):
        self.assertTrue(audit.scan_workflow_text(
            "run: curl https://osteosarc.com/data/catalog/datasets.json","sample.yml"))

    def test_guard_accepts_offline_synthetic_regression_command(self):
        sample="run: python -m unittest discover -s tools/research -p test_rna_expression_probe.py -v"
        self.assertEqual(audit.scan_workflow_text(sample,"sample.yml"),[])

    def test_guard_rejects_module_and_common_interpreter_flags(self):
        for command in (
            'python -m tools.research.public_evidence_probe --output result.json',
            'python -B tools/research/public_evidence_probe.py --output result.json',
            'python3.12 -W ignore -X dev -u tools/research/gdc_projection_probe.py',
        ):
            with self.subTest(command=command):
                self.assertTrue(audit.scan_workflow_text('run: ' + command, 'sample.yml'))

    def test_guard_checks_every_script_on_a_shell_line(self):
        command = ('run: python tools/research/runtime_probe.py --output safe.json && '
                   'python tools/research/public_evidence_probe.py --output result.json')
        self.assertTrue(audit.scan_workflow_text(command, 'sample.yml'))

    def test_receipt_records_nonpassing_audit_without_inventing_data_facts(self):
        self.assertTrue(callable(getattr(audit, 'build_receipt', None)))
        for outcome in ('failure', 'skipped', 'cancelled', ''):
            with self.subTest(outcome=outcome):
                receipt = audit.build_receipt(checkout='synthetic-test-commit',
                    audit_outcome=outcome, source_sha256={})
                self.assertFalse(receipt['known_entrypoint_scan']['passed'])
                self.assertEqual(receipt['known_entrypoint_scan']['outcome'], outcome or 'unknown')
                self.assertFalse(receipt['runtime_data_access_verified'])
                self.assertNotIn('patient_data_download_steps', receipt)
                self.assertNotIn('external_patient_data_inputs', receipt)

    def test_receipt_success_describes_only_the_static_scan(self):
        self.assertTrue(callable(getattr(audit, 'build_receipt', None)))
        receipt = audit.build_receipt(checkout='synthetic-test-commit',
            audit_outcome='success', source_sha256={'original.py':'fixture-hash'})
        self.assertTrue(receipt['known_entrypoint_scan']['passed'])
        self.assertFalse(receipt['runtime_data_access_verified'])
        self.assertEqual(receipt['declared_fixture_policy'], 'independently_authored_synthetic_only')
        self.assertEqual(receipt['sources_sha256'], {'original.py':'fixture-hash'})


if __name__=="__main__":
    unittest.main()
