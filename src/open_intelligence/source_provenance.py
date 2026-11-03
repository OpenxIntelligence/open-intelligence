"""Shared validation for source-linked manual and PDF transcription provenance.

The original source owner supplies frozen receipts and page anchors. These pure
checks preserve their association and shape; they do not independently reread
or authenticate source bytes, and they never establish clinical review.
"""
from __future__ import annotations

import re
from typing import Any

from .document_intake import safe_filename
from .store import InvalidInput

MAX_ID = 9223372036854775807
_HASH = re.compile(r"[0-9a-f]{64}\Z")
REVISION_FIELDS = ("annotation_revision_id", "annotation_revision")
_MANUAL_FIELDS = ("classification_origin", "annotation_method", "clinical_review",
                  "transcription_review_sha256", "initial_transcription_review_sha256") + REVISION_FIELDS
_PDF_IDENTITY = ("text_origin", "extraction_sha256")
_PDF_ANCHORS = ("source_page", "page_line", "page_text_sha256")
_PROVENANCE_FIELDS = _MANUAL_FIELDS + _PDF_IDENTITY + _PDF_ANCHORS


def _positive(value: Any, name: str) -> int:
    if type(value) is not int or not 1 <= value <= MAX_ID:
        raise InvalidInput(f"{name} must be a positive signed 64-bit integer")
    return value


def _hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise InvalidInput(f"{name} must be a SHA-256 digest")
    return value


PROVENANCE_FIELDS = _PROVENANCE_FIELDS


def source_provenance(source: dict) -> dict:
    """Validate source-linked receipt association, without reading raw bytes."""
    if "document_intake" not in source:
        if any(field in source for field in _PROVENANCE_FIELDS):
            raise InvalidInput("Manual or PDF source provenance requires its intake receipt")
        return {}
    receipt = source["document_intake"]
    required = {"filename", "media_type", "extraction_method", "annotation_method",
                "manual_transcription_confirmed", "clinical_review", "review_sha256",
                "initial_review_sha256", *REVISION_FIELDS}
    if not isinstance(receipt, dict) or not required <= receipt.keys():
        raise InvalidInput("Incomplete source intake provenance")
    filename = safe_filename(receipt["filename"])
    if (receipt["manual_transcription_confirmed"] is not True or
            receipt["clinical_review"] != "not_performed"):
        raise InvalidInput("Manual transcription must not imply clinical approval")
    reviewed = _hash(receipt["review_sha256"], "Transcription review")
    is_pdf = receipt["media_type"] == "application/pdf"
    if is_pdf:
        if (not filename.lower().endswith(".pdf") or receipt["extraction_method"] != "pypdf-text-v1" or
                receipt["annotation_method"] != "manual-exact-extraction-line-selection"):
            raise InvalidInput("Unsupported PDF source provenance")
    elif (receipt["media_type"] != "text/plain; charset=utf-8" or
          not filename.lower().endswith(".txt") or receipt["extraction_method"] != "utf8-plain-text-v1" or
          receipt["annotation_method"] != "manual-exact-line-selection" or
          "extraction_sha256" in receipt):
        raise InvalidInput("Unsupported text source provenance")
    expected = {"classification_origin": "user_selected",
                "annotation_method": receipt["annotation_method"],
                "clinical_review": "not_performed", "transcription_review_sha256": reviewed,
                "initial_transcription_review_sha256": _hash(
                    receipt["initial_review_sha256"], "Initial transcription review")}
    for field in REVISION_FIELDS:
        expected[field] = _positive(receipt[field], field)
        _positive(source.get(field), field)
    if is_pdf:
        expected.update({"text_origin": "pdf_extraction",
                         "extraction_sha256": _hash(receipt.get("extraction_sha256"), "PDF extraction")})
    if any(source.get(field) != value for field, value in expected.items()):
        raise InvalidInput("Source provenance does not match its intake receipt")
    if any(field in source for field in _PDF_ANCHORS) or (not is_pdf and any(field in source for field in _PDF_IDENTITY)):
        raise InvalidInput("Unexpected source-level PDF anchor provenance")
    return expected


def assertion_provenance(assertion: dict, source_provenance: dict, line: int) -> dict:
    """Preserve trusted frozen anchors and reject absent or mismatched origin.

    CaseStore already reads page anchors from the immutable rendition in the
    same transaction as this snapshot. This projection checks their shape and
    source receipt linkage; it does not independently reparse, re-hash, or
    reread PDF content. It cannot authenticate a consistently forged snapshot.
    """
    if not source_provenance:
        if any(field in assertion for field in _PROVENANCE_FIELDS):
            raise InvalidInput("Finding provenance has no associated source receipt")
        return {}
    for field in REVISION_FIELDS:
        _positive(assertion.get(field), field)
    if any(assertion.get(field) != value for field, value in source_provenance.items()):
        raise InvalidInput("Finding provenance does not match its source receipt")
    result = dict(source_provenance)
    if source_provenance.get("text_origin") == "pdf_extraction":
        page = _positive(assertion.get("source_page"), "Physical source page")
        page_line = _positive(assertion.get("page_line"), "Physical page line")
        if page > 20 or line > 512 or page_line > line:
            raise InvalidInput("PDF finding anchor exceeds the supported rendition bounds")
        result.update({"source_page": page, "page_line": page_line,
                       "page_text_sha256": _hash(assertion.get("page_text_sha256"), "Extracted page")})
    elif any(field in assertion for field in _PDF_IDENTITY + _PDF_ANCHORS):
        raise InvalidInput("Text finding cannot claim PDF extraction provenance")
    return result


