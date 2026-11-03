"""PDF passage corrections across the actual source, review and record HTTP boundary.

All documents are independently authored fictional fixtures. The saved PDF is
never replaced by the annotation revision, and reading/correcting after restart
must work without running the PDF parser again.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch

from pdf_fixtures import text_pdf
import test_pdf_document_intake_http as intake_http


AMBER = "Amber observation remains pending."
BLUE = "Blue observation was not assessed."


class PdfDocumentAnnotationRevisionHttpTests(unittest.TestCase):
    def setUp(self):
        # Composition reuses the loopback harness without duplicating all of
        # its upload tests through unittest inheritance.
        self.fixture = intake_http.PdfDocumentIntakeHttpTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        fixture = self.fixture
        fixture.raw = text_pdf([["Independent fictional correction fixture"], [AMBER, BLUE]])
        status, fixture.preview, _ = fixture.request(
            "/api/cases/CASE-ALPHA/documents/preview", fixture.preview_payload())
        self.assertEqual(status, 200, fixture.preview)
        payload = fixture.commit_payload()
        payload["findings"] = [self.finding()]
        status, imported, _ = fixture.request("/api/cases/CASE-ALPHA/documents", payload)
        self.assertEqual(status, 200, imported)
        self.source_id = imported["source_id"]
        self.path = f"/api/cases/CASE-ALPHA/sources/{self.source_id}/annotations"

    @staticmethod
    def finding(*, revised=False):
        return ({"key": "blue_tag", "state": "not-assessed", "quote": BLUE, "line": 3}
                if revised else
                {"key": "amber_tag", "state": "pending", "quote": AMBER, "line": 2})

    def payload(self, *, revised=True, expected_revision=1):
        return {
            "findings": [self.finding(revised=revised)],
            "expected_revision": expected_revision,
            "expected_sha256": self.fixture.preview["sha256"],
            "expected_extraction_sha256": self.fixture.preview["extraction_sha256"],
            "confirmed_case_id": "CASE-ALPHA",
            "manual_transcription_confirmed": True,
            "reason": "Correct the manually selected fictional passage after checking page two.",
        }

    def revised(self):
        status, result, _ = self.fixture.request(self.path, self.payload())
        self.assertEqual(status, 200, result)
        self.assertEqual(result["result"], "revised")
        self.assertEqual(result["annotation_revision"], 2)
        return result

    def test_read_and_correction_after_restart_use_frozen_pdf_without_reextraction(self):
        fixture = self.fixture
        fixture.stop_server()
        fixture.start_server()
        before = fixture.ledger()
        with patch("open_intelligence.pdf_intake.extract_pdf",
                   side_effect=AssertionError("Saved correction must not parse PDF bytes")):
            status, editor, headers = fixture.request(self.path)
            self.assertEqual(status, 200, editor)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(editor["media_type"], "application/pdf")
            for field in ("text", "pages", "lines", "extractor", "extraction_sha256"):
                self.assertEqual(editor[field], fixture.preview[field], field)
            self.assertEqual(editor["current_revision"]["revision"], 1)
            self.assertEqual(editor["current_revision"]["findings"], [self.finding()])
            self.assertEqual(fixture.ledger(), before)
            revised = self.revised()
            status, current, _ = fixture.request(self.path)
            self.assertEqual(status, 200, current)
            self.assertEqual([row["revision"] for row in current["history"]], [1, 2])
            self.assertEqual(current["history"][0]["findings"], [self.finding()])
            self.assertEqual(current["current_revision"]["findings"], [self.finding(revised=True)])
            self.assertEqual(current["pages"], editor["pages"])
            status, model, _ = fixture.request("/api/cases/CASE-ALPHA/world-model")
            self.assertEqual(status, 200, model)
            observation = model["observations"][0]
            self.assertEqual(observation["source_statement"], BLUE)
            self.assertEqual(observation["annotation_revision"], 2)
            self.assertEqual(observation["annotation_revision_id"], revised["annotation_revision_id"])
            self.assertEqual(observation["source_page"], 2)
            self.assertEqual(observation["page_line"], 2)
            self.assertEqual(observation["page_text_sha256"], fixture.preview["pages"][1]["sha256"])
            self.assertEqual(observation["source_sha256"], hashlib.sha256(fixture.raw).hexdigest())
            self.assertEqual(observation["extraction_sha256"], fixture.preview["extraction_sha256"])
            self.assertEqual(observation["clinical_review"], "not_performed")
            status, current_state, _ = fixture.request("/api/cases/CASE-ALPHA/state")
            self.assertEqual(status, 200)
            self.assertEqual(len(current_state["sources"]), 1)
            self.assertEqual(current_state["sources"][0]["version"], 1)
            status, original, headers = fixture.request(
                f"/api/cases/CASE-ALPHA/sources/{self.source_id}/download")
            self.assertEqual((status, original), (200, fixture.raw))
            self.assertEqual(headers["Content-Type"], "application/pdf")

    def test_missing_changed_or_null_original_and_extraction_identity_reject_without_writes(self):
        fixture = self.fixture
        before = fixture.ledger()
        for field in ("expected_sha256", "expected_extraction_sha256"):
            for value in ("missing", None, "0" * 64, fixture.preview["sha256"]
                          if field == "expected_extraction_sha256" else fixture.preview["extraction_sha256"]):
                with self.subTest(field=field, value=value):
                    payload = self.payload()
                    if value == "missing":
                        del payload[field]
                    else:
                        payload[field] = value
                    status, _, _ = fixture.request(self.path, payload)
                    self.assertEqual(status, 422)
                    self.assertEqual(fixture.ledger(), before)

    def test_forged_passage_and_client_page_fields_cannot_rewrite_saved_extraction(self):
        fixture = self.fixture
        before = fixture.ledger()
        mutations = [
            lambda value: value["findings"][0].update(quote="Invented finding absent from either PDF page."),
            lambda value: value["findings"][0].update(line=2),
            lambda value: value["findings"][0].update(page=1),
            lambda value: value["findings"][0].update(page_line=1),
            lambda value: value["findings"][0].update(page_text_sha256="0" * 64),
            lambda value: value.update(pages=[{"page": 2, "text": "Replacement page"}]),
            lambda value: value.update(extractor={"name": "client"}),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                payload = self.payload()
                mutate(payload)
                status, _, _ = fixture.request(self.path, payload)
                self.assertEqual(status, 422)
                self.assertEqual(fixture.ledger(), before)

    def test_pdf_retry_is_idempotent_and_a_stale_editor_cannot_replace_current_selections(self):
        fixture = self.fixture
        self.revised()
        before = fixture.ledger()
        status, retry, _ = fixture.request(self.path, self.payload())
        self.assertEqual(status, 200, retry)
        self.assertEqual((retry["result"], retry["annotation_revision"]), ("duplicate", 2))
        self.assertEqual(fixture.ledger(), before)
        status, _, _ = fixture.request(self.path, self.payload(revised=False))
        self.assertEqual(status, 422)
        self.assertEqual(fixture.ledger(), before)

    def test_historical_report_retains_captured_selection_page_and_hash_after_correction(self):
        fixture = self.fixture
        status, question, _ = fixture.request("/api/cases/CASE-ALPHA/questions", {
            "question": "Which fictional passage was selected from page two?"})
        self.assertEqual(status, 201, question)
        status, created, _ = fixture.request("/api/cases/CASE-ALPHA/snapshots", {
            "question_id": question["question_id"], "source_ids": [self.source_id],
            "summary": "Independent fictional manual source selection; no clinical conclusion.",
            "expected_annotation_revisions": {str(self.source_id): 1},
        })
        self.assertEqual(status, 201, created)
        snapshot = created["snapshot_id"]
        status, _, _ = fixture.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot}/review", {
            "reviewer_label": "Unverified fictional operator"})
        self.assertEqual(status, 200)
        self.assertIn(snapshot, self.revised()["invalidated_snapshots"])
        fixture.stop_server()
        fixture.start_server()
        before = fixture.ledger()
        with patch("open_intelligence.pdf_intake.extract_pdf",
                   side_effect=AssertionError("Historical PDF report must not re-extract")):
            status, raw, _ = fixture.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot}/export")
            self.assertEqual(status, 200)
            report = raw.decode("utf-8")
            self.assertIn("**stale**", report)
            self.assertIn("Annotation revision: 1", report)
            selected = report.split("User-selected annotations captured with this report:", 1)[1].split(
                "PDF extracted text below", 1)[0]
            self.assertIn(AMBER, selected)
            self.assertNotIn(BLUE, selected)
            self.assertIn("Finding: `amber_tag`", selected)
            self.assertIn("Physical page: 2 | Page line: 1", selected)
            self.assertIn(fixture.preview["pages"][1]["sha256"], selected)
            self.assertIn(fixture.preview["extraction_sha256"], report)
            self.assertIn(fixture.preview["sha256"], report)
            status, state, _ = fixture.request("/api/cases/CASE-ALPHA/state")
            self.assertEqual(status, 200)
            self.assertEqual(state["snapshots"][0]["state"], "stale")
            self.assertEqual(state["questions"][0]["state"], "open")
            status, _, _ = fixture.request(f"/api/cases/CASE-ALPHA/snapshots/{snapshot}/review", {
                "reviewer_label": "Unverified fictional operator"})
            self.assertEqual(status, 422)
        self.assertEqual(fixture.ledger(), before)

    def test_pdf_annotations_remain_case_scoped_for_both_read_and_revision(self):
        fixture = self.fixture
        before = fixture.ledger()
        path = self.path.replace("CASE-ALPHA", "CASE-BETA")
        payload = self.payload()
        payload["confirmed_case_id"] = "CASE-BETA"
        for body in (None, payload):
            status, error, _ = fixture.request(path, body)
            self.assertEqual(status, 422)
            self.assertNotIn(AMBER, str(error))
            self.assertNotIn(BLUE, str(error))
        wrong_confirmation = deepcopy(self.payload())
        wrong_confirmation["confirmed_case_id"] = "CASE-BETA"
        status, _, _ = fixture.request(self.path, wrong_confirmation)
        self.assertEqual(status, 422)
        self.assertEqual(fixture.ledger(), before)


if __name__ == "__main__":
    unittest.main()
