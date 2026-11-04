"""Real loopback HTTP handoff with independently authored synthetic records."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, SYNTHETIC, seed
from open_intelligence.store import CaseStore


class InvestigationReviewHandoffHttpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "handoff-http.sqlite")
        seed(self.path)
        handler = type("HandoffHandler", (Handler,), {"db_path": self.path})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, path, payload=None):
        request = Request(self.base + path,
                          data=json.dumps(payload).encode() if payload is not None else None,
                          headers={"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=8)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if "json" in response.headers.get("Content-Type", "") else raw

    def question(self, case="CASE-ALPHA"):
        code, body = self.request(f"/api/cases/{case}/questions", {
            "question": "Which fictional findings are supported and what remains unknown?"})
        self.assertEqual(code, 201)
        return body["question_id"]

    def run_model(self, question_id, **extra):
        return self.request("/api/cases/CASE-ALPHA/investigations", {
            "question_id": question_id, "template": "evidence-summary", "mode": "replay", **extra})

    def test_replay_prepare_export_explicit_review_amendment_lifecycle(self):
        question_id = self.question()
        code, run = self.run_model(question_id)
        self.assertEqual(code, 201)
        self.assertEqual(len(run.get("context_fingerprint") or ""), 64)
        code, state = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(next(q["state"] for q in state["questions"] if q["id"] == question_id), "open")
        route = f"/api/cases/CASE-ALPHA/investigations/{run['id']}/review-draft"
        code, prepared = self.request(route, {"question_id": question_id})
        self.assertEqual(code, 201)
        snapshot_id = prepared["snapshot_id"]
        self.assertFalse(prepared["duplicate"])
        self.assertEqual(prepared["state"], "draft")
        code, duplicate = self.request(route, {"question_id": question_id})
        self.assertEqual(code, 200)
        self.assertEqual(duplicate["snapshot_id"], snapshot_id)
        code, detail = self.request(f"/api/cases/CASE-ALPHA/investigations/{run['id']}")
        self.assertEqual(detail["review_state"], "pending")
        self.assertEqual(detail["review_draft"]["snapshot_id"], snapshot_id)
        code, report = self.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/export")
        self.assertEqual(code, 200)
        self.assertIn("model-assisted", report)
        self.assertIn("recorded-replay", report)
        self.assertIn("Resolved finding citations", report)
        code, review = self.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/review", {
            "reviewer_label": "Synthetic unverified reviewer"})
        self.assertEqual(code, 200)
        code, acknowledged_retry = self.request(route, {"question_id": question_id})
        self.assertEqual(code, 200)
        self.assertEqual(acknowledged_retry["state"], "reviewed_in_demo")
        self.request("/api/cases/CASE-ALPHA/imports", {
            "text": (SYNTHETIC / "alpha-pathology-amended.txt").read_text()})
        code, rejected = self.request(route, {"question_id": question_id})
        self.assertEqual(code, 422)
        self.assertIn("stale", rejected["error"])
        code, history = self.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/export")
        self.assertEqual(code, 200)
        self.assertIn("**stale**", history)
        self.assertIn("recorded-replay", history)
        store = CaseStore(self.path)
        try:
            self.assertEqual(store.db.execute("SELECT count(*) FROM review_events").fetchone()[0], 1)
        finally:
            store.close()

    def test_case_question_and_strict_id_failures_disclose_no_other_case_content(self):
        qid = self.question()
        beta_qid = self.question("CASE-BETA")
        _, run = self.run_model(qid)
        route = f"/api/cases/CASE-ALPHA/investigations/{run['id']}/review-draft"
        for invalid in (True, False, 0, -1, "1", 1.0, None):
            with self.subTest(invalid=invalid):
                status, body = self.request(route, {"question_id": invalid})
                self.assertEqual(status, 422)
        status, wrong = self.request(
            f"/api/cases/CASE-BETA/investigations/{run['id']}/review-draft", {"question_id": beta_qid})
        self.assertEqual(status, 422)
        status, missing = self.request(
            "/api/cases/CASE-BETA/investigations/9999999/review-draft", {"question_id": beta_qid})
        self.assertEqual(status, 422)
        self.assertEqual(wrong, missing)
        self.assertNotIn("ALPHA", json.dumps(wrong))
        status, body = self.request(route, {"question_id": beta_qid})
        self.assertEqual(status, 422)
        status, state = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(state["snapshots"], [])

    def test_without_preview_token_mid_model_change_still_rejects_save(self):
        qid = self.question()
        def changed_during_model(prompt, key):
            store = CaseStore(self.path)
            try:
                store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
            finally:
                store.close()
            return {"claims": [], "abstentions": [{"topic": "Missing fictional comparison", "reason": "insufficient_evidence"}]}
        with patch("open_intelligence.__main__.meta_api_key", return_value="synthetic-test-token"), \
             patch("open_intelligence.__main__.call_meta_api", side_effect=changed_during_model):
            code, rejected = self.run_model(qid, mode="live")
        self.assertEqual(code, 422)
        self.assertIn("stale", rejected["error"])
        code, runs = self.request("/api/cases/CASE-ALPHA/investigations")
        self.assertEqual(runs["investigations"], [])

    def test_live_mode_provenance_survives_handoff_without_any_live_call(self):
        qid = self.question()
        output = {"claims": [], "abstentions": [{"topic": "Missing independent fictional record", "reason": "no_evidence"}]}
        with patch("open_intelligence.__main__.meta_api_key", return_value="synthetic-test-token"), \
             patch("open_intelligence.__main__.call_meta_api", return_value=output):
            code, run = self.run_model(qid, mode="live")
        self.assertEqual(code, 201)
        code, prepared = self.request(f"/api/cases/CASE-ALPHA/investigations/{run['id']}/review-draft",
                                      {"question_id": qid})
        self.assertEqual(code, 201)
        self.assertEqual(prepared["provenance"]["mode"], "live")
        self.assertEqual(prepared["provenance"]["model"], run["model"])
        self.assertEqual(prepared["provenance"]["status"], "abstained")
        self.assertEqual(prepared["state"], "draft")

    def test_source_free_replay_can_prepare_missing_information_without_relaxing_manual_drafts(self):
        code, _ = self.request("/api/cases", {
            "case_id": "CASE-EMPTY", "label": "Fictional case without source records"})
        self.assertEqual(code, 201)
        question_id = self.question("CASE-EMPTY")
        code, run = self.request("/api/cases/CASE-EMPTY/investigations", {
            "question_id": question_id, "template": "evidence-summary", "mode": "replay"})
        self.assertEqual(code, 201)
        self.assertEqual(run["status"], "abstained")
        self.assertEqual(run["claims"], [])
        self.assertTrue(run["abstentions"])
        code, prepared = self.request(
            f"/api/cases/CASE-EMPTY/investigations/{run['id']}/review-draft",
            {"question_id": question_id, "source_ids": [9999999], "evidence_assessment_ids": [9999999]})
        self.assertEqual(code, 201)
        self.assertEqual(prepared["provenance"]["source_ids"], [])
        self.assertEqual(prepared["provenance"]["evidence_assessment_ids"], [])
        self.assertEqual(prepared["state"], "draft")
        code, rejected = self.request("/api/cases/CASE-EMPTY/snapshots", {
            "question_id": question_id, "summary": "Human-authored fictional review draft.",
            "source_ids": [], "allow_empty_sources": True, "max_dependencies": None})
        self.assertEqual(code, 422)
        self.assertIn("current source", rejected["error"])


if __name__ == "__main__":
    unittest.main()
