"""Corrections to independently authored PDF selections preserve source history."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from open_intelligence.composer import build_composer_context
from open_intelligence.document_intake import preview_saved_document
from open_intelligence.investigation import ValidatedInvestigation
from open_intelligence.pdf_worker import canonical_json, make_rendition
from open_intelligence.store import CaseStore, InvalidInput
from pdf_fixtures import text_pdf


class PdfAnnotationRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "pdf-annotation-revisions.sqlite"
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA", "Independently fictional PDF annotation case")
        self.store.add_case("CASE-BETA", "Unrelated fictional case")
        self.raw = text_pdf([["Independent fictional report", "Synthetic test input only."],
                             ["Marker Q was not assessed.", "Review remains pending."]])
        self.preview = self.store.preview_document("CASE-ALPHA", self.raw, "fictional.pdf")
        self.metadata = {"document_id": "PDF-ALPHA", "kind": "pathology",
                         "event_date": "2026-04-05", "issued_at": "2026-04-07",
                         "manual_transcription_confirmed": True}
        self.findings = [{"key": "marker-q", "state": "negative",
                          "quote": "Marker Q was not assessed.", "line": 3}]
        self.corrected = [{**self.findings[0], "state": "not-assessed"},
                          {"key": "review-follow-up", "state": "pending",
                           "quote": "Review remains pending.", "line": 4}]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ingest(self, findings=None):
        return self.store.import_document("CASE-ALPHA", self.raw, "fictional.pdf",
            self.metadata, self.findings if findings is None else findings,
            self.preview["sha256"], "CASE-ALPHA", self.preview["extraction_sha256"])["source_id"]

    def revise(self, source, **changes):
        payload = {"findings": self.corrected, "expected_revision": 1,
                   "expected_sha256": self.preview["sha256"], "confirmed_case_id": "CASE-ALPHA",
                   "manual_transcription_confirmed": True,
                   "reason": "Correct the selected status and include the pending follow-up passage.",
                   "expected_extraction_sha256": self.preview["extraction_sha256"]}
        payload.update(changes)
        return self.store.revise_document_annotations("CASE-ALPHA", source, **payload)

    def dump(self):
        return tuple(self.store.db.iterdump())

    def test_saved_read_and_correction_reuse_frozen_pages_after_restart_and_extractor_change(self):
        source = self.ingest()
        initial_receipt = dict(self.store.db.execute(
            "SELECT * FROM document_intake_metadata WHERE source_version_id=?", (source,)).fetchone())
        initial_rendition = dict(self.store.db.execute(
            "SELECT * FROM source_text_renditions WHERE source_version_id=?", (source,)).fetchone())
        self.store.close()
        self.store = CaseStore(self.path)
        future_descriptor = {**self.preview["extractor"], "version": "future-test-version"}
        with patch("open_intelligence.pdf_intake.extract_pdf", side_effect=AssertionError("Unexpected reparse")), \
                patch("open_intelligence.pdf_worker.extractor_descriptor", return_value=future_descriptor):
            saved = self.store.document_annotations("CASE-ALPHA", source)
            for field in ("text", "lines", "pages", "page_count", "extractor", "extraction_sha256", "sha256"):
                self.assertEqual(saved[field], self.preview[field])
            self.assertEqual(saved["lines"][2]["page"], 2)
            self.assertEqual(saved["lines"][2]["page_line"], 1)
            changed = self.revise(source)
            self.assertEqual(changed["annotation_revision"], 2)
            history = self.store.document_annotations("CASE-ALPHA", source)
            self.assertEqual(history["history"][0]["findings"], self.findings)
            self.assertEqual(history["history"][1]["findings"], self.corrected)
            before = self.dump()
            self.assertEqual(self.revise(source)["result"], "duplicate")
            self.assertEqual(self.dump(), before)
        self.assertEqual(self.store.source_document("CASE-ALPHA", source)["raw"], self.raw)
        self.assertEqual(dict(self.store.db.execute(
            "SELECT * FROM document_intake_metadata WHERE source_version_id=?", (source,)).fetchone()), initial_receipt)
        self.assertEqual(dict(self.store.db.execute(
            "SELECT * FROM source_text_renditions WHERE source_version_id=?", (source,)).fetchone()), initial_rendition)
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(len(state["sources"]), 1)
        self.assertEqual(state["sources"][0]["version"], 1)
        for row in state["assertions"]:
            self.assertEqual(row["annotation_revision"], 2)
            self.assertEqual(row["extraction_sha256"], self.preview["extraction_sha256"])
            self.assertEqual(row["source_page"], 2)
            self.assertEqual(row["page_text_sha256"], self.preview["pages"][1]["sha256"])
            self.assertEqual(row["clinical_review"], "not_performed")

    def test_correction_preserves_prior_report_and_model_inputs_and_requires_new_review(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "What does the fictional passage actually state?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
            "A human-authored draft before correcting manual selections.", [source])
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot, "Fictional reviewer")
        context = build_composer_context(self.store, "CASE-ALPHA", question)
        model = self.store.save_investigation("CASE-ALPHA", question, "evidence-summary",
            ValidatedInvestigation("abstained", [], [], [], "recorded-replay", "replay"),
            "replay", context_fingerprint=context["fingerprint"])
        initial_hash = self.store.document_annotations("CASE-ALPHA", source)["current_revision"]["review_sha256"]
        result = self.revise(source)
        self.assertEqual(result["invalidated_snapshots"], [snapshot])
        self.assertIn(model, result["invalidated_model_investigation_ids"])
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(state["questions"][0]["state"], "open")
        self.assertEqual(state["snapshots"][0]["state"], "stale")
        with patch("open_intelligence.pdf_intake.extract_pdf", side_effect=AssertionError("Unexpected reparse")):
            report = self.store.export_markdown("CASE-ALPHA", snapshot)
        for expected in ("Annotation revision: 1", initial_hash, "User-selected status: `negative`",
                         "Extraction line: 3", "Physical page: 2", "Page line: 1",
                         self.preview["pages"][1]["sha256"], self.preview["extraction_sha256"],
                         self.preview["sha256"], "**stale**", "Original PDF:"):
            self.assertIn(expected, report)
        self.assertNotIn(result["review_sha256"], report)
        self.assertNotIn("Original line:", report)
        captured = self.store.get_investigation("CASE-ALPHA", model)["input_annotations"]
        self.assertEqual(captured["context_revisions"][0]["revision"], 1)
        self.assertEqual(captured["prompt_assertions"][0]["certainty"], "negative")
        self.assertEqual(captured["prompt_assertions"][0]["source_page"], 2)
        with self.assertRaises(InvalidInput):
            self.store.create_snapshot("CASE-ALPHA", question, "A stale unchanged selection must reject.", [source])
        updated = self.store.create_snapshot("CASE-ALPHA", question, "A draft uses the explicitly reselected revision.",
            [source], expected_annotation_revisions={str(source): 2})
        self.assertIn("Annotation revision: 2", self.store.export_markdown("CASE-ALPHA", updated))
        self.assertEqual(self.store.state("CASE-ALPHA")["questions"][0]["state"], "open")

    def test_dual_hashes_exact_passage_and_case_confirmation_are_required_without_writes(self):
        source = self.ingest()
        before = self.dump()
        invalid = [{"expected_sha256": "0" * 64}, {"expected_extraction_sha256": None},
                   {"expected_extraction_sha256": "0" * 64}, {"expected_extraction_sha256": "malformed"},
                   {"confirmed_case_id": "CASE-BETA"}, {"manual_transcription_confirmed": False},
                   {"findings": [{**self.findings[0], "line": 1}]},
                   {"findings": [{**self.findings[0], "quote": "An invented quotation."}]},
                   {"findings": [{**self.findings[0], "source_page": 1}]},
                   {"findings": [{**self.findings[0], "page_line": 1}]}]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(InvalidInput):
                self.revise(source, **changes)
            self.assertEqual(self.dump(), before)
        with self.assertRaises(InvalidInput):
            self.store.document_annotations("CASE-BETA", source)
        self.assertEqual(self.dump(), before)

    def test_original_only_pdf_accepts_later_selections_and_revert_never_revives_context(self):
        source = self.ingest(findings=[])
        question = self.store.add_question("CASE-ALPHA", "Which annotation revision did the model receive?")
        original = build_composer_context(self.store, "CASE-ALPHA", question)
        self.revise(source)
        reverted = self.revise(source, expected_revision=2, findings=[],
            reason="Remove the optional selections while retaining their history.")
        current = build_composer_context(self.store, "CASE-ALPHA", question)
        self.assertEqual(reverted["annotation_revision"], 3)
        self.assertNotEqual(current["fingerprint"], original["fingerprint"])
        self.assertEqual(self.store.state("CASE-ALPHA")["assertions"], [])
        self.assertEqual([r["revision"] for r in self.store.document_annotations("CASE-ALPHA", source)["history"]], [1, 2, 3])
        with self.assertRaises(InvalidInput):
            self.revise(source)

    def test_late_failure_rolls_back_pdf_history_and_current_projection(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "Will a failed correction preserve the reviewed draft?")
        self.store.create_snapshot("CASE-ALPHA", question, "A fictional draft before a simulated storage failure.", [source])
        self.store.db.execute("""CREATE TRIGGER reject_pdf_annotation_event BEFORE INSERT ON events
            WHEN NEW.kind='document_annotations_revised' BEGIN
            SELECT RAISE(ABORT, 'simulated receipt failure'); END""")
        self.store.db.commit()
        before = self.dump()
        with self.assertRaises(sqlite3.IntegrityError):
            self.revise(source)
        self.assertEqual(self.dump(), before)

    def test_pre_revision_pdf_database_migrates_known_snapshot_and_immutable_rendition(self):
        source = self.ingest()
        question = self.store.add_question("CASE-ALPHA", "Which original annotation did this old PDF report capture?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
            "A report created before annotation revision history was implemented.", [source])
        with self.store.db:
            self.store.db.execute("DROP TABLE snapshot_annotation_revisions")
            self.store.db.execute("DROP TABLE investigation_annotation_inputs")
            self.store.db.execute("DROP TABLE document_annotation_revisions")
        self.store.close()
        with patch("open_intelligence.pdf_intake.extract_pdf", side_effect=AssertionError("Unexpected reparse")):
            self.store = CaseStore(self.path)
            saved = self.store.document_annotations("CASE-ALPHA", source)
            self.assertEqual(saved["current_revision"]["origin"], "legacy_intake_migration")
            self.assertEqual(saved["extraction_sha256"], self.preview["extraction_sha256"])
            self.revise(source)
            report = self.store.export_markdown("CASE-ALPHA", snapshot)
        self.assertIn("Annotation revision: 1", report)
        self.assertIn("User-selected status: `negative`", report)
        self.assertIn(self.preview["pages"][1]["sha256"], report)

    def test_superseded_pdf_history_remains_readable_and_is_not_editable(self):
        source = self.ingest()
        self.revise(source)
        raw = text_pdf([["Independent fictional amendment"], ["Marker Q remains pending."]])
        preview = self.store.preview_document("CASE-ALPHA", raw, "amended.pdf")
        self.store.import_document("CASE-ALPHA", raw, "amended.pdf", {**self.metadata, "amends_version": 1},
            [{"key": "marker-q", "state": "pending", "quote": "Marker Q remains pending.", "line": 2}],
            preview["sha256"], "CASE-ALPHA", preview["extraction_sha256"])
        saved = self.store.document_annotations("CASE-ALPHA", source)
        self.assertFalse(saved["writable"])
        self.assertEqual(saved["current_revision"]["revision"], 2)
        self.assertEqual(saved["extraction_sha256"], self.preview["extraction_sha256"])
        before = self.dump()
        with self.assertRaises(InvalidInput):
            self.revise(source, expected_revision=2)
        self.assertEqual(self.dump(), before)

    def test_text_revision_rejects_pdf_identity(self):
        raw = b"Independent fictional note\nReview pending.\n"
        source = self.store.import_document("CASE-ALPHA", raw, "fictional.txt",
            {**self.metadata, "document_id": "TEXT-ALPHA"}, [], hashlib.sha256(raw).hexdigest(), "CASE-ALPHA")["source_id"]
        before = self.dump()
        with self.assertRaises(InvalidInput):
            self.revise(source, expected_sha256=hashlib.sha256(raw).hexdigest(), findings=[])
        self.assertEqual(self.dump(), before)


class FrozenPdfPreviewTests(unittest.TestCase):
    def setUp(self):
        self.raw = text_pdf([["Independent fictional source"]])
        # Authored extraction strings exercise Unicode/blank physical pages;
        # these are deterministic validator inputs, not a visual PDF assertion.
        self.frozen = {**make_rendition(["Fictional note\r\n", "", "Marker Q\u2028Review pending.\n"]),
                       "original_sha256": hashlib.sha256(self.raw).hexdigest()}

    def test_saved_page_strings_keep_blank_page_and_unicode_separator_indices(self):
        preview = preview_saved_document(self.raw, "fictional.pdf", self.frozen)
        self.assertEqual(preview["lines"][2], {"line": 3, "text": "Review pending.", "page": 3, "page_line": 2})
        self.assertEqual(preview["pages"][1]["text"], "")
        self.assertEqual(preview["extraction_sha256"], self.frozen["extraction_sha256"])

    def test_inconsistent_frozen_text_page_hash_lines_descriptor_or_identity_rejects(self):
        variants = []
        for key, value in (("text", "Different text"), ("page_count", 2),
                           ("extractor", {**self.frozen["extractor"], "version": "changed"}),
                           ("extraction_sha256", "0" * 64), ("original_sha256", "0" * 64)):
            changed = deepcopy(self.frozen)
            changed[key] = value
            variants.append(changed)
        for field, key, value in (("pages", "sha256", "0" * 64), ("pages", "page", True),
                                  ("lines", "page", 2), ("lines", "page_line", True),
                                  ("lines", "text", "Invented passage")):
            changed = deepcopy(self.frozen)
            changed[field][0][key] = value
            # Even a recomputed container digest cannot make inconsistent page
            # anchors or hashes pass the frozen-text validation.
            payload = {key: changed[key] for key in ("text", "lines", "pages", "page_count", "extractor")}
            changed["extraction_sha256"] = hashlib.sha256(canonical_json(payload)).hexdigest()
            variants.append(changed)
        for index, rendition in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(InvalidInput):
                preview_saved_document(self.raw, "fictional.pdf", rendition)


if __name__ == "__main__":
    unittest.main()
