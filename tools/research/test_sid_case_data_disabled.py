"""Offline regressions for retired patient-dataset acquisition paths."""
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import clinical_semantics_probe
import gdc_projection_probe
import public_case_intake
import public_evidence_probe
import rna_expression_probe
import single_cell_probe


class RetiredDataAccess(unittest.TestCase):
    def test_case_catalog_access_denied_before_network(self):
        with patch("public_case_intake.build_opener",
                   side_effect=AssertionError("Network construction forbidden")) as opener:
            with self.assertRaises(PermissionError):
                public_case_intake.fetch_catalog()
            opener.assert_not_called()

    def test_rna_access_denied_before_network(self):
        with patch("rna_expression_probe.build_opener",
                   side_effect=AssertionError("Network construction forbidden")) as opener:
            with self.assertRaises(PermissionError):
                rna_expression_probe.fetch(rna_expression_probe.CATALOG_URL, 10)
            opener.assert_not_called()

    def test_single_cell_access_denied_before_network_or_file_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "never-downloaded"
            with patch("single_cell_probe.urllib.request.build_opener",
                       side_effect=AssertionError("Network construction forbidden")) as opener:
                with self.assertRaises(PermissionError):
                    single_cell_probe.acquire(single_cell_probe.CATALOG_URL, dest, 10)
                opener.assert_not_called()
            self.assertFalse(dest.exists())

    def assert_cohort_probe_denied(self, probe):
        # Install the network double before invoking a potentially regressed path.
        with patch("public_evidence_probe.urlopen",
                   side_effect=AssertionError("Network access forbidden")) as opener:
            with patch("public_evidence_probe.time.sleep"):
                with self.assertRaises(PermissionError):
                    probe()
            opener.assert_not_called()

    def test_tcia_patient_acquisition_denied(self):
        self.assert_cohort_probe_denied(public_evidence_probe.tcia_probe)

    def test_gdc_patient_acquisition_denied(self):
        self.assert_cohort_probe_denied(public_evidence_probe.gdc_probe)

    def test_gdc_projection_acquisition_denied(self):
        self.assert_cohort_probe_denied(gdc_projection_probe.run_probe)

    def test_clinical_semantics_acquisition_denied(self):
        self.assert_cohort_probe_denied(clinical_semantics_probe.run_probe)


if __name__ == "__main__":
    unittest.main()
