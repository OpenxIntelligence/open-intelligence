import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed


class ChangesHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerForChangesTest", (Handler,), {"db_path": cls.path})
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

    def request(self, path):
        try:
            with urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_changes_route_and_anchor_param(self):
        status, data = self.request("/api/cases/CASE-ALPHA/changes-since-review")
        self.assertEqual(status, 200)
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["anchor"]["kind"], "case_created")
        self.assertEqual(data["counts"]["new_sources"], 2)
        status, state = self.request("/api/cases/CASE-ALPHA/state")
        event_id = state["events"][-1]["id"]
        status, anchored = self.request(
            f"/api/cases/CASE-ALPHA/changes-since-review?since_event_id={event_id}")
        self.assertEqual(status, 200)
        self.assertEqual(anchored["anchor"]["event_id"], event_id)

    def test_changes_route_errors(self):
        status, data = self.request("/api/cases/CASE-NOPE/changes-since-review")
        self.assertEqual(status, 422)
        status, data = self.request("/api/cases/CASE-ALPHA/changes-since-review?since_event_id=abc")
        self.assertEqual(status, 422)
        status, data = self.request("/api/cases/CASE-ALPHA/changes-since-review?since_event_id=999999")
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
