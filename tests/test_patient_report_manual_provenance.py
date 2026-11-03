"""Readable reports retain real fictional intake provenance without promoting it."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from open_intelligence.patient_report import build_patient_report, render_text
from open_intelligence.store import CaseStore, InvalidInput
from pdf_fixtures import text_pdf
import test_pdf_document_intake_http as intake_http


class PatientReportManualProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "manual-report.sqlite"
        self.store = CaseStore(self.db_path)
        self.store.add_case("CASE-ALPHA", "Independent fictional report case")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def import_manual(self, *, pdf=True, amended=False):
        quote = "Marker P remains pending." if amended else "Marker P was not assessed."
        raw = (text_pdf([["Independent fictional record"], [quote]]) if pdf else
               ("Independent fictional record\n" + quote + "\n").encode())
        name = "fictional.pdf" if pdf else "fictional.txt"
        preview = self.store.preview_document("CASE-ALPHA", raw, name)
        metadata = {"document_id": "DOC-MANUAL", "kind": "pathology",
                    "event_date": "2026-07-01", "issued_at": "2026-07-03" if amended else "2026-07-02",
                    "manual_transcription_confirmed": True}
        if amended:
            metadata["amends_version"] = 1
        saved = self.store.import_document(
            "CASE-ALPHA", raw, name, metadata=metadata,
            findings=[{"key": "marker-p", "state": "pending" if amended else "not-assessed",
                       "quote": quote, "line": 2}],
            expected_sha256=preview["sha256"], confirmed_case_id="CASE-ALPHA",
            expected_extraction_sha256=preview.get("extraction_sha256"))
        return raw, preview, saved["source_id"]

    @staticmethod
    def item(payload):
        return next(section for section in payload["sections"] if section["id"] == "overview")["items"][0]

    def test_pdf_report_retains_page_identity_and_does_not_call_manual_status_source_authored(self):
        raw, preview, source_id = self.import_manual()
        state = self.store.state("CASE-ALPHA")
        untouched = copy.deepcopy(state)
        ledger = tuple(self.store.db.iterdump())
        payload = build_patient_report(state)
        item = self.item(payload)
        self.assertIn("user-selected status", item["detail"])
        self.assertNotIn("source states", item["detail"])
        self.assertIn("Clinical review not performed", item["detail"])
        self.assertEqual(item["text"], "Marker P was not assessed.")
        reference = item.get("source_reference", {})
        self.assertEqual(reference.get("source_version_id"), source_id)
        self.assertEqual(reference.get("document_id"), "DOC-MANUAL")
        self.assertEqual(reference.get("document_version"), 1)
        self.assertEqual(reference.get("classification_origin"), "user_selected")
        self.assertEqual(reference.get("annotation_method"), "manual-exact-extraction-line-selection")
        self.assertEqual(reference.get("clinical_review"), "not_performed")
        self.assertEqual(reference.get("text_origin"), "pdf_extraction")
        self.assertEqual(reference.get("source_line"), 2)
        self.assertEqual(reference.get("source_page"), 2)
        self.assertEqual(reference.get("page_line"), 1)
        self.assertEqual(reference.get("sha256"), hashlib.sha256(raw).hexdigest())
        self.assertEqual(reference.get("extraction_sha256"), preview["extraction_sha256"])
        self.assertEqual(reference.get("page_text_sha256"), hashlib.sha256(b"Marker P was not assessed.\n").hexdigest())
        self.assertEqual(reference.get("transcription_review_sha256"), state["sources"][0]["document_intake"]["review_sha256"])
        revision = self.store.document_annotations("CASE-ALPHA", source_id)["current_revision"]
        self.assertEqual(reference.get("annotation_revision_id"), revision["id"])
        self.assertEqual(reference.get("annotation_revision"), 1)
        self.assertEqual(reference.get("initial_transcription_review_sha256"), revision["review_sha256"])
        text = render_text(payload)
        for value in ("physical page 2", "page line 1", "global extraction line 2",
                      f"Annotation revision: 1; revision ID: {revision['id']}",
                      "Initial transcription review SHA-256: " + revision["review_sha256"],
                      "Transcription review SHA-256: " + revision["review_sha256"],
                      reference["sha256"], reference["extraction_sha256"],
                      reference["page_text_sha256"], reference["transcription_review_sha256"]):
            self.assertIn(value, item["citation"])
            self.assertIn(value, text)
        self.assertEqual(state, untouched)
        self.assertEqual(tuple(self.store.db.iterdump()), ledger)

    def test_readable_report_keeps_revision_identity_and_both_hashes_through_correction_revert_and_restart(self):
        for pdf in (False, True):
            with self.subTest(pdf=pdf):
                # A separate source is used for each format without changing the
                # shared source, annotation or historical report owners.
                self.store.close()
                self.store = CaseStore(Path(self.temp.name) / f"revisions-{pdf}.sqlite")
                self.store.add_case("CASE-ALPHA", "Independent fictional report case")
                raw, preview, source_id = self.import_manual(pdf=pdf)
                first = self.store.document_annotations("CASE-ALPHA", source_id)["current_revision"]
                initial_report = build_patient_report(self.store.state("CASE-ALPHA"))
                initial_text = render_text(initial_report)
                initial_reference = copy.deepcopy(self.item(initial_report)["source_reference"])
                corrected = self.store.revise_document_annotations(
                    "CASE-ALPHA", source_id,
                    findings=[{"key": "marker-p", "state": "pending",
                               "quote": "Marker P was not assessed.", "line": 2}],
                    expected_revision=1, expected_sha256=preview["sha256"],
                    confirmed_case_id="CASE-ALPHA", manual_transcription_confirmed=True,
                    reason="Record a different fictional user-selected classification.",
                    **({"expected_extraction_sha256": preview["extraction_sha256"]} if pdf else {}))
                current_report = build_patient_report(self.store.state("CASE-ALPHA"))
                reference = self.item(current_report)["source_reference"]
                self.assertEqual(reference.get("annotation_revision"), 2)
                self.assertEqual(reference.get("annotation_revision_id"), corrected["annotation_revision_id"])
                self.assertNotEqual(reference["annotation_revision_id"], first["id"])
                self.assertEqual(reference.get("initial_transcription_review_sha256"), first["review_sha256"])
                self.assertEqual(reference["transcription_review_sha256"], corrected["review_sha256"])
                self.assertNotEqual(reference["transcription_review_sha256"], first["review_sha256"])
                self.assertEqual(reference["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(reference["document_version"], 1)
                self.assertEqual(self.item(initial_report)["source_reference"], initial_reference)
                self.assertEqual(render_text(initial_report), initial_text)
                self.assertIn("Annotation revision: 1;", initial_text)
                self.assertNotIn(corrected["review_sha256"], initial_text)
                for digest_label, digest in (
                    ("Initial transcription review", first["review_sha256"]),
                    ("Transcription review", corrected["review_sha256"]),
                ):
                    self.assertIn(f"{digest_label} SHA-256: {digest}", render_text(current_report))
                reverted = self.store.revise_document_annotations(
                    "CASE-ALPHA", source_id, findings=first["findings"],
                    expected_revision=2, expected_sha256=preview["sha256"],
                    confirmed_case_id="CASE-ALPHA", manual_transcription_confirmed=True,
                    reason="Return to the original fictional classification while retaining history.",
                    **({"expected_extraction_sha256": preview["extraction_sha256"]} if pdf else {}))
                reverted_report = build_patient_report(self.store.state("CASE-ALPHA"))
                reverted_reference = self.item(reverted_report)["source_reference"]
                self.assertEqual(reverted_reference["annotation_revision"], 3)
                self.assertEqual(reverted_reference["annotation_revision_id"], reverted["annotation_revision_id"])
                self.assertNotEqual(reverted_reference["annotation_revision_id"], first["id"])
                self.assertEqual(reverted_reference["transcription_review_sha256"], first["review_sha256"])
                before_restart = render_text(reverted_report)
                path = Path(self.temp.name) / f"revisions-{pdf}.sqlite"
                self.store.close()
                self.store = CaseStore(path)
                self.assertEqual(render_text(build_patient_report(self.store.state("CASE-ALPHA"))), before_restart)
                self.assertEqual(self.store.source_document("CASE-ALPHA", source_id)["raw"], raw)
                self.assertEqual([row["revision"] for row in self.store.document_annotations(
                    "CASE-ALPHA", source_id)["history"]], [1, 2, 3])

    def test_revision_type_and_source_association_mismatches_refuse_readable_reports(self):
        _, _, source_id = self.import_manual()
        base = self.store.state("CASE-ALPHA")
        revision = self.store.document_annotations("CASE-ALPHA", source_id)["current_revision"]
        changes = [
            lambda state: state["assertions"][0].pop("annotation_revision_id"),
            lambda state: state["assertions"][0].update(annotation_revision_id=revision["id"] + 1),
            lambda state: state["assertions"][0].update(annotation_revision=2),
            lambda state: state["assertions"][0].pop("initial_transcription_review_sha256"),
            lambda state: state["assertions"][0].update(initial_transcription_review_sha256="0" * 64),
            lambda state: state["sources"][0].update(id=True),
        ]
        for field, receipt_field in (
            ("annotation_revision_id", "annotation_revision_id"),
            ("annotation_revision", "annotation_revision"),
            ("initial_transcription_review_sha256", "initial_review_sha256"),
        ):
            for value in ((True, 0, -1, 1.0, "1", 2 ** 63) if field != "initial_transcription_review_sha256"
                          else (True, None, "not-a-digest", "A" * 64)):
                def corrupt_together(state, field=field, receipt_field=receipt_field, value=value):
                    state["assertions"][0][field] = value
                    state["sources"][0][field] = value
                    state["sources"][0]["document_intake"][receipt_field] = value
                changes.append(corrupt_together)
        ledger = tuple(self.store.db.iterdump())
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                altered = copy.deepcopy(base)
                change(altered)
                with self.assertRaises(InvalidInput):
                    build_patient_report(altered)
        self.assertEqual(tuple(self.store.db.iterdump()), ledger)

    def test_manual_text_report_preserves_manual_review_without_claiming_pdf_extraction(self):
        raw, _, source_id = self.import_manual(pdf=False)
        item = self.item(build_patient_report(self.store.state("CASE-ALPHA")))
        self.assertIn("user-selected status", item["detail"])
        self.assertNotIn("source states", item["detail"])
        reference = item.get("source_reference", {})
        self.assertEqual(reference.get("source_version_id"), source_id)
        self.assertEqual(reference.get("classification_origin"), "user_selected")
        self.assertEqual(reference.get("annotation_method"), "manual-exact-line-selection")
        self.assertEqual(reference.get("sha256"), hashlib.sha256(raw).hexdigest())
        self.assertEqual(reference.get("source_line"), 2)
        for field in ("source_page", "page_line", "page_text_sha256", "extraction_sha256", "text_origin"):
            self.assertNotIn(field, reference)
        self.assertNotIn("extraction", item["citation"])

    def test_missing_or_inconsistent_manual_provenance_refuses_a_readable_report(self):
        self.import_manual()
        base = self.store.state("CASE-ALPHA")
        ledger = tuple(self.store.db.iterdump())
        changes = (
            lambda state: state["assertions"][0].pop("classification_origin"),
            lambda state: state["assertions"][0].update(clinical_review="approved"),
            lambda state: state["assertions"][0].update(transcription_review_sha256="0" * 64),
            lambda state: state["assertions"][0].update(extraction_sha256="0" * 64),
            lambda state: state["assertions"][0].update(source_page=True),
            lambda state: state["assertions"][0].update(page_line=3),
            lambda state: state["assertions"][0].pop("page_text_sha256"),
            lambda state: state["sources"][0].pop("document_intake"),
            lambda state: state.update(sources=[]),
        )
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                state = copy.deepcopy(base)
                change(state)
                with self.assertRaises(InvalidInput):
                    build_patient_report(state)
        self.assertEqual(tuple(self.store.db.iterdump()), ledger)

    def test_amendment_and_restart_keep_the_readable_report_bound_to_current_pdf(self):
        first_raw, _, first_id = self.import_manual()
        prior_report = build_patient_report(self.store.state("CASE-ALPHA"))
        amended_raw, _, amended_id = self.import_manual(amended=True)
        current_report = build_patient_report(self.store.state("CASE-ALPHA"))
        item = self.item(current_report)
        self.assertEqual(item.get("source_reference", {}).get("source_version_id"), amended_id)
        self.assertEqual(item["source_reference"]["sha256"], hashlib.sha256(amended_raw).hexdigest())
        self.assertEqual(item["source_reference"]["document_version"], 2)
        self.assertEqual(item["text"], "Marker P remains pending.")
        self.assertEqual(self.item(prior_report)["source_reference"]["source_version_id"], first_id)
        self.assertEqual(self.item(prior_report)["source_reference"]["sha256"], hashlib.sha256(first_raw).hexdigest())
        before_restart = render_text(current_report)
        self.store.close()
        self.store = CaseStore(self.db_path)
        self.assertEqual(render_text(build_patient_report(self.store.state("CASE-ALPHA"))), before_restart)
        self.assertEqual(self.store.source_document("CASE-ALPHA", first_id)["raw"], first_raw)


class PdfReadableReportHttpTests(unittest.TestCase):
    def setUp(self):
        self.fixture = intake_http.PdfDocumentIntakeHttpTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_pdf_intake_and_followthrough_share_the_existing_readable_report_routes(self):
        fixture = self.fixture
        source_id = fixture.commit()
        status, created, _ = fixture.request("/api/cases/CASE-ALPHA/followthrough-tasks", {
            "title": "Prepare the fictional PDF discussion", "source_version_id": source_id,
            "actor_label": "Fictional recorder", "reason": "Keep the source question visible."})
        self.assertEqual(status, 201, created)
        ledger = fixture.ledger()
        status, payload, _ = fixture.request("/api/cases/CASE-ALPHA/patient-report")
        self.assertEqual(status, 200, payload)
        item = PatientReportManualProvenanceTests.item(payload)
        self.assertEqual(item.get("source_reference", {}).get("source_page"), 2)
        self.assertIn("user-selected status", item["detail"])
        self.assertIn("Prepare the fictional PDF discussion", payload["text"])
        self.assertIn(f"Follow-through task #{created['task_id']}", payload["text"])
        status, exported, _ = fixture.request("/api/cases/CASE-ALPHA/patient-report?format=text")
        self.assertEqual(status, 200)
        self.assertEqual(exported.decode(), payload["text"])
        status, other, _ = fixture.request("/api/cases/CASE-BETA/patient-report")
        self.assertEqual(status, 200)
        self.assertNotIn("Marker P", other["text"])
        self.assertNotIn("fictional PDF discussion", other["text"])
        self.assertEqual(fixture.ledger(), ledger)

