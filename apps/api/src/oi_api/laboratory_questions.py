"""Durable, unreviewed questions anchored to observations in fictional FHIR originals."""
from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .composer_preflight import SHA256, SOURCE_SNAPSHOT_CONTRACT, prepare_laboratory_question
from .laboratory_fhir_store import PostgresLaboratoryFHIR
from .source_questions import PreparedResponse, _request_key
from .source_world_model import project_source_world_model
from .sources import PostgresSourceVersions, _source_id


MAX_LABORATORY_QUESTIONS = 250


def _intent(patient_id, case_id, organization, actor, purpose, request_key, source_id,
            observation_reference, question, snapshot, preflight):
    return _digest({
        "anchor_kind": "fhir_observation", "patient": patient_id, "case": case_id,
        "organization": organization, "actor": actor, "purpose": purpose, "request_key": request_key,
        "source_id": source_id, "observation_reference": observation_reference,
        "question": question, "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
        "source_snapshot_sha256": snapshot, "preflight_sha256": preflight,
    })


class PostgresLaboratoryQuestions:
    """The existing question ledger owns identity; its typed child owns only the anchor."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def _bound(self, patient_id, case_id, organization, actor, purpose, actions, prepare, recheck):
        if purpose != "operations":
            raise PatientRegistryDenied("Laboratory questions unavailable")
        with self.registry.transaction():
            for action in actions:
                self.registry._allow(actor, patient_id, action, purpose)
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                prepare_response=prepare, recheck_authority=recheck,
            )

    def save(self, patient_id: str, case_id: str, *, organization: str, actor: str, purpose: str,
             request_key: str, source_id: str, observation_reference: str, question: str,
             expected_source_snapshot_sha256: str, expected_preflight_sha256: str,
             recheck_authority: Callable[[], None],
             prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        patient_id, case_id = _key(patient_id, "patient_id"), _case_id(case_id)
        organization, actor = _key(organization, "organization"), _key(actor, "actor")
        source_id, request_key = _source_id(source_id), _request_key(request_key)
        if any(type(value) is not str or not SHA256.fullmatch(value) for value in
               (expected_source_snapshot_sha256, expected_preflight_sha256)):
            raise PatientRegistryError("Laboratory question requires SHA-256 fingerprints")
        intent = _intent(patient_id, case_id, organization, actor, purpose, request_key, source_id,
                         observation_reference, question, expected_source_snapshot_sha256,
                         expected_preflight_sha256)

        def response(qid, duplicate):
            result = {"question_id": qid, "duplicate": duplicate}
            return prepare_response(result) if prepare_response else result

        def existing():
            return self.registry._fetchone(
                "SELECT q.question_id,q.intent_sha256,q.source_snapshot_contract,q.source_line,"
                "q.source_id,a.source_id,a.observation_reference FROM investigation.source_questions q "
                "LEFT JOIN investigation.laboratory_question_anchors a ON a.question_id=q.question_id "
                "WHERE q.patient_id=%s AND q.request_key=%s FOR UPDATE OF q",
                (patient_id, request_key),
            )

        def replay(row):
            if (row is None or tuple(row[2:]) != (SOURCE_SNAPSHOT_CONTRACT, None, source_id,
                                                  source_id, observation_reference)
                    or not hmac.compare_digest(row[1], intent)):
                raise PatientRegistryConflict("Question request key reused with changed intent")
            # An authorized exact retry of a committed write retains the old
            # question identity even when its original is no longer current.
            return response(row[0], True)

        def write(index):
            old = existing()
            if old is not None:
                return replay(old)
            # The source owner holds the case lock through commit, so distinct
            # keys cannot concurrently overfill history. Exact retries precede
            # this check and remain recoverable at capacity.
            total, = self.registry._fetchone(
                "SELECT count(*) FROM investigation.source_questions WHERE patient_id=%s AND case_id=%s "
                "AND origin_org=%s AND purpose=%s AND source_line IS NULL",
                (patient_id, case_id, organization, purpose),
            )
            if total >= MAX_LABORATORY_QUESTIONS:
                raise PatientRegistryConflict("Laboratory question history has reached capacity")
            observations = PostgresLaboratoryFHIR(self.registry).current_observations_locked(case_id)
            prepared = prepare_laboratory_question(
                index, observations, patient_id=patient_id, case_id=case_id, source_id=source_id,
                observation_reference=observation_reference, question=question,
                expected_source_snapshot_sha256=expected_source_snapshot_sha256,
            )
            if not hmac.compare_digest(expected_preflight_sha256, prepared["preflight_sha256"]):
                raise PatientRegistryConflict("Laboratory preflight changed before question write")
            recheck_authority()
            selected = prepared["selected_source"]
            qid = "QUESTION-" + uuid.uuid4().hex.upper()
            inserted = self.registry._fetchone(
                "INSERT INTO investigation.source_questions "
                "(question_id,patient_id,case_id,origin_org,request_key,intent_sha256,actor,purpose,"
                "question,source_id,source_line,source_sha256,source_version,source_snapshot_sha256,"
                "preflight_sha256,source_snapshot_contract) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s,%s) "
                "ON CONFLICT (patient_id,request_key) DO NOTHING RETURNING question_id",
                (qid, patient_id, case_id, organization, request_key, intent, actor, purpose,
                 question, source_id, selected["sha256"], selected["version"],
                 expected_source_snapshot_sha256, expected_preflight_sha256, SOURCE_SNAPSHOT_CONTRACT),
            )
            if inserted is None:
                return replay(existing())
            self.registry._execute(
                "INSERT INTO investigation.laboratory_question_anchors "
                "(question_id,source_id,observation_reference) VALUES (%s,%s,%s)",
                (qid, source_id, observation_reference),
            )
            self.registry.append_event(
                patient_id, "investigation.question.created", question_id=qid,
                case_id=case_id, source_id=source_id, observation_reference=observation_reference,
                source_snapshot_sha256=expected_source_snapshot_sha256,
                source_snapshot_contract=SOURCE_SNAPSHOT_CONTRACT, actor=actor,
            )
            return response(qid, False)

        return self._bound(patient_id, case_id, organization, actor, purpose,
                           ("patient_read", "source_read", "composer_context_read", "question_create"),
                           write, recheck_authority)

    def project_locked(self, patient_id: str, case_id: str, *, organization: str, source_index: dict) -> list[dict]:
        """Project validated typed questions under the canonical source owner's locks."""
        if not self.registry._transaction_active:
            raise PatientRegistryError("Laboratory question projection requires caller transaction")
        if (source_index.get("patient_id"), source_index.get("case_id")) != (patient_id, case_id):
            raise PatientRegistryDenied("Laboratory question context unavailable")
        index = source_index
        observations = PostgresLaboratoryFHIR(self.registry).current_observations_locked(case_id)
        world = project_source_world_model(index, observations)
        current = {(o["source_id"], o["observation_reference"]): (o["document_version"], o["source_sha256"])
                   for o in world["laboratory_observations"]}
        # Include history even if a child is damaged; fail the whole read
        # rather than silently omitting an immutable saved question.
        rows = self.registry._fetchall(
            "SELECT q.question_id,q.question,q.source_id,q.source_version,q.source_sha256,"
            "q.source_snapshot_sha256,q.preflight_sha256,q.source_snapshot_contract,"
            "q.actor,q.request_key,q.intent_sha256,a.source_id,a.observation_reference "
            "FROM investigation.source_questions q LEFT JOIN investigation.laboratory_question_anchors a "
            "ON a.question_id=q.question_id WHERE q.patient_id=%s AND q.case_id=%s "
            "AND q.origin_org=%s AND q.purpose=%s AND q.source_line IS NULL "
            "ORDER BY q.created_at,q.question_id LIMIT %s",
            (patient_id, case_id, organization, "operations", MAX_LABORATORY_QUESTIONS + 1),
        )
        if len(rows) > MAX_LABORATORY_QUESTIONS:
            raise PatientRegistryError("Laboratory question list exceeds bounded read limit")
        originals = {s["source_id"]: (s["version"], s["sha256"]) for s in index["sources"]}
        questions = []
        for qid, question, sid, version, sha, snapshot, preflight, contract, author, key, saved, anchor_sid, ref in rows:
            if (contract != SOURCE_SNAPSHOT_CONTRACT or not ref or anchor_sid != sid
                    or originals.get(sid) != (version, sha)
                    or not hmac.compare_digest(saved, _intent(patient_id, case_id, organization,
                        author, "operations", key, sid, ref, question, snapshot, preflight))):
                raise PatientRegistryError("Stored laboratory question provenance is inconsistent")
            fresh = (current.get((sid, ref)) == (version, sha)
                     and hmac.compare_digest(snapshot, world["snapshot_fingerprint"]))
            questions.append({
                "question_id": qid, "question": question, "source_id": sid, "source_version": version,
                "source_sha256": sha, "observation_reference": ref, "source_snapshot_sha256": snapshot,
                "preflight_sha256": preflight, "source_context_state": (
                    "current_unreviewed_question" if fresh else "source_reassessment_required"),
            })
        return questions

    def list(self, patient_id: str, case_id: str, *, organization: str, actor: str, purpose: str,
             recheck_authority: Callable[[], None],
             prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        patient_id, case_id = _key(patient_id, "patient_id"), _case_id(case_id)
        organization, actor = _key(organization, "organization"), _key(actor, "actor")

        def prepare(index):
            questions = self.project_locked(patient_id, case_id, organization=organization, source_index=index)
            result = {"patient_id": patient_id, "case_id": case_id,
                      "access_receipt_id": index["access_receipt_id"], "questions": questions}
            return prepare_response(result) if prepare_response else result

        return self._bound(patient_id, case_id, organization, actor, purpose,
                           ("patient_read", "source_read", "question_read"), prepare, recheck_authority)
