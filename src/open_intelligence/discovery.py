"""Fictional literature/trials discovery records.

This module is deliberately deterministic and model-free: it parses
independently authored fixture text, enforces a fail-closed language guard,
and projects records that are always labelled fictional. It performs no live
fetching, no eligibility or efficacy inference, and no treatment-relevance
determination. A literature DOI here is an identifier only; bibliographic
metadata for a DOI is served separately by the existing Crossref metadata-only
path, which never passes abstracts or full-text links through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ID = re.compile(r"[A-Z][A-Z0-9-]{1,39}\Z")
# Same conservative ASCII subset as the Crossref metadata-only path. This is a
# syntax check on a fictional identifier, not a Crossref lookup.
DOI_PATTERN = re.compile(r"10\.[0-9]{4,9}/[A-Za-z0-9._;()/+\-]{1,200}\Z")
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")

# Words that would turn a fictional listing into an inferred clinical claim.
# Fail closed: any occurrence in a title, summary, or link rationale rejects
# the record. A human reviewer rewords the fixture; the guard never repairs it.
BANNED_TERMS = frozenset({
    "eligible", "eligibility", "effective", "efficacy",
    "recommended", "proven", "benefit",
})

DISCLAIMER = (
    "Fictional demonstration record. Not a real trial or publication. "
    "No eligibility, efficacy, or treatment relevance is inferred. "
    "A registry listing does not confirm recruitment availability."
)

APPLICABILITY = frozenset({"applicable", "limited", "not_applicable", "unknown"})


class DiscoveryInputError(ValueError):
    """A discovery fixture or link request violates the discovery contract."""


@dataclass(frozen=True)
class ParsedDiscovery:
    discovery_key: str
    kind: str
    title: str
    registry_id: str | None
    doi: str | None
    issued_at: str
    summary: str
    raw: bytes


def _check_language(field: str, value: str) -> None:
    lowered = value.lower()
    for term in sorted(BANNED_TERMS):
        if term in lowered:
            raise DiscoveryInputError(
                f"{field} contains a guarded clinical-claim term ({term}); "
                "discovery records must not infer eligibility, efficacy, or benefit"
            )


def parse_discovery(raw: bytes) -> ParsedDiscovery:
    """Parse one OI-SYNTHETIC-DISCOVERY/1 fixture.

    Strict field set: any unknown field — including an Abstract field — is
    rejected, so copyrighted article text can never enter through this path.
    Trials carry a Registry-Id and a fixed Status of not-verified; literature
    carries a DOI and no registry id. No other combination is accepted.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 32768:
        raise DiscoveryInputError("Discovery fixture must be nonempty UTF-8, at most 32 KiB")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise DiscoveryInputError("Discovery fixture must be UTF-8") from None
    if "\r" in text or "\x00" in text:
        raise DiscoveryInputError("CR and NUL are not supported")
    lines = text.splitlines()
    if not lines or lines[0] != "OI-SYNTHETIC-DISCOVERY/1":
        raise DiscoveryInputError("Only OI-SYNTHETIC-DISCOVERY/1 is accepted")
    allowed = {"Discovery", "Kind", "Title", "Registry-Id", "DOI", "Issued-At",
               "Rights", "Status", "Summary"}
    values: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        if ": " not in line:
            raise DiscoveryInputError(f"Discovery line {line_number}: expected 'Field: value'")
        label, value = line.split(": ", 1)
        if label not in allowed or label in values or not value.strip():
            raise DiscoveryInputError(
                f"Discovery line {line_number}: unknown, duplicate, or empty field")
        values[label] = value.strip()
    if not {"Discovery", "Kind", "Title", "Issued-At", "Rights", "Summary"} <= values.keys():
        raise DiscoveryInputError(
            "Discovery requires Discovery, Kind, Title, Issued-At, Rights, Summary")
    if values["Rights"] != "original-synthetic":
        raise DiscoveryInputError("Only explicitly original synthetic fixture text is supported")
    key = values["Discovery"]
    if not ID.fullmatch(key):
        raise DiscoveryInputError("Invalid discovery identifier; use uppercase A-Z, numbers and hyphens")
    kind = values["Kind"]
    if kind not in {"trial", "literature"}:
        raise DiscoveryInputError("Discovery Kind must be trial or literature")
    title = values["Title"]
    if not 4 <= len(title) <= 180:
        raise DiscoveryInputError("Discovery title must have 4-180 characters")
    issued_at = values["Issued-At"]
    if not DATE_PATTERN.fullmatch(issued_at):
        raise DiscoveryInputError("Dates must use YYYY-MM-DD")
    summary = values["Summary"]
    if not 10 <= len(summary) <= 600:
        raise DiscoveryInputError("Discovery summary must have 10-600 characters")
    registry_id = None
    doi = None
    if kind == "trial":
        if values.get("Status") != "not-verified":
            raise DiscoveryInputError("Trial Status must be not-verified; availability is never confirmed")
        registry_id = values.get("Registry-Id")
        if not registry_id or not ID.fullmatch(registry_id):
            raise DiscoveryInputError("Trial requires a valid Registry-Id")
        if "DOI" in values:
            raise DiscoveryInputError("Trial records do not carry a DOI")
    else:
        if "Registry-Id" in values or "Status" in values:
            raise DiscoveryInputError("Literature records do not carry Registry-Id or Status")
        doi = values.get("DOI")
        if not doi or not DOI_PATTERN.fullmatch(doi):
            raise DiscoveryInputError("Literature requires a valid public DOI identifier")
    _check_language("Title", title)
    _check_language("Summary", summary)
    return ParsedDiscovery(key, kind, title, registry_id, doi.lower() if doi else None,
                           issued_at, summary, raw)


def project_item(row: dict) -> dict:
    """Public projection of a stored discovery item. Never includes an abstract."""
    return {
        "id": row["id"],
        "discovery_key": row["discovery_key"],
        "kind": row["kind"],
        "title": row["title"],
        "registry_id": row["registry_id"],
        "doi": row["doi"],
        "issued_at": row["issued_at"],
        "summary": row["summary"],
        "status": row["status"],
        "fictional": True,
        "disclaimer": DISCLAIMER,
    }
