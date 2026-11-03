import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import Handler, seed

ROOT = Path(__file__).resolve().parents[1]
RECORDED_LABEL = "recorded date — not a clinical due date"
MISSING_SOURCE = "no source recorded"

GOOD_TYPE = "Fictional follow-up"
GOOD_NOTES = "The fictional chart notes a brief visit in May; the clerk filed the page."
GOOD_ANCHOR = "intake sheet p. 2"

# One directive/prescriptive probe per listed family. Each must be rejected
# in every author-controlled text field.
DIRECTIVE_PROBES = [
    "The visitor should return soon.",
    "The chart must note the visit.",
    "They need to come back in June.",
    "Please order a scan next time.",
    "Plan to start treatment in June.",
    "Plan to stop treatment in June.",
    "They were told to seek care.",
    "Watch for fever after the visit.",
    "The approach was effective.",
    "A proven method was used here.",
    "There was clear benefit noted.",
    "The team recommends therapy.",
]


class VisitRecordStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "test.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_record_amend_history_shows_both_versions_in_order(self):
        created = self.store.record_visit(
            "CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES, GOOD_ANCHOR)
        self.assertEqual(created["version"], 1)
        amended = self.store.amend_visit(
            "CASE-ALPHA", created["visit_id"], "2026-05-04",
            "Fictional chart correction",
            "The fictional clerk corrected the filing date; the earlier page is kept.",
            "correction slip p. 1")
        self.assertEqual(amended["version"], 2)
        self.assertEqual(amended["visit_id"], created["visit_id"])
        self.assertEqual(amended["supersedes_id"], created["version_id"])

        listing = self.store.list_visits("CASE-ALPHA")
        self.assertEqual(len(listing["visits"]), 1)
        entry = listing["visits"][0]
        history = entry["history"]
        self.assertEqual([v["version"] for v in history], [1, 2])
        self.assertEqual([v["state"] for v in history], ["superseded", "current"])
        self.assertIsNone(history[0]["previous_id"])
        self.assertEqual(history[1]["previous_id"], history[0]["id"])
        # Old wording survives untouched; current points at the new version.
        self.assertEqual(history[0]["notes"], GOOD_NOTES)
        self.assertEqual(entry["current"]["id"], history[1]["id"])
        self.assertEqual(entry["current"]["recorded_date"], "2026-05-04")
        for version in history:
            self.assertEqual(version["review_state"], "recorded")
            self.assertEqual(version["recorded_date_label"], RECORDED_LABEL)

    def test_directive_wording_rejected_in_every_text_field(self):
        for probe in DIRECTIVE_PROBES:
            with self.subTest(field="visit_type", probe=probe):
                with self.assertRaisesRegex(InvalidInput, "descriptive history only"):
                    self.store.record_visit("CASE-ALPHA", "2026-05-03", probe, GOOD_NOTES)
            with self.subTest(field="notes", probe=probe):
                with self.assertRaisesRegex(InvalidInput, "descriptive history only"):
                    self.store.record_visit("CASE-ALPHA", "2026-05-03", GOOD_TYPE, probe)
            with self.subTest(field="source_anchor", probe=probe):
                with self.assertRaisesRegex(InvalidInput, "descriptive history only"):
                    self.store.record_visit(
                        "CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES, probe)
        # The guard also applies to amendments, not just first records.
        created = self.store.record_visit(
            "CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES)
        with self.assertRaisesRegex(InvalidInput, "descriptive history only"):
            self.store.amend_visit(
                "CASE-ALPHA", created["visit_id"], "2026-05-04",
                GOOD_TYPE, "The visitor should return soon.")
        history = self.store.list_visits("CASE-ALPHA")["visits"][0]["history"]
        self.assertEqual(len(history), 1)
        # Past-tense history stays writable: it describes, never directs.
        allowed = self.store.record_visit(
            "CASE-ALPHA", "2026-05-05", GOOD_TYPE,
            "Labs were ordered and the visit started at noon, per the fictional page.")
        self.assertEqual(allowed["version"], 1)

    def test_missing_source_anchor_allowed_and_labelled(self):
        without = self.store.record_visit(
            "CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES)
        blank = self.store.record_visit(
            "CASE-ALPHA", "2026-05-04", GOOD_TYPE, GOOD_NOTES, "   ")
        with_anchor = self.store.record_visit(
            "CASE-ALPHA", "2026-05-05", GOOD_TYPE, GOOD_NOTES, GOOD_ANCHOR)
        by_id = {v["visit_id"]: v["current"]
                 for v in self.store.list_visits("CASE-ALPHA")["visits"]}
        self.assertIsNone(by_id[without["visit_id"]]["source_anchor"])
        self.assertEqual(by_id[without["visit_id"]]["source_display"], MISSING_SOURCE)
        self.assertIsNone(by_id[blank["visit_id"]]["source_anchor"])
        self.assertEqual(by_id[blank["visit_id"]]["source_display"], MISSING_SOURCE)
        self.assertEqual(by_id[with_anchor["visit_id"]]["source_anchor"], GOOD_ANCHOR)
        self.assertEqual(by_id[with_anchor["visit_id"]]["source_display"], GOOD_ANCHOR)

    def test_amending_one_visit_changes_no_other_record(self):
        first = self.store.record_visit(
            "CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES)
        second = self.store.record_visit(
            "CASE-ALPHA", "2026-05-04", "Fictional intake",
            "The fictional intake page was filed; nothing further was added.")
        before = {v["visit_id"]: v for v in self.store.list_visits("CASE-ALPHA")["visits"]}
        self.store.amend_visit(
            "CASE-ALPHA", first["visit_id"], "2026-05-06",
            "Fictional chart correction",
            "The fictional clerk corrected the first page; the earlier text is kept.")
        after = {v["visit_id"]: v for v in self.store.list_visits("CASE-ALPHA")["visits"]}
        # The untouched visit keeps its single current version byte-for-byte.
        self.assertEqual(after[second["visit_id"]]["history"],
                         before[second["visit_id"]]["history"])
        self.assertEqual(after[second["visit_id"]]["current"],
                         before[second["visit_id"]]["current"])
        self.assertEqual(len(after[first["visit_id"]]["history"]), 2)
        self.assertEqual(len(after[second["visit_id"]]["history"]), 1)

    def test_case_isolation_and_unknown_case(self):
        created = self.store.record_visit(
            "CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES)
        self.assertEqual(self.store.list_visits("CASE-BETA")["visits"], [])
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.amend_visit(
                "CASE-BETA", created["visit_id"], "2026-05-04", GOOD_TYPE, GOOD_NOTES)
        for unknown in ("CASE-NOPE",):
            with self.assertRaisesRegex(InvalidInput, "Unknown case"):
                self.store.record_visit(unknown, "2026-05-03", GOOD_TYPE, GOOD_NOTES)
            with self.assertRaisesRegex(InvalidInput, "Unknown case"):
                self.store.amend_visit(unknown, 1, "2026-05-03", GOOD_TYPE, GOOD_NOTES)
            with self.assertRaisesRegex(InvalidInput, "Unknown case"):
                self.store.list_visits(unknown)
        # Failed cross-case and unknown-case writes left no trace.
        self.assertEqual(len(self.store.list_visits("CASE-ALPHA")["visits"]), 1)
        self.assertEqual(self.store.list_visits("CASE-BETA")["visits"], [])

    def test_visit_writes_touch_no_investigation_or_source_state(self):
        self.store.add_question("CASE-ALPHA", "What does the fictional chart note?")
        before = self.store.state("CASE-ALPHA")
        created = self.store.record_visit(
            "CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES)
        self.store.amend_visit(
            "CASE-ALPHA", created["visit_id"], "2026-05-04",
            "Fictional chart correction",
            "The fictional clerk corrected the filing date; the earlier page is kept.")
        after = self.store.state("CASE-ALPHA")
        for key in ("sources", "assertions", "questions", "snapshots",
                    "evidence_assessments", "options"):
            self.assertEqual(after[key], before[key])

    def test_recorded_date_label_present_in_json_payload(self):
        self.store.record_visit("CASE-ALPHA", "2026-05-03", GOOD_TYPE, GOOD_NOTES)
        listing = self.store.list_visits("CASE-ALPHA")
        self.assertEqual(listing["recorded_date_label"], RECORDED_LABEL)
        self.assertIn(RECORDED_LABEL, json.dumps(listing, ensure_ascii=False))
        self.assertNotIn("due date", listing["visits"][0]["current"]["recorded_date"])
        with self.assertRaisesRegex(InvalidInput, "YYYY-MM-DD"):
            self.store.record_visit("CASE-ALPHA", "May 3rd", GOOD_TYPE, GOOD_NOTES)


class VisitRecordHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerForVisitsTest", (Handler,), {"db_path": cls.path})
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
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers=values)
        try:
            with urlopen(req, timeout=5) as response:
                body = response.read()
                ctype = response.headers.get("Content-Type", "")
                return response.status, json.loads(body) if "json" in ctype else body
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_visit_routes_record_amend_list_with_history(self):
        status, created = self.request("/api/cases/CASE-ALPHA/visits", {
            "recorded_date": "2026-05-03", "visit_type": GOOD_TYPE,
            "notes": GOOD_NOTES})
        self.assertEqual(status, 201)
        status, amended = self.request(
            f"/api/cases/CASE-ALPHA/visits/{created['visit_id']}/amend", {
                "recorded_date": "2026-05-04", "visit_type": "Fictional chart correction",
                "notes": "The fictional clerk corrected the filing date; the earlier page is kept."})
        self.assertEqual(status, 201)
        self.assertEqual(amended["version"], 2)
        status, listing = self.request("/api/cases/CASE-ALPHA/visits")
        self.assertEqual(status, 200)
        self.assertEqual(listing["recorded_date_label"], RECORDED_LABEL)
        self.assertIn(RECORDED_LABEL, json.dumps(listing, ensure_ascii=False))
        entry = next(v for v in listing["visits"] if v["visit_id"] == created["visit_id"])
        self.assertEqual([v["version"] for v in entry["history"]], [1, 2])
        self.assertEqual(entry["history"][0]["state"], "superseded")
        self.assertEqual(entry["current"]["state"], "current")
        self.assertEqual(entry["current"]["source_display"], MISSING_SOURCE)
        self.assertTrue(listing["synthetic"])

    def test_visit_routes_reject_directive_unknown_and_cross_case(self):
        status, error = self.request("/api/cases/CASE-ALPHA/visits", {
            "recorded_date": "2026-05-03", "visit_type": GOOD_TYPE,
            "notes": "The visitor should return soon."})
        self.assertEqual(status, 422)
        self.assertIn("descriptive history only", error["error"])
        status, error = self.request("/api/cases/CASE-NOPE/visits")
        self.assertEqual(status, 422)
        status, error = self.request("/api/cases/CASE-NOPE/visits", {
            "recorded_date": "2026-05-03", "visit_type": GOOD_TYPE, "notes": GOOD_NOTES})
        self.assertEqual(status, 422)
        status, created = self.request("/api/cases/CASE-ALPHA/visits", {
            "recorded_date": "2026-05-03", "visit_type": GOOD_TYPE, "notes": GOOD_NOTES})
        self.assertEqual(status, 201)
        status, error = self.request(
            f"/api/cases/CASE-BETA/visits/{created['visit_id']}/amend", {
                "recorded_date": "2026-05-04", "visit_type": GOOD_TYPE, "notes": GOOD_NOTES})
        self.assertEqual(status, 422)
        self.assertIn("not in this case", error["error"])
        status, error = self.request("/api/cases/CASE-ALPHA/visits/999999/amend", {
            "recorded_date": "2026-05-04", "visit_type": GOOD_TYPE, "notes": GOOD_NOTES})
        self.assertEqual(status, 422)
        self.assertIn("not in this case", error["error"])
        status, beta = self.request("/api/cases/CASE-BETA/visits")
        self.assertEqual(status, 200)
        self.assertNotIn(created["visit_id"], [v["visit_id"] for v in beta["visits"]])


class VisitRecordUiContractTests(unittest.TestCase):
    def test_case_view_contains_fictional_visits_panel(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn('href="#visits"', html)
        self.assertIn('id="visits"', html)
        self.assertIn('id="visit-list"', html)
        self.assertIn('id="visit-form"', html)
        self.assertIn('id="visit-date"', html)
        self.assertIn('id="visit-type"', html)
        self.assertIn('id="visit-notes"', html)
        self.assertIn('id="visit-anchor"', html)
        self.assertIn('id="visit-amend-form"', html)
        self.assertIn('id="visit-amend-choice"', html)
        self.assertIn('id="visit-amend-date"', html)
        self.assertIn('id="visit-amend-type"', html)
        self.assertIn('id="visit-amend-notes"', html)
        self.assertIn('id="visit-amend-anchor"', html)
        self.assertIn(RECORDED_LABEL, html)
        self.assertIn("FICTIONAL visit records", html)
        self.assertIn("Amend a visit (preserves history)", html)
        self.assertIn("no source recorded", html)

    def test_renderer_is_case_scoped_source_safe_and_labelled(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn("/api/cases/' + requested + '/visits", javascript)
        self.assertIn("renderVisits", javascript)
        self.assertIn("loadVisits", javascript)
        self.assertIn("clear('visit-list')", javascript)
        self.assertIn("'visit-notes'", javascript)
        self.assertIn("'visit-amend-notes'", javascript)
        self.assertIn("'visit-date'", javascript)
        self.assertIn("'visit-anchor'", javascript)
        self.assertIn(RECORDED_LABEL, javascript)
        self.assertIn("no source recorded", javascript)
        # Guards below are scoped to the new visits code, so each fails
        # without the feature (the marker lookup itself raises first).
        load_start = javascript.index("async function loadVisits")
        render_start = javascript.index("function renderVisits")
        render_end = javascript.index("function render()", render_start)
        loader = javascript[load_start:render_start]
        self.assertIn("requested !== caseId", loader)
        renderer = javascript[render_start:render_end]
        self.assertIn("textContent", renderer)
        self.assertNotIn("innerHTML", renderer)
        self.assertIn(RECORDED_LABEL, renderer)
        self.assertIn("no source recorded", renderer)
        record_at = javascript.index("el('visit-form')")
        record_handler = javascript[record_at:record_at + 2000]
        self.assertIn("readyCase()", record_handler)
        self.assertIn("requestedCase !== caseId", record_handler)
        amend_at = javascript.index("el('visit-amend-form')")
        amend_handler = javascript[amend_at:amend_at + 2000]
        self.assertIn("readyCase()", amend_handler)
        self.assertIn("requestedCase !== caseId", amend_handler)


if __name__ == "__main__":
    unittest.main()
