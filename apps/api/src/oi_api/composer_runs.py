"""PostgreSQL Composer execution: immutable intent and fenced bounded attempts.

The only executable kind is the existing synthetic source-question brief.
Credentials are supplied independently at execution time and never persisted.
"""
from __future__ import annotations

from collections.abc import Callable
import hashlib
import hmac
import json
import re
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .composer_run_contracts import ComposerRunResult, ComposerRunStatus, EnqueueComposerRun
from .source_question_contracts import SourceQuestionBrief
from .source_questions import PostgresSourceQuestions
from .source_event_delivery import EventLeaseLost, PostgresSourceEventDelivery

KIND = "source-question-brief/1"
ACTIONS = ("patient_read", "question_read", "source_read", "source_brief_export")
TERMINAL = frozenset({"completed", "blocked", "stale", "cancelled", "failed"})
RUN_FIELDS = (
    "run_id", "patient_id", "case_id", "question_id", "origin_org", "actor", "purpose",
    "kind", "source_snapshot_contract", "source_snapshot_sha256", "preflight_sha256",
    "source_id", "source_version", "source_sha256", "source_line", "request_key",
    "request_digest", "state", "revision", "attempt_count", "max_attempts", "lease_token",
    "lease_expires_at", "available_at", "created_at", "updated_at",
)
SELECT_RUN = (
    "SELECT " + ",".join("r." + name for name in RUN_FIELDS)
    + ",(SELECT result_sha256 FROM investigation.composer_tool_run_results z WHERE z.run_id=r.run_id),"
      "COALESCE(r.lease_expires_at>clock_timestamp(),false) "
      "FROM investigation.composer_tool_runs r "
)


class RunLeaseLost(PatientRegistryConflict):
    """The lease expired, was cancelled or was replaced; no result was accepted."""


