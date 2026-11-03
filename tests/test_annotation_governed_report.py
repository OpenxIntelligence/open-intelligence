"""Annotation identity survives the real fictional governed report workflow.

These tests use only independently authored text/PDF originals and permitted
fictional evidence. No medical source, network provider or live model is used.
"""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.store import CaseStore, InvalidInput
import test_pdf_governed_report as fixture

CASE, REASON = fixture.CASE, fixture.REASON


REVISION_FIELDS = ("annotation_revision_id", "annotation_revision")


class AnnotationGovernedReportTests(unittest.TestCase):
    setUp = fixture.PdfGovernedReportTests.setUp
    actor = fixture.PdfGovernedReportTests.actor
    workflow = fixture.PdfGovernedReportTests.workflow
    _source = fixture.PdfGovernedReportTests._source
    prepare = fixture.PdfGovernedReportTests.prepare
    attach = fixture.PdfGovernedReportTests.attach
    send = fixture.PdfGovernedReportTests.send
    review_writes = fixture.PdfGovernedReportTests.review_writes
    prepared = fixture.PdfGovernedReportTests.prepared

    def build(self, media="text"):
        scope = fixture.PdfGovernedReportTests.build(self, media)
        self.bind(scope, proposals=True, quotes=True)
        return scope

    @staticmethod
    def bind(scope, *, proposals=False, quotes=False):
        rows = (scope["proposals"] if proposals else []) + (scope["quotes"] if quotes else [])
        for row in rows:
            row["assertion_id"] = scope["assertion"]["id"]
            for key in REVISION_FIELDS:
                row[key] = scope["assertion"][key]

    def revise(self, scope, *, state="pending"):
        current = next(a for a in self.store.state(CASE)["assertions"]
                       if a["source_version_id"] == scope["source_id"])
        result = self.store.revise_document_annotations(
            CASE, scope["source_id"], [{**scope["findings"][0], "state": state}],
            current["annotation_revision"], hashlib.sha256(scope["raw"]).hexdigest(),
            CASE, True, "Correct the independently fictional manual classification.",
            **scope["options"])
        scope["assertion"] = next(a for a in self.store.state(CASE)["assertions"]
                                  if a["source_version_id"] == scope["source_id"])
        return result

    def preview(self, scope):
        return scope["service"].report.packets.preview(
            self.patient_id, CASE, scope["question"], selected_quotes=scope["quotes"],
            **self.actor())

    def test_manual_comparison_cannot_omit_captured_revision(self):
        scope = self.build()
        for field in REVISION_FIELDS:
            changed = scope["proposals"][0].pop(field)
            with self.subTest(field=field), self.assertRaises(KnowledgeContextError):
                scope["bridge"].snapshot(self.patient_id, CASE, scope["question"], **self.actor())
            scope["proposals"][0][field] = changed
        for row in scope["proposals"]:
            for field in REVISION_FIELDS:
                row.pop(field)
        with self.assertRaises(KnowledgeContextError):
            scope["bridge"].snapshot(self.patient_id, CASE, scope["question"], **self.actor())
        self.assertEqual(self.review_writes(), (0, 0))

    def test_manual_selected_quote_cannot_omit_captured_revision(self):
        scope = self.build()
        for field in REVISION_FIELDS:
            scope["quotes"][0].pop(field)
        with self.assertRaises(KnowledgeContextError):
            self.preview(scope)
        self.assertEqual(self.review_writes(), (0, 0))

    def test_reused_assertion_id_does_not_retarget_old_comparison(self):
        scope = self.build()
        original = deepcopy(scope["assertion"])
        self.revise(scope)
        # This is the actual SQLite reuse that makes an assertion-only input unsafe.
        self.assertEqual(scope["assertion"]["id"], original["id"])
        self.assertNotEqual(scope["assertion"]["annotation_revision_id"], original["annotation_revision_id"])
        with self.assertRaises(KnowledgeContextError):
            self.send(scope)
        self.assertEqual(self.review_writes(), (0, 0))

    def test_refreshed_comparison_does_not_retarget_an_old_quote_selection(self):
        scope = self.build()
        self.revise(scope)
        self.bind(scope, proposals=True)
        with self.assertRaises(KnowledgeContextError):
            self.send(scope)
        self.assertEqual(self.review_writes(), (0, 0))
        self.bind(scope, quotes=True)
        self.assertEqual(self.send(scope)["human_review_state"], "pending")
        self.assertEqual(self.review_writes(), (1, 1))

    def check_corrected_report(self, media):
        scope = self.build(media)
        initial = deepcopy(scope["assertion"])
        self.revise(scope)
        self.bind(scope, proposals=True, quotes=True)
        reference = self.preview(scope)["quoted_comparisons"][0]["patient_reference"]
        self.assertEqual(reference["annotation_revision"], 2)
        self.assertEqual(reference["annotation_revision_id"], scope["assertion"]["annotation_revision_id"])
        self.assertEqual(reference["initial_transcription_review_sha256"], initial["transcription_review_sha256"])
        self.assertNotEqual(reference["transcription_review_sha256"], initial["transcription_review_sha256"])
        result = self.send(scope)
        body = result["report"]["body"]
        self.assertIn(f"Annotation revision: 2; revision ID: {reference['annotation_revision_id']}", body)
        self.assertIn(f"Initial transcription review SHA-256: {initial['transcription_review_sha256']}", body)
        self.assertIn(f"Transcription review SHA-256: {reference['transcription_review_sha256']}", body)
        self.assertIn('User-selected status: "pending"', body)
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        captured = json.loads(event["details"])["prepared_report"]["patient_source"]
        for field in REVISION_FIELDS + ("initial_transcription_review_sha256", "transcription_review_sha256"):
            self.assertEqual(captured[field], reference[field])
        if media == "pdf":
            self.assertEqual(captured["source_page"], 2)
            self.assertEqual(captured["page_line"], 1)
            self.assertEqual(captured["extraction_sha256"], scope["preview"]["extraction_sha256"])
        else:
            self.assertNotIn("source_page", captured)
        self.assertEqual(self.review_writes(), (1, 1))

    def test_corrected_text_report_and_receipt_preserve_initial_and_effective_revision(self):
        self.check_corrected_report("text")

    def test_corrected_pdf_report_and_receipt_preserve_initial_effective_and_page_identity(self):
        self.check_corrected_report("pdf")

    def test_return_to_original_selection_does_not_revive_old_inputs_or_context(self):
        scope = self.build()
        original = deepcopy(scope["assertion"])
        first = self.preview(scope)
        self.revise(scope)
        self.revise(scope, state="not-assessed")
        self.assertEqual(scope["assertion"]["transcription_review_sha256"], original["transcription_review_sha256"])
        self.assertEqual(scope["assertion"]["id"], original["id"])
        self.assertEqual(scope["assertion"]["annotation_revision"], 3)
        with self.assertRaises(KnowledgeContextError):
            self.send(scope)
        self.assertEqual(self.review_writes(), (0, 0))
        self.bind(scope, proposals=True, quotes=True)
        latest = self.preview(scope)
        self.assertNotEqual(latest["composer_context_fingerprint"], first["composer_context_fingerprint"])
        self.assertNotEqual(latest["review_context_sha256"], first["review_context_sha256"])
        self.assertIn("Annotation revision: 3;", self.send(scope)["report"]["body"])

    def test_receipt_rejects_omitted_malformed_or_misbound_revision_before_writes(self):
        scope = self.build()
        preview, prepared = self.prepared(scope)
        for field in REVISION_FIELDS:
            for invalid in (None, True, False, 0, -1, 2**63, "1", 1.0, prepared["patient_source"][field] + 1):
                changed = deepcopy(prepared)
                if invalid is None:
                    changed["patient_source"].pop(field)
                else:
                    changed["patient_source"][field] = invalid
                with self.subTest(field=field, value=invalid), self.assertRaises(InvalidInput):
                    self.store.add_review_receipt(
                        CASE, preview["queue_key"], "returned", self.actor()["actor"], REASON,
                        expected_fingerprint=preview["queue_fingerprint"], prepared_report=changed)
                self.assertEqual(self.review_writes(), (0, 0))
        result = self.store.add_review_receipt(
            CASE, preview["queue_key"], "returned", self.actor()["actor"], REASON,
            expected_fingerprint=preview["queue_fingerprint"], prepared_report=prepared)
        self.assertIsInstance(result["receipt_id"], int)
        self.assertEqual(self.review_writes(), (1, 1))

    def test_receipt_does_not_accept_old_identity_after_selection_returns(self):
        scope = self.build()
        preview, prepared = self.prepared(scope)
        self.revise(scope)
        self.revise(scope, state="not-assessed")
        with self.assertRaises(InvalidInput):
            self.store.add_review_receipt(
                CASE, preview["queue_key"], "returned", self.actor()["actor"], REASON,
                expected_fingerprint=preview["queue_fingerprint"], prepared_report=prepared)
        self.assertEqual(self.review_writes(), (0, 0))

    def test_annotation_change_at_receipt_boundary_refuses_write(self):
        scope = self.build()
        original_write = self.store.add_review_receipt

        def change_then_write(*args, **kwargs):
            self.revise(scope)
            return original_write(*args, **kwargs)

        with patch.object(self.store, "add_review_receipt", side_effect=change_then_write):
            with self.assertRaises((InvalidInput, KnowledgeContextError, ClinicalContinuityError)):
                self.send(scope)
        self.assertEqual(self.review_writes(), (0, 0))

    def test_late_annotation_change_withholds_body_but_preserves_preparation(self):
        scope = self.build()
        initial = deepcopy(scope["assertion"])
        original_write = self.store.add_review_receipt

        def write_then_change(*args, **kwargs):
            result = original_write(*args, **kwargs)
            self.revise(scope)
            return result

        with patch.object(self.store, "add_review_receipt", side_effect=write_then_change):
            with self.assertRaises((InvalidInput, KnowledgeContextError, ClinicalContinuityError)):
                self.send(scope)
        self.assertEqual(self.review_writes(), (1, 1))
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        prepared = json.loads(event["details"])["prepared_report"]
        self.assertEqual(prepared["semantics"], "prepared_not_delivery_or_approval")
        self.assertEqual(prepared["patient_source"]["annotation_revision_id"], initial["annotation_revision_id"])
        self.assertEqual(prepared["patient_source"]["annotation_revision"], 1)
        self.assertEqual(scope["assertion"]["annotation_revision"], 2)
        self.assertEqual(self.store.review_queue(CASE)["receipts"][0]["action"], "returned")

    def test_proposal_and_quote_revision_inputs_reject_boolean_overflow_and_wrong_identity(self):
        scope = self.build()
        self.preview(scope)
        for collection in ("proposals", "quotes"):
            for field in REVISION_FIELDS:
                original = scope[collection][0][field]
                for invalid in (True, False, 0, -1, 2**63, "1", 1.0, original + 1):
                    scope[collection][0][field] = invalid
                    with self.subTest(collection=collection, field=field, value=invalid):
                        with self.assertRaises(KnowledgeContextError):
                            self.preview(scope)
                    self.assertEqual(self.review_writes(), (0, 0))
                scope[collection][0][field] = original
        self.preview(scope)

    def test_initial_receipt_and_original_survive_correction_and_restart(self):
        scope = self.build("pdf")
        first = self.send(scope)
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        self.revise(scope)
        self.bind(scope, proposals=True, quotes=True)
        second = self.send(scope)
        self.assertNotEqual(first["report"]["body_sha256"], second["report"]["body_sha256"])
        self.assertIn("Annotation revision: 1;", first["report"]["body"])
        self.assertIn("Annotation revision: 2;", second["report"]["body"])
        path = self.store.path
        self.store.close()
        reopened = CaseStore(path)
        try:
            state = reopened.state(CASE)
            self.assertEqual(reopened.source_document(CASE, scope["source_id"])["raw"], scope["raw"])
            self.assertEqual(next(e["details"] for e in state["events"] if e["id"] == event["id"]), event["details"])
            self.assertEqual(json.loads(event["details"])["prepared_report"]["patient_source"]["annotation_revision"], 1)
            self.assertEqual(len(reopened.review_queue(CASE)["receipts"]), 2)
            self.assertEqual(next(a for a in state["assertions"] if a["source_version_id"] == scope["source_id"])["annotation_revision"], 2)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
