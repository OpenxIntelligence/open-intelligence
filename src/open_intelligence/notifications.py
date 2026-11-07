"""D7 care-coordination notifications: the patient and team learn of
changes and due items (program plan slice D7, design-first).

Design (drafted first, in this docstring and in the D7 section of
``docs/IMPLEMENTATION_STATUS.md``; the build implements exactly this
design and the draft PR is the vehicle for its correction):

A notification is a derived, in-app-only record: one per trigger,
computed from the ledger at read time. Nothing is ever sent anywhere
— no message, email, push, or reminder leaves the product, and no
reminder is scheduled. The trigger kinds are a pinned allowlist;
adding a kind is a code change, never runtime expansion, and there
is no silent self-training or unreviewed expansion (OI-018). No
model call exists anywhere in this module.

* Triggers — each produces exactly one visible notification per
  source record, keyed stably so a trigger cannot duplicate itself:
  - ``followthrough-overdue`` — an open follow-through task whose
    due date is before today. Key carries the due date.
  - ``followthrough-due-soon`` — an open follow-through task due
    within the follow-through due-soon window (7 days). A task is
    due-soon or overdue, never both at once: once the due date
    passes, only the overdue notification derives, so the count per
    task never exceeds one due notification at a time.
  - ``followthrough-recheck`` — an open follow-through task anchored
    to a superseded source version (the task needs re-check). A
    re-review trigger on a task. Key carries the source version id.
  - ``rereview-open`` — an open re-review task: one per newly stale
    snapshot, created by invalidation events, with an assignee and
    an optional due date. A re-review trigger.
  - ``snapshot-stale`` — a stale snapshot whose question is still
    open (the draft needs a new answer). A staleness event.
  - ``appointment-due`` — a scheduled appointment whose date has
    passed (D6 deferred due items to D7: a past due date never
    auto-cancels, it is only flagged — here is where the flag
    becomes a notification). Key carries the scheduled date.
* Why both ``rereview-open`` and ``snapshot-stale`` for one
  amendment: they are different work items with different
  lifecycles — the stale draft needs a new answer (the notification
  lapses when its question closes), while the re-review task is the
  owned follow-up with an assignee and a due date (it lapses only
  when the task closes). The plan names "a re-review trigger, and a
  staleness event" as two separate triggers, each producing one
  notification. No separate notification is derived for options with
  ``review_state='needs_review'``: that is the same event the
  re-review task already owns (one task per newly stale snapshot),
  and a second notification would double-notify one event.
* Keys include the distinguishing value (due date, scheduled date,
  source version id), so a changed due date or a rescheduled
  appointment is a new occurrence — never the resurrection of a
  cleared one. A cleared key never derives again for that role.
* Role visibility. The patient sees due kinds only (overdue,
  due-soon, appointment-due) on their own bound case; operator and
  clinician see all kinds; an auditor sees none (auditors hold no
  case grants). The team sees everything the patient sees plus the
  review work — the patient is never shown review-work
  notifications, and the team is never blind to a due item the
  patient sees.
* Clearing is explicit and per-role. Clearing records (case, key,
  role, who, when) in ``notification_clears``; cleared rows are
  never deleted. Clearing is idempotent: clearing twice is the same
  as clearing once. Clearing acknowledges the alert only — it never
  changes the underlying task, draft, or review item, which stays
  exactly as it was until a human changes it in its own panel.
* Patient clearing carve-out (deliberate, narrow, tested). The
  generic case gate makes patients read-only (GET only), which
  would leave the primary audience of due notifications unable to
  dismiss them. The role check therefore allows a patient to POST
  only to the notifications-clear route, only on their own bound
  case — and the clear handler additionally rejects any key whose
  kind is not patient-visible, so a guessed team-only key cannot be
  cleared by a patient. A clear writes only an acknowledgment row;
  it cannot change, hide, or delete any case content. This is the
  single exception to patient read-only in the product, and it is
  pinned by tests.
* Ordering uses recorded dates only (the trigger's recorded date,
  oldest first), then kind order, then record id — mirroring the
  patient-attention projection. No urgency or priority is inferred.
* What is NOT in this slice. No external delivery of any kind; no
  reminder scheduling (no "send at" — the list is computed at read
  time); no snooze; no new inference; no link from a notification
  to a follow-through task beyond the shared record id; no C5
  evaluation-harness probes yet (a follow-up could add them).

Hard limits: no model call exists anywhere in this module (an AST
test pins that); no dimension module is imported — follow-through
is the same care-coordination dimension's pre-existing view, not a
dimension module, and the ledger is read through the store's own
list methods plus the same SQL predicates the patient-attention
projection already uses for stale snapshots; no vertical predicate
is read or moved. Dates are YYYY-MM-DD strings, ordered
lexicographically, exactly as the rest of the ledger does.
"""

from __future__ import annotations

import re
from datetime import date

