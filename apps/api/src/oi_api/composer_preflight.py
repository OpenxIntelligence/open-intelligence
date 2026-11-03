"""A bounded, source-only Composer preflight over canonical PostgreSQL originals.

This is an IN-MEMORY read-only handoff contract for the existing first-party
clinical Composer. That Composer's full question/evidence/run/review owners still
live in the separate clinical reference stack and are NOT implicitly ported.
A preflight is NOT an investigation, authorizer token, model run, human-review
receipt or clinical approval. No schema, source copy, model, or event is created.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .sources import _source_id
from .world_model_read import PostgresWorldModelRead

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
VERSION = "oi.synthetic-source-composer-preflight/1"


class PostgresSourceComposerPreflight:
    """Prepare exact authored source context; execute absolutely nothing."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL registry required")
        self.registry = registry

    def preview(self, patient_id: str, case_id: str, *,
                organization: str, actor: str, purpose: str,
                expected_source_snapshot_sha256: str,
                source_id: str, source_line: int,
                question: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        source_id = _source_id(source_id)
        if purpose != "operations":
            # H1 research purpose must not be relabelled clinical authority.
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

        # The established World Model adapter verifies raw SHA and literal
        # assertion/line matches under the existing qualified-case row lock.
        # This read commits before returning: its fingerprint is a historical
        # preflight receipt, never a durable authorization at execution time.
        world = PostgresWorldModelRead(self.registry).read(
            patient_id, case_id, organization=organization
        )
        if not hmac.compare_digest(
            world["source_snapshot_sha256"], expected_source_snapshot_sha256
        ):
            raise PatientRegistryConflict(
                "Source version changed; refresh the original before preflight"
            )
        selected = [
            item for item in world["observations"]
            if item["source_version_id"] == source_id
            and item["source_line"] == source_line
        ]
        if len(selected) != 1:
            raise PatientRegistryConflict(
                "Source anchor is absent, superseded or no longer current"
            )
        anchor = selected[0]
        # No external evidence appraisals are available in this adapter:
        # do NOT fabricate such receipts or infer licensed content rights.
        prepared = {
            "contract": VERSION,
            "patient_id": patient_id,
            "case_id": case_id,
            "question": question,
            "source_snapshot_sha256": world["source_snapshot_sha256"],
            "selected_source": {
                "source_id": anchor["source_version_id"],
                "document_id": anchor["document_id"],
                "version": anchor["document_version"],
                "sha256": anchor["source_sha256"],
                "line": anchor["source_line"],
                "finding_key": anchor["finding_key"],
                "reported_state": anchor["reported_state"],
                "statement": anchor["source_statement"],
                "kind": anchor["source_kind"],
                "event_date": anchor["event_date"],
                "issued_at": anchor["issued_at"],
                "specimen_id": anchor["specimen_id"],
            },
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
        raw = json.dumps(prepared, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
        prepared["preflight_sha256"] = hashlib.sha256(raw).hexdigest()
        # Permission must still be enforced for every later action. The
        # fingerprint is only a deterministic equality check, not a token.
        return prepared
