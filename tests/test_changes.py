import unittest
from pathlib import Path

from open_intelligence.changes import changes_since_review
from open_intelligence.store import CaseStore, InvalidInput

SYNTHETIC = Path(__file__).resolve().parents[1] / "examples" / "synthetic"

LAB_REPORT = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-ALPHA
Document: LAB-ALPHA
Type: laboratory
Event-Date: 2026-05-20
Issued-At: 2026-05-21
Finding: marker-b|reported|Fictional laboratory note records Marker B as present.
"""

EVIDENCE_TEXT = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: EVID-ALPHA
Title: Fictional example study summary
Issued-At: 2026-05-10
Rights: original-synthetic
Statement: A fictional example statement used only to exercise evidence withdrawal.
"""


def _alpha(store):
    store.add_case("CASE-ALPHA", "Fictional case Alpha")
    store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
    store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes())


class ChangesTests(unittest.TestCase):
    def test_no_review_yet_anchors_at_case_creation(self):
        store = CaseStore(":memory:")
        _alpha(store)
        result = changes_since_review(store, "CASE-ALPHA")
        self.assertEqual(result["anchor"]["kind"], "case_created")
        self.assertTrue(result["synthetic"])
        self.assertIn("Fictional synthetic data only", result["disclaimer"])
        self.assertEqual(result["counts"]["new_sources"], 2)
        self.assertEqual(result["counts"]["amendments"], 0)
        self.assertEqual(result["counts"]["new_questions"], 0)
        docs = {item["document_id"] for item in result["new_sources"]}
        self.assertEqual(docs, {"PATH-ALPHA", "IMG-ALPHA"})

    def test_review_then_amendment_question_and_new_source(self):
        store = CaseStore(":memory:")
        _alpha(store)
        question_id = store.add_question("CASE-ALPHA", "What does the fictional record show so far?")
        state = store.state("CASE-ALPHA")
        source_ids = [s["id"] for s in state["sources"] if s["state"] == "current"]
        snapshot_id = store.create_snapshot("CASE-ALPHA", question_id, "Human draft summary for testing.", source_ids)
        store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "demo-reviewer")
        cleared = changes_since_review(store, "CASE-ALPHA")
        self.assertEqual(cleared["anchor"]["kind"], "demo_review_acknowledged")
        self.assertEqual(cleared["counts"], {"new_sources": 0, "amendments": 0,
                                             "stale_investigations": 0, "new_questions": 0})
        store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        store.add_question("CASE-ALPHA", "What fictional follow-up is recorded after review?")
        store.import_report("CASE-ALPHA", LAB_REPORT)
        result = changes_since_review(store, "CASE-ALPHA")
        self.assertEqual(result["counts"]["amendments"], 1)
        amendment = result["amendments"][0]
        self.assertEqual(amendment["document_id"], "PATH-ALPHA")
        self.assertEqual(amendment["version"], 2)
        self.assertEqual(amendment["superseded_version"], 1)
        self.assertEqual(amendment["invalidated_snapshot_ids"], [snapshot_id])
        diff = amendment["finding_key_diff"]
        self.assertEqual(diff["added_finding_keys"], [])
        self.assertEqual(diff["removed_finding_keys"], [])
        self.assertEqual(diff["reported_state_changes"], [
            {"finding_key": "marker-a", "previous_reported_state": "not-reported",
             "reported_state": "negative"}])
        # No significance claim anywhere except the disclaimer's explicit negation.
        body = str({k: v for k, v in result.items() if k != "disclaimer"}).lower()
        for word in ("progression", "improved", "worsened", "significant"):
            self.assertNotIn(word, body)
        self.assertEqual(result["counts"]["stale_investigations"], 1)
        stale = result["stale_investigations"][0]
        self.assertEqual(stale["snapshot_id"], snapshot_id)
        self.assertEqual(stale["current_state"], "stale")
        self.assertEqual(stale["question_state"], "open")
        self.assertEqual(stale["causes"][0]["cause"], "source_amendment")
        self.assertEqual(result["counts"]["new_questions"], 1)
        self.assertEqual(result["counts"]["new_sources"], 1)
        self.assertEqual(result["new_sources"][0]["document_id"], "LAB-ALPHA")

    def test_evidence_withdrawal_marks_draft_stale(self):
        store = CaseStore(":memory:")
        _alpha(store)
        question_id = store.add_question("CASE-ALPHA", "What fictional evidence is assessed here?")
        imported = store.import_synthetic_evidence(EVIDENCE_TEXT)
        assessment_id = store.assess_synthetic_evidence(
            "CASE-ALPHA", question_id, imported["evidence_version_id"],
            "context", "limited", "Fictional rationale long enough to pass validation.")
        state = store.state("CASE-ALPHA")
        source_ids = [s["id"] for s in state["sources"] if s["state"] == "current"]
        snapshot_id = store.create_snapshot("CASE-ALPHA", question_id, "Human draft summary for testing.",
                                            source_ids, [assessment_id])
        store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "demo-reviewer")
        store.withdraw_synthetic_evidence(imported["evidence_version_id"],
                                          "Fictional withdrawal reason for testing.")
        result = changes_since_review(store, "CASE-ALPHA")
        self.assertEqual(result["counts"]["stale_investigations"], 1)
        stale = result["stale_investigations"][0]
        self.assertEqual(stale["current_state"], "stale")
        self.assertEqual(stale["causes"][0]["cause"], "evidence_change")
        self.assertEqual(stale["causes"][0]["reason"], "withdrawal")

    def test_explicit_anchor_and_purity(self):
        store = CaseStore(":memory:")
        _alpha(store)
        events_before = store.state("CASE-ALPHA")["events"]
        created_id = min(event["id"] for event in events_before)
        first = changes_since_review(store, "CASE-ALPHA", since_event_id=created_id)
        second = changes_since_review(store, "CASE-ALPHA", since_event_id=created_id)
        self.assertEqual(first, second)
        self.assertEqual(first["anchor"]["event_id"], created_id)
        events_after = store.state("CASE-ALPHA")["events"]
        self.assertEqual(len(events_before), len(events_after))

    def test_anchor_errors(self):
        store = CaseStore(":memory:")
        _alpha(store)
        store.add_case("CASE-BETA", "Fictional case Beta")
        beta_event = store.state("CASE-BETA")["events"][0]["id"]
        with self.assertRaises(InvalidInput):
            changes_since_review(store, "CASE-NOPE")
        with self.assertRaises(InvalidInput):
            changes_since_review(store, "CASE-ALPHA", since_event_id=beta_event)
        with self.assertRaises(InvalidInput):
            changes_since_review(store, "CASE-ALPHA", since_event_id=0)
        with self.assertRaises(InvalidInput):
            changes_since_review(store, "CASE-ALPHA", since_event_id="3")


if __name__ == "__main__":
    unittest.main()
