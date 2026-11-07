"""H1 source/question projection contract tests for unittest discovery."""
import unittest

from open_intelligence.h1_semantic_bridge import bind_authorized_h1_question
from open_intelligence.semantic_contract import (
    Concept, Relationship, SemanticContractError, SemanticRegistry,
)

SID = "SRC-" + "A" * 32
QID = "QUESTION-" + "B" * 32
DIGEST = "c" * 64


def registry():
    return SemanticRegistry(
        (Concept("oi:observation", 1, "Source report"),
         Concept("oi:investigation", 1, "Saved question")),
        (Relationship("oi:source-to-question", 1, "oi:observation", "oi:investigation"),),
    )


def projections():
    question = dict(patient_id="P1", case_id="CASE-1", source_id=SID, question_id=QID,
                    source_sha256=DIGEST, source_version=1, source_line=2,
                    source_context_state="current_unreviewed_question",
                    human_review_state="not_submitted", clinical_approval=False)
    source = dict(source_id=SID, sha256=DIGEST, version=1)
    return question, source


def bind(q, s):
    return bind_authorized_h1_question(
        registry=registry(), question=q, source=s,
        authorized_patient_id="P1", authorized_case_id="CASE-1",
    )


class H1SemanticBridgeTests(unittest.TestCase):
    def assert_rejected(self, reason, callback):
        with self.assertRaises(SemanticContractError) as error:
            callback()
        self.assertEqual(error.exception.code, reason)

    def test_bind_exact_source_version(self):
        q, s = projections()
        result = bind(q, s)
        self.assertEqual(result.source.record_id, SID)
        self.assertEqual(result.question.record_id, QID)
        self.assertEqual(result.source.source_version_id, result.question.source_version_id)
        self.assertFalse(result.requires_reassessment)

    def test_stale_question_remains_unreviewed(self):
        q, s = projections()
        q["source_context_state"] = "source_reassessment_required"
        self.assertTrue(bind(q, s).requires_reassessment)

    def test_invalid_question_projection(self):
        for target, value, reason in (
            ("patient_id", "P2", "scope_mismatch"),
            ("case_id", "CASE-2", "scope_mismatch"),
            ("source_id", "SRC-other", "invalid_owner_identity"),
            ("source_sha256", "wrong", "invalid_owner_identity"),
            ("source_version", 2, "source_version_mismatch"),
            ("source_line", 0, "source_version_mismatch"),
            ("human_review_state", "approved", "unsupported_review_claim"),
            ("clinical_approval", True, "unsupported_review_claim"),
            ("source_context_state", "reviewed", "unknown_question_state"),
        ):
            with self.subTest(field=target, value=value):
                q, s = projections()
                q[target] = value
                self.assert_rejected(reason, lambda: bind(q, s))

    def test_mismatched_source_projection(self):
        for target, value in (
            ("source_id", "SRC-" + "D" * 32),
            ("sha256", "d" * 64),
            ("version", 2),
        ):
            with self.subTest(field=target, value=value):
                q, s = projections()
                s[target] = value
                self.assert_rejected("source_version_mismatch", lambda: bind(q, s))


if __name__ == "__main__":
    unittest.main()
