"""Read-only per-question gap rollup over the case ledger (B-06).

This module never writes to the ledger, never calls a model, and never
fetches external data. It reports ledger facts only: the question row with
its fictional owner label and workflow markers, the case's current
unresolved source items as context for that question, the snapshots bound
to the question, its versioned needed-evidence notes, and its owner
history.

Vocabulary is imported, never forked: unresolved states come from
``mission.UNRESOLVED_SOURCE_STATES`` and coverage gap / date-conflict
semantics come from ``timeline.case_timeline``. The brief's word "missing"
maps to the imported ``not-reported`` / ``not-assessed`` states; the exact
stored state is always shown beside each item.

Ordering is mechanical and stated in ``ORDERING_RULE``: no question is
ever labeled more or less important than another.
"""

from __future__ import annotations

from .mission import UNRESOLVED_SOURCE_STATES
from .store import CaseStore, InvalidInput
from .timeline import case_timeline

ORDERING_RULE = (
    "Unresolved items are listed by (source_version_id, source_line); "
    "snapshots are listed by id; notes are listed by version. "
    "This order is mechanical and states no ranking."
)

SCOPE_NOTE = (
    "Unresolved items are case-level ledger facts shown as context for "
    "this question; only snapshots, needed-evidence notes, and owner "
    "history are bound to the question itself."
)

DISCLAIMER = (
    "Fictional synthetic data only. This rollup lists recorded ledger "
    "states with source anchors; it does not interpret clinical meaning, "
    "significance, or relevance, and it states no ranking between questions."
)


def question_gap_rollup(store: CaseStore, case_id: str, question_id: int) -> dict:
    """Build the gap rollup for one question. Reads only; writes nothing."""
    if type(question_id) is not int:
        raise InvalidInput("Question id must be an integer")
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        question = store.db.execute(
            "SELECT * FROM questions WHERE id=? AND case_id=?",
            (question_id, case_id)).fetchone()
        if not question:
            raise InvalidInput("Question not in this case")
        wanted = sorted(UNRESOLVED_SOURCE_STATES)
        marks = ",".join("?" for _ in wanted)
        items = [dict(row) for row in store.db.execute(
            f"""SELECT a.finding_key,a.certainty AS state,a.quote,a.source_line,
            v.id AS source_version_id,v.document_id,v.version,
            v.event_date AS occurred,v.issued_at AS documented,v.received_at AS received
            FROM assertions a JOIN source_versions v ON v.id=a.source_version_id
            WHERE a.case_id=? AND v.state='current' AND a.certainty IN ({marks})
            ORDER BY v.id,a.source_line,a.finding_key""",
            (case_id, *wanted)).fetchall()]
        snapshots = [dict(row) for row in store.db.execute(
            """SELECT id,state,created_at,reviewed_at,reviewer_label FROM snapshots
            WHERE case_id=? AND question_id=? ORDER BY id""",
            (case_id, question_id)).fetchall()]
        for snapshot in snapshots:
            snapshot["source_ids"] = [row[0] for row in store.db.execute(
                """SELECT source_version_id FROM snapshot_sources
                WHERE snapshot_id=? ORDER BY source_version_id""",
                (snapshot["id"],)).fetchall()]
        notes = [dict(row) for row in store.db.execute(
            """SELECT version,note,created_at FROM question_evidence_notes
            WHERE case_id=? AND question_id=? ORDER BY version""",
            (case_id, question_id)).fetchall()]
        history = [dict(row) for row in store.db.execute(
            """SELECT owner_label,assigned_at FROM question_owner_history
            WHERE case_id=? AND question_id=? ORDER BY id""",
            (case_id, question_id)).fetchall()]
    timeline = case_timeline(store, case_id)
    counts: dict[str, int] = {}
    for item in items:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    return {
        "case_id": case_id,
        "synthetic": True,
        "disclaimer": DISCLAIMER,
        "as_of": timeline["as_of"],
        "question": {
            "id": question["id"],
            "question": question["question"],
            "state": question["state"],
            "triage": question["triage"],
            "owner_label": question["owner_label"],
            "created_at": question["created_at"],
        },
        "ordering_rule": ORDERING_RULE,
        "scope_note": SCOPE_NOTE,
        "counts_by_state": counts,
        "unresolved_items": items,
        "snapshots": snapshots,
        "needed_evidence_notes": notes,
        "owner_history": history,
        "case_coverage_context": {
            "note": ("Case-level coverage from the timeline projection; "
                     "context only, not bound to this question."),
            "gaps": timeline["gaps"],
            "date_conflicts": timeline["conflicts"],
        },
    }
