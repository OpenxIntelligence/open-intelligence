"""Offline evidence metadata contract and isolated SQLite reference index.

Source owner: KaijuCake, Open Intelligence PR #224, commit
57fb58bab63a931874e5e768858d741459aeb7fa; original catalog blob
963e253717c51389669dbbd7d6bed61d8b50c1f8. This bounded integration preserves
that contract while enforcing authoritative case/organization scope, exact
version search, and fail-closed malformed rights state.

The pure EvidenceRecord, metadata_hit, and record_fingerprint helpers are shared
with the PostgreSQL adapter. build_index is an ephemeral offline reference only;
it is not a patient registry or the H1 catalog persistence owner.

Permissions are declarations enforced by the existing rights gate, not proof
of publisher permission or patient access. The host must independently authorize
the action. Metadata lookup and identifier verification do not assess evidence
support, clinical applicability, or model-use rights. No network calls occur.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import asdict, dataclass, replace
from urllib.parse import urlsplit

from open_intelligence.rights import RightsError, normalize_permissions, permitted

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
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-]*\Z")
VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:\-]{0,127}\Z")


class CatalogError(ValueError):
    """A catalog record, query, or index is invalid or unavailable."""


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    source_kind: str
    version: str
    title: str
    terms: tuple[str, ...]
    licence: str
    link: str
    permissions: dict[str, dict[str, str]]
    revoked: bool = False
    superseded: bool = False
    case_id: str | None = None
    organization: str | None = None


@dataclass(frozen=True)
class LookupHit:
    id: str
    version: str
    licence: str
    availability: str
    link: str
    rights_status: str
    title: str | None
    case_id: str | None = None
    organization: str | None = None


def _is_blocked(kind, record_id, link, licence):
    haystacks = (kind.lower(), record_id.lower(), link.lower(), licence.lower())
    return any(token in hay for token in BLOCKED_SOURCES for hay in haystacks)


def _exact_bool(value, default=False):
    """Only exact bools are valid; explicit None is never a default grant.

    The legacy default argument is retained for source compatibility. Missing
    input is defaulted by load_records; every supplied non-bool fails closed.
    """
    return value if type(value) is bool else True


def _scope_text(value):
    return (type(value) is str and bool(value) and value == value.strip()
            and len(value) <= 128 and not any(ord(c) < 32 for c in value))


def _validate_metadata(rec):
    if not isinstance(rec, EvidenceRecord):
        raise CatalogError("EvidenceRecord required")
    if rec.source_kind == "crossref":
        from .crossref_metadata import normalize_doi
        try:
            if normalize_doi(rec.id) != rec.id:
                raise ValueError()
        except (TypeError, ValueError):
            raise CatalogError("Invalid Crossref DOI") from None
    elif type(rec.id) is not str or ID_PATTERN.fullmatch(rec.id) is None:
        raise CatalogError("Invalid record id")
    if type(rec.source_kind) is not str or rec.source_kind not in SOURCE_KINDS:
        raise CatalogError("Unknown source kind")
    if type(rec.version) is not str or VERSION_PATTERN.fullmatch(rec.version) is None:
        raise CatalogError("Record version is required")
    if type(rec.title) is not str or len(rec.title) > 2048:
        raise CatalogError("Invalid metadata title")
    if (type(rec.terms) is not tuple or len(rec.terms) > 64
            or any(type(term) is not str or not term.strip() or len(term) > 256
                   for term in rec.terms)):
        raise CatalogError("Metadata terms must be bounded strings")
    if type(rec.licence) is not str or not rec.licence.strip() or len(rec.licence) > 256:
        raise CatalogError("Invalid licence declaration")
    if type(rec.link) is not str or len(rec.link) > 2048:
        raise CatalogError("Invalid metadata link")
    try:
        parsed = urlsplit(rec.link)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or any(c.isspace() for c in rec.link)):
            raise CatalogError("Record link must be an HTTPS URL")
    except ValueError as exc:
        raise CatalogError("Invalid metadata link") from exc
    if rec.case_id is None and rec.organization is None:
        return
    if not _scope_text(rec.case_id) or not _scope_text(rec.organization):
        raise CatalogError("Scoped records require exact case and organization")


def _validated_record(rec):
    _validate_metadata(rec)
    try:
        permissions = normalize_permissions(rec.permissions)
    except (RightsError, TypeError, ValueError) as exc:
        raise CatalogError("Invalid permissions map") from exc
    return replace(rec, permissions=permissions,
                   revoked=_exact_bool(rec.revoked),
                   superseded=_exact_bool(rec.superseded))


def load_records(raw):
    """Validate records without inferring tenant identity or patient access."""
    if type(raw) is not list:
        raise CatalogError("Catalog input must be a list")
    records = []
    for item in raw:
        if type(item) is not dict:
            raise CatalogError("Catalog record must be an object")
        terms = item.get("terms", [])
        if type(terms) not in (list, tuple):
            raise CatalogError("Metadata terms must be a list")
        record = _validated_record(EvidenceRecord(
            id=item.get("id"), source_kind=item.get("source_kind"),
            version=item.get("version"), title=item.get("title", ""),
            terms=tuple(terms), licence=item.get("licence", "UNKNOWN"),
            link=item.get("link", ""), permissions=item.get("permissions", {}),
            revoked=item.get("revoked", False),
            superseded=item.get("superseded", False),
            case_id=item.get("case_id"), organization=item.get("organization"),
        ))
        if _is_blocked(record.source_kind, record.id, record.link, record.licence):
            raise CatalogError("Blocked source")
        records.append(record)
    return records


def rights_status(rec):
    """Enforce explicit metadata permissions; lifecycle flags never grant them."""
    try:
        rec = _validated_record(rec)
    except CatalogError:
        return "hold"
    if _is_blocked(rec.source_kind, rec.id, rec.link, rec.licence):
        return "blocked"
    if rec.licence.strip().upper() == "UNKNOWN":
        return "hold"
    if not permitted(rec.permissions, "metadata", "store",
                     revoked=rec.revoked, superseded=rec.superseded):
        return "hold"
    return "granted"


def _availability(rec):
    if _exact_bool(rec.revoked):
        return "revoked"
    if _exact_bool(rec.superseded):
        return "superseded"
    if rights_status(rec) != "granted":
        return "withheld"
    return "available"


def _scope_reason(rec, *, case_id, organization):
    """Stored scope is authoritative. Both None denotes global metadata."""
    if rec.case_id is not None and rec.case_id != case_id:
        return "cross_case"
    if rec.organization is not None and rec.organization != organization:
        return "cross_organization"
    if case_id is None and organization is None and rec.case_id is None:
        return None
    if not _scope_text(case_id):
        return "cross_case"
    if not _scope_text(organization):
        return "cross_organization"
    return None


def metadata_hit(rec, *, case_id, organization):
    """Return permitted metadata only, without granting the host any action.

    A global record has no patient scope. A scoped record requires its exact
    stored case and organization. A missing host context can reveal global
    records only. Title display remains independent from metadata storage.
    """
    try:
        rec = _validated_record(rec)
    except CatalogError:
        return None
    if _scope_reason(rec, case_id=case_id, organization=organization) is not None:
        return None
    if rights_status(rec) != "granted":
        return None
    title = rec.title if permitted(
        rec.permissions, "metadata", "display",
        revoked=rec.revoked, superseded=rec.superseded) else None
    return LookupHit(rec.id, rec.version, rec.licence, _availability(rec),
                     rec.link, "granted", title, rec.case_id, rec.organization)


def record_fingerprint(rec):
    """Hash exact immutable metadata, excluding separately versioned rights."""
    _validate_metadata(rec)
    identity = {
        "id": rec.id, "source_kind": rec.source_kind, "version": rec.version,
        "title": rec.title, "terms": list(rec.terms), "licence": rec.licence,
        "link": rec.link, "case_id": rec.case_id, "organization": rec.organization,
    }
    return hashlib.sha256(json.dumps(
        identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def fts5_available():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE _probe USING fts5(x)")
        return True
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def build_index(records):
    """Build an ephemeral reference index; one FTS row is one exact record."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            "CREATE TABLE records (id TEXT, version TEXT, organization TEXT,"
            " case_id TEXT, record_json TEXT)"
        )
        has_fts = fts5_available()
        if has_fts:
            conn.execute("CREATE VIRTUAL TABLE fts_terms USING fts5(text)")
        seen = set()
        for record in records:
            rec = _validated_record(record)
            if _is_blocked(rec.source_kind, rec.id, rec.link, rec.licence):
                raise CatalogError("Blocked source")
            key = (rec.id, rec.version, rec.organization, rec.case_id)
            if key in seen:
                raise CatalogError("Duplicate catalog identity")
            seen.add(key)
            cursor = conn.execute(
                "INSERT INTO records VALUES (?,?,?,?,?)",
                (rec.id, rec.version, rec.organization, rec.case_id,
                 json.dumps(asdict(rec), ensure_ascii=False, allow_nan=False)),
            )
            # rowid binds both immutable version and authoritative scope.
            if has_fts and rights_status(rec) == "granted":
                conn.execute("INSERT INTO fts_terms(rowid,text) VALUES (?,?)",
                             (cursor.lastrowid, " ".join(rec.terms)))
        conn.commit()
        return conn
    except Exception:
        conn.close()
        raise


