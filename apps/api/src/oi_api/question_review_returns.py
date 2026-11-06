"""Canonical H1 question inbox and nonterminal immutable return receipts.

Preserves the first-party derived review-queue/returned-receipt owner. Source
questions supply the only freshness projection; the canonical source owner
holds its locks through prepared DTOs, final authority and durable access audit.
No signed review, clinical approval, external dispatch or evidence assessment.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import hmac
from typing import TypeVar
import unicodedata
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .composer_preflight import SHA256, SOURCE_SNAPSHOT_CONTRACT
from .source_questions import LEGACY_SNAPSHOT_CONTRACT, PostgresSourceQuestions
from .sources import PostgresSourceVersions
from .question_passages import QuestionPassages
from .followthrough_contracts import ManualTaskDependency

MAX_RECEIPTS = 750
# Only published historical migration heads may omit the 0019 Review dependency.
# Missing storage at the current head or an unknown revision is an error.
PRE_REVIEW_DEPENDENCY_REVISIONS = frozenset({
    '0007_question_review_returns', '0007_question_snapshot_contract',
    '0008_merge_image_questions', '0008_review_convergence',
    '0009_image_review_merge', '0009_question_evidence',
    '0009_question_followthrough', '0010_authored_evidence_origin',
    '0010_question_evidence', '0011_evidence_convergence',
    '0011_image_evidence_merge', '0012_image_report_convergence',
    '0012_reviewed_documents', '0013_document_image_convergence',
    '0014_question_passages', '0015_manual_report_context',
    '0016_fhir_laboratory_sources', '0016_manual_task_dependency',
    '0017_lab_manual_convergence', '0018_laboratory_questions',
})
KIND = "source-question"
ACTION = "returned"
QUEUE_CONTRACT = "oi.synthetic-question-review-return-queue/2"
FINGERPRINT_CONTRACT = "oi.synthetic-source-review-return/2"
LEGACY_FINGERPRINT_CONTRACT = "oi.synthetic-source-review-return/1"
PreparedResponse = TypeVar("PreparedResponse")


def _question_id(value: str) -> str:
    import re
    if type(value) is not str or re.fullmatch(r"QUESTION-[0-9A-F]{32}", value) is None:
        raise PatientRegistryError("Invalid question identifier")
    return value


def _reason(value: str) -> str:
    if (type(value) is not str or value != value.strip()
            or not 10 <= len(value) <= 600
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value)):
        raise PatientRegistryError("Return reason must be one visible 10-600 character line")
    return value


def _queue_fingerprint(question: dict) -> str:
    """Version-bound queue item; receipt identifiers are not content or grants."""
    return _digest({
        "version": FINGERPRINT_CONTRACT,
        "queue_fingerprint_contract": FINGERPRINT_CONTRACT,
        "question_id": question["question_id"],
        "patient_id": question["patient_id"],
        "case_id": question["case_id"],
        "question": question["question"],
        "source_id": question["source_id"],
        "source_line": question["source_line"],
        "source_sha256": question["source_sha256"],
        "source_version": question["source_version"],
        "source_snapshot_sha256": question["source_snapshot_sha256"],
        "source_snapshot_contract": question["source_snapshot_contract"],
        "preflight_sha256": question["preflight_sha256"],
    })


class PostgresQuestionReviewReturns:
    """Nonterminal question-review receipts in the existing investigation schema."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def _read_locked(self, patient_id: str, case_id: str, organization: str,
                     source_index: dict) -> tuple[list[dict], list[dict]]:
        questions = PostgresSourceQuestions(self.registry).project_locked(
            patient_id, case_id, organization=organization, source_index=source_index,
        )
        receipt_rows = self.registry._fetchall(
            "SELECT receipt_id,question_id,patient_id,case_id,"
            "queue_fingerprint,source_snapshot_sha256,actor,action,reason,created_at,"
            "source_snapshot_contract,queue_fingerprint_contract "
            "FROM investigation.question_review_receipts "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s "
            "ORDER BY created_at,receipt_id LIMIT 751",
            (patient_id, case_id, organization),
        )
        # Older migration rehearsals intentionally create Review receipts before
        # the optional 0019 child exists. Never treat a missing child on the
        # current/unknown schema as a source-only Review history.
        child = self.registry._fetchone(
            "SELECT to_regclass('investigation.question_review_manual_dependencies')")
        if child is None:
            raise PatientRegistryError("Review manual dependency schema unavailable")
        if child[0] is None:
            revisions = self.registry._fetchall(
                "SELECT version_num FROM public.alembic_version ORDER BY version_num")
            if (not 1 <= len(revisions) <= 2
                    or any(row[0] not in PRE_REVIEW_DEPENDENCY_REVISIONS
                           for row in revisions)):
                raise PatientRegistryError("Missing current Review manual dependency owner")
            manual_rows = []
        else:
            manual_rows = self.registry._fetchall(
                "SELECT receipt_id,question_id,revision_id,patient_id,case_id,"
                "origin_org,references_sha256 "
                "FROM investigation.question_review_manual_dependencies "
                "WHERE patient_id=%s AND case_id=%s AND origin_org=%s LIMIT 751",
                (patient_id, case_id, organization),
            )
        if len(receipt_rows) > MAX_RECEIPTS or len(manual_rows) > MAX_RECEIPTS:
            raise PatientRegistryError("Review receipt history exceeds bounded limit")
        manual_by_receipt = {}
        for row in manual_rows:
            dep = dict(zip(("receipt_id", "question_id", "revision_id",
                            "patient_id", "case_id", "origin_org", "references_sha256"), row))
            if dep["receipt_id"] in manual_by_receipt:
                raise PatientRegistryError("Duplicate manual Review provenance")
            manual_by_receipt[dep["receipt_id"]] = dep
        text_questions = {q["question_id"] for q in questions}
        if any(row[1] not in text_questions for row in receipt_rows):
            raise RuntimeError("Stored review receipt has no matching text question")
        pairs = {(SOURCE_SNAPSHOT_CONTRACT, FINGERPRINT_CONTRACT),
                 (LEGACY_SNAPSHOT_CONTRACT, LEGACY_FINGERPRINT_CONTRACT)}
        for row in receipt_rows:
            if (row[2] != patient_id or row[3] != case_id or row[7] != ACTION
                    or (row[10], row[11]) not in pairs):
                raise PatientRegistryError("Review history scope/provenance integrity mismatch")
        receipts = []
        for r in receipt_rows:
            stored = manual_by_receipt.pop(r[0], None)
            manual_state = None
            if stored is not None:
                if (stored["question_id"] != r[1] or stored["patient_id"] != patient_id
                        or stored["case_id"] != case_id
                        or stored["origin_org"] != organization):
                    raise PatientRegistryError("Manual Review dependency scope differs")
                scope = dict(patient_id=patient_id, case_id=case_id, question_id=r[1],
                             organization=organization, actor=r[6], purpose="operations")
                dependency = {key: stored[key] for key in (
                    "patient_id", "case_id", "question_id", "revision_id", "references_sha256")}
                manual_state = QuestionPassages(self.registry).manual_dependency_state_locked(
                    scope, dependency)
            receipts.append({
                "receipt_id": r[0], "question_id": r[1],
                "queue_fingerprint": r[4], "source_snapshot_sha256": r[5],
                "actor_label": r[6], "action": r[7], "reason": r[8],
                "created_at": r[9].isoformat() if isinstance(r[9], datetime) else str(r[9]),
                "source_snapshot_contract": r[10], "queue_fingerprint_contract": r[11],
                "manual_dependency_revision_id": (manual_state["dependency_revision_id"]
                                                  if manual_state else None),
                "manual_context_state": manual_state["state"] if manual_state else None,
                "reviewer_identity_verified": False, "external_notification_sent": False,
                "clinical_approval": False,
            })
        if manual_by_receipt:
            raise PatientRegistryError("Stored manual Review dependency has no receipt")
        by_question: dict[str, list[dict]] = {}
        for receipt in receipts:
            by_question.setdefault(receipt["question_id"], []).append(receipt)
        output = []
        for question in questions:
            current = question["source_context_state"] == "current_unreviewed_question"
            fingerprint = _queue_fingerprint(question) if current else None
            prior = by_question.get(question["question_id"], [])
            matching = [r for r in prior if fingerprint is not None
                        and r["source_snapshot_contract"] == SOURCE_SNAPSHOT_CONTRACT
                        and r["queue_fingerprint_contract"] == FINGERPRINT_CONTRACT
                        and hmac.compare_digest(r["queue_fingerprint"], fingerprint)
                        and hmac.compare_digest(r["source_snapshot_sha256"],
                                                question["source_snapshot_sha256"])
                        and r["manual_context_state"] != "reassessment_required"]
            manual_recheck = any(r["manual_context_state"] == "reassessment_required"
                                 for r in prior)
            state = ("source_reassessment_required" if not current else
                     "returned_for_independent_verification" if matching else
                     "manual_reassessment_required" if manual_recheck else
                     "awaiting_independent_verification")
            anchor = {key: question[key] for key in (
                "question_id", "patient_id", "case_id", "question", "source_id",
                "source_line", "source_sha256", "source_version", "source_snapshot_sha256",
                "source_snapshot_contract", "preflight_sha256", "created_at",
                "source_context_state",
            )}
            output.append({
                **anchor, "kind": KIND, "queue_fingerprint": fingerprint,
                "queue_fingerprint_contract": FINGERPRINT_CONTRACT,
                "review_state": state,
                "current_return_receipt_id": matching[-1]["receipt_id"] if matching else None,
                "return_count": len(matching), "prior_return_count": len(prior) - len(matching),
                "manual_reassessment_required": manual_recheck,
                "clinical_approval": False, "reviewer_identity_verified": False,
            })
        return output, receipts

    def queue(self, patient_id: str, case_id: str, *, organization: str,
              actor: str, purpose: str, recheck_authority: Callable[[], None],
              prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        if purpose != "operations":
            raise PatientRegistryDenied("Question review queue unavailable")

        def prepare(index):
            items, receipts = self._read_locked(patient_id, case_id, organization, index)
            result = {
                "contract": QUEUE_CONTRACT, "patient_id": patient_id,
                "case_id": case_id, "synthetic": True,
                "access_receipt_id": index["access_receipt_id"],
                "items": items, "receipts": receipts,
                "external_notification_sent": False, "reviewer_identity_verified": False,
                "clinical_approval": False, "review_completion_supported": False,
            }
            return prepare_response(result) if prepare_response is not None else result

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=prepare, recheck_authority=recheck_authority,
            )

    def return_for_verification(self, patient_id: str, case_id: str, question_id: str, *,
                                organization: str, actor: str, purpose: str,
                                request_key: str, expected_queue_fingerprint: str, reason: str,
                                recheck_authority: Callable[[], None],
                                prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        question_id = _question_id(question_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _key(request_key, "request_key")
        reason = _reason(reason)
        if purpose != "operations":
            raise PatientRegistryDenied("Review return purpose unavailable")
        if (type(expected_queue_fingerprint) is not str
                or SHA256.fullmatch(expected_queue_fingerprint) is None):
            raise PatientRegistryError("Invalid queue fingerprint")
        intent = _digest({
            "patient_id": patient_id, "case_id": case_id, "question_id": question_id,
            "organization": organization, "actor": actor, "purpose": purpose,
            "request_key": request_key, "queue_fingerprint": expected_queue_fingerprint,
            "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
            "queue_fingerprint_contract": FINGERPRINT_CONTRACT,
            "reason": reason, "action": ACTION,
        })

        def response(receipt_id, duplicate):
            result = {"receipt_id": receipt_id, "question_id": question_id, "duplicate": duplicate}
            return prepare_response(result) if prepare_response is not None else result

        def matching_prior(row):
            return (row is not None and row[2] == question_id
                    and row[3] == SOURCE_SNAPSHOT_CONTRACT and row[4] == FINGERPRINT_CONTRACT
                    and hmac.compare_digest(row[1], intent))

        prior_sql = (
            "SELECT receipt_id,intent_sha256,question_id,source_snapshot_contract,"
            "queue_fingerprint_contract FROM investigation.question_review_receipts "
            "WHERE patient_id=%s AND request_key=%s"
        )

        def save(index):
            items, receipts = self._read_locked(patient_id, case_id, organization, index)
            prior = self.registry._fetchone(prior_sql + " FOR UPDATE", (patient_id, request_key))
            if prior is not None:
                if not matching_prior(prior):
                    raise PatientRegistryConflict("Review request key reused with changed intent")
                # Recover the original canonical receipt after an amendment;
                # legacy keys never become canonical through a retry. The source
                # owner still performs final refreshed authorization and audit.
                self.registry._allow(actor, patient_id, "review_return", purpose)
                return response(prior[0], True)
            if len(receipts) >= MAX_RECEIPTS:
                raise PatientRegistryError("Review receipt history exceeds bounded limit")
            item = next((i for i in items if i["question_id"] == question_id), None)
            if item is None:
                raise PatientRegistryDenied("Question review target unavailable")
            if item["queue_fingerprint"] is None:
                raise PatientRegistryConflict("Question source has changed; source reassessment required")
            if not hmac.compare_digest(expected_queue_fingerprint, item["queue_fingerprint"]):
                raise PatientRegistryConflict("Review queue item changed; refresh")
            self.registry._allow(actor, patient_id, "review_return", purpose)
            recheck_authority()
            receipt_id = "REVIEW-" + uuid.uuid4().hex.upper()
            inserted = self.registry._fetchone(
                "INSERT INTO investigation.question_review_receipts "
                "(receipt_id,question_id,patient_id,case_id,origin_org,request_key,"
                "intent_sha256,queue_fingerprint,source_snapshot_sha256,actor,purpose,action,reason,"
                "source_snapshot_contract,queue_fingerprint_contract) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'returned',%s,%s,%s) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING receipt_id",
                (receipt_id, question_id, patient_id, case_id, organization, request_key,
                 intent, expected_queue_fingerprint, item["source_snapshot_sha256"],
                 actor, purpose, reason, SOURCE_SNAPSHOT_CONTRACT, FINGERPRINT_CONTRACT),
            )
            if inserted is None:
                winner = self.registry._fetchone(prior_sql, (patient_id, request_key))
                if not matching_prior(winner):
                    raise PatientRegistryConflict("Review request key belongs to different intent")
                return response(winner[0], True)
            self.registry.append_event(
                patient_id, "investigation.review.returned_for_verification",
                case_id=case_id, question_id=question_id, receipt_id=receipt_id,
                queue_fingerprint=expected_queue_fingerprint,
                source_snapshot_sha256=item["source_snapshot_sha256"],
                source_snapshot_contract=SOURCE_SNAPSHOT_CONTRACT,
                queue_fingerprint_contract=FINGERPRINT_CONTRACT, actor=actor,
            )
            return response(receipt_id, False)

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=save, recheck_authority=recheck_authority,
            )
