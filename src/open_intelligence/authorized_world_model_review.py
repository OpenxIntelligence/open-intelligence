"""Authorized fictional Patient World Model + evidence + numeric review composition.

This is a read-only adapter over existing PatientRegistry/clinical continuity,
CaseStore, knowledge-rights, source-quote, and durable-run implementations.
All records are independently authored synthetic examples. It is neither a
clinical system of record nor a PHI-ready endpoint or professional approval.
"""
from __future__ import annotations

from .clinical_continuity import ClinicalContinuityError
from .patient_research_review import same
from .unified_clinical_review import UnifiedClinicalReview
from .world_model import synthetic_world_model


def _observation_key(observation: dict) -> tuple:
    """Authoritative fields shared by the original knowledge and PWM owners."""
    return (
        observation["source_version_id"],
        observation["source_line"],
        observation["finding_key"],
        observation["reported_state"],
        observation["source_statement"],
        observation["source_sha256"],
        observation["event_date"],
        observation["issued_at"],
    )


def _knowledge_key(assertion: dict) -> tuple:
    return (
        assertion["source_version_id"],
        assertion["source_line"],
        assertion["finding_key"],
        assertion["reported_state"],
        assertion["source_statement"],
        assertion["source_hash"],
        assertion["source_date"],
        assertion["issued_at"],
    )


class AuthorizedWorldModelReview:
    """Use exactly the already-authorized unified-review and source owners."""

    def __init__(self, unified: UnifiedClinicalReview):
        if not isinstance(unified, UnifiedClinicalReview):
            raise TypeError("Existing authorized unified clinical review is required")
        self.unified = unified
        self.knowledge = unified.knowledge
        self.store = unified.knowledge.store

    def preview(self, patient_id: str, case_id: str, question_id: int,
                run_id: int, *, actor: str, purpose: str,
                selected_quotes: list[dict]) -> dict:
        """Expose source observations only after patient and rights preflight.

        The before/after checks narrow source, rights and permission races,
        but cannot form an atomic snapshot of the separate lab review receiver
        or a separately supplied external rights provider.
        """
        before = self.knowledge.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose
        )
        review = self.unified.preview(
            patient_id, case_id, question_id, run_id,
            actor=actor, purpose=purpose, selected_quotes=selected_quotes
        )
        # No external caller is offered raw CaseStore state. This projection
        # only runs after the same authorized clinical source read as #149.
        current = synthetic_world_model(self.store.state(case_id), case_id)
        after = self.knowledge.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose
        )
        if (not same(before, after)
                or review["patient_id"] != patient_id
                or review["case_id"] != case_id
                or review["question_id"] != question_id
                or review["composer_context_fingerprint"] !=
                   after["clinical_composer"]["composer"]["fingerprint"]):
            raise ClinicalContinuityError(
                "patient, source, evidence or authority changed during world-model review"
            )

        observations = current["observations"]
        source_assertions = after["knowledge"]["patient_assertions"]
        keys = [_observation_key(x) for x in observations]
        expected = [_knowledge_key(x) for x in source_assertions]
        if (len(keys) != len(expected)
                or len(set(keys)) != len(keys)
                or set(keys) != set(expected)):
            raise ClinicalContinuityError(
                "patient world-model observations diverge from rights-gated source evidence"
            )
        # Verify every original source used in the projection is still
        # current according to the same case ledger. No inferred source joins.
        if {s["source_version_id"] for s in current["current_sources"]} != {
                s["id"] for s in self.store.state(case_id)["sources"]
                if s["state"] == "current"}:
            raise ClinicalContinuityError("source versions changed during world-model read")

        # Recheck the privileged clinical binding/purpose after the final
        # source query. These injected policy callbacks are fictional tests,
        # not credentials or a production consent service.
        clinical = self.knowledge.composer.clinical
        clinical._authorize(patient_id, case_id, actor, purpose)
        clinical.provenance._allow(
            patient_id, case_id, actor=actor, purpose=purpose,
            action="patient_context.read",
        )
        final = self.knowledge.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose
        )
        if not same(after, final):
            raise ClinicalContinuityError(
                "source, rights or clinical state changed during final patient review"
            )
        return {
            "contract": "oi.synthetic-authorized-world-model-review/1",
            "patient_id": patient_id,
            "case_id": case_id,
            "question_id": question_id,
            "patient_world_model": current,
            "unified_review": review,
            "authority": "injected_synthetic_authorization_only",
            "human_review_state": "pending",
            "clinical_approval": False,
            "model_executed_by_adapter": False,
            "publisher_rights_independently_verified": False,
            "snapshot_consistency": "sequential_preflight_not_distributed_atomic",
            "limitations": (
                "Original fictional source observations and permissions only; "
                "no clinical interpretation, real consent, licensed publication "
                "rights, authenticated provider, PHI, or medical action."
            ),
        }
