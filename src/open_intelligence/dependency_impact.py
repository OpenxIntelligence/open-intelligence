"""Conservative dependency impact planning over owner-verified immutable versions.

Pure analysis only: never reads records, changes state, grants access or
authorizes clinical review. The existing PostgreSQL owners must supply an
authorized, complete single-case snapshot and persist resulting transitions.
"""
from __future__ import annotations
from dataclasses import dataclass


class ImpactContractError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class VersionedNode:
    owner: str
    record_id: str
    version_id: str
    case_id: str
    kind: str

    def __post_init__(self):
        if self.kind not in {"source", "calculation", "investigation", "review_task"}:
            raise ImpactContractError("unsupported_kind")
        if any(not isinstance(v, str) or not v or v != v.strip()
               for v in (self.owner, self.record_id, self.version_id, self.case_id)):
            raise ImpactContractError("invalid_node_identity")

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.owner, self.record_id, self.version_id)


@dataclass(frozen=True)
class Dependency:
    input_key: tuple[str, str, str]
    output_key: tuple[str, str, str]


@dataclass(frozen=True)
class Impact:
    recompute: tuple[VersionedNode, ...]
    review: tuple[VersionedNode, ...]


def plan_amendment_impact(
    nodes: tuple[VersionedNode, ...],
    dependencies: tuple[Dependency, ...],
    *,
    amended_source_key: tuple[str, str, str],
    case_id: str,
) -> Impact:
    """Identify dependent-only stale candidates, without mutating history."""
    by_key: dict[tuple[str, str, str], VersionedNode] = {}
    for node in nodes:
        if node.key in by_key:
            raise ImpactContractError("duplicate_node")
        if node.case_id != case_id:
            raise ImpactContractError("cross_case_node")
        by_key[node.key] = node
    source = by_key.get(amended_source_key)
    if source is None or source.kind != "source":
        raise ImpactContractError("unknown_source_version")
    downstream: dict[tuple[str, str, str], set[tuple[str, str, str]]] = {}
    for edge in dependencies:
        if edge.input_key not in by_key or edge.output_key not in by_key:
            raise ImpactContractError("unknown_dependency_node")
        downstream.setdefault(edge.input_key, set()).add(edge.output_key)

    visiting: set[tuple[str, str, str]] = set()
    visited: set[tuple[str, str, str]] = set()

    def check_acyclic(key: tuple[str, str, str]) -> None:
        if key in visiting:
            raise ImpactContractError("cyclic_dependency")
        if key in visited:
            return
        visiting.add(key)
        for child in sorted(downstream.get(key, ())):
            check_acyclic(child)
        visiting.remove(key)
        visited.add(key)

    for key in sorted(by_key):
        check_acyclic(key)
    affected: set[tuple[str, str, str]] = set()
    pending = list(sorted(downstream.get(amended_source_key, ())))
    while pending:
        key = pending.pop()
        if key in affected:
            continue
        affected.add(key)
        pending.extend(sorted(downstream.get(key, ())))
    if any(by_key[key].kind == "source" for key in affected):
        raise ImpactContractError("source_as_derived_output")
    recompute = tuple(sorted((by_key[key] for key in affected
                              if by_key[key].kind == "calculation"), key=lambda n: n.key))
    review = tuple(sorted((by_key[key] for key in affected
                           if by_key[key].kind in {"investigation", "review_task"}), key=lambda n: n.key))
    return Impact(recompute=recompute, review=review)
