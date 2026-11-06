"""Source-question response contracts, independent of HTTP composition."""

from datetime import datetime
import hashlib
import hmac
from typing import Literal

from pydantic import Field, field_validator, model_validator

from open_intelligence.patient_registry import PatientRegistryError

from .contracts import Contract
from .source_brief import check_brief_size
from .source_contracts import SourceOncologyFields


class SelectedComposerSource(SourceOncologyFields):
    source_id: str
    document_id: str
    version: int = Field(ge=1)
    sha256: str
    line: int = Field(ge=1)
    finding_key: str
    reported_state: str
    statement: str
    kind: str
    event_date: str
    issued_at: str
    specimen_id: str | None


class QuestionSourceState(Contract):
    question_id: str
    patient_id: str
    case_id: str
    question: str
    source_id: str
    source_line: int = Field(ge=1)
    source_sha256: str
    source_version: int = Field(ge=1)
    source_snapshot_contract: Literal["oi.pg-source-world-model/1",
                                      "oi.synthetic-postgres-world-model-sources/1"]
    source_snapshot_sha256: str
    preflight_sha256: str
    created_at: datetime
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]
    human_review_state: Literal["not_submitted"]
    clinical_approval: Literal[False]
    model_executed: Literal[False]


class SourceQuestionBrief(Contract):
    contract: Literal["oi.synthetic-source-brief/2"]
    synthetic: Literal[True]
    patient_id: str
    case_id: str
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    access_receipt_id: str = Field(pattern=r"^ACCESS-[0-9A-F]{32}$")
    question: QuestionSourceState
    selected_source: SelectedComposerSource
    prepared_at: datetime
    media_type: Literal["text/plain;charset=utf-8"]
    body: str = Field(min_length=1)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    clinical_approval: Literal[False]
    model_executed: Literal[False]
    biomedical_evidence_included: Literal[False]

    @field_validator("prepared_at")
    @classmethod
    def aware_preparation(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Preparation time requires a timezone")
        return value

    @model_validator(mode="after")
    def exact_question_and_body(self):
        question = self.question
        source = self.selected_source
        if (question.patient_id != self.patient_id or question.case_id != self.case_id
                or question.source_snapshot_contract != self.source_snapshot_contract
                or question.source_snapshot_sha256 != self.source_snapshot_sha256
                or question.source_context_state != "current_unreviewed_question"
                or (question.source_id, question.source_line,
                    question.source_sha256, question.source_version)
                != (source.source_id, source.line, source.sha256, source.version)):
            raise ValueError("Brief must retain its current canonical question and source")
        if not hmac.compare_digest(self.body_sha256, hashlib.sha256(self.body.encode("utf-8")).hexdigest()):
            raise ValueError("Brief body digest does not match")
        try:
            # This is the complete JSON-mode DTO the HTTP response serializes,
            # including nested source/question references and UTC timestamps.
            check_brief_size(self.model_dump(mode="json"))
        except PatientRegistryError:
            raise ValueError("Source brief exceeds bounded response size") from None
        return self
