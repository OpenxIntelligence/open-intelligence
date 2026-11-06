"""A5 Trials — registry listings; listings are never eligibility (program plan slice D5).

Design (drafted first, per the plan's design-first rule for slices
that add a user-facing surface; implemented exactly as drafted):

- A trial listing is registry metadata only: listing id, registry
  id, title, phase, status, sponsor, condition. It states what a
  registry entry says exists. It never states who may join, who
  qualifies, or whether anyone is eligible. That boundary is
  enforced in code, not just in copy:
  - ``check_eligibility_claim`` detects eligibility language in any
    text and names the matched predicate. The predicates are pinned
    here (``ELIGIBILITY_PREDICATES``) and mirrored in
    ``hypothesis.py``'s scope guard, so a composed hypothesis can
    never smuggle an eligibility claim past the trials check; the
    D5 test file pins the two modules to agree on a shared probe
    set.
  - ``validate_trial_listing`` rejects a listing whose own text
    states eligibility, with reason ``states_eligibility``.
  - ``render_listing`` always attaches the fixed label
    ``LISTING_LABEL`` — "Registry listing — not an eligibility
    determination." — to every listing it renders. There is no
    render path without the label.
- The listings are pinned synthetic fixtures. Registry ids use the
  ``NCT9`` block (``NCT90000001`` …), a namespace this slice
  reserves for synthetic listings: the real registry sequence has
  not reached the 9-block, and every listing carries
  ``synthetic: True``. A listing without the synthetic flag is
  rejected with ``not_synthetic``; a registry id outside the
  well-formed ``NCT`` + 8 digits shape is rejected with
  ``malformed_registry_id`` (the same shape the K-checks enforce
  for identifier format). No live registry lookup exists in this
  slice — there is no network call anywhere in this module, and no
  listing is presented as a live registry result. A live lookup is
  future work.
- Lookup is keyword matching over title and condition, case
  insensitive, returning copies of the pinned listings.
- This module imports no other dimension module. It is the A5
  toolset; cross-dimension interaction happens only through the
  ledger and ``route.decided``.
"""

from __future__ import annotations

import copy
import re

# Fixed label carried by every rendered listing. There is no render
# path without it. Tests pin this string verbatim.
LISTING_LABEL = "Registry listing — not an eligibility determination."

REQUIRED_FIELDS = ("listing_id", "registry_id", "title", "phase", "status", "sponsor", "condition")

# Eligibility language. Each entry is (predicate name, compiled
# pattern). A match means the text states eligibility — or invites
# the reader to treat the listing as an eligibility verdict — and
# the text must be rejected, never rendered as a listing note.
# "Enrollment is open" as a status is listing metadata, not an
# eligibility claim; only language that says who may join, or that
# criteria are met, matches here.
ELIGIBILITY_PREDICATES: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("eligible", re.compile(r"\beligib\w*\b", re.IGNORECASE)),
    ("qualifies_for", re.compile(r"\bqualif\w+ for\b", re.IGNORECASE)),
    ("can_enroll", re.compile(r"\b(can|may|could) enroll\b", re.IGNORECASE)),
    ("meets_criteria", re.compile(r"\bmeets? (the )?(inclusion )?criteria\b", re.IGNORECASE)),
    ("criteria_met", re.compile(r"\binclusion criteria (met|satisfied|fulfilled)\b", re.IGNORECASE)),
    ("enroll_in_this", re.compile(r"\benrol\w+ (in|into) this\b", re.IGNORECASE)),
)

_REGISTRY_OK_RE = re.compile(r"^NCT\d{8}$")

