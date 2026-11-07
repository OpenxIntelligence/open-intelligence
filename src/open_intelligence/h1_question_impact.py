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
    question_versions: dict[str, str] = {}
    for bound in bound_questions:
        if not isinstance(bound, BoundQuestion):
            raise ImpactContractError("invalid_question_snapshot")
        source = bound.source
        question = bound.question
        previous_version = question_versions.get(question.record_id)
        if previous_version is not None:
            raise ImpactContractError("duplicate_or_ambiguous_question")
        question_versions[question.record_id] = question.source_version_id
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


def plan_h1_confirmed_supersessions(
    sources: list[dict],
    bound_questions: tuple[BoundQuestion, ...],
    *,
    case_id: str,
) -> tuple[dict, ...]:
    """Derive direct saved-question impact only from canonical source lineage.

    The H1 source owner must supply a complete, validated single-case index
    under current grants. Supersession is established by its immutable
    `supersedes_id`, document identity, consecutive versions and old state.
    A global snapshot fingerprint change alone is *not* direct dependency
    evidence. This projection never persists an invalidation.
    """
    from .h1_semantic_bridge import SHA256, SOURCE_ID

    if not isinstance(sources, list) or not isinstance(bound_questions, tuple):
        raise ImpactContractError("invalid_owner_snapshot")
    by_id: dict[str, dict] = {}
    for source in sources:
        if not isinstance(source, dict):
            raise ImpactContractError("invalid_owner_source")
        sid, version, sha = (source.get(k) for k in ("source_id", "version", "sha256"))
        document_id, state = source.get("document_id"), source.get("state")
        previous = source.get("supersedes_id")
        if (type(sid) is not str or SOURCE_ID.fullmatch(sid) is None
                or type(version) is not int or version < 1
                or type(sha) is not str or SHA256.fullmatch(sha) is None
                or type(document_id) is not str or not document_id
                or state not in {"current", "superseded"}
                or (previous is not None and
                    (type(previous) is not str or SOURCE_ID.fullmatch(previous) is None))):
            raise ImpactContractError("invalid_owner_source")
        if sid in by_id:
            raise ImpactContractError("duplicate_owner_source")
        by_id[sid] = source

    for bound in bound_questions:
        if not isinstance(bound, BoundQuestion):
            raise ImpactContractError("invalid_question_snapshot")
        previous_source = by_id.get(bound.source.record_id)
        if previous_source is None:
            raise ImpactContractError("unknown_question_source")
        expected = (f"{previous_source['source_id']}:"
                    f"{previous_source['version']}:{previous_source['sha256']}")
        if bound.source.source_version_id != expected or bound.question.source_version_id != expected:
            raise ImpactContractError("source_version_mismatch")

    entries = []
    superseded_once: set[str] = set()
    for new in sorted(sources, key=lambda item: (item["document_id"], item["version"])):
        prior_id = new["supersedes_id"]
        if prior_id is None:
            if new["version"] != 1:
                raise ImpactContractError("broken_source_lineage")
            continue
        previous = by_id.get(prior_id)
        if (previous is None or previous["document_id"] != new["document_id"]
                or previous["version"] + 1 != new["version"]
                or previous["state"] != "superseded" or prior_id in superseded_once):
            raise ImpactContractError("broken_source_lineage")
        superseded_once.add(prior_id)
        old_version_id = (f"{previous['source_id']}:"
                          f"{previous['version']}:{previous['sha256']}")
        affected = tuple(bound for bound in bound_questions
                         if bound.source.source_version_id == old_version_id)
        if any(not bound.requires_reassessment for bound in affected):
            raise ImpactContractError("inconsistent_reassessment_state")
        question_ids = (plan_h1_question_reassessment(
            affected, case_id=case_id, amended_source_version_id=old_version_id,
        ) if affected else ())
        entries.append({
            "superseded_source_id": prior_id,
            "amending_source_id": new["source_id"],
            "source_version_id": old_version_id,
            "question_ids": question_ids,
        })
    return tuple(entries)
