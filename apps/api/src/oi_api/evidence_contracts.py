"""Metadata discovery is distinct from evidence appraisal and clinical review."""
import unicodedata
import re
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

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


class PassageEvidenceLinkCreate(EvidenceLinkCreate):
    source_snapshot_contract: Literal["oi.reviewed-document-selection/1"]

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


class PassageReviewSelection(Contract):
    """Immutable user-selected origin, not a clinical or source-authored finding."""
    source_id: StrictStr = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    document_id: StrictStr = Field(min_length=2, max_length=40)
    source_version: StrictInt = Field(ge=1)
    original_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_revision_id: StrictStr = Field(pattern=r"^ANN-[0-9A-F]{32}$")
    annotation_revision: StrictInt = Field(ge=1)
    review_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    selected_by: StrictStr = Field(min_length=3, max_length=128)
    selected_at: StrictStr = Field(min_length=20, max_length=40)
    selected_state: Literal["reported", "negative", "pending", "indeterminate",
                            "not-reported", "not-assessed", "conflicting"]
    quote: StrictStr = Field(min_length=1, max_length=1200)
    line: StrictInt = Field(ge=1, le=512)
    page: StrictInt | None = Field(default=None, ge=1)
    classification_origin: Literal["user_selected"]
    clinical_review: Literal["not_performed"]
    anchor_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    selection_state: Literal["current_unreviewed_selection", "selection_reassessment_required"]


class PassageReviewPreparation(EvidenceScope):
    """Atomic, rights-filtered material for a future independent human review.

    Metadata-only citations do not imply scientific appraisal, comparison,
    clinical review, patient-specific evidence, or treatment guidance.
    """
    contract: Literal["oi.pg-passage-review-preparation/1"]
    source_id: StrictStr = Field(pattern=r"^SRC-[0-9A-F]{32}$")
    question_text: StrictStr = Field(min_length=8, max_length=500)
    selection: PassageReviewSelection
    links: list[EvidenceLink] = Field(max_length=100)
    human_review_state: Literal["not_performed"]
    next_step: Literal["independent_verification_required", "source_reassessment_required"]
    packet_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def status_and_source_are_not_promoted(self):
        if self.source_id != self.selection.source_id:
            raise ValueError("Review source mismatch")
        current = self.source_context_state == "current_unreviewed_question"
        if ((self.selection.selection_state == "current_unreviewed_selection") != current
                or self.next_step != ("independent_verification_required" if current
                                     else "source_reassessment_required")):
            raise ValueError("Historical passage cannot be marked ready for review")
        return self


class EvidenceLinkReceipt(Contract):
    link_id: str = Field(pattern=r"^EVIDENCE-LINK-[0-9A-F]{32}$")
    citation: str = Field(strict=True, pattern=CITATION_PATTERN, max_length=193)
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    duplicate: StrictBool
