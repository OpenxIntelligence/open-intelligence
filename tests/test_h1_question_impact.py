"""Pure synthetic H1 saved-question amendment impact contract tests."""
import unittest

from open_intelligence.dependency_impact import ImpactContractError
from open_intelligence.h1_question_impact import (
    plan_h1_question_reassessment, plan_h1_confirmed_supersessions,
)
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
        with self.assertRaisesRegex(ImpactContractError, "duplicate_or_ambiguous_question"):
            plan_h1_question_reassessment(
                (first, second), case_id="CASE-1",
                amended_source_version_id=first.source.source_version_id,
            )

    def test_duplicate_question_snapshot_rejected(self):
        first = bound("SRC-OLD", 1, "QUESTION-A")
        with self.assertRaisesRegex(ImpactContractError, "duplicate_or_ambiguous_question"):
            plan_h1_question_reassessment(
                (first, first), case_id="CASE-1",
                amended_source_version_id=first.source.source_version_id,
            )


class ConfirmedH1SupersessionTests(unittest.TestCase):
    OLD = "SRC-" + "A" * 32
    NEW = "SRC-" + "B" * 32
    OTHER = "SRC-" + "C" * 32

    def sources(self):
        return [
            dict(source_id=self.OLD, document_id="DOC-ONE",
                 version=1, sha256="c" * 64, state="superseded",
                 supersedes_id=None),
            dict(source_id=self.NEW, document_id="DOC-ONE",
                 version=2, sha256="d" * 64, state="current",
                 supersedes_id=self.OLD),
            dict(source_id=self.OTHER, document_id="DOC-TWO",
                 version=1, sha256="c" * 64, state="current",
                 supersedes_id=None),
        ]

    def test_only_confirmed_direct_source_amendment_impacts_its_questions(self):
        older = bound(self.OLD, 1, "QUESTION-OLD")
        other = bound(self.OTHER, 1, "QUESTION-UNRELATED")
        impact = plan_h1_confirmed_supersessions(
            self.sources(), (other, older), case_id="CASE-1",
        )
        self.assertEqual(len(impact), 1)
        self.assertEqual(impact[0]["superseded_source_id"], self.OLD)
        self.assertEqual(impact[0]["amending_source_id"], self.NEW)
        self.assertEqual(impact[0]["question_ids"], ("QUESTION-OLD",))
        self.assertNotIn("QUESTION-UNRELATED", impact[0]["question_ids"])

    def test_nonamended_source_has_no_direct_impact(self):
        original = self.sources()[2]
        self.assertEqual(
            plan_h1_confirmed_supersessions(
                [original], (bound(self.OTHER, 1, "QUESTION-ONLY"),),
                case_id="CASE-1",
            ),
            (),
        )

    def test_amendment_without_questions_does_not_fabricate_review(self):
        impact = plan_h1_confirmed_supersessions(
            self.sources(), (), case_id="CASE-1",
        )
        self.assertEqual(len(impact), 1)
        self.assertEqual(impact[0]["question_ids"], ())

    def test_broken_cross_document_lineage_rejected(self):
        sources = self.sources()
        sources[1]["document_id"] = "DOC-TWO"
        with self.assertRaisesRegex(ImpactContractError, "broken_source_lineage"):
            plan_h1_confirmed_supersessions(sources, (), case_id="CASE-1")

    def test_non_superseded_predecessor_rejected(self):
        sources = self.sources()
        sources[0]["state"] = "current"
        with self.assertRaisesRegex(ImpactContractError, "broken_source_lineage"):
            plan_h1_confirmed_supersessions(sources, (), case_id="CASE-1")

    def test_missing_lineage_field_rejected(self):
        sources = self.sources()
        del sources[0]["supersedes_id"]
        with self.assertRaisesRegex(ImpactContractError, "invalid_owner_source"):
            plan_h1_confirmed_supersessions(sources, (), case_id="CASE-1")

    def test_inconsistent_question_reassessment_flag_rejected(self):
        from dataclasses import replace
        old = replace(bound(self.OLD, 1, "QUESTION-OLD"),
                      requires_reassessment=False)
        with self.assertRaisesRegex(ImpactContractError, "inconsistent_reassessment_state"):
            plan_h1_confirmed_supersessions(
                self.sources(), (old,), case_id="CASE-1",
            )

    def test_ambiguous_duplicate_source_rejected(self):
        sources = self.sources()
        sources.append(dict(sources[0]))
        with self.assertRaisesRegex(ImpactContractError, "duplicate_owner_source"):
            plan_h1_confirmed_supersessions(sources, (), case_id="CASE-1")


if __name__ == "__main__":
    unittest.main()
