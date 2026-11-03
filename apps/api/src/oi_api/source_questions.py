"""Canonical H1 question intake port of first-party CaseStore.add_question.

One PostgreSQL question owner, ONE append-only identity-domain event journal,
one clinical_source.originals owner. There is no clinical review decision or
model run here. Every write recomputes the exact Composer preflight *inside*
the original-source row-locked PostgreSQL transaction.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
    _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .composer_preflight import PostgresSourceComposerPreflight, SHA256
from .sources import PostgresSourceVersions, _source_id
from .world_model_read import PostgresWorldModelRead


def _request_key(value: str) -> str:
    return _key(value, "request_key")


class PostgresSourceQuestions:
    """Owned question-intake persistence; NOT a clinical review queue."""

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
            "preflight_sha256": preflight_sha256,
        })

    def create(self, patient_id: str, case_id: str, *, organization: str,
               actor: str, purpose: str, request_key: str,
               source_id: str, source_line: int, question: str,
               expected_source_snapshot_sha256: str,
               expected_preflight_sha256: str) -> dict:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        actor = _key(actor, "actor")
        request_key = _request_key(request_key)
        source_id = _source_id(source_id)
        if (purpose != "operations"
                or type(expected_preflight_sha256) is not str
                or not SHA256.fullmatch(expected_preflight_sha256)):
            raise PatientRegistryDenied("Question intake unavailable")
        if type(expected_source_snapshot_sha256) is not str or not SHA256.fullmatch(
            expected_source_snapshot_sha256
        ):
            raise PatientRegistryError("Source fingerprint must be SHA-256")
        # Construct the intent from only authoritative supplied arguments, not
        # a caller-supplied identity/policy and not an unverified source quote.
        intent = self._intent(
            patient_id, case_id, organization, actor, purpose, request_key,
            source_id, source_line, question, expected_source_snapshot_sha256,
            expected_preflight_sha256,
        )
        with self.registry.transaction():
            # Lock before any create/retry, including a duplicate while a
            # source change or patient/case revocation is being committed.
            PostgresSourceVersions(self.registry)._binding(
                patient_id, case_id, organization
            )
            old = self.registry._fetchone(
                "SELECT question_id,intent_sha256 FROM investigation.source_questions "
                "WHERE patient_id=%s AND request_key=%s FOR UPDATE",
                (patient_id, request_key),
            )
            if old is not None:
                if not hmac.compare_digest(old[1], intent):
                    raise PatientRegistryConflict("Question request key reused with changed intent")
                return {"question_id": old[0], "duplicate": True}

            # Exact source/binding check and original-literal quote verification
            # happen here under the *same* source lock and DB transaction as
            # the write and event. A stale preview is not allowed to persist.
            prepared = PostgresSourceComposerPreflight(
                self.registry
            ).preview_locked(
                patient_id, case_id, organization=organization,
                actor=actor, purpose=purpose,
                expected_source_snapshot_sha256=expected_source_snapshot_sha256,
                source_id=source_id, source_line=source_line, question=question,
            )
            if not hmac.compare_digest(
                prepared["preflight_sha256"], expected_preflight_sha256
            ):
                raise PatientRegistryConflict("Composer preflight changed before question write")

            # Later clinical review identity/consent is a SEPARATE gate; this
            # independently granted source-question write is operational only.
            self.registry._allow(actor, patient_id, "question_create", purpose)
            source = prepared["selected_source"]
            question_id = "QUESTION-" + uuid.uuid4().hex.upper()
            created = self.registry._fetchone(
                "INSERT INTO investigation.source_questions "
                "(question_id,patient_id,case_id,origin_org,request_key,"
                "intent_sha256,actor,purpose,question,source_id,source_line,"
                "source_sha256,source_version,source_snapshot_sha256,preflight_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING "
                "RETURNING question_id",
                (question_id, patient_id, case_id, organization, request_key,
                 intent, actor, purpose, question, source_id, source_line,
                 source["sha256"], source["version"],
                 expected_source_snapshot_sha256, expected_preflight_sha256),
            )
            if created is None:
                # Another case can race on the same request_key. The unique
                # constraint serializes the winner even across case locks.
                winner = self.registry._fetchone(
                    "SELECT question_id,intent_sha256 "
                    "FROM investigation.source_questions "
                    "WHERE patient_id=%s AND request_key=%s",
                    (patient_id, request_key),
                )
                if winner is None or not hmac.compare_digest(winner[1], intent):
                    raise PatientRegistryConflict("Question request intent changed")
                return {"question_id": winner[0], "duplicate": True}
            self.registry.append_event(
                patient_id, "investigation.question.created",
                question_id=question_id, case_id=case_id,
                source_id=source_id, source_line=source_line,
                source_snapshot_sha256=expected_source_snapshot_sha256,
                actor=actor,
            )
            return {"question_id": question_id, "duplicate": False}

    def list(self, patient_id: str, case_id: str, *, organization: str) -> list[dict]:
        patient_id = _key(patient_id, "patient_id")
        case_id = _case_id(case_id)
        organization = _key(organization, "organization")
        with self.registry.transaction():
            # Revalidate all current original-source bytes and assertion
            # links under one case lock, not a stale application cache.
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
            if len(rows) > 250:
                raise PatientRegistryError("Question list exceeds bounded read limit")
            anchors = {
                (o["source_version_id"], o["source_line"]):
                (o["source_sha256"], o["document_version"])
                for o in world["observations"]
            }
            results = []
            for (qid, pid, cid, question, sid, line, digest, version,
                 old_fingerprint, preflight_sha, created_at) in rows:
                expected = anchors.get((sid, line))
                current = (expected == (digest, version) and
                           hmac.compare_digest(
                               old_fingerprint, world["source_snapshot_sha256"]
                           ))
                results.append({
                    "question_id": qid,
                    "patient_id": pid, "case_id": cid,
                    "question": question, "source_id": sid,
                    "source_line": line, "source_sha256": digest,
                    "source_version": version,
                    "source_snapshot_sha256": old_fingerprint,
                    "preflight_sha256": preflight_sha,
                    "created_at": (created_at.isoformat()
                                   if isinstance(created_at, datetime)
                                   else str(created_at)),
                    "source_context_state": (
                        "current_unreviewed_question"
                        if current else
                        "source_reassessment_required"
                    ),
                    "human_review_state": "not_submitted",
                    "clinical_approval": False,
                    "model_executed": False,
                })
            return results
