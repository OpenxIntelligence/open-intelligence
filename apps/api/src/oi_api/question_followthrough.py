"""Canonical question follow-through: immutable origin and attributed work history.

Reuses the first-party lifecycle and text/date rules, not the reference SQLite
runtime. Canonical sources/questions remain the sole source of context and
freshness. Recorded work is neither clinical approval nor an external action.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
import hmac
import re
from typing import TypeVar
import unicodedata
import uuid

from open_intelligence.followthrough import (
    DUE_SOON_DAYS, OPEN_STATUSES, STATUSES, TRANSITIONS,
    FollowthroughInputError, check_due_date, check_task_text,
)
from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError, _digest, _key,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

from .case_bindings import _case_id
from .composer_preflight import PostgresSourceComposerPreflight, SHA256, SOURCE_SNAPSHOT_CONTRACT
from .source_questions import PostgresSourceQuestions
from .sources import PostgresSourceVersions
from .question_passages import QuestionPassages
from .followthrough_contracts import ManualTaskDependency

CONTRACT = "oi.pg-question-followthrough/1"
MAX_TASKS = 250
MAX_EVENTS = 750
PreparedResponse = TypeVar("PreparedResponse")
TASK_FIELDS = (
    "task_id", "question_id", "patient_id", "case_id", "origin_org", "actor", "purpose",
    "title", "detail", "initial_owner_label", "due_date", "review_trigger", "created_at",
    "source_id", "source_line", "source_sha256", "source_version",
    "source_snapshot_contract", "source_snapshot_sha256", "preflight_sha256",
)
EVENT_FIELDS = (
    "event_id", "task_id", "patient_id", "case_id", "origin_org", "revision",
    "previous_status", "status", "owner_label", "actor_label", "purpose", "reason", "recorded_at",
)
ANCHOR_FIELDS = (
    "question_id", "patient_id", "case_id", "source_id", "source_line", "source_sha256",
    "source_version", "source_snapshot_contract", "source_snapshot_sha256", "preflight_sha256",
)


def _identifier(value: str, prefix: str) -> str:
    if type(value) is not str or re.fullmatch(prefix + r"-[0-9A-F]{32}", value) is None:
        raise PatientRegistryError("Invalid follow-through target identifier")
    return value


def _text(value: str, field: str, *, minimum: int, maximum: int) -> str:
    if (type(value) is not str or value != value.strip()
            or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value)):
        raise PatientRegistryError(f"{field} must contain visible text on one line")
    try:
        return check_task_text(value, field, min_len=minimum, max_len=maximum)
    except FollowthroughInputError as error:
        raise PatientRegistryError(str(error)) from error


def _due(value: str | None) -> str | None:
    try:
        return check_due_date(value)
    except FollowthroughInputError as error:
        raise PatientRegistryError(str(error)) from error


def _creation_fields(*, title: str, detail: str, owner_label: str, due_date: str | None,
                     review_trigger: str, reason: str) -> dict:
    fields = {
        "title": _text(title, "Task title", minimum=3, maximum=160),
        "detail": _text(detail, "Task detail", minimum=0, maximum=2000),
        "owner_label": _text(owner_label, "Owner label", minimum=0, maximum=80),
        "due_date": _due(due_date),
        "review_trigger": _text(review_trigger, "Review trigger", minimum=0, maximum=500),
        "reason": _text(reason, "Recorded reason", minimum=3, maximum=600),
    }
    if fields["due_date"] is None and not fields["review_trigger"]:
        raise PatientRegistryError("A due date or review trigger is required")
    return fields


def _transition_fields(*, expected_revision: int, status: str,
                       owner_label: str, reason: str) -> dict:
    if type(expected_revision) is not int or expected_revision < 1:
        raise PatientRegistryError("Expected task revision must be a positive integer")
    if type(status) is not str or status not in STATUSES:
        raise PatientRegistryError("Invalid follow-through status")
    owner = _text(owner_label, "Owner label", minimum=2 if status == "assigned" else 0, maximum=80)
    if status != "assigned" and owner:
        raise PatientRegistryError("An owner can be changed only with assignment")
    return {"expected_revision": expected_revision, "status": status, "owner_label": owner,
            "reason": _text(reason, "Recorded reason", minimum=3, maximum=600)}


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise PatientRegistryError("Task history timestamp unavailable")
    return value.isoformat()


def _project_task(task: dict, history: list[dict], question: dict, evaluated_on: str,
                  manual_state: dict | None = None) -> dict:
    """Read-only lifecycle projection from the canonical question's freshness."""
    if (not history or any(task[name] != question[name] for name in ANCHOR_FIELDS)
            or task["purpose"] != "operations"
            or question["source_context_state"] not in {
                "current_unreviewed_question", "source_reassessment_required"}):
        raise PatientRegistryError("Task origin or question provenance integrity mismatch")
    due = task["due_date"].isoformat() if type(task["due_date"]) is date else task["due_date"]
    _creation_fields(title=task["title"], detail=task["detail"], owner_label=task["initial_owner_label"],
                     due_date=due, review_trigger=task["review_trigger"], reason=history[0]["reason"])
    previous = None
    effective_owner = task["initial_owner_label"]
    output_history = []
    for revision, event in enumerate(history, 1):
        if (any(event[name] != task[name] for name in
                ("task_id", "patient_id", "case_id", "origin_org", "purpose"))
                or type(event["revision"]) is not int or event["revision"] != revision
                or event["previous_status"] != previous):
            raise PatientRegistryError("Task history scope or revision integrity mismatch")
        _identifier(event["event_id"], "TASK-EVENT")
        _key(event["actor_label"], "recorded actor")
        _text(event["reason"], "Recorded reason", minimum=3, maximum=600)
        _text(event["owner_label"], "Owner label", minimum=0, maximum=80)
        if revision == 1:
            valid = (event["status"] == "created" and event["actor_label"] == task["actor"]
                     and event["owner_label"] == effective_owner)
        else:
            valid = event["status"] in TRANSITIONS.get(previous, ())
            if event["status"] == "assigned":
                _text(event["owner_label"], "Assigned owner", minimum=2, maximum=80)
                effective_owner = event["owner_label"]
            valid = valid and event["owner_label"] == effective_owner
        if not valid:
            raise PatientRegistryError("Task history contains an invalid lifecycle transition")
        previous = event["status"]
        output_history.append({name: event[name] for name in (
            "event_id", "revision", "previous_status", "status", "owner_label", "actor_label", "reason",
        )} | {"recorded_at": _timestamp(event["recorded_at"])})
    is_open = previous in OPEN_STATUSES
    soon = (date.fromisoformat(evaluated_on) + timedelta(days=DUE_SOON_DAYS)).isoformat()
    return {
        **{name: task[name] for name in ("task_id", "title", "detail", "review_trigger", *ANCHOR_FIELDS)},
        "owner_label": effective_owner, "due_date": due,
        "created_at": _timestamp(task["created_at"]), "status": previous, "revision": len(history),
        "source_context_state": question["source_context_state"],
        "manual_dependency_revision_id": (manual_state["dependency_revision_id"] if manual_state else None),
        "manual_context_state": (manual_state["state"] if manual_state else None),
        "needs_recheck": bool(is_open and (question["source_context_state"] != "current_unreviewed_question"
                                         or (manual_state is not None and manual_state["needs_recheck"]))),
        "is_overdue": bool(is_open and due and due < evaluated_on),
        "is_due_soon": bool(is_open and due and evaluated_on <= due <= soon),
        "clinical_approval": False, "history": output_history,
    }


