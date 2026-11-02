"""Exact-source deterministic tool checks for fictional lab reports only."""
from __future__ import annotations

import unittest

from open_intelligence.lab_trends import build_lab_trend, case_lab_trend
from open_intelligence.store import CaseStore, InvalidInput


def report(document, day, value="10.0", unit="g/dL", qc="passed",
           state="reported", key="hemoglobin", amends=None, kind="laboratory",
           issued=None, specimen="BLOOD-ALPHA"):
    parts = [
        "OI-SYNTHETIC-REPORT/1",
        "Patient: CASE-ALPHA",
        f"Document: {document}",
        f"Type: {kind}",
        f"Event-Date: {day}",
        f"Issued-At: {issued or day}",
        f"Specimen: {specimen}",
    ]
    if amends:
        parts.append(f"Amends: {amends}")
    quote = (f"OI-LAB-VALUE/1;value={value};unit={unit};qc={qc}")
    parts.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(parts) + "\n").encode("utf-8")


class LabTrendToolTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Independent fictional case")
        self.store.add_case("CASE-BETA", "Unrelated fictional case")

    def tearDown(self):
        self.store.close()

    def put(self, *args, **kwargs):
        return self.store.import_report("CASE-ALPHA", report(*args, **kwargs))

    def test_two_source_anchored_values_compute_exact_decimal_difference(self):
        self.put("LAB-A1", "2026-05-01", "10.2")
        self.put("LAB-A2", "2026-06-01", "9.8")
        outcome = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(outcome["status"], "computed")
        self.assertTrue(outcome["analysis_executed"])
        self.assertEqual(outcome["delta"], "-0.4")
        self.assertEqual(outcome["direction"], "numeric_decrease")
        self.assertEqual(outcome["unit"], "g/dL")
        self.assertEqual(len(outcome["points"]), 2)
        self.assertEqual(outcome["holds"], [])
        self.assertEqual(outcome["clinical_review_state"], "not_performed")
        self.assertEqual(outcome["interpretation"], "none")
        self.assertTrue(all(
            p["source"]["source_sha256"] and p["source"]["source_line"] == 8
            and p["source"]["document_id"] for p in outcome["points"]))

    def test_case_switch_does_not_leak_source_or_values(self):
        self.put("LAB-A1", "2026-05-01")
        other = case_lab_trend(self.store, "CASE-BETA", "hemoglobin")
        self.assertEqual(other["case_id"], "CASE-BETA")
        self.assertEqual(other["points"], [])
        self.assertEqual(other["status"], "insufficient_current_measurements")
        self.assertNotIn("LAB-A1", str(other))
        with self.assertRaises(InvalidInput):
            case_lab_trend(self.store, "CASE-NONEXISTENT", "hemoglobin")

    def test_pending_negative_and_unassessed_cannot_turn_into_zero(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        self.put("LAB-A2", "2026-06-01", state="pending")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(result["status"], "held")
        self.assertFalse(result["analysis_executed"])
        self.assertIsNone(result["delta"])
        self.assertIn("source_state_not_reported",
                      [item["reason"] for item in result["holds"]])

    def test_qc_failed_holds_even_when_other_measurements_valid(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        self.put("LAB-A2", "2026-06-01", "11.0", qc="failed")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["holds"][0]["reason"], "qc_not_passed")
        self.assertIsNone(result["delta"])

    def test_unit_mismatch_does_not_convert_or_silently_choose(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        self.put("LAB-A2", "2026-06-01", "100.0", unit="mg/dL")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(result["status"], "held")
        self.assertIsNone(result["unit"])
        self.assertIn("incompatible_units_no_conversion",
                      [item["reason"] for item in result["holds"]])

    def test_multiple_same_day_samples_hold_without_ordering_assumption(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        self.put("LAB-A2", "2026-05-01", "11.0")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(result["status"], "held")
        self.assertIn("multiple_samples_same_day_no_sequence",
                      [item["reason"] for item in result["holds"]])

    def test_amendment_only_uses_current_source_without_erasing_history(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        self.put("LAB-A2", "2026-06-01", "11.0")
        initial = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.put("LAB-A2", "2026-06-01", "9.5", amends="LAB-A2@1")
        changed = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(initial["delta"], "1.0")
        self.assertEqual(changed["delta"], "-0.5")
        self.assertEqual(len(changed["points"]), 2)
        self.assertEqual(changed["points"][-1]["source"]["source_version"], 2)
        self.assertEqual(len(self.store.state("CASE-ALPHA")["sources"]), 3)
        self.assertNotEqual(initial["points"][-1]["source"]["source_sha256"],
                            changed["points"][-1]["source"]["source_sha256"])

    def test_invalid_narrative_does_not_become_a_numeric_test(self):
        self.put("LAB-A1", "2026-05-01")
        self.put("LAB-A2", "2026-06-01", value="not-measured")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["holds"][0]["reason"], "unsupported_measurement_format")

    def test_issued_before_event_holds(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        self.put("LAB-A2", "2026-06-01", "9.0", issued="2026-05-29")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(result["status"], "held")
        self.assertIn("issued_before_event", [x["reason"] for x in result["holds"]])

    def test_one_measurement_is_not_a_trend(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(result["status"], "insufficient_current_measurements")
        self.assertIsNone(result["delta"])

    def test_ignores_other_finding_keys_and_modalities(self):
        self.put("LAB-A1", "2026-05-01", "10.0")
        self.put("IMG-A1", "2026-06-01", "12.0", kind="imaging")
        self.put("LAB-A2", "2026-07-01", "8.0", key="sodium", unit="mmol/L")
        result = case_lab_trend(self.store, "CASE-ALPHA", "hemoglobin")
        self.assertEqual(len(result["points"]), 1)
        self.assertEqual(result["status"], "insufficient_current_measurements")

    def test_rejects_invalid_analyte_and_does_not_perform_tool_actions(self):
        self.put("LAB-A1", "2026-05-01")
        state = self.store.state("CASE-ALPHA")
        with self.assertRaises(InvalidInput):
            build_lab_trend(state, "hemoglobin; DELETE")
        with self.assertRaises(InvalidInput):
            build_lab_trend(state, True)
        self.assertFalse(build_lab_trend(state, "missing-test")["analysis_executed"])


if __name__ == "__main__":
    unittest.main()