from .followthrough import followthrough_view
from .store import InvalidInput, valid_date

# Pinned trigger kinds. The tuple is the allowlist: a notification
# kind exists only if it is listed here, with its key shape, its
# patient visibility, and its ordering.
KIND_ORDER = {
    "followthrough-overdue": 0,
    "followthrough-due-soon": 1,
    "appointment-due": 2,
    "followthrough-recheck": 3,
    "rereview-open": 4,
    "snapshot-stale": 5,
}

# Kinds a patient may see — and therefore may clear — on their own
# bound case. Review work (re-check, re-review, staleness) is team
# work; the patient sees the underlying items in their own panels
# but is never notified about review work.
PATIENT_VISIBLE_KINDS = frozenset({
    "followthrough-overdue",
    "followthrough-due-soon",
    "appointment-due",
})

ROLES = frozenset({"operator", "clinician", "patient", "auditor"})

DISCLAIMER = (
    "Fictional notifications only. This in-app list shows due items "
    "and changes recorded for this fictional case. Nothing is sent "
    "anywhere — no message, email, or reminder leaves the product. "
    "Clearing a notification acknowledges the alert only; the "
    "underlying task, draft, or review item stays exactly as it was "
    "until a human changes it."
)

_KEY_RE = re.compile(
    r"^(followthrough-overdue|followthrough-due-soon|appointment-due):"
    r"([1-9][0-9]*):([0-9]{4}-[0-9]{2}-[0-9]{2})$"
    r"|^(followthrough-recheck):([1-9][0-9]*):([1-9][0-9]*)$"
    r"|^(rereview-open|snapshot-stale):([1-9][0-9]*)$"
)


class NotificationInputError(ValueError):
    """A notification request violates the notification contract."""


def _key(kind: str, record_id: int, value: str | None = None) -> str:
    if value is None:
        return f"{kind}:{record_id}"
    return f"{kind}:{record_id}:{value}"


def check_notification_key(value: object) -> str:
    """Validate a notification key: pinned kind, positive record id,
    and a well-formed distinguishing value for the kinds that carry
    one. Returns the key unchanged; raises otherwise."""
    if not isinstance(value, str):
        raise NotificationInputError("Notification key must be text")
    match = _KEY_RE.fullmatch(value.strip())
    if match is None:
        raise NotificationInputError("Unknown notification key")
    groups = [part for part in match.groups() if part is not None]
    kind, record_id = groups[0], groups[1]
    if kind in ("followthrough-overdue", "followthrough-due-soon",
                "appointment-due"):
        try:
            valid_date(groups[2])
        except InvalidInput:
            raise NotificationInputError(
                "Notification key carries an invalid date") from None
    return value.strip()


def _entry(*, kind: str, title: str, detail: str, record_type: str,
           record_id: int, recorded_date: str | None,
           source_anchor: str, key_value: str | None = None) -> dict:
    return {
        "key": _key(kind, record_id, key_value),
        "kind": kind,
        "title": title,
        "detail": detail,
        "record_type": record_type,
        "record_id": record_id,
        "recorded_date": recorded_date,
        "source_anchor": source_anchor,
        "fictional": True,
    }


def _resolve_today(today: str | None) -> str:
    if today is None:
        return date.today().isoformat()
    try:
        return valid_date(today)
    except InvalidInput:
        raise NotificationInputError("today must use YYYY-MM-DD") from None


