"""Strict, pure H1 evidence provenance bridge. No clinical inference or persistence.

This adapter is intentionally read-only and synthetic-only. It binds a proposed
evidence excerpt to an existing canonical question/source anchor; a later
transactional owner must independently authorize and persist the result.
"""
from dataclasses import dataclass
import hashlib
import re

_HEX = re.compile(r"^[0-9a-f]{64}$")
_RELATIONS = frozenset({"supports", "contradicts", "context", "unknown"})
_RIGHTS = frozenset({"metadata", "abstract", "full_text"})


class EvidenceBridgeError(ValueError):
    """Reject an ungrounded, stale or rights-incompatible evidence projection."""


@dataclass(frozen=True, slots=True)
class CanonicalQuestionAnchor:
    patient_id: str
    case_id: str
    question_id: str
    source_id: str
    source_version_id: str
    source_sha256: str
    source_line: int


@dataclass(frozen=True, slots=True)
class ProposedEvidence:
    question_id: str
    patient_id: str
    case_id: str
    source_version_id: str
    evidence_id: str
    evidence_version: str
    relation: str
    quotation: str
    quotation_sha256: str
    rights: frozenset[str]
    review_state: str = "pending"


@dataclass(frozen=True, slots=True)
class EvidenceProjection:
    anchor: CanonicalQuestionAnchor
    evidence_id: str
    evidence_version: str
    relation: str
    quotation: str | None
    quotation_sha256: str
    review_state: str


def bind_evidence(
    anchor: CanonicalQuestionAnchor,
    proposal: ProposedEvidence,
    *,
    requested_content: str,
    current_source_sha256: str,
) -> EvidenceProjection:
    """Validate exact identity and content rights; never grant authority.

    Caller must first authenticate the principal and obtain current per-action
    grants, then recheck authority under its disclosure transaction. The rights
    set here is supplied by an independently verified rights owner, not a user.
    """
    for field in ("patient_id", "case_id", "question_id", "source_version_id"):
        left, right = getattr(anchor, field), getattr(proposal, field)
        if not isinstance(left, str) or not left or left != right:
            raise EvidenceBridgeError("evidence is not bound to the canonical question")
    if not anchor.source_id or not isinstance(anchor.source_line, int) or isinstance(anchor.source_line, bool) or anchor.source_line < 1:
        raise EvidenceBridgeError("invalid source anchor")
    if not isinstance(anchor.source_sha256, str) or not _HEX.fullmatch(anchor.source_sha256):
        raise EvidenceBridgeError("invalid source digest")
    if current_source_sha256 != anchor.source_sha256:
        raise EvidenceBridgeError("source changed; reassessment required")
    if not proposal.evidence_id or not proposal.evidence_version:
        raise EvidenceBridgeError("evidence identity and version required")
    if proposal.relation not in _RELATIONS or proposal.review_state != "pending":
        raise EvidenceBridgeError("unsupported relation or review state")
    if not isinstance(proposal.quotation, str) or not proposal.quotation:
        raise EvidenceBridgeError("empty quotation")
    if hashlib.sha256(proposal.quotation.encode("utf-8")).hexdigest() != proposal.quotation_sha256:
        raise EvidenceBridgeError("evidence quotation digest mismatch")
    if not isinstance(proposal.rights, frozenset) or not proposal.rights <= _RIGHTS:
        raise EvidenceBridgeError("unverified content-rights contract")
    if requested_content not in _RIGHTS:
        raise EvidenceBridgeError("unsupported disclosure scope")
    if requested_content not in proposal.rights:
        raise EvidenceBridgeError("content redistribution not permitted")
    # Metadata scope never includes the quotation, even if it was provided.
    return EvidenceProjection(
        anchor=anchor,
        evidence_id=proposal.evidence_id,
        evidence_version=proposal.evidence_version,
        relation=proposal.relation,
        quotation=proposal.quotation if requested_content != "metadata" else None,
        quotation_sha256=proposal.quotation_sha256,
        review_state="pending",
    )
