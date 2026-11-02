"""Authorized first-party clinical continuity → native source-bound Composer read.

This is a narrow, *read-only* composition of existing first-party product
owners. It creates no second patient/source/world-model record and executes no
model, clinical order or professional approval. All identities and policies in
its tests are fictional; production-grade verified identity/consent is absent.

ClinicalContinuityView already verifies the canonical patient-to-case mapping,
exact laboratory release provenance, EHR source linkage, and separate actor/
purpose access. The existing Composer preview adds current source/version/
question/assessed-evidence context. Neither source can authorize the other.
"""
from __future__ import annotations

import hmac

from .clinical_continuity import ClinicalContinuityView, ClinicalContinuityError
from .clinical_lab_bridge import LinkedLabCaseStore
from .composer import build_composer_context, composer_context_fingerprint


class AuthorizedClinicalComposer:
    """Join current clinical pointers and existing Composer under one gate.

    The same CaseStore/source connection must back the canonical clinical
    owner and Composer. The receiver for laboratory review remains distinct;
    the result explicitly does NOT claim a cross-database atomic snapshot.
    """

    def __init__(self, clinical: ClinicalContinuityView,
                 store: LinkedLabCaseStore):
        if not isinstance(clinical, ClinicalContinuityView):
            raise TypeError("Expected the existing clinical continuity authority")
        if not isinstance(store, LinkedLabCaseStore):
            raise TypeError("Composer must use the original linked CaseStore")
        if (clinical.registry.db is not store.db or
                clinical.lab.store is not store or
                clinical.provenance.sources is not store or
                clinical.lab.registry is not clinical.registry):
            raise ClinicalContinuityError(
                "Clinical and Composer reads must share one patient/source owner")
        self.clinical = clinical
        self.store = store

    def snapshot(self, patient_id: str, case_id: str, question_id: int, *,
                 actor: str, purpose: str) -> dict:
        """Return a fictional, permission-checked preview, not an action token.

        Fail closed when the patient/case mapping or source snapshot changes
        during assembly. Read-only preflight does not replace actor-scoped tool
        execution authorization or distributed consistency transactions.
        """
        clinical_before = self.clinical.snapshot(
            patient_id, case_id, actor=actor, purpose=purpose)
        # The source preview has NO independently trusted identity context. It
        # must never be called from an external API before the clinical gate.
        composer = build_composer_context(self.store, case_id, question_id)
        clinical_after = self.clinical.snapshot(
            patient_id, case_id, actor=actor, purpose=purpose)
        if clinical_before != clinical_after:
            raise ClinicalContinuityError(
                "Clinical context changed during Composer preview; refresh")
        latest = composer_context_fingerprint(self.store, case_id, question_id)
        if not hmac.compare_digest(latest, composer["fingerprint"]):
            raise ClinicalContinuityError(
                "Source/evidence context changed; stale Composer preview")
        # Recheck purpose and the actual case binding *after* the last
        # fingerprint read. This narrows revocation races but is not an atomic
        # snapshot across the separate laboratory review receiver.
        self.clinical._authorize(patient_id, case_id, actor, purpose)
        self.clinical.provenance._allow(
            patient_id, case_id, actor=actor,
            purpose=purpose, action="patient_context.read")

        return {
            "contract": "oi.synthetic-authorized-clinical-composer/1",
            "patient_id": patient_id,
            "case_id": case_id,
            "question_id": question_id,
            "clinical": clinical_after,
            "composer": composer,
            "authority": {
                "actor_policy": "synthetic_injected_authorizer_only",
                "patient_case_relationship": "fixture_reviewed_not_identity_proof",
                "clinical_review": "not_performed",
                "clinical_action": "not_authorized_or_executed",
            },
            "snapshot_consistency": "not_a_distributed_atomic_snapshot",
            "disclaimer": (
                "Synthetic research and engineering integration only. "
                "Source-reported clinical information and pending laboratory "
                "review are not accepted medical facts, treatments or sign-offs. "
                "The caller must independently authorize every later Composer "
                "tool run against current patient, source and purpose."
            ),
        }
