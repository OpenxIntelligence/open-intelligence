"""Synthetic dependency impact regressions using unittest discovery."""
import unittest

from open_intelligence.dependency_impact import (
    Dependency, ImpactContractError, VersionedNode, plan_amendment_impact,
)


def node(kind, record, version="1", case="case-a"):
    return VersionedNode("owner", record, version, case, kind)


def fixture():
    old = node("source", "lab", "1")
    new = node("source", "lab", "2")
    unrelated = node("source", "imaging")
    calculation = node("calculation", "score")
    question = node("investigation", "question")
    task = node("review_task", "task")
    other_calc = node("calculation", "other-score")
    nodes = (old, new, unrelated, calculation, question, task, other_calc)
    edges = (Dependency(old.key, calculation.key),
             Dependency(calculation.key, question.key),
             Dependency(question.key, task.key),
             Dependency(unrelated.key, other_calc.key))
    return nodes, edges


class DependencyImpactTests(unittest.TestCase):
    def assert_rejected(self, reason, callback):
        with self.assertRaises(ImpactContractError) as error:
            callback()
        self.assertEqual(error.exception.reason, reason)

    def test_exact_version_selective_impact(self):
        nodes, edges = fixture()
        impact = plan_amendment_impact(nodes, edges, amended_source_key=nodes[0].key, case_id="case-a")
        self.assertEqual([n.record_id for n in impact.recompute], ["score"])
        self.assertEqual([n.record_id for n in impact.review], ["question", "task"])
        self.assertEqual(plan_amendment_impact(
            nodes, edges, amended_source_key=nodes[1].key, case_id="case-a").recompute, ())
        self.assertEqual(impact, plan_amendment_impact(
            nodes, edges, amended_source_key=nodes[0].key, case_id="case-a"))

    def test_reject_cross_case(self):
        nodes, edges = fixture()
        self.assert_rejected("cross_case_node", lambda: plan_amendment_impact(
            nodes + (node("source", "foreign", case="case-b"),), edges,
            amended_source_key=nodes[0].key, case_id="case-a"))

    def test_reject_unknown_edge(self):
        nodes, edges = fixture()
        self.assert_rejected("unknown_dependency_node", lambda: plan_amendment_impact(
            nodes, edges + (Dependency(("x", "y", "z"), nodes[3].key),),
            amended_source_key=nodes[0].key, case_id="case-a"))

    def test_reject_cycle_even_when_unreachable(self):
        nodes, edges = fixture()
        self.assert_rejected("cyclic_dependency", lambda: plan_amendment_impact(
            nodes, edges + (Dependency(nodes[6].key, nodes[2].key),),
            amended_source_key=nodes[0].key, case_id="case-a"))

    def test_reject_derived_source(self):
        nodes, edges = fixture()
        self.assert_rejected("source_as_derived_output", lambda: plan_amendment_impact(
            nodes, edges + (Dependency(nodes[3].key, nodes[1].key),),
            amended_source_key=nodes[0].key, case_id="case-a"))

    def test_reject_duplicate_node(self):
        nodes, edges = fixture()
        self.assert_rejected("duplicate_node", lambda: plan_amendment_impact(
            nodes + (nodes[0],), edges,
            amended_source_key=nodes[0].key, case_id="case-a"))


if __name__ == "__main__":
    unittest.main()
