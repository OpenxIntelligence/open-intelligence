"""Bounded, metadata-only Europe PMC discovery with an offline default.

This adapter accepts a literal public title topic, never a case object. Input
validation constrains syntax; it does not detect PHI. Search results remain
unsaved discovery records, not appraised evidence or licensed article content.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
from http.client import HTTPException
import json
import re
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from tools.crossref_metadata import MetadataInputError, normalize_doi


API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
MAX_BYTES = 256 * 1024
MAX_RESULTS = 25
DEFAULT_RESULTS = 10
TIMEOUT_SECONDS = 8
ADAPTER_VERSION = "europe-pmc-lite/1"
USER_AGENT = "OpenIntelligenceMetadataPrototype/0.1 (https://github.com/OpenxIntelligence/open-intelligence)"
_live_lock = Lock()
_last_request_at: float | None = None


class EuropePMCInputError(ValueError):
    """The caller did not provide the bounded public-topic request contract."""


class EuropePMCUnavailable(ValueError):
    """Upstream transport or metadata cannot be accepted safely."""


class EuropePMCRateLimited(ValueError):
    """Another request is active or a local/provider rate limit applies."""


def _date(value: object, error_type: type[ValueError]) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise error_type("Expected an ISO calendar date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise error_type("Invalid calendar date") from None
    if not 1500 <= parsed.year <= 2200:
        raise error_type("Date is outside the supported range")
    return value


def validate_search_request(data: object) -> dict:
    """Validate literal syntax and bounds, not whether input identifies someone."""
    if not isinstance(data, dict) or set(data) - {"topic", "start_date", "end_date", "page_size"}:
        raise EuropePMCInputError("Only topic, start_date, end_date and page_size are accepted")
    topic = data.get("topic")
    if (not isinstance(topic, str) or len(topic) > 120 or
            not re.fullmatch(r"[A-Za-z0-9 -]+", topic)):
        raise EuropePMCInputError("Use a public title topic: 1–120 ASCII letters, numbers, spaces or hyphens")
    topic = " ".join(topic.split())
    if not topic or not any(c.isalnum() for c in topic):
        raise EuropePMCInputError("A public title topic is required")
    size = data.get("page_size", DEFAULT_RESULTS)
    if type(size) is not int or not 1 <= size <= MAX_RESULTS:
        raise EuropePMCInputError("page_size must be an integer between 1 and 25")
    start, end = data.get("start_date"), data.get("end_date")
    if (start is None) != (end is None):
        raise EuropePMCInputError("Provide both start_date and end_date, or neither")
    if start is not None:
        start = _date(start, EuropePMCInputError)
        end = _date(end, EuropePMCInputError)
        if start > end:
            raise EuropePMCInputError("start_date must not follow end_date")
    return {"topic": topic, "start_date": start, "end_date": end, "page_size": size}


def build_query(data: dict) -> str:
    request = validate_search_request(data)
    # Validation excludes quote/backslash/operator syntax. The entire topic is
    # a literal title phrase; the caller cannot override the MED source filter.
    query = 'SRC:MED AND TITLE:"' + request["topic"] + '"'
    if request["start_date"] is not None:
        query += f' AND FIRST_PDATE:[{request["start_date"]} TO {request["end_date"]}]'
    return query


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def _text(value: object, field: str, limit: int, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if (not isinstance(value, str) or not value.strip() or len(value) > limit or
            any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value)):
        raise EuropePMCUnavailable(f"Invalid provider {field}")
    return value.strip()


def _project_record(raw: object) -> dict:
    if not isinstance(raw, dict) or raw.get("source") != "MED":
        raise EuropePMCUnavailable("Unexpected provider source; only MED is supported")
    identity = raw.get("id")
    if not isinstance(identity, str) or not re.fullmatch(r"[1-9][0-9]{0,11}", identity):
        raise EuropePMCUnavailable("Invalid provider record identifier")
    pmid = raw.get("pmid")
    if pmid is not None and pmid != identity:
        raise EuropePMCUnavailable("Provider PMID does not match its MED record identifier")
    pmcid = raw.get("pmcid")
    if pmcid is not None and (not isinstance(pmcid, str) or not re.fullmatch(r"PMC[1-9][0-9]{0,11}", pmcid)):
        raise EuropePMCUnavailable("Invalid provider PMCID")
    doi = raw.get("doi")
    if doi is not None:
        try:
            doi = normalize_doi(doi)
        except MetadataInputError:
            raise EuropePMCUnavailable("Invalid provider DOI") from None
    year = raw.get("pubYear")
    if year is not None:
        if not isinstance(year, str) or not re.fullmatch(r"[0-9]{4}", year) or not 1500 <= int(year) <= 2200:
            raise EuropePMCUnavailable("Invalid provider publication year")
        year = int(year)
    first_date = raw.get("firstPublicationDate")
    if first_date is not None:
        first_date = _date(first_date, EuropePMCUnavailable)
    record = {
        "source": "MED", "id": identity, "pmid": pmid, "pmcid": pmcid, "doi": doi,
        "title": _text(raw.get("title"), "title", 1000, required=True),
        "authors": _text(raw.get("authorString"), "authors", 4000),
        "journal": _text(raw.get("journalTitle"), "journal", 300),
        "year": year, "first_publication_date": first_date,
    }
    # This hashes only the selected metadata, not the provider body or paper.
    record["metadata_sha256"] = _hash(record)
    record["canonical_url"] = "https://europepmc.org/article/MED/" + identity
    return record


def project_search(payload: object, search: dict, *, retrieved_at: str | None = None) -> dict:
    """Project one page; no abstract, raw link, rights assertion or cursor survives."""
    request = validate_search_request(search)
    if not isinstance(payload, dict) or type(payload.get("hitCount")) is not int or payload["hitCount"] < 0:
        raise EuropePMCUnavailable("Unexpected Europe PMC response envelope")
    collection = payload.get("resultList")
    records = collection.get("result") if isinstance(collection, dict) else None
    hits = payload["hitCount"]
    if (not isinstance(records, list) or len(records) > request["page_size"] or
            hits < len(records) or (hits > 0 and not records)):
        raise EuropePMCUnavailable("Invalid or incomplete Europe PMC result page")
    results = [_project_record(record) for record in records]
    if len({record["id"] for record in results}) != len(results):
        raise EuropePMCUnavailable("Duplicate provider record identifier")
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        if not isinstance(timestamp, str) or len(timestamp) > 64 or datetime.fromisoformat(timestamp).utcoffset() is None:
            raise ValueError
    except ValueError:
        raise EuropePMCUnavailable("Invalid retrieval timestamp") from None
    return {
        "kind": "bibliographic_discovery", "mode": "live", "hit_count": hits,
        "returned_count": len(results), "has_more": hits > len(results), "results": results,
        "provenance": {
            "provider": "Europe PMC REST API", "adapter_version": ADAPTER_VERSION,
            "retrieved_at": timestamp, "endpoint": API_URL,
            "query_fingerprint": _hash(request), "rights_status": "unassessed",
            "content_scope": "bibliographic_metadata_only",
            "access_policy": "https://europepmc.org/RestfulWebService",
            "copyright_policy": "https://europepmc.org/copyright",
            "date_precision": "Provider-normalized dates may include inferred month or day",
        },
        "clinical_evidence_appraised": False, "abstract_included": False,
        "full_text_included": False, "saved_to_ledger": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public_topic(search: dict, *, opener=None) -> dict:
    """Perform one fixed-host lookup. Callers must explicitly opt into live mode.

    One request per second per process, one active request, 8-second transport
    timeout, one page and a 256 KiB body. No retries or redirects are followed.
    """
    global _last_request_at
    request = validate_search_request(search)
    params = {"query": build_query(request), "format": "json", "resultType": "lite",
              "pageSize": request["page_size"], "cursorMark": "*"}
    outbound = Request(API_URL + "?" + urlencode(params), headers={
        "User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Encoding": "identity"})
    if not _live_lock.acquire(blocking=False):
        raise EuropePMCRateLimited("A public topic lookup is already active; retry later")
    try:
        now = monotonic()
        if _last_request_at is not None and now - _last_request_at < 1.0:
            raise EuropePMCRateLimited("Public topic lookup is rate limited; retry later")
        _last_request_at = now
        transport = opener or build_opener(_NoRedirect())
        try:
            with transport.open(outbound, timeout=TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise EuropePMCUnavailable("Europe PMC returned an unexpected status")
                if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                    raise EuropePMCUnavailable("Europe PMC did not return JSON")
                raw = response.read(MAX_BYTES + 1)
        except HTTPError as error:
            error.close()
            if error.code == 429:
                raise EuropePMCRateLimited("Europe PMC rate limit reached; retry later") from None
            raise EuropePMCUnavailable("Europe PMC metadata lookup unavailable") from None
        except (URLError, OSError, HTTPException):
            raise EuropePMCUnavailable("Europe PMC metadata lookup unavailable") from None
        if len(raw) > MAX_BYTES:
            raise EuropePMCUnavailable("Europe PMC response exceeds the metadata size limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise EuropePMCUnavailable("Malformed Europe PMC JSON") from None
        return project_search(payload, request)
    finally:
        _live_lock.release()


def demo_search() -> dict:
    """An original UI demonstration: no publication identifiers or fake links."""
    records = []
    for identity, title in (
        ("OI-DEMO-CITATION-1", "Fictional example: inspecting research sources over time"),
        ("OI-DEMO-CITATION-2", "Fictional example: documenting unanswered research questions"),
    ):
        record = {"source": "DEMO", "id": identity, "pmid": None, "pmcid": None, "doi": None,
                  "title": title, "authors": "A. Example; B. Invented", "journal": "Authored demonstration",
                  "year": 2026, "first_publication_date": None}
        record["metadata_sha256"] = _hash(record)
        record["canonical_url"] = None
        records.append(record)
    return {
        "kind": "bibliographic_discovery", "mode": "offline_demo", "hit_count": len(records),
        "returned_count": len(records), "has_more": False, "results": records,
        "provenance": {"provider": "Open Intelligence authored demonstration",
                       "adapter_version": ADAPTER_VERSION, "retrieved_at": None,
                       "endpoint": None, "query_fingerprint": None, "rights_status": "unassessed",
                       "content_scope": "fictional_demonstration_metadata"},
        "clinical_evidence_appraised": False, "abstract_included": False,
        "full_text_included": False, "saved_to_ledger": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Public title-topic discovery; metadata only, offline by default")
    parser.add_argument("topic", nargs="?", help="Literal public topic, never patient details; syntax checks do not detect PHI")
    parser.add_argument("--live", action="store_true", help="Explicitly send a public topic to Europe PMC")
    parser.add_argument("--start-date", help="First-publication range start, YYYY-MM-DD; pair with --end-date")
    parser.add_argument("--end-date", help="First-publication range end, YYYY-MM-DD")
    parser.add_argument("--page-size", type=int, default=DEFAULT_RESULTS, help="One page, 1–25 records")
    args = parser.parse_args()
    try:
        if args.live:
            result = fetch_public_topic({"topic": args.topic, "start_date": args.start_date,
                                         "end_date": args.end_date, "page_size": args.page_size})
        else:
            if args.topic is not None or args.start_date is not None or args.end_date is not None or args.page_size != DEFAULT_RESULTS:
                raise EuropePMCInputError("A topic or search options require explicit --live; omit them for the offline demonstration")
            result = demo_search()
    except (EuropePMCInputError, EuropePMCUnavailable, EuropePMCRateLimited) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
