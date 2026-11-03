import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.provenance import case_provenance
from open_intelligence.store import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC = ROOT / "examples" / "synthetic"


def _report(patient, document, event_date, issued_at, findings,
             specimen=None, amends=None, kind="pathology"):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", f"Type: {kind}",
             f"Event-Date: {event_date}", f"Issued-At: {issued_at}"]
    if specimen is not None:
        lines.append(f"Specimen: {specimen}")
    if amends is not None:
        lines.append(f"Amends: {amends}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode()


def _alpha_v3():
    return _report(
        "CASE-ALPHA", "PATH-ALPHA", "2026-05-03", "2026-05-12",
        [("histology", "reported",
          "Third fictional version refines the wording once more."),
         ("marker-a", "negative",
          "Marker A assay was performed and reported negative in the amended report."),
         ("margin", "indeterminate",
          "The margin cannot be assessed from this small specimen.")],
        specimen="BIOPSY-ALPHA", amends="PATH-ALPHA@2")


class ProvenanceStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()

    def test_twice_amended_source_shows_three_link_chain_in_order(self):
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        third = self.store.import_report("CASE-ALPHA", _alpha_v3())
        self.assertEqual(third["version"], 3)

        result = case_provenance(self.store, "CASE-ALPHA")
        document = next(item for item in result["documents"]
                        if item["document_id"] == "PATH-ALPHA")

        self.assertEqual(document["chain_length"], 3)
        self.assertEqual([link["version"] for link in document["chain"]], [1, 2, 3])
        self.assertEqual([link["state"] for link in document["chain"]],
                         ["superseded", "superseded", "current"])
        self.assertEqual([link["anchor"] for link in document["chain"]],
                         ["PATH-ALPHA@1", "PATH-ALPHA@2", "PATH-ALPHA@3"])
        self.assertEqual(document["current_version"], 3)
        for link in document["chain"]:
            self.assertRegex(link["received_date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertTrue(link["received_at"].startswith(link["received_date"]))
            self.assertEqual(link["anchor"], f"PATH-ALPHA@{link['version']}")
        self.assertIsNone(document["chain"][0]["supersedes_source_id"])
        self.assertEqual(document["chain"][1]["supersedes_source_id"],
                         document["chain"][0]["source_id"])
        self.assertEqual(document["chain"][2]["supersedes_source_id"],
                         document["chain"][1]["source_id"])
        self.assertEqual(document["chain"][0]["superseded_by_source_id"],
                         document["chain"][1]["source_id"])
        self.assertEqual(document["chain"][1]["superseded_by_source_id"],
                         document["chain"][2]["source_id"])
        self.assertIsNone(document["chain"][2]["superseded_by_source_id"])
        self.assertEqual([event["version"] for event in document["chain_events"]],
                         [1, 2, 3])

    def test_superseded_versions_remain_retrievable_with_anchors_intact(self):
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        self.store.import_report("CASE-ALPHA", _alpha_v3())

        result = case_provenance(self.store, "CASE-ALPHA")
        document = next(item for item in result["documents"]
                        if item["document_id"] == "PATH-ALPHA")
        texts = [self.store.source_text("CASE-ALPHA", link["source_id"])
                 for link in document["chain"]]

        self.assertIn("Marker A was not tested in this specimen.", texts[0])
        self.assertIn("reported negative in the amended report", texts[1])
        self.assertIn("Third fictional version refines the wording", texts[2])
        for link, text in zip(document["chain"], texts):
            self.assertIn(link["document_id"], text)
            self.assertEqual(link["anchor"],
                             f"{link['document_id']}@{link['version']}")

    def test_source_with_no_amendments_shows_single_link_chain(self):
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes())

        result = case_provenance(self.store, "CASE-ALPHA")
        document = next(item for item in result["documents"]
                        if item["document_id"] == "IMG-ALPHA")

        self.assertEqual(document["chain_length"], 1)
        link = document["chain"][0]
        self.assertEqual(link["version"], 1)
        self.assertEqual(link["state"], "current")
        self.assertEqual(link["anchor"], "IMG-ALPHA@1")
        self.assertIsNone(link["supersedes_source_id"])
        self.assertIsNone(link["superseded_by_source_id"])
        self.assertEqual(len(document["chain_events"]), 1)
        self.assertIsNone(document["chain_events"][0]["amends_source_id"])
        self.assertEqual(document["current_version"], 1)

    def test_citing_rows_review_states_match_ledger_exactly(self):
        pathology = self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        imaging = self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes())
        question_one = self.store.add_question(
            "CASE-ALPHA", "What does the pathology source report?")
        stale_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", question_one,
            "The original source reports Marker A was not tested.",
            [pathology["source_id"]])
        question_two = self.store.add_question(
            "CASE-ALPHA", "What does the imaging source report?")
        reviewed_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", question_two,
            "The imaging source reports prior images unavailable.",
            [imaging["source_id"]])
        self.store.acknowledge_demo_review(
            "CASE-ALPHA", reviewed_snapshot, "Synthetic reviewer")
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        draft_snapshot = self.store.create_snapshot(
            "CASE-ALPHA", question_one,
            "The amended source reports Marker A negative.",
            [self._current_source("CASE-ALPHA", "PATH-ALPHA")])

        result = case_provenance(self.store, "CASE-ALPHA")
        ledger = {item["id"]: item
                  for item in self.store.state("CASE-ALPHA")["snapshots"]}
        self.assertEqual(ledger[stale_snapshot]["state"], "stale")
        self.assertEqual(ledger[reviewed_snapshot]["state"], "reviewed_in_demo")
        self.assertEqual(ledger[draft_snapshot]["state"], "draft")

        by_source: dict[int, list[dict]] = {}
        for document in result["documents"]:
            for link in document["chain"]:
                by_source[link["source_id"]] = link["citing_snapshots"]
                for citing in link["citing_snapshots"]:
                    current = ledger[citing["snapshot_id"]]
                    self.assertEqual(citing["state"], current["state"])
                    self.assertEqual(citing["question_id"], current["question_id"])
        pathology_v1 = self._source_id("CASE-ALPHA", "PATH-ALPHA", 1)
        pathology_v2 = self._source_id("CASE-ALPHA", "PATH-ALPHA", 2)
        imaging_v1 = self._source_id("CASE-ALPHA", "IMG-ALPHA", 1)
        self.assertEqual(
            [(item["snapshot_id"], item["state"]) for item in by_source[pathology_v1]],
            [(stale_snapshot, "stale")])
        self.assertEqual(
            [(item["snapshot_id"], item["state"]) for item in by_source[pathology_v2]],
            [(draft_snapshot, "draft")])
        self.assertEqual(
            [(item["snapshot_id"], item["state"]) for item in by_source[imaging_v1]],
            [(reviewed_snapshot, "reviewed_in_demo")])

    def _current_source(self, case_id, document_id):
        rows = [item for item in self.store.state(case_id)["sources"]
                if item["document_id"] == document_id and item["state"] == "current"]
        return rows[0]["id"]

    def _source_id(self, case_id, document_id, version):
        rows = [item for item in self.store.state(case_id)["sources"]
                if item["document_id"] == document_id and item["version"] == version]
        return rows[0]["id"]

    def test_case_isolation_holds(self):
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        self.store.import_report(
            "CASE-BETA", (SYNTHETIC / "beta-pathology.txt").read_bytes())
        self.store.add_question("CASE-ALPHA", "What does the Alpha source report?")

        beta = case_provenance(self.store, "CASE-BETA")
        rendered = repr(beta)

        self.assertEqual([item["document_id"] for item in beta["documents"]],
                         ["PATH-BETA"])
        self.assertNotIn("PATH-ALPHA", rendered)
        self.assertNotIn("IMG-ALPHA", rendered)
        beta_ids = {item["id"] for item in self.store.state("CASE-BETA")["sources"]}
        for document in beta["documents"]:
            for link in document["chain"]:
                self.assertIn(link["source_id"], beta_ids)

    def test_amendment_visible_immediately_no_stale_cache(self):
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        before = case_provenance(self.store, "CASE-ALPHA")
        before_document = next(item for item in before["documents"]
                               if item["document_id"] == "PATH-ALPHA")
        self.assertEqual(before_document["chain_length"], 1)

        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        after = case_provenance(self.store, "CASE-ALPHA")
        after_document = next(item for item in after["documents"]
                              if item["document_id"] == "PATH-ALPHA")

        self.assertEqual(after_document["chain_length"], 2)
        self.assertEqual([link["state"] for link in after_document["chain"]],
                         ["superseded", "current"])
        self.assertGreater(after["as_of"]["event_id"], before["as_of"]["event_id"])
        self.assertEqual(len(after_document["chain_events"]), 2)

    def test_unknown_case_raises_existing_boundary(self):
        with self.assertRaises(InvalidInput) as raised:
            case_provenance(self.store, "CASE-UNKNOWN")
        self.assertEqual(str(raised.exception), "Unknown case")

    def test_empty_case_has_valid_empty_projection(self):
        result = case_provenance(self.store, "CASE-ALPHA")

        self.assertEqual(result["case_id"], "CASE-ALPHA")
        self.assertTrue(result["synthetic"])
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["counts"],
                         {"documents": 0, "versions": 0, "current": 0, "superseded": 0})

    def test_malformed_event_details_never_hide_chain_versions(self):
        self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO events (case_id,kind,details,occurred_at) VALUES (?,?,?,?)",
                ("CASE-ALPHA", "source_imported", "{not-json",
                 "2026-10-31T12:00:00+00:00"),
            )

        result = case_provenance(self.store, "CASE-ALPHA")
        document = next(item for item in result["documents"]
                        if item["document_id"] == "PATH-ALPHA")

        self.assertEqual(document["chain_length"], 1)
        self.assertEqual(document["chain"][0]["anchor"], "PATH-ALPHA@1")
        self.assertEqual(document["chain"][0]["state"], "current")
        self.assertEqual(len(document["chain_events"]), 1)

    def test_citing_snapshots_never_leak_across_cases(self):
        alpha_source = self.store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        self.store.import_report(
            "CASE-BETA", (SYNTHETIC / "beta-pathology.txt").read_bytes())
        question = self.store.add_question(
            "CASE-ALPHA", "What does the Alpha source report?")
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question,
            "The Alpha source reports its original findings here.",
            [alpha_source["source_id"]])

        beta = case_provenance(self.store, "CASE-BETA")

        for document in beta["documents"]:
            for link in document["chain"]:
                self.assertEqual(link["citing_snapshots"], [])
        # Structured check, not a repr substring: snapshot ids are small
        # integers that occur all over any repr (versions, dates, counts).
        beta_citing = {
            snap["snapshot_id"]
            for document in beta["documents"]
            for link in document["chain"]
            for snap in link["citing_snapshots"]
        }
        self.assertNotIn(snapshot_id, beta_citing)


class ProvenanceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "provenance-http.sqlite")
        seed(cls.path)
        bound_handler = type(
            "BoundProvenanceHandlerForTest", (Handler,), {"db_path": cls.path}
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
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

    def request(self, path, data=None):
        headers = {"Content-Type": "application/json"} if data is not None else {}
        body = None if data is None else json.dumps(data).encode()
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=body, headers=headers,
                          method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_seeded_case_exposes_ordered_chains(self):
        status, payload = self.request("/api/cases/CASE-ALPHA/provenance")

        self.assertEqual(status, 200)
        self.assertEqual(payload["case_id"], "CASE-ALPHA")
        self.assertTrue(payload["synthetic"])
        self.assertIn("Fictional", payload["disclaimer"])
        by_document = {item["document_id"]: item for item in payload["documents"]}
        self.assertEqual(sorted(by_document), ["IMG-ALPHA", "PATH-ALPHA"])
        for document in payload["documents"]:
            versions = [link["version"] for link in document["chain"]]
            self.assertEqual(versions, sorted(versions))
            self.assertEqual(document["chain_length"], len(document["chain"]))
            for link in document["chain"]:
                self.assertEqual(link["anchor"],
                                 f"{link['document_id']}@{link['version']}")
                self.assertIn(link["state"], ("current", "superseded"))
                self.assertRegex(link["received_date"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertIsInstance(link["citing_snapshots"], list)

    def test_unknown_case_returns_existing_422_boundary(self):
        status, error = self.request("/api/cases/CASE-UNKNOWN/provenance")

        self.assertEqual(status, 422)
        self.assertEqual(error["error"], "Unknown case")

    def test_amendment_visible_immediately_via_http(self):
        status, _ = self.request("/api/cases",
                                 {"case_id": "CASE-GAMMA", "label": "Fictional Gamma"})
        self.assertIn(status, (201, 422))
        original = _report(
            "CASE-GAMMA", "DOC-GAMMA", "2026-08-01", "2026-08-02",
            [("finding-a", "reported", "Fictional gamma original wording.")],
            specimen="SPECIMEN-GAMMA").decode()
        status, first = self.request("/api/cases/CASE-GAMMA/imports", {"text": original})
        self.assertEqual(status, 200)
        status, before = self.request("/api/cases/CASE-GAMMA/provenance")
        self.assertEqual(status, 200)
        before_document = next(item for item in before["documents"]
                               if item["document_id"] == "DOC-GAMMA")
        self.assertEqual(before_document["chain_length"], 1)

        amended = _report(
            "CASE-GAMMA", "DOC-GAMMA", "2026-08-01", "2026-08-03",
            [("finding-a", "reported", "Fictional gamma amended wording.")],
            specimen="SPECIMEN-GAMMA", amends="DOC-GAMMA@1").decode()
        status, _ = self.request("/api/cases/CASE-GAMMA/imports", {"text": amended})
        self.assertEqual(status, 200)
        status, after = self.request("/api/cases/CASE-GAMMA/provenance")
        self.assertEqual(status, 200)
        after_document = next(item for item in after["documents"]
                              if item["document_id"] == "DOC-GAMMA")

        self.assertEqual(after_document["chain_length"], 2)
        self.assertEqual([link["version"] for link in after_document["chain"]], [1, 2])
        self.assertEqual([link["state"] for link in after_document["chain"]],
                         ["superseded", "current"])
        self.assertGreater(after["as_of"]["event_id"], before["as_of"]["event_id"])

    def test_case_isolation_via_http(self):
        status, beta = self.request("/api/cases/CASE-BETA/provenance")

        self.assertEqual(status, 200)
        self.assertEqual([item["document_id"] for item in beta["documents"]],
                         ["PATH-BETA"])
        self.assertNotIn("PATH-ALPHA", json.dumps(beta))
        self.assertNotIn("IMG-ALPHA", json.dumps(beta))

    def test_superseded_versions_retrievable_via_http_with_anchors(self):
        status, _ = self.request("/api/cases",
                                 {"case_id": "CASE-DELTA", "label": "Fictional Delta"})
        self.assertIn(status, (201, 422))
        original = _report(
            "CASE-DELTA", "DOC-DELTA", "2026-09-01", "2026-09-02",
            [("finding-a", "reported", "Fictional delta original wording.")]).decode()
        amended = _report(
            "CASE-DELTA", "DOC-DELTA", "2026-09-01", "2026-09-03",
            [("finding-a", "reported", "Fictional delta amended wording.")],
            amends="DOC-DELTA@1").decode()
        self.request("/api/cases/CASE-DELTA/imports", {"text": original})
        self.request("/api/cases/CASE-DELTA/imports", {"text": amended})
        status, payload = self.request("/api/cases/CASE-DELTA/provenance")
        self.assertEqual(status, 200)
        document = next(item for item in payload["documents"]
                        if item["document_id"] == "DOC-DELTA")
        self.assertEqual(document["chain_length"], 2)

        for link in document["chain"]:
            status, body = self.request(
                f"/api/cases/CASE-DELTA/sources/{link['source_id']}")
            self.assertEqual(status, 200)
            self.assertIn("OI-SYNTHETIC-REPORT/1", body["text"])
            self.assertEqual(link["anchor"],
                             f"{link['document_id']}@{link['version']}")
        status, first = self.request(
            f"/api/cases/CASE-DELTA/sources/{document['chain'][0]['source_id']}")
        status2, second = self.request(
            f"/api/cases/CASE-DELTA/sources/{document['chain'][1]['source_id']}")
        self.assertIn("original wording", first["text"])
        self.assertIn("amended wording", second["text"])


class ProvenanceUiContractTests(unittest.TestCase):
    def test_portal_contains_provenance_panel(self):
        html = (ROOT / "web" / "index.html").read_text()

        self.assertIn('href="#provenance"', html)
        self.assertIn('id="provenance"', html)
        self.assertIn('id="provenance-status"', html)
        self.assertIn('id="provenance-list"', html)
        self.assertIn("Source provenance and amendment history", html)
        self.assertIn("FICTIONAL", html)
        self.assertIn('<script src="/provenance.js" defer></script>', html)

    def test_renderer_is_case_scoped_text_safe_and_refreshable(self):
        javascript = (ROOT / "web" / "provenance.js").read_text()

        self.assertIn("/provenance", javascript)
        self.assertIn("encodeURIComponent(caseId)", javascript)
        self.assertIn("/sources/", javascript)
        self.assertIn("requestSequence", javascript)
        self.assertIn("picker.value !== caseId", javascript)
        self.assertIn("MutationObserver", javascript)
        self.assertIn("textContent", javascript)
        self.assertIn("no-store", javascript)
        self.assertIn("FICTIONAL", javascript)
        self.assertIn("SUPERSEDED", javascript)
        self.assertIn("Exact anchor", javascript)
        self.assertNotIn("innerHTML", javascript)

    def test_renderer_reuses_existing_css_classes_only(self):
        javascript = (ROOT / "web" / "provenance.js").read_text()
        allowed = {"pill", "pill-neutral", "pill-warn", "pill-alert",
                   "source-card", "source-top", "source-title", "source-meta",
                   "snapshot", "topline", "snapshot-meta", "muted", "tiny",
                   "actions", "button", "secondary", "minor", "empty", "ref"}
        found: set[str] = set()
        for match in re.finditer(r'element\("([a-z]+)",\s*"([^"]*)"', javascript):
            for token in match.group(2).split():
                found.add(token)
        for match in re.finditer(r'className\s*=\s*"([^"]+)"', javascript):
            for token in match.group(1).split():
                found.add(token)
        for match in re.finditer(
                r'element\("[a-z]+",\s*[^,()?]+\?\s*"([^"]+)"\s*:\s*"([^"]+)"',
                javascript):
            for token in (match.group(1) + " " + match.group(2)).split():
                found.add(token)
        self.assertTrue(found)
        self.assertEqual(found - allowed, set())
        self.assertNotIn("style.", javascript)

    def test_provenance_panel_reuses_existing_css_classes_only(self):
        html = (ROOT / "web" / "index.html").read_text()
        start = html.index('id="provenance"')
        # Stop at the NEXT section's opening tag, not at its id attribute:
        # the id sits after class="panel panel-investigation" in that tag,
        # so slicing to the id would wrongly include the neighbor's class.
        end = html.rindex("<section", 0, html.index('id="investigations"'))
        section = html[start:end]
        allowed = {"panel", "panel-head", "eyebrow", "pill", "pill-neutral",
                   "muted", "tiny", "cards"}
        found: set[str] = set()
        for match in re.finditer(r'class="([^"]+)"', section):
            for token in match.group(1).split():
                found.add(token)
        self.assertTrue(found)
        self.assertEqual(found - allowed, set())

    def test_local_server_serves_renderer_and_route(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()

        self.assertIn('if path == "/provenance.js":', server)
        self.assertIn('self._static("provenance.js", "text/javascript; charset=utf-8")', server)
        self.assertIn("/provenance", server)
        self.assertIn("case_provenance", server)

    def test_projection_is_read_only_with_no_new_tables(self):
        projection = (ROOT / "src" / "open_intelligence" / "provenance.py").read_text()

        self.assertIn("def case_provenance", projection)
        self.assertIn("Unknown case", projection)
        self.assertNotIn("CREATE TABLE", projection)
        self.assertNotIn("INSERT INTO", projection)
        self.assertNotIn("UPDATE ", projection)
        self.assertNotIn("DELETE FROM", projection)


if __name__ == "__main__":
    unittest.main()
