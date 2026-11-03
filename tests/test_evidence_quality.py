"""Evidence quality and limitations panel: store + HTTP + UI-contract.

Fictional/demo data only. Quality notes are descriptive, never ratings.
Every assertion below is falsifiable: it fails without the feature.
"""

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
SAMPLE = ROOT / "examples" / "synthetic"


def report(name):
    return (SAMPLE / name).read_bytes()


def quality_kwargs(**overrides):
    base = {
        "assessor_label": "Fictional reviewer",
        "date_recorded": "2026-06-01",
        "completeness_note": "Fictional note: covers the stated assay only.",
        "limitations_text": "Fictional note: single time point, no follow-up.",
        "conflict_note": "Fictional note: no disagreement recorded.",
    }
    base.update(overrides)
    return base


class EvidenceQualityStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "test.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_not_assessed_marker_never_guesses_rating(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        view = self.store.evidence_quality("CASE-ALPHA")
        self.assertEqual(view["case_id"], "CASE-ALPHA")
        self.assertEqual(len(view["current"]), 1)
        entry = view["current"][0]
        self.assertEqual(entry["source_id"], first["source_id"])
        self.assertEqual(entry["document_id"], "PATH-ALPHA")
        self.assertIn("PATH-ALPHA@1", entry["citation_anchor"])
        self.assertIn(str(first["source_id"]), entry["citation_anchor"])
        self.assertEqual(entry["assessment_status"], "not_assessed")
        self.assertEqual(entry["assessments"], [])
        # No rating, score, or inferred quality field may appear on any entry.
        for key in entry:
            self.assertNotIn(key, ("rating", "score", "quality", "grade"))
        payload = json.dumps(view)
        self.assertNotIn('"rating"', payload)
        self.assertNotIn('"score"', payload)
        self.assertNotIn('"quality_score"', payload)
        self.assertEqual(view["superseded"], [])

    def test_second_assessment_appends_without_overwriting_first(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        sid = first["source_id"]
        first_id = self.store.record_evidence_quality("CASE-ALPHA", sid, **quality_kwargs(
            assessor_label="Fictional reviewer one",
            completeness_note="Fictional first note about coverage."))
        second_id = self.store.record_evidence_quality("CASE-ALPHA", sid, **quality_kwargs(
            assessor_label="Fictional reviewer two",
            date_recorded="2026-06-02",
            completeness_note="Fictional second note about coverage."))
        self.assertNotEqual(first_id, second_id)
        view = self.store.evidence_quality("CASE-ALPHA")
        entry = view["current"][0]
        self.assertEqual(entry["assessment_status"], "assessed")
        self.assertEqual([a["id"] for a in entry["assessments"]], [first_id, second_id])
        self.assertEqual(entry["assessments"][0]["assessor_label"], "Fictional reviewer one")
        self.assertEqual(entry["assessments"][0]["completeness_note"],
                         "Fictional first note about coverage.")
        self.assertEqual(entry["assessments"][1]["assessor_label"], "Fictional reviewer two")
        # Every record carries its source anchor.
        for note in entry["assessments"]:
            self.assertEqual(note["source_version_id"], sid)

    def test_recording_never_changes_source_or_review_state(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        before_sources = self.store.state("CASE-ALPHA")["sources"]
        qid = self.store.add_question("CASE-ALPHA", "What was reported in this fictional source?")
        draft = self.store.create_snapshot(
            "CASE-ALPHA", qid, "Human-authored fictional draft for review.", [first["source_id"]])
        self.store.acknowledge_demo_review("CASE-ALPHA", draft, "Fictional reviewer")
        before_snapshot = [s for s in self.store.state("CASE-ALPHA")["snapshots"] if s["id"] == draft][0]
        before_question = [q for q in self.store.state("CASE-ALPHA")["questions"] if q["id"] == qid][0]
        self.store.record_evidence_quality("CASE-ALPHA", first["source_id"], **quality_kwargs())
        after = self.store.state("CASE-ALPHA")
        self.assertEqual(after["sources"], before_sources)
        after_snapshot = [s for s in after["snapshots"] if s["id"] == draft][0]
        after_question = [q for q in after["questions"] if q["id"] == qid][0]
        self.assertEqual(after_snapshot["state"], before_snapshot["state"])
        self.assertEqual(after_snapshot["state"], "reviewed_in_demo")
        self.assertEqual(after_question["state"], before_question["state"])
        self.assertEqual(after_question["state"], "addressed")

    def test_amendment_moves_assessments_to_superseded_with_version_link(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        note_id = self.store.record_evidence_quality("CASE-ALPHA", first["source_id"], **quality_kwargs())
        amended = self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        view = self.store.evidence_quality("CASE-ALPHA")
        self.assertEqual(len(view["current"]), 1)
        self.assertEqual(len(view["superseded"]), 1)
        old = view["superseded"][0]
        new = view["current"][0]
        self.assertEqual(old["source_id"], first["source_id"])
        self.assertEqual(old["version"], 1)
        self.assertEqual(old["assessment_status"], "assessed")
        self.assertEqual(len(old["assessments"]), 1)
        self.assertEqual(old["assessments"][0]["id"], note_id)
        self.assertEqual(old["assessments"][0]["source_version_id"], first["source_id"])
        self.assertIn("PATH-ALPHA@1", old["citation_anchor"])
        self.assertIn(str(first["source_id"]), old["citation_anchor"])
        self.assertEqual(new["source_id"], amended["source_id"])
        self.assertEqual(new["version"], 2)
        self.assertEqual(new["assessment_status"], "not_assessed")
        self.assertEqual(new["assessments"], [])

    def test_case_isolation_holds(self):
        alpha = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        beta = self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        self.store.record_evidence_quality("CASE-ALPHA", alpha["source_id"], **quality_kwargs(
            completeness_note="Fictional alpha-only coverage note."))
        beta_view = self.store.evidence_quality("CASE-BETA")
        self.assertEqual(len(beta_view["current"]), 1)
        self.assertEqual(beta_view["current"][0]["source_id"], beta["source_id"])
        self.assertEqual(beta_view["current"][0]["assessment_status"], "not_assessed")
        self.assertNotIn("alpha-only", json.dumps(beta_view))
        # Cross-case source reference is rejected.
        with self.assertRaisesRegex(InvalidInput, "Source not in this case"):
            self.store.record_evidence_quality("CASE-BETA", alpha["source_id"], **quality_kwargs())
        with self.assertRaisesRegex(InvalidInput, "Source not in this case"):
            self.store.record_evidence_quality("CASE-ALPHA", beta["source_id"], **quality_kwargs())

    def test_unknown_case_raises(self):
        with self.assertRaisesRegex(InvalidInput, "Unknown case"):
            self.store.evidence_quality("CASE-NOPE")
        with self.assertRaisesRegex(InvalidInput, "Unknown case"):
            self.store.record_evidence_quality("CASE-NOPE", 1, **quality_kwargs())

    def test_quality_notes_are_validated_descriptive_text(self):
        first = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        sid = first["source_id"]
        with self.assertRaises(InvalidInput):
            self.store.record_evidence_quality("CASE-ALPHA", sid, **quality_kwargs(assessor_label="x"))
        with self.assertRaises(InvalidInput):
            self.store.record_evidence_quality("CASE-ALPHA", sid, **quality_kwargs(date_recorded="yesterday"))
        with self.assertRaises(InvalidInput):
            self.store.record_evidence_quality("CASE-ALPHA", sid, **quality_kwargs(completeness_note="  "))
        with self.assertRaises(InvalidInput):
            self.store.record_evidence_quality("CASE-ALPHA", sid, **quality_kwargs(limitations_text=""))
        with self.assertRaises(InvalidInput):
            self.store.record_evidence_quality("CASE-ALPHA", sid, **quality_kwargs(conflict_note="x" * 1001))
        self.assertEqual(self.store.evidence_quality("CASE-ALPHA")["current"][0]["assessment_status"],
                         "not_assessed")


class EvidenceQualityHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound = type("BoundHandlerForQualityTest", (Handler,), {"db_path": cls.path})
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
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers={"Content-Type": "application/json"} if data is not None else {})
        try:
            with urlopen(req, timeout=5) as response:
                body = response.read()
                ctype = response.headers.get("Content-Type", "")
                return response.status, json.loads(body) if "json" in ctype else body
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_get_returns_current_entries_with_explicit_marker(self):
        status, view = self.request("/api/cases/CASE-ALPHA/evidence-quality")
        self.assertEqual(status, 200)
        self.assertEqual(view["case_id"], "CASE-ALPHA")
        self.assertTrue(view["current"])
        for entry in view["current"]:
            self.assertIn("source_id", entry)
            self.assertIn("document_id", entry)
            self.assertIn("citation_anchor", entry)
            self.assertIn(entry["assessment_status"], ("assessed", "not_assessed"))
            self.assertIsInstance(entry["assessments"], list)
            if entry["assessment_status"] == "not_assessed":
                self.assertEqual(entry["assessments"], [])
            for key in entry:
                self.assertNotIn(key, ("rating", "score", "quality", "grade"))
        self.assertIsInstance(view["superseded"], list)
        payload = json.dumps(view)
        self.assertNotIn('"rating"', payload)
        self.assertNotIn('"score"', payload)

    def test_post_appends_and_get_shows_recorded_order(self):
        status, state = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        sid = [s for s in state["sources"] if s["state"] == "current"][0]["id"]
        first_body = {"source_version_id": sid, **quality_kwargs(
            assessor_label="Fictional HTTP reviewer one",
            completeness_note="Fictional HTTP first coverage note.")}
        status, first = self.request("/api/cases/CASE-ALPHA/evidence-quality", first_body)
        self.assertEqual(status, 201)
        self.assertIsInstance(first["assessment_id"], int)
        second_body = {"source_version_id": sid, **quality_kwargs(
            assessor_label="Fictional HTTP reviewer two",
            date_recorded="2026-06-03",
            completeness_note="Fictional HTTP second coverage note.")}
        status, second = self.request("/api/cases/CASE-ALPHA/evidence-quality", second_body)
        self.assertEqual(status, 201)
        status, view = self.request("/api/cases/CASE-ALPHA/evidence-quality")
        self.assertEqual(status, 200)
        entry = [e for e in view["current"] if e["source_id"] == sid][0]
        labels = [a["assessor_label"] for a in entry["assessments"]]
        self.assertIn("Fictional HTTP reviewer one", labels)
        self.assertIn("Fictional HTTP reviewer two", labels)
        self.assertLess(labels.index("Fictional HTTP reviewer one"),
                        labels.index("Fictional HTTP reviewer two"))

    def test_unknown_case_returns_422(self):
        status, body = self.request("/api/cases/CASE-NOPE/evidence-quality")
        self.assertEqual(status, 422)
        self.assertIn("Unknown case", body["error"])

    def test_http_case_isolation(self):
        status, alpha_state = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        sid = [s for s in alpha_state["sources"] if s["state"] == "current"][0]["id"]
        marker = "Fictional isolation marker note."
        status, _ = self.request("/api/cases/CASE-ALPHA/evidence-quality",
                                 {"source_version_id": sid, **quality_kwargs(completeness_note=marker)})
        self.assertEqual(status, 201)
        status, beta_view = self.request("/api/cases/CASE-BETA/evidence-quality")
        self.assertEqual(status, 200)
        self.assertNotIn(marker, json.dumps(beta_view))
        # A Beta client cannot file a note against an Alpha source id.
        status, body = self.request("/api/cases/CASE-BETA/evidence-quality",
                                    {"source_version_id": sid, **quality_kwargs()})
        self.assertEqual(status, 422)


class EvidenceQualityUiContractTests(unittest.TestCase):
    def test_panel_markup_exists_with_fictional_labels(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="evidence-quality"', html)
        self.assertIn('id="evidence-quality-current"', html)
        self.assertIn('id="evidence-quality-superseded"', html)
        self.assertIn('href="#evidence-quality"', html)
        self.assertIn("Evidence quality", html)
        self.assertIn("FICTIONAL", html)
        self.assertIn("Not assessed", html)

    def test_panel_logic_renders_not_assessed_without_guessing(self):
        js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("loadEvidenceQuality", js)
        self.assertIn("renderEvidenceQuality", js)
        self.assertIn("evidence-quality-current", js)
        self.assertIn("evidence-quality-superseded", js)
        self.assertIn("/evidence-quality", js)
        # The renderer keys off the API marker assessment_status and shows
        # the human text; the literal 'not_assessed' lives in the API payload.
        self.assertIn("assessment_status", js)
        self.assertIn("Not assessed", js)
        self.assertIn("FICTIONAL", js)
        # Recorded order: assessments render in the order returned.
        self.assertIn("entry.assessments", js)

    def test_panel_uses_textcontent_and_case_guards(self):
        js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        start = js.index("function renderEvidenceQuality")
        end = js.index("el('model-investigation-form')", start)
        block = js[start:end]
        self.assertIn("node(", block)
        self.assertNotIn("innerHTML", block)
        # No guessed rating/score is rendered from data: only the explicit
        # "Not assessed" marker appears when no note exists.
        self.assertNotIn("entry.rating", block)
        self.assertNotIn("entry.score", block)
        self.assertNotIn("note.rating", block)
        self.assertNotIn("note.score", block)
        self.assertIn("Not assessed", block)
        # Reuse existing CSS classes only (no new stylesheet hooks).
        for token in ("source-card", "source-top", "source-title",
                      "finding", "finding-head", "snapshot-meta", "muted", "ref"):
            self.assertIn(token, block)
        self.assertNotIn("quality-card", block)
        self.assertNotIn("quality-note", block)
        load_start = js.index("async function loadEvidenceQuality")
        load_end = js.index("function renderEvidenceQuality", load_start)
        load_block = js[load_start:load_end]
        self.assertIn("requested !== caseId", load_block)
        # Display containers are cleared before each load: no stale case leak.
        self.assertIn("clear(", load_block)
        self.assertIn("evidence-quality-current", load_block)
        self.assertIn("evidence-quality-superseded", load_block)
        self.assertIn("active.case.case_id", load_block)


if __name__ == "__main__":
    unittest.main()
