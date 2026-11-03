"""Canonical H1 question review inbox and nonterminal immutable return receipts.

Ports the first-party CaseStore.review_queue/add_review_receipt pattern:
inbox membership is DERIVED from the existing canonical source questions, and
only 'returned' review receipts are persisted in that same investigation owner.
No approved/reviewed/acknowledged action, second patient/evidence ledger,
clinical interpretation, external dispatch, trusted reviewer or signed review.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import hashlib
import hmac
import json
import unicodedata
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
    _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .composer_preflight import SHA256
from .world_model_read import PostgresWorldModelRead

MAX_QUESTIONS = 250
MAX_RECEIPTS = 750
KIND = "source-question"
ACTION = "returned"


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
    """Version-bound current queue item; never an authorization credential."""
    return _digest({
        "version": "oi.synthetic-source-review-return/1",
        "question_id": question["question_id"],
        "patient_id": question["patient_id"],
        "case_id": question["case_id"],
        "question": question["question"],
        "source_id": question["source_id"],
        "source_line": question["source_line"],
        "source_sha256": question["source_sha256"],
        "source_version": question["source_version"],
        "source_snapshot_sha256": question["source_snapshot_sha256"],
        "preflight_sha256": question["preflight_sha256"],
    })


class PostgresQuestionReviewReturns:
    """Nonterminal question-review receipts in the existing investigation schema."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def _read_locked(self, patient_id: str, case_id: str,
                     organization: str) -> tuple[list[dict], list[dict]]:
        # The source binding row lock serializes authoritatively with source
        # changes and case revocation, including all inserts and projections.
        world = PostgresWorldModelRead(self.registry).read_locked(
            patient_id, case_id, organization=organization
        )
        rows = self.registry._fetchall(
            "SELECT question_id,patient_id,case_id,question,source_id,"
            "source_line,source_sha256,source_version,"
            "source_snapshot_sha256,preflight_sha256,created_at "
            "FROM investigation.source_questions "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s "
            "ORDER BY created_at,question_id",
            (patient_id, case_id, organization),
        )
        if len(rows) > MAX_QUESTIONS:
            raise PatientRegistryError("Review queue exceeds bounded question limit")
        evidence = {
            (o["source_version_id"], o["source_line"]): (
                o["source_sha256"], o["document_version"])
            for o in world["observations"]
        }
        receipts_rows = self.registry._fetchall(
            "SELECT receipt_id,question_id,patient_id,case_id,"
            "queue_fingerprint,source_snapshot_sha256,"
            "actor,action,reason,created_at "
            "FROM investigation.question_review_receipts "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s "
            "ORDER BY created_at,receipt_id",
            (patient_id, case_id, organization),
        )
        if len(receipts_rows) > MAX_RECEIPTS:
            raise PatientRegistryError("Review receipt history exceeds bounded limit")
        receipts = [{
            "receipt_id": r[0], "question_id": r[1],
            "queue_fingerprint": r[4], "source_snapshot_sha256": r[5],
            "actor_label": r[6], "action": r[7], "reason": r[8],
            "created_at": r[9].isoformat() if isinstance(r[9], datetime) else str(r[9]),
            "reviewer_identity_verified": False,
            "external_notification_sent": False,
            "clinical_approval": False,
        } for r in receipts_rows]
        for r in receipts_rows:
            if r[2] != patient_id or r[3] != case_id or r[7] != ACTION:
                raise PatientRegistryError("Review history tenant/action integrity mismatch")
        by_question = {}
        for r in receipts:
            by_question.setdefault(r["question_id"], []).append(r)
        output = []
        for (qid,pid,cid,question,sid,line,digest,version,
             snapshot_sha,preflight_sha,created_at) in rows:
            current = (
                evidence.get((sid,line)) == (digest,version)
                and hmac.compare_digest(snapshot_sha, world["source_snapshot_sha256"])
            )
            anchor = {
                "question_id":qid, "patient_id":pid,"case_id":cid,
                "question":question,"source_id":sid,"source_line":line,
                "source_sha256":digest,"source_version":version,
                "source_snapshot_sha256":snapshot_sha,
                "preflight_sha256":preflight_sha,
            }
            fingerprint = _queue_fingerprint(anchor) if current else None
            prior = by_question.get(qid, [])
            matching = [r for r in prior if fingerprint is not None
                        and hmac.compare_digest(r["queue_fingerprint"],fingerprint)]
            state = ("source_reassessment_required" if not current else
                     "returned_for_independent_verification" if matching else
                     "awaiting_independent_verification")
            output.append({
                **anchor, "created_at": created_at.isoformat()
                if isinstance(created_at,datetime) else str(created_at),
                "kind":KIND, "queue_fingerprint":fingerprint,
                "source_context_state":(
                    "current_unreviewed_question" if current else
                    "source_reassessment_required"
                ),
                "review_state":state,
                "current_return_receipt_id":matching[-1]["receipt_id"] if matching else None,
                "return_count":len(matching),
                "prior_return_count":len(prior)-len(matching),
                "clinical_approval":False,"reviewer_identity_verified":False,
            })
        return output, receipts

    def queue(self, patient_id: str, case_id: str, *, organization: str,
              recheck_authority: Callable[[], None]) -> dict:
        patient_id = _key(patient_id,"patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization,"organization")
        with self.registry.transaction():
            items, receipts = self._read_locked(patient_id,case_id,organization)
            recheck_authority()
            return {
                "contract":"oi.synthetic-question-review-return-queue/1",
                "patient_id":patient_id, "case_id":case_id,"synthetic":True,
                "items":items,"receipts":receipts,
                "external_notification_sent":False,
                "reviewer_identity_verified":False,
                "clinical_approval":False,
                "review_completion_supported":False,
            }

    def return_for_verification(self,patient_id:str,case_id:str,question_id:str,*,
                                organization:str,actor:str,purpose:str,
                                request_key:str,expected_queue_fingerprint:str,
                                reason:str,
                                recheck_authority:Callable[[], None])->dict:
        patient_id = _key(patient_id,"patient_id")
        case_id = _case_id(case_id)
        question_id = _question_id(question_id)
        organization = _key(organization,"organization")
        actor = _key(actor,"actor")
        request_key = _key(request_key,"request_key")
        reason = _reason(reason)
        if purpose!="operations":
            raise PatientRegistryDenied("Review return purpose unavailable")
        if (type(expected_queue_fingerprint) is not str
                or SHA256.fullmatch(expected_queue_fingerprint) is None):
            raise PatientRegistryError("Invalid queue fingerprint")
        intent = _digest({
            "patient_id":patient_id,"case_id":case_id,
            "question_id":question_id,"organization":organization,
            "actor":actor,"purpose":purpose,"request_key":request_key,
            "queue_fingerprint":expected_queue_fingerprint,
            "reason":reason,"action":ACTION,
        })
        with self.registry.transaction():
            items, _ = self._read_locked(patient_id,case_id,organization)
            # For uncertain retries, recover the exact persisted return
            # even after the source was amended, but not after case revocation
            # or independent action/subject authorization was withdrawn.
            prior = self.registry._fetchone(
                "SELECT receipt_id,intent_sha256,question_id "
                "FROM investigation.question_review_receipts "
                "WHERE patient_id=%s AND request_key=%s FOR UPDATE",
                (patient_id,request_key),
            )
            if prior is not None:
                if (not hmac.compare_digest(prior[1],intent)
                        or prior[2]!=question_id):
                    raise PatientRegistryConflict(
                        "Review request key reused with changed intent")
                self.registry._allow(actor,patient_id,"review_return",purpose)
                recheck_authority()
                return {"receipt_id":prior[0],"question_id":question_id,"duplicate":True}
            item=next((i for i in items if i["question_id"]==question_id),None)
            if item is None:
                raise PatientRegistryDenied("Question review target unavailable")
            if item["queue_fingerprint"] is None:
                raise PatientRegistryConflict(
                    "Question source has changed; source reassessment required")
            if not hmac.compare_digest(
                expected_queue_fingerprint,item["queue_fingerprint"]
            ):
                raise PatientRegistryConflict("Review queue item changed; refresh")
            self.registry._allow(actor,patient_id,"review_return",purpose)
            recheck_authority()
            receipt_id="REVIEW-"+uuid.uuid4().hex.upper()
            inserted=self.registry._fetchone(
                "INSERT INTO investigation.question_review_receipts "
                "(receipt_id,question_id,patient_id,case_id,origin_org,"
                "request_key,intent_sha256,queue_fingerprint,"
                "source_snapshot_sha256,actor,purpose,action,reason) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'returned',%s) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING receipt_id",
                (receipt_id,question_id,patient_id,case_id,organization,
                 request_key,intent,expected_queue_fingerprint,
                 item["source_snapshot_sha256"],actor,purpose,reason),
            )
            if inserted is None:
                winner=self.registry._fetchone(
                    "SELECT receipt_id,intent_sha256,question_id "
                    "FROM investigation.question_review_receipts "
                    "WHERE patient_id=%s AND request_key=%s",
                    (patient_id,request_key),
                )
                if (winner is None or winner[2]!=question_id
                        or not hmac.compare_digest(winner[1],intent)):
                    raise PatientRegistryConflict(
                        "Review request key belongs to different intent")
                recheck_authority()
                return {"receipt_id":winner[0],"question_id":question_id,"duplicate":True}
            self.registry.append_event(
                patient_id,"investigation.review.returned_for_verification",
                case_id=case_id,question_id=question_id,receipt_id=receipt_id,
                queue_fingerprint=expected_queue_fingerprint,actor=actor,
            )
            recheck_authority()
            return {"receipt_id":receipt_id,"question_id":question_id,
                    "duplicate":False}
