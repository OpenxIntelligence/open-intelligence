"""A persisted, version-bound handoff; only independently authored fiction.

No live model or patient-derived fixtures. Exercise the real SQLite ledger,
including two connections and a transaction failure after snapshot insertion.
"""
from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from open_intelligence.__main__ import SYNTHETIC, seed
from open_intelligence.changes import changes_since_review
from open_intelligence.composer import composer_context_fingerprint
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.store import CaseStore, InvalidInput


class InvestigationReviewHandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "review-handoff.sqlite"
        seed(str(self.path))
        self.store = CaseStore(self.path)
        self.qid = self.store.add_question(
            "CASE-ALPHA", "What fictional source findings support or challenge this interpretation?")
        self.other_qid = self.store.add_question("CASE-BETA", "Which fictional facts remain uncertain?")
        evidence = self.store.import_synthetic_evidence((SYNTHETIC / "demo-evidence.txt").read_bytes())
        self.eid = evidence["evidence_version_id"]
        self.aid = self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.qid, self.eid, "context", "limited",
            "The independently authored methods example has limited applicability.")
        self.sid = self.store.state("CASE-ALPHA")["sources"][0]["id"]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def output(self):
        claims = [{"text": text, "support": support, "uncertainty": "high",
                   "limits": "Fictional observations cannot establish a clinical conclusion.",
                   "citations": [{"type": "source", "id": self.sid},
                                 {"type": "assessment", "id": self.aid}], "kind": "hypothesis"}
                  for support, text in (
                      ("supports", "The fictional source supports this limited observation."),
                      ("contradicts", "The fictional evidence challenges this interpretation."),
                      ("context", "The assay example supplies context, with uncertain applicability."))]
        return ValidatedInvestigation("completed", claims, [
            {"topic": "Missing follow-up record", "reason": "insufficient_evidence"}],
            [{"claim": {"text": "Rejected text must stay out of the report."},
              "reason": "unresolvable_citation"}], "recorded-replay", "replay")

    def save(self, output=None, captured=True):
        token = composer_context_fingerprint(self.store, "CASE-ALPHA", self.qid) if captured else None
        return self.store.save_investigation(
            "CASE-ALPHA", self.qid, "evidence-summary", output or self.output(), "replay",
            context_fingerprint=token)

    def prepare(self, run_id):
        return self.store.prepare_investigation_review_draft("CASE-ALPHA", run_id, self.qid)

    def question_state(self):
        return next(x["state"] for x in self.store.state("CASE-ALPHA")["questions"] if x["id"] == self.qid)

    def test_generation_and_preparation_do_not_acknowledge_review(self):
        run_id = self.save()
        self.assertEqual(self.question_state(), "open")
        result = self.prepare(run_id)
        self.assertEqual(result["state"], "draft")
        self.assertFalse(result["duplicate"])
        self.assertEqual(self.question_state(), "open")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM review_events").fetchone()[0], 0)
        self.store.acknowledge_demo_review("CASE-ALPHA", result["snapshot_id"], "Synthetic reviewer")
        self.assertEqual(self.question_state(), "addressed")
        self.assertEqual(self.store.get_investigation("CASE-ALPHA", run_id)["review_state"], "pending")

    def test_report_provenance_citations_and_original_output_survive_restart(self):
        output = self.output()
        original = copy.deepcopy(output)
        run_id = self.save(output)
        result = self.prepare(run_id)
        snapshot_id = result["snapshot_id"]
        self.store.close()
        self.store = CaseStore(self.path)
        run = self.store.get_investigation("CASE-ALPHA", run_id)
        self.assertEqual(run["claims"], original.claims)
        self.assertEqual(run["abstentions"], original.abstentions)
        self.assertEqual(run["dropped"], original.dropped)
        self.assertEqual(run["review_draft"]["snapshot_id"], snapshot_id)
        snapshot = self.store.state("CASE-ALPHA")["snapshots"][0]
        provenance = snapshot["investigation_origin"]
        self.assertEqual(provenance["investigation_id"], run_id)
        self.assertEqual(provenance["context_fingerprint"], run["context_fingerprint"])
        self.assertEqual(provenance["model"], "recorded-replay")
        self.assertEqual(provenance["mode"], "replay")
        self.assertEqual(provenance["template"], "evidence-summary")
        self.assertEqual(len(provenance["output_sha256"]), 64)
        self.assertEqual({(c["type"], c["id"]) for c in provenance["citations"]},
                         {("source", self.sid), ("assessment", self.aid)})
        for citation in provenance["citations"]:
            if citation["type"] == "source":
                self.assertIn("OI-SYNTHETIC", self.store.source_text("CASE-ALPHA", citation["id"]))
            else:
                self.assertEqual(citation["evidence_version_id"], self.eid)
                self.assertGreater(citation["statement_line"], 0)
        report = self.store.export_markdown("CASE-ALPHA", snapshot_id)
        for expected in ("Supporting findings", "Contradicting findings", "Context findings",
                         "Uncertainty: high", "Limits:", "Missing information and abstentions",
                         "Missing follow-up record", "insufficient_evidence", "recorded-replay",
                         "evidence-summary", "replay", "model-assisted", "source-", "assessment-"):
            self.assertIn(expected, report)
        self.assertNotIn("Rejected text must stay out", report)
        self.assertNotIn("Draft (human-authored)", report)

    def test_retry_before_and_after_explicit_review_creates_nothing_new(self):
        run_id = self.save()
        first = self.prepare(run_id)
        second = self.prepare(run_id)
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertTrue(second["duplicate"])
        self.store.acknowledge_demo_review("CASE-ALPHA", first["snapshot_id"], "Synthetic reviewer")
        reviewed_retry = self.prepare(run_id)
        self.assertEqual(reviewed_retry["state"], "reviewed_in_demo")
        self.assertTrue(reviewed_retry["duplicate"])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM investigation_review_drafts").fetchone()[0], 1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM events WHERE kind='draft_created'").fetchone()[0], 1)

    def test_concurrent_requests_create_one_snapshot_and_link(self):
        run_id = self.save()
        def worker():
            store = CaseStore(self.path)
            try:
                return store.prepare_investigation_review_draft("CASE-ALPHA", run_id, self.qid)
            finally:
                store.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(len({r["snapshot_id"] for r in results}), 1)
        self.assertEqual(sorted(r["duplicate"] for r in results), [False, True])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)

    def test_strict_identifiers_and_wrong_case_or_question_fail_without_writes(self):
        run_id = self.save()
        for invalid in (True, False, 0, -1, "1", 1.0, None):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(InvalidInput):
                    self.store.prepare_investigation_review_draft("CASE-ALPHA", invalid, self.qid)
                with self.assertRaises(InvalidInput):
                    self.store.prepare_investigation_review_draft("CASE-ALPHA", run_id, invalid)
        with self.assertRaises(InvalidInput) as wrong:
            self.store.prepare_investigation_review_draft("CASE-BETA", run_id, self.other_qid)
        self.assertNotIn("ALPHA", str(wrong.exception))
        with self.assertRaises(InvalidInput) as missing:
            self.store.prepare_investigation_review_draft("CASE-BETA", 9999999, self.other_qid)
        self.assertEqual(str(wrong.exception), str(missing.exception))
        another = self.store.add_question("CASE-ALPHA", "A different question in the same fictional case?")
        with self.assertRaises(InvalidInput):
            self.store.prepare_investigation_review_draft("CASE-ALPHA", run_id, another)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0)

    def test_legacy_or_changed_captured_context_requires_new_run(self):
        legacy = self.save(captured=False)
        with self.assertRaisesRegex(InvalidInput, "context|new run"):
            self.prepare(legacy)
        run_id = self.save()
        with self.store.db:
            self.store.db.execute("UPDATE questions SET question=? WHERE id=?",
                                  ("Changed fictional question after the model ran?", self.qid))
        with self.assertRaisesRegex(InvalidInput, "stale|context"):
            self.prepare(run_id)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0)

    def test_opening_a_pre_context_database_preserves_legacy_output_without_backfill(self):
        # Reproduce the actual old table contract, with a saved run already in it.
        output = self.output()
        with self.store.db:
            self.store.db.execute("DROP TABLE investigation_review_drafts")
            self.store.db.execute("DROP TABLE investigations")
            self.store.db.execute("""CREATE TABLE investigations (
                id INTEGER PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(case_id),
                question_id INTEGER NOT NULL REFERENCES questions(id), template TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('completed','abstained','blocked_by_policy','failed')),
                mode TEXT NOT NULL CHECK(mode IN ('live','replay')), model TEXT NOT NULL,
                claims_json TEXT NOT NULL, abstentions_json TEXT NOT NULL, dropped_json TEXT NOT NULL,
                stale INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
            self.store.db.execute("""INSERT INTO investigations VALUES
                (17,'CASE-ALPHA',?,'evidence-summary','completed','replay','recorded-replay',?,?,?,0,?)""",
                (self.qid, json.dumps(output.claims), json.dumps(output.abstentions),
                 json.dumps(output.dropped), "2026-01-01T00:00:00+00:00"))
        self.store.close()
        self.store = CaseStore(self.path)
        legacy = self.store.get_investigation("CASE-ALPHA", 17)
        self.assertIsNone(legacy["context_fingerprint"])
        self.assertIsNone(legacy["review_draft"])
        self.assertEqual(legacy["claims"], output.claims)
        self.assertEqual(legacy["created_at"], "2026-01-01T00:00:00+00:00")
        with self.assertRaisesRegex(InvalidInput, "captured context"):
            self.prepare(17)

    def test_generated_report_preserves_long_literal_text_and_refuses_silent_truncation(self):
        output = self.output()
        output.claims[0]["text"] = "Literal fictional text\n```\n<script>inert</script>\n```\n" + "Detail. " * 500
        run_id = self.save(output)
        result = self.prepare(run_id)
        snapshot = self.store.state("CASE-ALPHA")["snapshots"][0]
        self.assertIn(output.claims[0]["text"], snapshot["summary"])
        report = self.store.export_markdown("CASE-ALPHA", result["snapshot_id"])
        self.assertIn("````text\nModel-assisted review draft", report)
        self.assertIn(output.claims[0]["text"], report)
        oversized = self.output()
        oversized.claims[0]["text"] = "Fictional detail. " * 5000
        with self.assertRaisesRegex(InvalidInput, "limit"):
            self.prepare(self.save(oversized))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)

    def test_failed_or_blocked_runs_cannot_be_prepared(self):
        for status in ("failed", "blocked_by_policy"):
            output = self.output()
            output.status = status
            run_id = self.save(output)
            with self.assertRaises(InvalidInput):
                self.prepare(run_id)

    def test_citations_must_resolve_strictly_in_this_case_and_question(self):
        beta_source = self.store.state("CASE-BETA")["sources"][0]["id"]
        other_assessment = self.store.assess_synthetic_evidence(
            "CASE-BETA", self.other_qid, self.eid, "context", "unknown",
            "Independent fictional assessment in another case.")
        for citation in ({"type": "source", "id": beta_source},
                         {"type": "assessment", "id": other_assessment},
                         {"type": "source", "id": True},
                         {"type": "assessment", "id": "1"},
                         {"type": "source", "id": 0},
                         {"type": "source", "id": 9999999}):
            with self.subTest(citation=citation):
                output = self.output()
                output.claims[0]["citations"] = [citation]
                run_id = self.save(output)
                with self.assertRaises(InvalidInput):
                    self.prepare(run_id)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0)

    def test_link_insert_failure_rolls_back_snapshot_joins_and_events(self):
        run_id = self.save()
        before = self.store.db.execute("SELECT count(*) FROM events").fetchone()[0]
        self.store.db.execute("""CREATE TRIGGER force_link_failure BEFORE INSERT ON investigation_review_drafts
            BEGIN SELECT RAISE(ABORT, 'forced test failure'); END""")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "forced test failure"):
            self.prepare(run_id)
        for table in ("snapshots", "snapshot_sources", "snapshot_evidence", "investigation_review_drafts"):
            self.assertEqual(self.store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM events").fetchone()[0], before)
        self.assertEqual(self.question_state(), "open")
        self.store.db.execute("DROP TRIGGER force_link_failure")
        self.assertFalse(self.prepare(run_id)["duplicate"])

    def test_source_amendment_preserves_report_review_and_model_and_requires_new_run(self):
        run_id = self.save()
        prepared = self.prepare(run_id)
        snapshot_id = prepared["snapshot_id"]
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "Synthetic reviewer")
        before_run = self.store.get_investigation("CASE-ALPHA", run_id)
        before_report = self.store.state("CASE-ALPHA")["snapshots"][0]
        review_before = dict(self.store.db.execute("SELECT * FROM review_events").fetchone())
        self.store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        self.assert_stale_history(run_id, snapshot_id, before_report, review_before)
        after = self.store.get_investigation("CASE-ALPHA", run_id)
        for key in ("claims", "abstentions", "dropped", "created_at", "context_fingerprint"):
            self.assertEqual(after[key], before_run[key])
        self.sid = next(s["id"] for s in self.store.state("CASE-ALPHA")["sources"] if s["state"] == "current")
        new_run = self.save()
        new_report = self.prepare(new_run)
        self.assertNotEqual(new_report["snapshot_id"], snapshot_id)
        self.assertEqual(new_report["state"], "draft")

    def assert_stale_history(self, run_id, snapshot_id, original, review):
        after = next(x for x in self.store.state("CASE-ALPHA")["snapshots"] if x["id"] == snapshot_id)
        self.assertEqual(after["state"], "stale")
        for key in ("summary", "reviewed_at", "reviewer_label", "investigation_origin"):
            self.assertEqual(after[key], original[key])
        self.assertEqual(dict(self.store.db.execute("SELECT * FROM review_events WHERE snapshot_id=?", (snapshot_id,)).fetchone()), review)
        self.assertEqual(self.question_state(), "open")
        with self.assertRaisesRegex(InvalidInput, "stale"):
            self.prepare(run_id)
        with self.assertRaises(InvalidInput):
            self.store.acknowledge_demo_review("CASE-ALPHA", snapshot_id, "Another synthetic reviewer")

    def test_new_source_or_assessment_stales_linked_report_even_without_citation(self):
        for change in ("source", "assessment"):
            with self.subTest(change=change):
                run_id = self.save()
                result = self.prepare(run_id)
                self.store.acknowledge_demo_review("CASE-ALPHA", result["snapshot_id"], "Synthetic reviewer")
                original = next(x for x in self.store.state("CASE-ALPHA")["snapshots"] if x["id"] == result["snapshot_id"])
                review = dict(self.store.db.execute("SELECT * FROM review_events WHERE snapshot_id=?", (result["snapshot_id"],)).fetchone())
                if change == "source":
                    raw = (SYNTHETIC / "alpha-imaging.txt").read_bytes().replace(
                        b"Document: IMG-ALPHA\n", b"Document: IMG-ALPHA-ADDITIONAL\n")
                    self.store.import_report("CASE-ALPHA", raw)
                else:
                    self.store.assess_synthetic_evidence(
                        "CASE-ALPHA", self.qid, self.eid, "contradicts", "unknown",
                        "A new fictional assessment challenges the context of the saved run.")
                self.assert_stale_history(run_id, result["snapshot_id"], original, review)
                changes = changes_since_review(self.store, "CASE-ALPHA")
                self.assertEqual({item["snapshot_id"] for item in changes["stale_investigations"]},
                                 {result["snapshot_id"]})

    def test_evidence_withdrawal_preserves_historical_report_and_review(self):
        run_id = self.save()
        prepared = self.prepare(run_id)
        self.store.acknowledge_demo_review("CASE-ALPHA", prepared["snapshot_id"], "Synthetic reviewer")
        original = self.store.state("CASE-ALPHA")["snapshots"][0]
        review = dict(self.store.db.execute("SELECT * FROM review_events").fetchone())
        self.store.withdraw_synthetic_evidence(self.eid, "Fictional example withdrawn after a demonstration audit.")
        self.assert_stale_history(run_id, prepared["snapshot_id"], original, review)
        self.assertIn("Missing follow-up record", self.store.export_markdown("CASE-ALPHA", prepared["snapshot_id"]))

    def test_evidence_amendment_keeps_original_version_and_review(self):
        run_id = self.save()
        prepared = self.prepare(run_id)
        self.store.acknowledge_demo_review("CASE-ALPHA", prepared["snapshot_id"], "Synthetic reviewer")
        original = self.store.state("CASE-ALPHA")["snapshots"][0]
        review = dict(self.store.db.execute("SELECT * FROM review_events").fetchone())
        amended = (SYNTHETIC / "demo-evidence.txt").read_text().replace(
            "Statement: ", "Amends: EVID-ASSAY@1\nStatement: ").replace(
            "an assay limitation", "a separately described assay limitation")
        self.store.import_synthetic_evidence(amended.encode())
        self.assert_stale_history(run_id, prepared["snapshot_id"], original, review)
        export = self.store.export_markdown("CASE-ALPHA", prepared["snapshot_id"])
        self.assertIn("EVID-ASSAY@1", export)
        self.assertNotIn("a separately described assay limitation", export)

    def test_abstention_only_run_is_a_reviewable_missing_information_report(self):
        output = self.output()
        output.claims = []
        output.status = "abstained"
        run_id = self.save(output)
        report = self.prepare(run_id)
        text = self.store.export_markdown("CASE-ALPHA", report["snapshot_id"])
        self.assertIn("Missing follow-up record", text)
        self.assertEqual(self.question_state(), "open")

    def test_source_free_abstention_keeps_empty_context_until_first_source_arrives(self):
        self.store.add_case("CASE-EMPTY", "Fictional case without source records")
        question_id = self.store.add_question("CASE-EMPTY", "Which fictional records are missing?")
        output = ValidatedInvestigation("abstained", [], [
            {"topic": "No supplied source records", "reason": "no_evidence"}],
            [], "recorded-replay", "replay")
        run_id = self.store.save_investigation(
            "CASE-EMPTY", question_id, "evidence-summary", output, "replay",
            context_fingerprint=composer_context_fingerprint(self.store, "CASE-EMPTY", question_id))
        try:
            report = self.store.prepare_investigation_review_draft("CASE-EMPTY", run_id, question_id)
        except InvalidInput as error:
            self.fail(f"A source-free abstention must remain reviewable: {error}")
        snapshot_id = report["snapshot_id"]
        snapshot = self.store.state("CASE-EMPTY")["snapshots"][0]
        self.assertEqual(snapshot["state"], "draft")
        self.assertEqual(snapshot["source_ids"], [])
        self.assertEqual(snapshot["evidence_assessment_ids"], [])
        self.assertEqual(report["provenance"]["source_ids"], [])
        self.assertEqual(report["provenance"]["citations"], [])
        self.assertIn("No supplied source records", self.store.export_markdown("CASE-EMPTY", snapshot_id))
        self.store.acknowledge_demo_review("CASE-EMPTY", snapshot_id, "Synthetic reviewer")
        retry = self.store.prepare_investigation_review_draft("CASE-EMPTY", run_id, question_id)
        self.assertTrue(retry["duplicate"])
        self.assertEqual(retry["snapshot_id"], snapshot_id)
        original = self.store.get_investigation("CASE-EMPTY", run_id)
        raw = (SYNTHETIC / "alpha-imaging.txt").read_bytes().replace(
            b"Patient: CASE-ALPHA\n", b"Patient: CASE-EMPTY\n")
        self.store.import_report("CASE-EMPTY", raw)
        state = self.store.state("CASE-EMPTY")
        self.assertEqual(state["snapshots"][0]["state"], "stale")
        self.assertEqual(state["snapshots"][0]["summary"], snapshot["summary"])
        self.assertEqual(state["questions"][0]["state"], "open")
        self.assertEqual(self.store.get_investigation("CASE-EMPTY", run_id)["abstentions"], original["abstentions"])
        with self.assertRaisesRegex(InvalidInput, "stale"):
            self.store.prepare_investigation_review_draft("CASE-EMPTY", run_id, question_id)

    def test_source_free_handoff_requires_genuine_abstention_without_accepted_claims(self):
        self.store.add_case("CASE-EMPTY", "Fictional case without source records")
        question_id = self.store.add_question("CASE-EMPTY", "Which fictional records are missing?")
        assessment_id = self.store.assess_synthetic_evidence(
            "CASE-EMPTY", question_id, self.eid, "context", "unknown",
            "The fictional assessment cannot replace missing patient source records.")
        claim = copy.deepcopy(self.output().claims[0])
        claim["citations"] = [{"type": "assessment", "id": assessment_id}]
        abstentions = [{"topic": "Missing source records", "reason": "no_evidence"}]
        for status, claims, missing in (("completed", [], abstentions),
                                        ("completed", [claim], abstentions),
                                        ("abstained", [claim], abstentions),
                                        ("abstained", [], [])):
            with self.subTest(status=status, claims=bool(claims), missing=bool(missing)):
                output = ValidatedInvestigation(status, claims, missing, [], "recorded-replay", "replay")
                run_id = self.store.save_investigation(
                    "CASE-EMPTY", question_id, "evidence-summary", output, "replay",
                    context_fingerprint=composer_context_fingerprint(self.store, "CASE-EMPTY", question_id))
                with self.assertRaises(InvalidInput):
                    self.store.prepare_investigation_review_draft("CASE-EMPTY", run_id, question_id)
        self.assertEqual(self.store.state("CASE-EMPTY")["snapshots"], [])

    def test_generated_handoff_keeps_all_canonical_inputs_beyond_manual_draft_limits(self):
        source_ids = [source["id"] for source in self.store.state("CASE-ALPHA")["sources"]]
        raw = (SYNTHETIC / "alpha-imaging.txt").read_bytes()
        for index in range(49):
            added = self.store.import_report("CASE-ALPHA", raw.replace(
                b"Document: IMG-ALPHA\n", f"Document: IMG-ALPHA-EXTRA-{index}\n".encode()))
            source_ids.append(added["source_id"])
        assessment_ids = [self.aid]
        for index in range(50):
            assessment_ids.append(self.store.assess_synthetic_evidence(
                "CASE-ALPHA", self.qid, self.eid, "context", "unknown",
                f"Fictional independent assessment {index} leaves applicability unresolved."))
        self.assertEqual(len(source_ids), 51)
        self.assertEqual(len(assessment_ids), 51)
        # Public/manual drafts retain their at-least-one and max-50 policies.
        for sources, assessments in (([], []), (source_ids, []), ([self.sid], assessment_ids)):
            with self.subTest(sources=len(sources), assessments=len(assessments)):
                with self.assertRaises(InvalidInput):
                    self.store.create_snapshot("CASE-ALPHA", self.qid,
                                               "Human-authored fictional review draft.", sources, assessments)
        self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"], [])
        run_id = self.save()
        try:
            report = self.prepare(run_id)
        except InvalidInput as error:
            self.fail(f"Generated handoff must retain all canonical dependencies: {error}")
        snapshot = self.store.state("CASE-ALPHA")["snapshots"][0]
        self.assertEqual(snapshot["source_ids"], sorted(source_ids))
        self.assertEqual(snapshot["evidence_assessment_ids"], sorted(assessment_ids))
        self.assertEqual(report["provenance"]["source_ids"], sorted(source_ids))
        self.assertEqual(report["provenance"]["evidence_assessment_ids"], sorted(assessment_ids))
        self.assertEqual(self.prepare(run_id)["snapshot_id"], report["snapshot_id"])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
