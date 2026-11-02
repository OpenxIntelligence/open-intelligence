"""Vendor-independent imaging backend checks using original fictional reports."""
from __future__ import annotations

from pathlib import Path
import unittest

from open_intelligence.imaging_backend_contract import check_dicomweb_metadata
from open_intelligence.store import CaseStore, InvalidInput

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def qido(source_id: int, *, case_id="CASE-ALPHA", study="1.2.3",
         series="1.2.3.1", instance="1.2.3.1.1", day="20260517",
         modality="CT") -> dict:
    def tag(vr, value):
        return {"vr": vr, "Value": [value]}
    return {
        "oi_test_case_id": case_id,
        "oi_test_source_version_id": source_id,
        "0020000D": tag("UI", study),
        "0020000E": tag("UI", series),
        "00080018": tag("UI", instance),
        "00080020": tag("DA", day),
        "00080060": tag("CS", modality),
    }


class ImagingBackendContractTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Independent fictional Alpha")
        self.store.add_case("CASE-BETA", "Independent fictional Beta")
        self.source = self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-imaging.txt").read_bytes()
        )["source_id"]

    def tearDown(self):
        self.store.close()

    def test_study_series_instance_inventory_with_exact_source_receipt(self):
        rows = [
            qido(self.source, instance="1.2.3.1.2"),
            qido(self.source),
            qido(self.source, series="1.2.3.2", instance="1.2.3.2.1")
        ]
        result = check_dicomweb_metadata(self.store, "CASE-ALPHA", rows)
        self.assertEqual((result["study_count"], result["series_count"],
                          result["instance_count"]), (1, 2, 3))
        first = result["instances"][0]
        self.assertEqual(first["source_version_id"], self.source)
        self.assertEqual(first["source_document"], "IMG-ALPHA")
        self.assertEqual(first["source_event_date"], "2026-05-17")
        self.assertEqual(first["source_issued_at"], "2026-05-18")
        self.assertEqual(len(first["source_sha256"]), 64)
        self.assertFalse(result["pixel_data_processed"])
        self.assertFalse(result["wado_rs_object_retrieved"])
        self.assertFalse(result["stow_rs_object_stored"])
        self.assertEqual(result["clinical_review_state"], "not_performed")

    def test_missing_studies_are_unknown_not_normal_or_negative(self):
        result = check_dicomweb_metadata(self.store, "CASE-ALPHA", [])
        self.assertEqual(result["empty_input_state"], "not_provided")
        self.assertEqual(result["instances"], [])
        self.assertEqual(result["instance_count"], 0)

    def test_patient_isolation_applies_to_report_source_not_dicom_person_name(self):
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(self.store, "CASE-BETA", [qido(self.source)])
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(
                self.store, "CASE-ALPHA", [qido(self.source, case_id="CASE-BETA")]
            )
        row = qido(self.source)
        row["00100020"] = {"vr": "LO", "Value": ["CASE-BETA"]}
        result = check_dicomweb_metadata(self.store, "CASE-ALPHA", [row])
        # DICOM PatientID does not grant or alter authorized case binding.
        self.assertEqual(result["case_id"], "CASE-ALPHA")
        self.assertNotIn("CASE-BETA", str(result))

    def test_report_amendment_invalidates_old_study_binding(self):
        amended = (
            "OI-SYNTHETIC-REPORT/1\n"
            "Patient: CASE-ALPHA\n"
            "Document: IMG-ALPHA\n"
            "Type: imaging\n"
            "Event-Date: 2026-05-17\n"
            "Issued-At: 2026-05-19\n"
            "Amends: IMG-ALPHA@1\n"
            "Finding: comparison|reported|A corrected fictional report is issued.\n"
        ).encode()
        new_id = self.store.import_report("CASE-ALPHA", amended)["source_id"]
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(self.store, "CASE-ALPHA", [qido(self.source)])
        current = check_dicomweb_metadata(
            self.store, "CASE-ALPHA", [qido(new_id)]
        )
        self.assertEqual(current["instances"][0]["source_version"], 2)
        self.assertNotEqual(current["instances"][0]["source_sha256"], "")
        self.assertEqual(len(self.store.state("CASE-ALPHA")["sources"]), 2)

    def test_duplicates_and_inconsistent_study_lineage_rejected(self):
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(
                self.store, "CASE-ALPHA", [qido(self.source), qido(self.source)]
            )
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(self.store, "CASE-ALPHA", [
                qido(self.source, study="1.2", series="1.2.10", instance="1.2.10.1"),
                qido(self.source, study="1.3", series="1.2.10", instance="1.2.10.2")
            ])

    def test_study_date_and_modality_mismatches_are_held_not_inferred(self):
        for bad_day in ("20260230", "2026-05-17", "20260518"):
            with self.subTest(day=bad_day), self.assertRaises(InvalidInput):
                check_dicomweb_metadata(
                    self.store, "CASE-ALPHA", [qido(self.source, day=bad_day)]
                )
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(
                self.store, "CASE-ALPHA", [qido(self.source, modality="INVALID")]
            )

    def test_invalid_uids_and_malformed_tags_rejected(self):
        for bad_uid in ("1..2", "01.2", ".1", "1." + "2"*65):
            with self.subTest(uid=bad_uid), self.assertRaises(InvalidInput):
                check_dicomweb_metadata(self.store, "CASE-ALPHA", [
                    qido(self.source, study=bad_uid)
                ])
        for tagname in ("00080020", "00080018", "0020000D"):
            with self.subTest(tag=tagname):
                row = qido(self.source)
                row[tagname]["Value"] = ["1", "2"]
                with self.assertRaises(InvalidInput):
                    check_dicomweb_metadata(self.store, "CASE-ALPHA", [row])

    def test_non_imaging_source_and_invalid_bounded_input_denied(self):
        non_imaging = self.store.import_report(
            "CASE-ALPHA", (FIXTURES / "alpha-pathology-original.txt").read_bytes()
        )["source_id"]
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(
                self.store, "CASE-ALPHA", [qido(non_imaging)]
            )
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(self.store, "CASE-ALPHA", [qido(self.source)]*257)
        with self.assertRaises(InvalidInput):
            check_dicomweb_metadata(self.store, "CASE-ALPHA", "invalid")

    def test_read_only_projection_does_not_modify_case_ledger(self):
        before = self.store.state("CASE-ALPHA")
        check_dicomweb_metadata(self.store, "CASE-ALPHA", [qido(self.source)])
        after = self.store.state("CASE-ALPHA")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
