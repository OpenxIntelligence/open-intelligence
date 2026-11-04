"""Typed second-opinion packet draft boundary; no referral or dispatch semantics."""
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from open_intelligence.patient_registry import _key
from .contracts import Contract

DIGEST=r"^[0-9a-f]{64}$"
SOURCE=r"^SRC-[0-9A-F]{32}$"
QUESTION=r"^QUESTION-[0-9A-F]{32}$"
PACKET=r"^SECONDOP-[0-9A-F]{32}$"


class CreateSecondOpinionPacket(Contract):
    synthetic: Literal[True]
    request_key: str
    title: str = Field(min_length=8,max_length=300)
    expected_source_snapshot_sha256: str = Field(pattern=DIGEST)
    source_ids: list[str] = Field(min_length=1,max_length=32)
    question_ids: list[str] = Field(min_length=1,max_length=16)

    @field_validator("synthetic",mode="before")
    @classmethod
    def synthetic_only(cls,value):
        if value is not True:
            raise ValueError("Explicit fictional-data attestation required")
        return value

    @field_validator("request_key")
    @classmethod
    def request_key_valid(cls,value):
        return _key(value,"request_key")

    @field_validator("title")
    @classmethod
    def title_visible(cls,value):
        if value != value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):
            raise ValueError("Packet title must be visible one-line text")
        return value

    @field_validator("source_ids")
    @classmethod
    def sources_unique(cls,values):
        import re
        if len(values)!=len(set(values)) or any(re.fullmatch(SOURCE,v) is None for v in values):
            raise ValueError("Packet sources must be unique canonical source IDs")
        return values

    @field_validator("question_ids")
    @classmethod
    def questions_unique(cls,values):
        import re
        if len(values)!=len(set(values)) or any(re.fullmatch(QUESTION,v) is None for v in values):
            raise ValueError("Packet questions must be unique canonical question IDs")
        return values


class SecondOpinionPacketReceipt(Contract):
    packet_id: str = Field(pattern=PACKET)
    duplicate: bool


class SecondOpinionSourceRef(Contract):
    source_id: str = Field(pattern=SOURCE)
    document_id: str
    version: int = Field(ge=1)
    sha256: str = Field(pattern=DIGEST)
    kind: str
    state: Literal["current","superseded"]


class SecondOpinionQuestionRef(Contract):
    question_id: str = Field(pattern=QUESTION)
    question: str
    source_id: str = Field(pattern=SOURCE)
    source_line: int = Field(ge=1,le=10000)
    source_context_state: Literal["current_unreviewed_question","source_reassessment_required"]


class SecondOpinionPacket(Contract):
    packet_id: str = Field(pattern=PACKET)
    patient_id: str
    case_id: str
    title: str
    source_snapshot_sha256: str = Field(pattern=DIGEST)
    created_at: datetime
    preparation_state: Literal["current_preparation","source_reassessment_required"]
    sources: list[SecondOpinionSourceRef]
    questions: list[SecondOpinionQuestionRef]
    record_completeness_verified: Literal[False]
    recipient_verified: Literal[False]
    external_request_sent: Literal[False]
    clinical_approval: Literal[False]


class SecondOpinionPacketList(Contract):
    contract: Literal["oi.pg-second-opinion-packets/1"]
    patient_id: str
    case_id: str
    access_receipt_id: str
    packets: list[SecondOpinionPacket]
    synthetic: Literal[True]
    recipient_verification_supported: Literal[False]
    external_dispatch_supported: Literal[False]
    clinical_approval: Literal[False]
