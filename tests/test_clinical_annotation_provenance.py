"""Immutable fictional note links retain the annotation revision actually cited."""
from __future__ import annotations

import hashlib
import unittest

from open_intelligence.clinical_encounters import ClinicalEncounters
from open_intelligence.clinical_source_provenance import (
    ClinicalSourceProvenance, ClinicalSourceLinkError,
)
from open_intelligence.patient_registry import PatientRegistry
from open_intelligence.store import CaseStore

from pdf_fixtures import text_pdf
import test_clinical_source_provenance as source_fixture
import test_clinical_continuity as continuity_fixture


class ClinicalAnnotationProvenanceTests(unittest.TestCase):
    attach = source_fixture.ClinicalSourceProvenanceTests.attach
    read = source_fixture.ClinicalSourceProvenanceTests.read

    def setUp(self):
        source_fixture.ClinicalSourceProvenanceTests.setUp(self)
        self.authored_source = self.source
        self.raw = (b"Independently fictional annotation source.\n"
                    b"Marker Q remains unknown.\n")
        self.findings = [{"key": "marker-q", "state": "not-assessed",
                          "quote": "Marker Q remains unknown.", "line": 2}]
        metadata = {"document_id": "NOTE-ANNOTATION-SOURCE", "kind": "pathology",
                    "event_date": "2026-06-01", "issued_at": "2026-06-02",
                    "manual_transcription_confirmed": True}
        self.source = self.store.import_document(
            "CASE-ALPHA", self.raw, "fictional-note-source.txt", metadata,
            self.findings, hashlib.sha256(self.raw).hexdigest(), "CASE-ALPHA")["source_id"]
        self.source_line = 2
        self.initial = self.store.document_annotations(
            "CASE-ALPHA", self.source)["current_revision"]

    def revise(self, findings=None, expected=1):
        return self.store.revise_document_annotations(
            "CASE-ALPHA", self.source,
            [{**self.findings[0], "state": "pending"}] if findings is None else findings,
            expected, hashlib.sha256(self.raw).hexdigest(), "CASE-ALPHA", True,
            "Correct the independently fictional manually selected passage.")

    def context(self):
        return self.provenance.context_snapshot(self.patient, "CASE-ALPHA", **self.actor)

    def writes(self):
        return tuple(self.db.execute(sql).fetchone()[0] for sql in (
            "SELECT count(*) FROM clinical_note_source_refs",
            "SELECT count(*) FROM identity_domain_events"))

    def test_first_link_rejects_an_old_preview_after_a_correction_without_writes(self):
        self.revise()
        before = self.writes()
        with self.assertRaises(ClinicalSourceLinkError):
            self.attach()
        self.assertEqual(self.writes(), before)

    def test_invalid_expected_revision_types_cannot_create_a_link_or_event(self):
        for invalid in (True, False, 1.0, "1", 0, -1, 2 ** 31, []):
            with self.subTest(expected_revision=invalid):
                before = self.writes()
                with self.assertRaises(ClinicalSourceLinkError):
                    self.attach(expected_annotation_revision=invalid)
                self.assertEqual(self.writes(), before)

    def test_authored_source_rejects_an_inappropriate_annotation_revision(self):
        before = self.writes()
        with self.assertRaises(ClinicalSourceLinkError):
            self.attach(source_version_id=self.authored_source, source_line=9,
                        expected_annotation_revision=1)
        self.assertEqual(self.writes(), before)

    def test_explicit_stale_revision_cannot_create_a_link_or_event(self):
        self.revise()
        before = self.writes()
        with self.assertRaises(ClinicalSourceLinkError):
            self.attach(expected_annotation_revision=1)
        self.assertEqual(self.writes(), before)

    def test_correction_preserves_linked_selection_and_requires_note_review(self):
        self.attach()
        self.revise()
        linked = self.read()[0]
        self.assertEqual(linked["certainty"], "not-assessed")
        self.assertEqual(linked["original_statement"], "Marker Q remains unknown.")
        self.assertEqual(linked.get("annotation_revision"), 1)
        self.assertEqual(linked.get("annotation_revision_id"), self.initial["id"])
        self.assertEqual(linked.get("transcription_review_sha256"), self.initial["review_sha256"])
        self.assertEqual(linked["provenance_state"], "annotation_revision_changed_review_required")
        context = self.context()
        self.assertEqual(context["note_versions_requiring_source_review"], [self.note_version_id])
        self.assertEqual(context["note_source_links"][0].get("annotation_revision"), 1)
        current = next(a for a in context["source_reported_assertions"]
                       if a["source_version_id"] == self.source)
        self.assertEqual(current["certainty"], "pending")
        self.assertEqual(current["annotation_revision"], 2)

    def test_removed_selection_remains_inspectable_from_linked_revision(self):
        receipt = self.attach()
        self.revise(findings=[])
        linked = self.read()
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["link_id"], receipt["link_id"])
        self.assertEqual(linked[0]["original_statement"], "Marker Q remains unknown.")
        self.assertEqual(linked[0]["certainty"], "not-assessed")
        self.assertEqual(linked[0]["provenance_state"], "annotation_revision_changed_review_required")
        self.assertEqual(self.context()["note_versions_requiring_source_review"], [self.note_version_id])

    def test_revert_keeps_prior_link_stale_and_cannot_rebind_a_duplicate(self):
        self.attach()
        self.revise()
        reverted = self.revise(findings=self.findings, expected=2)
        self.assertEqual(reverted["review_sha256"], self.initial["review_sha256"])
        linked = self.read()[0]
        self.assertEqual(linked["provenance_state"], "annotation_revision_changed_review_required")
        self.assertEqual(linked.get("annotation_revision_id"), self.initial["id"])
        self.assertEqual(linked.get("annotation_revision"), 1)
        before = self.writes()
        with self.assertRaises(ClinicalSourceLinkError):
            self.attach(expected_annotation_revision=3)
        self.assertEqual(self.writes(), before)

    def test_new_note_version_can_explicitly_link_the_corrected_revision(self):
        self.attach()
        changed = self.revise()
        self.clinical.write_note(
            self.patient, self.encounter_id, "NOTE-ONE",
            "A new independently fictional note inspects the corrected selection.",
            expected_version=1, request_key="REQUEST-DRAFT-CORRECTED", **self.actor)
        current_note = self.clinical.note_history(
            self.patient, self.encounter_id, "NOTE-ONE", **self.actor)[-1]["id"]
        self.attach(note_version_id=current_note, expected_annotation_revision=2)
        current = self.read(note_version_id=current_note)[0]
        self.assertEqual(current.get("annotation_revision_id"), changed["annotation_revision_id"])
        self.assertEqual(current["provenance_state"], "current_source_unreviewed")
        self.assertEqual(current["certainty"], "pending")
        self.assertEqual(self.context()["note_versions_requiring_source_review"], [self.note_version_id])

    def test_restart_preserves_the_linked_revision_and_original_note(self):
        self.attach()
        history = self.clinical.note_history(
            self.patient, self.encounter_id, "NOTE-ONE", **self.actor)
        self.revise(findings=[])
        self.store.close()
        self.store = CaseStore(self.path)
        self.addCleanup(self.store.close)
        self.db = self.store.db
        self.registry = PatientRegistry(self.db, self.identity_policy)
        self.clinical = ClinicalEncounters(self.registry, self.clinical_policy)
        self.provenance = ClinicalSourceProvenance(
            self.registry, self.store, self.clinical_policy, self.binding_policy)
        linked = self.read()
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].get("annotation_revision_id"), self.initial["id"])
        self.assertEqual(linked[0]["original_statement"], "Marker Q remains unknown.")
        self.assertEqual(self.clinical.note_history(
            self.patient, self.encounter_id, "NOTE-ONE", **self.actor), history)

    def test_old_schema_manual_links_remain_visible_without_invented_history(self):
        # Recreate the pre-binding schema, with a real historical reference.
        # No selection version was recorded by that earlier contract.
        with self.db:
            self.db.execute("DROP TABLE clinical_note_source_refs")
            self.db.execute("""CREATE TABLE clinical_note_source_refs (
                id INTEGER PRIMARY KEY,
                patient_id TEXT NOT NULL REFERENCES identity_patients(patient_id),
                case_id TEXT NOT NULL REFERENCES cases(case_id),
                note_version_id INTEGER NOT NULL REFERENCES clinical_note_versions(id),
                source_version_id INTEGER NOT NULL REFERENCES source_versions(id),
                source_line INTEGER NOT NULL CHECK(source_line > 0),
                linked_by TEXT NOT NULL, linked_at TEXT NOT NULL,
                UNIQUE(note_version_id,source_version_id,source_line))""")
            self.db.execute("""INSERT INTO clinical_note_source_refs
                (patient_id,case_id,note_version_id,source_version_id,source_line,linked_by,linked_at)
                VALUES (?,?,?,?,?,?,?)""", (self.patient, "CASE-ALPHA", self.note_version_id,
                self.source, 2, "CLINICIAN-ONE", "2026-06-03T00:00:00+00:00"))
        self.provenance = ClinicalSourceProvenance(
            self.registry, self.store, self.clinical_policy, self.binding_policy)
        self.revise(findings=[])
        linked = self.read()
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0].get("annotation_capture_state"), "not_recorded")
        self.assertEqual(linked[0]["provenance_state"], "annotation_revision_unrecorded_review_required")
        self.assertIsNone(linked[0].get("original_statement"))
        self.assertIsNone(linked[0].get("certainty"))
        self.assertIsNone(linked[0].get("annotation_revision_id"))
        self.assertEqual(self.context()["note_versions_requiring_source_review"], [self.note_version_id])

    def test_pdf_link_keeps_captured_review_and_frozen_page_after_removal(self):
        passage = "Independently fictional page-two selection."
        raw = text_pdf([["Independently fictional original."], [passage]])
        preview = self.store.preview_document("CASE-ALPHA", raw, "fictional-note.pdf")
        findings = [{"key": "page-two", "state": "not-assessed", "quote": passage, "line": 2}]
        metadata = {"document_id": "NOTE-PDF-SOURCE", "kind": "pathology",
                    "event_date": "2026-06-01", "issued_at": "2026-06-02",
                    "manual_transcription_confirmed": True}
        source = self.store.import_document(
            "CASE-ALPHA", raw, "fictional-note.pdf", metadata, findings,
            hashlib.sha256(raw).hexdigest(), "CASE-ALPHA",
            expected_extraction_sha256=preview["extraction_sha256"])["source_id"]
        self.attach(source_version_id=source, source_line=2)
        before = self.read()[0]
        self.store.revise_document_annotations(
            "CASE-ALPHA", source, [], 1, hashlib.sha256(raw).hexdigest(), "CASE-ALPHA", True,
            "Remove a manually selected fictional passage.",
            expected_extraction_sha256=preview["extraction_sha256"])
        linked = self.read()
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]["original_statement"], passage)
        self.assertEqual(linked[0].get("annotation_revision"), 1)
        self.assertEqual(linked[0]["source_page"], 2)
        self.assertEqual(linked[0]["page_line"], 1)
        self.assertEqual(linked[0]["page_text_sha256"], hashlib.sha256((passage + "\n").encode()).hexdigest())
        self.assertEqual(linked[0]["transcription_review_sha256"], before["transcription_review_sha256"])
        self.assertEqual(linked[0]["extraction_sha256"], preview["extraction_sha256"])
        self.assertEqual(linked[0]["provenance_state"], "annotation_revision_changed_review_required")


