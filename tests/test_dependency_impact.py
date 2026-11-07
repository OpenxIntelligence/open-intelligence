"""Synthetic exact-version dependency impact regressions."""
import pytest

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


def test_exact_version_selective_impact():
    nodes, edges = fixture()
    impact = plan_amendment_impact(nodes, edges, amended_source_key=nodes[0].key, case_id="case-a")
    assert [n.record_id for n in impact.recompute] == ["score"]
    assert [n.record_id for n in impact.review] == ["question", "task"]
    assert plan_amendment_impact(nodes, edges, amended_source_key=nodes[1].key, case_id="case-a").recompute == ()
    assert impact == plan_amendment_impact(nodes, edges, amended_source_key=nodes[0].key, case_id="case-a")


def test_reject_cross_case():
    nodes, edges = fixture()
    with pytest.raises(ImpactContractError, match="cross_case_node"):
        plan_amendment_impact(nodes + (node("source", "foreign", case="case-b"),), edges,
                              amended_source_key=nodes[0].key, case_id="case-a")


def test_reject_unknown_edge():
    nodes, edges = fixture()
    with pytest.raises(ImpactContractError, match="unknown_dependency_node"):
        plan_amendment_impact(nodes, edges + (Dependency(("x", "y", "z"), nodes[3].key),),
                              amended_source_key=nodes[0].key, case_id="case-a")


def test_reject_cycle_even_when_unreachable():
    nodes, edges = fixture()
    with pytest.raises(ImpactContractError, match="cyclic_dependency"):
        plan_amendment_impact(nodes, edges + (Dependency(nodes[6].key, nodes[2].key),),
                              amended_source_key=nodes[0].key, case_id="case-a")


def test_reject_derived_source():
    nodes, edges = fixture()
    with pytest.raises(ImpactContractError, match="source_as_derived_output"):
        plan_amendment_impact(nodes, edges + (Dependency(nodes[3].key, nodes[1].key),),
                              amended_source_key=nodes[0].key, case_id="case-a")


def test_reject_duplicate_node():
    nodes, edges = fixture()
    with pytest.raises(ImpactContractError, match="duplicate_node"):
        plan_amendment_impact(nodes + (nodes[0],), edges, amended_source_key=nodes[0].key, case_id="case-a")