def _decoded_record(record_json):
    return load_records([json.loads(record_json)])[0]


def lookup(conn, query, *, limit=20, case_id=None, organization=None):
    """Return permitted exact-version metadata matching a literal FTS phrase."""
    if not fts5_available():
        raise CatalogError("FTS5 unavailable")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CatalogError("Invalid lookup limit")
    if type(query) is not str or not query.strip():
        return []
    if len(query) > 1024:
        raise CatalogError("Query is too long")
    phrase = '"' + query.replace('"', '""') + '"'
    rows = conn.execute(
        "SELECT r.record_json FROM fts_terms t JOIN records r ON r.rowid=t.rowid"
        " WHERE t.text MATCH ? AND ((r.case_id IS NULL AND r.organization IS NULL)"
        " OR (r.case_id=? AND r.organization=?)) ORDER BY r.rowid LIMIT ?",
        (phrase, case_id, organization, limit),
    ).fetchall()
    hits = [metadata_hit(_decoded_record(row[0]), case_id=case_id,
                         organization=organization) for row in rows]
    return [hit for hit in hits if hit is not None]


def _records_for(conn, record_id, version=None):
    """Internal verifier input, never a metadata disclosure operation."""
    if version is None:
        rows = conn.execute(
            "SELECT record_json FROM records WHERE id=? ORDER BY rowid",
            (record_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT record_json FROM records WHERE id=? AND version=? ORDER BY rowid",
            (record_id, version),
        ).fetchall()
    return [_decoded_record(row[0]) for row in rows]


def get(conn, record_id, version=None, *, case_id=None, organization=None):
    """Return only permitted scoped metadata; never guess among versions."""
    hits = [metadata_hit(rec, case_id=case_id, organization=organization)
            for rec in _records_for(conn, record_id, version)]
    hits = [hit for hit in hits if hit is not None]
    if len(hits) > 1:
        raise CatalogError("Exact unambiguous catalog version required")
    return hits[0] if hits else None
