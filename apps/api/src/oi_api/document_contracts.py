"""Strict command boundary for source-owned, manually reviewed documents."""
import base64
import binascii
from typing import Literal

from pydantic import Field, StrictBool, StrictInt, field_validator

from open_intelligence.document_intake import safe_filename, validate_revision_reason
from .contracts import Contract


class FictionalDocument(Contract):
    synthetic: StrictBool

    @field_validator("synthetic")
    @classmethod
    def fictional(cls, value):
        if value is not True:
            raise ValueError("Independently authored fictional documents only")
        return value


class DocumentUpload(FictionalDocument):
    filename: str = Field(max_length=120)
    original_base64: str = Field(min_length=4, max_length=87384)

    @field_validator("filename")
    @classmethod
    def basename(cls, value):
        return safe_filename(value)

    def original_bytes(self) -> bytes:
        try:
            raw = base64.b64decode(self.original_base64, validate=True)
            if not 1 <= len(raw) <= 65536 or base64.b64encode(raw).decode() != self.original_base64:
                raise ValueError()
            return raw
        except (ValueError, binascii.Error):
            raise ValueError("Invalid bounded document bytes") from None


class ManualFinding(Contract):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,59}$")
    state: Literal["reported", "negative", "pending", "indeterminate", "not-reported", "not-assessed", "conflicting"]
    quote: str = Field(min_length=1, max_length=1200)
    line: StrictInt = Field(ge=1, le=512)


class DocumentMetadata(Contract):
    document_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{1,39}$")
    kind: Literal["clinical", "pathology", "laboratory", "imaging", "molecular", "other"]
    event_date: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    issued_at: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    specimen_id: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9-]{1,39}$")
    amends_version: StrictInt | None = Field(default=None, ge=1, le=2147483647)
    manual_transcription_confirmed: StrictBool


class DocumentImport(DocumentUpload):
    confirmed_case_id: str = Field(pattern=r"^CASE-[A-Z0-9-]{1,35}$")
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_extraction_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    metadata: DocumentMetadata
    findings: list[ManualFinding] = Field(max_length=30)


class AnnotationCorrection(FictionalDocument):
    request_key: str = Field(min_length=3, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    expected_revision_id: str = Field(pattern=r"^ANN-[A-F0-9]{32}$")
    confirmed_case_id: str = Field(pattern=r"^CASE-[A-Z0-9-]{1,35}$")
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_extraction_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str = Field(min_length=3, max_length=500)
    findings: list[ManualFinding] = Field(max_length=30)

    @field_validator("reason")
    @classmethod
    def correction_reason(cls, value):
        return validate_revision_reason(value)
