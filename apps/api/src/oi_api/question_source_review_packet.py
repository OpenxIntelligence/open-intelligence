"""Source-quoted evidence inspection over one canonical H1 question and source.

Read-only adaptation of first-party source quotation / review preflight ideas:
no second source, question, rights, evidence, or review record; no model calls.
The trusted PostgresSourceVersions owner verifies literal source statements,
bytes, versions and case binding before this derived packet is prepared.

This is NOT a clinical/biomedical literature evidence assessment, eligibility
claim, clinician review, approved report or transfer of source rights.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import hashlib
import hmac
import json
import re
from typing import TypeVar

from open_intelligence.patient_registry import (
    PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from .case_bindings import _case_id
from .composer_preflight import SOURCE_SNAPSHOT_CONTRACT
from .source_world_model import project_source_world_model
from .sources import PostgresSourceVersions

Packet = TypeVar("Packet")
QUESTION_ID = re.compile(r"QUESTION-[0-9A-F]{32}\Z")
MAX_RELATED = 16


def _observation_view(o: dict) -> dict:
    """Copy ONLY the bounded, original source-derived fields."""
    return {
        "source_id": o["source_id"], "document_id": o["document_id"],
        "document_version": o["document_version"],
        "source_sha256": o["source_sha256"], "source_line": o["source_line"],
        "finding_key": o["finding_key"], "reported_state": o["reported_state"],
        "source_statement": o["source_statement"], "source_kind": o["source_kind"],
        "specimen_id": o["specimen_id"], "event_date": o["event_date"],
        "issued_at": o["issued_at"],
        "review_state": "not_established",
        "clinical_meaning": None,
    }


class PostgresQuestionSourcePacket:
    """Patient/source-bound packet prepared inside source owner transaction."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Existing PostgreSQL patient registry required")
        self.registry = registry

    def read(self, patient_id: str, case_id: str, question_id: str, *,
             organization: str, actor: str, purpose: str,
             recheck_authority: Callable[[], None],
             prepare_response: Callable[[dict], Packet] | None = None) -> Packet | dict:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if (purpose != "operations" or type(question_id) is not str
                or QUESTION_ID.fullmatch(question_id) is None):
            raise PatientRegistryDenied("Source question unavailable")

        def prepare(index: dict):
            # This is the original World Model's source-only projection,
            # under the source owner's actual PostgreSQL case lock. Its
            # literal source content and all assertion lines have already
            # been validated against the original bytes in list_locked().
            world = project_source_world_model(index)
            row = self.registry._fetchone(
                "SELECT patient_id,case_id,question,source_id,source_line,"
                "source_sha256,source_version,source_snapshot_sha256,"
                "preflight_sha256,created_at,source_snapshot_contract "
                "FROM investigation.source_questions "
                "WHERE question_id=%s AND patient_id=%s AND case_id=%s "
                "AND origin_org=%s" + text_question_filter(self.registry),
                (question_id,patient_id,case_id,organization),
            )
            if row is None:
                raise PatientRegistryDenied("Source question unavailable")
            (pid,cid,question,source_id,line,digest,version,snapshot,
             preflight,created_at,snapshot_contract) = row
            original = {
                "source_id":source_id, "source_line":line,
                "source_sha256":digest,"source_version":version,
                "source_snapshot_sha256":snapshot,
                "source_snapshot_contract":snapshot_contract,
                "preflight_sha256":preflight,
            }
            # A legacy question created from an incompatible World Model
            # fingerprint can NEVER be promoted by hash equality alone.
            matches = [
                o for o in world["observations"]
                if (o["source_id"]==source_id and o["source_line"]==line
                    and o["source_sha256"]==digest
                    and o["document_version"]==version)
            ]
            current = (
                snapshot_contract==SOURCE_SNAPSHOT_CONTRACT
                and hmac.compare_digest(snapshot,world["snapshot_fingerprint"])
                and len(matches)==1
            )
            selected = _observation_view(matches[0]) if current else None
            related: list[dict] = []
            related_total=0
            if selected is not None and selected["specimen_id"] is not None:
                related_all=[
                    o for o in world["observations"]
                    if (o["source_id"],o["source_line"])!=(source_id,line)
                    and o["finding_key"]==selected["finding_key"]
                    and o["specimen_id"]==selected["specimen_id"]
                    and o["event_date"]==selected["event_date"]
                ]
                related_total=len(related_all)
                related=[_observation_view(o) for o in related_all[:MAX_RELATED]]
            # Stable packet digest intentionally EXCLUDES the newly created
            # source-access receipt ID. It is a content-change detector, never
            # an execution grant or a receipt of browser delivery.
            stable={
                "contract":"oi.synthetic-question-source-review-packet/1",
                "patient_id":pid,"case_id":cid,"question_id":question_id,
                "question":question,
                "original_anchor":original,
                "source_context_state":(
                    "current_unreviewed_source" if current
                    else "source_reassessment_required"),
                "current_source_snapshot_sha256":world["snapshot_fingerprint"],
                "selected_statement":selected,"related_statements":related,
                "related_statement_count_total":related_total,
                "related_statements_truncated":related_total>len(related),
                "current_source_count":world["summary"]["current_sources"],
                "current_observation_count":world["summary"]["current_observations"],
                "external_biomedical_evidence_qualified":False,
                "published_evidence_rights_verified":False,
                "medical_interpretation_performed":False,
                "clinical_review_connected":False,
                "clinical_approval":False,
                "reviewer_identity_verified":False,
                "synthetic":True,
                "review_next_step":(
                    "independent_source_verification_required"
                    if current else "refresh_source_and_create_new_question"),
            }
            packet_sha256=hashlib.sha256(json.dumps(
                stable,sort_keys=True,ensure_ascii=False,
                separators=(",",":"),allow_nan=False,
            ).encode("utf-8")).hexdigest()
            result={
                **stable,
                "packet_sha256":packet_sha256,
                "source_access_receipt_id":index["access_receipt_id"],
            }
            # Typed response preparation occurs before final current-grant
            # revalidation and audit event insertion in list_locked().
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id,case_id,organization=organization,actor=actor,
                purpose=purpose,prepare_response=prepare,
                recheck_authority=recheck_authority,
            )
