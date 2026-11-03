"""Whole-journey timeline slice: store projection, HTTP routes, UI contract.

Additive to the existing source-chronology timeline (``timeline.py``),
which stays untouched. This slice projects ledger events oldest-first:
fictional imports, amendments, questions, drafts, demo reviews,
quarantine, and status changes. Superseded entries stay visible with a
pointer to the newer entry; history is never hidden.

Each test here fails without the journey feature: the store tests
import ``journey.case_journey``, the HTTP tests request ``/journey``
and ``/timeline?view=journey`` (404 without the routes), and the UI
contract tests look for journey ids and strings absent from the base UI.
"""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.journey import case_journey
from open_intelligence.store import CaseStore, InvalidInput

SYNTHETIC = Path(__file__).resolve().parents[1] / "examples" / "synthetic"
ROOT = Path(__file__).resolve().parents[1]


def _seed_alpha(store):
    store.add_case("CASE-ALPHA", "Fictional case Alpha")
    store.import_report(
        "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes()
    )
    store.import_report(
        "CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes()
    )


def _full_journey(store):
    """Imports, then an amendment, then question/draft/review in order."""
    _seed_alpha(store)
    store.import_report(
        "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes()
    )
    question_id = store.add_question(
        "CASE-ALPHA", "Which fictional findings need reconciliation next?"
    )
    current = [
        s["id"] for s in store.state("CASE-ALPHA")["sources"] if s["state"] == "current"
    ]
    snapshot_id = store.create_snapshot(
        "CASE-ALPHA",
        question_id,
        "Reported observations:\nFictional pathology and imaging recorded.",
        current,
    )
    store.acknowledge_demo_review(
        "CASE-ALPHA", snapshot_id, "Synthetic reviewer (unverified)"
    )
    return question_id, snapshot_id


