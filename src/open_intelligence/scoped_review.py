"""Scoped human review: per-snapshot scope notes, dissent, and handoff.

This module holds the pure (database-free) part of slice B-04. The ledger
tables and write methods live on CaseStore in store.py; this module defines
the scope vocabulary, input validation, status derivation, and the
export-markdown rendering so all three stay consistent.

Documented granularity choice (brief B-04 behavior 6 allows per-claim OR
per-snapshot): scope decisions are PER-SNAPSHOT with two independent
dimensions (extraction, interpretation). Dissent additionally references one
finding key (one claim) inside the snapshot's pinned basis, so a disputed
claim is visible without blocking the rest. The export therefore renders
per-dimension scope status, flags every unreviewed dimension, and lists each
dissent beside its claim reference.

These records describe record states only. They are acknowledgment and scope
recording: not clinician credential verification, not a clinical sign-off,
and not a treatment decision.
"""

from __future__ import annotations

import re

# The three scope values a scoped decision may record (brief B-04).
EXTRACTION_ACCEPTED = "extraction_accepted"
INTERPRETATION_ENDORSED = "interpretation_endorsed"
LEFT_OPEN = "left_open"
SCOPES = frozenset({EXTRACTION_ACCEPTED, INTERPRETATION_ENDORSED, LEFT_OPEN})

# Status shown for a dimension no decision (explicit or otherwise) covers.
UNREVIEWED = "unreviewed"

# A dissent claim reference names one finding key inside the snapshot basis.
_CLAIM_KEY = re.compile(r"[a-z][a-z0-9_-]{0,59}\Z")


def check_reviewer_label(value: object) -> str:
    """Fictional free-text reviewer label; same 2-80 rule as demo review.

    No credential check is performed here (that dependency belongs to the
    identity slice and remains visibly unmet).
    """
    if not isinstance(value, str) or not 2 <= len(value.strip()) <= 80:
        raise ValueError("Provide a reviewer label of 2-80 characters")
    return value.strip()


def check_note(value: object, field: str = "Note") -> str:
    """Decision notes and dissent rationales carry 10-600 characters."""
    if not isinstance(value, str) or not 10 <= len(value.strip()) <= 600:
        raise ValueError(f"{field} must have 10-600 characters")
    return value.strip()


def check_scope(value: object) -> str:
    if not isinstance(value, str) or value not in SCOPES:
        raise ValueError("Scope must be extraction_accepted, interpretation_endorsed, or left_open")
    return value


def check_claim_ref(value: object) -> str:
    if not isinstance(value, str) or not _CLAIM_KEY.fullmatch(value):
        raise ValueError("Claim reference must be a finding key: lowercase letters, numbers, hyphen, underscore")
    return value


def derive_status(decisions: list[dict]) -> dict:
    """Derive per-dimension review status from a snapshot's decision rows.

    Each row supplies a "scope" value. extraction_accepted settles only the
    extraction dimension; interpretation_endorsed settles only the
    interpretation dimension; left_open marks explicitly-unresolved review
    without settling either dimension. A dimension with no covering decision
    reads "unreviewed", or "left_open" once an explicit left-open note exists.
    """
    scopes = {str(row["scope"]) for row in decisions}
    has_left_open = LEFT_OPEN in scopes
    extraction = EXTRACTION_ACCEPTED if EXTRACTION_ACCEPTED in scopes else (LEFT_OPEN if has_left_open else UNREVIEWED)
    interpretation = (
        INTERPRETATION_ENDORSED if INTERPRETATION_ENDORSED in scopes else (LEFT_OPEN if has_left_open else UNREVIEWED)
    )
    open_items = []
    if extraction != EXTRACTION_ACCEPTED:
        open_items.append("extraction")
    if interpretation != INTERPRETATION_ENDORSED:
        open_items.append("interpretation")
    return {"extraction": extraction, "interpretation": interpretation, "open_items": open_items}


def _id_list(ids: object) -> str:
    items = sorted(int(x) for x in (ids or []))  # type: ignore[union-attr]
    return ", ".join("#" + str(x) for x in items) if items else "none"


def render_scoped_review_lines(scoped: dict) -> list[str]:
    """Render the export-markdown body of one snapshot's scoped review.

    Descriptive only: states what was recorded and what remains open, never
    a clinical sign-off and never a treatment decision.
    """
    lines = [
        "## Scoped review (record-state notes)",
        "",
        "These notes record what was looked at and what remains open. They are not clinician",
        "credential verification, not a clinical sign-off, and not a treatment decision.",
        "",
        f"Extraction record state: {scoped['extraction']}",
        f"Interpretation record state: {scoped['interpretation']}",
        "",
    ]
    open_items = list(scoped.get("open_items") or [])
    if open_items:
        lines.append("Open items (no settled note recorded): " + ", ".join(open_items))
    else:
        lines.append("Open items: none — both dimensions have a settled note.")
    lines.append("")
    decisions = list(scoped.get("decisions") or [])
    if not decisions:
        lines.extend(["No scoped decisions recorded; both dimensions are unreviewed.", ""])
    for item in decisions:
        lines.extend(
            [
                f"Decision #{item['id']} by {item['reviewer_label']}: {item['scope']}",
                f"Pinned basis: sources {_id_list(item.get('source_version_ids'))} · "
                f"evidence assessments {_id_list(item.get('evidence_assessment_ids'))} · "
                f"broker links {_id_list(item.get('broker_link_ids'))} · {item['decided_at']}",
                f"Note: {item['note']}",
                "",
            ]
        )
    dissents = list(scoped.get("dissents") or [])
    if dissents:
        lines.extend(["Disagreements recorded (the noted views above are unchanged):", ""])
        for item in dissents:
            lines.extend(
                [
                    f"Dissent #{item['id']} by {item['reviewer_label']} on claim `{item['claim_ref']}`",
                    f"Pinned basis: sources {_id_list(item.get('source_version_ids'))} · {item['dissented_at']}",
                    f"Rationale: {item['rationale']}",
                    "",
                ]
            )
    handoffs = list(scoped.get("handoffs") or [])
    if handoffs:
        lines.extend(["Review handoffs (history preserved, nothing rewritten):", ""])
        for item in handoffs:
            lines.extend(
                [
                    f"Handoff #{item['id']}: {item['from_reviewer']} handed open items to {item['to_reviewer']} · "
                    f"{item['handed_at']}",
                    f"Basis carried: snapshot #{item['snapshot_id']} · sources "
                    f"{_id_list(item.get('source_version_ids'))} · prior decisions "
                    f"{_id_list(item.get('prior_decision_ids'))}",
                    "",
                ]
            )
    return lines
