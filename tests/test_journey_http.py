"""Journey HTTP routes + case-view surface contract.

Server checks run against a seeded local demo server. UI checks read the
shipped HTML/JS without a browser: they pin the reachable section, the
plain-language disclaimer, and the append-only rendering path.
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

ROOT = Path(__file__).resolve().parents[1]


class JourneyHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "journey-http.sqlite")
        seed(cls.path)
        bound_handler = type("BoundJourneyHandlerForTest", (Handler,), {"db_path": cls.path})
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

    def request(self, path, data=None):
        values = {"Content-Type": "application/json"} if data is not None else {}
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(),
                          headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                content = response.read()
                kind = response.headers.get("Content-Type", "")
                return response.status, json.loads(content) if "json" in kind else content
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_journey_round_trip_preserves_history(self):
        status, empty = self.request("/api/cases/CASE-BETA/journey")
        self.assertEqual(status, 200)
        self.assertIsNone(empty["current_stage"])
        self.assertEqual(empty["transitions"], [])

        status, first = self.request("/api/cases/CASE-BETA/journey-transitions", {
            "to_stage": "diagnosis",
            "reason": "the fictional intake paperwork is grouped here for review",
            "transition_date": "2026-05-06",
            "triggering_source_version_id": None,
        })
        self.assertEqual(status, 201)
        self.assertIsInstance(first["transition_id"], int)

        status, history = self.request("/api/cases/CASE-BETA/journey")
        self.assertEqual(status, 200)
        self.assertEqual(history["current_stage"], "diagnosis")
        self.assertEqual(len(history["transitions"]), 1)
        self.assertIn("descriptive labels", history["disclaimer"])

        status, second = self.request("/api/cases/CASE-BETA/journey-transitions", {
            "to_stage": "treatment",
            "reason": "the fictional care paperwork is now grouped with active notes",
            "transition_date": "2026-06-02",
            "triggering_source_version_id": None,
        })
        self.assertEqual(status, 201)

        status, grown = self.request("/api/cases/CASE-BETA/journey")
        self.assertEqual(grown["current_stage"], "treatment")
        self.assertEqual(len(grown["transitions"]), 2)
        # The first record is unchanged by the second append.
        self.assertEqual(grown["transitions"][0]["id"], first["transition_id"])
        self.assertEqual(grown["transitions"][0]["to_stage"], "diagnosis")
        self.assertEqual(grown["transitions"][1]["id"], second["transition_id"])

        status, state = self.request("/api/cases/CASE-BETA/state")
        self.assertEqual(status, 200)
        self.assertEqual(state["journey_current"], "treatment")
        self.assertEqual(len(state["journey_transitions"]), 2)

    def test_journey_rejects_unknown_stage_and_unknown_case(self):
        status, error = self.request("/api/cases/CASE-ALPHA/journey-transitions", {
            "to_stage": "remission",
            "reason": "a fictional reason long enough to pass length checks",
            "transition_date": "2026-05-06",
        })
        self.assertEqual(status, 422)
        self.assertIn("Unknown journey stage", error["error"])

        status, error = self.request("/api/cases/CASE-UNKNOWN/journey")
        self.assertEqual(status, 422)
        self.assertEqual(error["error"], "Unknown case")


class JourneyUiContractTests(unittest.TestCase):
    def test_case_view_contains_reachable_journey_surface(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn('href="#journey"', html)
        self.assertIn('id="journey"', html)
        self.assertIn('id="journey-current"', html)
        self.assertIn('id="journey-list"', html)
        self.assertIn('id="journey-form"', html)
        self.assertIn('id="journey-to-stage"', html)
        self.assertIn('id="journey-date"', html)
        self.assertIn('id="journey-reason"', html)
        self.assertIn('id="journey-source-choice"', html)
        self.assertIn("FICTIONAL ORGANIZING LABELS ONLY", html)
        self.assertIn("descriptive labels for organizing this fictional record", html)
        self.assertIn("never rewrites an earlier one", html)
        self.assertIn("Diagnosis (organizing label)", html)
        self.assertIn("Advanced disease (organizing label)", html)

    def test_renderer_is_case_scoped_and_text_safe(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn("function renderJourney()", javascript)
        self.assertIn("/journey-transitions", javascript)
        self.assertIn("journey-reason", javascript)
        self.assertIn("triggering_source_label", javascript)
        self.assertIn("textContent", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_server_exposes_additive_journey_routes(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()
        self.assertIn('/journey"', server)
        self.assertIn("/journey-transitions", server)
        self.assertIn("journey_history", server)
        self.assertIn("record_journey_transition", server)


if __name__ == "__main__":
    unittest.main()
