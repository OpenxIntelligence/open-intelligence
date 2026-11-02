"""MRT-01 first connected seam: real local HTTP+SQLite, invented case fixtures.

This is an acceptance/regression test of the EXISTING synthetic demonstration,
not the full clinical MVP, an authenticated EHR, or a live AI model evaluation.
It deliberately uses a recorded replay and a demo-only review, never clinical
sign-off. No external network request or personal-case data is needed.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore
from open_intelligence.__main__ import Handler

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class FirstConnectedSlice(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "mrt01.sqlite")
        # This handler is bound to a fresh, synthetic-only empty SQLite DB.
        with CaseStore(self.db_path):
            pass
        bound = type("MRT01BoundHandler", (Handler,), {
            "db_path": self.db_path, "allow_crossref_live": False,
        })
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tempdir.cleanup()

    def api(self, endpoint, payload=None):
        headers = {}
        body = None
        if payload is not None:
            headers = {
                "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.port}",
            }
            body = json.dumps(payload).encode("utf-8")
        request = Request(f"http://127.0.0.1:{self.port}{endpoint}",
                          data=body, headers=headers)
        try:
            with urlopen(request, timeout=8) as response:
                raw = response.read()
                if "json" in response.headers.get("Content-Type", ""):
                    return response.status, json.loads(raw)
                return response.status, raw.decode("utf-8")
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def fixture(self, name):
        return (FIXTURES / name).read_text(encoding="utf-8")

    def assert_api(self, endpoint, payload, expected):
        status, result = self.api(endpoint, payload)
        self.assertEqual(status, expected, f"{endpoint}: {result}")
        return result

    def test_source_evidence_replay_review_amendment_and_persistence(self):
        """Full demonstrated slice, including genuine negative controls."""
        for case in ("CASE-ALPHA", "CASE-BETA"):
            self.assert_api("/api/cases",
                            {"case_id": case, "label": f"Independent fictional {case}"},
                            201)
        root = "/api/cases/CASE-ALPHA"
        beta = "/api/cases/CASE-BETA"
        # Identity mismatch must quarantine without creating any assertions.
        mismatch = self.assert_api(root + "/imports",
            {"text": self.fixture("beta-pathology.txt")}, 200)
        self.assertEqual(mismatch["result"], "quarantined")
        self.assertEqual(self.api(root + "/state")[1]["assertions"], [])

        pathology = self.assert_api(root + "/imports",
            {"text": self.fixture("alpha-pathology-original.txt")}, 200)
        imaging = self.assert_api(root + "/imports",
            {"text": self.fixture("alpha-imaging.txt")}, 200)
        beta_path = self.assert_api(beta + "/imports",
            {"text": self.fixture("beta-pathology.txt")}, 200)
        self.assertEqual(pathology["result"], "imported")
        self.assertEqual(imaging["result"], "imported")
        self.assertEqual(beta_path["result"], "imported")
        state = self.api(root + "/state")[1]
        before = {a["finding_key"]: a["certainty"] for a in state["assertions"]}
        self.assertEqual(before["marker-a"], "not-reported")
        self.assertEqual(before["comparison"], "pending")
        self.assertEqual(self.api(
            beta + f"/sources/{pathology['source_id']}")[0], 422)

        question = self.assert_api(root + "/questions",
            {"question": "What does the fictional pathology report establish?"}, 201)
        qid = question["question_id"]
        evidence = self.assert_api("/api/evidence/imports",
            {"text": self.fixture("demo-evidence.txt")}, 200)
        eid = evidence["evidence_version_id"]
        assessment = self.assert_api(root + "/evidence-assessments", {
            "question_id": qid, "evidence_version_id": eid,
            "relation": "context", "applicability": "limited",
            "rationale": "The invented methods note is relevant only as a provenance demonstration.",
        }, 201)["assessment_id"]

        linked = self.assert_api(root + "/snapshots", {
            "question_id": qid,
            "summary": "Authored fictional source and evidence review, not a medical conclusion.",
            "source_ids": [pathology["source_id"]],
            "evidence_assessment_ids": [assessment],
        }, 201)["snapshot_id"]
        independent = self.assert_api(root + "/snapshots", {
            "question_id": qid,
            "summary": "Independent fictional imaging review; prior comparison remains pending.",
            "source_ids": [imaging["source_id"]],
        }, 201)["snapshot_id"]
        self.assert_api(root + f"/snapshots/{linked}/review",
                        {"reviewer_label": "Demo-only reviewer"}, 200)
        status, exported = self.api(root + f"/snapshots/{linked}/export")
        self.assertEqual(status, 200)
        self.assertIn("EVID-ASSAY@1", exported)
        self.assertIn("FICTIONAL", exported.upper())

        replay = self.assert_api(root + "/investigations", {
            "question_id": qid, "template": "evidence-summary", "mode": "replay",
        }, 201)
        self.assertEqual(replay["model"], "recorded-replay")
        self.assertEqual(replay["kind"], "hypothesis")
        self.assertEqual(replay["review_state"], "pending")
        self.assertTrue(replay["claims"])
        self.assertEqual(self.api("/api/bibliography/status")[1]["live_enabled"], False)

        corrected = self.assert_api(root + "/imports",
            {"text": self.fixture("alpha-pathology-amended.txt")}, 200)
        self.assertIn(linked, corrected["invalidated_snapshots"])
        self.assertNotIn(independent, corrected["invalidated_snapshots"])
        updated = self.api(root + "/state")[1]
        snapshots = {s["id"]: s for s in updated["snapshots"]}
        self.assertEqual(snapshots[linked]["state"], "stale")
        self.assertEqual(snapshots[independent]["state"], "draft")
        self.assertEqual(next(q for q in updated["questions"] if q["id"] == qid)["state"], "open")
        latest = {a["finding_key"]: a["certainty"] for a in updated["assertions"]}
        self.assertEqual(latest["marker-a"], "negative")
        old_source = self.api(root + f"/sources/{pathology['source_id']}")[1]["text"]
        self.assertIn("not tested in this specimen", old_source)
        self.assertEqual(self.api(root + f"/snapshots/{linked}/review",
                                  {"reviewer_label": "Demo-only reviewer"})[0], 422)
        self.assertEqual(self.api(beta + "/state")[1]["sources"][0]["state"], "current")

        # A fresh independent SQLite connection proves the state was stored.
        with CaseStore(self.db_path) as reopened:
            historical = {s["id"]: s for s in reopened.state("CASE-ALPHA")["snapshots"]}
            self.assertEqual(historical[linked]["state"], "stale")
            self.assertEqual(historical[independent]["state"], "draft")
            self.assertEqual(reopened.state("CASE-BETA")["case"]["case_id"], "CASE-BETA")


if __name__ == "__main__":
    unittest.main()
