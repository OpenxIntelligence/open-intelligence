"""Metadata discovery is distinct from evidence appraisal and clinical review."""
import re
import unicodedata
from typing import Literal

from pydantic import Field, StrictBool, field_validator

from .contracts import Contract


class EvidenceCommand(Contract):
    synthetic: Literal[True]

    @field_validator("synthetic", mode="before")
    @classmethod
    def exact_synthetic(cls, value):
        if value is not True:
            raise ValueError("Synthetic fixture acknowledgement required")
        return value


class EvidenceSearch(EvidenceCommand):
    query: str = Field(strict=True, min_length=1, max_length=200)

    @field_validator("query")
    @classmethod
    def visible_query(cls, value):
        if value != value.strip() or any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value):
            raise ValueError("Visible query required")
        return value


class EvidenceLinkCreate(EvidenceCommand):
    request_key: str = Field(strict=True, min_length=3, max_length=128)
    citation: str = Field(strict=True, pattern=r"^FICT-[A-Z0-9-]+@[A-Za-z0-9._-]+$", max_length=193)
    expected_metadata_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    expected_source_snapshot_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    expected_preflight_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")


class EvidenceMetadata(Contract):
    citation: str = Field(max_length=193)
    id: str = Field(pattern=r"^FICT-[A-Z0-9-]+$", max_length=128)
    version: str = Field(pattern=r"^[A-Za-z0-9._-]+$", max_length=64)
    source_kind: Literal["fictional"]
    title: str = Field(min_length=1, max_length=300)
    licence: str = Field(min_length=1, max_length=128)
    link: str = Field(max_length=512)
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    availability: Literal["metadata_only"] = "metadata_only"
    rights_status: Literal["granted"] = "granted"


class EvidenceScope(Contract):
    patient_id: str
    case_id: str
    question_id: str = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    source_context_state: Literal["current_unreviewed_question", "source_reassessment_required"]
    source_access_receipt_id: str = Field(pattern=r"^ACCESS-[0-9A-F]{32}$")
    synthetic: Literal[True] = True
    model_executed: Literal[False] = False
    content_appraised: Literal[False] = False
    clinical_approval: Literal[False] = False


class EvidenceSearchResult(EvidenceScope):
    contract: Literal["oi.pg-question-evidence-search/1"]
    query: str
    records: list[EvidenceMetadata] = Field(max_length=25)


class EvidenceLink(Contract):
    link_id: str = Field(pattern=r"^EVIDENCE-LINK-[0-9A-F]{32}$")
    citation: str
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str
    actor_label: str = Field(max_length=128)
    status: Literal["available", "rights_restricted", "superseded", "unavailable"]
    record: EvidenceMetadata | None


class EvidenceLinks(EvidenceScope):
    contract: Literal["oi.pg-question-evidence-links/1"]
    links: list[EvidenceLink] = Field(max_length=100)


class EvidenceLinkReceipt(Contract):
    link_id: str = Field(pattern=r"^EVIDENCE-LINK-[0-9A-F]{32}$")
    citation: str
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate: StrictBool
