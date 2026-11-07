"""Fictional owner-DTO -> semantic reference -> selective impact acceptance.

No database access or clinical state transition. The DTOs represent outputs
which existing H1 services must obtain and authorize before invoking this seam.
"""
import unittest

from open_intelligence.dependency_impact import Dependency, VersionedNode, plan_amendment_impact
from open_intelligence.h1_semantic_bridge import bind_authorized_h1_question
from open_intelligence.semantic_contract import Concept, Relationship, SemanticRegistry

SID = "SRC-" + "A" * 32
QID = "QUESTION-" + "B" * 32
SHA = "c" * 64


class SyntheticCrossModuleContractTests(unittest.TestCase):
    def test_h1_question_impact_is_version_specific_and_review_only(self):
        registry = SemanticRegistry(
            (Concept("oi:observation", 1, "Source report"),
             Concept("oi:investigation", 1, "Question")),
            (Relationship("oi:source-to-question", 1, "oi:observation", "oi:investigation"),),
        )
        question = {
            "patient_id": "P1", "case_id": "CASE-1", "source_id": SID,
            "question_id": QID, "source_sha256": SHA, "source_version": 1,
            "source_line": 3, "source_context_state": "source_reassessment_required",
            "human_review_state": "not_submitted", "clinical_approval": False,
        }
        source = {"source_id": SID, "sha256": SHA, "version": 1}
        bound = bind_authorized_h1_question(
            registry=registry, question=question, source=source,
            authorized_patient_id="P1", authorized_case_id="CASE-1",
        )
        self.assertTrue(bound.requires_reassessment)
        old = VersionedNode(bound.source.owner, bound.source.record_id,
                            bound.source.source_version_id, "CASE-1", "source")
        question_node = VersionedNode(bound.question.owner, bound.question.record_id,
                                      bound.question.source_version_id, "CASE-1", "investigation")
        other = VersionedNode("h1.source_versions", "OTHER-SOURCE", "v1", "CASE-1", "source")
        other_calculation = VersionedNode("calculation", "unrelated", "v1", "CASE-1", "calculation")
        nodes = (old, question_node, other, other_calculation)
        edges = (Dependency(old.key, question_node.key),
                 Dependency(other.key, other_calculation.key))
        impact = plan_amendment_impact(
            nodes, edges, amended_source_key=old.key, case_id="CASE-1",
        )
        self.assertEqual(impact.recompute, ())
        self.assertEqual(impact.review, (question_node,))
        self.assertNotIn(other_calculation, impact.recompute)
        self.assertEqual(
            plan_amendment_impact(nodes, edges, amended_source_key=other.key,
                                  case_id="CASE-1").recompute, (other_calculation,),
        )


if __name__ == "__main__":
    unittest.main()
