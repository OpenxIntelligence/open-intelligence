"""Metadata discovery is distinct from evidence appraisal and clinical review."""
import unicodedata
import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, StrictBool, field_validator, model_validator

from .contracts import Contract

CITATION_PATTERN = r"^FICT-[A-Z0-9-]{1,123}@[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"


def _visible_metadata(value):
    if value != value.strip() or any(
            unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value):
        raise ValueError("Visible metadata required")
    return value


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
    citation: str = Field(strict=True, pattern=CITATION_PATTERN, max_length=193)
    expected_metadata_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    source_snapshot_contract: Literal["oi.pg-source-world-model/1"]
    expected_source_snapshot_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    expected_preflight_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")


class EvidenceMetadata(Contract):
    citation: str = Field(strict=True, pattern=CITATION_PATTERN, max_length=193)
    id: str = Field(strict=True, pattern=r"^FICT-[A-Z0-9-]+$", max_length=128)
    version: str = Field(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$", max_length=64)
    source_kind: Literal["fictional"]
    title: str = Field(strict=True, min_length=1, max_length=300)
    licence: str = Field(strict=True, min_length=1, max_length=128)
    link: str = Field(strict=True, max_length=512)
    metadata_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    availability: Literal["metadata_only"] = "metadata_only"
    rights_status: Literal["granted"] = "granted"

    @field_validator("title", "licence", "link")
    @classmethod
    def visible_metadata(cls, value):
        return _visible_metadata(value)

    @field_validator("link")
    @classmethod
    def fictional_link(cls, value):
        url = urlsplit(value)
        if (url.scheme != "https" or url.netloc != "example.invalid"
                or not url.path.startswith("/fictional/") or url.query or url.fragment
                or any(c.isspace() for c in value)):
            raise ValueError("Explicit fictional source link required")
        return value

    @model_validator(mode="after")
    def exact_identity(self):
        if self.citation != f"{self.id}@{self.version}":
            raise ValueError("Metadata identity must match its exact citation")
        return self


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
    citation: str = Field(strict=True, pattern=CITATION_PATTERN, max_length=193)
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str = Field(strict=True, min_length=20, max_length=40)
    actor_label: str = Field(max_length=128)
    status: Literal["available", "rights_restricted", "superseded", "unavailable"]
    record: EvidenceMetadata | None

    @field_validator("created_at")
    @classmethod
    def exact_timestamp(cls, value):
        """Preserve the stored offset string, but never serialize spoofed history dates.

        The canonical PostgreSQL original uses datetime.isoformat(), including
        fractional seconds when needed. A literal ASCII T, full seconds and
        explicit zone are required; Python's permissive ISO parser alone also
        accepts invisible Unicode separators and non-calendar forms.
        """
        if (re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
                value) is None):
            raise ValueError("Explicit visible ISO timestamp required")
        # datetime.fromisoformat can normalize invalid numeric offset
        # minutes (for example +05:99 becomes +06:39). Refuse such input
        # *before* parsing rather than silently altering its interpretation.
        if value[-1] != "Z" and (
                int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            raise ValueError("Invalid UTC offset fields")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError()
        except ValueError:
            raise ValueError("Actual calendar timestamp with timezone required") from None
        return value

    @model_validator(mode="after")
    def governed_metadata(self):
        if (self.status == "available") != (self.record is not None):
            raise ValueError("Only available evidence may disclose metadata")
        if self.record is not None and (
                self.record.citation != self.citation
                or self.record.metadata_sha256 != self.metadata_sha256):
            raise ValueError("Metadata must match the durable citation and fingerprint")
        return self


class EvidenceLinks(EvidenceScope):
    contract: Literal["oi.pg-question-evidence-links/1"]
    links: list[EvidenceLink] = Field(max_length=100)


class EvidenceLinkReceipt(Contract):
    link_id: str = Field(pattern=r"^EVIDENCE-LINK-[0-9A-F]{32}$")
    citation: str = Field(strict=True, pattern=CITATION_PATTERN, max_length=193)
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate: StrictBool


class LaboratoryEvidenceAnchor(Contract):
    """The immutable original result selected when this question was saved."""

    source_id: str = Field(strict=True, pattern=r"^SRC-[0-9A-F]{32}$")
    source_version: int = Field(strict=True, ge=1)
    source_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    observation_reference: str = Field(strict=True, pattern=r"^Observation/[A-Za-z0-9.-]{1,64}$")
    source_snapshot_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    preflight_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")


class LaboratoryEvidenceSearchResult(EvidenceSearchResult):
    question_anchor: LaboratoryEvidenceAnchor


class LaboratoryEvidenceLinks(EvidenceLinks):
    question_anchor: LaboratoryEvidenceAnchor

class RunEvidenceReview(EvidenceCommand):
    verification: Literal["exact_version_metadata_only"]
    link_id: str = Field(strict=True, pattern=r"^EVIDENCE-LINK-[0-9A-F]{32}$")
    citation: str = Field(strict=True, pattern=CITATION_PATTERN, max_length=193)
    expected_metadata_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    expected_result_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")


class RunQuoteReview(EvidenceCommand):
    verification: Literal["exact_authored_quote"]
    assessment_id: str = Field(strict=True, pattern=r"^ASSESSMENT-[0-9A-F]{32}$")
    expected_evidence_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    expected_quote_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")
    expected_result_sha256: str = Field(strict=True, pattern=r"^[0-9a-f]{64}$")


class RunReviewReceipt(Contract):
    contract: Literal["oi.synthetic-run-evidence-review-return/1"]
    receipt_id: str = Field(pattern=r"^REVIEW-[0-9A-F]{32}$")
    question_id: str = Field(pattern=r"^QUESTION-[0-9A-F]{32}$")
    run_id: str = Field(pattern=r"^RUN-[0-9A-F]{32}$")
    result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate: StrictBool
    review_state: Literal["returned_for_independent_verification"]
    clinical_approval: Literal[False]
    model_executed: Literal[False]


class RunEvidenceReviewReceipt(RunReviewReceipt):
    verification: Literal["exact_version_metadata_only"]
    link_id: str = Field(pattern=r"^EVIDENCE-LINK-[0-9A-F]{32}$")
    citation: str = Field(pattern=CITATION_PATTERN, max_length=193)
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RunQuoteReviewReceipt(RunReviewReceipt):
    verification: Literal["exact_authored_quote"]
    assessment_id: str = Field(pattern=r"^ASSESSMENT-[0-9A-F]{32}$")
    evidence_id: str = Field(pattern=r"^EVIDENCE-[0-9A-F]{32}$")
    evidence_version: int = Field(strict=True, ge=1)
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    statement_line: int = Field(strict=True, ge=1)
    quote_start: int = Field(strict=True, ge=0)
    quote_length: int = Field(strict=True, ge=1, le=400)
    quote_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
