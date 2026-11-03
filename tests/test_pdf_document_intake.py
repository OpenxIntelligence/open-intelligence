"""PDF source-owner integration using independently authored fictional records."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from open_intelligence.changes import changes_since_review
from open_intelligence.composer import build_composer_context, composer_context_fingerprint
from open_intelligence.investigation import ValidatedInvestigation, build_prompt
from open_intelligence.mission import build_patient_mission
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.timeline import case_timeline
from pdf_fixtures import encrypted_pdf, streams_pdf, text_pdf


class PdfDocumentIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fictional-pdf.sqlite"
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA", "Independent fictional PDF case")
        self.store.add_case("CASE-BETA", "Unrelated fictional case")
        self.raw = text_pdf([["Independent fictional report", "No clinical interpretation."],
                             ["Marker P was not assessed."]])
        self.preview = self.store.preview_document("CASE-ALPHA", self.raw, "fictional.pdf")
        self.metadata = {"document_id": "PDF-ALPHA", "kind": "pathology",
                         "event_date": "2026-07-01", "issued_at": "2026-07-02",
                         "specimen_id": "SYNTH-SPECIMEN", "manual_transcription_confirmed": True}
        self.findings = [{"key": "marker-p", "state": "not-assessed",
                          "quote": "Marker P was not assessed.", "line": 3}]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def ledger(self):
        return tuple(self.store.db.iterdump())

    def commit(self, **overrides):
        args = {"case_id": "CASE-ALPHA", "raw": self.raw, "filename": "fictional.pdf",
                "metadata": self.metadata, "findings": self.findings,
                "expected_sha256": self.preview["sha256"], "confirmed_case_id": "CASE-ALPHA",
                "expected_extraction_sha256": self.preview["extraction_sha256"]}
        args.update(overrides)
        return self.store.import_document(**args)

    def add_work(self, source_id):
        question = self.store.add_question("CASE-ALPHA", "What does the fictional PDF say?")
        snapshot = self.store.create_snapshot("CASE-ALPHA", question,
            "The selected passage requires independent human review.", [source_id])
        context = build_composer_context(self.store, "CASE-ALPHA", question)
        result = ValidatedInvestigation("abstained", [],
            [{"topic": "Fictional passage", "reason": "insufficient_evidence"}], [], "recorded-replay", "replay")
        model = self.store.save_investigation("CASE-ALPHA", question, "evidence-summary", result,
            "replay", context_fingerprint=context["fingerprint"])
        return question, snapshot, model, context

    def amendment(self):
        raw = text_pdf([["Independent fictional report", "No clinical interpretation."],
                        ["Marker P remains pending."]])
        preview = self.store.preview_document("CASE-ALPHA", raw, "amended.pdf")
        return {"raw": raw, "filename": "amended.pdf", "metadata": {**self.metadata, "amends_version": 1},
                "findings": [{"key": "marker-p", "state": "pending", "quote": "Marker P remains pending.", "line": 3}],
                "expected_sha256": preview["sha256"], "expected_extraction_sha256": preview["extraction_sha256"]}

    def test_preview_is_read_only_and_preserves_physical_page_two_without_assertions(self):
        before = self.ledger()
        preview = self.store.preview_document("CASE-ALPHA", self.raw, "fictional.pdf")
        self.assertEqual(self.ledger(), before)
        self.assertEqual(preview["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(preview["media_type"], "application/pdf")
        self.assertEqual(preview["lines"][2], {"line": 3, "page": 2, "page_line": 1,
                                               "text": "Marker P was not assessed."})
        self.assertEqual(preview["clinical_review"], "not_performed")
        self.assertEqual(self.store.state("CASE-ALPHA")["assertions"], [])

    def test_restart_retains_original_binary_and_frozen_rendition_without_reparsing(self):
        imported = self.commit()
        question, snapshot, _, _ = self.add_work(imported["source_id"])
        before = self.store.state("CASE-ALPHA")
        self.store.close()
        self.store = CaseStore(self.path)
        # Reading a saved record must work even if extraction later becomes unavailable.
        with patch("open_intelligence.pdf_intake.extract_pdf", side_effect=AssertionError("Unexpected reparse")):
            original = self.store.source_document("CASE-ALPHA", imported["source_id"])
            view = self.store.source_view("CASE-ALPHA", imported["source_id"])
            self.assertEqual(original["raw"], self.raw)
            self.assertEqual(original["media_type"], "application/pdf")
            self.assertEqual(original["sha256"], hashlib.sha256(self.raw).hexdigest())
            self.assertEqual(view["text"], "Independent fictional report\nNo clinical interpretation.\nMarker P was not assessed.")
            self.assertEqual(view["text_origin"], "pdf_extraction")
            self.assertEqual(view["extraction_sha256"], self.preview["extraction_sha256"])
            self.assertEqual(view["pages"][1]["text"], "Marker P was not assessed.\n")
            self.assertEqual(self.store.state("CASE-ALPHA"), before)
            self.assertEqual(self.store.source_text("CASE-ALPHA", imported["source_id"]), view["text"])
            self.assertIn("Marker P was not assessed.", self.store.export_markdown("CASE-ALPHA", snapshot))
            self.assertTrue(build_composer_context(self.store, "CASE-ALPHA", question)["source_anchors"])

    def test_page_anchor_and_manual_missingness_survive_every_existing_consumer(self):
        self.commit()
        question = self.store.add_question("CASE-ALPHA", "What does the exact passage support?")
        state = self.store.state("CASE-ALPHA")
        facts = self.store.investigation_facts("CASE-ALPHA", question)
        context = build_composer_context(self.store, "CASE-ALPHA", question)
        rows = {"state": state["assertions"][0], "investigation": facts["assertions"][0],
                "composer": context["source_anchors"][0], "mission": build_patient_mission(state)["what_we_know"][0],
                "timeline": case_timeline(self.store, "CASE-ALPHA")["entries"][0]["reported_findings"][0],
                "changes": changes_since_review(self.store, "CASE-ALPHA")["new_sources"][0]["reported_findings"][0]}
        for consumer, row in rows.items():
            with self.subTest(consumer=consumer):
                self.assertEqual(row["classification_origin"], "user_selected")
                self.assertEqual(row["clinical_review"], "not_performed")
                self.assertEqual(row["text_origin"], "pdf_extraction")
                self.assertEqual(row.get("source_page"), 2)
                self.assertEqual(row.get("page_line"), 1)
                self.assertEqual(row["extraction_sha256"], self.preview["extraction_sha256"])
                self.assertEqual(row["page_text_sha256"], hashlib.sha256(b"Marker P was not assessed.\n").hexdigest())
        self.assertEqual(state["assertions"][0]["certainty"], "not-assessed")
        self.assertEqual(context["source_anchors"][0]["reported_state"], "not-assessed")
        self.assertEqual(context["fingerprint"], composer_context_fingerprint(self.store, "CASE-ALPHA", question))
        prompt = build_prompt("evidence-summary", facts["question"]["question"], facts["assertions"], facts["assessments"])
        for text in ("user_selected_status=not-assessed", "classification_origin=user_selected",
                     "source_page=2", "page_line=1", "extraction_line=3", self.preview["extraction_sha256"],
                     "clinical_review=not_performed", "quote='Marker P was not assessed.'"):
            self.assertIn(text, prompt)
        self.assertNotIn("certainty=negative", prompt)

    def test_original_and_extraction_identity_mismatches_reject_without_writes(self):
        before = self.ledger()
        for overrides in ({"expected_sha256": "0" * 64}, {"expected_extraction_sha256": "0" * 64},
                          {"expected_extraction_sha256": None}, {"expected_extraction_sha256": "malformed"},
                          {"confirmed_case_id": "CASE-BETA"}, {"confirmed_case_id": True}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(InvalidInput):
                    self.commit(**overrides)
                self.assertEqual(self.ledger(), before)

    def test_forged_quote_line_or_client_page_fields_cannot_create_an_assertion(self):
        before = self.ledger()
        for change in ({"quote": "Marker P was negative."}, {"line": 1}, {"line": True},
                       {"line": 4}, {"page": 1}, {"page_line": 99}, {"source_page": 2}):
            with self.subTest(change=change):
                with self.assertRaises(InvalidInput):
                    self.commit(findings=[{**self.findings[0], **change}])
                self.assertEqual(self.ledger(), before)

    def test_duplicate_review_is_noop_but_changed_annotations_and_original_only_edit_are_rejected(self):
        first = self.commit()
        before = self.ledger()
        duplicate = self.commit(filename="renamed.pdf")
        self.assertEqual(duplicate, {"result": "duplicate", "source_id": first["source_id"], "version": 1})
        self.assertEqual(self.ledger(), before)
        self.assertEqual(self.store.source_document("CASE-ALPHA", first["source_id"])["filename"], "fictional.pdf")
        for changes in ({"findings": []}, {"findings": [{**self.findings[0], "state": "negative"}]},
                        {"metadata": {**self.metadata, "document_id": "DIFFERENT-DOCUMENT"}}):
            with self.assertRaises(InvalidInput):
                self.commit(**changes)
            self.assertEqual(self.ledger(), before)
        self.commit(case_id="CASE-BETA", confirmed_case_id="CASE-BETA", findings=[])
        before = self.ledger()
        self.assertEqual(self.store.state("CASE-BETA")["assertions"], [])
        with self.assertRaises(InvalidInput):
            self.commit(case_id="CASE-BETA", confirmed_case_id="CASE-BETA")
        self.assertEqual(self.ledger(), before)

    def test_wrong_case_read_and_unknown_case_preview_do_not_expose_source(self):
        source_id = self.commit()["source_id"]
        before = self.ledger()
        for reader in (self.store.source_document, self.store.source_view, self.store.source_text):
            with self.assertRaises(InvalidInput):
                reader("CASE-BETA", source_id)
        with self.assertRaises(InvalidInput):
            self.store.preview_document("CASE-UNKNOWN", self.raw, "fictional.pdf")
        self.assertEqual(self.ledger(), before)

    def test_encrypted_and_image_only_extraction_failures_leave_entire_ledger_unchanged(self):
        self.commit()
        before = self.ledger()
        for raw in (encrypted_pdf(empty_password=True),
                    streams_pdf([b"q 100 0 0 100 36 600 cm /Im0 Do Q"], image_pages=(0,))):
            with self.subTest(prefix=raw[:8]):
                with self.assertRaises(InvalidInput):
                    self.store.preview_document("CASE-ALPHA", raw, "unsupported.pdf")
                with self.assertRaises(InvalidInput):
                    self.commit(raw=raw, expected_sha256=hashlib.sha256(raw).hexdigest())
                self.assertEqual(self.ledger(), before)

    def test_rendition_or_receipt_insert_failure_rolls_back_sources_events_and_invalidation(self):
        first = self.commit()
        _, snapshot, model, _ = self.add_work(first["source_id"])
        amendment = self.amendment()
        for table in ("source_text_renditions", "document_intake_metadata"):
            with self.subTest(table=table):
                self.store.db.execute(f"CREATE TRIGGER reject_pdf_child BEFORE INSERT ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'intentional integration failure'); END")
                self.store.db.commit()
                before = self.ledger()
                with self.assertRaises(sqlite3.IntegrityError):
                    self.commit(**amendment)
                self.assertEqual(self.ledger(), before)
                self.assertFalse(self.store.get_investigation("CASE-ALPHA", model)["stale"])
                self.assertEqual(self.store.state("CASE-ALPHA")["snapshots"][0]["state"], "draft")
                self.assertEqual(self.store.source_document("CASE-ALPHA", first["source_id"])["raw"], self.raw)
                self.store.db.execute("DROP TRIGGER reject_pdf_child")
                self.store.db.commit()

    def test_amendment_reopens_question_stales_work_and_retains_original_rendition_and_export(self):
        first = self.commit()
        question, snapshot, model, context = self.add_work(first["source_id"])
        # A recorded, unreviewed model attempt must not complete the human question.
        self.assertEqual(self.store.state("CASE-ALPHA")["questions"][0]["state"], "open")
        self.store.acknowledge_demo_review("CASE-ALPHA", snapshot, "Unverified synthetic reviewer")
        self.assertEqual(self.store.state("CASE-ALPHA")["questions"][0]["state"], "addressed")
        amendment = self.amendment()
        updated = self.commit(**amendment)
        self.assertIn(snapshot, updated["invalidated_snapshots"])
        self.assertIn(model, updated["invalidated_model_investigation_ids"])
        self.assertTrue(self.store.get_investigation("CASE-ALPHA", model)["stale"])
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(state["questions"][0]["state"], "open")
        self.assertEqual(state["snapshots"][0]["state"], "stale")
        self.assertEqual(state["assertions"][0]["certainty"], "pending")
        self.assertNotEqual(build_composer_context(self.store, "CASE-ALPHA", question)["fingerprint"], context["fingerprint"])
        self.assertEqual(self.store.source_document("CASE-ALPHA", first["source_id"])["raw"], self.raw)
        self.assertEqual(self.store.source_document("CASE-ALPHA", updated["source_id"])["raw"], amendment["raw"])
        exported = self.store.export_markdown("CASE-ALPHA", snapshot)
        for text in ("**stale**", "Marker P was not assessed.", "3 → 2 / 1", self.preview["extraction_sha256"],
                     self.preview["sha256"], "classification_origin=user_selected", "clinical_review=not_performed"):
            self.assertIn(text, exported)
        self.assertNotIn("Marker P remains pending.", exported)
        result = ValidatedInvestigation("abstained", [], [], [], "recorded-replay", "replay")
        with self.assertRaisesRegex(InvalidInput, "stale"):
            self.store.save_investigation("CASE-ALPHA", question, "evidence-summary", result, "replay",
                                         context_fingerprint=context["fingerprint"])
        self.assertEqual(self.store.state("CASE-BETA")["sources"], [])

    def test_persisted_extraction_cannot_be_updated_or_deleted(self):
        source_id = self.commit()["source_id"]
        before = self.ledger()
        for statement in ("UPDATE source_text_renditions SET text='forged' WHERE source_version_id=?",
                          "DELETE FROM source_text_renditions WHERE source_version_id=?"):
            with self.assertRaises(sqlite3.IntegrityError):
                with self.store.db:
                    self.store.db.execute(statement, (source_id,))
            self.assertEqual(self.ledger(), before)

    def test_text_intake_still_preserves_bom_crlf_and_has_no_pdf_rendition(self):
        raw = b"\xef\xbb\xbfIndependent fictional note\r\nReview pending.\r\n"
        preview = self.store.preview_document("CASE-ALPHA", raw, "legacy.txt")
        source = self.store.import_document("CASE-ALPHA", raw, "legacy.txt",
            {**self.metadata, "document_id": "TEXT-ALPHA"}, [], preview["sha256"], "CASE-ALPHA")
        view = self.store.source_view("CASE-ALPHA", source["source_id"])
        self.assertEqual(view["text"].encode(), raw)
        self.assertEqual(view["text_origin"], "original")
        self.assertEqual(view["media_type"], "text/plain; charset=utf-8")
        self.assertNotIn("extraction_sha256", view)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM source_text_renditions").fetchone()[0], 0)
        self.assertEqual(self.store.source_document("CASE-ALPHA", source["source_id"])["raw"], raw)


if __name__ == "__main__":
    unittest.main()
