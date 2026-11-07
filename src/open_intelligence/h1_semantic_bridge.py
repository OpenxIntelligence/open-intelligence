"""Fail-closed bridge from H1 source-question projections to semantic references.

This adapter consumes *already authorized* projections returned by the
canonical H1 source and question owners. It performs no database access and
cannot grant source/original access, create an investigation, or assert review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .semantic_contract import SemanticContractError, SemanticReference, SemanticRegistry

SOURCE_ID = re.compile(r"SRC-[0-9A-F]{32}\Z")
QUESTION_ID = re.compile(r"QUESTION-[0-9A-F]{32}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class BoundQuestion:
    source: SemanticReference
    question: SemanticReference
    source_sha256: str
    source_line: int
    requires_reassessment: bool


def bind_authorized_h1_question(
    *,
    registry: SemanticRegistry,
    question: dict,
    source: dict,
    authorized_patient_id: str,
    authorized_case_id: str,
) -> BoundQuestion:
    """Bind owner-issued identifiers only after strict source/version matching.

    Callers must obtain both projections under current grants, and recheck
    authorization at disclosure/commit. This is validation, not authorization.
    """
    if not isinstance(question, dict) or not isinstance(source, dict):
        raise SemanticContractError("invalid_owner_projection")
    if any(not isinstance(v, str) or not v for v in (authorized_patient_id, authorized_case_id)):
        raise SemanticContractError("missing_scope")
    if question.get("patient_id") != authorized_patient_id or question.get("case_id") != authorized_case_id:
        raise SemanticContractError("scope_mismatch")
    source_id = question.get("source_id")
    question_id = question.get("question_id")
    digest = question.get("source_sha256")
    if (type(source_id) is not str or SOURCE_ID.fullmatch(source_id) is None
            or type(question_id) is not str or QUESTION_ID.fullmatch(question_id) is None
            or type(digest) is not str or SHA256.fullmatch(digest) is None):
        raise SemanticContractError("invalid_owner_identity")
    if source.get("source_id") != source_id or source.get("sha256") != digest:
        raise SemanticContractError("source_version_mismatch")
    version = question.get("source_version")
    line = question.get("source_line")
    if (type(version) is not int or version < 1 or source.get("version") != version
            or type(line) is not int or line < 1):
        raise SemanticContractError("source_version_mismatch")
    state = question.get("source_context_state")
    if state not in ("current_unreviewed_question", "source_reassessment_required"):
        raise SemanticContractError("unknown_question_state")
    if question.get("human_review_state") != "not_submitted" or question.get("clinical_approval") is not False:
        raise SemanticContractError("unsupported_review_claim")
    source_ref = SemanticReference(
        owner="h1.source_versions", record_id=source_id, concept_id="oi:observation",
        concept_version=1, source_version_id=f"{source_id}:{version}:{digest}",
        knowledge_kind="reported", evidence_status="present",
    )
    question_ref = SemanticReference(
        owner="h1.source_questions", record_id=question_id, concept_id="oi:investigation",
        concept_version=1, source_version_id=f"{source_id}:{version}:{digest}",
        knowledge_kind="hypothesis", evidence_status="pending",
    )
    registry.validate_edge("oi:source-to-question", 1, source_ref, question_ref)
    return BoundQuestion(
        source=source_ref, question=question_ref, source_sha256=digest,
        source_line=line, requires_reassessment=state == "source_reassessment_required",
    )
