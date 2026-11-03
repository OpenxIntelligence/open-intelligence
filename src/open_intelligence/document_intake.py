"""Bounded UTF-8 text intake and explicit manual source-line transcription.

This module validates bytes and annotations; it does not persist an original,
infer clinical findings, verify a person's identity, or approve clinical care.
The original CaseStore remains the only source/version/assertion owner.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata

from .store import (Finding, InvalidInput, KEY, MAX_SOURCE_BYTES, ParsedReport,
                    STATES, TYPES, valid_date, valid_id)

MAX_LINES = 512
MAX_FINDINGS = 30
MEDIA_TYPE = "text/plain; charset=utf-8"
EXTRACTION_METHOD = "utf8-plain-text-v1"
ANNOTATION_METHOD = "manual-exact-line-selection"
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ ()-]*\.txt\Z", re.IGNORECASE)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED_METADATA = frozenset({
    "document_id", "kind", "event_date", "issued_at", "manual_transcription_confirmed",
})
_OPTIONAL_METADATA = frozenset({"specimen_id", "amends_version"})


def classification_provenance(receipt: dict) -> dict:
    """Keep manual classification distinct from the literal source quotation."""
    return {
        "classification_origin": "user_selected",
        "annotation_method": receipt["annotation_method"],
        "clinical_review": receipt["clinical_review"],
        "transcription_review_sha256": receipt["review_sha256"],
    }


def safe_filename(filename: object) -> str:
    """Accept a bounded download basename, never a path or MIME declaration."""
    if (not isinstance(filename, str) or len(filename) > 120 or
            not _FILENAME.fullmatch(filename) or ".." in filename):
        raise InvalidInput("Filename must be a safe .txt basename of at most 120 characters")
    return filename


def preview_text(raw: bytes, filename: str) -> dict:
    """Decode without normalizing bytes; number LF/CRLF lines for selection."""
    filename = safe_filename(filename)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES:
        raise InvalidInput("Document must be nonempty UTF-8 text, at most 64 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise InvalidInput("Only UTF-8 plain-text documents are supported") from None
    for index, character in enumerate(text):
        if character in {"\n", "\t"} or (character == "\ufeff" and index == 0):
            continue
        if character == "\r" and index + 1 < len(text) and text[index + 1] == "\n":
            continue
        if unicodedata.category(character) in {"Cc", "Cf", "Cs", "Zl", "Zp"}:
            raise InvalidInput("Document contains unsupported controls or binary content")
    visible = text.removeprefix("\ufeff").strip()
    if not visible:
        raise InvalidInput("Document must contain visible plain text")
    # A renamed container/markup document is not a plain-text import. This is
    # a bounded format guard, not a malware scanner or a general file detector.
    if visible.lower().startswith(("%pdf-", "{\\rtf", "<?xml", "<!doctype", "<html", "<svg")):
        raise InvalidInput("Unsupported document format; supply a plain-text .txt file")
    logical_lines = text.split("\n")
    if logical_lines[-1] == "":
        logical_lines.pop()
    logical_lines = [line.removesuffix("\r") for line in logical_lines]
    if len(logical_lines) > MAX_LINES:
        raise InvalidInput("Document must have at most 512 lines")
    return {
        "filename": filename, "media_type": MEDIA_TYPE,
        "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": len(raw),
        "text": text,
        "lines": [{"line": index, "text": line}
                  for index, line in enumerate(logical_lines, start=1)],
        "extraction_method": EXTRACTION_METHOD,
        "annotation_method": ANNOTATION_METHOD,
        "clinical_review": "not_performed",
    }


def review_text(case_id: str, raw: bytes, filename: str, metadata: dict,
                findings: list[dict], expected_sha256: str,
                confirmed_case_id: str) -> tuple[ParsedReport, dict]:
    """Validate an explicit source attachment and exact-line manual selections.

    Confirmation means the operator checked transcription and chose this case.
    It is neither verified patient identity nor credentialed clinical review.
    """
    if not isinstance(confirmed_case_id, str) or confirmed_case_id != case_id:
        raise InvalidInput("Explicit confirmation must match the selected case")
    preview = preview_text(raw, filename)
    if (not isinstance(expected_sha256, str) or not _HASH.fullmatch(expected_sha256) or
            not hmac.compare_digest(expected_sha256, preview["sha256"])):
        raise InvalidInput("Document changed or preview SHA-256 is missing; preview again")
    if (not isinstance(metadata, dict) or not _REQUIRED_METADATA <= metadata.keys() or
            metadata.keys() - _REQUIRED_METADATA - _OPTIONAL_METADATA):
        raise InvalidInput("Document metadata is incomplete or contains unsupported fields")
    if metadata["manual_transcription_confirmed"] is not True:
        raise InvalidInput("Confirm manual transcription; this does not establish clinical approval")
    document_id = valid_id(metadata["document_id"])
    kind = metadata["kind"]
    if not isinstance(kind, str) or kind not in TYPES:
        raise InvalidInput("Unknown document type")
    event_date = valid_date(metadata["event_date"])
    issued_at = valid_date(metadata["issued_at"])
    specimen = metadata.get("specimen_id")
    specimen_id = valid_id(specimen) if specimen is not None else None
    amends_version = metadata.get("amends_version")
    if amends_version is not None and (type(amends_version) is not int or
                                       not 1 <= amends_version <= 2147483647):
        raise InvalidInput("Amendment version must be a positive integer")
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        raise InvalidInput("Select at most 30 manual findings, or an empty list")
    selected = []
    keys = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"key", "state", "quote", "line"}:
            raise InvalidInput("Each finding needs exactly key, state, quote, and line")
        key, state, quote, line = (finding[field] for field in ("key", "state", "quote", "line"))
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in keys:
            raise InvalidInput("Finding key is invalid or repeated")
        if not isinstance(state, str) or state not in STATES:
            raise InvalidInput("Finding state must use an existing source-report state")
        if type(line) is not int or not 1 <= line <= len(preview["lines"]):
            raise InvalidInput("Finding line must identify an original numbered line")
        if (not isinstance(quote, str) or not quote.strip() or len(quote) > 1200 or
                "\r" in quote or "\n" in quote or quote not in preview["lines"][line - 1]["text"]):
            raise InvalidInput("Finding quote must be an exact nonempty original-line substring, at most 1200 characters")
        selected.append(Finding(key, state, quote, line))
        keys.add(key)
    # Annotation order and the local upload filename do not alter review
    # identity. A duplicate retains the original receipt's first filename.
    selected.sort(key=lambda item: item.key)
    reviewed = {
        "case_id": case_id, "document_id": document_id, "kind": kind,
        "event_date": event_date, "issued_at": issued_at, "specimen_id": specimen_id,
        "amends_version": amends_version, "manual_transcription_confirmed": True,
        "findings": [{"key": item.key, "state": item.state, "quote": item.quote, "line": item.line}
                     for item in selected],
    }
    receipt = {
        "filename": preview["filename"], "media_type": MEDIA_TYPE,
        "extraction_method": EXTRACTION_METHOD, "annotation_method": ANNOTATION_METHOD,
        "manual_transcription_confirmed": True, "clinical_review": "not_performed",
        "review_sha256": hashlib.sha256(json.dumps(
            reviewed, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
    }
    report = ParsedReport(
        case_id, document_id, kind, event_date, issued_at, specimen_id,
        (document_id, amends_version) if amends_version is not None else None,
        tuple(selected), raw)
    return report, receipt
