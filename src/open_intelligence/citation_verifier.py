"""ID-level citation verifier, issue 117 (WS-06).

Verifies a cited identifier against the offline evidence catalog in
evidence_catalog.py. It checks identity, version, rights, and case
scope only. It does NOT check whether a source supports a claim, and
it never resolves a link over the network.

Reason codes: ok, malformed, unknown_id, version_mismatch,
blocked_source, rights_hold, revoked, superseded, cross_case,
no_version.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from open_intelligence.evidence_catalog import (
    BLOCKED_SOURCES,
    get,
)

CITATION_PATTERN = re.compile(r"^(FICT-[A-Z0-9\-]+|[0-9]+\.[0-9]+/\S+|NCT[0-9]+)(?:@(.+))?$")


@dataclass(frozen=True)
class CitationResult:
    citation: str
    ok: bool
    reason: str


def parse_citation(text):
    """Split 'ID@version' into (id, version or None). Raises ValueError
    on a malformed citation."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Citation is empty")
    match = CITATION_PATTERN.match(text.strip())
    if not match:
        raise ValueError(f"Malformed citation: {text!r}")
    return match.group(1), match.group(2)


def verify_citation(conn, citation, *, case_id, record_case_scope=None):
    if not isinstance(citation, str):
        return CitationResult(citation, False, "malformed")
    lowered = citation.lower()
    if any(token in lowered for token in BLOCKED_SOURCES):
        return CitationResult(citation, False, "blocked_source")
    try:
        record_id, version = parse_citation(citation)
    except ValueError:
        return CitationResult(citation, False, "malformed")
    if version is None:
        return CitationResult(citation, False, "no_version")
    hit = get(conn, record_id, version)
    if hit is None:
        if get(conn, record_id) is not None:
            return CitationResult(citation, False, "version_mismatch")
        return CitationResult(citation, False, "unknown_id")
    if record_case_scope is not None:
        scope = record_case_scope.get(record_id)
        if scope is not None and scope != case_id:
            return CitationResult(citation, False, "cross_case")
    if hit.availability == "revoked":
        return CitationResult(citation, False, "revoked")
    if hit.availability == "superseded":
        return CitationResult(citation, False, "superseded")
    if hit.rights_status != "granted":
        return CitationResult(citation, False, "rights_hold")
    return CitationResult(citation, True, "ok")


def verify_all(conn, citations, *, case_id, record_case_scope=None):
    return [
        verify_citation(conn, citation, case_id=case_id,
                        record_case_scope=record_case_scope)
        for citation in citations
    ]
