"""Case search and triage list: store, HTTP, and UI-contract checks.

Every assertion here must fail without the feature: the old /api/cases
ignores its query string and returns unenriched id-ordered rows, so any
check for filtering, recent ordering, counts, 422 on bad sort, or the
new UI surface fails against that baseline.
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
from open_intelligence.case_search import list_cases
from open_intelligence.store import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"

# Distinctive clinical text from the bundled fixtures. It must appear in
# per-case state (proving a leak would be detectable) and never in the
# list payload.
ALPHA_QUOTES = [
    "malignant epithelial neoplasm",
    "Marker A was not tested in this specimen.",
    "31 mm",
]
BETA_QUOTES = [
    "indeterminate finding requiring additional review",
    "Marker A testing was not assessed for this sample.",
]


def report(name):
    return (SAMPLE / name).read_bytes()


def expected_counts(store, case_id):
    state = store.state(case_id)
    return {
        "sources": len([s for s in state["sources"] if s["state"] == "current"]),
        "open_questions": len([q for q in state["questions"] if q["state"] == "open"]),
        "pending_reviews": len([s for s in state["snapshots"] if s["state"] == "draft"]),
        "overdue_follow_ups": 0,
    }


class CaseSearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "search.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        self.store.import_report("CASE-BETA", report("beta-pathology.txt"))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_search_id_substring_returns_only_matching_case(self):
        for needle in ("ALPHA", "alpha", "AlPhA", "PHA"):
            with self.subTest(needle=needle):
                result = list_cases(self.store, search=needle, sort="id")
                self.assertEqual([c["case_id"] for c in result], ["CASE-ALPHA"])
                self.assertEqual(result[0]["label"], "Fictional case Alpha")
                self.assertEqual(result[0]["counts"], expected_counts(self.store, "CASE-ALPHA"))

    def test_search_label_substring_is_case_insensitive(self):
        result = list_cases(self.store, search="case beta", sort="id")
        self.assertEqual([c["case_id"] for c in result], ["CASE-BETA"])
        both = list_cases(self.store, search="Fictional case", sort="id")
        self.assertEqual([c["case_id"] for c in both], ["CASE-ALPHA", "CASE-BETA"])

    def test_empty_search_returns_all_sorted_by_id(self):
        for needle in ("", "   "):
            with self.subTest(needle=repr(needle)):
                result = list_cases(self.store, search=needle, sort="id")
                self.assertEqual([c["case_id"] for c in result], ["CASE-ALPHA", "CASE-BETA"])
                for item in result:
                    self.assertEqual(item["counts"], expected_counts(self.store, item["case_id"]))
                    self.assertIsNotNone(item["created_at"])
                    self.assertIsNotNone(item["last_activity_at"])

    def test_no_match_returns_empty_never_error(self):
        result = list_cases(self.store, search="zzz-no-such-case-123", sort="id")
        self.assertEqual(result, [])
        result = list_cases(self.store, search="zzz-no-such-case-123", sort="recent")
        self.assertEqual(result, [])

    def test_search_treats_wildcards_literally(self):
        for needle in ("%", "_", "%_%", "CASE-%", "ALPHA_"):
            with self.subTest(needle=needle):
                result = list_cases(self.store, search=needle, sort="id")
                self.assertEqual(result, [])

    def test_none_search_and_sort_use_safe_defaults(self):
        result = list_cases(self.store, search=None, sort=None)
        self.assertEqual([c["case_id"] for c in result], ["CASE-ALPHA", "CASE-BETA"])
        result = list_cases(self.store, search=None, sort="")
        self.assertEqual([c["case_id"] for c in result], ["CASE-ALPHA", "CASE-BETA"])

    def test_counts_match_per_case_state_exactly(self):
        qid = self.store.add_question("CASE-ALPHA", "What does the Alpha source report?")
        sid = self.store.state("CASE-ALPHA")["sources"][0]["id"]
        self.store.create_snapshot("CASE-ALPHA", qid, "A human-authored draft for count checks.", [sid])
        for case_id in ("CASE-ALPHA", "CASE-BETA"):
            with self.subTest(case_id=case_id):
                found = [c for c in list_cases(self.store, search="", sort="id") if c["case_id"] == case_id][0]
                self.assertEqual(found["counts"], expected_counts(self.store, case_id))
        alpha = [c for c in list_cases(self.store, search="ALPHA", sort="id")][0]
        self.assertEqual(alpha["counts"]["sources"], 2)
        self.assertEqual(alpha["counts"]["open_questions"], 1)
        self.assertEqual(alpha["counts"]["pending_reviews"], 1)
        self.assertEqual(alpha["counts"]["overdue_follow_ups"], 0)

    def test_counts_change_after_adding_question_to_one_case_only(self):
        before = {c["case_id"]: dict(c["counts"]) for c in list_cases(self.store, search="", sort="id")}
        self.store.add_question("CASE-ALPHA", "Which fictional finding needs a follow-up note?")
        after = {c["case_id"]: dict(c["counts"]) for c in list_cases(self.store, search="", sort="id")}
        self.assertEqual(after["CASE-ALPHA"]["open_questions"], before["CASE-ALPHA"]["open_questions"] + 1)
        self.assertEqual(after["CASE-BETA"], before["CASE-BETA"])
        self.assertEqual(after["CASE-ALPHA"]["sources"], before["CASE-ALPHA"]["sources"])
        self.assertEqual(after["CASE-ALPHA"]["pending_reviews"], before["CASE-ALPHA"]["pending_reviews"])

    def test_pending_counts_drafts_not_stale_history(self):
        qid = self.store.add_question("CASE-ALPHA", "What was reported about Marker A?")
        original = self.store.state("CASE-ALPHA")["sources"][0]["id"]
        draft = self.store.create_snapshot("CASE-ALPHA", qid, "Draft before amendment for review.", [original])
        pending = [c for c in list_cases(self.store, search="ALPHA", sort="id")][0]["counts"]["pending_reviews"]
        self.assertEqual(pending, 1)
        self.store.acknowledge_demo_review("CASE-ALPHA", draft, "Synthetic reviewer")
        pending = [c for c in list_cases(self.store, search="ALPHA", sort="id")][0]["counts"]["pending_reviews"]
        self.assertEqual(pending, 0)
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        alpha = [c for c in list_cases(self.store, search="ALPHA", sort="id")][0]
        # The stale snapshot stays history; the reopened question signals rework.
        self.assertEqual(alpha["counts"]["pending_reviews"], 0)
        self.assertEqual(alpha["counts"]["open_questions"], 1)

    def test_sort_recent_orders_by_latest_recorded_activity(self):
        # BETA's import is last in setUp, so BETA is most recent first.
        recent = [c["case_id"] for c in list_cases(self.store, search="", sort="recent")]
        self.assertEqual(recent, ["CASE-BETA", "CASE-ALPHA"])
        by_id = [c["case_id"] for c in list_cases(self.store, search="", sort="id")]
        self.assertEqual(by_id, ["CASE-ALPHA", "CASE-BETA"])
        self.store.add_question("CASE-ALPHA", "A new fictional question makes Alpha most recent?")
        recent = [c["case_id"] for c in list_cases(self.store, search="", sort="recent")]
        self.assertEqual(recent, ["CASE-ALPHA", "CASE-BETA"])
        # The payload exposes the activity behind the order for inspection.
        items = list_cases(self.store, search="", sort="recent")
        self.assertGreater(items[0]["last_activity_event_id"], items[1]["last_activity_event_id"])

    def test_list_payload_carries_zero_clinical_text(self):
        payload = list_cases(self.store, search="", sort="id")
        dumped = json.dumps(payload)
        for quote in ALPHA_QUOTES + BETA_QUOTES:
            with self.subTest(quote=quote[:24]):
                self.assertNotIn(quote, dumped)
        # The same quotes are present in per-case state, so absence is meaningful.
        alpha_state = json.dumps(self.store.state("CASE-ALPHA"))
        beta_state = json.dumps(self.store.state("CASE-BETA"))
        for quote in ALPHA_QUOTES:
            self.assertIn(quote, alpha_state)
        for quote in BETA_QUOTES:
            self.assertIn(quote, beta_state)
        for item in payload:
            self.assertEqual(
                set(item.keys()),
                {"case_id", "label", "created_at", "last_activity_at",
                 "last_activity_event_id", "synthetic", "counts"},
            )
            self.assertEqual(
                set(item["counts"].keys()),
                {"sources", "open_questions", "pending_reviews", "overdue_follow_ups"},
            )

    def test_search_never_leaks_other_case(self):
        self.store.add_question("CASE-BETA", "Beta-only fictional question about review?")
        result = list_cases(self.store, search="ALPHA", sort="id")
        self.assertEqual(len(result), 1)
        dumped = json.dumps(result)
        self.assertNotIn("CASE-BETA", dumped)
        self.assertNotIn("Beta-only fictional question", dumped)
        for quote in BETA_QUOTES:
            self.assertNotIn(quote, dumped)
        before = expected_counts(self.store, "CASE-ALPHA")
        self.store.add_question("CASE-BETA", "Another Beta-only fictional question here?")
        after = [c for c in list_cases(self.store, search="ALPHA", sort="id")][0]["counts"]
        self.assertEqual(after, before)

    def test_invalid_sort_is_rejected(self):
        with self.assertRaisesRegex(InvalidInput, "Sort must be recent or id"):
            list_cases(self.store, search="", sort="bogus")


class CaseSearchHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "search-http.sqlite")
        seed(cls.path)
        bound = type("BoundSearchHandlerForTest", (Handler,), {"db_path": cls.path})
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

    def request(self, path, data=None):
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers=headers)
        try:
            with urlopen(req, timeout=5) as response:
                body = response.read()
                ctype = response.headers.get("Content-Type", "")
                return response.status, json.loads(body) if "json" in ctype else body
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def state_counts(self, case_id):
        status, state = self.request(f"/api/cases/{case_id}/state")
        self.assertEqual(status, 200)
        return {
            "sources": len([s for s in state["sources"] if s["state"] == "current"]),
            "open_questions": len([q for q in state["questions"] if q["state"] == "open"]),
            "pending_reviews": len([s for s in state["snapshots"] if s["state"] == "draft"]),
            "overdue_follow_ups": 0,
        }

    def test_search_id_substring_returns_only_matching_case(self):
        status, items = self.request("/api/cases?search=ALPHA&sort=id")
        self.assertEqual(status, 200)
        self.assertEqual([c["case_id"] for c in items], ["CASE-ALPHA"])
        self.assertEqual(items[0]["counts"], self.state_counts("CASE-ALPHA"))
        dumped = json.dumps(items)
        for quote in ALPHA_QUOTES + BETA_QUOTES:
            self.assertNotIn(quote, dumped)
        status, state = self.request("/api/cases/CASE-ALPHA/state")
        self.assertIn(ALPHA_QUOTES[0], json.dumps(state))

    def test_empty_search_returns_all_enriched(self):
        status, items = self.request("/api/cases?search=&sort=id")
        self.assertEqual(status, 200)
        self.assertEqual([c["case_id"] for c in items], ["CASE-ALPHA", "CASE-BETA"])
        for item in items:
            self.assertEqual(item["counts"], self.state_counts(item["case_id"]))
            self.assertIn("created_at", item)
            self.assertIn("last_activity_at", item)

    def test_no_match_returns_empty_never_error(self):
        status, items = self.request("/api/cases?search=zzz-no-such-case-999&sort=id")
        self.assertEqual(status, 200)
        self.assertEqual(items, [])

    def test_label_substring_with_encoding_returns_only_matching_case(self):
        status, items = self.request("/api/cases?search=case%20beta&sort=id")
        self.assertEqual(status, 200)
        self.assertEqual([c["case_id"] for c in items], ["CASE-BETA"])

    def test_sort_recent_follows_latest_activity(self):
        status, by_id = self.request("/api/cases?search=&sort=id")
        self.assertEqual([c["case_id"] for c in by_id], ["CASE-ALPHA", "CASE-BETA"])
        status, _ = self.request("/api/cases/CASE-BETA/questions",
                                 {"question": "Which fictional Beta item is most recent now?"})
        self.assertEqual(status, 201)
        status, recent = self.request("/api/cases?search=&sort=recent")
        self.assertEqual(recent[0]["case_id"], "CASE-BETA")
        status, _ = self.request("/api/cases/CASE-ALPHA/questions",
                                 {"question": "Which fictional Alpha item is most recent now?"})
        self.assertEqual(status, 201)
        status, recent = self.request("/api/cases?search=&sort=recent")
        self.assertEqual(recent[0]["case_id"], "CASE-ALPHA")
        self.assertGreater(recent[0]["last_activity_event_id"], recent[1]["last_activity_event_id"])

    def test_counts_change_after_adding_question(self):
        status, before = self.request("/api/cases?search=&sort=id")
        before_map = {c["case_id"]: dict(c["counts"]) for c in before}
        status, created = self.request("/api/cases/CASE-ALPHA/questions",
                                       {"question": "Does the triage count track new questions?"})
        self.assertEqual(status, 201)
        status, after = self.request("/api/cases?search=&sort=id")
        after_map = {c["case_id"]: dict(c["counts"]) for c in after}
        self.assertEqual(after_map["CASE-ALPHA"]["open_questions"],
                         before_map["CASE-ALPHA"]["open_questions"] + 1)
        self.assertEqual(after_map["CASE-BETA"], before_map["CASE-BETA"])

    def test_invalid_sort_is_rejected(self):
        status, error = self.request("/api/cases?search=&sort=bogus")
        self.assertEqual(status, 422)
        self.assertIn("Sort must be", error["error"])


class CaseSearchUiContractTests(unittest.TestCase):
    def test_html_contains_search_surface(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn('href="#case-search"', html)
        self.assertIn('id="case-search"', html)
        self.assertIn('id="case-search-form"', html)
        self.assertIn('id="case-search-input"', html)
        self.assertIn('id="case-search-sort"', html)
        self.assertIn('id="case-search-list"', html)
        self.assertIn('id="case-search-count"', html)
        self.assertIn('<script src="/case_search.js" defer></script>', html)
        self.assertIn("FICTIONAL DEMO CASES ONLY", html)
        self.assertIn("not a clinical triage list", html)
        self.assertIn("Most recent activity first", html)
        self.assertIn("Case ID (A to Z)", html)

    def test_renderer_is_safe_list_scoped_and_refreshable(self):
        js = (ROOT / "web" / "case_search.js").read_text()
        self.assertIn("/api/cases?search=", js)
        self.assertIn("encodeURIComponent", js)
        self.assertIn("requestSequence", js)
        self.assertIn("MutationObserver", js)
        self.assertIn("textContent", js)
        self.assertIn("FICTIONAL", js)
        self.assertIn("Open this case", js)
        self.assertIn("Currently open", js)
        self.assertIn("No fictional cases match", js)
        self.assertIn('picker.dispatchEvent(new Event("change"))', js)
        self.assertNotIn("innerHTML", js)

    def test_server_serves_renderer_and_search_route(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()
        self.assertIn('if path == "/case_search.js":', server)
        self.assertIn('self._static("case_search.js", "text/javascript; charset=utf-8")', server)
        self.assertIn("from .case_search import list_cases", server)
        self.assertIn('query.get("search"', server)
        self.assertIn('query.get("sort"', server)


if __name__ == "__main__":
    unittest.main()
