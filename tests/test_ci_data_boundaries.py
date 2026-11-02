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


    def test_guard_rejects_module_execution_of_retired_patient_data_adapters(self):
        modules=("public_case_intake","rna_expression_probe","single_cell_probe",
                 "public_evidence_probe","gdc_projection_probe","clinical_semantics_probe")
        for module in modules:
            commands=(f"PYTHONPATH=tools/research python -m {module}",
                      f"python3 -u -m tools.research.{module}",
                      f"python3.12 -I -m research.{module}")
            for command in commands:
                with self.subTest(command=command):
                    self.assertTrue(audit.scan_workflow_text(
                        f"run: {command} --output fictional.json","sample.yml"))

    def test_guard_preserves_public_metadata_and_offline_module_commands(self):
        for command in ("python -m tools.crossref_metadata",
                        "python -m trial_screening_probe",
                        "python -m tools.research.trial_screening_probe",
                        "python -m unittest discover -s tools/research",
                        "python -m tools.research.rna_expression_probe_helper"):
            with self.subTest(command=command):
                self.assertEqual(audit.scan_workflow_text(
                    f"run: {command}","sample.yml"),[])

    def test_guard_checks_retired_modules_after_an_allowed_command(self):
        sample=("run: python -m unittest --help && "
                "PYTHONPATH=tools/research python -m gdc_projection_probe")
        self.assertTrue(audit.scan_workflow_text(sample,"sample.yml"))


if __name__=="__main__":
    unittest.main()
