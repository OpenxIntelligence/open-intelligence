"""First-party synthetic clinical-order/LIS operational state tests.

This is NOT a regulated EHR, LIS, clinical laboratory, device connection,
clinician authorization, PHI workflow, treatment decision or deployed service.
The source of clinical text remains the existing CaseStore source ledger.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from open_intelligence.clinical_lab import ClinicalLabOperations
from open_intelligence.store import CaseStore, InvalidInput


def fictional_report(case="CASE-OPS-A", document="SOURCE-ORDER-A", *,
                     kind="clinical", specimen=None, finding_key="order",
                     state="reported", text="A fictional assay order was documented.",
                     amendment=None):
    data = [
        "OI-SYNTHETIC-REPORT/1", f"Patient: {case}", f"Document: {document}",
        f"Type: {kind}", "Event-Date: 2026-01-05", "Issued-At: 2026-01-06",
    ]
    if specimen:
        data.append(f"Specimen: {specimen}")
    if amendment is not None:
        data.append(f"Amends: {document}@{amendment}")
    data.append(f"Finding: {finding_key}|{state}|{text}")
    return ("\n".join(data) + "\n").encode()


class ClinicalLabOperationsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fictional-operations.sqlite"
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-OPS-A", "Fictional clinical case A")
        self.store.add_case("CASE-OPS-B", "Fictional clinical case B")
        self.ops = ClinicalLabOperations(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def import_order_source(self, case="CASE-OPS-A"):
        return self.store.import_report(
            case, fictional_report(case=case,
                                   document="ORDER-A" if case.endswith("-A") else "ORDER-B")
        )["source_id"]

    def import_lab_source(self, case="CASE-OPS-A", *, specimen="SPEC-OPS-A",
                          state="negative", amendment=None):
        return self.store.import_report(
            case, fictional_report(case=case,
                                   document="LAB-A" if case.endswith("-A") else "LAB-B",
                                   kind="laboratory", specimen=specimen,
                                   finding_key="result", state=state,
                                   text=("Synthetic laboratory finding is " + state + "."),
                                   amendment=amendment)
        )["source_id"]

    def requested(self):
        order_src = self.import_order_source()
        return self.ops.request_lab_order("CASE-OPS-A", "ORDER-OPS-A",
            order_src, "Fictional marker assay", "Synthetic requester")

    def accessioned(self):
        self.requested()
        return self.ops.accession_specimen(
            "CASE-OPS-A", "ORDER-OPS-A", "ACC-OPS-A", "SPEC-OPS-A",
            "Synthetic accessioner")

    def test_order_to_accession_qc_to_source_linked_result_release(self):
        order = self.requested()
        self.assertFalse(order["duplicate"])
        before = self.ops.case_state("CASE-OPS-A")
        self.assertEqual(before["orders"][0]["state"], "requested")
        self.assertEqual(before["accessions"], [])
        self.assertEqual(before["releases"], [])
        self.ops.accession_specimen("CASE-OPS-A", "ORDER-OPS-A",
                                  "ACC-OPS-A", "SPEC-OPS-A", "Synthetic accessioner")
        lab_source = self.import_lab_source()
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A", "QC-OPS-A",
                                      lab_source, "passed", "Synthetic checker")
        self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A",
                                     "REL-OPS-A", lab_source, "result", "Synthetic releaser")
        state = self.ops.case_state("CASE-OPS-A")
        self.assertEqual(len(state["orders"]), 1)
        self.assertEqual(len(state["accessions"]), 1)
        self.assertEqual(len(state["qc_records"]), 1)
        self.assertEqual(len(state["releases"]), 1)
        self.assertEqual(state["releases"][0]["freshness"], "current")
        self.assertEqual(state["releases"][0]["source_version_id"], lab_source)
        self.assertEqual(state["releases"][0]["reported_state"], "negative")
        self.assertNotIn("treatment_administration", str(state))
        self.assertEqual(self.ops.case_state("CASE-OPS-B")["releases"], [])

    def test_failed_or_pending_qc_does_not_release(self):
        self.accessioned()
        lab_src = self.import_lab_source()
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A",
                                      "QC-FAIL", lab_src, "failed", "Synthetic checker")
        with self.assertRaisesRegex(InvalidInput, "QC"):
            self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A", "REL-FAIL",
                                         lab_src, "result", "Synthetic releaser")
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A",
                                      "QC-PENDING", lab_src, "pending", "Synthetic checker")
        with self.assertRaisesRegex(InvalidInput, "QC"):
            self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A", "REL-PENDING",
                                         lab_src, "result", "Synthetic releaser")
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A",
                                      "QC-PASS", lab_src, "passed", "Synthetic checker")
        result = self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A", "REL-PASS",
                                              lab_src, "result", "Synthetic releaser")
        self.assertFalse(result["duplicate"])

    def test_pending_assay_finding_cannot_be_promoted_to_released_result(self):
        self.accessioned()
        pending_src = self.import_lab_source(state="pending")
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A", "QC-OPS-A",
                                      pending_src, "passed", "Synthetic checker")
        with self.assertRaisesRegex(InvalidInput, "finding"):
            self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A", "REL-OPS-A",
                                         pending_src, "result", "Synthetic releaser")
        self.assertEqual(self.ops.case_state("CASE-OPS-A")["releases"], [])

    def test_wrong_case_and_specimen_source_cannot_release(self):
        self.accessioned()
        wrong_case = self.import_lab_source(case="CASE-OPS-B", specimen="SPEC-OPS-B")
        with self.assertRaises(InvalidInput):
            self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A", "QC-WRONG",
                                          wrong_case, "passed", "Synthetic checker")
        wrong_specimen = self.import_lab_source(specimen="SPEC-WRONG")
        with self.assertRaisesRegex(InvalidInput, "specimen"):
            self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A", "QC-WRONG-2",
                                          wrong_specimen, "passed", "Synthetic checker")
        self.assertEqual(self.ops.case_state("CASE-OPS-A")["qc_records"], [])

    def test_amendment_stales_prior_release_without_erasing_history(self):
        self.accessioned()
        original = self.import_lab_source()
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A", "QC-OPS-A",
                                      original, "passed", "Synthetic checker")
        self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A", "REL-OPS-A",
                                     original, "result", "Synthetic releaser")
        changed = self.import_lab_source(state="indeterminate", amendment=1)
        self.assertNotEqual(changed, original)
        before = self.ops.case_state("CASE-OPS-A")["releases"]
        self.assertEqual(before[0]["freshness"], "stale_source")
        with self.assertRaises(InvalidInput):
            self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A",
                                         "REL-OLD", original, "result", "Synthetic releaser")
        with self.assertRaisesRegex(InvalidInput, "QC"):
            self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A",
                                         "REL-NEW", changed, "result", "Synthetic releaser")
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A",
                                      "QC-NEW", changed, "passed", "Synthetic checker")
        self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A",
                                     "REL-NEW", changed, "result", "Synthetic releaser")
        after = {x["release_key"]: x for x in self.ops.case_state("CASE-OPS-A")["releases"]}
        self.assertEqual(after["REL-OPS-A"]["freshness"], "stale_source")
        self.assertEqual(after["REL-NEW"]["freshness"], "current")
        self.assertEqual(after["REL-NEW"]["reported_state"], "indeterminate")

    def test_duplicate_commands_are_idempotent_conflicts_are_rejected(self):
        order_id = self.import_order_source()
        one = self.ops.request_lab_order("CASE-OPS-A", "ORDER-OPS-A", order_id,
                                         "Fictional marker assay", "Synthetic requester")
        two = self.ops.request_lab_order("CASE-OPS-A", "ORDER-OPS-A", order_id,
                                         "Fictional marker assay", "Synthetic requester")
        self.assertEqual(one["id"], two["id"])
        self.assertTrue(two["duplicate"])
        with self.assertRaises(InvalidInput):
            self.ops.request_lab_order("CASE-OPS-A", "ORDER-OPS-A", order_id,
                                       "Different assay", "Synthetic requester")
        a = self.ops.accession_specimen("CASE-OPS-A", "ORDER-OPS-A",
                                        "ACC-OPS-A", "SPEC-OPS-A", "Synthetic accessioner")
        b = self.ops.accession_specimen("CASE-OPS-A", "ORDER-OPS-A",
                                        "ACC-OPS-A", "SPEC-OPS-A", "Synthetic accessioner")
        self.assertTrue(b["duplicate"])
        with self.assertRaises(InvalidInput):
            self.ops.accession_specimen("CASE-OPS-A", "ORDER-OPS-A",
                                        "ACC-OPS-A", "SPEC-DIFFERENT", "Synthetic accessioner")
        self.assertEqual(a["id"], b["id"])

    def test_cancelled_order_cannot_be_accessioned(self):
        self.requested()
        self.ops.cancel_order("CASE-OPS-A", "ORDER-OPS-A",
                              "Fictional cancellation for a synthetic test")
        with self.assertRaisesRegex(InvalidInput, "cancelled"):
            self.ops.accession_specimen("CASE-OPS-A", "ORDER-OPS-A",
                                        "ACC-OPS-A", "SPEC-OPS-A", "Synthetic accessioner")
        self.assertEqual(self.ops.case_state("CASE-OPS-A")["orders"][0]["state"], "cancelled")

    def test_operational_rows_survive_database_restart_without_extra_patient_ledger(self):
        self.accessioned()
        lab_src = self.import_lab_source()
        self.ops.record_quality_check("CASE-OPS-A", "ACC-OPS-A", "QC-OPS-A",
                                      lab_src, "passed", "Synthetic checker")
        self.ops.release_observation("CASE-OPS-A", "ACC-OPS-A", "REL-OPS-A",
                                     lab_src, "result", "Synthetic releaser")
        self.store.close()
        self.store = CaseStore(self.path)
        self.ops = ClinicalLabOperations(self.store)
        state = self.ops.case_state("CASE-OPS-A")
        self.assertEqual(len(state["releases"]), 1)
        self.assertEqual(state["releases"][0]["freshness"], "current")
        tables = {r[0] for r in self.store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("source_versions", tables)
        self.assertNotIn("clinical_patient_records", tables)
        self.assertNotIn("clinical_lab_sources", tables)

    def test_event_write_failure_rolls_back_an_operational_order(self):
        src = self.import_order_source()
        original = self.store._event

        def fail_event(case_id, kind, **details):
            if kind == "clinical_lab_order_requested":
                raise RuntimeError("Synthetic event append failed")
            return original(case_id, kind, **details)

        self.store._event = fail_event
        with self.assertRaisesRegex(RuntimeError, "event append failed"):
            self.ops.request_lab_order("CASE-OPS-A", "ORDER-OPS-A", src,
                                       "Fictional marker assay", "Synthetic requester")
        self.store._event = original
        self.assertEqual(self.ops.case_state("CASE-OPS-A")["orders"], [])
        self.assertFalse(any(e["kind"] == "clinical_lab_order_requested"
                             for e in self.store.state("CASE-OPS-A")["events"]))


if __name__ == "__main__":
    unittest.main()
