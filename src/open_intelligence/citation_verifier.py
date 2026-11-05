"""Identifier-level citation verification for the #224 evidence contract.

Source owner: KaijuCake, Open Intelligence PR #224, commit
57fb58bab63a931874e5e768858d741459aeb7fa; original verifier blob
8adeb71435dc11ee661a88436e0031c04bfafa57. The pure verify_record helper
allows the H1 PostgreSQL owner to enforce the same rules without SQLite.

Verification checks identity, exact version, authoritative organization/case
scope, current declared rights and availability only. It does not establish
claim support, publisher permission, clinician approval or host authorization.
No link is fetched and no model is called.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from open_intelligence.evidence_catalog import (
    BLOCKED_SOURCES, CatalogError, EvidenceRecord,
    _exact_bool, _records_for, _scope_reason, _validate_metadata, rights_status,
)

CITATION_PATTERN = re.compile(
    r"(FICT-[A-Z0-9\-]+|[0-9]+\.[0-9]+/[^\s@]+|NCT[0-9]+)"
    r"(?:@([A-Za-z0-9][A-Za-z0-9._:\-]{0,127}))?\Z"
)


@dataclass(frozen=True)
class CitationResult:
    citation: str
    ok: bool
    reason: str


def parse_citation(text):
    """Split ID@version without allowing a DOI suffix to consume the version."""
    if type(text) is not str or not text.strip() or len(text) > 512:
        raise ValueError("Citation is malformed")
    match = CITATION_PATTERN.fullmatch(text.strip())
    if not match:
        raise ValueError("Citation is malformed")
    return match.group(1), match.group(2)


def _parsed(citation):
    if type(citation) is not str:
        return None, CitationResult(citation, False, "malformed")
    if any(token in citation.lower() for token in BLOCKED_SOURCES):
        return None, CitationResult(citation, False, "blocked_source")
    try:
        record_id, version = parse_citation(citation)
    except ValueError:
        return None, CitationResult(citation, False, "malformed")
    if version is None:
        return None, CitationResult(citation, False, "no_version")
    return (record_id, version), None


def verify_record(record, citation, *, case_id, organization):
    """Verify one authoritative EvidenceRecord, independent of persistence."""
    parsed, failure = _parsed(citation)
    if failure is not None:
        return failure
    record_id, version = parsed
    if record is None or (isinstance(record, EvidenceRecord) and record.id != record_id):
        return CitationResult(citation, False, "unknown_id")
    try:
        _validate_metadata(record)
    except CatalogError:
        return CitationResult(citation, False, "malformed")
    scope_reason = _scope_reason(record, case_id=case_id, organization=organization)
    if scope_reason is not None:
        return CitationResult(citation, False, scope_reason)
    if record.version != version:
        return CitationResult(citation, False, "version_mismatch")
    if _exact_bool(record.revoked):
        return CitationResult(citation, False, "revoked")
    if _exact_bool(record.superseded):
        return CitationResult(citation, False, "superseded")
    status = rights_status(record)
    if status == "blocked":
        return CitationResult(citation, False, "blocked_source")
    if status != "granted":
        return CitationResult(citation, False, "rights_hold")
    return CitationResult(citation, True, "ok")


def verify_citation(conn, citation, *, case_id, organization=None,
                    record_case_scope=None):
    """Use stored scope; the legacy map may add a veto but never grant access."""
    parsed, failure = _parsed(citation)
    if failure is not None:
        return failure
    record_id, version = parsed
    candidates = _records_for(conn, record_id, version)
    if not candidates:
        candidates = _records_for(conn, record_id)
    if not candidates:
        return CitationResult(citation, False, "unknown_id")
    matching = [rec for rec in candidates if _scope_reason(
        rec, case_id=case_id, organization=organization) is None]
    if len(matching) > 1:
        # A nonexistent requested version is still a version mismatch, not an
        # invitation to select an arbitrary historical version.
        if all(rec.version != version for rec in matching):
            return CitationResult(citation, False, "version_mismatch")
        return CitationResult(citation, False, "malformed")
    result = verify_record(matching[0] if matching else candidates[0], citation,
                           case_id=case_id, organization=organization)
    if not result.ok:
        return result
    if record_case_scope is not None:
        if type(record_case_scope) is not dict:
            return CitationResult(citation, False, "malformed")
        legacy_scope = record_case_scope.get(record_id)
        if legacy_scope is not None and legacy_scope != case_id:
            return CitationResult(citation, False, "cross_case")
    return result


def verify_all(conn, citations, *, case_id, organization=None,
               record_case_scope=None):
    return [
        verify_citation(conn, citation, case_id=case_id,
                        organization=organization,
                        record_case_scope=record_case_scope)
        for citation in citations
    ]
