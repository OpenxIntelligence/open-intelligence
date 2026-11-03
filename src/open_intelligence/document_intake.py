"""Bounded document intake and explicit manual passage transcription.

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
_FILENAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ ()-]*\.(?:txt|pdf)\Z", re.IGNORECASE)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED_METADATA = frozenset({
    "document_id", "kind", "event_date", "issued_at", "manual_transcription_confirmed",
})
_OPTIONAL_METADATA = frozenset({"specimen_id", "amends_version"})


def classification_provenance(receipt: dict) -> dict:
    """Keep manual classification distinct from the literal source quotation."""
    result = {
        "classification_origin": "user_selected",
        "annotation_method": receipt["annotation_method"],
        "clinical_review": receipt["clinical_review"],
        "transcription_review_sha256": receipt["review_sha256"],
    }
    if receipt.get("extraction_sha256"):
        result["extraction_sha256"] = receipt["extraction_sha256"]
        result["text_origin"] = "pdf_extraction"
    for key in ("annotation_revision_id", "annotation_revision"):
        if receipt.get(key) is not None:
            result[key] = receipt[key]
    if "initial_review_sha256" in receipt:
        result["initial_transcription_review_sha256"] = receipt["initial_review_sha256"]
    return result


def validate_revision_reason(reason: object) -> str:
    """Keep an operator's bounded correction reason separate from findings."""
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500:
        raise InvalidInput("Annotation revision reason must have 3–500 characters")
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs", "Zl", "Zp"}
           and character not in {"\n", "\t"} for character in reason):
        raise InvalidInput("Annotation revision reason contains unsupported controls")
    return reason.strip()


def safe_filename(filename: object) -> str:
    """Accept a bounded download basename, never a path or MIME declaration."""
    if (not isinstance(filename, str) or len(filename) > 120 or
            not _FILENAME.fullmatch(filename) or ".." in filename):
        raise InvalidInput("Filename must be a safe .txt or .pdf basename of at most 120 characters")
    return filename


def preview_text(raw: bytes, filename: str) -> dict:
    """Decode without normalizing bytes; number LF/CRLF lines for selection."""
    filename = safe_filename(filename)
    if not filename.lower().endswith(".txt"):
        raise InvalidInput("Plain-text preview requires a .txt filename")
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


def preview_document(raw: bytes, filename: str) -> dict:
    """One media-aware preview, without persisting or inferring patient facts."""
    filename = safe_filename(filename)
    if filename.lower().endswith(".txt"):
        return preview_text(raw, filename)
    from .pdf_intake import extract_pdf
    rendition = extract_pdf(raw)
    return {
        "filename": filename, "media_type": "application/pdf",
        "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": len(raw),
        **rendition,
        "extraction_method": "pypdf-text-v1",
        "annotation_method": "manual-exact-extraction-line-selection",
        "clinical_review": "not_performed",
    }


def preview_saved_document(raw: bytes, filename: str,
                           frozen_rendition: dict | None = None) -> dict:
    """Validate an existing original and its server-owned frozen display text.

    A PDF correction must use the rendition reviewed at intake. Reconstructing
    indices and hashes from its saved page strings does not run a PDF parser.
    Keep the saved extractor descriptor in the digest even if the installed
    extractor has since changed. This checks ledger consistency, not clinical
    correctness, visual fidelity, or authenticity of the uploaded document.
    """
    filename = safe_filename(filename)
    if filename.lower().endswith(".txt"):
        if frozen_rendition is not None:
            raise InvalidInput("Plain-text annotations cannot use a PDF rendition")
        return preview_text(raw, filename)
    if (not isinstance(raw, bytes) or not raw or len(raw) > MAX_SOURCE_BYTES or
            not isinstance(frozen_rendition, dict)):
        raise InvalidInput("Saved PDF original or frozen extraction is unavailable")
    original_sha256 = hashlib.sha256(raw).hexdigest()
    original = frozen_rendition.get("original_sha256")
    extraction = frozen_rendition.get("extraction_sha256")
    if (not isinstance(original, str) or not _HASH.fullmatch(original) or
            not hmac.compare_digest(original_sha256, original) or
            not isinstance(extraction, str) or not _HASH.fullmatch(extraction)):
        raise InvalidInput("Saved PDF extraction does not match its original or identity")
    from .pdf_worker import PdfRejected, canonical_json, make_rendition
    try:
        pages = frozen_rendition["pages"]
        if (not isinstance(pages, list) or
                any(not isinstance(page, dict) or not isinstance(page.get("text"), str) for page in pages)):
            raise ValueError("Invalid saved PDF pages")
        derived = make_rendition([page["text"] for page in pages])
        # JSON equality preserves exact key and scalar types, including rejecting
        # a Boolean masquerading as a page/line number. Never trust client anchors.
        for field in ("text", "lines", "pages", "page_count"):
            if canonical_json(frozen_rendition[field]) != canonical_json(derived[field]):
                raise ValueError("Saved PDF page or line identity changed")
        extractor = frozen_rendition["extractor"]
        if (not isinstance(extractor, dict) or not isinstance(extractor.get("name"), str) or
                not isinstance(extractor.get("version"), str)):
            raise ValueError("Saved extractor descriptor is unavailable")
        payload = {field: frozen_rendition[field]
                   for field in ("text", "lines", "pages", "page_count", "extractor")}
        if not hmac.compare_digest(hashlib.sha256(canonical_json(payload)).hexdigest(), extraction):
            raise ValueError("Saved extraction fingerprint changed")
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError, PdfRejected):
        raise InvalidInput("Saved PDF extraction or page anchors are inconsistent") from None
    return {
        "filename": filename, "media_type": "application/pdf",
        "sha256": original_sha256, "byte_count": len(raw), **payload,
        "extraction_sha256": extraction,
        "extraction_method": "pypdf-text-v1",
        "annotation_method": "manual-exact-extraction-line-selection",
        "clinical_review": "not_performed",
    }


