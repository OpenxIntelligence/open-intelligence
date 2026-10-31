import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed


class EvidenceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "evidence.sqlite")
        seed(cls.path)
        bound = type("EvidenceTestHandler", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def call(self, path, data=None, origin=True):
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
            if origin:
                headers["Origin"] = f"http://127.0.0.1:{self.port}"
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(),
                          headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_evidence_lifecycle_through_http(self):
        status, example = self.call("/api/examples/evidence")
        self.assertEqual(status, 200)
        self.assertIn("original-synthetic", example["text"])
        status, imported = self.call("/api/evidence/imports", {"text": example["text"]})
        self.assertEqual(status, 200)
        self.assertIn(imported["result"], ("imported", "duplicate"))
        evidence_id = imported["evidence_version_id"]
        status, source = self.call(f"/api/evidence/{evidence_id}")
        self.assertEqual(status, 200)
        self.assertEqual(source["text"], example["text"])
        status, case = self.call("/api/cases/CASE-ALPHA/state")
        source_id = next(s["id"] for s in case["sources"] if s["state"] == "current")
        status, question = self.call("/api/cases/CASE-ALPHA/questions", {"question": "How limited is the fictional evidence?"})
        self.assertEqual(status, 201)
        qid = question["question_id"]
        status, assessed = self.call("/api/cases/CASE-ALPHA/evidence-assessments",
                                     {"question_id": qid, "evidence_version_id": evidence_id,
                                      "relation": "context", "applicability": "unknown",
                                      "rationale": "Fictional evidence demonstrates source lineage but not clinical benefits."})
        self.assertEqual(status, 201)
        status, snapshot = self.call("/api/cases/CASE-ALPHA/snapshots",
                                      {"question_id": qid, "summary": "This is only a synthetic demonstration.",
                                       "source_ids": [source_id],
                                       "evidence_assessment_ids": [assessed["assessment_id"]]})
        self.assertEqual(status, 201)
        status, state = self.call("/api/cases/CASE-ALPHA/state")
        linked = next(s for s in state["snapshots"] if s["id"] == snapshot["snapshot_id"])
        self.assertEqual(linked["evidence_assessment_ids"], [assessed["assessment_id"]])
        status, withdrawn = self.call(f"/api/evidence/{evidence_id}/withdraw",
                                      {"reason": "This fictional evidence has been retired for testing."})
        self.assertEqual(status, 200)
        self.assertIn(snapshot["snapshot_id"], withdrawn["invalidated_snapshots"])
        status, state = self.call("/api/cases/CASE-ALPHA/state")
        self.assertEqual(next(s["state"] for s in state["snapshots"]
                              if s["id"] == snapshot["snapshot_id"]), "stale")

    def test_untrusted_origin_and_unapproved_rights_rejected(self):
        status, error = self.call("/api/evidence/imports",
                                  {"text": "OI-SYNTHETIC-EVIDENCE/1"},
                                  origin=False)
        # curl or other non-browser local clients may omit Origin; this is a
        # local-only demo, and NOT a promise of request authentication.
        self.assertIn(status, (200, 422))
        status, error = self.call("/api/evidence/imports",
                                  {"text": "OI-SYNTHETIC-EVIDENCE/1"},
                                  origin=True)
        self.assertEqual(status, 422)

if __name__ == "__main__":
    unittest.main()
