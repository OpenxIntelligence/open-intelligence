"""H1 semantic snapshot must use the canonical locked source read owner."""
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from oi_api.source_questions import PostgresSourceQuestions

SID = "SRC-" + "A" * 32
QID = "QUESTION-" + "B" * 32
RECEIPT = "ACCESS-" + "C" * 32
SHA = "d" * 64


class FakeRegistry:
    def __init__(self):
        self.transaction_calls = 0

    def transaction(self):
        self.transaction_calls += 1
        return nullcontext()


class FakeOwner:
    def __init__(self, registry):
        self.registry = registry

    def list_locked(self, patient_id, case_id, *, organization, actor, purpose,
                    prepare_response, recheck_authority):
        assert self.registry.transaction_calls == 1
        assert (patient_id, case_id, organization, purpose) == (
            "P1", "CASE-1", "ORG1", "operations"
        )
        assert callable(recheck_authority)
        index = {
            "contract": "oi.synthetic-original-sources/1",
            "patient_id": patient_id, "case_id": case_id,
            "access_receipt_id": RECEIPT,
            "sources": [{"source_id": SID, "version": 1, "sha256": SHA}],
            "synthetic": True, "clinical_interpretation": False,
        }
        return prepare_response(index)


class FakeQuestionService:
    semantic_snapshot = PostgresSourceQuestions.semantic_snapshot

    def __init__(self, questions):
        self.registry = FakeRegistry()
        self.questions = questions

    def project_locked(self, patient_id, case_id, *, organization, source_index):
        assert source_index["access_receipt_id"] == RECEIPT
        return self.questions


def question():
    return {
        "question_id": QID, "patient_id": "P1", "case_id": "CASE-1",
        "source_id": SID, "source_version": 1, "source_sha256": SHA,
        "source_line": 1, "source_context_state": "source_reassessment_required",
        "human_review_state": "not_submitted", "clinical_approval": False,
    }


class SemanticOwnerReadTests(unittest.TestCase):
    def test_owner_transaction_and_receipt_are_reused(self):
        service = FakeQuestionService([question()])
        with patch("oi_api.source_questions.PostgresSourceVersions", FakeOwner):
            result = service.semantic_snapshot(
                "P1", "CASE-1", organization="ORG1", actor="actor",
                purpose="operations", recheck_authority=lambda: None,
            )
        self.assertEqual(service.registry.transaction_calls, 1)
        self.assertEqual(result["access_receipt_id"], RECEIPT)
        self.assertEqual(result["bindings"][0]["question_id"], QID)
        self.assertTrue(result["bindings"][0]["requires_reassessment"])
        self.assertFalse(result["clinical_approval"])

    def test_invalid_question_projection_rolls_back_owner_preparation(self):
        malformed = question()
        malformed["source_sha256"] = "0" * 64
        service = FakeQuestionService([malformed])
        with patch("oi_api.source_questions.PostgresSourceVersions", FakeOwner):
            with self.assertRaises(Exception):
                service.semantic_snapshot(
                    "P1", "CASE-1", organization="ORG1", actor="actor",
                    purpose="operations", recheck_authority=lambda: None,
                )
        self.assertEqual(service.registry.transaction_calls, 1)

    def test_empty_question_snapshot_is_nonclinical(self):
        service = FakeQuestionService([])
        with patch("oi_api.source_questions.PostgresSourceVersions", FakeOwner):
            result = service.semantic_snapshot(
                "P1", "CASE-1", organization="ORG1", actor="actor",
                purpose="operations", recheck_authority=lambda: None,
            )
        self.assertEqual(result["bindings"], [])
        self.assertFalse(result["clinical_approval"])

    def test_research_purpose_rejected_before_read(self):
        service = FakeQuestionService([question()])
        with self.assertRaises(Exception):
            service.semantic_snapshot(
                "P1", "CASE-1", organization="ORG1", actor="actor",
                purpose="research", recheck_authority=lambda: None,
            )
        self.assertEqual(service.registry.transaction_calls, 0)


if __name__ == "__main__":
    unittest.main()
