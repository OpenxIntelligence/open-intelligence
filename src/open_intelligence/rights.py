"""Deterministic rights gate for external evidence sources (issue #2).

This module is pure: no network, no database, no model calls. It answers
one question only — may this exact content item be stored, shown,
redistributed, or used for ML under this exact rights record?

Rules (fail closed, per the issue #2 boundary reconciliation):

- A permission is usable only when explicitly recorded as "allowed" for
  that item AND that use, on a rights record that is not revoked or
  superseded. "unknown" and "denied" both mean NO. A missing entry
  means "unknown", which means NO.
- Content modes follow from the gate, never from a claim about the
  source:
  - "full": full_text may be stored AND displayed. An excerpt may be
    kept only in this mode.
  - "metadata_only": metadata may be stored (title/identifier fields),
    but no excerpt. The record is usable as a citation, not as evidence
    text.
  - "citation_only": nothing but the source identity (key, version,
    owner, attribution) is kept. No excerpt, no metadata fields.
- The gate never verifies that a rights record is legally true. It only
  enforces what the record says. A record whose permissions are unknown
  is unusable for content, by construction.
- Nothing here fetches external content. Acquisition, if any, happens
  elsewhere under a separately authorized scope; this gate is the
  checkpoint before anything is stored or attached to a case.
"""

from __future__ import annotations

ITEMS = frozenset({
    "metadata", "abstract", "full_text", "figures", "terminology", "api_output",
})
USES = frozenset({"store", "display", "redistribute", "ml_use"})
PERMISSION_VALUES = frozenset({"allowed", "denied", "unknown"})

RELATIONS = frozenset({"supports", "contradicts", "context", "unknown"})
APPLICABILITY = frozenset({"applicable", "limited", "not_applicable", "unknown"})


class RightsError(ValueError):
    """A rights record or gate request is invalid or not permitted."""


def normalize_permissions(permissions: object) -> dict[str, dict[str, str]]:
    """Validate a permissions map; fill every item/use as unknown unless given.

    Input shape: {"full_text": {"store": "allowed", "display": "denied", ...}, ...}
    Unknown items or uses are rejected (they would be silent unknowns);
    every other cell defaults to "unknown" so the gate fails closed.
    """
    if not isinstance(permissions, dict):
        raise RightsError("Permissions must be an object keyed by content item")
    normalized: dict[str, dict[str, str]] = {}
    for item in sorted(ITEMS):
        normalized[item] = {use: "unknown" for use in sorted(USES)}
    for item, uses in permissions.items():
        if item not in ITEMS:
            raise RightsError(f"Unknown content item: {item!r}")
        if not isinstance(uses, dict):
            raise RightsError(f"Permissions for {item!r} must be an object keyed by use")
        for use, value in uses.items():
            if use not in USES:
                raise RightsError(f"Unknown use: {use!r}")
            if value not in PERMISSION_VALUES:
                raise RightsError(f"Permission for {item}/{use} must be allowed, denied, or unknown")
            normalized[item][use] = value
    return normalized


def permitted(permissions: dict[str, dict[str, str]], item: str, use: str,
              *, revoked: bool = False, superseded: bool = False) -> bool:
    """True only for an explicitly allowed, currently active permission."""
    if revoked or superseded:
        return False
    if item not in ITEMS or use not in USES:
        return False
    return permissions.get(item, {}).get(use) == "allowed"


def excerpt_mode(permissions: dict[str, dict[str, str]], *,
                 revoked: bool = False, superseded: bool = False) -> str:
    """Content mode for a rights record: full, metadata_only, or citation_only."""
    if permitted(permissions, "full_text", "store", revoked=revoked, superseded=superseded) \
            and permitted(permissions, "full_text", "display", revoked=revoked, superseded=superseded):
        return "full"
    if permitted(permissions, "metadata", "store", revoked=revoked, superseded=superseded):
        return "metadata_only"
    return "citation_only"


def check_link_content(permissions: dict[str, dict[str, str]], *,
                       revoked: bool = False, superseded: bool = False,
                       citation_title: str | None, excerpt: str | None) -> str:
    """Validate proposed link content against the gate; return the mode.

    Raises RightsError when the caller tries to store more than the
    record permits: an excerpt without full mode, or a title without
    metadata (or full) permission. Citation identity alone is always
    storable, because it carries no source content.
    """
    mode = excerpt_mode(permissions, revoked=revoked, superseded=superseded)
    if excerpt is not None and mode != "full":
        raise RightsError(
            f"Excerpt requires full-text store and display permission; mode is {mode}")
    # A title is metadata content, not citation identity: it needs its own
    # metadata store permission even when full-text permission is granted.
    if citation_title is not None and not permitted(
            permissions, "metadata", "store", revoked=revoked, superseded=superseded):
        raise RightsError(
            "Citation title requires metadata store permission")
    return mode
