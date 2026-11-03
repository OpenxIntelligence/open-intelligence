"""Read-only clinician overview projection for the synthetic demo.

The projection organizes facts already present in ``CaseStore.state()`` for
one case. It creates no new record, makes no care decision, and makes no
clinical claim. It lists current sources, open questions, items waiting for review,
follow-up tasks, a goals count, and a workflow journey stage. Every item
carries a citation to its source version or record id.

Language boundary: the projection's own labels avoid directive clinical
wording. The required disclaimer contains the word "recommendation" only in
negated form ("not a clinical recommendation"). Verbatim question, task, and
option labels are quoted facts from the ledger, not projection directives.
"""

from __future__ import annotations

DISCLAIMER = "Summary of the recorded case file only \u2014 not a clinical recommendation, not a treatment decision."

SCOPE = "synthetic_only"

STAGE_LABELS = {
    "awaiting_sources": "Awaiting sources",
    "ready_to_define_question": "Ready to define question",
    "investigation_in_progress": "Investigation in progress",
    "review_required": "Review required",
    "reviewed_in_demo": "Reviewed in demo",
}

GOALS_NOTE = "No goals are recorded in the current synthetic ledger for this case."

_TERMINAL_TASK_STATUSES = frozenset({"done", "cancelled"})


def _citation_source(item: dict) -> str:
    return f"{item.get('document_id')}@{item.get('version')} \u00b7 source version #{item.get('id')}"


def _current_sources(state: dict) -> list[dict]:
    out = []
    for item in state.get("sources", []):
        if item.get("state") != "current":
            continue
        out.append({
            "source_version_id": item.get("id"),
            "document_id": item.get("document_id"),
            "version": item.get("version"),
            "kind": item.get("kind"),
            "event_date": item.get("event_date"),
            "issued_at": item.get("issued_at"),
            "state": "current",
            "citation": _citation_source(item),
        })
    out.sort(key=lambda x: (str(x["document_id"]), int(x["version"])))
    return out


def _open_questions(state: dict) -> list[dict]:
    out = []
    for item in state.get("questions", []):
        if item.get("state") != "open":
            continue
        out.append({
            "question_id": item.get("id"),
            "question": item.get("question"),
            "created_at": item.get("created_at"),
            "state": "open",
            "citation": f"question #{item.get('id')}",
        })
    out.sort(key=lambda x: int(x["question_id"]))
    return out


def _pending_reviews(state: dict, open_ids: set[int]) -> list[dict]:
    """Items waiting for review, derived from the same ledger the UI shows.

    Draft snapshots need acknowledgment. Stale snapshots whose question is
    still open need reconciliation; historical stale snapshots whose question
    was later addressed stay in history but are not pending. Options with
    review_state needs_review need re-review. Quarantined deliveries need
    inspection because no assertions were imported from them.
    """
    out = []
    for snap in state.get("snapshots", []):
        snap_state = snap.get("state")
        if snap_state == "draft":
            out.append({
                "kind": "snapshot_draft",
                "snapshot_id": snap.get("id"),
                "question_id": snap.get("question_id"),
                "created_at": snap.get("created_at"),
                "source_ids": list(snap.get("source_ids", [])),
                "review_state": "draft",
                "citation": f"snapshot #{snap.get('id')} \u00b7 question #{snap.get('question_id')}",
            })
        elif snap_state == "stale" and snap.get("question_id") in open_ids:
            out.append({
                "kind": "snapshot_stale",
                "snapshot_id": snap.get("id"),
                "question_id": snap.get("question_id"),
                "created_at": snap.get("created_at"),
                "source_ids": list(snap.get("source_ids", [])),
                "review_state": "stale",
                "citation": f"snapshot #{snap.get('id')} \u00b7 question #{snap.get('question_id')}",
            })
    for option in state.get("options", []):
        if option.get("review_state") == "needs_review":
            out.append({
                "kind": "option_needs_review",
                "option_id": option.get("id"),
                "label": option.get("label"),
                "operational_status": option.get("operational_status"),
                "review_state": "needs_review",
                "snapshot_id": option.get("snapshot_id"),
                "citation": f"option #{option.get('id')}",
            })
    for entry in state.get("quarantines", []):
        out.append({
            "kind": "quarantined_delivery",
            "quarantine_id": entry.get("id"),
            "reason": entry.get("reason"),
            "received_at": entry.get("received_at"),
            "review_state": "quarantined",
            "citation": f"quarantined delivery #{entry.get('id')}",
        })
    return out


def _follow_up_tasks(state: dict) -> list[dict]:
    """Pending preparation tasks, exactly as recorded on options.

    Only tasks with status done or cancelled are finished history and are
    not listed here. Every other recorded status stays visible with its
    owner and status, cited to task and option ids, so an unfamiliar
    status fails visible rather than silently hidden.
    """
    out = []
    for option in state.get("options", []):
        for task in option.get("preparation_tasks", []):
            if task.get("status") in _TERMINAL_TASK_STATUSES:
                continue
            out.append({
                "task_id": task.get("id"),
                "option_id": option.get("id"),
                "label": task.get("label"),
                "owner_label": task.get("owner_label"),
                "status": task.get("status"),
                "lead_time_days": task.get("lead_time_days"),
                "citation": f"task #{task.get('id')} \u00b7 option #{option.get('id')}",
            })
    out.sort(key=lambda x: (int(x["option_id"]), int(x["task_id"])))
    return out


def build_clinician_overview(state: dict) -> dict:
    """Project a canonical case snapshot into a clinician case summary."""
    case = state["case"]
    case_id = case["case_id"]
    sources = _current_sources(state)
    questions = _open_questions(state)
    open_ids = {int(item["question_id"]) for item in questions}
    pending = _pending_reviews(state, open_ids)
    tasks = _follow_up_tasks(state)
    snapshots = state.get("snapshots", [])
    drafts = [s for s in snapshots if s.get("state") == "draft"]
    reviewed = [s for s in snapshots if s.get("state") == "reviewed_in_demo"]

    if pending:
        # Drafts are pending (they wait for acknowledgment), so a case with
        # only drafts is already review_required above, not below.
        stage = "review_required"
    elif questions:
        stage = "investigation_in_progress"
    elif reviewed:
        stage = "reviewed_in_demo"
    elif sources:
        stage = "ready_to_define_question"
    else:
        stage = "awaiting_sources"

    return {
        "case": {
            "case_id": case_id,
            "label": case["label"],
            "scope": SCOPE,
        },
        "disclaimer": DISCLAIMER,
        "current_sources": sources,
        "open_questions": questions,
        "pending_reviews": pending,
        "follow_up_tasks": tasks,
        "goals": {
            "count": 0,
            "items": [],
            "note": GOALS_NOTE,
            "citation": f"case {case_id}",
        },
        "journey_stage": {
            "stage": stage,
            "label": STAGE_LABELS[stage],
            "basis": {
                "current_source_documents": len(sources),
                "open_questions": len(questions),
                "draft_snapshots": len(drafts),
                "reviewed_snapshots": len(reviewed),
                "pending_reviews": len(pending),
                "pending_tasks": len(tasks),
                "quarantined_deliveries": len(state.get("quarantines", [])),
            },
            "citation": f"case {case_id}",
        },
    }
