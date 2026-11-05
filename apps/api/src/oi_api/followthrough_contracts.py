"""Typed operational task boundary; source and clinical authority remain separate."""
from datetime import date
from typing import Literal
import unicodedata

from pydantic import Field, StrictInt, field_validator, model_validator

from open_intelligence.followthrough import check_due_date, check_task_text
from open_intelligence.patient_registry import _key

from .contracts import Contract

TaskStatus = Literal["created", "assigned", "acknowledged", "completed", "deferred"]
TaskID = r"^TASK-[0-9A-F]{32}$"
EventID = r"^TASK-EVENT-[0-9A-F]{32}$"
QuestionID = r"^QUESTION-[0-9A-F]{32}$"
Digest = r"^[0-9a-f]{64}$"


def _visible(value: str, field: str, low: int, high: int) -> str:
    checked = check_task_text(value, field, min_len=low, max_len=high)
    if checked != value or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value):
        raise ValueError("Task fields must contain visible text without surrounding whitespace")
    return checked


class ManualTaskDependency(Contract):
    """Explicit versioned manual reference, not a source grant or a task write.

    Kept separate from FollowthroughCreate until the existing task owner can
    atomically persist and revalidate it under its case/permission locks.
    No original text, quotations, or clinical conclusions may be carried here.
    """
    patient_id: str
    case_id: str
    question_id: str = Field(pattern=QuestionID)
    revision_id: str = Field(pattern=r"^PASSAGES-[0-9A-F]{32}$")
    references_sha256: str = Field(pattern=Digest)

    @field_validator("patient_id", "case_id")
    @classmethod
    def scoped_identifier(cls, value, info):
        return _key(value, info.field_name)


class FollowthroughCreate(Contract):
    synthetic: Literal[True]
    request_key: str
    title: str = Field(min_length=3, max_length=160)
    detail: str = Field(default="", max_length=2000)
    owner_label: str = Field(default="", max_length=80)
    due_date: str | None = None
    review_trigger: str = Field(default="", max_length=500)
    reason: str = Field(min_length=3, max_length=600)
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    expected_source_snapshot_sha256: str = Field(pattern=Digest)
    expected_preflight_sha256: str = Field(pattern=Digest)
    manual_dependency: ManualTaskDependency | None = None

    @field_validator("synthetic", mode="before")
    @classmethod
    def exact_attestation(cls, value):
        if value is not True:
            raise ValueError("Explicit synthetic attestation required")
        return value

    @field_validator("request_key")
    @classmethod
    def valid_key(cls, value):
        return _key(value, "request_key")

    @field_validator("title", "detail", "owner_label", "review_trigger", "reason")
    @classmethod
    def visible_text(cls, value, info):
        bounds = {"title": (3, 160), "detail": (0, 2000), "owner_label": (0, 80),
                  "review_trigger": (0, 500), "reason": (3, 600)}
        return _visible(value, info.field_name, *bounds[info.field_name])

    @field_validator("due_date")
    @classmethod
    def valid_date(cls, value):
        return check_due_date(value)

    @model_validator(mode="after")
    def revisit_basis(self):
        if self.due_date is None and not self.review_trigger:
            raise ValueError("Record a due date or review trigger")
        return self


class FollowthroughTransition(Contract):
    synthetic: Literal[True]
    request_key: str
    expected_revision: StrictInt = Field(ge=1)
    status: Literal["assigned", "acknowledged", "completed", "deferred"]
    owner_label: str = Field(default="", max_length=80)
    reason: str = Field(min_length=3, max_length=600)

    @field_validator("synthetic", mode="before")
    @classmethod
    def exact_attestation(cls, value):
        if value is not True:
            raise ValueError("Explicit synthetic attestation required")
        return value

    @field_validator("request_key")
    @classmethod
    def valid_key(cls, value):
        return _key(value, "request_key")

    @field_validator("owner_label", "reason")
    @classmethod
    def visible_text(cls, value, info):
        return _visible(value, info.field_name, *( (0, 80) if info.field_name == "owner_label" else (3, 600)))

    @model_validator(mode="after")
    def owner_assignment(self):
        if self.status == "assigned" and len(self.owner_label) < 2:
            raise ValueError("Assignment requires a recorded owner label")
        if self.status != "assigned" and self.owner_label:
            raise ValueError("Owner changes require an assignment transition")
        return self