def review_saved_document(case_id: str, raw: bytes, filename: str, metadata: dict,
                          findings: list[dict], expected_sha256: str,
                          confirmed_case_id: str,
                          expected_extraction_sha256: str | None = None, *,
                          frozen_rendition: dict | None = None
                          ) -> tuple[ParsedReport, dict]:
    """Review a correction against the saved original/rendition, never a reparse."""
    preview = preview_saved_document(raw, filename, frozen_rendition)
    if preview["media_type"] == "application/pdf":
        if (not isinstance(expected_extraction_sha256, str) or
                not _HASH.fullmatch(expected_extraction_sha256) or
                not hmac.compare_digest(expected_extraction_sha256, preview["extraction_sha256"])):
            raise InvalidInput("PDF extraction changed or extraction SHA-256 is missing; refresh saved selections")
    elif expected_extraction_sha256 is not None:
        raise InvalidInput("An extraction SHA-256 is only accepted for PDF annotations")
    return _review_preview(case_id, raw, preview, metadata, findings,
                           expected_sha256, confirmed_case_id)


def review_text(case_id: str, raw: bytes, filename: str, metadata: dict,
                findings: list[dict], expected_sha256: str,
                confirmed_case_id: str) -> tuple[ParsedReport, dict]:
    """Compatibility entry point; retain the original text review digest."""
    return _review_preview(case_id, raw, preview_text(raw, filename), metadata,
                           findings, expected_sha256, confirmed_case_id)


def review_document(case_id: str, raw: bytes, filename: str, metadata: dict,
                    findings: list[dict], expected_sha256: str,
                    confirmed_case_id: str,
                    expected_extraction_sha256: str | None = None
                    ) -> tuple[ParsedReport, dict, dict | None]:
    """Bind selections to server-extracted bytes, before the write transaction."""
    if not isinstance(confirmed_case_id, str) or confirmed_case_id != case_id:
        raise InvalidInput("Explicit confirmation must match the selected case")
    # Reject an obviously changed original before spending resources parsing it.
    if (not isinstance(raw, bytes) or not isinstance(expected_sha256, str) or
            not _HASH.fullmatch(expected_sha256) or
            not hmac.compare_digest(expected_sha256, hashlib.sha256(raw).hexdigest())):
        raise InvalidInput("Document changed or preview SHA-256 is missing; preview again")
    preview = preview_document(raw, filename)
    rendition = None
    if preview["media_type"] == "application/pdf":
        if (not isinstance(expected_extraction_sha256, str) or
                not _HASH.fullmatch(expected_extraction_sha256) or
                not hmac.compare_digest(expected_extraction_sha256, preview["extraction_sha256"])):
            raise InvalidInput("PDF extraction changed or preview extraction SHA-256 is missing; preview again")
        rendition = {key: preview[key] for key in (
            "text", "lines", "pages", "page_count", "extractor", "extraction_sha256")}
        rendition["original_sha256"] = preview["sha256"]
    elif expected_extraction_sha256 is not None:
        raise InvalidInput("An extraction SHA-256 is only accepted for PDF intake")
    report, receipt = _review_preview(case_id, raw, preview, metadata, findings,
                                     expected_sha256, confirmed_case_id)
    return report, receipt, rendition


def _review_preview(case_id: str, raw: bytes, preview: dict, metadata: dict,
                    findings: list[dict], expected_sha256: str,
                    confirmed_case_id: str) -> tuple[ParsedReport, dict]:
    """Validate an explicit source attachment and exact-line manual selections.

    Confirmation means the operator checked transcription and chose this case.
    It is neither verified patient identity nor credentialed clinical review.
    """
    if not isinstance(confirmed_case_id, str) or confirmed_case_id != case_id:
        raise InvalidInput("Explicit confirmation must match the selected case")
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
            raise InvalidInput("Finding line must identify a numbered preview line")
        if (not isinstance(quote, str) or not quote.strip() or len(quote) > 1200 or
                "\r" in quote or "\n" in quote or quote not in preview["lines"][line - 1]["text"]):
            raise InvalidInput("Finding quote must be an exact nonempty preview-line substring, at most 1200 characters")
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
    # Existing text receipts remain byte-for-byte compatible. PDF review binds
    # both the original and the frozen extraction/configuration, not client text.
    if preview["media_type"] == "application/pdf":
        reviewed["original_sha256"] = preview["sha256"]
        reviewed["extraction_sha256"] = preview["extraction_sha256"]
    receipt = {
        "filename": preview["filename"], "media_type": preview["media_type"],
        "extraction_method": preview["extraction_method"], "annotation_method": preview["annotation_method"],
        "manual_transcription_confirmed": True, "clinical_review": "not_performed",
        "review_sha256": hashlib.sha256(json.dumps(
            reviewed, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
    }
    if preview["media_type"] == "application/pdf":
        receipt["extraction_sha256"] = preview["extraction_sha256"]
    report = ParsedReport(
        case_id, document_id, kind, event_date, issued_at, specimen_id,
        (document_id, amends_version) if amends_version is not None else None,
        tuple(selected), raw)
    return report, receipt
