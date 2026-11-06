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

LAB_QUEUE_CONTRACT = "oi.laboratory-inspection-review-returns/1"
LAB_FINGERPRINT_CONTRACT = "oi.laboratory-inspection-review-return/1"
MAX_RECEIPTS = 750
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


def _laboratory_return_fingerprint(context):
    return _digest({"contract": LAB_FINGERPRINT_CONTRACT, **context})


def _laboratory_return_intent(context, organization, actor, purpose, command):
    return _digest({"contract": LAB_FINGERPRINT_CONTRACT,
        **{k: context[k] for k in ("patient_id", "case_id", "question_id", "snapshot_id")},
        "organization": organization, "actor": actor, "purpose": purpose, "action": ACTION, **command})


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
            "AND queue_fingerprint_contract<>%s "
            "ORDER BY created_at,receipt_id LIMIT 751",
            (patient_id, case_id, organization, LAB_FINGERPRINT_CONTRACT),
        )
        if len(receipt_rows) > MAX_RECEIPTS:
            raise PatientRegistryError("Review receipt history exceeds bounded limit")
        text_questions = {q["question_id"] for q in questions}
        if any(row[1] not in text_questions for row in receipt_rows):
            raise RuntimeError("Stored review receipt has no matching text question")
        pairs = {(SOURCE_SNAPSHOT_CONTRACT, FINGERPRINT_CONTRACT),
                 (LEGACY_SNAPSHOT_CONTRACT, LEGACY_FINGERPRINT_CONTRACT)}
        for row in receipt_rows:
            if (row[2] != patient_id or row[3] != case_id or row[7] != ACTION
                    or (row[10], row[11]) not in pairs):
                raise PatientRegistryError("Review history scope/provenance integrity mismatch")
        receipts = [{
            "receipt_id": r[0], "question_id": r[1],
            "queue_fingerprint": r[4], "source_snapshot_sha256": r[5],
            "actor_label": r[6], "action": r[7], "reason": r[8],
            "created_at": r[9].isoformat() if isinstance(r[9], datetime) else str(r[9]),
            "source_snapshot_contract": r[10], "queue_fingerprint_contract": r[11],
            "reviewer_identity_verified": False, "external_notification_sent": False,
            "clinical_approval": False,
        } for r in receipt_rows]
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
                                                question["source_snapshot_sha256"])]
            state = ("source_reassessment_required" if not current else
                     "returned_for_independent_verification" if matching else
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

    def laboratory_inspection_queue(self, patient_id, case_id, question_id, snapshot_id, *,
                                    organization, actor, purpose, recheck_authority, prepare_response=None):
        return self._laboratory_inspection(
            patient_id, case_id, question_id, snapshot_id, organization=organization,
            actor=actor, purpose=purpose, recheck_authority=recheck_authority,
            prepare_response=prepare_response)

    def return_laboratory_inspection(self, patient_id, case_id, question_id, snapshot_id, *,
                                    organization, actor, purpose, request_key, expected_queue_fingerprint,
                                    expected_captured_report_sha256, expected_report_sha256, reason,
                                    recheck_authority, prepare_response=None):
        command = {"request_key": _key(request_key, "request_key"), "reason": _reason(reason),
                   "queue_fingerprint": expected_queue_fingerprint,
                   "captured_report_sha256": expected_captured_report_sha256,
                   "report_sha256": expected_report_sha256}
        if any(type(command[k]) is not str or SHA256.fullmatch(command[k]) is None
               for k in ("queue_fingerprint", "captured_report_sha256", "report_sha256")):
            raise PatientRegistryError("Exact laboratory inspection fingerprints required")
        return self._laboratory_inspection(
            patient_id, case_id, question_id, snapshot_id, organization=organization,
            actor=actor, purpose=purpose, recheck_authority=recheck_authority,
            prepare_response=prepare_response, command=command)

    def _laboratory_inspection(self, patient_id, case_id, question_id, snapshot_id, *,
                               organization, actor, purpose, recheck_authority,
                               prepare_response, command=None):
        from .laboratory_inspection_snapshots import LaboratoryInspectionSnapshots
        patient_id, case_id, question_id = _key(patient_id, "patient_id"), _case_id(case_id), _question_id(question_id)
        organization, actor = _key(organization, "organization"), _key(actor, "actor")
        if purpose != "operations":
            raise PatientRegistryDenied("Laboratory inspection review unavailable")
        action = "review_return" if command is not None else "review_queue_read"
        source_owner = PostgresSourceVersions(self.registry)
        source_signature = None
        binding_revision = None

        def authority():
            recheck_authority()
            self.registry._allow(actor, patient_id, action, purpose)
            # Case locks serialize other connections. Also detect a trusted callback
            # changing the binding or source versions within this same transaction.
            if source_signature is not None:
                if (source_owner._binding(patient_id, case_id, organization, purpose) != binding_revision
                        or _digest(source_owner._sources(case_id)) != source_signature):
                    raise PatientRegistryDenied("Laboratory review context changed")

        def render(value):
            return prepare_response(value) if prepare_response is not None else value

        def project(reopened):
            nonlocal source_signature, binding_revision
            source_signature = _digest(source_owner._sources(case_id))
            binding_revision = source_owner._binding(patient_id, case_id, organization, purpose)
            snapshot, report = reopened["snapshot"], reopened["inspection"]
            citations = report["citations"]
            anchor = citations["question_anchor"]
            context = {"patient_id": patient_id, "case_id": case_id, "question_id": question_id,
                       "snapshot_id": snapshot_id, "captured_report_sha256": snapshot["captured_report_sha256"],
                       "current_report_sha256": report["report_sha256"],
                       "source_context_state": citations["source_context_state"]}
            fingerprint = _laboratory_return_fingerprint(context)
            rows = self._laboratory_return_history(context, organization, purpose, anchor)
            if command is not None:
                intent = _laboratory_return_intent(context, organization, actor, purpose, command)
                prior = self.registry._fetchone(
                    "SELECT receipt_id,intent_sha256,question_id,queue_fingerprint_contract "
                    "FROM investigation.question_review_receipts WHERE patient_id=%s AND request_key=%s FOR UPDATE",
                    (patient_id, command["request_key"]))
                if prior is not None:
                    if (prior[2] != question_id or prior[3] != LAB_FINGERPRINT_CONTRACT
                            or not hmac.compare_digest(prior[1], intent)
                            or not any(r["receipt_id"] == prior[0] for r in rows)):
                        raise PatientRegistryConflict("Review request key reused with changed intent")
                    return render({"receipt_id": prior[0], "question_id": question_id,
                                   "snapshot_id": snapshot_id, "duplicate": True})
                if (not hmac.compare_digest(fingerprint, command["queue_fingerprint"])
                        or not hmac.compare_digest(snapshot["captured_report_sha256"], command["captured_report_sha256"])
                        or not hmac.compare_digest(report["report_sha256"], command["report_sha256"])):
                    raise PatientRegistryConflict("Saved inspection changed; reopen before returning")
                count, = self.registry._fetchone(
                    "SELECT count(*) FROM investigation.question_review_receipts "
                    "WHERE patient_id=%s AND case_id=%s AND origin_org=%s", (patient_id, case_id, organization))
                if count >= MAX_RECEIPTS or len(rows) >= 100:
                    raise PatientRegistryError("Review receipt history exceeds bounded limit")
                authority()
                receipt_id = "REVIEW-" + uuid.uuid4().hex.upper()
                self.registry._execute(
                    "INSERT INTO investigation.laboratory_review_origins "
                    "(receipt_id,snapshot_id,captured_report_sha256,report_sha256,source_context_state,source_access_receipt_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (receipt_id, snapshot_id, snapshot["captured_report_sha256"], report["report_sha256"],
                     citations["source_context_state"], citations["source_access_receipt_id"]))
                inserted = self.registry._fetchone(
                    "INSERT INTO investigation.question_review_receipts "
                    "(receipt_id,question_id,patient_id,case_id,origin_org,request_key,intent_sha256,"
                    "queue_fingerprint,source_snapshot_sha256,actor,purpose,action,reason,"
                    "source_snapshot_contract,queue_fingerprint_contract) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'returned',%s,%s,%s) "
                    "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING receipt_id",
                    (receipt_id, question_id, patient_id, case_id, organization, command["request_key"], intent,
                     fingerprint, anchor["source_snapshot_sha256"], actor, purpose, command["reason"],
                     SOURCE_SNAPSHOT_CONTRACT, LAB_FINGERPRINT_CONTRACT))
                if inserted is None:
                    # Same-case commands serialize on the existing source lock.
                    # A winner from a different case necessarily has different intent.
                    raise PatientRegistryConflict("Review request key belongs to different intent")
                self.registry.append_event(patient_id, "investigation.review.returned_for_verification",
                    case_id=case_id, question_id=question_id, receipt_id=receipt_id, actor=actor,
                    snapshot_id=snapshot_id, captured_report_sha256=snapshot["captured_report_sha256"],
                    report_sha256=report["report_sha256"], source_context_state=citations["source_context_state"],
                    queue_fingerprint=fingerprint, queue_fingerprint_contract=LAB_FINGERPRINT_CONTRACT,
                    source_snapshot_sha256=anchor["source_snapshot_sha256"],
                    source_snapshot_contract=SOURCE_SNAPSHOT_CONTRACT)
                return render({"receipt_id": receipt_id, "question_id": question_id,
                               "snapshot_id": snapshot_id, "duplicate": False})
            matching = [r for r in rows if hmac.compare_digest(r["queue_fingerprint"], fingerprint)]
            state = ("source_reassessment_required" if context["source_context_state"] == "source_reassessment_required"
                     else "returned_for_independent_verification" if matching else "awaiting_independent_verification")
            return render({**context, "contract": LAB_QUEUE_CONTRACT, "queue_fingerprint": fingerprint,
                "source_access_receipt_id": citations["source_access_receipt_id"], "review_state": state,
                "current_return_receipt_id": matching[-1]["receipt_id"] if matching else None,
                "return_count": len(matching), "prior_return_count": len(rows) - len(matching), "receipts": rows,
                "synthetic": True, "clinical_approval": False, "reviewer_identity_verified": False,
                "external_notification_sent": False})

        return LaboratoryInspectionSnapshots(self.registry).read(
            patient_id, case_id, question_id, snapshot_id=snapshot_id, organization=organization,
            actor=actor, purpose=purpose, recheck_authority=authority, prepare_response=project)

    def _laboratory_return_history(self, context, organization, purpose, anchor):
        fields = ("receipt_id", "question_id", "patient_id", "case_id", "origin_org", "request_key", "intent_sha256",
                  "queue_fingerprint", "source_snapshot_sha256", "actor", "purpose", "action", "reason", "created_at",
                  "source_snapshot_contract", "queue_fingerprint_contract")
        origins = ("snapshot_id", "captured_report_sha256", "report_sha256", "source_context_state", "source_access_receipt_id")
        rows = self.registry._fetchall(
            "SELECT " + ",".join("r." + f for f in fields) + "," + ",".join("o." + f for f in origins) +
            " FROM investigation.question_review_receipts r JOIN investigation.laboratory_review_origins o USING(receipt_id) "
            "WHERE r.patient_id=%s AND r.case_id=%s AND r.question_id=%s AND r.origin_org=%s AND o.snapshot_id=%s "
            "ORDER BY r.created_at,r.receipt_id LIMIT 101",
            (context["patient_id"], context["case_id"], context["question_id"], organization, context["snapshot_id"]))
        if len(rows) > 100:
            raise PatientRegistryError("Review receipt history exceeds bounded limit")
        result = []
        for raw in rows:
            row = dict(zip((*fields, *origins), raw))
            command = {k: row[k] for k in ("request_key", "reason", "queue_fingerprint", "captured_report_sha256", "report_sha256")}
            saved_context = {**context, "current_report_sha256": row["report_sha256"],
                             "source_context_state": row["source_context_state"]}
            if (row["purpose"] != purpose or row["action"] != ACTION
                    or row["source_snapshot_contract"] != SOURCE_SNAPSHOT_CONTRACT
                    or row["queue_fingerprint_contract"] != LAB_FINGERPRINT_CONTRACT
                    or row["source_snapshot_sha256"] != anchor["source_snapshot_sha256"]
                    or row["captured_report_sha256"] != context["captured_report_sha256"]
                    or row["queue_fingerprint"] != _laboratory_return_fingerprint(saved_context)
                    or row["intent_sha256"] != _laboratory_return_intent(context, organization, row["actor"], purpose, command)):
                raise PatientRegistryError("Laboratory review history provenance is inconsistent")
            result.append({**{k: row[k] for k in ("receipt_id", "question_id", *origins[:-1], "queue_fingerprint", "action", "reason")},
                "actor_label": row["actor"], "created_at": row["created_at"].isoformat(), "clinical_approval": False,
                "reviewer_identity_verified": False, "external_notification_sent": False})
        return result
