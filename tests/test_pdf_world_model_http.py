"""Actual loopback HTTP convergence of PDF intake and the existing projection."""
from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from open_intelligence.store import CaseStore
from pdf_fixtures import text_pdf
import test_pdf_document_intake_http as intake_http


class PdfWorldModelHttpTests(unittest.TestCase):
    def setUp(self):
        # Reuse the existing independently fictional HTTP intake fixture,
        # without inheriting and duplicating its complete test suite.
        self.fixture = intake_http.PdfDocumentIntakeHttpTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_http_projection_source_pages_and_originals_are_case_scoped_and_read_only(self):
        fixture = self.fixture
        source_id = fixture.commit()
        before = fixture.ledger()
        status, model, headers = fixture.request("/api/cases/CASE-ALPHA/world-model")
        self.assertEqual(status, 200, model)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertTrue(model["synthetic"])
        self.assertEqual(model["scope"], "fictional_case_only_not_a_verified_patient")
        self.assertEqual(model["clinical_interpretation"], "not_generated")
        observation = model["observations"][0]
        self.assertEqual(observation["reported_state"], "not-assessed")
        self.assertEqual(observation.get("classification_origin"), "user_selected")
        self.assertEqual(observation.get("source_page"), 2)
        self.assertEqual(observation.get("page_line"), 1)
        status, source, _ = fixture.request(f"/api/cases/CASE-ALPHA/sources/{source_id}")
        self.assertEqual(status, 200, source)
        self.assertEqual(observation["source_sha256"], source["original_sha256"])
        self.assertEqual(observation.get("extraction_sha256"), source["extraction_sha256"])
        self.assertEqual(observation.get("page_text_sha256"), source["pages"][1]["sha256"])
        self.assertEqual(source["lines"][observation["source_line"] - 1],
            {"line": 2, "text": observation["source_statement"], "page": 2, "page_line": 1})
        status, original, headers = fixture.request(f"/api/cases/CASE-ALPHA/sources/{source_id}/download")
        self.assertEqual((status, original), (200, fixture.raw))
        self.assertEqual(headers["Content-Type"], "application/pdf")
        status, beta, _ = fixture.request("/api/cases/CASE-BETA/world-model")
        self.assertEqual(status, 200)
        self.assertEqual(beta["observations"], [])
        for path in (f"/api/cases/CASE-BETA/sources/{source_id}",
                     f"/api/cases/CASE-BETA/sources/{source_id}/download",
                     "/api/cases/CASE-NOPE/world-model",
                     "/api/cases/CASE-ALPHA/sources/9223372036854775808",
                     "/api/cases/CASE-ALPHA/sources/99999999999999999999999999"):
            with self.subTest(path=path):
                status, error, _ = fixture.request(path)
                self.assertEqual(status, 422, error)
                self.assertNotIn("Marker P", str(error))
        status, _, _ = fixture.request("/api/cases/CASE-ALPHA/world-model", headers={"Host": "external.invalid"})
        self.assertEqual(status, 403)
        status, script, headers = fixture.request("/patient-record.js")
        self.assertEqual(status, 200)
        self.assertIn("text/javascript", headers["Content-Type"])
        expected_script = Path(__file__).resolve().parents[1] / "web" / "patient-record.js"
        self.assertEqual(script, expected_script.read_bytes())
        self.assertEqual(fixture.ledger(), before)

    def test_http_rejects_case_status_page_and_provenance_mismatches(self):
        fixture = self.fixture
        fixture.commit()
        before = fixture.ledger()
        original_state = CaseStore.state
        changes = [
            lambda state: state["case"].update(case_id="CASE-BETA"),
            lambda state: state["sources"][0].update(state="superseded"),
            lambda state: state["sources"][0].update(state=[]),
            lambda state: state["assertions"][0].update(source_page=True),
            lambda state: state["assertions"][0].update(page_line=0),
            lambda state: state["assertions"][0].update(certainty=[]),
            lambda state: state["assertions"][0].update(extraction_sha256="0" * 64),
            lambda state: state["assertions"][0].update(transcription_review_sha256="0" * 64),
            lambda state: state["sources"][0]["document_intake"].update(clinical_review="approved"),
        ]
        for index, change in enumerate(changes):
            def inconsistent(store, case_id):
                state = original_state(store, case_id)
                change(state)
                return state
            with self.subTest(change=index), patch.object(CaseStore, "state", new=inconsistent):
                status, error, _ = fixture.request("/api/cases/CASE-ALPHA/world-model")
                self.assertEqual(status, 422, error)
                self.assertNotIn("Marker P", str(error))
        self.assertEqual(fixture.ledger(), before)

    def test_http_amendment_and_restart_preserve_historical_pdf_without_parser(self):
        fixture = self.fixture
        source_id = fixture.commit()
        original_bytes = fixture.raw
        original_preview = fixture.preview
        status, before, _ = fixture.request("/api/cases/CASE-ALPHA/world-model")
        self.assertEqual(status, 200)
        store = CaseStore(fixture.db_path)
        try:
            question = store.add_question("CASE-ALPHA", "What did the fictional report state?")
            snapshot = store.create_snapshot("CASE-ALPHA", question, "Fictional human review draft", [source_id])
            store.acknowledge_demo_review("CASE-ALPHA", snapshot, "Unverified fictional operator")
        finally:
            store.close()
        fixture.raw = text_pdf([["Independent fictional PDF"], ["Marker P remains pending."]])
        status, fixture.preview, _ = fixture.request("/api/cases/CASE-ALPHA/documents/preview", fixture.preview_payload())
        self.assertEqual(status, 200, fixture.preview)
        payload = fixture.commit_payload()
        payload["metadata"]["amends_version"] = 1
        payload["findings"][0].update(state="pending", quote="Marker P remains pending.")
        status, amended, _ = fixture.request("/api/cases/CASE-ALPHA/documents", payload)
        self.assertEqual(status, 200, amended)
        self.assertIn(snapshot, amended["invalidated_snapshots"])
        fixture.stop_server()
        fixture.start_server()
        ledger = fixture.ledger()
        with patch("open_intelligence.pdf_intake.extract_pdf", side_effect=AssertionError("Unexpected parser call")):
            status, after, _ = fixture.request("/api/cases/CASE-ALPHA/world-model")
            self.assertEqual(status, 200, after)
            self.assertEqual(after["observations"][0]["reported_state"], "pending")
            self.assertEqual(after["observations"][0]["clinical_review"], "not_performed")
            self.assertEqual(after["observations"][0]["extraction_sha256"], fixture.preview["extraction_sha256"])
            self.assertEqual(after["history"][0]["document_intake"], before["current_sources"][0]["document_intake"])
            self.assertEqual(after["history"][0]["extraction_sha256"], original_preview["extraction_sha256"])
            self.assertEqual(after["review_needed"]["stale_snapshot_ids"], [snapshot])
            self.assertEqual(after["review_needed"]["open_question_ids"], [question])
            status, old_view, _ = fixture.request(f"/api/cases/CASE-ALPHA/sources/{source_id}")
            self.assertEqual(status, 200)
            self.assertEqual(old_view["pages"][1]["text"], "Marker P was not assessed.\n")
            status, raw, _ = fixture.request(f"/api/cases/CASE-ALPHA/sources/{source_id}/download")
            self.assertEqual((status, raw), (200, original_bytes))
            status, report, _ = fixture.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot}/export")
            self.assertEqual(status, 200)
            self.assertIn(b"**stale**", report)
            self.assertIn(b"Marker P was not assessed.", report)
        self.assertEqual(fixture.ledger(), ledger)
