"""Journey stages + care transitions: append-only organizing labels.

These tests verify software behaviour only, not clinical correctness. All
cases and reasons are independently authored fiction. Journey stages are
descriptive labels for organizing the record; they assert nothing clinical,
and the store never infers a stage from source text.
"""

import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


def report(name):
    return (SAMPLE / name).read_bytes()


class JourneyStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "journey.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_importing_sources_never_infers_a_stage(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        history = self.store.journey_history("CASE-ALPHA")
        self.assertIsNone(history["current_stage"])
        self.assertEqual(history["transitions"], [])

    def test_first_transition_sets_single_current_stage(self):
        transition_id = self.store.record_journey_transition(
            "CASE-ALPHA", "diagnosis",
            "the fictional intake paperwork is grouped here for review",
            "2026-05-06")
        self.assertIsInstance(transition_id, int)
        history = self.store.journey_history("CASE-ALPHA")
        self.assertEqual(history["current_stage"], "diagnosis")
        self.assertEqual(history["current_stage_label"], "Diagnosis")
        self.assertEqual(len(history["transitions"]), 1)
        first = history["transitions"][0]
        self.assertIsNone(first["from_stage"])
        self.assertEqual(first["to_stage"], "diagnosis")
        self.assertEqual(first["review_state"], "current")
        # The other fictional case is unaffected.
        self.assertIsNone(self.store.journey_history("CASE-BETA")["current_stage"])

    def test_successive_transitions_preserve_full_history_in_order(self):
        self.store.record_journey_transition(
            "CASE-ALPHA", "diagnosis",
            "the fictional intake paperwork is grouped here for review",
            "2026-05-06")
        self.store.record_journey_transition(
            "CASE-ALPHA", "treatment",
            "the fictional care paperwork is now grouped with active notes",
            "2026-06-02")
        self.store.record_journey_transition(
            "CASE-ALPHA", "survivorship",
            "the fictional follow-up paperwork is grouped for later review",
            "2026-09-10")
        history = self.store.journey_history("CASE-ALPHA")
        self.assertEqual(history["current_stage"], "survivorship")
        self.assertEqual([t["to_stage"] for t in history["transitions"]],
                         ["diagnosis", "treatment", "survivorship"])
        self.assertEqual([t["from_stage"] for t in history["transitions"]],
                         [None, "diagnosis", "treatment"])
        self.assertIn("Step 1", history["transitions"][0]["summary"])
        self.assertIn("Step 3", history["transitions"][2]["summary"])
        self.assertIn("Survivorship", history["transitions"][2]["summary"])

    def test_later_transition_leaves_earlier_rows_unchanged(self):
        first_id = self.store.record_journey_transition(
            "CASE-ALPHA", "diagnosis",
            "the fictional intake paperwork is grouped here for review",
            "2026-05-06")
        before = [dict(t) for t in self.store.journey_history("CASE-ALPHA")["transitions"]]
        self.store.record_journey_transition(
            "CASE-ALPHA", "treatment",
            "the fictional care paperwork is now grouped with active notes",
            "2026-06-02")
        after = self.store.journey_history("CASE-ALPHA")["transitions"]
        self.assertEqual(len(after), 2)
        self.assertEqual(after[0]["id"], first_id)
        for key in ("case_id", "from_stage", "to_stage", "reason",
                    "transition_date", "triggering_source_version_id",
                    "review_state", "created_at"):
            self.assertEqual(after[0][key], before[0][key], key)

    def test_same_stage_transition_is_rejected(self):
        self.store.record_journey_transition(
            "CASE-ALPHA", "diagnosis",
            "the fictional intake paperwork is grouped here for review",
            "2026-05-06")
        with self.assertRaisesRegex(InvalidInput, "different organizing label"):
            self.store.record_journey_transition(
                "CASE-ALPHA", "diagnosis",
                "a repeated fictional grouping note with no new label",
                "2026-05-20")
        self.assertEqual(len(self.store.journey_history("CASE-ALPHA")["transitions"]), 1)

    def test_invalid_stage_date_and_reason_are_rejected(self):
        with self.assertRaisesRegex(InvalidInput, "Unknown journey stage"):
            self.store.record_journey_transition(
                "CASE-ALPHA", "remission",
                "a fictional reason long enough to pass length checks",
                "2026-05-06")
        with self.assertRaisesRegex(InvalidInput, "YYYY-MM-DD"):
            self.store.record_journey_transition(
                "CASE-ALPHA", "diagnosis",
                "a fictional reason long enough to pass length checks",
                "May 6 2026")
        with self.assertRaisesRegex(InvalidInput, "10–600|10-600"):
            self.store.record_journey_transition("CASE-ALPHA", "diagnosis", "short", "2026-05-06")
        self.assertEqual(self.store.journey_history("CASE-ALPHA")["transitions"], [])

    def test_treatment_recommendation_language_is_rejected(self):
        with self.assertRaisesRegex(InvalidInput, "recommendation, order, or eligibility"):
            self.store.record_journey_transition(
                "CASE-ALPHA", "treatment",
                "the patient should receive chemotherapy starting now",
                "2026-06-02")
        self.assertEqual(self.store.journey_history("CASE-ALPHA")["transitions"], [])

    def test_triggering_source_must_be_current_and_same_case(self):
        alpha = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        beta = self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        with self.assertRaisesRegex(InvalidInput, "another case"):
            self.store.record_journey_transition(
                "CASE-ALPHA", "diagnosis",
                "a fictional grouping note citing the wrong case file",
                "2026-05-06", beta["source_id"])
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        with self.assertRaisesRegex(InvalidInput, "superseded"):
            self.store.record_journey_transition(
                "CASE-ALPHA", "diagnosis",
                "a fictional grouping note citing an outdated source file",
                "2026-05-06", alpha["source_id"])
        self.assertEqual(self.store.journey_history("CASE-ALPHA")["transitions"], [])

    def test_amendment_flags_only_citing_transitions_and_preserves_the_rest(self):
        original = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        citing = self.store.record_journey_transition(
            "CASE-ALPHA", "diagnosis",
            "the fictional intake file is grouped here for review",
            "2026-05-06", original["source_id"])
        plain = self.store.record_journey_transition(
            "CASE-ALPHA", "treatment",
            "the fictional care paperwork is now grouped with active notes",
            "2026-06-02")
        before = {t["id"]: dict(t) for t in self.store.journey_history("CASE-ALPHA")["transitions"]}
        outcome = self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        self.assertEqual(outcome["invalidated_journey_transitions"], [citing])
        history = self.store.journey_history("CASE-ALPHA")
        by_id = {t["id"]: t for t in history["transitions"]}
        # Both rows survive; only the citing row's review flag moves.
        self.assertEqual(sorted(by_id), sorted([citing, plain]))
        self.assertEqual(by_id[citing]["review_state"], "needs_review")
        self.assertEqual(by_id[plain]["review_state"], "current")
        for key in ("case_id", "from_stage", "to_stage", "reason",
                    "transition_date", "triggering_source_version_id", "created_at"):
            self.assertEqual(by_id[citing][key], before[citing][key], key)
            self.assertEqual(by_id[plain][key], before[plain][key], key)
        # The current label still derives from the latest row.
        self.assertEqual(history["current_stage"], "treatment")
        # The other fictional case is unaffected.
        self.assertEqual(self.store.journey_history("CASE-BETA")["transitions"], [])

    def test_history_survives_close_and_reopen(self):
        self.store.record_journey_transition(
            "CASE-ALPHA", "diagnosis",
            "the fictional intake paperwork is grouped here for review",
            "2026-05-06")
        self.store.record_journey_transition(
            "CASE-ALPHA", "advanced_disease",
            "the fictional record grouping changed after new paperwork arrived",
            "2026-07-01")
        self.store.close()
        reopened_path = Path(self.tmp.name) / "journey.sqlite"
        self.store = CaseStore(reopened_path)
        history = self.store.journey_history("CASE-ALPHA")
        self.assertEqual(history["current_stage"], "advanced_disease")
        self.assertEqual([t["to_stage"] for t in history["transitions"]],
                         ["diagnosis", "advanced_disease"])

    def test_state_exposes_journey_with_descriptive_disclaimer(self):
        self.store.record_journey_transition(
            "CASE-ALPHA", "diagnosis",
            "the fictional intake paperwork is grouped here for review",
            "2026-05-06")
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(state["journey_current"], "diagnosis")
        self.assertEqual(state["journey_current_label"], "Diagnosis")
        self.assertEqual(len(state["journey_transitions"]), 1)
        self.assertIn("descriptive labels", state["journey_disclaimer"])
        self.assertIn("not", state["journey_disclaimer"].lower())
        self.assertIn("staging determinations", state["journey_disclaimer"])


if __name__ == "__main__":
    unittest.main()
