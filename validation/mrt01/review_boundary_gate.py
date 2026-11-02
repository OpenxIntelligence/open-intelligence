"""Strict MRT-01 composed acceptance; not collected on unpatched main.

Reuses #138's real loopback HTTP harness and original fictional source fixtures.
No model reasoning, publication retrieval or verified clinical approval is
claimed. The live model and bibliography transports are tripwires.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests"), str(ROOT)]
from open_intelligence import CaseStore
import test_mrt01_first_connected_slice as seam


class ComposedReviewBoundary(unittest.TestCase):
    # Reuse the actual HTTP setup; do not inherit/recount the existing test.
    api = seam.FirstConnectedSlice.api
    fixture = seam.FirstConnectedSlice.fixture
    assert_api = seam.FirstConnectedSlice.assert_api
    tearDown = seam.FirstConnectedSlice.tearDown

    def setUp(self):
        seam.FirstConnectedSlice.setUp(self)
        for target in ("call_meta_api", "fetch_public_doi"):
            tripwire = patch("open_intelligence.__main__." + target,
                             side_effect=AssertionError("External call forbidden in MRT-01"))
            mock = tripwire.start()
            self.addCleanup(tripwire.stop)
            self.addCleanup(mock.assert_not_called)
        for case_id in ("CASE-ALPHA", "CASE-BETA"):
            self.assert_api("/api/cases", {"case_id": case_id,
                "label": "Independently fictional " + case_id}, 201)
        self.root = "/api/cases/CASE-ALPHA"
        self.beta = "/api/cases/CASE-BETA"
        self.source_id = self.assert_api(self.root + "/imports", {
            "text": self.fixture("alpha-pathology-original.txt")}, 200)["source_id"]
        self.qid = self.question(self.root, "What does the invented report support?")
        self.beta_qid = self.question(self.beta, "What information is still absent?")

    def question(self, root, text):
        return self.assert_api(root + "/questions", {"question": text}, 201)["question_id"]

    def state(self, root):
        return self.assert_api(root + "/state", None, 200)

    def question_state(self, root, qid):
        return next(q["state"] for q in self.state(root)["questions"] if q["id"] == qid)

    def replay(self, root, qid):
        receipt = self.assert_api(root + "/investigations", {
            "question_id": qid, "template": "evidence-summary", "mode": "replay"}, 201)
        self.assertEqual(receipt["model"], "recorded-replay")
        self.assertEqual(receipt["kind"], "hypothesis")
        self.assertEqual(receipt["review_state"], "pending")
        return receipt

    def snapshot(self, source_id, assessments=None):
        return self.assert_api(self.root + "/snapshots", {
            "question_id": self.qid,
            "summary": "Human-authored fictional review draft; not a medical conclusion.",
            "source_ids": [source_id], "evidence_assessment_ids": assessments or [],
        }, 201)["snapshot_id"]

    def test_completed_replay_does_not_settle_a_fresh_question(self):
        receipt = self.replay(self.root, self.qid)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue(receipt["claims"])
        self.assertEqual(self.question_state(self.root, self.qid), "open")
        self.assertEqual(self.question_state(self.beta, self.beta_qid), "open")
        snap = self.snapshot(self.source_id)
        self.assert_api(self.root + f"/snapshots/{snap}/review", {
            "reviewer_label": "Invented demonstration reviewer, not identity proof"}, 200)
        self.assertEqual(self.question_state(self.root, self.qid), "addressed")
        again = self.replay(self.root, self.qid)
        self.assertEqual(again["review_state"], "pending")
        self.assertEqual(self.question_state(self.root, self.qid), "addressed")
        reopened = CaseStore(self.db_path)
        try:
            self.assertEqual(reopened.get_investigation("CASE-ALPHA", receipt["id"])["review_state"], "pending")
            self.assertEqual(reopened.get_investigation("CASE-ALPHA", again["id"])["review_state"], "pending")
        finally:
            reopened.close()

    def test_abstained_replay_keeps_missing_information_visible(self):
        receipt = self.replay(self.beta, self.beta_qid)
        self.assertEqual(receipt["status"], "abstained")
        self.assertEqual(receipt["claims"], [])
        self.assertTrue(receipt["abstentions"])
        self.assertEqual(self.question_state(self.beta, self.beta_qid), "open")
        mission = self.assert_api(self.beta + "/mission", None, 200)
        self.assertEqual(mission["where_am_i"]["open_questions"], 1)
        self.assertNotIn("monitor_changes", {a["kind"] for a in mission["next_actions"]})

    def test_new_replay_cannot_clear_amendment_review(self):
        snap = self.snapshot(self.source_id)
        self.assert_api(self.root + f"/snapshots/{snap}/review", {
            "reviewer_label": "Fictional scoped review"}, 200)
        changed = self.assert_api(self.root + "/imports", {
            "text": self.fixture("alpha-pathology-amended.txt")}, 200)
        self.assertIn(snap, changed["invalidated_snapshots"])
        self.assertEqual(self.question_state(self.root, self.qid), "open")
        self.replay(self.root, self.qid)
        self.assertEqual(self.question_state(self.root, self.qid), "open")
        self.assertEqual(next(s for s in self.state(self.root)["snapshots"] if s["id"] == snap)["state"], "stale")
        self.assertIn("not tested in this specimen", self.assert_api(
            self.root + f"/sources/{self.source_id}", None, 200)["text"])
        self.assertEqual(self.question_state(self.beta, self.beta_qid), "open")

    def test_counterevidence_and_withdrawal_preserve_independent_sources(self):
        linked = []
        versions = []
        for key, relation, statement in (
            ("EVID-INV-A", "supports", "This invented reference supports only a fictional provenance exercise."),
            ("EVID-INV-B", "contradicts", "This invented reference contradicts the invented example; it is not a real study."),
        ):
            text = (f"OI-SYNTHETIC-EVIDENCE/1\nEvidence: {key}\n"
                    "Title: Independently authored fictional reference\n"
                    "Issued-At: 2026-05-08\nRights: original-synthetic\n"
                    f"Statement: {statement}\n")
            version = self.assert_api("/api/evidence/imports", {"text": text}, 200)["evidence_version_id"]
            versions.append(version)
            linked.append(self.assert_api(self.root + "/evidence-assessments", {
                "question_id": self.qid, "evidence_version_id": version,
                "relation": relation, "applicability": "limited",
                "rationale": "Authored engineering label, not independent scientific appraisal.",
            }, 201)["assessment_id"])
        snap = self.snapshot(self.source_id, linked)
        exported = self.assert_api(self.root + f"/snapshots/{snap}/export", None, 200)
        for word in ("supports", "contradicts", "EVID-INV-A@1", "EVID-INV-B@1"):
            self.assertIn(word, exported)
        self.assert_api(self.root + f"/snapshots/{snap}/review", {
            "reviewer_label": "Fictional test reviewer"}, 200)
        result = self.assert_api(f"/api/evidence/{versions[0]}/withdraw", {
            "reason": "Invented source intentionally retired for an offline regression."}, 200)
        self.assertIn(snap, result["invalidated_snapshots"])
        self.assertEqual(self.question_state(self.root, self.qid), "open")
        states = {e["id"]: e["state"] for e in self.state(self.root)["evidence"]}
        self.assertEqual(states[versions[0]], "withdrawn")
        self.assertEqual(states[versions[1]], "current")
        self.assertEqual(self.question_state(self.beta, self.beta_qid), "open")
        self.assertEqual(self.api(self.root + "/snapshots", {
            "question_id": self.qid, "summary": "Cannot silently reuse withdrawn reference.",
            "source_ids": [self.source_id], "evidence_assessment_ids": linked,
        })[0], 422)


if __name__ == "__main__":
    unittest.main()
