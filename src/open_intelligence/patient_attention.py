"""Read-only patient attention projection over the existing case ledger.

This module never writes to the ledger, never creates tables, never calls a
model, and never fetches external data. It lists what is still open in one
fictional case, in plain language, derived only from rows that already exist:

- open questions (questions.state open),
- drafts awaiting demo review and discussion items needing re-review,
- open follow-up tasks, recorded deadlines, and recorded threats,
- stale drafts whose question is still open (needs a new answer).

Ordering uses recorded YYYY-MM-DD dates only (sourced deadline and threat
dates). Entries without a recorded date appear last with the explicit marker
"no date recorded". No urgency, priority, or clinical meaning is inferred.
Nothing here authorizes, schedules, or executes any action. Deadlines and
threats for withdrawn, expired, or rejected discussion items are historical
and stay visible in the Options panel; they are not listed here.
"""

from __future__ import annotations

from .store import CaseStore, InvalidInput

DISCLAIMER = (
    "FICTIONAL synthetic demo only. This read-only list shows existing open "
    "questions, drafts awaiting demo review, open follow-up tasks, recorded "
    "deadlines, and stale drafts. Ordering uses recorded dates only; entries "
    "without a recorded date appear last as 'no date recorded'. No urgency is "
    "inferred. Nothing here authorizes, schedules, or executes any action. "
    "For a real result, talk to your care team."
)

NO_DATE = "no date recorded"

KIND_ORDER = {
    "open_question": 0,
    "pending_review": 1,
    "follow_up": 2,
    "unanswered": 3,
}


def _entry(*, kind: str, title: str, record_type: str, record_id: int,
           recorded_date: str | None, review_state: str,
           source_anchor: str, detail: str) -> dict:
    return {
        "kind": kind,
        "title": title,
        "recorded_date": recorded_date,
        "date_display": recorded_date if recorded_date is not None else NO_DATE,
        "record_id": record_id,
        "record_type": record_type,
        "fictional": True,
        "review_state": review_state,
        "source_anchor": source_anchor,
        "detail": detail,
    }


