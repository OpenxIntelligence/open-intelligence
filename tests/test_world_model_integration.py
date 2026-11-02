"""Real local HTTP: one source projection and the existing model-report lifecycle."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, SYNTHETIC, WEB, seed


class WorldModelIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "world-model-integration.sqlite")
        seed(self.path)
        handler = type("WorldModelIntegrationHandler", (Handler,), {"db_path": self.path})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    def request(self, route, data=None):
        request = Request(self.base + route,
                          data=None if data is None else json.dumps(data).encode(),
                          headers={"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=8)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            mime = response.headers.get("Content-Type", "")
            return response.status, mime, json.loads(raw) if "json" in mime else raw

    def api(self, route, data=None, expected=200):
        code, _, payload = self.request(route, data)
        self.assertEqual(code, expected, payload)
        return payload

    def world(self):
        return self.api("/api/cases/CASE-ALPHA/world-model")

    def assert_observations_remain_unreviewed(self, projection):
        self.assertEqual(projection["authority"], "source_report_only_unreviewed")
        self.assertTrue(projection["observations"])
        for observation in projection["observations"]:
            self.assertEqual(observation["review_state"], "not_established")
            self.assertIsNone(observation["clinical_meaning"])

    def test_inspector_script_is_served_as_javascript(self):
        code, mime, body = self.request("/world-model.js")
        self.assertEqual(code, 200, body)
        self.assertEqual(mime, "text/javascript; charset=utf-8")
        self.assertEqual(body, (WEB / "world-model.js").read_bytes())
        self.assertIn(b"oi.synthetic-world-model/1", body)

    def test_generated_report_review_amendment_and_reassessment_share_one_projection(self):
        before = self.world()
        self.assertEqual(before["contract"], "oi.synthetic-world-model/1")
        self.assertEqual(before["case_id"], "CASE-ALPHA")
        self.assert_observations_remain_unreviewed(before)
        qid = self.api("/api/cases/CASE-ALPHA/questions", {
            "question": "Which fictional source observations still require review?"
        }, expected=201)["question_id"]

        def prepare():
            run = self.api("/api/cases/CASE-ALPHA/investigations", {
                "question_id": qid, "template": "evidence-summary", "mode": "replay"
            }, expected=201)
            return self.api(f"/api/cases/CASE-ALPHA/investigations/{run['id']}/review-draft",
                            {"question_id": qid}, expected=201)["snapshot_id"]

        first_id = prepare()
        draft = self.world()
        self.assertIn(first_id, draft["review_needed"]["draft_snapshot_ids"])
        self.assertIn(qid, draft["review_needed"]["open_question_ids"])
        self.assert_observations_remain_unreviewed(draft)
        self.api(f"/api/cases/CASE-ALPHA/snapshots/{first_id}/review",
                 {"reviewer_label": "Synthetic source reviewer"})
        reviewed = self.world()
        self.assertNotIn(first_id, reviewed["review_needed"]["draft_snapshot_ids"])
        self.assertNotIn(first_id, reviewed["review_needed"]["stale_snapshot_ids"])
        self.assertNotIn(qid, reviewed["review_needed"]["open_question_ids"])
        self.assert_observations_remain_unreviewed(reviewed)
        state = self.api("/api/cases/CASE-ALPHA/state")
        original = next(row for row in state["snapshots"] if row["id"] == first_id)
        self.assertEqual(original["state"], "reviewed_in_demo")

        self.api("/api/cases/CASE-ALPHA/imports", {
            "text": (SYNTHETIC / "alpha-pathology-amended.txt").read_text()
        })
        amended = self.world()
        self.assertIn(first_id, amended["review_needed"]["stale_snapshot_ids"])
        self.assertIn(qid, amended["review_needed"]["open_question_ids"])
        self.assertTrue(any(source["document_id"] == "PATH-ALPHA"
                            and source["version"] == 1 for source in amended["history"]))
        self.assert_observations_remain_unreviewed(amended)
        second_id = prepare()
        self.assertNotEqual(first_id, second_id)
        reassessed = self.world()
        self.assertIn(first_id, reassessed["review_needed"]["stale_snapshot_ids"])
        self.assertIn(second_id, reassessed["review_needed"]["draft_snapshot_ids"])
        self.assert_observations_remain_unreviewed(reassessed)
        self.api(f"/api/cases/CASE-ALPHA/snapshots/{second_id}/review",
                 {"reviewer_label": "Synthetic source reviewer"})
        reviewed_again = self.world()
        self.assertNotIn(qid, reviewed_again["review_needed"]["open_question_ids"])
        self.assertNotIn(second_id, reviewed_again["review_needed"]["draft_snapshot_ids"])
        # Historical stale reports remain visible; they are not an open question.
        self.assertIn(first_id, reviewed_again["review_needed"]["stale_snapshot_ids"])
        self.assert_observations_remain_unreviewed(reviewed_again)
        final = self.api("/api/cases/CASE-ALPHA/state")
        old = next(row for row in final["snapshots"] if row["id"] == first_id)
        self.assertEqual(old["summary"], original["summary"])
        self.assertEqual(old["reviewed_at"], original["reviewed_at"])
        self.assertEqual(old["reviewer_label"], original["reviewer_label"])
        self.assertEqual(old["state"], "stale")
        code, _, historical_export = self.request(
            f"/api/cases/CASE-ALPHA/snapshots/{first_id}/export")
        self.assertEqual(code, 200)
        self.assertIn(b"PATH-ALPHA@1", historical_export)


if __name__ == "__main__":
    unittest.main()
