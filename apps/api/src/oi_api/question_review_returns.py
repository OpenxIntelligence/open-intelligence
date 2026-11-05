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

from .attribution_reassessment import compare_versions
from .case_bindings import _case_id
from .composer_preflight import SHA256, SOURCE_SNAPSHOT_CONTRACT
from .source_questions import LEGACY_SNAPSHOT_CONTRACT, PostgresSourceQuestions
from .source_world_model import project_source_world_model
from .sources import PostgresSourceVersions

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


def _return_intent(patient_id, case_id, question_id, organization, actor, purpose,
                   request_key, fingerprint, reason, comparison_source):
    intent = {
        "patient_id": patient_id, "case_id": case_id, "question_id": question_id,
        "organization": organization, "actor": actor, "purpose": purpose,
        "request_key": request_key, "queue_fingerprint": fingerprint,
        "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
        "queue_fingerprint_contract": FINGERPRINT_CONTRACT, "reason": reason, "action": ACTION,
    }
    if comparison_source is not None:
        intent["comparison_source"] = comparison_source
    return _digest(intent)


def attribution_comparison(observations: list[dict], question: dict, peer: dict) -> dict:
    """Resolve two explicitly selected passages from the already verified current snapshot."""
    by_line = {(o["source_id"], o["source_line"]): o for o in observations}
    first = by_line.get((question["source_id"], question["source_line"]))
    second = by_line.get((peer["source_id"], peer["source_line"]))
    if first and second:
        a, b = first.get("oncology"), second.get("oncology")
        if (a and b and a["role"] == b["role"] == "metastasis"
                and a["episode_id"] != b["episode_id"]
                and first["document_id"] != second["document_id"]
                and first["specimen_id"] is not None
                and all(first[key] == second[key] for key in ("specimen_id", "event_date", "finding_key"))):
            return second
    raise PatientRegistryConflict("The selected reports cannot be compared for episode attribution")


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
            "source_snapshot_contract,queue_fingerprint_contract,request_key,intent_sha256 "
            "FROM investigation.question_review_receipts "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s "
            "ORDER BY created_at,receipt_id LIMIT 751",
            (patient_id, case_id, organization),
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
        self._attach_comparison_sources(patient_id, case_id, organization, source_index, receipt_rows, receipts)
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

    def _attach_comparison_sources(self, patient_id, case_id, organization, source_index, receipt_rows, receipts):
        # A return and its journal entry commit together. Only the second exact
        # anchor is added to the existing event. Original bytes stay with Sources.
        comparison_events = self.registry._fetchall(
            "SELECT metadata_json FROM identity.identity_domain_events WHERE patient_id=%s "
            "AND event_type='investigation.review.returned_for_verification' "
            "AND metadata_json->>'case_id'=%s AND metadata_json ? 'comparison_source_id' "
            "ORDER BY id LIMIT 751", (patient_id, case_id),
        )
        if len(comparison_events) > MAX_RECEIPTS:
            raise PatientRegistryError("Comparison history exceeds the receipt bound")
        sources = {s["source_id"]: s for s in source_index["sources"]}
        events = {e["receipt_id"]: e for (e,) in comparison_events}
        if len(events) != len(comparison_events):
            raise PatientRegistryError("Duplicate comparison return event")
        for receipt, row in zip(receipts, receipt_rows):
            event = events.pop(receipt["receipt_id"], None)
            peer = None
            if event is not None:
                source = sources.get(event.get("comparison_source_id"))
                line = event.get("comparison_source_line")
                if (source is None or type(line) is not int or not 1 <= line <= 10000
                        or event.get("comparison_source_sha256") != source["sha256"]
                        or event.get("question_id") != receipt["question_id"]
                        or event.get("queue_fingerprint") != receipt["queue_fingerprint"]
                        or event.get("source_snapshot_sha256") != receipt["source_snapshot_sha256"]
                        or event.get("actor") != receipt["actor_label"]):
                    raise PatientRegistryError("Comparison return provenance mismatch")
                peer = {"source_id": source["source_id"], "source_line": line}
                receipt["comparison_source"] = {
                    **peer, "source_sha256": source["sha256"], "document_id": source["document_id"],
                    "source_version": source["version"],
                }
            if receipt["source_snapshot_contract"] == SOURCE_SNAPSHOT_CONTRACT:
                expected = _return_intent(patient_id, case_id, receipt["question_id"], organization,
                                          receipt["actor_label"], "operations", row[12],
                                          receipt["queue_fingerprint"], receipt["reason"], peer)
                if not hmac.compare_digest(row[13], expected):
                    raise PatientRegistryError("Stored review intent does not match its source references")
            elif peer is not None:
                raise PatientRegistryError("Legacy return cannot carry a paired attribution")
        if events:
            raise PatientRegistryError("Comparison event has no matching return")

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

    def compare_attributions(self, patient_id: str, case_id: str, receipt_id: str, *, organization: str,
                             actor: str, purpose: str, recheck_authority: Callable[[], None],
                             prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        if purpose != "operations":
            raise PatientRegistryDenied("Attribution review unavailable")
        sources = PostgresSourceVersions(self.registry)
        scope = dict(organization=organization, actor=actor, purpose=purpose, recheck_authority=recheck_authority)

        def prepare(index):
            questions, receipts = self._read_locked(patient_id, case_id, organization, index)
            receipt = next((r for r in receipts if r["receipt_id"] == receipt_id), None)
            if receipt is None or "comparison_source" not in receipt:
                raise PatientRegistryDenied("Attribution review unavailable")
            question = next(q for q in questions if q["question_id"] == receipt["question_id"])
            current = {s["document_id"]: s for s in index["sources"] if s["state"] == "current"}

            def side(anchor):
                original = sources.original_locked(patient_id, case_id, anchor["source_id"], **scope)
                latest = current.get(original["document_id"])
                if latest is None:
                    raise PatientRegistryError("Current document version unavailable")
                return (compare_versions(anchor, original, latest, index["source_reported_assertions"]),
                        original["access_receipt_id"])

            first, first_access = side(question)
            second, second_access = side(receipt["comparison_source"])
            self.registry.append_event(
                patient_id, "investigation.review.attribution_compared", case_id=case_id,
                question_id=question["question_id"], review_receipt_id=receipt_id, actor=actor,
                source_access_receipt_id=index["access_receipt_id"], first_original_access_id=first_access,
                second_original_access_id=second_access, first_latest_source_id=first["latest"]["source_id"],
                second_latest_source_id=second["latest"]["source_id"],
            )
            packet = {"contract": "oi.synthetic-attribution-reassessment/1", "synthetic": True,
                      "clinical_approval": False, "patient_id": patient_id, "case_id": case_id,
                      "receipt_id": receipt_id, "question_id": question["question_id"],
                      "access_receipt_id": index["access_receipt_id"],
                      "first": first, "second": second}
            return prepare_response(packet) if prepare_response else packet

        with self.registry.transaction():
            return sources.list_locked(patient_id, case_id, **scope, prepare_response=prepare)

    def return_for_verification(self, patient_id: str, case_id: str, question_id: str, *,
                                organization: str, actor: str, purpose: str,
                                request_key: str, expected_queue_fingerprint: str, reason: str,
                                comparison_source: dict | None = None,
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
        intent = _return_intent(patient_id, case_id, question_id, organization, actor, purpose,
                                request_key, expected_queue_fingerprint, reason, comparison_source)

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
            comparison_event = {}
            if comparison_source is not None:
                peer = attribution_comparison(project_source_world_model(index)["observations"], item, comparison_source)
                comparison_event = {"comparison_source_id": peer["source_id"],
                                    "comparison_source_line": peer["source_line"],
                                    "comparison_source_sha256": peer["source_sha256"]}
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
                queue_fingerprint_contract=FINGERPRINT_CONTRACT, actor=actor, **comparison_event,
            )
            return response(receipt_id, False)

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=save, recheck_authority=recheck_authority,
            )
