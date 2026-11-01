"""Read-only "what changed since last review" projection over the case ledger.

This module never writes to the ledger and never infers clinical meaning from
a change. It reports ledger facts only: which fictional sources arrived, which
documents were amended, which drafts were marked stale by those amendments or
by evidence changes, and which questions were created — all after an anchor
event. The anchor is the case's latest demo-review acknowledgment, or the
case-creation event when nothing has been acknowledged yet. A caller may also
pass an explicit event id as the anchor.

Every payload is labeled synthetic. Finding states are quoted verbatim as
"reported_state" (the state authored in the fictional source text); a
mechanical key diff between two source versions reports which finding keys
were added, removed, or carry a different reported state. That diff is a
ledger comparison, not an interpretation of significance, progression, or
clinical relevance — no such claim is made anywhere in this projection.
"""

from __future__ import annotations

import json

from .store import CaseStore, InvalidInput

DISCLAIMER = (
    "Fictional synthetic data only. This projection reports ledger changes "
    "since the anchor event; it does not interpret clinical meaning, "
    "significance, or relevance of any change. Nothing listed here has been "
    "demo-acknowledged after the anchor; a new acknowledgment creates a new anchor."
)


def _finding_diff(old_rows: list[dict], new_rows: list[dict]) -> dict:
    old = {row["finding_key"]: row["certainty"] for row in old_rows}
    new = {row["finding_key"]: row["certainty"] for row in new_rows}
    changed = [
        {"finding_key": key, "previous_reported_state": old[key], "reported_state": new[key]}
        for key in sorted(set(old) & set(new))
        if old[key] != new[key]
    ]
    return {
        "added_finding_keys": sorted(set(new) - set(old)),
        "removed_finding_keys": sorted(set(old) - set(new)),
        "reported_state_changes": changed,
    }


