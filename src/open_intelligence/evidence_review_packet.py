"""Inspectably quoted, rights-gated synthetic evidence review packet.

Extends the existing AuthorizedClinicalKnowledge preflight without a new
patient store, knowledge source, clinical assertion, investigation ledger,
model call, clinician approval, or network integration. All selected
quotations must match exact rights-permitted fictional source text.
A literal quote does NOT establish scientific entailment or clinical validity.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from .clinical_continuity import ClinicalContinuityError
from .clinical_knowledge_context import AuthorizedClinicalKnowledge
from .knowledge_context import KnowledgeContextError
from .source_provenance import PROVENANCE_FIELDS, REVISION_FIELDS, _positive
from .store import InvalidInput

MAX_QUOTE = 400


def _snapshot_bytes(value: dict) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise KnowledgeContextError("unsupported non-reproducible review context") from exc


class EvidenceReviewPacket:
    """Create a read-only evidence handoff with *exact* quoted source anchors.

    Rechecks the original patient/rights-authorized bridge after constructing
    the packet, refusing a stale review preview. Two reads are not an atomic
    snapshot across an independent source rights provider or review receiver.
    """

    def __init__(self, bridge: AuthorizedClinicalKnowledge):
        if not isinstance(bridge, AuthorizedClinicalKnowledge):
            raise TypeError("Use existing authorized clinical knowledge owner")
        self.bridge = bridge

    def preview(self, patient_id: str, case_id: str, question_id: int,
                *, actor: str, purpose: str, selected_quotes: list[dict]) -> dict:
        if not isinstance(selected_quotes, list) or len(selected_quotes) > 100:
            raise KnowledgeContextError("selected evidence quotations must be a bounded list")
        before = self.bridge.snapshot(patient_id, case_id, question_id,
                                      actor=actor, purpose=purpose)
        patient = {r["id"]: r for r in before["knowledge"]["patient_assertions"]}
        evidence = {r["id"]: r for r in before["knowledge"]["knowledge_sources"]}
        proposals = {
            (r["assertion_id"], r["knowledge_id"]): r
            for r in before["knowledge"]["comparison_proposals"]
        }
        if len(proposals) != len(before["knowledge"]["comparison_proposals"]):
            raise KnowledgeContextError("ambiguous repeated evidence comparison")
        seen = set()
        rows = []
        for selected in selected_quotes:
            required = {
                "assertion_id", "knowledge_id", "quote",
            }
            if not isinstance(selected, dict) or not required <= selected.keys():
                raise KnowledgeContextError("selected quote requires exact identifiers and text")
            aid, kid, quote = (selected["assertion_id"],
                               selected["knowledge_id"], selected["quote"])
            if type(aid) is not int or not isinstance(kid, str):
                raise KnowledgeContextError("source anchor identifiers have wrong type")
            key = (aid, kid)
            if key in seen or key not in proposals or aid not in patient or kid not in evidence:
                raise KnowledgeContextError("unknown or duplicated source/evidence comparison")
            observation = patient[aid]
            manual = observation.get("classification_origin") == "user_selected"
            if set(selected) != required | (set(REVISION_FIELDS) if manual else set()):
                raise KnowledgeContextError("selected quote requires its captured annotation revision")
            if manual:
                # A freshly loaded proposal cannot authorize an old browser
                # selection against a different revision of the same passage.
                for field in REVISION_FIELDS:
                    try:
                        captured = _positive(selected[field], field)
                    except InvalidInput as exc:
                        raise KnowledgeContextError(str(exc)) from exc
                    if captured != observation[field]:
                        raise KnowledgeContextError("selected quote cites a stale annotation revision; reselect")
            seen.add(key)
            source = evidence[kid]
            if not source["model_text_available"] or not isinstance(source["evidence_text"], str):
                raise KnowledgeContextError("quoted evidence lacks current explicit AI-use rights")
            if not isinstance(quote, str) or not quote.strip() or len(quote) > MAX_QUOTE:
                raise KnowledgeContextError("quote must be nonempty and bounded")
            if quote not in source["evidence_text"]:
                raise KnowledgeContextError("quoted passage is absent from permitted original text")
            proposal = proposals[key]
            rows.append({
                "candidate_relation": proposal["relation"],
                "candidate_applicability": proposal["applicability"],
                "clinical_review_state": "not_performed",
                "evidence_review_state": "unreviewed_proposal",
                "patient_reference": {
                    "assertion_id": aid,
                    "source_version_id": observation["source_version_id"],
                    "document_id": observation["source_document"],
                    "version": observation["version"],
                    "sha256": observation["source_hash"],
                    "source_line": observation["source_line"],
                    "event_date": observation["source_date"],
                    "issued_at": observation["issued_at"],
                    "received_at": observation["received_at"],
                    "reported_state": observation["reported_state"],
                    "original_statement": observation["source_statement"],
                    **{key: observation[key] for key in PROVENANCE_FIELDS
                       if key in observation},
                },
                "external_reference": {
                    "knowledge_id": kid,
                    "family": source["family"],
                    "content_item": source["content_item"],
                    "content_item_basis": source["content_item_basis"],
                    "public_identifier": source["public_identifier"],
                    "version": source["version"],
                    "source_date": source["source_date"],
                    "exact_quote": quote,
                    "evidence_text_sha256": source["evidence_text_sha256"],
                    "report_export_allowed": source["report_export_allowed"],
                    "rights_status": source["rights_status"],
                    "permission_receipt": source["approval_receipt"],
                    "publisher_rights_independently_verified": False,
                },
                "reviewer_note": proposal["reviewer_note"],
                "proposed_by": proposal["proposed_by"],
            })

        # Refetch through the owner to detect stale patient/source/permission
        # context while this read-only review handoff was assembled.
        after = self.bridge.snapshot(patient_id, case_id, question_id,
                                     actor=actor, purpose=purpose)
        if not hmac.compare_digest(_snapshot_bytes(before), _snapshot_bytes(after)):
            raise ClinicalContinuityError(
                "clinical or evidence context changed before review preview; refresh")
        return {
            "contract": "oi.synthetic-source-quote-review/1",
            "patient_id": patient_id,
            "case_id": case_id,
            "question_id": question_id,
            "question": after["clinical_composer"]["composer"]["question"],
            "available_comparison_count": len(proposals),
            "review_context_sha256": hashlib.sha256(_snapshot_bytes(after)).hexdigest(),
            "composer_context_fingerprint": after["clinical_composer"]["composer"]["fingerprint"],
            "quoted_comparisons": rows,
            "missing_or_withheld_evidence": after["knowledge"]["missing_evidence"],
            "human_review_state": "pending",
            "model_executed": False,
            "clinical_conclusion_established": False,
            "action_authorized": False,
            "rights_proof": "fixture_declarations_only_not_publisher_authorization",
            "snapshot_consistency": "sequential_preflight_not_cross_system_atomic",
            "limitations": (
                "Literal passage match validates quotation, not medical relevance "
                "or entailment. Proposed support/contradiction is not a clinical "
                "fact, approved guideline, permission to feed text to an actual "
                "model, clinical decision, order or authorization."
            ),
        }
