"""Tie an exported synthetic report to the existing nonterminal review receipt.

This is a library boundary, not an HTTP route or verified clinical identity.
Only report hashes and source references enter the existing receipt event.
No report body is stored and no completed review/delivery is claimed.
"""
from __future__ import annotations

import copy
import hashlib

from .authorized_evidence_review import AuthorizedEvidenceReviewHandoff
from .clinical_continuity import ClinicalContinuityError
from .evidence_review_report import EvidenceReviewReport


class ReportReviewHandoff:
    """Compose the original report and review owners without duplicating state.

    Current external rights and authority remain sequential checks. A refusal
    after a committed nonterminal preparation leaves that receipt intact but
    returns no body. That receipt is not evidence of delivery or clinical review.
    """

    def __init__(self, report: EvidenceReviewReport,
                 review: AuthorizedEvidenceReviewHandoff):
        if (not isinstance(report, EvidenceReviewReport) or
                not isinstance(review, AuthorizedEvidenceReviewHandoff)):
            raise TypeError("Use the original report and evidence review owners")
        if report.packets is not review.packet:
            raise ValueError("Report and review must share the same source packet owner")
        self.report = report
        self.review = review

    def return_for_review(self, patient_id: str, case_id: str, question_id: int,
                          assessment_id: int, *, actor: str, purpose: str,
                          selected_quotes: list[dict], reason: str) -> dict:
        # A readable/exportable report is not permission to change the queue.
        self.review._authorize_return(patient_id, actor, purpose)
        selected = copy.deepcopy(selected_quotes)
        inputs = dict(patient_id=patient_id, case_id=case_id, question_id=question_id,
                      actor=actor, purpose=purpose, selected_quotes=selected)
        report = self.report.render(**inputs)
        if report["body_sha256"] != hashlib.sha256(report["body"].encode("utf-8")).hexdigest():
            raise ClinicalContinuityError("Rendered report digest does not match its body")
        reference = {key: report[key] for key in ("body_sha256", "packet_sha256")}
        receipt = self.review.return_for_review(
            **inputs, assessment_id=assessment_id, reason=reason,
            report_reference=reference)
        # Recheck export permissions, patient context and exact bytes after
        # the effect. A denial leaves a preparation record, not a delivery.
        latest = self.report.render(**inputs)
        if (latest["body_sha256"] != reference["body_sha256"] or
                latest["packet_sha256"] != reference["packet_sha256"]):
            raise ClinicalContinuityError("Report changed after preparation; body withheld")
        return {
            "contract": "oi.synthetic-report-review-handoff/1",
            "report": latest,
            "receipt": receipt,
            "receipt_semantics": "prepared_report_reference_not_delivery_or_approval",
            "clinical_signoff": False,
            "human_review_state": "pending",
            "distributed_snapshot_atomic": False,
        }
