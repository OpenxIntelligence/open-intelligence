"""Read-only case search and triage list over the existing case ledger.

This module never writes to the ledger, never creates tables, and never
infers clinical meaning. It projects the canonical case ledger into a
searchable list for finding cases and seeing work counts at a glance.

Returned per case only: case id, display label, created date, last
recorded activity, and counts (current sources, open questions, drafts
awaiting demo review, overdue follow-ups). No source text, finding
quotes, question text, draft summaries, notes, or other clinical text
appears in the list payload.

Counts derive from the same tables and state filters the case views use:

- sources: source_versions WHERE state='current' (same as the workspace
  metrics, the incoming board current-source count, and the Patient
  Mission current_source_documents).
- open_questions: questions WHERE state='open' (same as the workspace,
  the board, and the mission projection).
- pending_reviews: snapshots WHERE state='draft' (drafts awaiting a
  demo acknowledgment; same as the mission drafts and the workspace
  draft-review button). Stale snapshots are preserved history, not
  pending review; their rework signal is the reopened open question.
- overdue_follow_ups: always 0. The demo ledger contains no follow-up
  due dates, urgency, priority, or next clinical step, so none is shown
  or inferred. Returning 0 rather than guessing preserves the existing
  incoming-board boundary that this demo is not a clinical triage list.

Search matches case id and display label substrings only,
case-insensitive. Empty search returns all cases. A term matching
nothing returns an empty list, never an error. Sorting is either
case-id order (existing cases() order) or recent-first by latest
recorded activity (latest event id per case, from the same events
ledger the case views show). Created date is the case_created event
timestamp, or None when unavailable rather than a guessed date.
"""

from __future__ import annotations

from .store import CaseStore, InvalidInput


def list_cases(store: CaseStore, search: str | None = "", sort: str | None = "id") -> list[dict]:
    """List case summaries matching a substring, with exact work counts.

    Reads only; writes nothing. Raises InvalidInput for a non-text
    search or an unknown sort so the HTTP layer returns its existing
    422 boundary.
    """
    if search is None:
        search = ""
    if not isinstance(search, str):
        raise InvalidInput("Search must be text")
    if sort is None or sort == "":
        sort = "id"
    if sort not in ("recent", "id"):
        raise InvalidInput("Sort must be recent or id")
    needle = search.strip().lower()
    # A single read transaction keeps counts, created dates, and last
    # activity mutually consistent if a write commits during the list.
    with store.db:
        store.db.execute("BEGIN")
        rows = store.db.execute(
            "SELECT case_id,label,synthetic FROM cases ORDER BY case_id"
        ).fetchall()
        if needle:
            rows = [
                row for row in rows
                if needle in str(row["case_id"]).lower()
                or needle in str(row["label"]).lower()
            ]
        summaries: list[dict] = []
        for row in rows:
            case_id = str(row["case_id"])
            sources = store.db.execute(
                "SELECT COUNT(*) FROM source_versions WHERE case_id=? AND state='current'",
                (case_id,),
            ).fetchone()[0]
            open_questions = store.db.execute(
                "SELECT COUNT(*) FROM questions WHERE case_id=? AND state='open'",
                (case_id,),
            ).fetchone()[0]
            pending_reviews = store.db.execute(
                "SELECT COUNT(*) FROM snapshots WHERE case_id=? AND state='draft'",
                (case_id,),
            ).fetchone()[0]
            created = store.db.execute(
                "SELECT occurred_at FROM events WHERE case_id=? AND kind='case_created'"
                " ORDER BY id LIMIT 1",
                (case_id,),
            ).fetchone()
            last = store.db.execute(
                "SELECT id,occurred_at FROM events WHERE case_id=? ORDER BY id DESC LIMIT 1",
                (case_id,),
            ).fetchone()
            summaries.append({
                "case_id": case_id,
                "label": str(row["label"]),
                "created_at": created["occurred_at"] if created else None,
                "last_activity_at": last["occurred_at"] if last else None,
                "last_activity_event_id": int(last["id"]) if last else 0,
                "synthetic": row["synthetic"],
                "counts": {
                    "sources": int(sources),
                    "open_questions": int(open_questions),
                    "pending_reviews": int(pending_reviews),
                    # No follow-up ledger exists; 0 is the honest count.
                    "overdue_follow_ups": 0,
                },
            })
        if sort == "recent":
            summaries.sort(key=lambda item: (-int(item["last_activity_event_id"]), item["case_id"]))
        else:
            summaries.sort(key=lambda item: item["case_id"])
        return summaries
