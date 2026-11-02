"""Mission review work follows real synthetic report reassessment, not old history.

The model results below are independently authored replay abstentions. No live
model, patient data, mocked ledger or persisted workflow flags are involved.
"""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from open_intelligence.composer import composer_context_fingerprint
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.mission import build_patient_mission
from open_intelligence.store import CaseStore


SYNTHETIC = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class MissionReassessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CaseStore(Path(self.temp.name) / "fictional-mission.sqlite")
        self.addCleanup(self.store.close)
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.import_report("CASE-ALPHA",
            (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        self.question_id = self.store.add_question(
            "CASE-ALPHA", "Which fictional source observations remain uncertain?")

    def prepare(self, question_id=None):
        question_id = self.question_id if question_id is None else question_id
        result = ValidatedInvestigation("abstained", [], [
            {"topic": "Fictional source uncertainty", "reason": "insufficient_evidence"}
        ], [], "recorded-replay", "replay")
        run_id = self.store.save_investigation(
            "CASE-ALPHA", question_id, "evidence-summary", result, "replay",
            context_fingerprint=composer_context_fingerprint(
                self.store, "CASE-ALPHA", question_id))
        return self.store.prepare_investigation_review_draft(
            "CASE-ALPHA", run_id, question_id)["snapshot_id"]

    def acknowledge(self, snapshot_id):
        self.store.acknowledge_demo_review(
            "CASE-ALPHA", snapshot_id, "Synthetic reviewer")

    def amend(self):
        return self.store.import_report("CASE-ALPHA",
            (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())

    def stale_report(self):
        original = self.prepare()
        self.acknowledge(original)
        self.amend()
        return original

    def reassessed_pair(self):
        original = self.stale_report()
        replacement = self.prepare()
        self.acknowledge(replacement)
        return original, replacement

    def mission(self):
        return build_patient_mission(self.store.state("CASE-ALPHA"))

    def assert_active_review(self, mission, expected_ids):
        self.assertEqual(mission["workflow_status"], "review_required")
        self.assertEqual(set(mission["what_remains_unresolved"]["stale_investigation_ids"]),
                         set(expected_ids))
        self.assertIn("reconcile_stale_investigation",
                      {action["kind"] for action in mission["next_actions"]})

    def test_second_acknowledgment_clears_active_review_without_rewriting_history(self):
        original = self.stale_report()
        self.assert_active_review(self.mission(), [original])
        replacement = self.prepare()
        self.assert_active_review(self.mission(), [original])
        self.acknowledge(replacement)
        before = self.store.state("CASE-ALPHA")
        old = next(item for item in before["snapshots"] if item["id"] == original)
        mission = build_patient_mission(before)

        self.assertEqual(mission["workflow_status"], "reviewed_in_demo")
        self.assertEqual(mission["what_remains_unresolved"]["questions"], [])
        self.assertEqual(mission["what_remains_unresolved"]["stale_investigation_ids"], [])
        self.assertEqual([item["kind"] for item in mission["next_actions"]], ["monitor_changes"])
        self.assertEqual(mission["where_am_i"]["stale_investigations"], 1)
        self.assertEqual(mission["review_history"]["stale_investigation_ids"], [original])
        self.assertTrue(mission["what_remains_unresolved"]["source_findings"])
        self.assertEqual(self.store.state("CASE-ALPHA"), before)
        self.assertEqual(old["state"], "stale")
        self.assertTrue(old["reviewed_at"])
        self.assertEqual(old["reviewer_label"], "Synthetic reviewer")
        self.assertIn("PATH-ALPHA@1", self.store.export_markdown("CASE-ALPHA", original))

    def test_later_amendment_reopens_a_previously_resolved_question(self):
        original, replacement = self.reassessed_pair()
        third_version = (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes().replace(
            b"Amends: PATH-ALPHA@1", b"Amends: PATH-ALPHA@2")
        change = self.store.import_report("CASE-ALPHA", third_version)
        self.assertIn(replacement, change["invalidated_snapshots"])
        mission = self.mission()
        self.assert_active_review(mission, [original, replacement])
        self.assertEqual([item["question_id"] for item in
                          mission["what_remains_unresolved"]["questions"]], [self.question_id])

    def test_open_question_stays_active_even_with_another_current_review_for_it(self):
        imaging = self.store.import_report("CASE-ALPHA",
            (SYNTHETIC / "alpha-imaging.txt").read_bytes())
        original = self.prepare()
        self.acknowledge(original)
        narrow_review = self.store.create_snapshot(
            "CASE-ALPHA", self.question_id, "Fictional imaging-only review.",
            [imaging["source_id"]])
        self.acknowledge(narrow_review)
        self.amend()
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(next(item["state"] for item in state["snapshots"]
                              if item["id"] == narrow_review), "reviewed_in_demo")
        self.assertEqual(state["questions"][0]["state"], "open")
        self.assert_active_review(build_patient_mission(state), [original])

    def test_review_of_another_question_does_not_clear_existing_review_work(self):
        original = self.stale_report()
        other_question = self.store.add_question(
            "CASE-ALPHA", "An independent fictional question?")
        self.acknowledge(self.prepare(other_question))
        self.assert_active_review(self.mission(), [original])

    def test_remaining_current_draft_keeps_work_in_progress_after_acknowledgment(self):
        original = self.stale_report()
        acknowledged = self.prepare()
        remaining = self.prepare()
        self.acknowledge(acknowledged)
        mission = self.mission()
        self.assertEqual(mission["workflow_status"], "investigation_in_progress")
        self.assertEqual(mission["what_remains_unresolved"]["stale_investigation_ids"], [])
        self.assertEqual(mission["review_history"]["stale_investigation_ids"], [original])
        self.assertEqual([item["kind"] for item in mission["next_actions"]],
                         ["acknowledge_demo_review"])
        self.assertEqual(next(item["state"] for item in self.store.state("CASE-ALPHA")["snapshots"]
                              if item["id"] == remaining), "draft")

    def test_missing_question_or_current_review_cannot_silently_hide_stale_work(self):
        original, replacement = self.reassessed_pair()
        complete = self.store.state("CASE-ALPHA")
        for missing in ("question", "question-state", "snapshot-link", "review"):
            with self.subTest(missing=missing):
                state = copy.deepcopy(complete)
                if missing == "question":
                    state["questions"] = []
                elif missing == "question-state":
                    state["questions"][0].pop("state")
                elif missing == "snapshot-link":
                    next(item for item in state["snapshots"] if item["id"] == original)["question_id"] = None
                else:
                    state["snapshots"] = [item for item in state["snapshots"] if item["id"] != replacement]
                self.assert_active_review(build_patient_mission(state), [original])


if __name__ == "__main__":
    unittest.main()
