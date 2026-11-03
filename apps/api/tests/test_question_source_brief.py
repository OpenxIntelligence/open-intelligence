"""Source-question brief boundary checks with independently fictional inputs."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import unittest

from oi_api.app import create_app
from oi_api.config import Settings
from oi_api import patients as patient_routes, source_questions as question_owner
from oi_api.source_world_model import project_source_world_model
from open_intelligence.patient_registry import PatientRegistryError
from pydantic import ValidationError

from http_support import running_server
import test_patients as patient_fixture


PATIENT = "PAT-" + "A" * 32
SOURCE = "SRC-" + "B" * 32
QUESTION_ID = "QUESTION-" + "C" * 32
QUESTION = "What remains unknown about the fictional café finding?"
STATEMENT = "Fictional café <script>literal</script> remains unassessed."
PREPARED_AT = datetime(2026, 11, 3, 4, 5, 6, tzinfo=timezone.utc)
RESPONSE_FIELDS = {
    "contract", "synthetic", "patient_id", "case_id", "source_snapshot_contract",
    "source_snapshot_sha256", "access_receipt_id", "question", "selected_source",
    "prepared_at", "media_type", "body", "body_sha256", "clinical_approval",
    "model_executed", "biomedical_evidence_included",
}


def fictional_brief_inputs(state="not-assessed"):
    """Complete existing source-index shape; no real patient or partial doubles."""
    original = ("Independently fictional report.\n" + STATEMENT + "\n").encode()
    digest = hashlib.sha256(original).hexdigest()
    index = {
        "contract": "oi.synthetic-original-sources/1", "patient_id": PATIENT,
        "case_id": "CASE-ALPHA", "access_receipt_id": "ACCESS-" + "D" * 32,
        "synthetic": True, "clinical_interpretation": False,
        "research_review_invalidation_integrated": False,
        "sources": [{
            "source_id": SOURCE, "document_id": "DOC-FICTIONAL", "version": 1,
            "sha256": digest, "kind": "pathology", "event_date": "2026-01-10",
            "issued_at": "2026-01-11", "received_at": "2026-01-12T00:00:00+00:00",
            "specimen_id": "SPECIMEN-FICTIONAL", "state": "current", "supersedes_id": None,
        }],
        "source_reported_assertions": [{
            "source_id": SOURCE, "finding_key": "marker", "reported_state": state,
            "source_statement": STATEMENT, "source_line": 2,
            "clinical_review_state": "not_established",
        }],
    }
    world = project_source_world_model(index)
    question = {
        "question_id": QUESTION_ID, "patient_id": PATIENT, "case_id": "CASE-ALPHA",
        "question": QUESTION, "source_id": SOURCE, "source_line": 2,
        "source_sha256": digest, "source_version": 1,
        "source_snapshot_contract": "oi.pg-source-world-model/1",
        "source_snapshot_sha256": world["snapshot_fingerprint"],
        "preflight_sha256": "e" * 64, "created_at": "2026-02-03T00:00:00+00:00",
        "source_context_state": "current_unreviewed_question",
        "human_review_state": "not_submitted", "clinical_approval": False,
        "model_executed": False,
    }
    selected = {
        "source_id": SOURCE, "document_id": "DOC-FICTIONAL", "version": 1,
        "sha256": digest, "line": 2, "finding_key": "marker", "reported_state": state,
        "statement": STATEMENT, "kind": "pathology", "event_date": "2026-01-10",
        "issued_at": "2026-01-11", "specimen_id": "SPECIMEN-FICTIONAL",
    }
    return world, question, selected


class QuestionBriefBoundaryTests(unittest.TestCase):
    def test_brief_requires_trusted_identity_before_any_database_operation(self):
        """An unregistered or unprotected export route must not hide as 404/200."""
        path = ("/v1/patients/PAT-" + "A" * 32 +
                "/cases/CASE-ALPHA/questions/QUESTION-" + "B" * 32 + "/brief")
        intent = {
            "synthetic": True,
            "source_snapshot_contract": "oi.pg-source-world-model/1",
            "expected_source_snapshot_sha256": "a" * 64,
            "expected_preflight_sha256": "b" * 64,
        }
        with running_server(create_app(Settings.from_env({}))) as base:
            for token in (None, "unrecognized-fictional-token"):
                with self.subTest(token_present=token is not None):
                    status, body, headers = patient_fixture.request(
                        base, path, token=token, body=intent,
                    )
                    self.assertEqual(status, 401, body)
                    self.assertEqual(body, {"detail": "Authentication required"})
                    self.assertEqual(headers["Cache-Control"], "no-store")


class QuestionBriefRendererTests(unittest.TestCase):
    def render(self, *inputs, prepared_at=PREPARED_AT):
        renderer = getattr(question_owner, "render_source_brief", None)
        self.assertTrue(callable(renderer), "The source brief renderer is not implemented")
        return renderer(*(inputs or fictional_brief_inputs()), prepared_at=prepared_at)

    def test_body_keeps_literal_source_question_dates_and_hash_without_mutating_inputs(self):
        inputs = fictional_brief_inputs()
        before = deepcopy(inputs)
        brief = self.render(*inputs)
        self.assertEqual(inputs, before)
        self.assertEqual(set(brief), RESPONSE_FIELDS)
        self.assertEqual(brief["contract"], "oi.synthetic-source-brief/2")
        self.assertEqual(brief["media_type"], "text/plain;charset=utf-8")
        self.assertEqual(brief["question"], before[1])
        self.assertEqual(brief["selected_source"], before[2])
        self.assertEqual(brief["source_snapshot_sha256"], before[0]["snapshot_fingerprint"])
        self.assertEqual(datetime.fromisoformat(brief["prepared_at"]), PREPARED_AT)
        self.assertEqual(brief["body_sha256"], hashlib.sha256(brief["body"].encode("utf-8")).hexdigest())
        for literal in (QUESTION, STATEMENT, SOURCE, "DOC-FICTIONAL", before[2]["sha256"],
                        "2026-01-10", "2026-01-11", "2026-11-03", "not-assessed"):
            self.assertIn(literal, brief["body"])
        self.assertIs(brief["synthetic"], True)
        for field in ("clinical_approval", "model_executed", "biomedical_evidence_included"):
            self.assertIs(brief[field], False)
        self.assertRegex(brief["body"].lower(), r"fictional|synthetic")
        self.assertRegex(brief["body"].lower(), r"unreviewed|not.submitted|no.{0,30}review|not.{0,30}review")

    def test_unknown_negative_and_pending_source_states_are_not_collapsed(self):
        for state in ("not-reported", "not-assessed", "pending", "indeterminate", "negative"):
            with self.subTest(state=state):
                brief = self.render(*fictional_brief_inputs(state))
                self.assertEqual(brief["selected_source"]["reported_state"], state)
                self.assertIn(state, brief["body"])
                self.assertFalse(brief["clinical_approval"])

    def test_stale_legacy_or_clinically_promoted_question_cannot_render(self):
        changes = (
            ("source_context_state", "source_reassessment_required"),
            ("source_snapshot_contract", "oi.synthetic-postgres-world-model-sources/1"),
            ("source_snapshot_sha256", "0" * 64),
            ("source_sha256", "0" * 64),
            ("source_version", 2), ("source_line", 3),
            ("patient_id", "PAT-" + "F" * 32), ("case_id", "CASE-BETA"),
            ("clinical_approval", True), ("model_executed", True),
            ("human_review_state", "approved"),
        )
        for field, value in changes:
            with self.subTest(field=field):
                world, question, selected = fictional_brief_inputs()
                question[field] = value
                with self.assertRaises(PatientRegistryError):
                    self.render(world, question, selected)

    def test_selected_quote_must_match_its_exact_current_world_model_anchor(self):
        changes = (
            ("source_id", "SRC-" + "F" * 32), ("line", 3), ("version", 2),
            ("sha256", "0" * 64), ("statement", "Forged fictional quotation."),
            ("document_id", "DOC-OTHER"), ("reported_state", "reported"),
            ("event_date", "2026-09-09"), ("specimen_id", "SPECIMEN-OTHER"),
        )
        for field, value in changes:
            with self.subTest(field=field):
                world, question, selected = fictional_brief_inputs()
                selected[field] = value
                with self.assertRaises(PatientRegistryError):
                    self.render(world, question, selected)

    def test_response_boundary_rejects_forged_claims_body_digest_and_unknown_fields(self):
        brief = self.render()
        response_model = getattr(patient_routes, "SourceQuestionBrief", None)
        self.assertIsNotNone(response_model, "Typed source brief response is not implemented")
        response_model(**brief)
        changes = (
            {"contract": "oi.synthetic-source-brief/1"}, {"synthetic": False},
            {"clinical_approval": True}, {"model_executed": True},
            {"biomedical_evidence_included": True}, {"body": "Substituted export body."},
            {"body_sha256": "0" * 64}, {"unknown_clinical_field": "approved"},
            {"question": {**brief["question"], "clinical_approval": True}},
        )
        for change in changes:
            with self.subTest(change=list(change)), self.assertRaises(ValidationError):
                response_model(**{**brief, **change})

    def test_complete_response_envelope_must_fit_even_when_body_alone_fits(self):
        brief = self.render()
        response_model = getattr(patient_routes, "SourceQuestionBrief", None)
        self.assertIsNotNone(response_model, "Typed source brief response is not implemented")
        body = "z" * 65_500
        oversized = {**brief, "body": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest()}
        self.assertLess(len(body.encode("utf-8")), 65_536)
        self.assertGreater(len(json.dumps(oversized, ensure_ascii=False, separators=(",", ":")).encode()), 65_536)
        with self.assertRaises(ValidationError):
            response_model(**oversized)


if __name__ == "__main__":
    unittest.main()