class ClinicalAnnotationContinuityTests(unittest.TestCase):
    setUp = continuity_fixture.ClinicalContinuityIntegrationTests.setUp
    actor = continuity_fixture.ClinicalContinuityIntegrationTests.actor
    workflow = continuity_fixture.ClinicalContinuityIntegrationTests.workflow
    _source = continuity_fixture.ClinicalContinuityIntegrationTests._source
    snapshot = continuity_fixture.ClinicalContinuityIntegrationTests.snapshot

    def test_continuity_distinguishes_annotation_change_from_a_source_amendment(self):
        _, note_id = self.workflow()
        case = continuity_fixture.CASE
        raw = b"Independent fictional source.\nThe passage awaits manual review.\n"
        findings = [{"key": "review", "state": "not-assessed",
                     "quote": "The passage awaits manual review.", "line": 2}]
        metadata = {"document_id": "CONTINUITY-ANNOTATIONS", "kind": "pathology",
                    "event_date": "2026-06-01", "issued_at": "2026-06-02",
                    "manual_transcription_confirmed": True}
        source = self.store.import_document(case, raw, "fictional-continuity.txt",
            metadata, findings, hashlib.sha256(raw).hexdigest(), case)["source_id"]
        self.provenance.attach(self.patient_id, case, note_id, source, 2, **self.actor())
        self.store.revise_document_annotations(case, source, [], 1,
            hashlib.sha256(raw).hexdigest(), case, True,
            "Remove the unreviewed fictional annotation.")
        notes = [item for item in self.snapshot()["review_required"] if item["kind"] == "clinical_note"]
        self.assertEqual(notes, [{"kind": "clinical_note", "note_version_id": note_id,
                                  "reason": "annotation_revision_changed"}])


if __name__ == "__main__":
    unittest.main()