def canonical_result(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


class PostgresComposerRuns:
    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry
        self.questions = PostgresSourceQuestions(registry)

    def source_events(self) -> PostgresSourceEventDelivery:
        """Compose the platform transport with this owner's explicit commands."""
        return PostgresSourceEventDelivery(
            self.registry, authorize_scope_locked=self.questions.authorize_run_scope_locked,
            consume_locked=self.consume_source_event_locked,
            receipt_locked=self.source_event_receipt_locked)

    def source_event_receipt_locked(self, claim: dict) -> dict | None:
        """Read one attempt's immutable receipt after transport scope checking."""
        if not self.registry._transaction_active:
            raise PatientRegistryError("Source event receipt requires caller transaction")
        row = self.registry._fetchone(
            "SELECT event_id,claim_token,invalidated_count,has_more "
            "FROM investigation.composer_source_event_receipts "
            "WHERE delivery_id=%s AND attempt_count=%s",
            (claim["delivery_id"], claim["attempt_count"]))
        if row is None:
            return None
        if (row[0] != claim["event_id"] or type(claim.get("lease_token")) is not str
                or not hmac.compare_digest(row[1], claim["lease_token"])):
            raise EventLeaseLost("Source event receipt does not match this claim")
        return {"status": "queued" if row[3] else "delivered", "invalidated_count": row[2]}

    def consume_source_event_locked(self, delivery: dict, *, recheck_authority: Callable[[], None]) -> dict:
        """Reconcile at most 100 outdated pending runs and persist one receipt.

        An event wakes current-context reconciliation; it is not evidence that
        this particular historical import caused every change. Original run
        pins are immutable and were validated at enqueue. Comparing the whole
        current snapshot covers changes outside the selected source as well.
        """
        if not self.registry._transaction_active:
            raise PatientRegistryError("Source event consumption requires caller transaction")

        def reconcile(context):
            rows = self.registry._fetchall(
                SELECT_RUN + "WHERE r.patient_id=%s AND r.case_id=%s AND r.origin_org=%s "
                "AND r.actor=%s AND r.purpose=%s AND r.state IN ('queued','running') "
                "AND (r.source_snapshot_contract<>%s OR r.source_snapshot_sha256<>%s) "
                "ORDER BY r.created_at,r.run_id LIMIT 101 FOR UPDATE OF r",
                (delivery["patient_id"], delivery["case_id"], delivery["origin_org"],
                 delivery["actor"], delivery["purpose"], context["source_snapshot_contract"],
                 context["source_snapshot_sha256"]))
            batch, has_more = rows[:100], len(rows) > 100
            for row in batch:
                self._transition(self._unpack(row), "stale", "source_changed", source_event=delivery)
            self.registry._execute(
                "INSERT INTO investigation.composer_source_event_receipts "
                "(delivery_id,attempt_count,event_id,claim_token,source_snapshot_contract,"
                "source_snapshot_sha256,invalidated_count,has_more) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (delivery["delivery_id"], delivery["attempt_count"], delivery["event_id"],
                 delivery["lease_token"], context["source_snapshot_contract"],
                 context["source_snapshot_sha256"], len(batch), has_more))
            self.registry.append_event(
                delivery["patient_id"], "composer.source_event.reconciled",
                case_id=delivery["case_id"], actor=delivery["actor"], purpose=delivery["purpose"],
                delivery_id=delivery["delivery_id"], source_event_id=delivery["event_id"],
                attempt_count=delivery["attempt_count"], invalidated_count=len(batch),
                has_more=has_more, source_snapshot_sha256=context["source_snapshot_sha256"])
            return {"status": "queued" if has_more else "delivered", "invalidated_count": len(batch)}

        return self.questions.prepare_run_context_locked(
            delivery["patient_id"], delivery["case_id"], organization=delivery["origin_org"],
            actor=delivery["actor"], purpose=delivery["purpose"],
            recheck_authority=recheck_authority, prepare_response=reconcile)

    @staticmethod
    def _unpack(row):
        return dict(zip((*RUN_FIELDS, "result_sha256", "lease_current"), row)) if row else None

    @staticmethod
    def _identifier(value, prefix):
        if type(value) is not str or re.fullmatch(prefix + r"-[0-9A-F]{32}", value) is None:
            raise PatientRegistryDenied("Composer run unavailable")
        return value

    def _scope(self, patient_id, case_id, organization, actor, purpose, recheck_authority):
        recheck_authority()
        self.questions.authorize_run_scope_locked(
            patient_id, case_id, organization=organization, actor=actor, purpose=purpose)

    def _load(self, patient_id, case_id, question_id, run_id, organization, actor, purpose, *, lock=False):
        self._identifier(question_id, "QUESTION")
        self._identifier(run_id, "RUN")
        row = self.registry._fetchone(
            SELECT_RUN + "WHERE r.patient_id=%s AND r.case_id=%s AND r.question_id=%s AND r.run_id=%s "
            "AND r.origin_org=%s AND r.actor=%s AND r.purpose=%s" + (" FOR UPDATE OF r" if lock else ""),
            (patient_id, case_id, question_id, run_id, organization, actor, purpose))
        if row is None:
            raise PatientRegistryDenied("Composer run unavailable")
        return self._unpack(row)

    def _reload(self, row, *, lock=False):
        return self._load(row["patient_id"], row["case_id"], row["question_id"], row["run_id"],
                          row["origin_org"], row["actor"], row["purpose"], lock=lock)

    @staticmethod
    def _status(row):
        fields = (
            "run_id", "patient_id", "case_id", "question_id", "kind", "state", "revision",
            "attempt_count", "max_attempts", "source_snapshot_contract", "source_snapshot_sha256",
            "preflight_sha256", "created_at", "updated_at", "available_at", "lease_expires_at",
            "result_sha256",
        )
        return ComposerRunStatus(**{key: row[key] for key in fields}).model_dump(mode="json")

    def _event(self, row, reason_code, *, source_event=None):
        self.registry._execute(
            "INSERT INTO investigation.composer_tool_run_events "
            "(run_id,revision,state,attempt_count,reason_code) VALUES (%s,%s,%s,%s,%s)",
            (row["run_id"], row["revision"], row["state"], row["attempt_count"], reason_code))
        self.registry.append_event(
            row["patient_id"], "composer.run." + row["state"], run_id=row["run_id"],
            case_id=row["case_id"], question_id=row["question_id"], capability=KIND,
            actor=row["actor"], purpose=row["purpose"], revision=row["revision"],
            attempt_count=row["attempt_count"], reason_code=reason_code,
            **({"source_event_id": source_event["event_id"],
                "delivery_id": source_event["delivery_id"],
                "delivery_attempt": source_event["attempt_count"]} if source_event else {}))

    def _transition(self, row, state, reason_code, *, delay=0, source_event=None):
        self.registry._execute(
            "UPDATE investigation.composer_tool_runs SET state=%s,revision=revision+1,"
            "lease_token=NULL,lease_expires_at=NULL,updated_at=clock_timestamp(),"
            "available_at=clock_timestamp()+(%s * interval '1 second') WHERE run_id=%s",
            (state, delay, row["run_id"]))
        current = self._reload(row)
        self._event(current, reason_code, source_event=source_event)
        return current

    @staticmethod
    def _prepared(result, prepare_response):
        return prepare_response(result) if prepare_response is not None else result

    def enqueue(self, patient_id: str, case_id: str, question_id: str, *,
                organization: str, actor: str, purpose: str, request_key: str,
                source_snapshot_contract: str, expected_source_snapshot_sha256: str,
                expected_preflight_sha256: str, recheck_authority: Callable[[], None],
                prepare_response=None):
        request = EnqueueComposerRun(
            synthetic=True, request_key=request_key, source_snapshot_contract=source_snapshot_contract,
            expected_source_snapshot_sha256=expected_source_snapshot_sha256,
            expected_preflight_sha256=expected_preflight_sha256)
        self._identifier(question_id, "QUESTION")
        intent = dict(patient_id=patient_id, case_id=case_id, question_id=question_id,
                      origin_org=organization, actor=actor, purpose=purpose, kind=KIND,
                      **request.model_dump(exclude={"synthetic"}))
        digest = hashlib.sha256(canonical_result(intent)).hexdigest()

        # A committed intent is recoverable even after its inputs become stale.
        # Return only its bounded receipt under CURRENT scope/authority; fresh
        # source validation still governs every genuinely new run and result.
        with self.registry.transaction():
            self._scope(patient_id, case_id, organization, actor, purpose, recheck_authority)
            old = self.registry._fetchone(
                "SELECT run_id,request_digest FROM investigation.composer_tool_runs "
                "WHERE origin_org=%s AND actor=%s AND purpose=%s AND request_key=%s",
                (organization, actor, purpose, request_key))
            if old is not None:
                if not hmac.compare_digest(old[1], digest):
                    raise PatientRegistryConflict("Execution request key reused with changed intent")
                row = self._load(patient_id, case_id, question_id, old[0], organization, actor, purpose)
                result = self._prepared({"run": self._status(row), "duplicate": True}, prepare_response)
                recheck_authority()
                self.registry.append_event(patient_id, "composer.run.read_authorized", run_id=old[0],
                                           case_id=case_id, actor=actor, purpose=purpose)
                recheck_authority()
                return result

        def queue(brief):
            validated = SourceQuestionBrief(**brief)
            recheck_authority()
            selected = validated.selected_source
            run_id = "RUN-" + uuid.uuid4().hex.upper()
            inserted = self.registry._fetchone(
                "INSERT INTO investigation.composer_tool_runs "
                "(run_id,patient_id,case_id,question_id,origin_org,actor,purpose,kind,"
                "source_snapshot_contract,source_snapshot_sha256,preflight_sha256,source_id,"
                "source_version,source_sha256,source_line,request_key,request_digest) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (origin_org,actor,purpose,request_key) DO NOTHING RETURNING run_id",
                (run_id, patient_id, case_id, question_id, organization, actor, purpose, KIND,
                 source_snapshot_contract, expected_source_snapshot_sha256, expected_preflight_sha256,
                 selected.source_id, selected.version, selected.sha256, selected.line, request_key, digest))
            if inserted is None:
                old = self.registry._fetchone(
                    "SELECT run_id,request_digest FROM investigation.composer_tool_runs "
                    "WHERE origin_org=%s AND actor=%s AND purpose=%s AND request_key=%s",
                    (organization, actor, purpose, request_key))
                if old is None or not hmac.compare_digest(old[1], digest):
                    raise PatientRegistryConflict("Execution request key reused with changed intent")
                run_id = old[0]
            row = self._load(patient_id, case_id, question_id, run_id, organization, actor, purpose)
            if inserted:
                self._event(row, "queued")
            result = self._prepared({"run": self._status(row), "duplicate": inserted is None}, prepare_response)
            recheck_authority()
            return result

        return self.questions.prepare_brief(
            patient_id, case_id, question_id, organization=organization, actor=actor, purpose=purpose,
            source_snapshot_contract=source_snapshot_contract,
            expected_source_snapshot_sha256=expected_source_snapshot_sha256,
            expected_preflight_sha256=expected_preflight_sha256,
            recheck_authority=recheck_authority, prepare_response=queue)

    def _inspect(self, patient_id, case_id, question_id, run_id, *, organization, actor, purpose,
                 recheck_authority, prepare_response=None, cancel=False, private=False):
        with self.registry.transaction():
            self._scope(patient_id, case_id, organization, actor, purpose, recheck_authority)
            row = self._load(patient_id, case_id, question_id, run_id, organization, actor, purpose, lock=cancel)
            if cancel and row["state"] not in TERMINAL:
                row = self._transition(row, "cancelled", "cancelled")
            result = self._prepared(row if private else self._status(row), prepare_response)
            recheck_authority()
            if not private:
                self.registry.append_event(patient_id, "composer.run.read_authorized", run_id=run_id,
                                           case_id=case_id, actor=actor, purpose=purpose)
            recheck_authority()
            return result

    def get(self, patient_id, case_id, question_id, run_id, **kwargs):
        return self._inspect(patient_id, case_id, question_id, run_id, **kwargs)

    def cancel(self, patient_id, case_id, question_id, run_id, **kwargs):
        return self._inspect(patient_id, case_id, question_id, run_id, cancel=True, **kwargs)

    def claim_next(self, patient_id: str, case_id: str, *, organization: str, actor: str,
                   purpose: str, recheck_authority: Callable[[], None], lease_seconds: int = 30):
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise PatientRegistryError("Lease duration must be between 1 and 300 seconds")
        with self.registry.transaction():
            self._scope(patient_id, case_id, organization, actor, purpose, recheck_authority)
            row = self._unpack(self.registry._fetchone(
                SELECT_RUN + "WHERE r.patient_id=%s AND r.case_id=%s AND r.origin_org=%s "
                "AND r.actor=%s AND r.purpose=%s AND "
                "((r.state='queued' AND r.available_at<=clock_timestamp()) OR "
                "(r.state='running' AND r.lease_expires_at<=clock_timestamp())) "
                "ORDER BY r.created_at,r.run_id LIMIT 1 FOR UPDATE OF r SKIP LOCKED",
                (patient_id, case_id, organization, actor, purpose)))
            if row is None:
                recheck_authority()
                return None
            if row["attempt_count"] >= row["max_attempts"]:
                self._transition(row, "failed", "attempts_exhausted")
                recheck_authority()
                return None
            token = "LEASE-" + uuid.uuid4().hex.upper()
            self.registry._execute(
                "UPDATE investigation.composer_tool_runs SET state='running',revision=revision+1,"
                "attempt_count=attempt_count+1,lease_token=%s,"
                "lease_expires_at=clock_timestamp()+(%s * interval '1 second'),"
                "updated_at=clock_timestamp() WHERE run_id=%s", (token, lease_seconds, row["run_id"]))
            claim = self._reload(row)
            self._event(claim, "lease_recovered" if row["state"] == "running" else "claimed")
            recheck_authority()
            return claim

    def _fence(self, claim):
        row = self._reload(claim, lock=True)
        if (row["state"] != "running" or not row["lease_current"]
                or row["attempt_count"] != claim["attempt_count"]
                or not isinstance(claim.get("lease_token"), str)
                or not hmac.compare_digest(row["lease_token"], claim["lease_token"])):
            raise RunLeaseLost("Execution lease is no longer current")
        return row

    @staticmethod
    def _validate_artifact(row, brief):
        result = SourceQuestionBrief(**brief).model_dump(mode="json")
        question, selected = result["question"], result["selected_source"]
        if ((result["patient_id"], result["case_id"], question["question_id"],
             result["source_snapshot_contract"], result["source_snapshot_sha256"],
             question["preflight_sha256"], selected["source_id"], selected["version"],
             selected["sha256"], selected["line"])
                != tuple(row[k] for k in ("patient_id", "case_id", "question_id",
                         "source_snapshot_contract", "source_snapshot_sha256", "preflight_sha256",
                         "source_id", "source_version", "source_sha256", "source_line"))):
            raise PatientRegistryError("Execution result does not match its immutable intent")
        return result

    def complete(self, claim: dict, *, recheck_authority: Callable[[], None]):
        def persist(brief):
            row = self._fence(claim)
            artifact = self._validate_artifact(row, brief)
            encoded = canonical_result(artifact)
            digest = hashlib.sha256(encoded).hexdigest()
            recheck_authority()
            # The completed row and its immutable result are checked together
            # at commit, after the source owner's final authority/audit checks.
            current = self._transition(row, "completed", "completed")
            self.registry._execute(
                "INSERT INTO investigation.composer_tool_run_results (run_id,result_json,result_sha256) "
                "VALUES (%s,%s::jsonb,%s)", (row["run_id"], encoded.decode("utf-8"), digest))
            current["result_sha256"] = digest
            result = self._status(current)
            recheck_authority()
            return result

        return self.questions.prepare_brief(
            claim["patient_id"], claim["case_id"], claim["question_id"],
            organization=claim["origin_org"], actor=claim["actor"], purpose=claim["purpose"],
            source_snapshot_contract=claim["source_snapshot_contract"],
            expected_source_snapshot_sha256=claim["source_snapshot_sha256"],
            expected_preflight_sha256=claim["preflight_sha256"],
            recheck_authority=recheck_authority, prepare_response=persist)

    def finish_failure(self, claim: dict, *, reason_code: str) -> str:
        """Record only a held attempt's bounded failure, without source access.

        A live lease permits this internal bookkeeping after credential failure;
        it never permits source/result disclosure. No HTTP handler exposes it.
        """
        if reason_code not in {"source_changed", "authority_unavailable", "invalid_output", "retryable_failure"}:
            raise PatientRegistryError("Unknown bounded execution failure")
        with self.registry.transaction():
            try:
                row = self._fence(claim)
            except RunLeaseLost:
                return "fenced"
            state = {"source_changed": "stale", "authority_unavailable": "blocked",
                     "invalid_output": "failed", "retryable_failure": "queued"}[reason_code]
            if state == "queued" and row["attempt_count"] >= row["max_attempts"]:
                state, reason_code = "failed", "attempts_exhausted"
            self._transition(row, state, reason_code,
                             delay=min(2 ** row["attempt_count"], 30) if state == "queued" else 0)
            return state

    def result(self, patient_id, case_id, question_id, run_id, *, organization, actor, purpose,
               recheck_authority, prepare_response=None):
        row = self._inspect(patient_id, case_id, question_id, run_id, organization=organization,
                            actor=actor, purpose=purpose, recheck_authority=recheck_authority, private=True)
        if row["state"] != "completed":
            raise PatientRegistryConflict("Execution has no completed result")

        def disclose(current_brief):
            current = self._reload(row)
            saved = self.registry._fetchone(
                "SELECT result_json,result_sha256 FROM investigation.composer_tool_run_results WHERE run_id=%s",
                (run_id,))
            if saved is None or not hmac.compare_digest(
                    hashlib.sha256(canonical_result(saved[0])).hexdigest(), saved[1]):
                raise PatientRegistryError("Stored execution result failed integrity verification")
            artifact = self._validate_artifact(current, saved[0])
            response = ComposerRunResult(run=self._status(current),
                                        access_receipt_id=current_brief["access_receipt_id"],
                                        result_sha256=saved[1], brief=artifact).model_dump(mode="json")
            return self._prepared(response, prepare_response)

        return self.questions.prepare_brief(
            patient_id, case_id, question_id, organization=organization, actor=actor, purpose=purpose,
            source_snapshot_contract=row["source_snapshot_contract"],
            expected_source_snapshot_sha256=row["source_snapshot_sha256"],
            expected_preflight_sha256=row["preflight_sha256"],
            recheck_authority=recheck_authority, prepare_response=disclose)