# Pinned synthetic listings. Titles, sponsors, and conditions are
# invented; no listing describes a real trial, and no registry id
# is a real registry entry (the NCT9 block is this slice's synthetic
# namespace). Statuses are registry vocabulary, not eligibility.
PINNED_LISTINGS: tuple[dict, ...] = (
    {
        "listing_id": "TRL-0001",
        "registry_id": "NCT90000001",
        "title": "Synthetic study of longitudinal record review in oncology care",
        "phase": "Phase 2",
        "status": "recruiting",
        "sponsor": "Synthetic Oncology Cooperative",
        "condition": "synthetic oncology cohort",
        "synthetic": True,
    },
    {
        "listing_id": "TRL-0002",
        "registry_id": "NCT90000002",
        "title": "Synthetic imaging comparison study in cardiology care",
        "phase": "Phase 1",
        "status": "active, not recruiting",
        "sponsor": "Synthetic Cardiology Network",
        "condition": "synthetic cardiology cohort",
        "synthetic": True,
    },
    {
        "listing_id": "TRL-0003",
        "registry_id": "NCT90000003",
        "title": "Synthetic molecular evidence linkage study",
        "phase": "Phase 3",
        "status": "completed",
        "sponsor": "Synthetic Genomics Collective",
        "condition": "synthetic molecular cohort",
        "synthetic": True,
    },
    {
        "listing_id": "TRL-0004",
        "registry_id": "NCT90000004",
        "title": "Synthetic symptom-note ordering study",
        "phase": "Not applicable",
        "status": "recruiting",
        "sponsor": "Synthetic Care Research Group",
        "condition": "synthetic symptom cohort",
        "synthetic": True,
    },
)


def check_eligibility_claim(text: str) -> str | None:
    """Name of the eligibility predicate matched in ``text``, or None.

    A match means the text states eligibility (or invites the reader
    to treat a listing as an eligibility verdict). Returns the first
    predicate name in pinned order, so the result is deterministic.
    """
    if not isinstance(text, str):
        return None
    for name, pattern in ELIGIBILITY_PREDICATES:
        if pattern.search(text):
            return name
    return None


def validate_trial_listing(listing: object) -> list[dict]:
    """Typed problems with a trial listing; empty means valid.

    Reasons: ``not_a_listing`` (not a dict), ``missing_field``,
    ``not_synthetic``, ``malformed_registry_id``,
    ``states_eligibility`` (with the matched predicate). A listing
    with any problem must never be rendered.
    """
    if not isinstance(listing, dict):
        return [{"reason": "not_a_listing"}]
    problems: list[dict] = []
    for field_name in REQUIRED_FIELDS:
        value = listing.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append({"reason": "missing_field", "field": field_name})
    if listing.get("synthetic") is not True:
        problems.append({"reason": "not_synthetic"})
    registry_id = listing.get("registry_id")
    if isinstance(registry_id, str) and registry_id.strip() and not _REGISTRY_OK_RE.match(registry_id.strip()):
        problems.append({"reason": "malformed_registry_id", "registry_id": registry_id})
    for field_name in ("title", "condition"):
        value = listing.get(field_name)
        if isinstance(value, str) and value:
            predicate = check_eligibility_claim(value)
            if predicate is not None:
                problems.append({
                    "reason": "states_eligibility",
                    "field": field_name,
                    "predicate": predicate,
                })
    return problems


def list_listings(condition: str | None = None) -> list[dict]:
    """Pinned synthetic listings, optionally filtered by a condition keyword.

    Matching is a case-insensitive substring over the title and the
    condition. Returns deep copies; the pinned registry is never
    handed out mutably. With no condition, every pinned listing is
    returned in pinned order.
    """
    listings = [copy.deepcopy(listing) for listing in PINNED_LISTINGS]
    if condition is None or not str(condition).strip():
        return listings
    needle = str(condition).strip().lower()
    return [listing for listing in listings
            if needle in " ".join([listing["title"], listing["condition"]]).lower()]


def get_listing(listing_id: str) -> dict | None:
    """One pinned listing by id, or None. Returns a copy."""
    for listing in PINNED_LISTINGS:
        if listing["listing_id"] == listing_id:
            return copy.deepcopy(listing)
    return None


def render_listing(listing: dict) -> dict:
    """Render a validated listing for display, always with the fixed label.

    Returns ``{"label": LISTING_LABEL, "listing": <copy>}``. Raises
    ``ValueError`` with the validation problems if the listing is
    invalid — an invalid listing is never rendered. Callers validate
    first with ``validate_trial_listing`` when they need the typed
    problems instead of the exception.
    """
    problems = validate_trial_listing(listing)
    if problems:
        raise ValueError(f"Cannot render an invalid trial listing: {problems!r}")
    return {"label": LISTING_LABEL, "listing": copy.deepcopy(listing)}
