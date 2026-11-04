"""Regression: existing model investigations track actual changes in their inputs.

All records are fictional. Existing CaseStore sources, evidence assessments,
questions and model investigation artifacts are the only persisted systems.
No live models, real clinical content or duplicate patient store.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from open_intelligence.__main__ import SYNTHETIC, seed
from open_intelligence.composer import build_composer_context
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.store import CaseStore


def evidence(amends=False):
    text = (SYNTHETIC / "demo-evidence.txt").read_text()
    if amends:
        text = text.replace("Statement: ", "Amends: EVID-ASSAY@1\nStatement: ")
        text = text.replace("an assay limitation", "a separately described assay limitation")
    return text.encode("utf-8")


class ComposerInputFreshnessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "source-evidence-freshness.sqlite"
        seed(str(self.path))
        self.store = CaseStore(self.path)
        self.qa = self.store.add_question(
            "CASE-ALPHA", "Which fictional source facts support this question?")
        self.qb = self.store.add_question(
            "CASE-BETA", "Which Beta records support a separate question?")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def question_state(self, case, qid):
        return next(q["state"] for q in self.store.state(case)["questions"]
                    if q["id"] == qid)

    def save_model(self, case, question):
        preview = build_composer_context(self.store, case, question)
        result = ValidatedInvestigation(
            "abstained", [], [{"topic": "Unresolved synthetic record",
                               "reason": "insufficient_evidence"}],
            [], "recorded-replay", "replay")
        return self.store.save_investigation(
            case, question, "evidence-summary", result, "replay",
            context_fingerprint=preview["fingerprint"])

    def stale(self, case, investigation_id):
        return bool(self.store.get_investigation(case, investigation_id)["stale"])

    def new_source(self):
        raw = (SYNTHETIC / "alpha-imaging.txt").read_bytes()
        return raw.replace(b"Document: IMG-ALPHA\n",
                           b"Document: IMG-ALPHA-SECOND\n")

    def test_new_valid_source_stales_previous_case_model_and_reopens_question(self):
        aid = self.save_model("CASE-ALPHA", self.qa)
        bid = self.save_model("CASE-BETA", self.qb)
        before = build_composer_context(self.store, "CASE-ALPHA", self.qa)
        imported = self.store.import_report("CASE-ALPHA", self.new_source())
        self.assertEqual(imported["result"], "imported")
        after = build_composer_context(self.store, "CASE-ALPHA", self.qa)
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])
        self.assertTrue(self.stale("CASE-ALPHA", aid))
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "open")
        self.assertFalse(self.stale("CASE-BETA", bid))
        self.assertEqual(self.question_state("CASE-BETA", self.qb), "open")

    def test_duplicate_and_quarantined_source_do_not_false_stale_model(self):
        run_id = self.save_model("CASE-ALPHA", self.qa)
        existing = (SYNTHETIC / "alpha-imaging.txt").read_bytes()
        self.assertEqual(
            self.store.import_report("CASE-ALPHA", existing)["result"], "duplicate")
        self.assertEqual(
            self.store.import_report("CASE-BETA", self.new_source())["result"],
            "quarantined")
        self.assertFalse(self.stale("CASE-ALPHA", run_id))
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "open")

    def test_amended_source_without_snapshot_stales_case_model_and_preserves_history(self):
        # A model consumes current case assertions even if its saved output
        # contains no claims and no review snapshot has been created.
        other_question = self.store.add_question(
            "CASE-ALPHA", "Which other fictional source observations are unresolved?")
        first = self.save_model("CASE-ALPHA", self.qa)
        same_case = self.save_model("CASE-ALPHA", other_question)
        other_case = self.save_model("CASE-BETA", self.qb)
        self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"], [])
        before = self.store.get_investigation("CASE-ALPHA", first)
        original = self.store.db.execute(
            "SELECT id,raw,sha256,state FROM source_versions "
            "WHERE case_id=? AND document_id=? AND version=1",
            ("CASE-ALPHA", "PATH-ALPHA")).fetchone()
        self.assertIsNotNone(original)
        original_bytes, original_hash = original["raw"], original["sha256"]

        amended = (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes()
        changed = self.store.import_report("CASE-ALPHA", amended)
        self.assertEqual(changed["result"], "imported")
        self.assertEqual(changed["invalidated_snapshots"], [])
        self.assertEqual(set(changed["invalidated_model_investigation_ids"]),
                         {first, same_case})
        self.assertTrue(self.stale("CASE-ALPHA", first))
        self.assertTrue(self.stale("CASE-ALPHA", same_case))
        self.assertFalse(self.stale("CASE-BETA", other_case))
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "open")
        after = self.store.get_investigation("CASE-ALPHA", first)
        for field in ("id", "abstentions", "claims", "dropped",
                      "context_fingerprint", "created_at"):
            self.assertEqual(after[field], before[field])
        historical = self.store.db.execute(
            "SELECT raw,sha256,state FROM source_versions WHERE id=?",
            (original["id"],)).fetchone()
        self.assertEqual(historical["state"], "superseded")
        self.assertEqual(historical["raw"], original_bytes)
        self.assertEqual(historical["sha256"], original_hash)

        def source_event_count():
            return self.store.db.execute(
                "SELECT count(*) FROM events WHERE case_id=? AND kind='source_imported'",
                ("CASE-ALPHA",)).fetchone()[0]

        prior_events = source_event_count()
        self.assertEqual(self.store.import_report("CASE-ALPHA", amended)["result"],
                         "duplicate")
        self.assertEqual(source_event_count(), prior_events)
        self.store.close()
        self.store = CaseStore(self.path)
        self.assertTrue(self.stale("CASE-ALPHA", first))
        self.assertTrue(self.stale("CASE-ALPHA", same_case))
        self.assertFalse(self.stale("CASE-BETA", other_case))
        self.assertEqual(source_event_count(), prior_events)

    def test_amendment_reopens_model_question_but_not_unrelated_review_snapshot(self):
        # An unrelated human-authored imaging review does not depend on
        # PATH-ALPHA; the model still does because it saw the whole case.
        imaging = self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes())
        run = self.save_model("CASE-ALPHA", self.qa)
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", self.qa, "Independent fictional imaging-only review.",
            [imaging["source_id"]])
        self.store.acknowledge_demo_review(
            "CASE-ALPHA", snapshot_id, "Synthetic reviewer")
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "addressed")

        changed = self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        self.assertEqual(changed["invalidated_snapshots"], [])
        self.assertIn(run, changed["invalidated_model_investigation_ids"])
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(next(s["state"] for s in state["snapshots"]
                              if s["id"] == snapshot_id), "reviewed_in_demo")
        self.assertTrue(self.stale("CASE-ALPHA", run))
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "open")

    def test_new_assessment_reopens_only_its_question(self):
        other_question = self.store.add_question(
            "CASE-ALPHA", "What different source issue is still uncertain?")
        aid = self.save_model("CASE-ALPHA", self.qa)
        other = self.save_model("CASE-ALPHA", other_question)
        e = self.store.import_synthetic_evidence(evidence())
        self.assertEqual(e["result"], "imported")
        self.assertFalse(self.stale("CASE-ALPHA", aid))
        self.assertFalse(self.stale("CASE-ALPHA", other))
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.qa, e["evidence_version_id"],
            "context", "limited",
            "Fictional research note has limited relevance to this precise question.")
        self.assertTrue(self.stale("CASE-ALPHA", aid))
        self.assertFalse(self.stale("CASE-ALPHA", other))
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "open")
        self.assertEqual(self.question_state("CASE-ALPHA", other_question), "open")

    def test_evidence_withdrawal_stales_model_without_snapshot(self):
        eid = self.store.import_synthetic_evidence(evidence())["evidence_version_id"]
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.qa, eid, "supports", "limited",
            "Synthetic note supports only a narrow methodological statement.")
        aid = self.save_model("CASE-ALPHA", self.qa)
        bid = self.save_model("CASE-BETA", self.qb)
        self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"], [])
        self.store.withdraw_synthetic_evidence(
            eid, "Fictional rights and relevance review withdrew this example.")
        self.assertTrue(self.stale("CASE-ALPHA", aid))
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "open")
        self.assertFalse(self.stale("CASE-BETA", bid))

    def test_evidence_amendment_stales_model_without_snapshot(self):
        eid = self.store.import_synthetic_evidence(evidence())["evidence_version_id"]
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.qa, eid, "contradicts", "limited",
            "Fictional methods note challenges this proposed interpretation.")
        aid = self.save_model("CASE-ALPHA", self.qa)
        amended = self.store.import_synthetic_evidence(evidence(amends=True))
        self.assertEqual(amended["result"], "imported")
        self.assertTrue(self.stale("CASE-ALPHA", aid))
        self.assertEqual(self.question_state("CASE-ALPHA", self.qa), "open")

    def test_invalidation_preserves_historical_model_artifact(self):
        eid = self.store.import_synthetic_evidence(evidence())["evidence_version_id"]
        self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.qa, eid, "context", "unknown",
            "Fictional evidence applicability remains uncertain here.")
        aid = self.save_model("CASE-ALPHA", self.qa)
        original = self.store.get_investigation("CASE-ALPHA", aid)
        self.store.withdraw_synthetic_evidence(
            eid, "Fictional evidence removed for an independent reproducibility check.")
        after = self.store.get_investigation("CASE-ALPHA", aid)
        self.assertEqual(after["id"], original["id"])
        self.assertEqual(after["abstentions"], original["abstentions"])
        self.assertEqual(after["created_at"], original["created_at"])
        self.assertEqual(after["review_state"], "pending")
        self.assertTrue(after["stale"])


if __name__ == "__main__":
    unittest.main()
