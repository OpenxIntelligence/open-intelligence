"""Canonical H1 question intake over one validated source owner and event journal.

Preserves the first-party question persistence and idempotency contract. Every
operation prepares its DTO under source locks, then refreshes authority and
records source access before the same transaction commits. No review is implied.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hmac
import re
from typing import TypeVar
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .question_origin import classify_stored_question_origin
from .composer_preflight import PostgresSourceComposerPreflight, SHA256, SOURCE_SNAPSHOT_CONTRACT
from .sources import PostgresSourceVersions, _source_id
from .source_world_model import project_source_world_model
from .source_brief import render_source_brief

LEGACY_SNAPSHOT_CONTRACT = "oi.synthetic-postgres-world-model-sources/1"
QUESTION_LIST_CONTRACT = "oi.synthetic-source-questions/2"
PreparedResponse = TypeVar("PreparedResponse")


def _request_key(value: str) -> str:
    return _key(value, "request_key")


class PostgresSourceQuestions:
    """Owned, operational question intake; not a clinical review queue."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    @staticmethod
    def _intent(patient_id: str, case_id: str, organization: str,
                actor: str, purpose: str, key: str, source_id: str,
                source_line: int, question: str, fingerprint: str,
                preflight_sha256: str) -> str:
        return _digest({
            "patient": patient_id, "case": case_id, "organization": organization,
            "actor": actor, "purpose": purpose, "request_key": key,
            "source_id": source_id, "source_line": source_line,
            "question": question, "source_snapshot_sha256": fingerprint,
            "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
            "preflight_sha256": preflight_sha256,
        })

    @staticmethod
    def _question_state(row: tuple, world: dict) -> dict:
        """One projection for saved-question history and its readable brief."""
        (qid, pid, cid, question, sid, line, digest, version,
         old_fingerprint, preflight_sha, created_at, snapshot_contract) = row
        anchors = {(item["source_id"], item["source_line"]):
                   (item["source_sha256"], item["document_version"])
                   for item in world["observations"]}
        current = (snapshot_contract == SOURCE_SNAPSHOT_CONTRACT
                   and anchors.get((sid, line)) == (digest, version)
                   and hmac.compare_digest(old_fingerprint, world["snapshot_fingerprint"]))
        return {
            "question_id": qid, "patient_id": pid, "case_id": cid,
            "question": question, "source_id": sid, "source_line": line,
            "source_sha256": digest, "source_version": version,
            "source_snapshot_sha256": old_fingerprint,
            "source_snapshot_contract": snapshot_contract,
            "preflight_sha256": preflight_sha,
            "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
            "source_context_state": ("current_unreviewed_question" if current
                                     else "source_reassessment_required"),
            "human_review_state": "not_submitted",
            "clinical_approval": False, "model_executed": False,
        }

    def prepare_brief(self, patient_id: str, case_id: str, question_id: str, *,
                      organization: str, actor: str, purpose: str,
                      source_snapshot_contract: str,
                      expected_source_snapshot_sha256: str,
                      expected_preflight_sha256: str,
                      recheck_authority: Callable[[], None],
                      prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        """Prepare a current saved question under its sole source owner's lock.

        Export does not create or approve a question, rerun a model, or change
        review state. Only the existing source-read receipt is committed.
        """
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if (purpose != "operations" or type(question_id) is not str
                or re.fullmatch(r"QUESTION-[0-9A-F]{32}", question_id) is None):
            raise PatientRegistryDenied("Question brief unavailable")
        if source_snapshot_contract != SOURCE_SNAPSHOT_CONTRACT:
            raise PatientRegistryConflict("Question source contract requires reassessment")
        if any(type(value) is not str or not SHA256.fullmatch(value) for value in (
                expected_source_snapshot_sha256, expected_preflight_sha256)):
            raise PatientRegistryError("Question brief fingerprints must be SHA-256")

        def prepare(index):
            for action in ("patient_read", "question_read", "source_read", "source_brief_export"):
                self.registry._allow(actor, patient_id, action, purpose)
            row = self.registry._fetchone(
                "SELECT question_id,patient_id,case_id,question,source_id,"
                "source_line,source_sha256,source_version,source_snapshot_sha256,"
                "preflight_sha256,created_at,source_snapshot_contract "
                "FROM investigation.source_questions "
                "WHERE patient_id=%s AND case_id=%s AND origin_org=%s AND question_id=%s AND source_line IS NOT NULL",
                (patient_id, case_id, organization, question_id),
            )
            if row is None:
                raise PatientRegistryDenied("Question brief unavailable")
            world = project_source_world_model(index)
            question = self._question_state(row, world)
            if (question["source_context_state"] != "current_unreviewed_question"
                    or not hmac.compare_digest(question["source_snapshot_sha256"],
                                               expected_source_snapshot_sha256)
                    or not hmac.compare_digest(question["preflight_sha256"],
                                               expected_preflight_sha256)):
                raise PatientRegistryConflict("Question context changed; reassessment required")
            # Reuse the source-only calculation, not its composer permission:
            # this independent read/export grant cannot create a question or run AI.
            preflight = PostgresSourceComposerPreflight(self.registry).preview_locked(
                patient_id, case_id, organization=organization, actor=actor,
                purpose=purpose, expected_source_snapshot_sha256=expected_source_snapshot_sha256,
                source_id=question["source_id"], source_line=question["source_line"],
                question=question["question"], source_index=index,
            )
            selected = preflight["selected_source"]
            if (not hmac.compare_digest(preflight["preflight_sha256"], expected_preflight_sha256)
                    or (selected["source_id"], selected["line"], selected["sha256"], selected["version"])
                    != (question["source_id"], question["source_line"],
                        question["source_sha256"], question["source_version"])):
                raise PatientRegistryConflict("Question preflight changed; reassessment required")
            result = render_source_brief(world, question, selected,
                                         prepared_at=datetime.now(timezone.utc))
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=prepare, recheck_authority=recheck_authority,
            )

    def create(self, patient_id: str, case_id: str, *, organization: str,
               actor: str, purpose: str, request_key: str,
               source_id: str, source_line: int, question: str,
               expected_source_snapshot_sha256: str, expected_preflight_sha256: str,
               recheck_authority: Callable[[], None],
               prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _request_key(request_key)
        source_id = _source_id(source_id)
        if (purpose != "operations" or type(expected_preflight_sha256) is not str
                or not SHA256.fullmatch(expected_preflight_sha256)):
            raise PatientRegistryDenied("Question intake unavailable")
        if (type(expected_source_snapshot_sha256) is not str
                or not SHA256.fullmatch(expected_source_snapshot_sha256)):
            raise PatientRegistryError("Source fingerprint must be SHA-256")
        intent = self._intent(patient_id, case_id, organization, actor, purpose,
                              request_key, source_id, source_line, question,
                              expected_source_snapshot_sha256, expected_preflight_sha256)

        def receipt(question_id, duplicate):
            result = {"question_id": question_id, "duplicate": duplicate}
            return prepare_response(result) if prepare_response is not None else result

        def save(index):
            old = self.registry._fetchone(
                "SELECT question_id,intent_sha256,source_snapshot_contract "
                "FROM investigation.source_questions "
                "WHERE patient_id=%s AND request_key=%s FOR UPDATE",
                (patient_id, request_key),
            )
            if old is not None:
                if old[2] != SOURCE_SNAPSHOT_CONTRACT or not hmac.compare_digest(old[1], intent):
                    raise PatientRegistryConflict("Question request key reused with changed intent")
                # Exact retries preserve their original anchor even after an
                # amendment. The enclosing source owner still validates current
                # custody and refreshes every grant after preparing this DTO.
                return receipt(old[0], True)

            prepared = PostgresSourceComposerPreflight(self.registry).preview_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                expected_source_snapshot_sha256=expected_source_snapshot_sha256,
                source_id=source_id, source_line=source_line, question=question,
                source_index=index,
            )
            if not hmac.compare_digest(prepared["preflight_sha256"], expected_preflight_sha256):
                raise PatientRegistryConflict("Composer preflight changed before question write")
            self.registry._allow(actor, patient_id, "question_create", purpose)
            # Preserve the upstream pre-insert recheck as well as the final
            # source-owner recheck after all preparation and event work.
            recheck_authority()
            source = prepared["selected_source"]
            question_id = "QUESTION-" + uuid.uuid4().hex.upper()
            created = self.registry._fetchone(
                "INSERT INTO investigation.source_questions "
                "(question_id,patient_id,case_id,origin_org,request_key,"
                "intent_sha256,actor,purpose,question,source_id,source_line,"
                "source_sha256,source_version,source_snapshot_sha256,preflight_sha256,source_snapshot_contract) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING question_id",
                (question_id, patient_id, case_id, organization, request_key,
                 intent, actor, purpose, question, source_id, source_line,
                 source["sha256"], source["version"], expected_source_snapshot_sha256,
                 expected_preflight_sha256, SOURCE_SNAPSHOT_CONTRACT),
            )
            if created is None:
                winner = self.registry._fetchone(
                    "SELECT question_id,intent_sha256,source_snapshot_contract "
                    "FROM investigation.source_questions WHERE patient_id=%s AND request_key=%s",
                    (patient_id, request_key),
                )
                if (winner is None or winner[2] != SOURCE_SNAPSHOT_CONTRACT
                        or not hmac.compare_digest(winner[1], intent)):
                    raise PatientRegistryConflict("Question request intent changed")
                return receipt(winner[0], True)
            self.registry.append_event(
                patient_id, "investigation.question.created",
                question_id=question_id, case_id=case_id, source_id=source_id,
                source_line=source_line, source_snapshot_sha256=expected_source_snapshot_sha256,
                source_snapshot_contract=SOURCE_SNAPSHOT_CONTRACT, actor=actor,
            )
            return receipt(question_id, False)

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=save, recheck_authority=recheck_authority,
            )

    def project_locked(self, patient_id: str, case_id: str, *, organization: str,
                       source_index: dict) -> list[dict]:
        """Project question freshness from the source owner's validated context.

        Called only inside ``PostgresSourceVersions.list_locked`` preparation.
        This helper owns question freshness, not source materialization, grants,
        transactions or receipts. Both question history and review use it.
        """
        if not self.registry._transaction_active:
            raise PatientRegistryError("Question projection requires caller transaction")
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        if (source_index.get("patient_id"), source_index.get("case_id")) != (patient_id, case_id):
            raise PatientRegistryDenied("Question source context unavailable")
        world = project_source_world_model(source_index)
        rows = self.registry._fetchall(
            "SELECT q.question_id,q.patient_id,q.case_id,q.question,q.source_id,"
            "q.source_line,q.source_sha256,q.source_version,q.source_snapshot_sha256,"
            "q.preflight_sha256,q.created_at,q.source_snapshot_contract,"
            "a.source_id,a.observation_reference "
            "FROM investigation.source_questions q "
            "LEFT JOIN investigation.laboratory_question_anchors a ON a.question_id=q.question_id "
            "WHERE q.patient_id=%s AND q.case_id=%s AND q.origin_org=%s AND q.source_line IS NOT NULL "
            "ORDER BY q.created_at,q.question_id LIMIT 251",
            (patient_id, case_id, organization),
        )
        if len(rows) > 250:
            raise PatientRegistryError("Question list exceeds bounded read limit")
        anchors = {(item["source_id"], item["source_line"]):
                   (item["source_sha256"], item["document_version"])
                   for item in world["observations"]}
        results = []
        for (qid, pid, cid, question, sid, line, digest, version,
             old_fingerprint, preflight_sha, created_at, snapshot_contract, anchor_sid, anchor_ref) in rows:
            try:
                origin = classify_stored_question_origin(question_id=qid, source_id=sid,
                                                         source_line=line, observation_reference=anchor_ref,
                                                         anchor_source_id=anchor_sid)
            except ValueError as exc:
                raise PatientRegistryError("Stored source-line question origin is invalid") from exc
            if origin.kind != "source_line":
                raise PatientRegistryError("Stored source-line question origin is inconsistent")
            current = (snapshot_contract == SOURCE_SNAPSHOT_CONTRACT
                       and anchors.get((sid, line)) == (digest, version)
                       and hmac.compare_digest(old_fingerprint, world["snapshot_fingerprint"]))
            results.append({
                "question_id": qid, "patient_id": pid, "case_id": cid,
                "question": question, "source_id": sid, "source_line": line,
                "source_sha256": digest, "source_version": version,
                "source_snapshot_sha256": old_fingerprint,
                "source_snapshot_contract": snapshot_contract,
                "preflight_sha256": preflight_sha,
                "created_at": created_at.isoformat() if isinstance(created_at, datetime) else str(created_at),
                "source_context_state": ("current_unreviewed_question" if current
                                         else "source_reassessment_required"),
                "human_review_state": "not_submitted",
                "clinical_approval": False, "model_executed": False,
            })
        return results

    def list(self, patient_id: str, case_id: str, *, organization: str,
             actor: str, purpose: str, recheck_authority: Callable[[], None],
             prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        if purpose != "operations":
            raise PatientRegistryDenied("Question intake unavailable")
        def prepare(index):
            results = self.project_locked(
                patient_id, case_id, organization=organization, source_index=index,
            )
            result = {
                "contract": QUESTION_LIST_CONTRACT,
                "patient_id": patient_id, "case_id": case_id,
                "access_receipt_id": index["access_receipt_id"],
                "questions": results, "synthetic": True,
                "clinical_review_connected": False, "clinical_approval": False,
            }
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=prepare, recheck_authority=recheck_authority,
            )
