"""Public contracts for one deterministic, synthetic Composer execution kind."""
from datetime import datetime
from typing import Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from open_intelligence.patient_registry import _key

from .contracts import Contract
from .source_question_contracts import SourceQuestionBrief

RunState = Literal["queued", "running", "completed", "blocked", "stale", "cancelled", "failed"]


class CancelComposerRun(Contract):
    synthetic: StrictBool

    @field_validator("synthetic")
    @classmethod
    def fictional_only(cls, value):
        if value is not True:
            raise ValueError("Only independently fictional execution is enabled")
        return value


class EnqueueComposerRun(CancelComposerRun):
    request_key: str = Field(min_length=3, max_length=128)
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    expected_source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_preflight_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("request_key")
    @classmethod
    def opaque_key(cls, value):
        return _key(value, "request_key")


class ComposerRunStatus(Contract):
    contract: Literal["oi.synthetic-composer-run/1"] = "oi.synthetic-composer-run/1"
    synthetic: Literal[True] = True
    run_id: str = Field(pattern=r"^RUN-[0-9A-F]{32}$")
    patient_id: str
    case_id: str
    question_id: str = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    kind: Literal["source-question-brief/1"]
    state: RunState
    revision: int = Field(ge=1)
    attempt_count: int = Field(ge=0, le=3)
    max_attempts: Literal[3]
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preflight_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime
    updated_at: datetime
    available_at: datetime
    lease_expires_at: datetime | None
    result_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    model_executed: Literal[False] = False
    clinical_approval: Literal[False] = False

    @field_validator("created_at", "updated_at", "available_at", "lease_expires_at")
    @classmethod
    def aware_time(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Execution timestamps require explicit timezones")
        return value

    @model_validator(mode="after")
    def coherent_state(self):
        if (self.state == "running") != (self.lease_expires_at is not None):
            raise ValueError("Only running work has a current lease")
        if self.state == "running" and self.attempt_count < 1:
            raise ValueError("A running lease needs an attempt")
        if (self.state == "completed") != (self.result_sha256 is not None):
            raise ValueError("Only completed work has an accepted result")
        return self


class ComposerRunReceipt(Contract):
    run: ComposerRunStatus
    duplicate: bool


class ComposerRunResult(Contract):
    contract: Literal["oi.synthetic-composer-run-result/1"] = "oi.synthetic-composer-run-result/1"
    run: ComposerRunStatus
    access_receipt_id: str = Field(pattern=r"^ACCESS-[0-9A-F]{32}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    brief: SourceQuestionBrief

    @model_validator(mode="after")
    def bound_to_run(self):
        run, brief = self.run, self.brief
        if (run.state != "completed" or run.result_sha256 != self.result_sha256
                or (run.patient_id, run.case_id, run.question_id,
                    run.source_snapshot_contract, run.source_snapshot_sha256, run.preflight_sha256)
                != (brief.patient_id, brief.case_id, brief.question.question_id,
                    brief.source_snapshot_contract, brief.source_snapshot_sha256,
                    brief.question.preflight_sha256)):
            raise ValueError("Result must retain its exact run, question and source")
        return self