def notifications_view(store, case_id: str, role: str,
                       today: str | None = None) -> dict:
    """Derived in-app notifications for one case and one role.

    Reads only; writes nothing. Each trigger in the ledger yields at
    most one entry per role (keys are unique by construction), minus
    the keys this role has explicitly cleared. A cleared key never
    derives again for that role; a changed due date or rescheduled
    appointment is a new key and therefore a new notification. The
    route does not pass ``today`` (the server date is not the
    patient's date); the derivation exists for the view and the
    tests.
    """
    if role not in ROLES:
        raise NotificationInputError("Unknown role for notifications")
    day = _resolve_today(today)
    visible = KIND_ORDER if role in ("operator", "clinician") \
        else PATIENT_VISIBLE_KINDS if role == "patient" else frozenset()
    entries: dict[str, dict] = {}

    def add(entry: dict) -> None:
        if entry["kind"] in visible:
            entries[entry["key"]] = entry

    # Due and re-check triggers on follow-through tasks. The view is
    # the single source of truth for overdue / due-soon / re-check;
    # this slice reuses it rather than re-deriving the flags.
    tasks = followthrough_view(store, case_id, day)["tasks"]
    for task in tasks:
        task_id = int(task["id"])
        due = task.get("due_date")
        if task.get("is_overdue"):
            add(_entry(
                kind="followthrough-overdue",
                title="FICTIONAL \u2014 Follow-through task #"
                      f"{task_id} is overdue.",
                detail=str(task.get("title") or ""),
                record_type="followthrough_task",
                record_id=task_id,
                recorded_date=due,
                source_anchor=f"Follow-through task #{task_id} due {due}",
                key_value=due,
            ))
        elif task.get("is_due_soon"):
            add(_entry(
                kind="followthrough-due-soon",
                title="FICTIONAL \u2014 Follow-through task #"
                      f"{task_id} is due soon.",
                detail=str(task.get("title") or ""),
                record_type="followthrough_task",
                record_id=task_id,
                recorded_date=due,
                source_anchor=f"Follow-through task #{task_id} due {due}",
                key_value=due,
            ))
        if task.get("needs_recheck") and task.get("source_version_id") is not None:
            source_version_id = int(task["source_version_id"])
            add(_entry(
                kind="followthrough-recheck",
                title="FICTIONAL \u2014 Follow-through task #"
                      f"{task_id} needs a re-check: its source changed.",
                detail=str(task.get("title") or ""),
                record_type="followthrough_task",
                record_id=task_id,
                recorded_date=None,
                source_anchor=f"Follow-through task #{task_id} anchored "
                              f"to source version {source_version_id}",
                key_value=str(source_version_id),
            ))

    # Past-due appointments: scheduled, date before today. A past due
    # date never auto-cancels; here it becomes a notification (D6).
    for item in store.list_appointments(case_id)["appointments"]:
        current = item.get("current") or {}
        if current.get("status") != "scheduled":
            continue
        scheduled = current.get("scheduled_date") or ""
        if not scheduled or scheduled >= day:
            continue
        appointment_id = int(item["appointment_id"])
        add(_entry(
            kind="appointment-due",
            title="FICTIONAL \u2014 Appointment #"
                  f"{appointment_id} is past its scheduled date.",
            detail=str(current.get("title") or ""),
            record_type="appointment",
            record_id=appointment_id,
            recorded_date=scheduled,
            source_anchor=(
                f"Appointment #{appointment_id} scheduled {scheduled}"
                + (f" {current['scheduled_time']}"
                   if current.get("scheduled_time") else "")),
            key_value=scheduled,
        ))

    # Open re-review tasks: the owned follow-up for a stale draft.
    for row in store.list_re_review_tasks(case_id):
        if row.get("status") != "open":
            continue
        task_id = int(row["id"])
        add(_entry(
            kind="rereview-open",
            title="FICTIONAL \u2014 Re-review task #"
                  f"{task_id} is open: an earlier draft went stale.",
            detail=f"Draft #{int(row['snapshot_id'])} for question "
                   f"#{int(row['question_id'])} · cause {row['cause']} · "
                   f"assignee {row['assignee_label']}",
            record_type="re_review_task",
            record_id=task_id,
            recorded_date=row.get("due_date"),
            source_anchor=f"Re-review task #{task_id} for snapshot "
                          f"#{int(row['snapshot_id'])}",
        ))

    # Staleness events: stale snapshots whose question is still open.
    # Same predicates as the patient-attention projection; a new
    # answer is still owed, so the event stays visible.
    with store.db:
        store.db.execute("BEGIN")
        stale = store.db.execute(
            "SELECT s.id, s.question_id, s.summary FROM snapshots s "
            "JOIN questions q ON q.id=s.question_id "
            "WHERE s.case_id=? AND s.state='stale' AND q.state='open' "
            "AND q.case_id=? ORDER BY s.id",
            (case_id, case_id)).fetchall()
    for row in stale:
        snapshot_id = int(row["id"])
        add(_entry(
            kind="snapshot-stale",
            title="FICTIONAL \u2014 Earlier draft #"
                  f"{snapshot_id} is stale because a source changed.",
            detail=str(row["summary"]),
            record_type="snapshot",
            record_id=snapshot_id,
            recorded_date=None,
            source_anchor=f"Stale snapshot #{snapshot_id} for "
                          f"Q{int(row['question_id'])}",
        ))

    # Explicit clears: per role, never deleted. A cleared key is
    # omitted for that role only; the same key stays visible to other
    # roles until they clear it too.
    cleared = {
        row["notification_key"]
        for row in store.list_notification_clears(case_id)
        if row["role"] == role
    }
    ordered = sorted(
        (entry for key, entry in entries.items() if key not in cleared),
        key=lambda e: (
            e["recorded_date"] is None,
            e["recorded_date"] or "",
            KIND_ORDER[e["kind"]],
            e["record_type"],
            e["record_id"],
        ),
    )
    counts = {kind: 0 for kind in KIND_ORDER}
    for entry in ordered:
        counts[entry["kind"]] += 1
    return {
        "case_id": case_id,
        "role": role,
        "synthetic": True,
        "today": day,
        "disclaimer": DISCLAIMER,
        "counts": counts,
        "cleared_count": len(cleared),
        "notifications": ordered,
    }
