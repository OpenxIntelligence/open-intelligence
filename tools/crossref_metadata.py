"""Metadata-only Crossref DOI lookup. No patient data, abstracts, or clinical appraisal.

The narrow, deterministic projection intentionally drops unknown or copyrighted
fields. Live mode is explicitly opt-in; offline fixture mode is the default
development path. This module does not create case-level evidence assertions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

API_ROOT = "https://api.crossref.org/works/"
POLICY_URL = "https://www.crossref.org/documentation/retrieve-metadata/"
ACCESS_URL = "https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/"
USER_AGENT = "OpenIntelligenceMetadataPrototype/0.1 (https://github.com/OpenxIntelligence/open-intelligence)"
MAX_BYTES = 256 * 1024
# An intentionally conservative, ASCII-only subset of valid DOI syntax.
DOI_PATTERN = re.compile(r"10\.[0-9]{4,9}/[A-Za-z0-9._;()/+\-]{1,200}\Z")
CONTACT_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\Z")


class MetadataInputError(ValueError):
    """A DOI, source payload or field violates the metadata-only contract."""


def normalize_doi(value: str) -> str:
    if not isinstance(value, str) or not DOI_PATTERN.fullmatch(value):
        raise MetadataInputError("Expected a public ASCII DOI identifier, not free text or patient data")
    if len(value) > 256:
        raise MetadataInputError("DOI is too long")
    return value.lower()


def _short_text(value: object, *, limit: int, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise MetadataInputError(f"{field} must be a nonempty bounded string")
    if any(ord(c) < 32 for c in value):
        raise MetadataInputError(f"{field} contains disallowed control characters")
    return value.strip()


def _first_text(value: object, *, limit: int, field: str, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, list) or len(value) == 0:
        if required:
            raise MetadataInputError(f"{field} is missing")
        return None
    return _short_text(value[0], limit=limit, field=field)


def _year(message: dict) -> int | None:
    for key in ("issued", "published", "published-print", "published-online"):
        obj = message.get(key)
        if not isinstance(obj, dict):
            continue
        parts = obj.get("date-parts")
        if (isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0] and
                type(parts[0][0]) is int and 1500 <= parts[0][0] <= 2200):
            return parts[0][0]
    return None


def project_work(payload: dict, requested_doi: str, *, retrieved_at: str | None = None) -> dict:
    """Allowlist factual fields from one Crossref record, dropping every other key.

    The provider's abstract and full-text links must never be passed through.
    A bibliographic entry is not evidence that any clinical hypothesis is true.
    """
    doi = normalize_doi(requested_doi)
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        raise MetadataInputError("Unexpected Crossref response envelope")
    message = payload.get("message")
    if not isinstance(message, dict):
        raise MetadataInputError("Missing Crossref message")
    provided = normalize_doi(message.get("DOI"))
    if provided != doi:
        raise MetadataInputError("Crossref record DOI does not match requested identifier")
    title = _first_text(message.get("title"), limit=500, field="title", required=True)
    journal = _first_text(message.get("container-title"), limit=300, field="journal")
    kind = message.get("type")
    if kind is not None:
        kind = _short_text(kind, limit=90, field="type")
    authors = []
    raw_authors = message.get("author", [])
    if not isinstance(raw_authors, list):
        raise MetadataInputError("Invalid authors collection")
    if len(raw_authors) > 100:
        raise MetadataInputError("Too many authors to display safely")
    for entry in raw_authors:
        if not isinstance(entry, dict):
            raise MetadataInputError("Invalid author entry")
        given = entry.get("given", "")
        family = entry.get("family", "")
        if not isinstance(given, str) or not isinstance(family, str):
            raise MetadataInputError("Invalid author name")
        if not given.strip() and not family.strip():
            continue
        name = _short_text((" ".join([given.strip(), family.strip()])).strip(),
                           limit=150, field="author name")
        authors.append(name)
    timestamp = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not isinstance(timestamp, str) or len(timestamp) > 64:
        raise MetadataInputError("Invalid retrieval timestamp")
    # Construct destinations only from the validated DOI, never source HTML/URLs.
    encoded = quote(doi, safe="")
    return {
        "kind": "bibliographic_metadata_only",
        "doi": doi,
        "title": title,
        "journal": journal,
        "year": _year(message),
        "publication_type": kind,
        "authors": authors,
        "canonical_url": "https://doi.org/" + encoded,
        "source": {
            "provider": "Crossref REST API",
            "retrieved_at": timestamp,
            "record_url": API_ROOT + encoded,
            "rights_basis": POLICY_URL,
            "access_policy": ACCESS_URL,
            "scope": "bibliographic facts only; Crossref-generated data CC0",
        },
        "clinical_evidence_appraised": False,
        "copyrighted_abstract_included": False,
    }


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_public_doi(doi: str, *, contact: str | None = None, opener=None) -> dict:
    """Fetch exactly one public DOI with bounded JSON and no redirect following.

    No case/question contents can be passed: only an ASCII DOI identifier.
    This is not a patient-specific search endpoint.
    """
    doi = normalize_doi(doi)
    if contact is not None:
        if not isinstance(contact, str) or not CONTACT_PATTERN.fullmatch(contact) or len(contact) > 180:
            raise MetadataInputError("Provide a valid public contact email for the polite pool")
    url = API_ROOT + quote(doi, safe="")
    if contact:
        url += "?" + urlencode({"mailto": contact})
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    transport = opener or build_opener(_NoRedirect())
    try:
        with transport.open(request, timeout=8) as response:
            content_type = response.headers.get("Content-Type", "")
            if "application/json" not in content_type.lower():
                raise MetadataInputError("Crossref did not return JSON")
            data = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as error:
        raise MetadataInputError(f"Crossref metadata lookup unavailable ({type(error).__name__})") from None
    if len(data) > MAX_BYTES:
        raise MetadataInputError("Crossref response exceeds metadata size limit")
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MetadataInputError("Malformed Crossref JSON") from None
    return project_work(payload, doi)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crossref bibliography-only lookup; not clinical evidence")
    parser.add_argument("doi", help="Public DOI identifier only (no free-text patient queries)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", type=Path, help="Read a reviewed local JSON fixture without network access")
    mode.add_argument("--live", action="store_true", help="Explicitly fetch metadata from Crossref")
    parser.add_argument("--contact", help="Optional operator contact email for Crossref polite pool")
    args = parser.parse_args()
    try:
        if args.live:
            result = fetch_public_doi(args.doi, contact=args.contact)
        else:
            if args.contact:
                raise MetadataInputError("--contact is only meaningful with --live")
            raw = args.fixture.read_bytes()
            if len(raw) > MAX_BYTES:
                raise MetadataInputError("Fixture exceeds size limit")
            result = project_work(json.loads(raw.decode("utf-8")), args.doi)
    except (MetadataInputError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
