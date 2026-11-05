"""Source-only Composer preparation over the canonical, validated PG source owner.

Ported from the first-party preflight without its competing World Model reader.
This prepares fictional source context, never a model run or clinical approval.
Successful disclosure commits the existing source-read authorization receipt.
"""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import hmac
import json
import re
from typing import TypeVar

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .source_anchor import selected_observation_anchor
from .question_anchors import anchor_from_preflight
from .sources import PostgresSourceVersions, _source_id
from .source_world_model import project_source_world_model

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
VERSION = "oi.synthetic-source-composer-preflight/2"
SOURCE_SNAPSHOT_CONTRACT = "oi.pg-source-world-model/1"
PreparedResponse = TypeVar("PreparedResponse")


class PostgresSourceComposerPreflight:
    """Prepare an exact current source anchor; execute no investigation."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL registry required")
        self.registry = registry

    def preview(self, patient_id: str, case_id: str, *,
                organization: str, actor: str, purpose: str,
                expected_source_snapshot_sha256: str,
                source_id: str, source_line: int, question: str,
                recheck_authority: Callable[[], None],
                prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        def prepare(index):
            result = self.preview_locked(
                patient_id, case_id, organization=organization, actor=actor,
                purpose=purpose, expected_source_snapshot_sha256=expected_source_snapshot_sha256,
                source_id=source_id, source_line=source_line, question=question,
                source_index=index,
            )
            return prepare_response(result) if prepare_response is not None else result

        return PostgresSourceVersions(self.registry).list(
            patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
            prepare_response=prepare, recheck_authority=recheck_authority,
        )

    def preview_laboratory(self, patient_id: str, case_id: str, *,
                           organization: str, actor: str, purpose: str,
                           expected_source_snapshot_sha256: str,
                           source_id: str, observation_reference: str, question: str,
                           recheck_authority: Callable[[], None],
                           prepare_response: Callable[[dict], PreparedResponse] | None = None
                           ) -> dict | PreparedResponse:
        """Prepare a typed laboratory anchor without creating a saved question.

        The canonical source owner validates original custody, holds the active
        patient/case locks, and commits its existing read receipt only after the
        complete response and fresh authority checks succeed. Laboratory children
        are read inside that same transaction, never from caller-supplied values.
        """
        from .laboratory_fhir_store import PostgresLaboratoryFHIR

        if purpose != "operations":
            raise PatientRegistryDenied("Laboratory question context unavailable")
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")

        def prepare(index):
            if not self.registry._transaction_active:
                raise PatientRegistryError("Laboratory preflight requires source transaction")
            observations = PostgresLaboratoryFHIR(self.registry).current_observations_locked(case_id)
            result = prepare_laboratory_question(
                index, observations, patient_id=patient_id, case_id=case_id,
                source_id=source_id, observation_reference=observation_reference,
                question=question,
                expected_source_snapshot_sha256=expected_source_snapshot_sha256,
            )
            return prepare_response(result) if prepare_response is not None else result

        return PostgresSourceVersions(self.registry).list(
            patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
            prepare_response=prepare, recheck_authority=recheck_authority,
        )

    def preview_locked(self, patient_id: str, case_id: str, *,
                       organization: str, actor: str, purpose: str,
                       expected_source_snapshot_sha256: str,
                       source_id: str, source_line: int, question: str,
                       source_index: dict) -> dict:
        """Prepare from the source owner's validated index in its transaction.

        The caller is the trusted source-preparation callback; it still owns
        final authority checks, the read receipt and commit. The index's ACCESS
        identifier is reserved until those steps all succeed.
        """
        if not self.registry._transaction_active:
            raise PatientRegistryError("Composer locked preflight requires caller transaction")
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        _key(organization, "organization")
        _key(actor, "actor")
        source_id = _source_id(source_id)
        if purpose != "operations":
            raise PatientRegistryDenied("Composer purpose unavailable")
        if (type(expected_source_snapshot_sha256) is not str
                or not SHA256.fullmatch(expected_source_snapshot_sha256)):
            raise PatientRegistryError("Invalid source snapshot fingerprint")
        if type(source_line) is not int or not 1 <= source_line <= 10_000:
            raise PatientRegistryError("Invalid exact original line")
        if (type(question) is not str or not 8 <= len(question.strip()) <= 500
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in question)
                or question != question.strip()):
            raise PatientRegistryError("Invalid fictional Composer question")

        world = project_source_world_model(source_index)
        if (world["patient_id"] != patient_id or world["case_id"] != case_id
                or world["contract"] != SOURCE_SNAPSHOT_CONTRACT):
            raise PatientRegistryDenied("Source context unavailable")
        if not hmac.compare_digest(world["snapshot_fingerprint"], expected_source_snapshot_sha256):
            raise PatientRegistryConflict("Source version changed; refresh the original before preflight")
        selected = [item for item in world["observations"]
                    if item["source_id"] == source_id and item["source_line"] == source_line]
        if len(selected) != 1:
            raise PatientRegistryConflict("Source anchor is absent, superseded or no longer current")
        anchor = selected[0]
        prepared = {
            "contract": VERSION,
            "patient_id": patient_id,
            "case_id": case_id,
            "question": question,
            "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
            "source_snapshot_sha256": world["snapshot_fingerprint"],
            "selected_source": selected_observation_anchor(anchor),
            "source_context_only": True,
            "biomedical_evidence_rights_verified": False,
            "model_execution_authorized": False,
            "durable_question_created": False,
            "durable_review_connected": False,
            "clinical_approval": False,
            "clinical_interpretation": "not_performed",
            "reassessment_policy": "revalidate_source_and_authority_before_any_future_write",
            "limitations": (
                "Independently authored fictional source quotation only; no "
                "clinical assessment, validated provider, real consent, "
                "licensed scientific evidence, AI execution or clinician review. "
                "The existing clinical Composer/review ledger is not yet "
                "mounted on the PostgreSQL source owner."
            ),
        }
        anchor_from_preflight(prepared)
        raw = json.dumps(prepared, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
        prepared["preflight_sha256"] = hashlib.sha256(raw).hexdigest()
        # Receipt churn must not change the content/intent fingerprint. The
        # ACCESS identifier only describes the authorized source-context read.
        prepared["access_receipt_id"] = world["access_receipt_id"]
        return prepared


def prepare_laboratory_question(source_index: dict, laboratory_observations: list[dict], *,
                                patient_id: str, case_id: str, source_id: str,
                                observation_reference: str, question: str,
                                expected_source_snapshot_sha256: str) -> dict:
    """Build literal typed context from an already validated source-owner read.

    Internal projection, not an authorization or integrity validator. Only the
    owner callback above may supply this context to a request. The source read
    validates every stored laboratory child against its exact original bytes.
    No original byte offsets, text lines, clinical conclusions or new identities
    are invented. The reference is local to the selected immutable source.
    """
    from .laboratory_fhir_r4 import LaboratoryBundleRejected, _reference

    patient_id = _key(patient_id, "patient_id")
    case_id = _case_id(case_id)
    source_id = _source_id(source_id)
    try:
        _reference({"reference": observation_reference}, "Observation")
    except LaboratoryBundleRejected:
        raise PatientRegistryError("Invalid local laboratory observation reference") from None
    if (type(expected_source_snapshot_sha256) is not str
            or not SHA256.fullmatch(expected_source_snapshot_sha256)):
        raise PatientRegistryError("Invalid source snapshot fingerprint")
    if (type(question) is not str or not 8 <= len(question.strip()) <= 500
            or question != question.strip()
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in question)):
        raise PatientRegistryError("Invalid fictional Composer question")
    if (type(source_index) is not dict
            or (source_index.get("patient_id"), source_index.get("case_id"))
            != (patient_id, case_id)):
        raise PatientRegistryDenied("Laboratory source context unavailable")
    world = project_source_world_model(source_index, laboratory_observations)
    if not hmac.compare_digest(world["snapshot_fingerprint"], expected_source_snapshot_sha256):
        raise PatientRegistryConflict("Source version changed; refresh before laboratory preflight")
    selected = [item for item in world["laboratory_observations"]
                if (item["source_id"], item["observation_reference"])
                == (source_id, observation_reference)]
    if len(selected) != 1:
        raise PatientRegistryConflict("Laboratory anchor is absent, superseded or no longer current")
    anchor = selected[0]
    source = next(item for item in world["current_sources"] if item["source_id"] == source_id)
    if (anchor["specimen_reference"] != "Specimen/" + str(source["specimen_id"])
            or anchor["report_reference"] != "DiagnosticReport/" + source["document_id"]):
        raise PatientRegistryError("Laboratory source relationships do not match canonical context")
    selected_source = {
        "anchor_kind": "fhir_observation", "source_id": source_id,
        "document_id": anchor["document_id"], "version": anchor["document_version"],
        "sha256": anchor["source_sha256"], "kind": "laboratory",
        "resource_reference": observation_reference,
        "specimen_reference": anchor["specimen_reference"],
        "specimen_type_text": anchor["specimen_type_text"],
        "specimen_collected_at": anchor["specimen_collected_at"],
        "report_reference": anchor["report_reference"],
        "loinc_code": anchor["loinc_code"], "effective_at": anchor["effective_at"],
        "issued_at": anchor["issued_at"], "status": anchor["status"],
        "value_text": anchor["value_text"], "unit_code": anchor["unit_code"],
        "absent_reason": anchor["absent_reason"], "source_reported": True,
        **({"coded_result": anchor["coded_result"]} if "coded_result" in anchor else {}),
        "review_state": "not_established", "clinical_review": "not_performed",
    }
    prepared = laboratory_preflight_payload(patient_id, case_id, question, world["snapshot_fingerprint"], selected_source)
    # Reserved by the source owner. It becomes a durable read receipt only after
    # serialization, final authority, event persistence and transaction commit.
    prepared["access_receipt_id"] = world["access_receipt_id"]
    return prepared


def laboratory_preflight_payload(patient_id: str, case_id: str, question: str, snapshot: str,
                                 selected_source: dict) -> dict:
    """Stable saved-question material. A matching digest grants no access or review status."""
    prepared = {
        "contract": "oi.synthetic-laboratory-question-preflight/1",
        "patient_id": patient_id, "case_id": case_id, "question": question,
        "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
        "source_snapshot_sha256": snapshot,
        "selected_source": selected_source, "synthetic": True,
        "source_context_only": True, "durable_question_created": False,
        "durable_review_connected": False, "biomedical_evidence_rights_verified": False,
        "model_execution_authorized": False, "clinical_approval": False,
        "clinical_interpretation": "not_performed", "terminology_validation": "not_performed",
        "reassessment_policy": "revalidate_source_and_authority_before_any_future_write",
    }
    anchor_from_preflight(prepared)
    raw = json.dumps(prepared, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    prepared["preflight_sha256"] = hashlib.sha256(raw).hexdigest()
    return prepared