def changes_since_review(store: CaseStore, case_id: str, since_event_id: int | None = None) -> dict:
    """Build the change projection for one case. Reads only; writes nothing."""
    if since_event_id is not None and (type(since_event_id) is not int or since_event_id < 1):
        raise InvalidInput("since_event_id must be a positive integer")
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute("SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")
        events = [dict(row) for row in store.db.execute(
            "SELECT id,kind,details,occurred_at FROM events WHERE case_id=? ORDER BY id", (case_id,)).fetchall()]
        if since_event_id is not None:
            anchor = next((event for event in events if event["id"] == since_event_id), None)
            if anchor is None:
                raise InvalidInput("Anchor event not in this case")
        else:
            acknowledged = [event for event in events if event["kind"] == "demo_review_acknowledged"]
            anchor = acknowledged[-1] if acknowledged else (events[0] if events else None)
        if anchor is None:
            raise InvalidInput("Case has no events to anchor on")
        after = [event for event in events if event["id"] > anchor["id"]]

        def source_row(source_id: int) -> dict | None:
            row = store.db.execute(
                """SELECT id,document_id,version,kind,event_date,issued_at,received_at,state
                FROM source_versions WHERE id=? AND case_id=?""", (source_id, case_id)).fetchone()
            return dict(row) if row else None

        def findings_for(source_id: int) -> list[dict]:
            return [dict(row) for row in store.db.execute(
                "SELECT finding_key,certainty,quote,source_line FROM assertions WHERE source_version_id=? ORDER BY finding_key",
                (source_id,)).fetchall()]

        new_sources: list[dict] = []
        amendments: list[dict] = []
        stale_causes: list[dict] = []
        for event in after:
            details = json.loads(event["details"])
            if event["kind"] == "source_imported":
                row = source_row(details["source_id"])
                if row is None:
                    continue
                findings = findings_for(details["source_id"])
                if details.get("amends_id") is None:
                    new_sources.append({
                        "event_id": event["id"],
                        "occurred_at": event["occurred_at"],
                        "source_id": row["id"],
                        "document_id": row["document_id"],
                        "version": row["version"],
                        "kind": row["kind"],
                        "event_date": row["event_date"],
                        "issued_at": row["issued_at"],
                        "received_at": row["received_at"],
                        "reported_findings": [
                            {"finding_key": f["finding_key"], "reported_state": f["certainty"]}
                            for f in findings
                        ],
                    })
                else:
                    previous = source_row(details["amends_id"])
                    diff = _finding_diff(
                        findings_for(details["amends_id"]) if previous else [], findings)
                    amendments.append({
                        "event_id": event["id"],
                        "occurred_at": event["occurred_at"],
                        "source_id": row["id"],
                        "document_id": row["document_id"],
                        "version": row["version"],
                        "kind": row["kind"],
                        "event_date": row["event_date"],
                        "issued_at": row["issued_at"],
                        "received_at": row["received_at"],
                        "supersedes_source_id": details["amends_id"],
                        "superseded_version": previous["version"] if previous else None,
                        "finding_key_diff": diff,
                        "invalidated_snapshot_ids": details.get("invalidated_snapshots", []),
                    })
                    for snapshot_id in details.get("invalidated_snapshots", []):
                        stale_causes.append({
                            "event_id": event["id"],
                            "occurred_at": event["occurred_at"],
                            "cause": "source_amendment",
                            "snapshot_id": snapshot_id,
                        })
            elif event["kind"] == "evidence_invalidated":
                for snapshot_id in details.get("invalidated_snapshots", []):
                    stale_causes.append({
                        "event_id": event["id"],
                        "occurred_at": event["occurred_at"],
                        "cause": "evidence_change",
                        "reason": details.get("reason"),
                        "evidence_version_id": details.get("evidence_version_id"),
                        "snapshot_id": snapshot_id,
                    })
        new_questions: list[dict] = []
        for event in after:
            if event["kind"] != "question_created":
                continue
            details = json.loads(event["details"])
            row = store.db.execute(
                "SELECT id,question,state,created_at FROM questions WHERE id=? AND case_id=?",
                (details["question_id"], case_id)).fetchone()
            if row:
                new_questions.append({
                    "event_id": event["id"],
                    "question_id": row["id"],
                    "question": row["question"],
                    "state": row["state"],
                    "created_at": row["created_at"],
                })
        stale_investigations: list[dict] = []
        seen_snapshots: set[int] = set()
        for cause in stale_causes:
            snapshot_id = cause["snapshot_id"]
            if snapshot_id in seen_snapshots:
                continue
            seen_snapshots.add(snapshot_id)
            row = store.db.execute(
                "SELECT id,question_id,state FROM snapshots WHERE id=? AND case_id=?",
                (snapshot_id, case_id)).fetchone()
            if not row:
                continue
            question = store.db.execute(
                "SELECT id,question,state FROM questions WHERE id=? AND case_id=?",
                (row["question_id"], case_id)).fetchone()
            causes = [c for c in stale_causes if c["snapshot_id"] == snapshot_id]
            stale_investigations.append({
                "snapshot_id": row["id"],
                "current_state": row["state"],
                "question_id": row["question_id"],
                "question": question["question"] if question else None,
                "question_state": question["state"] if question else None,
                "causes": [
                    {k: v for k, v in c.items() if k != "snapshot_id"} for c in causes
                ],
            })
        return {
            "case_id": case_id,
            "synthetic": True,
            "disclaimer": DISCLAIMER,
            "anchor": {"event_id": anchor["id"], "kind": anchor["kind"], "occurred_at": anchor["occurred_at"]},
            "counts": {
                "new_sources": len(new_sources),
                "amendments": len(amendments),
                "stale_investigations": len(stale_investigations),
                "new_questions": len(new_questions),
            },
            "new_sources": new_sources,
            "amendments": amendments,
            "stale_investigations": stale_investigations,
            "new_questions": new_questions,
        }
