"""Wire contracts for independently checking the transcription of an amended lab result."""
from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictInt, field_validator

from open_intelligence.patient_registry import _key
from .contracts import Contract
from .followthrough_contracts import Digest, QuestionID, TaskID, _visible

SourceID = Annotated[str, Field(pattern=r"^SRC-[0-9A-F]{32}$")]
ReviewID = Annotated[str, Field(pattern=r"^VERIFY-[0-9A-F]{32}$")]
SHA256 = Annotated[str, Field(pattern=Digest)]
Disposition = Literal["transcription_checked", "needs_clarification"]
MAX_REVIEW_ENTRIES = 750


class _Command(Contract):
    synthetic: Literal[True]
    request_key: str
    expected_latest_source_id: SourceID
    expected_latest_sha256: SHA256
    reason: str = Field(min_length=3, max_length=600)

    @field_validator("synthetic", mode="before")
    @classmethod
    def explicit_attestation(cls, value):
        if value is not True:
            raise ValueError("Explicit synthetic attestation required")
        return value

    @field_validator("request_key")
    @classmethod
    def bounded_key(cls, value):
        return _key(value, "request_key")

    @field_validator("reason")
    @classmethod
    def visible_reason(cls, value):
        return _visible(value, "Recorded reason", 3, 600)


class RequestVerification(_Command):
    action: Literal["request"]


class RespondToVerification(_Command):
    action: Literal["respond"]
    request_id: ReviewID
    disposition: Disposition


AmendmentCommand = Annotated[RequestVerification | RespondToVerification, Field(discriminator="action")]


class AmendmentReceipt(Contract):
    entry_id: ReviewID
    request_id: ReviewID
    duplicate: StrictBool


class ReportedObservation(Contract):
    loinc_code: str
    status: Literal["reported_value", "reported_absent"]
    value_text: str | None
    unit_code: str | None
    absent_reason: Literal["unknown", "not-performed", "error", "masked"] | None
    specimen_reference: str
    effective_at: str
    issued_at: str


class ReportVersion(Contract):
    source_id: SourceID
    version: StrictInt = Field(ge=1)
    sha256: SHA256
    document_id: str
    observation: ReportedObservation | None


class OriginalReportVersion(ReportVersion):
    observation: ReportedObservation


class ReviewEntry(Contract):
    entry_id: ReviewID
    request_id: ReviewID
    action: Literal["request", "respond"]
    actor: str
    recorded_at: str
    reason: str
    disposition: Disposition | None
    original_source_id: SourceID
    latest_source_id: SourceID
    latest_sha256: SHA256


class AmendmentComparison(Contract):
    contract: Literal["oi.laboratory-amendment-review/1"]
    patient_id: str
    case_id: str
    task_id: str = Field(pattern=TaskID)
    question_id: str = Field(pattern=QuestionID)
    observation_reference: str = Field(pattern=r"^Observation/[A-Za-z0-9.-]{1,64}$")
    original: OriginalReportVersion
    latest: ReportVersion
    entries: list[ReviewEntry] = Field(max_length=MAX_REVIEW_ENTRIES)
    clinical_approval: Literal[False]


class PendingRequest(Contract):
    request_id: ReviewID
    task_id: str = Field(pattern=TaskID)
    question_id: str = Field(pattern=QuestionID)
    latest_source_id: SourceID


class AmendmentInbox(Contract):
    contract: Literal["oi.laboratory-amendment-inbox/1"]
    patient_id: str
    case_id: str
    requests: list[PendingRequest] = Field(max_length=MAX_REVIEW_ENTRIES)
    clinical_approval: Literal[False]
