"""World Model browser script is actually served by the existing local app.

These tests use an empty fictional SQLite store and loopback HTTP only.
No real patient input, network research service or clinical authorization.
"""
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from open_intelligence.__main__ import Handler
from open_intelligence.store import CaseStore


class WorldModelAssetDeliveryTests(unittest.TestCase):
    def test_world_model_script_is_served_by_existing_local_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "synthetic.sqlite")
            store = CaseStore(db)
            store.close()
            bound = type("WorldModelAssetHandler", (Handler,), {
                "db_path": db, "allow_crossref_live": False,
                "log_message": lambda self, *args: None,
            })
            server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                root = f"http://127.0.0.1:{server.server_port}"
                with urlopen(root + "/", timeout=8) as page:
                    html = page.read().decode("utf-8")
                    self.assertEqual(page.status, 200)
                    self.assertIn('src="/world-model.js"', html)
                with urlopen(root + "/world-model.js", timeout=8) as asset:
                    code = asset.read().decode("utf-8")
                    self.assertEqual(asset.status, 200)
                    self.assertIn("text/javascript", asset.headers["Content-Type"])
                    self.assertEqual(asset.headers.get("Cache-Control"), "no-store")
                    self.assertIn("Draft question from this source", code)
                    self.assertIn("question-text", code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
