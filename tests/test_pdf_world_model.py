"""World-model projection of existing, independently fictional PDF sources."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.world_model import synthetic_world_model
from pdf_fixtures import text_pdf


MANUAL_FIELDS = ("classification_origin", "annotation_method", "clinical_review",
                 "transcription_review_sha256")
PDF_FIELDS = ("text_origin", "extraction_sha256", "source_page", "page_line", "page_text_sha256")


def attach_pdf(store, *, case="CASE-ALPHA", document="PDF-ALPHA", state="not-assessed",
               quote="Marker P was not assessed.", amendment=None):
    raw = text_pdf([["Independent fictional report"], [quote]])
    preview = store.preview_document(case, raw, "fictional.pdf")
    metadata = {"document_id": document, "kind": "pathology", "event_date": "2026-07-01",
                "issued_at": "2026-07-02", "specimen_id": "FICTIONAL-SPECIMEN",
                "manual_transcription_confirmed": True}
    if amendment is not None:
        metadata["amends_version"] = amendment
    imported = store.import_document(case, raw, "fictional.pdf", metadata,
        [{"key": "marker-p", "state": state, "quote": quote, "line": 2}],
        preview["sha256"], case, expected_extraction_sha256=preview["extraction_sha256"])
    return imported, raw, preview


class PdfWorldModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "world-model.sqlite"
        self.store = CaseStore(self.path)
        for case in ("CASE-ALPHA", "CASE-BETA"):
            self.store.add_case(case, "Independent fictional case")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_manual_pdf_provenance_survives_observation_unresolved_and_source_views(self):
        imported, raw, preview = attach_pdf(self.store)
        state = self.store.state("CASE-ALPHA")
        unchanged = deepcopy(state)
        model = synthetic_world_model(state, "CASE-ALPHA")
        observation = model["observations"][0]
        self.assertEqual(observation["reported_state"], "not-assessed")
        self.assertEqual(observation["source_statement"], "Marker P was not assessed.")
        self.assertEqual(observation["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(observation["source_version_id"], imported["source_id"])
        self.assertEqual(observation.get("classification_origin"), "user_selected")
        self.assertEqual(observation.get("source_page"), 2)
        self.assertEqual(observation.get("page_line"), 1)
        self.assertEqual(observation.get("page_text_sha256"), hashlib.sha256(b"Marker P was not assessed.\n").hexdigest())
        self.assertEqual(observation.get("extraction_sha256"), preview["extraction_sha256"])
        for field in MANUAL_FIELDS + PDF_FIELDS:
            self.assertEqual(observation.get(field), state["assertions"][0][field], field)
            self.assertEqual(model["unresolved"][0].get(field), observation[field], field)
        source = model["current_sources"][0]
        self.assertEqual(source.get("document_intake"), state["sources"][0]["document_intake"])
        for field in MANUAL_FIELDS + PDF_FIELDS[:2]:
            self.assertEqual(source.get(field), state["sources"][0][field], field)
        self.assertEqual(observation["review_state"], "not_established")
        self.assertIsNone(observation["clinical_meaning"])
        self.assertEqual(state, unchanged)

    def test_manual_text_keeps_classification_origin_without_pdf_fields(self):
        raw = b"Independent fictional note\r\nMarker P remains pending.\r\n"
        metadata = {"document_id": "TEXT-ALPHA", "kind": "pathology", "event_date": "2026-07-01",
                    "issued_at": "2026-07-02", "manual_transcription_confirmed": True}
        self.store.import_document("CASE-ALPHA", raw, "fictional.txt", metadata,
            [{"key": "marker-p", "state": "pending", "quote": "Marker P remains pending.", "line": 2}],
            hashlib.sha256(raw).hexdigest(), "CASE-ALPHA")
        state = self.store.state("CASE-ALPHA")
        model = synthetic_world_model(state, "CASE-ALPHA")
        for row in (model["observations"][0], model["unresolved"][0], model["current_sources"][0]):
            self.assertEqual(row.get("classification_origin"), "user_selected")
            self.assertEqual(row.get("annotation_method"), "manual-exact-line-selection")
            self.assertEqual(row.get("clinical_review"), "not_performed")
            self.assertEqual(row.get("transcription_review_sha256"), state["assertions"][0]["transcription_review_sha256"])
            self.assertTrue(all(field not in row for field in PDF_FIELDS))

    def test_manual_conflict_references_retain_original_and_extraction_provenance(self):
        attach_pdf(self.store, document="PDF-ONE", state="reported", quote="Marker P was reported.")
        attach_pdf(self.store, document="PDF-TWO", state="negative", quote="Marker P was negative.")
        model = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        self.assertEqual(model["summary"]["source_disagreements"], 1)
        conflict = model["conflicts"][0]
        self.assertEqual(conflict["clinical_interpretation"], "not_performed")
        observations = {row["assertion_id"]: row for row in model["observations"]}
        for reference in conflict["observation_refs"]:
            observation = observations[reference["assertion_id"]]
            for field in ("source_sha256",) + MANUAL_FIELDS + PDF_FIELDS:
                self.assertEqual(reference.get(field), observation.get(field), field)
                self.assertIsNotNone(reference.get(field), field)

    def test_incomplete_or_mismatched_manual_pdf_provenance_rejects(self):
        attach_pdf(self.store)
        state = self.store.state("CASE-ALPHA")
        mutations = []
        for field in MANUAL_FIELDS + PDF_FIELDS:
            changed = deepcopy(state)
            del changed["assertions"][0][field]
            mutations.append(("missing assertion " + field, changed))
        for field in MANUAL_FIELDS + PDF_FIELDS[:2]:
            changed = deepcopy(state)
            del changed["sources"][0][field]
            mutations.append(("missing source " + field, changed))
        for field, bad in (("classification_origin", "source_authored"), ("clinical_review", "approved"),
                           ("annotation_method", "manual-exact-line-selection"),
                           ("transcription_review_sha256", "0" * 64), ("extraction_sha256", "0" * 64),
                           ("text_origin", "original"), ("source_page", True), ("source_page", 21),
                           ("page_line", 0), ("page_line", 3), ("source_line", 513),
                           ("page_text_sha256", "not-a-hash")):
            changed = deepcopy(state)
            changed["assertions"][0][field] = bad
            mutations.append(("bad assertion " + field, changed))
        for field, bad in (("manual_transcription_confirmed", False), ("clinical_review", "approved"),
                           ("review_sha256", "0" * 64), ("extraction_sha256", "0" * 64),
                           ("media_type", "text/plain; charset=utf-8")):
            changed = deepcopy(state)
            changed["sources"][0]["document_intake"][field] = bad
            mutations.append(("bad receipt " + field, changed))
        changed = deepcopy(state)
        del changed["sources"][0]["document_intake"]
        mutations.append(("missing receipt", changed))
        for name, changed in mutations:
            with self.subTest(mutation=name):
                with self.assertRaises(InvalidInput):
                    synthetic_world_model(changed, "CASE-ALPHA")

    def test_assertion_cannot_borrow_another_source_receipt_or_case(self):
        first, _, _ = attach_pdf(self.store)
        second, _, _ = attach_pdf(self.store, document="PDF-OTHER", state="pending", quote="Marker P remains pending.")
        state = self.store.state("CASE-ALPHA")
        changed = deepcopy(state)
        first_assertion = next(row for row in changed["assertions"] if row["source_version_id"] == first["source_id"])
        first_assertion["source_version_id"] = second["source_id"]
        with self.assertRaises(InvalidInput):
            synthetic_world_model(changed, "CASE-ALPHA")
        for field in ("sources", "assertions"):
            changed = deepcopy(state)
            changed[field][0]["case_id"] = "CASE-BETA"
            with self.assertRaises(InvalidInput):
                synthetic_world_model(changed, "CASE-ALPHA")
        with self.assertRaises(InvalidInput):
            synthetic_world_model(state, "CASE-BETA")
        self.assertEqual(synthetic_world_model(self.store.state("CASE-BETA"), "CASE-BETA")["observations"], [])

    def test_signed_64_bit_identifiers_reject_boolean_float_and_overflow(self):
        attach_pdf(self.store)
        question = self.store.add_question("CASE-ALPHA", "What remains uncertain?")
        source_id = self.store.state("CASE-ALPHA")["sources"][0]["id"]
        self.store.create_snapshot("CASE-ALPHA", question, "Fictional report", [source_id])
        state = self.store.state("CASE-ALPHA")
        for collection, field in (("sources", "id"), ("assertions", "id"), ("assertions", "source_version_id"),
                                  ("questions", "id"), ("snapshots", "id"), ("events", "id")):
            for invalid in (True, 1.0, 0, 2 ** 63):
                changed = deepcopy(state)
                previous_id = changed[collection][0][field]
                changed[collection][0][field] = invalid
                if collection == "sources" and field == "id":
                    for assertion in changed["assertions"]:
                        if assertion["source_version_id"] == previous_id:
                            assertion["source_version_id"] = invalid
                if collection == "assertions" and field == "source_version_id":
                    for source in changed["sources"]:
                        if source["id"] == previous_id:
                            source["id"] = invalid
                with self.subTest(collection=collection, field=field, invalid=invalid):
                    with self.assertRaises(InvalidInput):
                        synthetic_world_model(changed, "CASE-ALPHA")

    def test_amendment_history_selective_snapshot_staleness_and_no_reparse_restart(self):
        first, raw, preview = attach_pdf(self.store)
        other, _, _ = attach_pdf(self.store, document="PDF-INDEPENDENT", state="reported", quote="Independent sample finding was reported.")
        question = self.store.add_question("CASE-ALPHA", "What does the first source say?")
        independent_question = self.store.add_question("CASE-ALPHA", "What does the independent source say?")
        affected = self.store.create_snapshot("CASE-ALPHA", question, "First fictional report", [first["source_id"]])
        untouched = self.store.create_snapshot("CASE-ALPHA", independent_question, "Independent fictional report", [other["source_id"]])
        self.store.acknowledge_demo_review("CASE-ALPHA", affected, "Unverified fictional operator")
        self.store.acknowledge_demo_review("CASE-ALPHA", untouched, "Unverified fictional operator")
        before = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
        amended, amended_raw, amended_preview = attach_pdf(self.store, state="pending", quote="Marker P remains pending.", amendment=1)
        self.store.close()
        self.store = CaseStore(self.path)
        ledger = tuple(self.store.db.iterdump())
        with patch("open_intelligence.pdf_intake.extract_pdf", side_effect=AssertionError("Unexpected parser call")):
            result = synthetic_world_model(self.store.state("CASE-ALPHA"), "CASE-ALPHA")
            history = next(row for row in result["history"] if row["source_version_id"] == first["source_id"])
            self.assertEqual(history.get("extraction_sha256"), preview["extraction_sha256"])
            self.assertEqual(history.get("document_intake"), before["current_sources"][0]["document_intake"])
            current = next(row for row in result["observations"] if row["source_version_id"] == amended["source_id"])
            self.assertEqual(current["reported_state"], "pending")
            self.assertEqual(current.get("extraction_sha256"), amended_preview["extraction_sha256"])
            self.assertEqual(result["review_needed"]["stale_snapshot_ids"], [affected])
            self.assertNotIn(untouched, result["review_needed"]["stale_snapshot_ids"])
            self.assertEqual(result["review_needed"]["open_question_ids"], [question])
            self.assertEqual(self.store.source_document("CASE-ALPHA", first["source_id"])["raw"], raw)
            self.assertEqual(self.store.source_document("CASE-ALPHA", amended["source_id"])["raw"], amended_raw)
            old = self.store.source_view("CASE-ALPHA", first["source_id"])
            self.assertEqual(old["pages"][1]["text"], "Marker P was not assessed.\n")
            self.assertEqual(old["extraction_sha256"], preview["extraction_sha256"])
        self.assertEqual(tuple(self.store.db.iterdump()), ledger)
