"""Bind existing patient/EHR/LIS/Composer preview to rights-aware evidence preflight.

Synthetic only. Read-only; no network, clinical AI execution, verified consent,
medical interpretation, model authorization, or new patient/source ledger.
"""
from __future__ import annotations

import copy
import hmac
import json
from typing import Callable

from .clinical_composer_context import AuthorizedClinicalComposer
from .clinical_continuity import ClinicalContinuityError
from .clinical_lab_bridge import LinkedLabCaseStore
from .composer import composer_context_fingerprint
from .knowledge_context import compile_context, KnowledgeContextError
from .source_provenance import PROVENANCE_FIELDS

# A trusted caller must provide an independently authorized and versioned
# source-rights service in production. This fixture callback is NOT one.
KnowledgeProvider = Callable[[str, str, int, str, str], dict]


def _sealed(value: object) -> bytes:
    """Strict deterministic comparison, rejecting mutable/unserializable claims."""
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise KnowledgeContextError("invalid external knowledge record") from exc


class AuthorizedClinicalKnowledge:
    """Join *existing* owners, not a second identity or biomedical knowledge DB."""

    def __init__(self, composer: AuthorizedClinicalComposer,
                 store: LinkedLabCaseStore,
                 source_provider: KnowledgeProvider | None = None):
        if not isinstance(composer, AuthorizedClinicalComposer) or composer.store is not store:
            raise TypeError("knowledge adapter must share the authorized Composer source owner")
        self.composer = composer
        self.store = store
        self.source_provider = source_provider

    def _provider(self, patient_id: str, case_id: str, question_id: int,
                  actor: str, purpose: str) -> dict:
        # No provider means *no* external evidence; fail closed, not a
        # fallback to a public endpoint, fabricated summary or guideline.
        if self.source_provider is None:
            return {"sources": [], "proposals": []}
        payload = self.source_provider(patient_id, case_id, question_id,
                                       actor, purpose)
        if not isinstance(payload, dict) or set(payload) != {"sources", "proposals"}:
            raise KnowledgeContextError("trusted source provider must return sources and proposals")
        return copy.deepcopy(payload)

    @staticmethod
    def _align_assertions(composer: dict, packet: dict) -> None:
        # Composer previews are capped at 100 source records and assertions.
        # Reject incomplete crossings rather than silently losing patient facts.
        if (composer["source_count"] > composer["source_preview_limit"] or
                len(packet["patient_assertions"]) != len(composer["source_anchors"])):
            raise ClinicalContinuityError("Composer source preview is incomplete")
        originals = {row["id"]: row for row in composer["current_sources"]}
        if (len(originals) != composer["source_count"] or
                any(row["source_version_id"] not in originals
                    for row in composer["source_anchors"])):
            raise ClinicalContinuityError("Composer original source references are incomplete")
        from_packet = {
            (x["source_version_id"], x["source_line"],
             x["finding_key"], x["reported_state"], x["source_statement"],
             x["source_document"], x["version"], x["source_hash"],
             _sealed({key: x[key] for key in PROVENANCE_FIELDS if key in x}))
            for x in packet["patient_assertions"]
        }
        from_composer = {
            (x["source_version_id"], x["source_line"],
             x["finding_key"], x["reported_state"], x["statement"],
             originals[x["source_version_id"]]["document_id"],
             originals[x["source_version_id"]]["version"],
             originals[x["source_version_id"]]["sha256"],
             _sealed({key: x[key] for key in PROVENANCE_FIELDS if key in x}))
            for x in composer["source_anchors"]
        }
        if from_packet != from_composer or len(from_packet) != len(packet["patient_assertions"]):
            raise ClinicalContinuityError("knowledge observations diverge from Composer source anchors")

    def snapshot(self, patient_id: str, case_id: str, question_id: int, *,
                 actor: str, purpose: str) -> dict:
        """Authorized fictional review preview with independent evidence-rights gate.

        No packet is a credential, model prompt authorization or clinical signoff.
        Two reads narrow races; separate review DB and rights provider mean no
        cross-system atomic snapshot is claimed.
        """
        before = self.composer.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose)
        supplied = self._provider(patient_id, case_id, question_id, actor, purpose)
        signature = _sealed(supplied)
        state = self.store.state(case_id)
        packet = compile_context(case_id, state, supplied["sources"],
                                 supplied["proposals"])
        self._align_assertions(before["composer"], packet)

        # Independently enforce binding, purpose and current clinical sources
        # again after the external evidence provider and context compilation.
        after = self.composer.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose)
        if before != after:
            raise ClinicalContinuityError("clinical or Composer context changed during knowledge assembly")
        current = composer_context_fingerprint(self.store, case_id, question_id)
        if not hmac.compare_digest(current, after["composer"]["fingerprint"]):
            raise ClinicalContinuityError("patient source or evidence changed during knowledge assembly")
        if not hmac.compare_digest(signature, _sealed(self._provider(
                patient_id, case_id, question_id, actor, purpose))):
            raise KnowledgeContextError("external rights or knowledge state changed; retry review")
        # The last provider call can outlive a source amendment, failed QC or
        # note revision even when its own rights/evidence payload is unchanged.
        # Re-read the complete authorized clinical projection *after* that call;
        # checking only permissions or Composer's source hash misses QC/notes.
        final = self.composer.snapshot(
            patient_id, case_id, question_id, actor=actor, purpose=purpose)
        if after != final:
            raise ClinicalContinuityError(
                "clinical or Composer context changed during final knowledge read")
        # Final sensitive-context gate after independently reading external
        # rights; still not an atomic distributed read or legal source proof.
        self.composer.clinical._authorize(patient_id, case_id, actor, purpose)
        self.composer.clinical.provenance._allow(
            patient_id, case_id, actor=actor, purpose=purpose,
            action="patient_context.read")
        self._align_assertions(final["composer"], packet)

        return {
            "contract": "oi.synthetic-authorized-patient-evidence/1",
            "patient_id": patient_id,
            "case_id": case_id,
            "question_id": question_id,
            "clinical_composer": final,
            "knowledge": packet,
            "review_state": "pending_human_evidence_review",
            "model_execution_authorized": False,
            "clinical_conclusion_established": False,
            "rights_clearance": "external_receipts_unverified_fixture_only",
            "snapshot_consistency": "non_atomic_cross_domain_preflight_only",
            "disclaimer": (
                "Fictional patient information and independently authored "
                "biomedical test evidence, not a real medical record, "
                "verified guideline, diagnosis, treatment or model input grant. "
                "Patient access, source rights and clinical approval require "
                "separate production authority and independent review."
            ),
        }