class JourneyStoreTests(unittest.TestCase):
    def test_seeded_imports_before_amendment_before_review_in_order(self):
        store = CaseStore(":memory:")
        _full_journey(store)
        result = case_journey(store, "CASE-ALPHA")
        kinds = [entry["kind"] for entry in result["entries"]]
        # Fails without the feature: no question/draft/review kinds exist in
        # the source-only timeline, and order would not include reviews.
        self.assertEqual(
            kinds, ["import", "import", "amendment", "question", "draft", "review"]
        )
        event_ids = [entry["event_id"] for entry in result["entries"]]
        self.assertEqual(event_ids, sorted(event_ids))
        self.assertEqual(result["count"], 6)
        self.assertEqual(result["counts"], {"entries": 6})

    def test_amendment_produces_superseding_entry_and_superseded_marker(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-ALPHA", "Fictional case Alpha")
        store.import_report(
            "CASE-ALPHA",
            (SYNTHETIC / "alpha-pathology-original.txt").read_bytes(),
        )
        store.import_report(
            "CASE-ALPHA",
            (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes(),
        )
        result = case_journey(store, "CASE-ALPHA")
        self.assertEqual(result["count"], 2)
        first, second = result["entries"]
        self.assertEqual(first["kind"], "import")
        self.assertEqual(first["status"], "superseded")
        self.assertEqual(first["source_ref"], "PATH-ALPHA@1")
        self.assertEqual(second["kind"], "amendment")
        self.assertEqual(second["status"], "current")
        self.assertEqual(second["source_ref"], "PATH-ALPHA@2")
        # Both directions of the supersession pointer must exist.
        self.assertEqual(second["supersedes_event_id"], first["event_id"])
        self.assertEqual(first["superseded_by_event_id"], second["event_id"])

    def test_superseded_history_never_hidden_after_draft_and_review(self):
        store = CaseStore(":memory:")
        _, snapshot_id = _full_journey(store)
        # A second amendment after review must keep every prior entry visible
        # while marking the dependent draft/review stale.
        amended = bytearray(
            (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes()
        )
        # Same bytes would be a duplicate; craft v3 by editing the quotation
        # only (event date, type, specimen unchanged per the contract).
        text = amended.decode().replace(
            "Amended fictional report refines",
            "Second fictional amendment refines",
        ).replace("Amends: PATH-ALPHA@1", "Amends: PATH-ALPHA@2")
        store.import_report("CASE-ALPHA", text.encode())
        result = case_journey(store, "CASE-ALPHA")
        kinds = [entry["kind"] for entry in result["entries"]]
        self.assertEqual(
            kinds,
            ["import", "import", "amendment", "question", "draft", "review", "amendment"],
        )
        by_snapshot = [
            e for e in result["entries"] if e.get("snapshot_id") == snapshot_id
        ]
        self.assertEqual(len(by_snapshot), 2)
        for entry in by_snapshot:
            self.assertEqual(entry["status"], "stale")
            self.assertIsNotNone(entry["superseded_by_event_id"])

    def test_each_entry_carries_time_description_kind_source_ref_and_status(self):
        store = CaseStore(":memory:")
        _full_journey(store)
        result = case_journey(store, "CASE-ALPHA")
        for entry in result["entries"]:
            for field in (
                "occurred_at",
                "description",
                "kind",
                "source_version_id",
                "source_ref",
                "source_version_ids",
                "source_refs",
                "status",
                "event_id",
                "fictional",
            ):
                self.assertIn(field, entry)
            self.assertTrue(entry["occurred_at"])
            self.assertTrue(entry["description"])
            self.assertTrue(entry["fictional"])
        imports = [e for e in result["entries"] if e["kind"] in ("import", "amendment")]
        self.assertTrue(imports)
        for entry in imports:
            self.assertIsNotNone(entry["source_version_id"])
            self.assertIsNotNone(entry["source_ref"])

    def test_case_isolation_beta_never_in_alpha(self):
        store = CaseStore(":memory:")
        _seed_alpha(store)
        store.add_case("CASE-BETA", "Fictional case Beta")
        store.import_report(
            "CASE-BETA", (SYNTHETIC / "beta-pathology.txt").read_bytes()
        )
        alpha = case_journey(store, "CASE-ALPHA")
        beta = case_journey(store, "CASE-BETA")
        alpha_text = json.dumps(alpha["entries"])
        beta_text = json.dumps(beta["entries"])
        self.assertNotIn("PATH-BETA", alpha_text)
        self.assertNotIn("PATH-ALPHA", beta_text)
        self.assertNotIn("IMG-ALPHA", beta_text)
        self.assertEqual(beta["count"], 1)
        self.assertEqual(beta["entries"][0]["source_ref"], "PATH-BETA@1")

    def test_empty_case_has_no_invented_entries(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-EMPTY", "Fictional empty case")
        result = case_journey(store, "CASE-EMPTY")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["counts"], {"entries": 0})

    def test_quarantine_entry_carries_no_source_and_stays_visible(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-ALPHA", "Fictional case Alpha")
        outcome = store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "wrong-patient.txt").read_bytes()
        )
        self.assertEqual(outcome["result"], "quarantined")
        result = case_journey(store, "CASE-ALPHA")
        self.assertEqual(result["count"], 1)
        entry = result["entries"][0]
        self.assertEqual(entry["kind"], "quarantine")
        self.assertEqual(entry["status"], "quarantined")
        self.assertIsNone(entry["source_version_id"])
        self.assertIsNone(entry["source_ref"])
        self.assertEqual(entry["source_version_ids"], [])
        self.assertIn("quarantined", entry["description"].lower())
        self.assertIn("No statements were imported", entry["description"])

    def test_unknown_case_raises(self):
        store = CaseStore(":memory:")
        _seed_alpha(store)
        with self.assertRaises(InvalidInput):
            case_journey(store, "CASE-NOPE")

    def test_purity_two_calls_identical_no_writes(self):
        store = CaseStore(":memory:")
        _full_journey(store)
        before = store.state("CASE-ALPHA")
        first = case_journey(store, "CASE-ALPHA")
        second = case_journey(store, "CASE-ALPHA")
        self.assertEqual(first, second)
        after = store.state("CASE-ALPHA")
        self.assertEqual(before["events"], after["events"])
        self.assertEqual(before["sources"], after["sources"])

    def test_fictional_labeling_and_no_clinical_inference(self):
        store = CaseStore(":memory:")
        _full_journey(store)
        result = case_journey(store, "CASE-ALPHA")
        self.assertTrue(result["synthetic"])
        self.assertIn("Fictional synthetic data only", result["disclaimer"])
        body = json.dumps(
            {key: value for key, value in result.items() if key != "disclaimer"}
        ).lower()
        for word in (
            "response",
            "progression",
            "staging",
            "grading",
            "eligibility",
            "efficacy",
            "treatment",
            "significan",
            "benefit",
            "improved",
            "worsened",
        ):
            self.assertNotIn(word, body)
        self.assertIn("fictional", body)


class JourneyHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound = type("BoundHandlerForJourneyTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
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

    def test_journey_route_returns_entries_oldest_first_plus_count(self):
        status, data = self.request("/api/cases/CASE-ALPHA/journey")
        self.assertEqual(status, 200)
        self.assertTrue(data["synthetic"])
        self.assertIn("Fictional synthetic data only", data["disclaimer"])
        # Seeded Alpha has two imports and nothing else yet: oldest-first.
        self.assertEqual(data["count"], 2)
        self.assertEqual(
            [entry["source_ref"] for entry in data["entries"]],
            ["PATH-ALPHA@1", "IMG-ALPHA@1"],
        )
        self.assertEqual(
            [entry["kind"] for entry in data["entries"]], ["import", "import"]
        )
        event_ids = [entry["event_id"] for entry in data["entries"]]
        self.assertEqual(event_ids, sorted(event_ids))

    def test_journey_route_is_case_isolated(self):
        status, alpha = self.request("/api/cases/CASE-ALPHA/journey")
        self.assertEqual(status, 200)
        status, beta = self.request("/api/cases/CASE-BETA/journey")
        self.assertEqual(status, 200)
        self.assertEqual(beta["count"], 1)
        self.assertEqual(beta["entries"][0]["source_ref"], "PATH-BETA@1")
        self.assertNotIn("PATH-BETA", json.dumps(alpha["entries"]))
        self.assertNotIn("PATH-ALPHA", json.dumps(beta["entries"]))

    def test_journey_route_unknown_case_is_422(self):
        status, _ = self.request("/api/cases/CASE-NOPE/journey")
        self.assertEqual(status, 422)

    def test_timeline_journey_view_matches_journey_route(self):
        status, direct = self.request("/api/cases/CASE-ALPHA/journey")
        self.assertEqual(status, 200)
        status, view = self.request("/api/cases/CASE-ALPHA/timeline?view=journey")
        self.assertEqual(status, 200)
        # Fails without the feature: the base timeline ignores the query and
        # returns source-chronology keys (gaps/conflicts/history), never a
        # journey count with import kinds.
        self.assertEqual(view, direct)
        self.assertEqual(view["count"], 2)
        self.assertEqual(
            [entry["kind"] for entry in view["entries"]], ["import", "import"]
        )

    def test_timeline_journey_view_unknown_case_is_422(self):
        status, _ = self.request("/api/cases/CASE-NOPE/timeline?view=journey")
        self.assertEqual(status, 422)

    def test_timeline_unknown_view_is_422(self):
        status, _ = self.request("/api/cases/CASE-ALPHA/timeline?view=nope")
        # Fails without the feature: the base route ignores unknown queries
        # and returns 200 with the source chronology.
        self.assertEqual(status, 422)


class JourneyUiContractTests(unittest.TestCase):
    def test_markup_contains_whole_journey_panel(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn('href="#journey"', html)
        self.assertIn('id="journey"', html)
        self.assertIn('id="journey-list"', html)
        self.assertIn('id="journey-count"', html)
        self.assertIn("Whole-journey timeline", html)
        # The FICTIONAL banner must be inside the journey panel itself:
        # without the slice, the panel is absent and the lookup fails.
        start = html.index('id="journey"')
        snippet = html[start : start + 2000]
        self.assertIn("FICTIONAL DEMO DATA", snippet)

    def test_renderer_fetches_journey_guards_cases_and_labels_fiction(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        # Each of these strings is absent without the slice.
        self.assertIn("/api/cases/' + requested + '/journey", javascript)
        self.assertIn("renderJourney", javascript)
        self.assertIn("loadJourney", javascript)
        self.assertIn("No timeline entries recorded yet", javascript)
        self.assertIn("pill('FICTIONAL'", javascript)
        self.assertIn("clear('journey-list')", javascript)
        # Guards must live inside the journey loader itself: without the
        # slice, the loader is absent and the lookup fails the test.
        start = javascript.index("async function loadJourney")
        snippet = javascript[start : start + 2000]
        self.assertIn("requested !== caseId", snippet)
        self.assertIn("active.case.case_id !== requested", snippet)
        self.assertIn("clear('journey-list')", snippet)

    def test_journey_rendering_uses_text_content_only(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        start = javascript.index("function renderJourney")
        snippet = javascript[start : start + 4000]
        # The journey renderer must exist (fails without the feature) and
        # must build items through the textContent helper, never innerHTML.
        self.assertIn("textContent", snippet + javascript[:2000])
        self.assertIn("node('li'", snippet)
        self.assertIn("node('p'", snippet)
        self.assertNotIn("innerHTML", snippet)


if __name__ == "__main__":
    unittest.main()
