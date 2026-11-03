"""Offline, rights-gated evidence metadata catalog, issue 117 (WS-06).

This module is the Vision 02 next-slice design, built as a Jarvis
pickup after Vision 02 went down: a pure, offline term lookup over
permitted metadata only, plus the record model the citation verifier
in citation_verifier.py checks against. It is NOT a live fetch, NOT a
vector index, and NOT a claim about any real source's terms.

Rules, fail closed:
- Only fictional fixture records shaped like CIViC, NCI Thesaurus,
  Crossref, ClinicalTrials.gov, or plain fictional metadata are
  loaded. Live connectors for those sources stay HOLD until their
  terms are recorded; this catalog encodes ID patterns and link
  templates only, never source content.
- Blocked families are hard-blocked at load, independent of granted
  rights: nccn, asco, esmo, oncokb, cosmic, umls, snomed, matched
  against source kind, ID, link host, and licence. A blocked record
  is never indexed.
- A record with no version, an unknown source kind, a non-HTTPS
  link, or an invalid permissions map is rejected at load.
- Only records with metadata store permission, a known licence
  (not UNKNOWN), and exact-bool revoked/superseded both False are
  returned by lookup. Revoked or superseded records keep their
  availability in the store so the verifier can report it, but they
  are never lookup hits.
- Exact-bool authorization: revoked and superseded must be bool.
  Any other type (1, "false", [False], None) is treated as revoked.
  This mirrors the PR 150 fix, where only an exact True authorizes.
- Lookup output carries only id, version, licence, availability,
  link, rights_status, and a gated title. Title is emitted only
  when metadata display is also allowed. No abstract, no full text,
  no guideline text, ever.
- SQLite FTS5 is used through the stdlib only. When FTS5 is
  unavailable, lookup raises CatalogError instead of falling back
  to a scan that could surface blocked data.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from open_intelligence.rights import normalize_permissions, permitted

SOURCE_KINDS = frozenset(
    {"civic", "nci_thesaurus", "crossref", "clinicaltrials_gov", "fictional"}
)
AVAILABILITY = frozenset({"available", "withheld", "revoked", "superseded"})
RIGHTS_STATUS = frozenset({"granted", "hold", "blocked"})

BLOCKED_SOURCES = frozenset(
    {"nccn", "asco", "esmo", "oncokb", "cosmic", "umls", "snomed"}
)

LINK_TEMPLATES = {
    "civic": "https://example.invalid/civic/{id}/{version}",
    "nci_thesaurus": "https://example.invalid/nci/{id}/{version}",
    "crossref": "https://example.invalid/crossref/{id}/{version}",
    "clinicaltrials_gov": "https://example.invalid/clinicaltrials/{id}/{version}",
    "fictional": "https://example.invalid/fictional/{id}/{version}",
}

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]*$")


class CatalogError(ValueError):
    """A catalog record, query, or index is invalid or unavailable."""


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    source_kind: str
    version: str
    title: str
    terms: tuple
    licence: str
    link: str
    permissions: dict
    revoked: bool = False
    superseded: bool = False
    case_id: str | None = None


@dataclass(frozen=True)
class LookupHit:
    id: str
    version: str
    licence: str
    availability: str
    link: str
    rights_status: str
    title: str | None


def _is_blocked(kind, record_id, link, licence):
    haystacks = [kind.lower(), record_id.lower(), link.lower(), licence.lower()]
    return any(token in hay for token in BLOCKED_SOURCES for hay in haystacks)


def _exact_bool(value, default=False):
    """Return the bool only when it is exactly a bool, else True (revoked)."""
    if type(value) is bool:
        return value
    if value is None:
        return default
    return True


def fts5_available():
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
        conn.close()
        return True
    except sqlite3.Error:
        return False


def load_records(raw):
    """Validate and normalize a list of raw record dicts, fail closed."""
    if not isinstance(raw, list):
        raise CatalogError("Catalog input must be a list")
    records = []
    for item in raw:
        if not isinstance(item, dict):
            raise CatalogError("Catalog record must be an object")
        record_id = item.get("id")
        kind = item.get("source_kind")
        version = item.get("version")
        title = item.get("title", "")
        terms = item.get("terms", [])
        licence = item.get("licence", "UNKNOWN")
        link = item.get("link", "")
        if not isinstance(record_id, str) or not ID_PATTERN.match(record_id):
            raise CatalogError(f"Invalid record id: {record_id!r}")
        if kind not in SOURCE_KINDS:
            raise CatalogError(f"Unknown source kind: {kind!r}")
        if not isinstance(version, str) or not version.strip():
            raise CatalogError("Record version is required")
        if not isinstance(link, str) or not link.startswith("https://"):
            raise CatalogError("Record link must be an HTTPS URL")
        if _is_blocked(kind, record_id, link, licence):
            raise CatalogError(f"Blocked source: {record_id!r}")
        try:
            permissions = normalize_permissions(item.get("permissions", {}))
        except Exception as exc:
            raise CatalogError(f"Invalid permissions for {record_id!r}: {exc}") from exc
        records.append(
            EvidenceRecord(
                id=record_id,
                source_kind=kind,
                version=version,
                title=title,
                terms=tuple(terms),
                licence=licence,
                link=link,
                permissions=permissions,
                revoked=_exact_bool(item.get("revoked", False)),
                superseded=_exact_bool(item.get("superseded", False)),
                case_id=item.get("case_id"),
            )
        )
    return records


def rights_status(rec):
    if _is_blocked(rec.source_kind, rec.id, rec.link, rec.licence):
        return "blocked"
    if rec.licence == "UNKNOWN":
        return "hold"
    if not permitted(rec.permissions, "metadata", "store",
                     revoked=rec.revoked, superseded=rec.superseded):
        return "hold"
    return "granted"


def _availability(rec):
    if rec.revoked:
        return "revoked"
    if rec.superseded:
        return "superseded"
    if rights_status(rec) != "granted":
        return "withheld"
    return "available"


def build_index(records):
    """Build an in-memory index. All loaded records are stored; only
    granted records are searchable, so the verifier can still report
    hold, revoked, and superseded reasons for stored records."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE records (id TEXT, version TEXT, licence TEXT,"
        " availability TEXT, link TEXT, rights_status TEXT, title TEXT,"
        " case_id TEXT, searchable INTEGER)"
    )
    if fts5_available():
        conn.execute("CREATE VIRTUAL TABLE fts_terms USING fts5(id, text)")
    for rec in records:
        status = rights_status(rec)
        searchable = 1 if status == "granted" else 0
        title = rec.title if permitted(
            rec.permissions, "metadata", "display",
            revoked=rec.revoked, superseded=rec.superseded) else None
        conn.execute(
            "INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?)",
            (rec.id, rec.version, rec.licence, _availability(rec), rec.link,
             status, title, rec.case_id, searchable),
        )
        if searchable and fts5_available():
            conn.execute(
                "INSERT INTO fts_terms VALUES (?,?)",
                (rec.id, " ".join(rec.terms)),
            )
    conn.commit()
    return conn


def lookup(conn, query, *, limit=20):
    """Return granted LookupHits whose terms match the query phrase."""
    if not fts5_available():
        raise CatalogError("FTS5 unavailable")
    if not isinstance(query, str) or not query.strip():
        return []
    phrase = '"' + query.replace('"', '""') + '"'
    rows = conn.execute(
        "SELECT r.id, r.version, r.licence, r.availability, r.link,"
        " r.rights_status, r.title FROM fts_terms t JOIN records r"
        " ON r.id = t.id WHERE t.text MATCH ? AND r.searchable = 1"
        " LIMIT ?",
        (phrase, limit),
    ).fetchall()
    return [LookupHit(*row) for row in rows]


def get(conn, record_id, version=None):
    """Return the stored record row for an id, optionally at a version."""
    if version is None:
        row = conn.execute(
            "SELECT id, version, licence, availability, link, rights_status,"
            " title FROM records WHERE id = ? ORDER BY version DESC LIMIT 1",
            (record_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id, version, licence, availability, link, rights_status,"
            " title FROM records WHERE id = ? AND version = ?",
            (record_id, version),
        ).fetchone()
    return LookupHit(*row) if row else None
