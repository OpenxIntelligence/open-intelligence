"""Authorized read-only review for original synthetic Composer calculation receipts.

No second patient, evidence, model or job ledger. No clinical authorization.
"""
from __future__ import annotations

import hmac
import json

from .clinical_knowledge_context import AuthorizedClinicalKnowledge
from .clinical_continuity import ClinicalContinuityError
from .durable_runs import DurableComposerRuns
from .store import InvalidInput


def same(left: dict, right: dict) -> bool:
    encode = lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False,
                                  allow_nan=False).encode("utf-8")
    return hmac.compare_digest(encode(left), encode(right))


class PatientResearchReview:
    """Patient-scoped source-linked derived view of an existing run journal."""

    def __init__(self, knowledge: AuthorizedClinicalKnowledge,
                 runs: DurableComposerRuns):
        if not isinstance(knowledge, AuthorizedClinicalKnowledge):
            raise TypeError("expected authorized clinical knowledge")
        if not isinstance(runs, DurableComposerRuns) or runs.store is not knowledge.store:
            raise TypeError("durable run must share original source owner")
        self.knowledge = knowledge
        self.runs = runs

    def _check_sources(self, case_id: str, run: dict) -> list[dict]:
        payload = run["result"]
        if payload is None:
            return []
        if payload.get("task_kind") != "deterministic_synthetic_numeric_comparison":
            raise ClinicalContinuityError("unexpected computation kind")
        result = payload.get("result")
        if not isinstance(result, dict) or result.get("case_id") != case_id:
            raise ClinicalContinuityError("computation result has wrong subject")
        if not isinstance(result.get("points"), list):
            raise ClinicalContinuityError("computation lacks source points")
        verified = []
        for point in result["points"]:
            ref = point.get("source") if isinstance(point, dict) else None
            if not isinstance(ref, dict):
                raise ClinicalContinuityError("missing source reference")
            records = self.runs.db.execute(
                """SELECT s.*,a.source_line,a.finding_key,a.certainty,a.quote
                   FROM source_versions s JOIN assertions a
                     ON a.source_version_id=s.id AND a.case_id=s.case_id
                   WHERE s.case_id=? AND s.id=? AND a.source_line=?
                     AND a.finding_key=?""",
                (case_id,ref.get("source_version_id"),ref.get("source_line"),
                 ref.get("finding_key"))).fetchall()
            if len(records) != 1:
                raise ClinicalContinuityError("ambiguous or missing source assertion")
            r = records[0]
            expected = {
                "source_version_id":r["id"],"document_id":r["document_id"],
                "source_version":r["version"],"source_sha256":r["sha256"],
                "source_line":r["source_line"],"finding_key":r["finding_key"],
                "reported_state":r["certainty"],"event_date":r["event_date"],
                "issued_at":r["issued_at"],"received_at":r["received_at"],
                "specimen_id":r["specimen_id"],
            }
            if ref != expected:
                raise ClinicalContinuityError("source provenance mismatch")
            if r["quote"] != (
                f"OI-LAB-VALUE/1;value={point.get('value')};"
                f"unit={point.get('unit')};qc=passed"
            ):
                raise ClinicalContinuityError("result value differs from original source")
            verified.append({"source_version_id":r["id"],
                             "source_hash":r["sha256"],
                             "source_state":r["state"]})
        return verified

    def snapshot(self, patient_id: str, case_id: str, question_id: int,
                 run_id: int, *, actor: str, purpose: str) -> dict:
        before = self.knowledge.snapshot(
            patient_id,case_id,question_id,actor=actor,purpose=purpose)
        run = self.runs.get(case_id,run_id)
        if run["case_id"] != case_id or run["question_id"] != question_id:
            raise InvalidInput("run belongs to another subject or question")
        sources = self._check_sources(case_id,run)
        after = self.knowledge.snapshot(
            patient_id,case_id,question_id,actor=actor,purpose=purpose)
        if not same(before,after):
            raise ClinicalContinuityError("patient or evidence changed during review")
        again = self.runs.get(case_id,run_id)
        if not same(run,again):
            raise ClinicalContinuityError("durable run changed during review")
        self.knowledge.composer.clinical._authorize(patient_id,case_id,actor,purpose)
        self.knowledge.composer.clinical.provenance._allow(
            patient_id,case_id,actor=actor,purpose=purpose,
            action="patient_context.read")
        current = hmac.compare_digest(
            run["context_fingerprint"],
            after["clinical_composer"]["composer"]["fingerprint"])
        status = ("current_numeric_receipt_pending_human_review"
                  if run["state"]=="completed" and current else
                  "historical_numeric_receipt_reassessment_required"
                  if run["state"]=="stale" or not current else
                  "no_current_numeric_result_for_review")
        return {
            "contract":"oi.synthetic-patient-durable-research-review/1",
            "patient_id":patient_id,"case_id":case_id,"question_id":question_id,
            "patient_evidence":after,"durable_run":again,
            "original_source_provenance":sources,"review_status":status,
            "clinical_approval":"not_performed",
            "model_execution_authorized":False,
            "clinical_interpretation":"not_performed",
            "report_kind":"synthetic_numeric_methods_receipt_not_clinical_report",
            "disclaimer":(
                "Independently authored fictional measurements only. Numerical "
                "differences are not diagnosis, treatment guidance, validated "
                "laboratory results, verified content rights or clinician approval."
            ),
        }

    def export_markdown(self, patient_id: str, case_id: str, question_id: int,
                        run_id: int, *, actor: str, purpose: str) -> str:
        """Generate a source-cited research handoff without external content export.

        The knowledge preflight allows certain content to be *displayed* but
        does not establish rights to redistribute it. Therefore this export
        deliberately includes NO third-party article text, titles, summaries,
        clinical note narrative or unreviewed biomedical comparisons.
        """
        reviewed = self.snapshot(
            patient_id,case_id,question_id,run_id,actor=actor,purpose=purpose)
        run = reviewed["durable_run"]
        points = (run["result"] or {}).get("result",{}).get("points",[])
        lines = [
            "# Open Intelligence — fictional numeric research handoff",
            "",
            "**Not a clinical report, medical recommendation or clinician approval.**",
            "",
            f"Patient reference: `{patient_id}`",
            f"Fictional case: `{case_id}`",
            f"Question reference: `{question_id}`",
            f"Original durable run: `{run_id}`",
            f"Run status: `{run['state']}`",
            f"Review state: `{reviewed['review_status']}`",
            f"Source-context fingerprint: `{run['context_fingerprint']}`",
            "",
            "## Original fictional measurement sources",
            "",
        ]
        if not points:
            lines.append("No eligible numeric result; the original receipt remains inspectable.")
        for point in points:
            ref = point["source"]
            lines.append(
                f"- `{point['value']} {point['unit']}` from fictional "
                f"source `{ref['document_id']}@{ref['source_version']}`, "
                f"version ID `{ref['source_version_id']}`, "
                f"line `{ref['source_line']}`, "
                f"SHA-256 `{ref['source_sha256']}`"
            )
        lines.extend([
            "",
            "## Computation and evidence limitations",
            "",
            "Values were independently authored fictional source assertions. "
            "The existing deterministic tool performs arithmetic only.",
            "Published biomedical evidence and clinician conclusions were "
            "not independently reviewed or authorized for redistribution.",
            "A stale computation remains historical and must not be presented "
            "as current. Re-run and independent human review are required.",
        ])
        return "\n".join(lines)+"\n"
