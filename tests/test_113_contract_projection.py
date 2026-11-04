"""Issue 113 contract projection tests.

Maps legacy journeys to API read projections on clean main, without
changing any legacy file or application behavior. Fictional data only,
via the existing seed() fixture.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed

FULL_PERMS = {
    "metadata": {"store": "allowed", "display": "allowed"},
    "full_text": {"store": "allowed", "display": "allowed"},
}


class ContractProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerFor113Contract", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, payload=None):
        url = f"http://127.0.0.1:{self.port}{path}"
        headers = {"X-Fictional-Actor": "FICTIONAL-NAVIGATOR-A"}
        if payload is None:
            req = Request(url, headers=headers)
        else:
            req = Request(url, data=json.dumps(payload).encode(), method="POST",
                          headers={"Content-Type": "application/json", **headers})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_store_state_projection(self):
        status, data = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["sources"]), 2)

    def test_chronology_timeline_projection(self):
        status, data = self.request("/api/cases/CASE-ALPHA/timeline")
        self.assertEqual(status, 200)
        self.assertEqual(data["counts"]["entries"], 2)
        self.assertEqual([e["document_id"] for e in data["entries"]],
                         ["PATH-ALPHA", "IMG-ALPHA"])

    def test_amendment_changes_projection(self):
        status, data = self.request("/api/cases/CASE-ALPHA/changes-since-review")
        self.assertEqual(status, 200)
        self.assertEqual(data["anchor"]["kind"], "case_created")
        self.assertEqual(data["counts"]["new_sources"], 2)

    def test_rights_revoke_projection(self):
        status, data = self.request("/api/rights/sources", {
            "source_key": "EXT-113-1", "owner": "Fictional Archive",
            "version_label": "v1", "retrieved_at": "2026-01-15",
            "permissions": FULL_PERMS})
        self.assertEqual(status, 201)
        rid = data["rights_source_id"]
        status, data = self.request("/api/cases/CASE-ALPHA/questions",
                                    {"question": "What do the sources report?"})
        qid = data["question_id"]
        status, data = self.request("/api/cases/CASE-ALPHA/broker-links", {
            "question_id": qid, "rights_source_id": rid, "relation": "context",
            "applicability": "unknown",
            "rationale": "Human review notes the limits of this source."})
        self.assertEqual(status, 201)
        status, _ = self.request(f"/api/rights/sources/{rid}/revoke",
                                 {"reason": "Rights withdrawn by the fictional archive."})
        self.assertEqual(status, 200)
        status, _ = self.request("/api/cases/CASE-ALPHA/broker-links", {
            "question_id": qid, "rights_source_id": rid, "relation": "context",
            "applicability": "unknown",
            "rationale": "Human review notes the limits of this source."})
        self.assertEqual(status, 422)

    def test_unknown_case_projections_fail_closed(self):
        for path in ("/api/cases/CASE-NOPE/state",
                     "/api/cases/CASE-NOPE/timeline",
                     "/api/cases/CASE-NOPE/changes-since-review"):
            status, _ = self.request(path)
            self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
