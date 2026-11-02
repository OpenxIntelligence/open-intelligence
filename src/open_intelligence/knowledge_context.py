"""Patient-anchored, rights-aware biomedical investigation context.

This module extends the existing CaseStore.state() and rights.py contracts.
It does not create another patient/evidence ledger, fetch publications, or
call an AI model. Source text only reaches model context when independently
recorded use-specific rights attestations permit it.

Patient assertions are limited to independently authored fictional records.
Never pass real patient data to an unqualified model/service through this API.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Mapping

from .rights import RightsError, normalize_permissions, permitted

SOURCE_FAMILIES = frozenset({
    "nccn", "asco", "esmo", "nci_pdq", "pubmed", "pmc", "civic",
    "clinicaltrials", "fda_label", "other",
})
RELATIONS = frozenset({"supports", "contradicts", "context", "unknown"})
APPLICABILITY = frozenset({"applicable", "limited", "not_applicable", "unknown"})
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/@+-]{1,199}\Z")


class KnowledgeContextError(ValueError):
    """Unsafe or unqualified external knowledge comparison input."""


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise KnowledgeContextError(f"{field} must be an opaque identifier")
    return value


def _date(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise KnowledgeContextError(f"{field} must be YYYY-MM-DD")
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError:
        raise KnowledgeContextError(f"{field} must be YYYY-MM-DD") from None
    return value


def _source(item: Mapping[str, Any]) -> dict:
    """Return a safe source capability and allowed context. No network I/O.

    An asserted receipt is *not* legal proof: this API is a preflight for
    separately reviewed rights records, and must be called only behind a
    trusted source-rights service in any deployed system.
    """
    if not isinstance(item, dict):
        raise KnowledgeContextError("knowledge source must be an object")
    required = {
        "id", "family", "public_identifier", "version", "source_date",
        "rights_state", "permission_receipt", "permissions", "content_state",
    }
    if not required <= set(item):
        raise KnowledgeContextError("knowledge source missing required rights/provenance fields")
    identifier = _identifier(item["id"], "source id")
    public_id = _identifier(item["public_identifier"], "public identifier")
    version = _identifier(item["version"], "source version")
    source_date = _date(item["source_date"], "source date")
    family = item["family"]
    if family not in SOURCE_FAMILIES:
        raise KnowledgeContextError("unrecognized source family")
    state = item["rights_state"]
    content_state = item["content_state"]
    if state not in {"approved", "hold", "revoked"} or content_state not in {"current", "superseded", "withdrawn"}:
        raise KnowledgeContextError("invalid rights/content status")
    receipt = item["permission_receipt"]
    approved = state == "approved" and content_state == "current" and (
        isinstance(receipt, str) and bool(receipt.strip())
    )
    try:
        permissions = normalize_permissions(item["permissions"])
    except RightsError as exc:
        raise KnowledgeContextError(str(exc)) from exc
    metadata = item.get("title")
    excerpt = item.get("evidence_text")
    if metadata is not None and (not isinstance(metadata, str) or not metadata.strip()):
        raise KnowledgeContextError("title must be nonempty text if supplied")
    if excerpt is not None and (not isinstance(excerpt, str) or not excerpt.strip()):
        raise KnowledgeContextError("evidence_text must be nonempty if supplied")
    if excerpt is not None and len(excerpt) > 10000:
        raise KnowledgeContextError("excessive external evidence text")
    metadata_allowed = bool(
        approved and permitted(permissions, "metadata", "store")
        and permitted(permissions, "metadata", "display")
    )
    # Rights to download and *read* a PDF are not rights to feed it to an LLM.
    model_text_allowed = bool(
        approved and permitted(permissions, "full_text", "store")
        and permitted(permissions, "full_text", "display")
        and permitted(permissions, "full_text", "ml_use")
    )
    if metadata is not None and not metadata_allowed:
        raise KnowledgeContextError("cannot ingest source title without metadata rights")
    if excerpt is not None and not model_text_allowed:
        raise KnowledgeContextError("cannot ingest source text without explicit AI rights")
    return {
        "id": identifier,
        "family": family,
        "public_identifier": public_id,
        "version": version,
        "source_date": source_date,
        "rights_status": state,
        "content_status": content_state,
        "approval_receipt": receipt if approved else None,
        "title": metadata if metadata_allowed else None,
        "evidence_text": excerpt if model_text_allowed else None,
        "model_text_available": bool(model_text_allowed and excerpt),
        "content_withheld": not bool(model_text_allowed and excerpt),
    }


def compile_context(case_id: str, case_state: Mapping[str, Any],
                    knowledge_sources: list[dict],
                    comparison_proposals: list[dict] | None = None) -> dict:
    """Create a source-cited, *non-diagnostic* patient/evidence context packet.

    The resulting data can be inspected in an authorized application. The
    contained patient assertions are NEVER independently approved for remote
    model transmission by this function. The caller must separately enforce
    trusted actor/purpose, PHI controls, model/data-use rights and clinical
    authority. No clinical relevance or literature support is inferred.
    """
    _identifier(case_id, "case id")
    if not isinstance(case_state, dict) or not isinstance(case_state.get("case"), dict):
        raise KnowledgeContextError("CaseStore.state snapshot required")
    if case_state["case"].get("case_id") != case_id:
        raise KnowledgeContextError("cross-patient case snapshot")
    versions = {}
    for item in case_state.get("sources", []):
        sid = item.get("id")
        if type(sid) is not int or sid <= 0 or sid in versions:
            raise KnowledgeContextError("ambiguous source version identifier")
        versions[sid] = item
    observed = []
    current_ids = set()
    for item in case_state.get("assertions", []):
        sid = item.get("source_version_id")
        parent = versions.get(sid)
        if parent is None or parent.get("state") != "current":
            raise KnowledgeContextError("assertion depends on non-current or missing original source")
        if type(item.get("id")) is not int or type(item.get("source_line")) is not int:
            raise KnowledgeContextError("source assertion needs stable ID and line")
        if item["id"] in current_ids:
            raise KnowledgeContextError("duplicated assertion")
        current_ids.add(item["id"])
        observed.append({
            "id": item["id"],
            "finding_key": item["finding_key"],
            "reported_state": item["certainty"],
            "source_version_id": sid,
            "source_document": parent["document_id"],
            "version": parent["version"],
            "source_hash": parent["sha256"],
            "source_line": item["source_line"],
            "source_date": parent["event_date"],
            "issued_at": parent["issued_at"],
            "source_statement": item["quote"],
            "epistemic_kind": "reported_observation",
        })
    if not isinstance(knowledge_sources, list) or not isinstance(comparison_proposals or [], list):
        raise KnowledgeContextError("knowledge sources and links must be lists")
    checked = [_source(src) for src in knowledge_sources]
    if len({item["id"] for item in checked}) != len(checked):
        raise KnowledgeContextError("duplicated knowledge source")
    knowledge_map = {item["id"]: item for item in checked}
    proposed_links = []
    for link in comparison_proposals or []:
        if not isinstance(link, dict) or set(link) != {
            "assertion_id", "knowledge_id", "relation", "applicability",
            "reviewer_note", "proposed_by",
        }:
            raise KnowledgeContextError("invalid comparison proposal shape")
        if type(link["assertion_id"]) is not int or link["assertion_id"] not in current_ids:
            raise KnowledgeContextError("comparison cites unknown or stale patient assertion")
        source = knowledge_map.get(link["knowledge_id"])
        if source is None or not source["model_text_available"]:
            raise KnowledgeContextError("comparison requires current rights-qualified evidence text")
        if link["relation"] not in RELATIONS or link["applicability"] not in APPLICABILITY:
            raise KnowledgeContextError("invalid relation or applicability")
        for field in ("reviewer_note", "proposed_by"):
            if not isinstance(link[field], str) or not link[field].strip():
                raise KnowledgeContextError(f"{field} is required")
        proposed_links.append({**link, "review_state": "unreviewed_proposal"})
    return {
        "case_id": case_id,
        "context_kind": "fictional_source_grounded_research_packet",
        "patient_assertions": observed,
        "knowledge_sources": checked,
        "comparison_proposals": proposed_links,
        "missing_evidence": [
            {"knowledge_id": s["id"], "reason": "unlicensed_unavailable_or_no_text"}
            for s in checked if s["content_withheld"]
        ],
        "clinical_review_state": "not_clinically_reviewed",
        "model_use_state": "not_authorized_by_this_packet",
        "limitations": (
            "No content rights inferred from a publisher URL, public PDF, "
            "metadata API, NCCN/ASCO/ESMO membership or unverified MCP server. "
            "No autonomous diagnosis, regimen selection, dosing or eligibility."
        ),
    }
