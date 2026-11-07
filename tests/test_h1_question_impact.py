"""Pure synthetic H1 saved-question amendment impact contract tests."""
import unittest

from open_intelligence.dependency_impact import ImpactContractError
from open_intelligence.h1_question_impact import plan_h1_question_reassessment
from open_intelligence.h1_semantic_bridge import BoundQuestion
from open_intelligence.semantic_contract import SemanticReference


def bound(source_id, version, question_id):
    version_id = f"{source_id}:{version}:" + "c" * 64
    return BoundQuestion(
        source=SemanticReference("h1.source_versions", source_id, "oi:observation",
                                 1, version_id, "reported", "present"),
        question=SemanticReference("h1.source_questions", question_id, "oi:investigation",
                                   1, version_id, "hypothesis", "pending"),
        source_sha256="c" * 64, source_line=1, requires_reassessment=True,
    )


class H1QuestionImpactTests(unittest.TestCase):
    def test_exact_source_version_only(self):
        old = bound("SRC-OLD", 1, "QUESTION-OLD")
        new = bound("SRC-OLD", 2, "QUESTION-NEW")
        other = bound("SRC-OTHER", 1, "QUESTION-OTHER")
        result = plan_h1_question_reassessment(
            (old, new, other), case_id="CASE-1",
            amended_source_version_id=old.source.source_version_id,
        )
        self.assertEqual(result, ("QUESTION-OLD",))
        self.assertEqual(plan_h1_question_reassessment(
            (old, new, other), case_id="CASE-1",
            amended_source_version_id=new.source.source_version_id,
        ), ("QUESTION-NEW",))

    def test_multiple_questions_share_one_source(self):
        first = bound("SRC-OLD", 1, "QUESTION-A")
        second = bound("SRC-OLD", 1, "QUESTION-B")
        self.assertEqual(plan_h1_question_reassessment(
            (second, first), case_id="CASE-1",
            amended_source_version_id=first.source.source_version_id,
        ), ("QUESTION-A", "QUESTION-B"))

    def test_unknown_source_fails_closed(self):
        first = bound("SRC-OLD", 1, "QUESTION-A")
        with self.assertRaisesRegex(ImpactContractError, "unknown_or_ambiguous_amended_source"):
            plan_h1_question_reassessment(
                (first,), case_id="CASE-1", amended_source_version_id="missing",
            )

    def test_conflicting_question_version_rejected(self):
        first = bound("SRC-OLD", 1, "QUESTION-A")
        second = bound("SRC-OLD", 2, "QUESTION-A")
        # Two historical versions of one question are distinct nodes; the
        # owner must decide which immutable versions are actionable.
        self.assertEqual(plan_h1_question_reassessment(
            (first, second), case_id="CASE-1",
            amended_source_version_id=first.source.source_version_id,
        ), ("QUESTION-A",))


if __name__ == "__main__":
    unittest.main()
