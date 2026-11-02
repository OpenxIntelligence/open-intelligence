"""Bounded public bibliographic discovery, without patient or evidence ingestion.

Only call with independently human-authored, public biomedical search terms.
The attestations below are caller obligations, not a patient-data detector.
Results are discovery candidates, not rights receipts or clinical evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from http.client import HTTPException
from typing import Any, Callable, Literal, NotRequired, TypedDict
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ADAPTER_VERSION = "1"
MAX_QUERY_LENGTH = 240
MAX_PAGE_SIZE = 10
MAX_RESPONSE_BYTES = 256 * 1024
TIMEOUT_SECONDS = 8
CLINICAL_USE = "not evidence for a clinical conclusion"

_QUERY = re.compile(r"[A-Za-z0-9 ()+/'\",\-]+\Z")
_PMID = re.compile(r"[1-9][0-9]{0,9}\Z")
_PMCID = re.compile(r"PMC[1-9][0-9]{0,9}\Z")
_DOI = re.compile(r"10\.[0-9]{4,9}/[A-Za-z0-9._;()/+\-]{1,200}\Z")
_VERSION = re.compile(r"[0-9]{1,3}(?:\.[0-9]{1,3}){0,3}\Z")
_INTEGRITY_LABEL = re.compile(r"retract|erratum|correct(?:ion|ed)|expression of concern", re.I)


class CitationIdentifiers(TypedDict):
    pmid: str | None
    pmcid: str | None
    doi: str | None


class ProviderMarker(TypedDict):
    field: str
    value: str
    related_source: NotRequired[str]
    related_id: NotRequired[str]


class PublicationIntegrity(TypedDict):
    status: Literal["unknown", "provider_markers_present"]
    markers: list[ProviderMarker]


class Citation(TypedDict):
    citation_id: str
    source_database: Literal["MED", "PMC"]
    source_record_id: str
    identifiers: CitationIdentifiers
    title: str
    authors: str | None
    journal: str | None
    publication_year: int | None
    first_publication_date: str | None
    date_precision: Literal["unknown", "provider_may_impute_month_or_day"]
    publication_types: list[str]
    integrity: PublicationIntegrity
    record_url: str
    metadata_sha256: str
    metadata_only: Literal[True]
    clinical_evidence_appraised: Literal[False]
    clinical_use: str
    rights_status: Literal["not_assessed"]


class LiteratureSearchResult(TypedDict):
    provider: Literal["europe_pmc"]
    endpoint: str
    adapter_version: str
    provider_api_version: str | None
    retrieved_at: str
    response_sha256: str
    provider_hit_count: int
    returned_record_count: int
    excluded_counts: dict[str, int]
    citations: list[Citation]
    metadata_only: Literal[True]
    clinical_evidence_appraised: Literal[False]
    clinical_use: str
    rights_status: Literal["not_assessed"]


class LiteratureError(ValueError):
    """Safe, query-free failure. ``code`` is suitable for local diagnostics."""

    def __init__(self, code: str):
        self.code = code
        messages = {
            "invalid_input": "Public human-authored terms and bounded search options are required.",
            "transport_failed": "Bibliographic metadata service could not be reached safely.",
            "invalid_response": "Bibliographic metadata service returned an unsupported response.",
            "response_too_large": "Bibliographic metadata response exceeds the byte limit.",
            "invalid_clock": "A timezone-aware retrieval clock is required.",
        }
        super().__init__(messages[code])


class _InvalidRecord(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _text(value: Any, limit: int, *, required: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            raise _InvalidRecord("invalid_metadata")
        return None
    if (not isinstance(value, str) or len(value) > limit or not value.strip()
            or any(unicodedata.category(char).startswith("C") for char in value)):
        raise _InvalidRecord("invalid_metadata")
    return value.strip()


def _id(value: Any, pattern: re.Pattern, *, required: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            raise _InvalidRecord("missing_identifier")
        return None
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _InvalidRecord("invalid_identifier")
    return value


def _identity(record: dict) -> tuple[str, str]:
    source = record.get("source")
    if source not in ("MED", "PMC"):
        raise _InvalidRecord("unsupported_source")
    identifier = _id(record.get("id"), _PMID if source == "MED" else _PMCID, required=True)
    return source, identifier


def _publication_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError
    except ValueError:
        raise _InvalidRecord("invalid_metadata") from None
    return value


def _publication_year(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if type(value) not in (str, int) or not re.fullmatch(r"[12][0-9]{3}", str(value)):
        raise _InvalidRecord("invalid_metadata")
    return int(value)


def _types_and_integrity(record: dict) -> tuple[list[str], PublicationIntegrity]:
    raw = _text(record.get("pubType"), 2048)
    types = list(dict.fromkeys(part.strip() for part in raw.split(";") if part.strip())) if raw else []
    markers: list[ProviderMarker] = [
        {"field": "pubType", "value": value} for value in types if _INTEGRITY_LABEL.search(value)
    ]
    core_types = record.get("pubTypeList")
    if core_types is not None:
        values = core_types.get("pubType") if isinstance(core_types, dict) else None
        if not isinstance(values, list) or len(values) > 20:
            raise _InvalidRecord("invalid_metadata")
        for value in values:
            value = _text(value, 100, required=True)
            if value not in types:
                types.append(value)
            if _INTEGRITY_LABEL.search(value):
                markers.append({"field": "pubTypeList.pubType", "value": value})
    if len(types) > 20 or any(len(value) > 100 for value in types):
        raise _InvalidRecord("invalid_metadata")
    # Normally core-only. Preserve explicit relationship metadata if supplied
    # unexpectedly; discard the free-text reference/note and all content.
    corrections = record.get("commentCorrectionList")
    if corrections is not None:
        if not isinstance(corrections, dict):
            raise _InvalidRecord("invalid_metadata")
        entries = corrections.get("commentCorrection")
        if not isinstance(entries, list) or len(entries) > 20:
            raise _InvalidRecord("invalid_metadata")
        for entry in entries:
            if not isinstance(entry, dict):
                raise _InvalidRecord("invalid_metadata")
            value = _text(entry.get("type"), 100, required=True)
            marker: ProviderMarker = {"field": "commentCorrectionList.type", "value": value}
            if entry.get("source") is not None or entry.get("id") is not None:
                source, identifier = _identity(entry)
                marker.update(related_source=source, related_id=identifier)
            markers.append(marker)
    return types, {"status": "provider_markers_present" if markers else "unknown", "markers": markers}


def _project_record(record: dict) -> Citation:
    source, identifier = _identity(record)
    pmid = _id(record.get("pmid"), _PMID)
    pmcid = _id(record.get("pmcid"), _PMCID)
    own_id = pmid if source == "MED" else pmcid
    if own_id is not None and own_id != identifier:
        raise _InvalidRecord("invalid_identifier")
    pmid = identifier if source == "MED" else pmid
    pmcid = identifier if source == "PMC" else pmcid
    doi = _id(record.get("doi"), _DOI)
    if doi and len(doi) > 256:
        raise _InvalidRecord("invalid_identifier")
    types, integrity = _types_and_integrity(record)
    published = _publication_date(record.get("firstPublicationDate"))
    citation = {
        "citation_id": f"europepmc:{source}:{identifier}",
        "source_database": source, "source_record_id": identifier,
        "identifiers": {"pmid": pmid, "pmcid": pmcid, "doi": doi.lower() if doi else None},
        "title": _text(record.get("title"), 1000, required=True),
        "authors": _text(record.get("authorString"), 4000),
        "journal": _text(record.get("journalTitle"), 300),
        "publication_year": _publication_year(record.get("pubYear")),
        "first_publication_date": published,
        "date_precision": "provider_may_impute_month_or_day" if published else "unknown",
        "publication_types": types, "integrity": integrity,
        "record_url": f"https://europepmc.org/article/{source}/{identifier}",
        "metadata_only": True, "clinical_evidence_appraised": False,
        "clinical_use": CLINICAL_USE, "rights_status": "not_assessed",
    }
    canonical = json.dumps(citation, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    citation["metadata_sha256"] = hashlib.sha256(canonical).hexdigest()
    return citation


def _read_response(request: Request, opener: Any) -> bytes:
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status != 200 or response.geturl() != request.full_url:
                raise LiteratureError("invalid_response")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
            if content_type != "application/json" or encoding != "identity":
                raise LiteratureError("invalid_response")
            length = response.headers.get("Content-Length")
            if length is not None:
                if not isinstance(length, str) or not re.fullmatch(r"[0-9]{1,10}", length):
                    raise LiteratureError("invalid_response")
                if int(length) > MAX_RESPONSE_BYTES:
                    raise LiteratureError("response_too_large")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if not isinstance(raw, bytes):
                raise LiteratureError("invalid_response")
            if len(raw) > MAX_RESPONSE_BYTES:
                raise LiteratureError("response_too_large")
            return raw
    except LiteratureError:
        raise
    except HTTPError as error:
        error.close()
        raise LiteratureError("transport_failed") from None
    except (OSError, HTTPException, ValueError, AttributeError, TypeError):
        raise LiteratureError("transport_failed") from None


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _no_nonfinite(value: str) -> None:
    raise ValueError


def search_europe_pmc(
    terms: str, *, human_authored: bool = False, public_terms_only: bool = False,
    page_size: int = 5, opener: Any = None,
    clock: Callable[[], datetime] | None = None,
) -> LiteratureSearchResult:
    """Fetch one bounded metadata page; never follow provider-supplied URLs.

    Terms must be manually authored without patient/case context. The restricted
    ASCII grammar accepts words, numbers, spaces and ()+/'",- punctuation; it
    excludes URLs, email addresses, field selectors and control characters.
    This grammar cannot identify private information. The trusted caller must
    enforce public-only input before this function is reachable.

    ``opener`` and ``clock`` are trusted offline-test seams, not user options.
    No result contains the query, abstract, full text, content links or license.
    """
    if (human_authored is not True or public_terms_only is not True
            or not isinstance(terms, str) or not 3 <= len(terms) <= MAX_QUERY_LENGTH
            or not _QUERY.fullmatch(terms) or not re.search(r"[A-Za-z]", terms)
            or "//" in terms or len(terms.strip()) < 3
            or type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE):
        raise LiteratureError("invalid_input")
    query = " ".join(terms.split())
    request = Request(ENDPOINT + "?" + urlencode({
        "query": query, "format": "json", "resultType": "lite",
        "pageSize": page_size, "cursorMark": "*", "synonym": "false",
    }), headers={"Accept": "application/json", "Accept-Encoding": "identity",
                 "User-Agent": "OpenIntelligenceMetadataPrototype/1"})
    raw = _read_response(request, build_opener(_NoRedirect()) if opener is None else opener)
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_no_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        raise LiteratureError("invalid_response") from None
    if not isinstance(data, dict) or "errMsg" in data or "errCode" in data:
        raise LiteratureError("invalid_response")
    count = data.get("hitCount")
    result_list = data.get("resultList")
    records = result_list.get("result") if isinstance(result_list, dict) else None
    version = data.get("version")
    if (type(count) is not int or count < 0 or not isinstance(records, list)
            or len(records) > min(page_size, count) or any(not isinstance(row, dict) for row in records)
            or (version is not None and (not isinstance(version, str) or not _VERSION.fullmatch(version)))):
        raise LiteratureError("invalid_response")
    citations: list[Citation] = []
    excluded: dict[str, int] = {}
    seen = set()
    for record in records:
        try:
            citation = _project_record(record)
            if citation["citation_id"] in seen:
                raise _InvalidRecord("duplicate_identifier")
            seen.add(citation["citation_id"])
            citations.append(citation)
        except _InvalidRecord as error:
            code = str(error)
            excluded[code] = excluded.get(code, 0) + 1
    now = clock() if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise LiteratureError("invalid_clock")
    return {
        "provider": "europe_pmc", "endpoint": ENDPOINT, "adapter_version": ADAPTER_VERSION,
        "provider_api_version": version, "retrieved_at": now.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "response_sha256": hashlib.sha256(raw).hexdigest(), "provider_hit_count": count,
        "returned_record_count": len(records), "excluded_counts": excluded, "citations": citations,
        "metadata_only": True, "clinical_evidence_appraised": False,
        "clinical_use": CLINICAL_USE, "rights_status": "not_assessed",
    }
