"""Versioned, domain-neutral semantic mapping contract.

Pure validation only. Does not store clinical records, grant authority, or
infer that a source is clinically true. Owners persist references themselves.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

KnowledgeKind = Literal["observed", "reported", "inferred", "calculated", "hypothesis"]
EvidenceStatus = Literal["present", "negative", "missing", "pending", "indeterminate", "conflicting"]


class SemanticContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Concept:
    identifier: str
    version: int
    definition: str


@dataclass(frozen=True)
class Relationship:
    identifier: str
    version: int
    source_concept: str
    target_concept: str


@dataclass(frozen=True)
class SemanticReference:
    owner: str
    record_id: str
    concept_id: str
    concept_version: int
    source_version_id: str
    knowledge_kind: KnowledgeKind
    evidence_status: EvidenceStatus


class SemanticRegistry:
    """Explicit versioned identifiers and domain/range checks, no implicit coercion."""

    def __init__(self, concepts: tuple[Concept, ...], relationships: tuple[Relationship, ...]):
        self.concepts: dict[tuple[str, int], Concept] = {}
        self.relationships: dict[tuple[str, int], Relationship] = {}
        for concept in concepts:
            self._check_id(concept.identifier)
            if type(concept.version) is not int or concept.version < 1 or not isinstance(concept.definition, str) or not concept.definition.strip():
                raise SemanticContractError("invalid_concept")
            key = (concept.identifier, concept.version)
            if key in self.concepts:
                raise SemanticContractError("duplicate_concept")
            self.concepts[key] = concept
        for relation in relationships:
            self._check_id(relation.identifier)
            if type(relation.version) is not int or relation.version < 1:
                raise SemanticContractError("invalid_relationship")
            key = (relation.identifier, relation.version)
            if key in self.relationships:
                raise SemanticContractError("duplicate_relationship")
            if not any(k[0] == relation.source_concept for k in self.concepts):
                raise SemanticContractError("unknown_source_concept")
            if not any(k[0] == relation.target_concept for k in self.concepts):
                raise SemanticContractError("unknown_target_concept")
            self.relationships[key] = relation

    @staticmethod
    def _check_id(value: str) -> None:
        if not isinstance(value, str) or not value or value.strip() != value or ":" not in value or value.startswith(":") or value.endswith(":"):
            raise SemanticContractError("invalid_semantic_id")

    def validate_reference(self, ref: SemanticReference) -> None:
        if (ref.concept_id, ref.concept_version) not in self.concepts:
            raise SemanticContractError("unknown_concept_version")
        if any(not isinstance(value, str) or not value.strip() or value != value.strip()\n               for value in (ref.owner, ref.record_id, ref.source_version_id)):
            raise SemanticContractError("missing_provenance")
        if ref.knowledge_kind not in ("observed", "reported", "inferred", "calculated", "hypothesis"):
            raise SemanticContractError("invalid_knowledge_kind")
        if ref.evidence_status not in ("present", "negative", "missing", "pending", "indeterminate", "conflicting"):
            raise SemanticContractError("invalid_evidence_status")

    def validate_edge(self, relation_id: str, version: int, source: SemanticReference, target: SemanticReference) -> None:
        self.validate_reference(source)
        self.validate_reference(target)
        relation = self.relationships.get((relation_id, version))
        if relation is None:
            raise SemanticContractError("unknown_relationship_version")
        if source.concept_id != relation.source_concept or target.concept_id != relation.target_concept:
            raise SemanticContractError("relationship_domain_range_mismatch")
