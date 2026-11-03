"""Review handoff to the *existing* CaseStore review-queue owner (PR #82).

Only independently authored synthetic evidence can be matched to the existing
synthetic evidence ledger. External licensed publications are NOT imported or
considered legally cleared by this adapter. This is a bounded, read-only
inspection and a 'returned for verification' receipt, NOT a clinician signoff.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable

from .evidence_review_packet import EvidenceReviewPacket
from .knowledge_context import KnowledgeContextError
from .clinical_continuity import ClinicalContinuityError
from .store import InvalidInput
from .source_provenance import PROVENANCE_FIELDS

def _digest(payload: dict) -> str:
    try:
        return json.dumps(payload, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise KnowledgeContextError("unserializable evidence review context") from exc


class AuthorizedEvidenceReviewHandoff:
    """Build a bounded review queue item; never create competing durable truth."""

    def __init__(self, packet: EvidenceReviewPacket,
                 return_authorizer: Callable[[str, str, str, str], bool] | None = None):
        if not isinstance(packet, EvidenceReviewPacket):
            raise TypeError("Use the existing source-quoted evidence packet owner")
        self.packet = packet
        self.store = packet.bridge.store
        self.return_authorizer = return_authorizer
        if not hasattr(self.store, "review_queue") or not hasattr(self.store, "add_review_receipt"):
            raise RuntimeError("Require the existing append-only review queue contract")

    def _authorize_return(self, patient_id: str, actor: str, purpose: str) -> None:
        """Reading evidence NEVER implies permission to change review state."""
        # Require an actual Boolean True from the trusted policy boundary.
        # Truthy strings, numbers, dicts or custom objects are not authority.
        try:
            decision = (self.return_authorizer(
                actor, patient_id, "evidence.review_return", purpose)
                if self.return_authorizer is not None else None)
        except Exception:
            decision = None
        if decision is not True:
            raise PermissionError("returning evidence for review requires a separate trusted grant")

    def preview(self, patient_id: str, case_id: str, question_id: int,
                assessment_id: int, *, actor: str, purpose: str,
                selected_quotes: list[dict]) -> dict:
        """Match only to an existing *fictional*, versioned evidence assessment.

        External publisher articles are intentionally ineligible for this
        local synthetic-only mapping. They need a separately qualified rights
        and review-owner integration, not a forged synthetic evidence import.
        """
        if type(assessment_id) is not int or assessment_id <= 0:
            raise KnowledgeContextError("existing assessment id must be positive")
        packet = self.packet.preview(
            patient_id, case_id, question_id, actor=actor, purpose=purpose,
            selected_quotes=selected_quotes)
        if len(packet["quoted_comparisons"]) != 1:
            raise KnowledgeContextError("exactly one source-quoted comparison per handoff")
        item = packet["quoted_comparisons"][0]
        state = self.store.state(case_id)
        assessment = next((a for a in state["evidence_assessments"]
                           if a["id"] == assessment_id and
                           a["question_id"] == question_id), None)
        if assessment is None:
            raise KnowledgeContextError("no existing case- and question-scoped evidence assessment")
        source = next((s for s in state["evidence"]
                       if s["id"] == assessment["evidence_version_id"]), None)
        if source is None or source["state"] != "current" or source["rights"] != "original-synthetic":
            raise KnowledgeContextError("review assessment source is unavailable or not current")
        quoted = item["external_reference"]
        if not (quoted["family"] == "other"
                and quoted["knowledge_id"] == source["evidence_key"]
                and quoted["version"] == "v" + str(source["version"])
                and quoted["source_date"] == source["issued_at"]
                and quoted["rights_status"] == "approved"):
            raise KnowledgeContextError("external evidence is not the exact stored fictional source version")
        if (assessment["relation"] != item["candidate_relation"]
                or assessment["applicability"] != item["candidate_applicability"]):
            raise KnowledgeContextError("reviewed comparison differs from stored assessment")
        if item["patient_reference"]["assertion_id"] not in {
            a["id"] for a in state["assertions"]
        }:
            raise KnowledgeContextError("cited patient assertion no longer current")
        # For this synthetic-only bridge, ensure the rights-qualified provider
        # text equals the already stored authored original. Never mirror real
        # publications into the synthetic evidence ledger.
        provider = self.packet.bridge.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose)
        sources = [s for s in provider["knowledge"]["knowledge_sources"]
                   if s["id"] == source["evidence_key"]]
        if len(sources) != 1 or sources[0]["evidence_text"] != source["statement"]:
            raise KnowledgeContextError("provider text differs from original fictional evidence ledger")
        if quoted["exact_quote"] not in source["statement"]:
            raise KnowledgeContextError("quotation not present in stored source")
        queue = self.store.review_queue(case_id)
        key = f"evidence-assessment:{assessment_id}"
        matching = [x for x in queue["awaiting"] + queue["resolved"]
                    if x["queue_key"] == key]
        if len(matching) != 1:
            raise KnowledgeContextError("review queue target is missing or ambiguous")
        if matching[0]["status"] == "resolved":
            raise KnowledgeContextError("existing review item already resolved")
        # Late approval, right or source changes must invalidate the preview.
        second = self.packet.preview(
            patient_id, case_id, question_id, actor=actor, purpose=purpose,
            selected_quotes=selected_quotes)
        if not hmac.compare_digest(_digest(packet), _digest(second)):
            raise ClinicalContinuityError("review packet changed; refresh before handoff")
        return {
            "contract": "oi.synthetic-authorized-evidence-review-queue/1",
            "patient_id": patient_id,
            "case_id": case_id,
            "question_id": question_id,
            "queue_key": key,
            "queue_fingerprint": matching[0]["fingerprint"],
            "queue_status": matching[0]["status"],
            "assessment_id": assessment_id,
            "original_evidence_version_id": source["id"],
            "source_quote_packet": second,
            "review_action_allowed": "returned_only",
            "clinician_signoff_authorized": False,
            "publisher_rights_independently_verified": False,
            "distributed_snapshot_atomic": False,
            "disclaimer": (
                "Fictional assessment and test-only actor permission. This is "
                "not clinical review, medical evidence applicability, a "
                "licensed content integration, or an authorized action."
            ),
        }

    def return_for_review(self, patient_id: str, case_id: str, question_id: int,
                          assessment_id: int, *, actor: str, purpose: str,
                          selected_quotes: list[dict], reason: str,
                          report_reference: dict | None = None) -> dict:
        """Append ONLY a returned receipt; never grant completion or signoff.

        The original review queue owns all durable receipts. Cross-provider
        authorization is *not* a distributed transaction; the nonterminal
        returned decision cannot approve a clinical item, even on a race.
        """
        self._authorize_return(patient_id, actor, purpose)
        first = self.preview(patient_id, case_id, question_id, assessment_id,
                             actor=actor, purpose=purpose, selected_quotes=selected_quotes)
        second = self.preview(patient_id, case_id, question_id, assessment_id,
                              actor=actor, purpose=purpose, selected_quotes=selected_quotes)
        if not hmac.compare_digest(_digest(first), _digest(second)):
            raise ClinicalContinuityError("review changed before return receipt")
        prepared = None
        if report_reference is not None:
            if (not isinstance(report_reference, dict) or
                    set(report_reference) != {"body_sha256", "packet_sha256"}):
                raise KnowledgeContextError("report reference requires exact digest fields")
            expected = hashlib.sha256(
                _digest(second["source_quote_packet"]).encode("utf-8")).hexdigest()
            if report_reference["packet_sha256"] != expected:
                raise ClinicalContinuityError("report packet changed before review handoff")
            cited = second["source_quote_packet"]["quoted_comparisons"][0]["patient_reference"]
            prepared = {
                "contract": "oi.synthetic-prepared-report-reference/1",
                "semantics": "prepared_not_delivery_or_approval",
                "body_sha256": report_reference["body_sha256"],
                "packet_sha256": expected,
                "question_id": question_id,
                "patient_source": {
                    **{key: cited[key] for key in
                       ("assertion_id", "source_version_id", "sha256", "source_line")},
                    **{key: cited[key] for key in PROVENANCE_FIELDS if key in cited},
                },
            }
        # Distinct write-action authorization, rechecked at the effect boundary.
        self._authorize_return(patient_id, actor, purpose)
        kwargs = {} if prepared is None else {"prepared_report": prepared}
        receipt = self.store.add_review_receipt(
            case_id, first["queue_key"], "returned", reviewer_label=actor,
            reason=reason, expected_fingerprint=first["queue_fingerprint"], **kwargs)
        # Returning an item remains unresolved. Do not call an acknowledgment
        # review a clinical signoff, even if a later preflight is interrupted.
        return {
            "result": "returned_for_independent_review",
            "queue_key": first["queue_key"],
            "receipt_id": receipt["receipt_id"],
            "queue_fingerprint": receipt["fingerprint"],
            "clinical_signoff": False,
            "reviewer_authority": "synthetic_policy_only",
        }
