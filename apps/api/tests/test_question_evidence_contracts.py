"""Adversarial response contracts using independently fictional metadata only."""
from copy import deepcopy
import json
import unittest

from pydantic import ValidationError

from oi_api.evidence_contracts import (
    EvidenceLink, EvidenceLinkCreate, EvidenceLinkReceipt, EvidenceLinks, EvidenceMetadata,
)
from oi_api.evidence_routes import _prepare


def metadata():
    return {
        "citation": "FICT-DEMO@1", "id": "FICT-DEMO", "version": "1",
        "source_kind": "fictional", "title": "Original fictional continuity example",
        "licence": "Original synthetic fixture",
        "link": "https://example.invalid/fictional/FICT-DEMO/1",
        "metadata_sha256": "a" * 64,
        "availability": "metadata_only", "rights_status": "granted",
    }


def link():
    return {
        "link_id": "EVIDENCE-LINK-" + "A" * 32,
        "citation": "FICT-DEMO@1", "metadata_sha256": "a" * 64,
        "created_at": "2026-11-03T00:00:00+00:00", "actor_label": "FICTIONAL-ACTOR",
        "status": "available", "record": metadata(),
    }


class QuestionEvidenceContractTests(unittest.TestCase):
    def test_valid_exact_metadata_round_trips_without_changing_public_fields(self):
        original = metadata()
        self.assertEqual(EvidenceMetadata(**original).model_dump(mode="json"), original)
        self.assertEqual(EvidenceLink(**link()).model_dump(mode="json"), link())
        # Fixture URLs may describe a source independently of its catalog key.
        original["link"] = "https://example.invalid/fictional/record-continuity"
        self.assertEqual(EvidenceMetadata(**original).link, original["link"])

    def test_redacted_history_preserves_only_the_original_identity_receipt(self):
        for status in ("rights_restricted", "superseded", "unavailable"):
            with self.subTest(status=status):
                original = {**link(), "status": status, "record": None}
                parsed = EvidenceLink(**original).model_dump(mode="json")
                self.assertEqual(parsed, original)
                self.assertNotIn(metadata()["title"], json.dumps(parsed))

    def test_metadata_identity_must_agree_with_its_exact_citation(self):
        for change in ({"citation": "FICT-OTHER@1"}, {"citation": "FICT-DEMO@2"},
                       {"id": "FICT-OTHER"}, {"version": "2"}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                EvidenceMetadata(**{**metadata(), **change})

    def test_only_available_history_can_contain_metadata(self):
        inconsistent = [{**link(), "record": None}]
        inconsistent.extend({**link(), "status": status}
                            for status in ("rights_restricted", "superseded", "unavailable"))
        for value in inconsistent:
            with self.subTest(status=value["status"], has_record=value["record"] is not None):
                with self.assertRaises(ValidationError):
                    EvidenceLink(**value)

    def test_nested_metadata_must_match_the_durable_link_identity_and_hash(self):
        for change in ({"citation": "FICT-OTHER@1"}, {"metadata_sha256": "b" * 64}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                EvidenceLink(**{**link(), **change})

    def test_metadata_links_stay_within_the_explicit_fictional_url_boundary(self):
        invalid = (
            "http://example.invalid/fictional/FICT-DEMO/1",
            "https://example.org/fictional/FICT-DEMO/1",
            "https://example.invalid.evil.example/fictional/FICT-DEMO/1",
            "https://user@example.invalid/fictional/FICT-DEMO/1",
            "https://example.invalid:443/fictional/FICT-DEMO/1",
            "https://example.invalid/clinical/FICT-DEMO/1",
            "https://example.invalid/fictional/FICT-DEMO/1?fetch=private",
            "https://example.invalid/fictional/FICT-DEMO/1#private",
            "javascript:alert(1)", "//example.invalid/fictional/FICT-DEMO/1",
            "https://example.invalid/fictional/white space",
            "https://example.invalid/\nfictional/FICT-DEMO/1",
            "https://example.invalid/fictional/FICT\u202eDEMO/1",
        )
        for value in invalid:
            with self.subTest(link=value), self.assertRaises(ValidationError):
                EvidenceMetadata(**{**metadata(), "link": value})

    def test_title_and_licence_are_visible_trimmed_metadata(self):
        invalid = (" leading", "trailing ", "embedded\nline", "\u202espoof",
                   "\ud800", "\u2028line", "   ")
        for field in ("title", "licence"):
            for value in invalid:
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    EvidenceMetadata(**{**metadata(), field: value})

    def test_metadata_does_not_coerce_non_string_identity_or_content(self):
        for field in ("citation", "id", "version", "title", "licence", "link", "metadata_sha256"):
            value = metadata()[field].encode()
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceMetadata(**{**metadata(), field: value})

    def test_all_durable_citation_references_require_one_bounded_exact_version(self):
        for citation in ("", "FICT-DEMO", "FICT-DEMO@.1", "FICT-DEMO@" + "1" * 65,
                         "NCT123@1", "FICT-" + "A" * 124 + "@1"):
            payloads = (
                (EvidenceLink, {**link(), "status": "rights_restricted", "record": None}),
                (EvidenceLinkReceipt, {"link_id": link()["link_id"], "citation": "FICT-DEMO@1",
                                       "metadata_sha256": "a" * 64, "duplicate": True}),
                (EvidenceLinkCreate, {
                    "synthetic": True, "request_key": "FICTIONAL-LINK-ONE", "citation": "FICT-DEMO@1",
                    "expected_metadata_sha256": "a" * 64,
                    "source_snapshot_contract": "oi.pg-source-world-model/1",
                    "expected_source_snapshot_sha256": "b" * 64,
                    "expected_preflight_sha256": "c" * 64,
                }),
            )
            for model, payload in payloads:
                with self.subTest(model=model.__name__, citation=citation):
                    with self.assertRaises(ValidationError):
                        model(**{**payload, "citation": citation})

    def test_wire_preparation_rejects_metadata_in_a_rights_restricted_history_row(self):
        value = {
            "contract": "oi.pg-question-evidence-links/1", "patient_id": "FICTIONAL-PATIENT",
            "case_id": "CASE-FICTIONAL", "question_id": "QUESTION-" + "B" * 32,
            "source_context_state": "current_unreviewed_question",
            "source_access_receipt_id": "ACCESS-" + "C" * 32,
            "links": [link()],
        }
        self.assertEqual(_prepare(EvidenceLinks, value).status_code, 200)
        inconsistent = deepcopy(value)
        inconsistent["links"][0]["status"] = "rights_restricted"
        with self.assertRaises(ValidationError):
            _prepare(EvidenceLinks, inconsistent)