def case_patient_attention(store: CaseStore, case_id: str) -> dict:
    """Build the attention projection for one case. Reads only; writes nothing."""
    with store.db:
        store.db.execute("BEGIN")
        case = store.db.execute(
            "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if not case:
            raise InvalidInput("Unknown case")

        entries: list[dict] = []

        for row in store.db.execute(
                "SELECT id, question, state, created_at FROM questions "
                "WHERE case_id=? AND state='open' ORDER BY id",
                (case_id,)).fetchall():
            qid = int(row["id"])
            entries.append(_entry(
                kind="open_question",
                title=f"FICTIONAL \u2014 Open question Q{qid} still has no reviewed answer in this demo.",
                record_type="question",
                record_id=qid,
                recorded_date=None,
                review_state=str(row["state"]),
                source_anchor=f"Question Q{qid} recorded {row['created_at']}",
                detail=str(row["question"]),
            ))

        for row in store.db.execute(
                "SELECT id, question_id, summary, state, created_at FROM snapshots "
                "WHERE case_id=? AND state='draft' ORDER BY id",
                (case_id,)).fetchall():
            sid = int(row["id"])
            sources = [r[0] for r in store.db.execute(
                "SELECT source_version_id FROM snapshot_sources "
                "WHERE snapshot_id=? ORDER BY source_version_id",
                (sid,)).fetchall()]
            entries.append(_entry(
                kind="pending_review",
                title=f"FICTIONAL \u2014 Draft investigation #{sid} awaits a demo review and is not medical advice.",
                record_type="snapshot",
                record_id=sid,
                recorded_date=None,
                review_state=str(row["state"]),
                source_anchor=(
                    f"Snapshot #{sid} for Q{int(row['question_id'])} cites "
                    f"source versions {sources or []}"
                ),
                detail=str(row["summary"]),
            ))

        for row in store.db.execute(
                "SELECT id, snapshot_id, label, operational_status, review_state "
                "FROM options WHERE case_id=? AND review_state='needs_review' "
                "AND operational_status IN ('proposed','reviewed','held') ORDER BY id",
                (case_id,)).fetchall():
            oid = int(row["id"])
            entries.append(_entry(
                kind="pending_review",
                title=f"FICTIONAL \u2014 Discussion item #{oid} needs another review after a recorded change.",
                record_type="option",
                record_id=oid,
                recorded_date=None,
                review_state=f"{row['operational_status']}/{row['review_state']}",
                source_anchor=f"Option #{oid} based on investigation #{int(row['snapshot_id'])}",
                detail=str(row["label"]),
            ))

        for row in store.db.execute(
                "SELECT id, option_id, label, owner_label, status FROM preparation_tasks "
                "WHERE case_id=? AND status IN ('not_started','in_progress','blocked') "
                "ORDER BY id",
                (case_id,)).fetchall():
            tid = int(row["id"])
            entries.append(_entry(
                kind="follow_up",
                title=f"FICTIONAL \u2014 Follow-up task #{tid} is still open and has a named owner.",
                record_type="task",
                record_id=tid,
                recorded_date=None,
                review_state=str(row["status"]),
                source_anchor=f"Task #{tid} for option #{int(row['option_id'])}",
                detail=f"{row['label']} \u00b7 Owner: {row['owner_label']} \u00b7 Status: {row['status']}",
            ))

        for row in store.db.execute(
                "SELECT d.id, d.option_id, d.kind, d.deadline_date, "
                "d.deadline_basis, d.anchor "
                "FROM option_dependencies d JOIN options o ON o.id=d.option_id "
                "WHERE o.case_id=? AND d.deadline_date IS NOT NULL "
                "AND o.operational_status IN ('proposed','reviewed','held') "
                "ORDER BY d.deadline_date, d.id",
                (case_id,)).fetchall():
            did = int(row["id"])
            due = str(row["deadline_date"])
            entries.append(_entry(
                kind="follow_up",
                title=f"FICTIONAL \u2014 A recorded deadline of {due} applies to discussion item #{int(row['option_id'])}.",
                record_type="dependency",
                record_id=did,
                recorded_date=due,
                review_state=str(row["deadline_basis"]),
                source_anchor=f"Dependency #{did} ({row['kind']}) anchor: {row['anchor']}",
                detail=f"Recorded deadline {due} with a human-supplied anchor.",
            ))

        for row in store.db.execute(
                "SELECT t.id, t.option_id, t.kind, t.description, t.threat_date, "
                "t.threat_basis, t.anchor FROM optionality_threats t "
                "JOIN options o ON o.id=t.option_id WHERE o.case_id=? "
                "AND o.operational_status IN ('proposed','reviewed','held') "
                "ORDER BY t.id",
                (case_id,)).fetchall():
            threat_id = int(row["id"])
            threat_date = row["threat_date"]
            if threat_date is not None:
                entries.append(_entry(
                    kind="follow_up",
                    title=f"FICTIONAL \u2014 A recorded date of {threat_date} is linked to discussion item #{int(row['option_id'])}.",
                    record_type="threat",
                    record_id=threat_id,
                    recorded_date=str(threat_date),
                    review_state=f"{row['kind']}/{row['threat_basis']}",
                    source_anchor=f"Threat #{threat_id} anchor: {row['anchor']}",
                    detail=str(row["description"]),
                ))
            else:
                entries.append(_entry(
                    kind="follow_up",
                    title=f"FICTIONAL \u2014 A possible loss of choice is recorded for discussion item #{int(row['option_id'])}.",
                    record_type="threat",
                    record_id=threat_id,
                    recorded_date=None,
                    review_state=f"{row['kind']}/{row['threat_basis']}",
                    source_anchor=f"Threat #{threat_id} anchor: {row['anchor']}",
                    detail=str(row["description"]),
                ))

        for row in store.db.execute(
                "SELECT s.id, s.question_id, s.summary, s.state FROM snapshots s "
                "JOIN questions q ON q.id=s.question_id "
                "WHERE s.case_id=? AND s.state='stale' AND q.state='open' "
                "AND q.case_id=? ORDER BY s.id",
                (case_id, case_id)).fetchall():
            sid = int(row["id"])
            sources = [r[0] for r in store.db.execute(
                "SELECT source_version_id FROM snapshot_sources "
                "WHERE snapshot_id=? ORDER BY source_version_id",
                (sid,)).fetchall()]
            entries.append(_entry(
                kind="unanswered",
                title=f"FICTIONAL \u2014 Earlier draft #{sid} is stale because a source changed.",
                record_type="snapshot",
                record_id=sid,
                recorded_date=None,
                review_state=f"{row['state']}/question-open",
                source_anchor=(
                    f"Stale snapshot #{sid} for Q{int(row['question_id'])} cited "
                    f"source versions {sources or []}"
                ),
                detail=str(row["summary"]),
            ))

        dated = sorted(
            (e for e in entries if e["recorded_date"] is not None),
            key=lambda e: (e["recorded_date"], KIND_ORDER[e["kind"]],
                           e["record_type"], e["record_id"]),
        )
        undated = sorted(
            (e for e in entries if e["recorded_date"] is None),
            key=lambda e: (KIND_ORDER[e["kind"]], e["record_type"], e["record_id"]),
        )
        ordered = dated + undated
        return {
            "case_id": case_id,
            "synthetic": True,
            "disclaimer": DISCLAIMER,
            "counts": {"entries": len(ordered)},
            "entries": ordered,
        }
