"""Version-specific question impact from an owner-authorized H1 projection.

This intentionally covers *only* H1 source -> saved-question dependencies.
It cannot claim to discover calculation/report/task dependencies without those
canonical owners exposing a complete authorized dependency snapshot.
"""
from __future__ import annotations

from .dependency_impact import (
    Dependency, ImpactContractError, VersionedNode, plan_amendment_impact,
)
from .h1_semantic_bridge import BoundQuestion


def plan_h1_question_reassessment(
    bound_questions: tuple[BoundQuestion, ...],
    *,
    case_id: str,
    amended_source_version_id: str,
) -> tuple[str, ...]:
    """Return exact saved question IDs requiring reassessment, never mutate them.

    The owner must establish that an amendment actually supersedes the named
    source version and that the supplied projection is complete and authorized.
    """
    if (type(case_id) is not str or not case_id or case_id != case_id.strip()
            or type(amended_source_version_id) is not str or not amended_source_version_id):
        raise ImpactContractError("invalid_amendment_scope")
    if not isinstance(bound_questions, tuple):
        raise ImpactContractError("invalid_question_snapshot")
    nodes: dict[tuple[str, str, str], VersionedNode] = {}
    edges: set[Dependency] = set()
    for bound in bound_questions:
        if not isinstance(bound, BoundQuestion):
            raise ImpactContractError("invalid_question_snapshot")
        source = bound.source
        question = bound.question
        if source.source_version_id != question.source_version_id:
            raise ImpactContractError("source_version_mismatch")
        if source.owner != "h1.source_versions" or question.owner != "h1.source_questions":
            raise ImpactContractError("unexpected_owner")
        source_node = VersionedNode(source.owner, source.record_id,
                                    source.source_version_id, case_id, "source")
        question_node = VersionedNode(question.owner, question.record_id,
                                      question.source_version_id, case_id, "investigation")
        for node in (source_node, question_node):
            old = nodes.get(node.key)
            if old is not None and old != node:
                raise ImpactContractError("conflicting_node")
            nodes[node.key] = node
        edges.add(Dependency(source_node.key, question_node.key))
    candidates = [node for node in nodes.values()
                  if node.kind == "source" and node.version_id == amended_source_version_id]
    if len(candidates) != 1:
        raise ImpactContractError("unknown_or_ambiguous_amended_source")
    impact = plan_amendment_impact(
        tuple(nodes.values()), tuple(edges),
        amended_source_key=candidates[0].key, case_id=case_id,
    )
    return tuple(node.record_id for node in impact.review)
