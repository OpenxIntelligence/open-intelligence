"""Read-only unified evidence quotation + numerical research review preview.

This composes existing, independently owned patient/clinical/knowledge,
source-quote, and durable-run components. It adds no second record, decision,
evidence, authorization or tool-execution store.

For independently authored fictional cases only. A sequential preflight is
NOT an atomic distributed transaction or a professional approval.
"""
from __future__ import annotations

from .clinical_continuity import ClinicalContinuityError
from .clinical_knowledge_context import AuthorizedClinicalKnowledge
from .durable_runs import DurableComposerRuns
from .evidence_review_packet import EvidenceReviewPacket
from .patient_research_review import PatientResearchReview, same


class UnifiedClinicalReview:
    """One read-only user-review preview from existing authorized owners."""

    def __init__(self, knowledge: AuthorizedClinicalKnowledge,
                 runs: DurableComposerRuns):
        self.numeric = PatientResearchReview(knowledge, runs)
        self.evidence = EvidenceReviewPacket(knowledge)
        self.knowledge = knowledge
        self.runs = runs

    def preview(self, patient_id: str, case_id: str, question_id: int,
                run_id: int, *, actor: str, purpose: str,
                selected_quotes: list[dict]) -> dict:
        # A single preflight across both read pathways detects input drift
        # between a valid evidence quotation and a durable numeric receipt.
        before = self.knowledge.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose)
        quoted = self.evidence.preview(
            patient_id, case_id, question_id, actor=actor, purpose=purpose,
            selected_quotes=selected_quotes)
        numeric = self.numeric.snapshot(
            patient_id, case_id, question_id, run_id,
            actor=actor, purpose=purpose)
        after = self.knowledge.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose)
        current_fingerprint = after["clinical_composer"]["composer"]["fingerprint"]
        if (not same(before, after) or
                not same(numeric["patient_evidence"], after) or
                quoted["composer_context_fingerprint"] != current_fingerprint):
            raise ClinicalContinuityError(
                "patient, source or knowledge changed during unified review")
        # A work receipt could change after the numerical reader returns.
        # Compare its original content before exposing even a pending packet.
        if not same(self.runs.get(case_id, run_id), numeric["durable_run"]):
            raise ClinicalContinuityError(
                "durable research receipt changed during unified review")
        # Recheck authorization after the final tool/rights read. This cannot
        # make multiple separate stores into an atomic consistent snapshot.
        self.knowledge.composer.clinical._authorize(
            patient_id, case_id, actor, purpose)
        self.knowledge.composer.clinical.provenance._allow(
            patient_id, case_id, actor=actor, purpose=purpose,
            action="patient_context.read")
        return {
            "contract": "oi.synthetic-unified-clinical-review/1",
            "patient_id": patient_id,
            "case_id": case_id,
            "question_id": question_id,
            "composer_context_fingerprint": current_fingerprint,
            "evidence_review": quoted,
            "numeric_receipt": {
                "run_id": run_id,
                "status": numeric["review_status"],
                "run": numeric["durable_run"],
                "original_source_provenance":
                    numeric["original_source_provenance"],
            },
            "human_review_state": "pending",
            "clinical_decision": "not_performed",
            "clinical_approval": False,
            "model_executed_by_bundle": False,
            "external_effect_authorized": False,
            "publisher_rights_independently_verified": False,
            "snapshot_consistency": "sequential_preflight_not_cross_system_atomic",
            "limitations": (
                "Fictional data only. Literal matching does not establish "
                "medical applicability. Historical numeric receipts are not "
                "current results. This is a read-only preview, not a clinician "
                "signature, permission to redistribute research text, real "
                "patient consent, or an authorized clinical action."
            ),
        }
