"""Case follow-through tasks: human-owned records of agreed work.

A follow-through task records what was agreed, who owns it, and when it
should be revisited (a due date, a review trigger, or both). Every status
change appends an accountability record — who made the change, when, and
why — and history rows are never updated or deleted. Completed tasks stay
in history; overdue and due-soon tasks are derived read-only views.

Records only. Creating, assigning, acknowledging, completing, or deferring
a task never performs a clinical action, contacts anyone, or changes any
source, assertion, question, evidence record, or investigation. Completion
is reachable only through a recorded acknowledgment, so the platform never
claims an action was taken without one. This module writes nothing; the
projection derives its flags from the ledger at read time.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

STATUSES = frozenset({"created", "assigned", "acknowledged", "completed", "deferred"})
OPEN_STATUSES = frozenset({"created", "assigned", "acknowledged"})

# Completion is reachable only from acknowledged: no path may claim human
# action was taken without a recorded acknowledgment first. Deferred work
# reopens only through a fresh assignment with a named owner.
TRANSITIONS = {
    "created": frozenset({"assigned", "deferred"}),
    "assigned": frozenset({"acknowledged", "deferred"}),
    "acknowledged": frozenset({"completed", "deferred"}),
    "deferred": frozenset({"assigned"}),
    "completed": frozenset(),
}

DUE_SOON_DAYS = 7

DISCLAIMER = (
    "Fictional follow-through records for humans to act on. The platform "
    "takes no action, sends no message, and claims no action was taken "
    "without a recorded acknowledgment."
)

# Narrow guard, not a clinical-language classifier: follow-through text must
# not state a recommendation, order, eligibility claim, diagnosis, or dose.
# Human review remains the gate; the disclaimer on every view states the
# boundary. The guard covers the fields a task author controls.
_CLINICAL_LANGUAGE = re.compile(
    r"\b(recommend\w*|prescrib\w*|eligible|diagnos\w*)\b"
    r"|\bshould\s+(receive|undergo|get|start)\b"
    r"|\bmust\s+(receive|undergo)\b"
    r"|\border\s+(this|the)\s+(treatment|therapy|procedure)\b"
    r"|\bstart\s+treatment\b"
    r"|\bdos(e|age)\b"
    r"|\bbest\s+(treatment|therapy|drug)\b",
    re.IGNORECASE,
)


class FollowthroughInputError(ValueError):
    """A follow-through request violates the task contract."""


def check_task_text(value: object, field: str, *, min_len: int, max_len: int) -> str:
    """Validate one author-controlled text field, including the guard."""
    if not isinstance(value, str):
        raise FollowthroughInputError(f"{field} must be text")
    text = value.strip()
    if not min_len <= len(text) <= max_len:
        raise FollowthroughInputError(
            f"{field} must have {min_len}\u2013{max_len} characters")
    if text and _CLINICAL_LANGUAGE.search(text):
        raise FollowthroughInputError(
            f"{field} must not state a clinical recommendation, order, "
            "eligibility claim, diagnosis, or dose")
    return text


def check_actor(value: object) -> str:
    return check_task_text(value, "Actor label", min_len=2, max_len=80)


def check_optional_text(value: object, field: str, *, max_len: int) -> str:
    if value is None:
        return ""
    return check_task_text(value, field, min_len=0, max_len=max_len)


def check_due_date(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise FollowthroughInputError("Due date must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise FollowthroughInputError("Due date must use YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise FollowthroughInputError("Due date must use YYYY-MM-DD")
    return value


def _resolve_today(today: str | None) -> str:
    if today is None:
        return date.today().isoformat()
    checked = check_due_date(today)
    return checked if checked is not None else date.today().isoformat()


def _select(store, case_id: str, day: str) -> dict:
    """Build the projection. The caller must hold a read transaction."""
    from .store import InvalidInput
    soon_through = (date.fromisoformat(day) + timedelta(days=DUE_SOON_DAYS)).isoformat()
    case = store.db.execute(
        "SELECT case_id FROM cases WHERE case_id=?", (case_id,)).fetchone()
    if not case:
        raise InvalidInput("Unknown case")
    rows = store.db.execute(
        "SELECT * FROM followthrough_tasks WHERE case_id=? ORDER BY id",
        (case_id,)).fetchall()
    tasks = []
    for row in rows:
        task = dict(row)
        history = [dict(event) for event in store.db.execute(
            "SELECT id,previous_status,new_status,actor_label,reason,noted_at"
            " FROM followthrough_task_events WHERE task_id=? ORDER BY id",
            (task["id"],)).fetchall()]
        source_state = None
        if task["source_version_id"] is not None:
            source = store.db.execute(
                "SELECT state FROM source_versions WHERE id=? AND case_id=?",
                (task["source_version_id"], case_id)).fetchone()
            source_state = source["state"] if source else "missing"
        question_state = None
        if task["question_id"] is not None:
            question = store.db.execute(
                "SELECT state FROM questions WHERE id=? AND case_id=?",
                (task["question_id"], case_id)).fetchone()
            question_state = question["state"] if question else "missing"
        is_open = task["status"] in OPEN_STATUSES
        due = task["due_date"]
        acknowledged = any(event["new_status"] == "acknowledged" for event in history)
        task["history"] = history
        task["source_state"] = source_state
        task["question_state"] = question_state
        task["is_overdue"] = bool(is_open and due and due < day)
        task["is_due_soon"] = bool(is_open and due and day <= due <= soon_through)
        task["needs_recheck"] = bool(is_open and source_state == "superseded")
        # The only action claim this platform makes: completed, which by
        # construction required a recorded acknowledgment first. Anything
        # without that recorded path reports no human action.
        task["human_action_recorded"] = bool(
            task["status"] == "completed" and acknowledged)
        tasks.append(task)
    overdue = [task["id"] for task in tasks if task["is_overdue"]]
    due_soon = [task["id"] for task in tasks if task["is_due_soon"]]
    open_ids = [task["id"] for task in tasks if task["status"] in OPEN_STATUSES]
    return {
        "case_id": case_id,
        "synthetic": True,
        "today": day,
        "due_soon_days": DUE_SOON_DAYS,
        "disclaimer": DISCLAIMER,
        "tasks": tasks,
        "counts": {
            "open": len(open_ids),
            "overdue": len(overdue),
            "due_soon": len(due_soon),
            "deferred": sum(1 for task in tasks if task["status"] == "deferred"),
            "completed": sum(1 for task in tasks if task["status"] == "completed"),
        },
        "overdue_task_ids": overdue,
        "due_soon_task_ids": due_soon,
        "open_task_ids": open_ids,
    }


def followthrough_view(store, case_id: str, today: str | None = None) -> dict:
    """Read-only follow-through projection for one case. Writes nothing.

    Overdue and due-soon flags are derived here from the stored due date
    and the given day (server date by default; tests pass an explicit
    day). Completed and deferred tasks are never overdue: completion is
    history, and a deferral explicitly moved the work out of the open
    queue with a recorded reason. A task anchored to a superseded source
    version is flagged for re-check; the flag is derived, never stored.
    """
    day = _resolve_today(today)
    with store.db:
        store.db.execute("BEGIN")
        return _select(store, case_id, day)


def followthrough_view_in_transaction(store, case_id: str,
                                     today: str | None = None) -> dict:
    """Same projection for callers that already hold a read transaction."""
    return _select(store, case_id, _resolve_today(today))
