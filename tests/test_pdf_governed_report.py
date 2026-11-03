"""Real fictional PDF intake through canonical clinical owners and report receipts.

The originals and evidence are independently authored test strings. No external
patient data, medical publication, provider call or clinical approval is used.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from open_intelligence.authorized_evidence_review import AuthorizedEvidenceReviewHandoff
from open_intelligence.clinical_continuity import ClinicalContinuityError
from open_intelligence.evidence_report_handoff import ReportReviewHandoff
from open_intelligence.evidence_review_packet import EvidenceReviewPacket
from open_intelligence.evidence_review_report import EvidenceReviewReport
from open_intelligence.knowledge_context import KnowledgeContextError
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.world_model import synthetic_world_model

from pdf_fixtures import text_pdf
import test_authorized_evidence_review_handoff as fixture

CASE, EVIDENCE_KEY = fixture.CASE, fixture.EVIDENCE_KEY
ORIGINAL, STATEMENT = fixture.ORIGINAL, fixture.STATEMENT


MANUAL_FIELDS = ("classification_origin", "annotation_method", "clinical_review",
                 "transcription_review_sha256")
PDF_FIELDS = ("text_origin", "extraction_sha256", "source_page", "page_line",
              "page_text_sha256")
PASSAGE = "Marker Q needs a separate review."
REASON = "An independent fictional appraisal of source and evidence remains necessary."


class PdfGovernedReportTests(unittest.TestCase):
    setUp = fixture.ReviewHandoffTests.setUp
    actor = fixture.ReviewHandoffTests.actor
    workflow = fixture.ReviewHandoffTests.workflow
    _source = fixture.ReviewHandoffTests._source
    prepare = fixture.ReviewHandoffTests.prepare

    def attach(self, *, media="pdf", state="not-assessed", quote=PASSAGE,
               amendment=None):
        if media == "pdf":
            raw = text_pdf([
                ["Independently authored fictional report.",
                 "No patient information from outside this test."], [quote]])
            filename, line = "fictional-governed.pdf", 3
        else:
            raw = ("Independently authored fictional report.\r\n" + quote + "\r\n").encode()
            filename, line = "fictional-governed.txt", 2
        metadata = {
            "document_id": "PDF-GOV-001" if media == "pdf" else "TXT-GOV-001",
            "kind": "pathology", "event_date": "2026-01-07",
            "issued_at": "2026-01-08", "specimen_id": "SPEC-CONT-001",
            "manual_transcription_confirmed": True,
        }
        if amendment is not None:
            metadata["amends_version"] = amendment
        findings = [{"key": "marker-q", "state": state, "quote": quote, "line": line}]
        preview = self.store.preview_document(CASE, raw, filename)
        options = ({"expected_extraction_sha256": preview["extraction_sha256"]}
                   if media == "pdf" else {})
        imported = self.store.import_document(
            CASE, raw, filename, metadata, findings, hashlib.sha256(raw).hexdigest(),
            CASE, **options)
        assertion = next(a for a in self.store.state(CASE)["assertions"]
                         if a["source_version_id"] == imported["source_id"])
        return {"media": media, "raw": raw, "filename": filename, "metadata": metadata,
                "findings": findings, "preview": preview, "source_id": imported["source_id"],
                "assertion": assertion, "options": options}

    def build(self, media="pdf"):
        bridge, question, sources, proposals = self.prepare()
        if media == "authored":
            assertion = self.store.state(CASE)["assertions"][0]
            attached = {"media": media, "source_id": assertion["source_version_id"],
                        "assertion": assertion}
        else:
            attached = self.attach(media=media)
            assertion = attached["assertion"]
        evidence = self.store.import_synthetic_evidence(ORIGINAL)["evidence_version_id"]
        assessment = self.store.assess_synthetic_evidence(
            CASE, question, evidence, "context", "limited",
            "Fictional source comparison awaiting independent appraisal.")
        sources[0].update({"id": EVIDENCE_KEY, "version": "v1", "evidence_text": STATEMENT,
                           "content_item": "api_output"})
        # Content-specific permission must survive this whole PDF/report path.
        sources[0]["permissions"]["api_output"] = sources[0]["permissions"].pop("full_text")
        for part in ("metadata", "api_output"):
            sources[0]["permissions"][part]["redistribute"] = "allowed"
        proposals.append({
            "assertion_id": assertion["id"], "knowledge_id": EVIDENCE_KEY,
            "relation": "context", "applicability": "limited",
            "reviewer_note": "Independently fictional comparison without a clinical conclusion.",
            "proposed_by": "TEST-REVIEWER",
        })
        quotes = [{"assertion_id": assertion["id"], "knowledge_id": EVIDENCE_KEY,
                   "quote": "claims no therapeutic outcomes"}]
        packets = EvidenceReviewPacket(bridge)
        review = AuthorizedEvidenceReviewHandoff(
            packets, return_authorizer=lambda actor, patient, action, purpose: (
                actor == self.actor()["actor"] and patient == self.patient_id
                and action == "evidence.review_return" and purpose == "care"))
        renderer = EvidenceReviewReport(
            packets, export_authorizer=lambda actor, patient, action, purpose: (
                actor == self.actor()["actor"] and patient == self.patient_id
                and action == "evidence_report.export" and purpose == "care"))
        return {**attached, "bridge": bridge, "question": question, "sources": sources,
                "proposals": proposals, "assessment": assessment, "quotes": quotes,
                "service": ReportReviewHandoff(renderer, review)}

    def send(self, scope, **overrides):
        args = {"patient_id": self.patient_id, "case_id": CASE,
                "question_id": scope["question"], "assessment_id": scope["assessment"],
                "selected_quotes": scope["quotes"], "reason": REASON, **self.actor()}
        args.update(overrides)
        return scope["service"].return_for_review(**args)

    def review_writes(self):
        return tuple(self.store.db.execute(sql).fetchone()[0] for sql in (
            "SELECT count(*) FROM review_receipts",
            "SELECT count(*) FROM events WHERE kind='review_receipt_recorded'"))

    def prepared(self, scope):
        packet = scope["service"].review.preview(
            self.patient_id, CASE, scope["question"], scope["assessment"],
            selected_quotes=scope["quotes"], **self.actor())
        report = scope["service"].report.render(
            self.patient_id, CASE, scope["question"],
            selected_quotes=scope["quotes"], **self.actor())
        ref = packet["source_quote_packet"]["quoted_comparisons"][0]["patient_reference"]
        fields = ("assertion_id", "source_version_id", "sha256", "source_line")
        source = {key: ref[key] for key in fields}
        source.update({key: scope["assertion"][key] for key in MANUAL_FIELDS + PDF_FIELDS
                       if key in scope["assertion"]})
        prepared = {"contract": "oi.synthetic-prepared-report-reference/1",
                    "semantics": "prepared_not_delivery_or_approval",
                    "question_id": scope["question"], "body_sha256": report["body_sha256"],
                    "packet_sha256": report["packet_sha256"], "patient_source": source}
        return packet, prepared

    def test_pdf_provenance_survives_clinical_context_packet_report_and_receipt(self):
        # Dropping manual/PDF fields at any crossing must fail this integration.
        scope = self.build()
        context = scope["bridge"].snapshot(
            self.patient_id, CASE, scope["question"], **self.actor())
        self.assertEqual(context["clinical_composer"]["clinical"]["patient_id"], self.patient_id)
        self.assertEqual(len(context["clinical_composer"]["clinical"]["lab_evidence_candidates"]), 1)
        self.assertEqual(len(context["clinical_composer"]["clinical"]["note_source_links"]), 1)
        knowledge = next(a for a in context["knowledge"]["patient_assertions"]
                         if a["id"] == scope["assertion"]["id"])
        composer = next(a for a in context["clinical_composer"]["composer"]["source_anchors"]
                        if a["source_version_id"] == scope["source_id"])
        world = next(a for a in synthetic_world_model(self.store.state(CASE), CASE)["observations"]
                     if a["assertion_id"] == scope["assertion"]["id"])
        packet = scope["service"].review.packet.preview(
            self.patient_id, CASE, scope["question"],
            selected_quotes=scope["quotes"], **self.actor())
        reference = packet["quoted_comparisons"][0]["patient_reference"]
        self.assertEqual(reference["sha256"], hashlib.sha256(scope["raw"]).hexdigest())
        for layer, row in (("knowledge", knowledge), ("composer", composer),
                           ("world_model", world), ("quote_packet", reference)):
            with self.subTest(layer=layer):
                self.assertEqual(row.get("classification_origin"), "user_selected")
                self.assertEqual(row.get("annotation_method"), "manual-exact-extraction-line-selection")
                self.assertEqual(row.get("clinical_review"), "not_performed")
                self.assertEqual(row.get("text_origin"), "pdf_extraction")
                self.assertEqual(row.get("source_line"), 3)
                self.assertEqual(row.get("source_page"), 2)
                self.assertEqual(row.get("page_line"), 1)
                self.assertEqual(row.get("page_text_sha256"), hashlib.sha256((PASSAGE + "\n").encode()).hexdigest())
                self.assertEqual(row.get("extraction_sha256"), scope["preview"]["extraction_sha256"])
                self.assertEqual(row.get("transcription_review_sha256"), scope["assertion"]["transcription_review_sha256"])
        self.assertNotEqual(knowledge["epistemic_kind"], "reported_observation")
        result = self.send(scope)
        body = result["report"]["body"]
        self.assertIn("user-selected", body.lower())
        self.assertIn('"not-assessed"', body)
        self.assertNotIn('Source-reported state: "not-assessed"', body)
        self.assertIn("not_performed", body)
        self.assertIn(scope["preview"]["extraction_sha256"], body)
        self.assertIn(scope["assertion"]["transcription_review_sha256"], body)
        self.assertEqual(packet["quoted_comparisons"][0]["external_reference"]["content_item"], "api_output")
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        prepared = json.loads(event["details"])["prepared_report"]
        for key in MANUAL_FIELDS + PDF_FIELDS:
            self.assertEqual(prepared["patient_source"].get(key), scope["assertion"][key], key)
        self.assertEqual(prepared["body_sha256"], hashlib.sha256(body.encode()).hexdigest())
        self.assertEqual(prepared["packet_sha256"], result["report"]["packet_sha256"])
        self.assertNotIn("body", prepared)
        self.assertNotIn(PASSAGE, event["details"])
        self.assertFalse(result["clinical_signoff"])
        self.assertEqual(result["human_review_state"], "pending")
        self.assertEqual(self.review_writes(), (1, 1))
        self.assertEqual(next(q["state"] for q in self.store.state(CASE)["questions"]
                              if q["id"] == scope["question"]), "open")
        self.assertFalse(any(q["queue_key"] == result["receipt"]["queue_key"]
                             for q in self.store.review_queue(CASE)["resolved"]))

    def test_manual_text_keeps_review_identity_without_inventing_pdf_coordinates(self):
        scope = self.build("text")
        result = self.send(scope)
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        source = json.loads(event["details"])["prepared_report"]["patient_source"]
        self.assertEqual(source["source_line"], 2)
        self.assertEqual(source.get("classification_origin"), "user_selected")
        self.assertEqual(source.get("annotation_method"), "manual-exact-line-selection")
        self.assertEqual(source.get("clinical_review"), "not_performed")
        self.assertEqual(source.get("transcription_review_sha256"), scope["assertion"]["transcription_review_sha256"])
        self.assertTrue(all(key not in source for key in PDF_FIELDS))
        self.assertIn("user-selected", result["report"]["body"].lower())

    def test_clinical_source_and_note_links_retain_the_same_manual_pdf_origin(self):
        # The earlier clinical projection must not erase what the report later displays.
        scope = self.build()
        note_id = self.store.db.execute(
            "SELECT id FROM clinical_note_versions ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.provenance.attach(self.patient_id, CASE, note_id, scope["source_id"], 3,
                               **self.actor())
        clinical = self.provenance.context_snapshot(self.patient_id, CASE, **self.actor())
        assertion = next(a for a in clinical["source_reported_assertions"]
                         if a["source_version_id"] == scope["source_id"])
        source = next(s for s in clinical["source_versions"]
                      if s["source_version_id"] == scope["source_id"])
        note = next(n for n in self.provenance.note_sources(
            self.patient_id, CASE, note_id, **self.actor())
                    if n["source_version_id"] == scope["source_id"])
        for layer, row in (("clinical assertion", assertion), ("note source", note)):
            for key in MANUAL_FIELDS + PDF_FIELDS:
                with self.subTest(layer=layer, field=key):
                    self.assertEqual(row.get(key), scope["assertion"][key])
            self.assertEqual(row["source_line"], 3)
        for key in MANUAL_FIELDS + PDF_FIELDS[:2]:
            with self.subTest(layer="clinical source", field=key):
                self.assertEqual(source.get(key), scope["assertion"][key])
        self.assertEqual(note["clinical_review_state"], "not_established_by_source_link")
        self.assertEqual(clinical["clinical_interpretation"], "not_generated")
        self.assertEqual(self.review_writes(), (0, 0))

    def test_authored_source_still_uses_its_original_reference_contract(self):
        scope = self.build("authored")
        result = self.send(scope)
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        source = json.loads(event["details"])["prepared_report"]["patient_source"]
        self.assertEqual(set(source), {"assertion_id", "source_version_id", "sha256", "source_line"})
        self.assertIn('Source-reported state: "reported"', result["report"]["body"])
        self.assertNotIn("User-selected", result["report"]["body"])

    def test_incomplete_or_relabelled_read_provenance_cannot_prepare_a_report(self):
        scope = self.build()
        original_state = self.store.state
        mutations = [(key, None) for key in MANUAL_FIELDS + PDF_FIELDS]
        mutations.extend([
            ("classification_origin", "source_authored"), ("clinical_review", "approved"),
            ("annotation_method", "manual-exact-line-selection"),
            ("transcription_review_sha256", "0" * 64), ("extraction_sha256", "0" * 64),
            ("source_page", 1), ("page_line", 0), ("page_text_sha256", "invalid"),
        ])
        before = self.review_writes()
        for key, value in mutations:
            def corrupt(case, *, field=key, invalid=value):
                state = deepcopy(original_state(case))
                item = next(a for a in state["assertions"] if a["id"] == scope["assertion"]["id"])
                if invalid is None:
                    item.pop(field)
                else:
                    item[field] = invalid
                return state
            with self.subTest(field=key, value=value), patch.object(self.store, "state", side_effect=corrupt):
                with self.assertRaises((InvalidInput, KnowledgeContextError, ClinicalContinuityError)):
                    self.send(scope)
            self.assertEqual(self.review_writes(), before)

    def test_knowledge_alignment_rejects_changed_original_identity(self):
        # Same quotation and manual fields cannot substitute a different original.
        scope = self.build()
        context = scope["bridge"].snapshot(
            self.patient_id, CASE, scope["question"], **self.actor())
        before = self.review_writes()
        for key, value in (("source_hash", "0" * 64),
                           ("source_document", "DIFFERENT-FICTIONAL-DOCUMENT"), ("version", 2)):
            changed = deepcopy(context["knowledge"])
            observation = next(a for a in changed["patient_assertions"]
                               if a["id"] == scope["assertion"]["id"])
            observation[key] = value
            with self.subTest(field=key), self.assertRaises(ClinicalContinuityError):
                scope["bridge"]._align_assertions(
                    context["clinical_composer"]["composer"], changed)
        self.assertEqual(self.review_writes(), before)

    def test_receipt_owner_rechecks_full_pdf_reference_before_any_write(self):
        scope = self.build()
        preview, prepared = self.prepared(scope)
        before = self.review_writes()
        mutations = [(key, None) for key in MANUAL_FIELDS + PDF_FIELDS]
        mutations.extend([(key, "0" * 64) for key in (
            "transcription_review_sha256", "extraction_sha256", "page_text_sha256")])
        mutations.extend([("source_page", 1), ("page_line", 2),
                          ("clinical_review", "approved"), ("classification_origin", "source_authored"),
                          ("source_page", True), ("page_line", 2 ** 63),
                          ("unrecognized_provenance", "must not be persisted")])
        for key, value in mutations:
            changed = deepcopy(prepared)
            if value is None:
                changed["patient_source"].pop(key)
            else:
                changed["patient_source"][key] = value
            with self.subTest(field=key, value=value), self.assertRaises(InvalidInput):
                self.store.add_review_receipt(
                    CASE, preview["queue_key"], "returned", self.actor()["actor"], reason=REASON,
                    expected_fingerprint=preview["queue_fingerprint"], prepared_report=changed)
            self.assertEqual(self.review_writes(), before)
        # A valid reference through the same real write owner must succeed.
        result = self.store.add_review_receipt(
            CASE, preview["queue_key"], "returned", self.actor()["actor"], reason=REASON,
            expected_fingerprint=preview["queue_fingerprint"], prepared_report=prepared)
        self.assertIsInstance(result["receipt_id"], int)
        self.assertEqual(self.review_writes(), (1, 1))

    def test_legacy_only_receipt_cannot_downgrade_a_manual_pdf_source(self):
        # A complete omission looks like valid authored text unless the locked
        # write checks the original owner's actual manual/PDF source identity.
        scope = self.build()
        preview, prepared = self.prepared(scope)
        for key in MANUAL_FIELDS + PDF_FIELDS:
            prepared["patient_source"].pop(key)
        before = self.review_writes()
        with self.assertRaises(InvalidInput):
            self.store.add_review_receipt(
                CASE, preview["queue_key"], "returned", self.actor()["actor"], reason=REASON,
                expected_fingerprint=preview["queue_fingerprint"], prepared_report=prepared)
        self.assertEqual(self.review_writes(), before)

    def test_same_original_cannot_silently_replace_the_manual_classification(self):
        scope = self.build()
        sent = self.send(scope)
        before = self.review_writes()
        relabelled = deepcopy(scope["findings"])
        relabelled[0]["state"] = "reported"
        with self.assertRaises(InvalidInput):
            self.store.import_document(
                CASE, scope["raw"], scope["filename"], scope["metadata"], relabelled,
                hashlib.sha256(scope["raw"]).hexdigest(), CASE, **scope["options"])
        self.assertEqual(self.review_writes(), before)
        self.assertEqual(next(a["certainty"] for a in self.store.state(CASE)["assertions"]
                              if a["id"] == scope["assertion"]["id"]), "not-assessed")
        self.assertEqual(self.send(scope)["report"]["body_sha256"], sent["report"]["body_sha256"])

    def test_pdf_amendment_denies_old_comparison_and_keeps_receipt_after_restart(self):
        scope = self.build()
        first = self.send(scope)
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        amended = self.attach(state="pending", quote="Marker Q awaits corrected review.", amendment=1)
        before = self.review_writes()
        with self.assertRaises((InvalidInput, KnowledgeContextError, ClinicalContinuityError)):
            self.send(scope)
        self.assertEqual(self.review_writes(), before)
        path = self.store.path
        self.store.close()
        reopened = CaseStore(path)
        try:
            state = reopened.state(CASE)
            historical = next(s for s in state["sources"] if s["id"] == scope["source_id"])
            self.assertEqual(historical["state"], "superseded")
            current = next(a for a in state["assertions"] if a["source_version_id"] == amended["source_id"])
            self.assertEqual(current["certainty"], "pending")
            self.assertEqual(current["source_page"], 2)
            self.assertEqual(current["source_line"], 3)
            self.assertEqual(reopened.source_document(CASE, scope["source_id"])["raw"], scope["raw"])
            self.assertEqual(reopened.source_document(CASE, amended["source_id"])["raw"], amended["raw"])
            receipt = next(r for r in reopened.review_queue(CASE)["receipts"]
                           if r["id"] == first["receipt"]["receipt_id"])
            self.assertEqual(receipt["action"], "returned")
            self.assertEqual(next(e["details"] for e in state["events"] if e["id"] == event["id"]), event["details"])
            self.assertEqual(next(q["state"] for q in state["questions"] if q["id"] == scope["question"]), "open")
        finally:
            reopened.close()

    def test_rights_and_actor_withdrawal_deny_pdf_reports_without_new_receipts(self):
        scope = self.build()
        first = self.send(scope)
        before = self.review_writes()
        scope["sources"][0]["permissions"]["api_output"]["redistribute"] = "denied"
        with self.assertRaises(KnowledgeContextError):
            self.send(scope)
        self.assertEqual(self.review_writes(), before)
        scope["sources"][0]["permissions"]["api_output"]["redistribute"] = "allowed"
        for overrides in ({"actor": "idp:untrusted"}, {"purpose": "research"},
                          {"case_id": "CASE-CLIN-CONT-OTHER"}):
            with self.subTest(scope=overrides), self.assertRaises((ValueError, PermissionError)):
                self.send(scope, **overrides)
            self.assertEqual(self.review_writes(), before)
        scope["service"].report.export_authorizer = None
        with self.assertRaises(PermissionError):
            self.send(scope)
        self.assertEqual(self.review_writes(), before)
        self.assertEqual(self.store.review_queue(CASE)["receipts"][0]["id"], first["receipt"]["receipt_id"])

    def test_postreceipt_rights_withdrawal_withholds_pdf_report_and_preserves_preparation(self):
        # Removing the final export recheck would leak the body after permission loss.
        scope = self.build()
        original_write = self.store.add_review_receipt

        def withdraw_after_real_commit(*args, **kwargs):
            receipt = original_write(*args, **kwargs)
            scope["sources"][0]["permissions"]["api_output"]["redistribute"] = "denied"
            return receipt

        with patch.object(self.store, "add_review_receipt", side_effect=withdraw_after_real_commit):
            with self.assertRaises(KnowledgeContextError):
                self.send(scope)
        self.assertEqual(self.review_writes(), (1, 1))
        event = next(e for e in self.store.state(CASE)["events"] if e["kind"] == "review_receipt_recorded")
        prepared = json.loads(event["details"])["prepared_report"]
        self.assertEqual(prepared["semantics"], "prepared_not_delivery_or_approval")
        self.assertEqual(prepared["patient_source"].get("source_page"), 2)
        self.assertEqual(prepared["patient_source"].get("classification_origin"), "user_selected")
        self.assertNotIn("body", prepared)
        self.assertEqual(next(q["state"] for q in self.store.state(CASE)["questions"]
                              if q["id"] == scope["question"]), "open")


if __name__ == "__main__":
    unittest.main()