class FollowthroughReceipt(Contract):
    task_id: str = Field(pattern=TaskID)
    question_id: str = Field(pattern=QuestionID)
    event_id: str = Field(pattern=EventID)
    revision: StrictInt = Field(ge=1)
    duplicate: bool


class FollowthroughEvent(Contract):
    event_id: str = Field(pattern=EventID)
    revision: StrictInt = Field(ge=1)
    previous_status: TaskStatus | None
    status: TaskStatus
    owner_label: str
    actor_label: str
    reason: str
    recorded_at: str


class FollowthroughTask(Contract):
    task_id: str = Field(pattern=TaskID)
    question_id: str = Field(pattern=QuestionID)
    patient_id: str
    case_id: str
    title: str
    detail: str
    owner_label: str
    due_date: str | None
    review_trigger: str
    created_at: str
    status: TaskStatus
    revision: StrictInt = Field(ge=1)
    source_id: str
    source_line: StrictInt = Field(ge=1)
    source_sha256: str = Field(pattern=Digest)
    source_version: StrictInt = Field(ge=1)
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    source_snapshot_sha256: str = Field(pattern=Digest)
    preflight_sha256: str = Field(pattern=Digest)
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]
    manual_dependency_revision_id: str | None = None
    manual_context_state: Literal["current_unreviewed", "reassessment_required"] | None = None
    needs_recheck: bool
    is_overdue: bool
    is_due_soon: bool
    clinical_approval: Literal[False]
    history: list[FollowthroughEvent] = Field(min_length=1, max_length=750)

    @model_validator(mode="after")
    def coherent_history(self):
        from open_intelligence.followthrough import TRANSITIONS
        if [e.revision for e in self.history] != list(range(1, self.revision + 1)):
            raise ValueError("Task history must retain every revision")
        previous = None
        for event in self.history:
            if event.previous_status != previous:
                raise ValueError("Task history predecessor mismatch")
            if previous is None:
                if event.status != "created":
                    raise ValueError("Task history must begin with creation")
            elif event.status not in TRANSITIONS[previous]:
                raise ValueError("Task history contains an invalid transition")
            previous = event.status
        last = self.history[-1]
        if (last.status, last.owner_label) != (self.status, self.owner_label):
            raise ValueError("Task status must match its recorded history")
        return self


class FollowthroughList(Contract):
    contract: Literal["oi.pg-question-followthrough/1"]
    patient_id: str
    case_id: str
    access_receipt_id: str
    evaluated_on: str
    tasks: list[FollowthroughTask] = Field(max_length=250)
    synthetic: Literal[True]
    clinical_approval: Literal[False]
    external_notification_sent: Literal[False]

    @field_validator("evaluated_on")
    @classmethod
    def exact_day(cls, value):
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("Expected ISO evaluation day")
        return value

    @model_validator(mode="after")
    def scoped_tasks(self):
        if len({t.task_id for t in self.tasks}) != len(self.tasks):
            raise ValueError("Duplicate task identifier")
        if sum(len(t.history) for t in self.tasks) > 750:
            raise ValueError("Task history exceeds bounded read limit")
        for task in self.tasks:
            if (task.patient_id, task.case_id) != (self.patient_id, self.case_id):
                raise ValueError("Task scope mismatch")
        return self


class LaboratoryFollowthroughTask(FollowthroughTask):
    """An Observation in an immutable original has no text line or manual passage."""
    source_line: None
    observation_reference: str = Field(strict=True, pattern=r"^Observation/[A-Za-z0-9.-]{1,64}$")
    manual_dependency_revision_id: None = None
    manual_context_state: None = None


class FollowthroughListV2(FollowthroughList):
    contract: Literal["oi.pg-question-followthrough/2"]
    tasks: list[FollowthroughTask | LaboratoryFollowthroughTask] = Field(max_length=250)
