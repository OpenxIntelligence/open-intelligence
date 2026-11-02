import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from open_intelligence.__main__ import Handler, seed


class TimelineHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerForTimelineTest", (Handler,), {"db_path": cls.path})
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

    def test_timeline_route(self):
        status, data = self.request("/api/cases/CASE-ALPHA/timeline")
        self.assertEqual(status, 200)
        self.assertTrue(data["synthetic"])
        self.assertIn("Fictional synthetic data only", data["disclaimer"])
        self.assertEqual(data["counts"]["entries"], 2)
        self.assertEqual([e["document_id"] for e in data["entries"]],
                         ["PATH-ALPHA", "IMG-ALPHA"])
        self.assertEqual(data["counts"]["gaps"], 1)
        self.assertEqual(data["counts"]["conflicts"], 0)
        status, beta = self.request("/api/cases/CASE-BETA/timeline")
        self.assertEqual(status, 200)
        self.assertEqual(beta["counts"]["entries"], 1)
        self.assertEqual(beta["counts"]["gaps"], 0)

    def test_timeline_route_errors(self):
        status, _ = self.request("/api/cases/CASE-NOPE/timeline")
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