class PostgresQuestionFollowthrough:
    """One task owner under existing patient/case/source transactions."""

    def __init__(self, registry: PostgresPatientRegistry):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry

    def _scope(self, patient_id, case_id, organization, actor, purpose):
        scope = (_key(patient_id, "patient_id"), _case_id(case_id),
                 _key(organization, "organization"), _key(actor, "actor"))
        if purpose != "operations":
            raise PatientRegistryDenied("Follow-through unavailable")
        return scope

    def _authority(self, patient_id, actor, purpose, action, recheck_authority):
        if not callable(recheck_authority):
            raise PatientRegistryError("A trusted authority recheck is required")

        def allow():
            for grant in ("patient_read", "question_read", "source_read", action):
                self.registry._allow(actor, patient_id, grant, purpose)

        allow()  # Independent grants are required before any source access.

        def final():
            recheck_authority()
            allow()  # Domain callers cannot bypass the independent final grants.

        return final

    def _read_locked(self, patient_id, case_id, organization, index, evaluated_on):
        questions = {q["question_id"]: q for q in PostgresSourceQuestions(self.registry).project_locked(
            patient_id, case_id, organization=organization, source_index=index)}
        rows = self.registry._fetchall(
            "SELECT " + ",".join(TASK_FIELDS) + " FROM coordination.question_followthrough_tasks "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s ORDER BY created_at,task_id LIMIT 251",
            (patient_id, case_id, organization),
        )
        events = self.registry._fetchall(
            "SELECT " + ",".join(EVENT_FIELDS) + " FROM coordination.question_followthrough_events "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s ORDER BY task_id,revision LIMIT 751",
            (patient_id, case_id, organization),
        )
        manual_rows = self.registry._fetchall(
            "SELECT task_id,question_id,revision_id,patient_id,case_id,origin_org,references_sha256 "
            "FROM coordination.question_followthrough_manual_dependencies "
            "WHERE patient_id=%s AND case_id=%s AND origin_org=%s LIMIT 251",
            (patient_id, case_id, organization),
        )
        if len(rows) > MAX_TASKS or len(events) > MAX_EVENTS or len(manual_rows) > MAX_TASKS:
            raise PatientRegistryError("Follow-through exceeds bounded read limit")
        histories = {}
        for row in events:
            event = dict(zip(EVENT_FIELDS, row))
            histories.setdefault(event["task_id"], []).append(event)
        manual_by_task = {}
        for row in manual_rows:
            entry = dict(zip(("task_id", "question_id", "revision_id", "patient_id",
                              "case_id", "origin_org", "references_sha256"), row))
            if entry["task_id"] in manual_by_task:
                raise PatientRegistryError("Duplicate manual task dependency")
            manual_by_task[entry["task_id"]] = entry
        output = []
        for row in rows:
            task = dict(zip(TASK_FIELDS, row))
            question = questions.get(task["question_id"])
            if question is None:
                raise PatientRegistryError("Task question unavailable in canonical context")
            bound = manual_by_task.pop(task["task_id"], None)
            manual_state = None
            if bound is not None:
                if (bound["question_id"] != task["question_id"]
                        or bound["patient_id"] != patient_id
                        or bound["case_id"] != case_id
                        or bound["origin_org"] != organization):
                    raise PatientRegistryError("Manual task dependency origin mismatch")
                scope = dict(patient_id=patient_id, case_id=case_id, organization=organization,
                             question_id=task["question_id"], purpose="operations", actor=task["actor"])
                dependency = {k:bound[k] for k in (
                    "patient_id", "case_id", "question_id", "revision_id", "references_sha256")}
                manual_state = QuestionPassages(self.registry).manual_dependency_state_locked(scope, dependency)
            output.append(_project_task(task, histories.pop(task["task_id"], []), question,
                                        evaluated_on, manual_state))
        if histories or manual_by_task:
            raise PatientRegistryError("Task history lacks its scoped origin")
        return output, questions, len(events)

    def _prior(self, patient_id, case_id, organization, request_key, intent):
        row = self.registry._fetchone(
            "SELECT e.task_id,t.question_id,e.event_id,e.revision,e.intent_sha256,e.case_id,e.origin_org "
            "FROM coordination.question_followthrough_events e "
            "JOIN coordination.question_followthrough_tasks t ON t.task_id=e.task_id "
            "WHERE e.patient_id=%s AND e.request_key=%s FOR UPDATE OF e",
            (patient_id, request_key),
        )
        if row is not None:
            if row[5] != case_id or row[6] != organization:
                raise PatientRegistryDenied("Follow-through target unavailable")
            if not hmac.compare_digest(row[4], intent):
                raise PatientRegistryConflict("Follow-through request key reused with changed intent")
            return {"task_id": row[0], "question_id": row[1], "event_id": row[2],
                    "revision": row[3], "duplicate": True}
        return None

    @staticmethod
    def _prepared(result, prepare_response):
        return prepare_response(result) if prepare_response is not None else result

    def _append(self, *, patient_id, case_id, organization, actor, purpose, task_id, question_id,
                request_key, intent, revision, previous_status, status, owner_label, reason):
        event_id = "TASK-EVENT-" + uuid.uuid4().hex.upper()
        self.registry._execute(
            "INSERT INTO coordination.question_followthrough_events "
            "(event_id,task_id,patient_id,case_id,origin_org,request_key,intent_sha256,revision,"
            "previous_status,status,owner_label,actor_label,purpose,reason) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (event_id, task_id, patient_id, case_id, organization, request_key, intent, revision,
             previous_status, status, owner_label, actor, purpose, reason),
        )
        kind = "coordination.followthrough.created" if revision == 1 else "coordination.followthrough.transitioned"
        self.registry.append_event(patient_id, kind, case_id=case_id, question_id=question_id,
                                   task_id=task_id, task_event_id=event_id, revision=revision, actor=actor)
        return {"task_id": task_id, "question_id": question_id, "event_id": event_id,
                "revision": revision, "duplicate": False}

    def list(self, patient_id: str, case_id: str, *, organization: str, actor: str, purpose: str,
             recheck_authority: Callable[[], None],
             prepare_response: Callable[[dict], PreparedResponse] | None = None,
             evaluated_on: str | None = None) -> dict | PreparedResponse:
        patient_id, case_id, organization, actor = self._scope(patient_id, case_id, organization, actor, purpose)
        day = _due(evaluated_on) if evaluated_on is not None else datetime.now(timezone.utc).date().isoformat()
        final = self._authority(patient_id, actor, purpose, "followthrough_read", recheck_authority)

        def prepare(index):
            tasks, _, _ = self._read_locked(patient_id, case_id, organization, index, day)
            return self._prepared({
                "contract": CONTRACT, "patient_id": patient_id, "case_id": case_id,
                "access_receipt_id": index["access_receipt_id"], "evaluated_on": day, "tasks": tasks,
                "synthetic": True, "clinical_approval": False, "external_notification_sent": False,
            }, prepare_response)

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                recheck_authority=final, prepare_response=prepare)

    def create(self, patient_id: str, case_id: str, question_id: str, *, organization: str,
               actor: str, purpose: str, request_key: str, title: str, detail: str,
               owner_label: str, due_date: str | None, review_trigger: str, reason: str,
               source_snapshot_contract: str, expected_source_snapshot_sha256: str,
               expected_preflight_sha256: str, recheck_authority: Callable[[], None],
               prepare_response: Callable[[dict], PreparedResponse] | None = None,
               manual_dependency: dict | None = None) -> dict | PreparedResponse:
        patient_id, case_id, organization, actor = self._scope(patient_id, case_id, organization, actor, purpose)
        question_id = _identifier(question_id, "QUESTION")
        request_key = _key(request_key, "request_key")
        fields = _creation_fields(title=title, detail=detail, owner_label=owner_label,
                                  due_date=due_date, review_trigger=review_trigger, reason=reason)
        if source_snapshot_contract != SOURCE_SNAPSHOT_CONTRACT:
            raise PatientRegistryConflict("Question source contract requires reassessment")
        if any(type(v) is not str or SHA256.fullmatch(v) is None
               for v in (expected_source_snapshot_sha256, expected_preflight_sha256)):
            raise PatientRegistryError("Task source fingerprints must be SHA-256")
        bound = ManualTaskDependency(**manual_dependency).model_dump(mode="json") if manual_dependency is not None else None
        if bound is not None and any(bound[k] != v for k,v in (
                ("patient_id", patient_id), ("case_id", case_id), ("question_id", question_id))):
            raise PatientRegistryDenied("Manual dependency scope differs from task question")
        final = self._authority(patient_id, actor, purpose, "followthrough_create", recheck_authority)
        intent = _digest({"operation": "followthrough.create", "patient_id": patient_id,
                          "case_id": case_id, "question_id": question_id, "organization": organization,
                          "actor": actor, "purpose": purpose, "request_key": request_key, **fields,
                          "source_snapshot_contract": source_snapshot_contract,
                          "source_snapshot_sha256": expected_source_snapshot_sha256,
                          "preflight_sha256": expected_preflight_sha256,
                          **({"manual_dependency": bound} if bound is not None else {})})

        def prepare(index):
            prior = self._prior(patient_id, case_id, organization, request_key, intent)
            if prior is not None:
                return self._prepared(prior, prepare_response)
            tasks, questions, event_count = self._read_locked(
                patient_id, case_id, organization, index, datetime.now(timezone.utc).date().isoformat())
            if len(tasks) >= MAX_TASKS or event_count >= MAX_EVENTS:
                raise PatientRegistryError("Follow-through exceeds bounded write limit")
            question = questions.get(question_id)
            if question is None:
                raise PatientRegistryDenied("Question follow-through target unavailable")
            if (question["source_context_state"] != "current_unreviewed_question"
                    or question["source_snapshot_contract"] != source_snapshot_contract
                    or not hmac.compare_digest(question["source_snapshot_sha256"], expected_source_snapshot_sha256)
                    or not hmac.compare_digest(question["preflight_sha256"], expected_preflight_sha256)):
                raise PatientRegistryConflict("Question source context changed; reassessment required")
            preflight = PostgresSourceComposerPreflight(self.registry).preview_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                expected_source_snapshot_sha256=expected_source_snapshot_sha256,
                source_id=question["source_id"], source_line=question["source_line"],
                question=question["question"], source_index=index)
            if not hmac.compare_digest(preflight["preflight_sha256"], expected_preflight_sha256):
                raise PatientRegistryConflict("Saved question preflight requires reassessment")
            if bound is not None:
                scope = dict(patient_id=patient_id, case_id=case_id, question_id=question_id,
                             organization=organization, actor=actor, purpose=purpose)
                state = QuestionPassages(self.registry).manual_dependency_state_locked(scope, bound)
                if state["needs_recheck"]:
                    raise PatientRegistryConflict("Selected manual passage dependency requires reassessment")
            task_id = "TASK-" + uuid.uuid4().hex.upper()
            self.registry._execute(
                "INSERT INTO coordination.question_followthrough_tasks "
                "(task_id,question_id,patient_id,case_id,origin_org,actor,purpose,title,detail,"
                "initial_owner_label,due_date,review_trigger,source_id,source_line,source_sha256,"
                "source_version,source_snapshot_contract,source_snapshot_sha256,preflight_sha256) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (task_id, question_id, patient_id, case_id, organization, actor, purpose, title, detail,
                 owner_label, due_date, review_trigger, question["source_id"], question["source_line"],
                 question["source_sha256"], question["source_version"], source_snapshot_contract,
                 expected_source_snapshot_sha256, expected_preflight_sha256),
            )
            if bound is not None:
                self.registry._execute(
                    "INSERT INTO coordination.question_followthrough_manual_dependencies "
                    "(task_id,question_id,revision_id,patient_id,case_id,origin_org,references_sha256) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (task_id, question_id, bound["revision_id"], patient_id, case_id,
                     organization, bound["references_sha256"]),
                )
            result = self._append(patient_id=patient_id, case_id=case_id, organization=organization,
                actor=actor, purpose=purpose, task_id=task_id, question_id=question_id,
                request_key=request_key, intent=intent, revision=1, previous_status=None,
                status="created", owner_label=owner_label, reason=reason)
            return self._prepared(result, prepare_response)

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                recheck_authority=final, prepare_response=prepare)

    def transition(self, patient_id: str, case_id: str, task_id: str, *, organization: str,
                   actor: str, purpose: str, request_key: str, expected_revision: int, status: str,
                   owner_label: str, reason: str, recheck_authority: Callable[[], None],
                   prepare_response: Callable[[dict], PreparedResponse] | None = None) -> dict | PreparedResponse:
        patient_id, case_id, organization, actor = self._scope(patient_id, case_id, organization, actor, purpose)
        task_id = _identifier(task_id, "TASK")
        request_key = _key(request_key, "request_key")
        fields = _transition_fields(expected_revision=expected_revision, status=status,
                                    owner_label=owner_label, reason=reason)
        final = self._authority(patient_id, actor, purpose, "followthrough_update", recheck_authority)
        intent = _digest({"operation": "followthrough.transition", "patient_id": patient_id,
                          "case_id": case_id, "task_id": task_id, "organization": organization,
                          "actor": actor, "purpose": purpose, "request_key": request_key, **fields})

        def prepare(index):
            prior = self._prior(patient_id, case_id, organization, request_key, intent)
            if prior is not None:
                return self._prepared(prior, prepare_response)
            tasks, _, event_count = self._read_locked(
                patient_id, case_id, organization, index, datetime.now(timezone.utc).date().isoformat())
            task = next((item for item in tasks if item["task_id"] == task_id), None)
            if task is None:
                raise PatientRegistryDenied("Follow-through target unavailable")
            if task["revision"] != expected_revision:
                raise PatientRegistryConflict("Task revision changed; refresh before recording another transition")
            if status not in TRANSITIONS[task["status"]]:
                raise PatientRegistryConflict("Task transition unavailable; completion requires acknowledgment")
            if event_count >= MAX_EVENTS:
                raise PatientRegistryError("Follow-through exceeds bounded write limit")
            result = self._append(patient_id=patient_id, case_id=case_id, organization=organization,
                actor=actor, purpose=purpose, task_id=task_id, question_id=task["question_id"],
                request_key=request_key, intent=intent, revision=expected_revision + 1,
                previous_status=task["status"], status=status,
                owner_label=owner_label if status == "assigned" else task["owner_label"], reason=reason)
            return self._prepared(result, prepare_response)

        with self.registry.transaction():
            return PostgresSourceVersions(self.registry).list_locked(
                patient_id, case_id, organization=organization, actor=actor, purpose=purpose,
                recheck_authority=final, prepare_response=prepare)
