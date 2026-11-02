"""Actual HTTP integration for the existing Composer/investigation route.

Every test uses original fictional sources, a loopback server and an isolated
SQLite file. Live provider calls are replaced by explicit in-process doubles.
"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from open_intelligence.__main__ import Handler, SYNTHETIC, seed
from open_intelligence.store import CaseStore


class NativeComposerHttpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "composer-http.sqlite")
        seed(self.db)
        handler = type("BoundComposerHandler", (Handler,), {"db_path": self.db})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, path, payload=None, headers=None):
        headers = dict(headers or {})
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = Request("http://127.0.0.1:" + str(self.port) + path,
                      data=None if payload is None else json.dumps(payload).encode("utf-8"),
                      headers=headers)
        try:
            with urlopen(req, timeout=8) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def question(self, case="CASE-ALPHA"):
        code, result = self.request(
            f"/api/cases/{case}/questions",
            {"question": "Which source-linked details changed and what remains uncertain?"})
        self.assertEqual(code, 201)
        return result["question_id"]

    def preview(self, case, question_id):
        return self.request(
            f"/api/cases/{case}/composer/context?question_id={question_id}")

    def test_existing_form_has_native_composer_preview_not_separate_chat(self):
        code, html = self.request_html("/")
        self.assertEqual(code, 200)
        self.assertIn('id="model-investigation-form"', html)
        self.assertIn('id="composer-context"', html)
        self.assertIn('src="/composer.js"', html)
        self.assertNotIn("next/script", html.lower())
        code, script = self.request_html("/composer.js")
        self.assertEqual(code, 200)
        self.assertIn("composer/context", script)

    def request_html(self, path):
        req = Request(f"http://127.0.0.1:{self.port}{path}")
        with urlopen(req, timeout=8) as resp:
            return resp.status, resp.read().decode("utf-8")

    def test_preview_is_question_case_and_source_bound(self):
        q = self.question()
        status, result = self.preview("CASE-ALPHA", q)
        self.assertEqual(status, 200)
        self.assertEqual(result["case_id"], "CASE-ALPHA")
        self.assertEqual(result["question_id"], q)
        self.assertEqual(len(result["fingerprint"]), 64)
        self.assertTrue(result["source_anchors"])
        self.assertEqual(result["tool_status"]["external_guideline_search"], "unavailable")
        status, denied = self.preview("CASE-BETA", q)
        self.assertEqual(status, 422)
        self.assertNotIn("CASE-ALPHA", json.dumps(denied))
        status, missing = self.preview("CASE-ALPHA", 999999)
        self.assertEqual(status, 422)

    def test_preview_rejects_non_ascii_excessive_and_overflowing_question_ids(self):
        for raw in ("%C2%B2", "9" * 4301, "9223372036854775808", "0", "-1"):
            with self.subTest(identifier=raw[:25], length=len(raw)):
                try:
                    status, response = self.request(
                        "/api/cases/CASE-ALPHA/composer/context?question_id=" + raw)
                except Exception as error:
                    self.fail(f"Invalid identifiers must return a validation response: {type(error).__name__}")
                self.assertEqual(status, 422)
                self.assertIn("positive integer", response["error"])
        status, missing = self.preview("CASE-ALPHA", 9223372036854775807)
        self.assertEqual(status, 422)
        self.assertIn("not in this case", missing["error"])

    def test_amendment_after_preview_rejects_stale_replay_before_run(self):
        q = self.question()
        status, context = self.preview("CASE-ALPHA", q)
        self.assertEqual(status, 200)
        status, amendment = self.request(
            "/api/cases/CASE-ALPHA/imports",
            {"text": (SYNTHETIC / "alpha-pathology-amended.txt").read_text()})
        self.assertEqual(status, 200)
        self.assertEqual(amendment["result"], "imported")
        status, blocked = self.request("/api/cases/CASE-ALPHA/investigations", {
            "question_id": q, "template": "evidence-summary", "mode": "replay",
            "context_fingerprint": context["fingerprint"]})
        self.assertEqual(status, 422)
        self.assertIn("stale", blocked["error"].lower())
        store = CaseStore(self.db)
        try:
            self.assertEqual(store.list_investigations("CASE-ALPHA"), [])
        finally:
            store.close()

    def test_mid_model_source_change_cannot_be_saved_under_old_snapshot(self):
        q = self.question()
        status, before = self.preview("CASE-ALPHA", q)
        self.assertEqual(status, 200)
        calls = []
        def model_changes_source(prompt, token):
            calls.append(True)
            writer = CaseStore(self.db)
            try:
                writer.import_report(
                    "CASE-ALPHA",
                    (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
            finally:
                writer.close()
            return {"claims": [], "abstentions": [
                {"topic": "Unresolved synthetic history", "reason": "insufficient_evidence"}]}
        with patch("open_intelligence.__main__.meta_api_key", return_value="fake-test-token"), \
             patch("open_intelligence.__main__.call_meta_api", side_effect=model_changes_source):
            code, blocked = self.request("/api/cases/CASE-ALPHA/investigations", {
                "question_id": q, "template": "evidence-summary", "mode": "live",
                "context_fingerprint": before["fingerprint"]})
        self.assertEqual(calls, [True])
        self.assertEqual(code, 422)
        self.assertIn("stale", blocked["error"].lower())
        store = CaseStore(self.db)
        try:
            self.assertEqual(store.list_investigations("CASE-ALPHA"), [])
        finally:
            store.close()

    def test_current_context_runs_original_replay_path_and_is_persistent(self):
        q = self.question()
        _, before = self.preview("CASE-ALPHA", q)
        status, completed = self.request("/api/cases/CASE-ALPHA/investigations", {
            "question_id": q, "template": "evidence-summary", "mode": "replay",
            "context_fingerprint": before["fingerprint"]})
        self.assertEqual(status, 201)
        self.assertEqual(completed["kind"], "hypothesis")
        self.assertEqual(completed["review_state"], "pending")
        self.assertEqual(completed["mode"], "replay")
        self.assertEqual(completed["model"], "recorded-replay")
        store = CaseStore(self.db)
        try:
            self.assertEqual(len(store.list_investigations("CASE-ALPHA")), 1)
        finally:
            store.close()

    def test_malformed_context_fingerprint_rejected_without_investigation(self):
        q = self.question()
        code, response = self.request("/api/cases/CASE-ALPHA/investigations", {
            "question_id": q, "template": "evidence-summary", "mode": "replay",
            "context_fingerprint": "wrong"})
        self.assertEqual(code, 422)
        store = CaseStore(self.db)
        try:
            self.assertEqual(store.list_investigations("CASE-ALPHA"), [])
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
