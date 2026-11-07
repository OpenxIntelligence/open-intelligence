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


def bind_authorized_h1_question_list(
    *,
    registry: SemanticRegistry,
    question_list: dict,
    source_index: dict,
    authorized_patient_id: str,
    authorized_case_id: str,
) -> tuple[BoundQuestion, ...]:
    """Validate a complete owner-projected question list against source versions.

    Input must come from the existing source-owner transaction and its question
    projection, with current grants checked by the owner. This adapter neither
    queries the database nor creates a new read/authorization path. Historical
    superseded versions are retained for stale-question review.
    """
    if not isinstance(question_list, dict) or not isinstance(source_index, dict):
        raise SemanticContractError("invalid_owner_projection")
    if any(
        projection.get("patient_id") != authorized_patient_id
        or projection.get("case_id") != authorized_case_id
        for projection in (question_list, source_index)
    ):
        raise SemanticContractError("scope_mismatch")
    if question_list.get("contract") != "oi.synthetic-source-questions/2":
        raise SemanticContractError("unknown_question_contract")
    if source_index.get("contract") != "oi.synthetic-original-sources/1":
        raise SemanticContractError("unknown_source_contract")
    # Both projections must originate from the same canonical source-owner
    # preparation/receipt, not from two separately fetched snapshots.
    receipt = question_list.get("access_receipt_id")
    if (type(receipt) is not str or re.fullmatch(r"ACCESS-[0-9A-F]{32}", receipt) is None
            or source_index.get("access_receipt_id") != receipt):
        raise SemanticContractError("snapshot_receipt_mismatch")
    if (question_list.get("synthetic") is not True
            or source_index.get("synthetic") is not True
            or question_list.get("clinical_approval") is not False
            or question_list.get("clinical_review_connected") is not False
            or source_index.get("clinical_interpretation") is not False):
        raise SemanticContractError("unsupported_owner_claim")
    questions = question_list.get("questions")
    sources = source_index.get("sources")
    if not isinstance(questions, list) or not isinstance(sources, list):
        raise SemanticContractError("invalid_owner_projection")
    if len(questions) > 250:
        raise SemanticContractError("question_limit_exceeded")
    if not all(isinstance(source, dict) for source in sources):
        raise SemanticContractError("invalid_owner_projection")
    by_id: dict[str, dict] = {}
    for source in sources:
        sid = source.get("source_id")
        if type(sid) is not str or SOURCE_ID.fullmatch(sid) is None or sid in by_id:
            raise SemanticContractError("duplicate_or_invalid_source")
        by_id[sid] = source
    bound = []
    seen: set[str] = set()
    for question in questions:
        if not isinstance(question, dict):
            raise SemanticContractError("invalid_owner_projection")
        qid = question.get("question_id")
        if type(qid) is not str or qid in seen:
            raise SemanticContractError("duplicate_question")
        seen.add(qid)
        source = by_id.get(question.get("source_id"))
        if source is None:
            raise SemanticContractError("unknown_question_source")
        bound.append(bind_authorized_h1_question(
            registry=registry, question=question, source=source,
            authorized_patient_id=authorized_patient_id,
            authorized_case_id=authorized_case_id,
        ))
    return tuple(bound)
