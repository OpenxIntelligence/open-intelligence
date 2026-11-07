"""D6 care-coordination appointments: the patient can know appointment
times and changes (program plan slice D6, design-first).

Design (drafted first, in this docstring and in the D6 section of
``docs/IMPLEMENTATION_STATUS.md``; the build implements exactly this
design and the draft PR is the vehicle for its correction):

An appointment is a fictional, case-scoped record of a planned
meeting about the case — nothing in the product tells the patient
something is due, and follow-through tasks and receipts exist but no
appointment surface. An appointment carries a short title (what it
is for), an optional purpose (one or two sentences of plain
context), a scheduled date (YYYY-MM-DD, required) and an optional
scheduled time (HH:MM, 24-hour), an optional location (a room, a
clinic name, or a video-link label — plain text, never a real
address or a real scheduling link), and a status. Recording an
appointment records the plan; it does not book anything anywhere.
There is no real scheduling integration in this slice: no calendar,
no invite, no message, no reminder is sent.

* Statuses and transitions. ``scheduled`` is the only open status.
  A reschedule changes the date and/or time and keeps the status
  ``scheduled`` — the change is the event, not a new state. A
  reschedule that changes neither the date nor the time is rejected
  — history records changes, not no-ops. A scheduled appointment
  may be ``cancelled`` or ``completed``.
  Cancelled and completed appointments stay in history; further
  work is recorded as a new appointment, never by reopening (this
  mirrors the follow-through rule that completed work stays in
  history). Every change appends one event row — who made the
  change, when, why, and the previous and new date, time, and
  status — and history rows are never updated or deleted.
* Change history. Each appointment carries its full event history
  in order: created, then each reschedule, cancellation, and
  completion with previous and new values. The list view projects
  the current appointment plus its history, oldest first (mirroring
  ``list_visits``).
* Role visibility. Appointments are case-scoped and role-gated from
  the start through the existing generic case gate — no new gate
  code: a patient reads only their own bound case (GET); writes
  (create/change) are operator/clinician only, so a patient POST is
  denied by role even on their own case; an auditor holds no case
  grants and is denied everywhere. The UI renders what the server
  returns and shows the denial text on a 403; it invents no
  visibility rule of its own.
* Text guard. Appointment text is author-controlled, so the same
  narrow guard as follow-through tasks applies — reused, not
  forked: the validators below call the follow-through checks, so
  the title, purpose, location, actor label, and change reason must
  not state a clinical recommendation, order, eligibility claim,
  diagnosis, or dose. Human review remains the gate; the disclaimer
  on every view states the boundary.
* What is NOT in this slice. No reminder or notification delivery
  (that is D7, which builds on follow-through tasks, re-review
  tasks, and staleness events); no link to a follow-through task
  (no speculative coupling); no calendar invite or external
  scheduling; no past-visit semantics (visits already record what
  happened — appointments record what is planned; the two are
  distinct tables and are never merged); no per-appointment link to
  a source version (an appointment is a plan, not evidence — it
  cites no source and carries no anchor).

Hard limits: no model call exists anywhere in this module (an AST
test pins that); no dimension module is imported (the follow-through
checks are the same care-coordination dimension's pre-existing text
guard, not a dimension slice module, and the guard is one canonical
rule — forking it would let the two drift); no vertical predicate
is read or moved. The module reads only the ledger and the store's
own list method. Dates are YYYY-MM-DD strings, ordered
lexicographically, exactly as the rest of the ledger does; times
are HH:MM strings, 24-hour. A scheduled date is a recorded plan,
not a booking; the platform sends nothing and books nothing.
"""

from __future__ import annotations

import re
from datetime import date

from .followthrough import (
    FollowthroughInputError,
    check_actor,
    check_optional_text,
    check_task_text,
)
from .store import InvalidInput, valid_date

STATUSES = frozenset({"scheduled", "cancelled", "completed"})
ACTIONS = frozenset({"reschedule", "cancel", "complete"})
CHANGE_KINDS = frozenset({"created", "rescheduled", "cancelled", "completed"})

# A change out of a terminal status is refused: the appointment stays
# in history and further work is a new appointment.
TERMINAL_STATUSES = frozenset({"cancelled", "completed"})

DISCLAIMER = (
    "Fictional appointments only. A scheduled date is a recorded plan, "
    "not a booking: the platform sends no message, books nothing, and "
    "contacts no one. A cancelled or completed appointment stays in "
    "history; record a new appointment for further work."
)

_TIME_RE = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


class AppointmentInputError(ValueError):
    """An appointment request violates the appointment contract."""


def _guarded(call):
    """Run a follow-through check, surfacing its failure as ours."""
    try:
        return call()
    except FollowthroughInputError as error:
        raise AppointmentInputError(str(error)) from error


def check_title(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Appointment title", min_len=1, max_len=120))


def check_purpose(value: object) -> str:
    return _guarded(lambda: check_optional_text(
        value, "Appointment purpose", max_len=1000))


def check_location(value: object) -> str:
    return _guarded(lambda: check_optional_text(
        value, "Appointment location", max_len=200))


def check_actor_label(value: object) -> str:
    return _guarded(lambda: check_actor(value))


def check_reason(value: object, *, required: bool) -> str:
    if required:
        return _guarded(lambda: check_task_text(
            value, "Change reason", min_len=10, max_len=600))
    return _guarded(lambda: check_optional_text(
        value, "Creation note", max_len=600))


def check_scheduled_date(value: object) -> str:
    """A scheduled date is required and must be YYYY-MM-DD."""
    if not isinstance(value, str):
        raise AppointmentInputError("Scheduled date must use YYYY-MM-DD")
    try:
        return valid_date(value)
    except InvalidInput:
        raise AppointmentInputError("Scheduled date must use YYYY-MM-DD") from None


def check_time(value: object, field: str = "Scheduled time") -> str | None:
    """Validate an optional HH:MM (24-hour) time; None means not supplied."""
    if value is None:
        return None
    if not isinstance(value, str) or not _TIME_RE.fullmatch(value):
        raise AppointmentInputError(f"{field} must use HH:MM (24-hour)")
    return value


def appointments_view(store, case_id: str, today: str | None = None) -> dict:
    """List this case's appointments with full change history.

    Sorted by scheduled date, then id — the order a patient reads
    "what is due" in. When ``today`` (YYYY-MM-DD) is supplied, each
    scheduled appointment also carries ``days_until`` (negative when
    the scheduled date has passed) and ``past_due_date``; a past due
    date never auto-cancels or auto-completes anything — it is only
    flagged, and D7 is where due items become notifications. The
    route does not pass ``today`` (the server date is not the
    patient's date); the derivation exists for the view and the
    tests. Counts are derived, never stored.
    """
    if today is not None:
        try:
            valid_date(today)
        except InvalidInput:
            raise AppointmentInputError("today must use YYYY-MM-DD") from None
    listed = store.list_appointments(case_id)
    appointments = listed["appointments"]
    ordered = sorted(
        appointments,
        key=lambda item: ((item["current"] or {}).get("scheduled_date") or "",
                          item["appointment_id"]),
    )
    counts = {"scheduled": 0, "cancelled": 0, "completed": 0, "past_due_date": 0}
    for item in ordered:
        current = item["current"] or {}
        status = current.get("status")
        if status in counts:
            counts[status] += 1
        item["days_until"] = None
        item["past_due_date"] = False
        if today is not None and status == "scheduled":
            scheduled = current.get("scheduled_date") or ""
            if scheduled:
                item["days_until"] = (
                    date.fromisoformat(scheduled).toordinal()
                    - date.fromisoformat(today).toordinal()
                )
                if item["days_until"] < 0:
                    item["past_due_date"] = True
                    counts["past_due_date"] += 1
    return {
        "case_id": case_id,
        "appointments": ordered,
        "counts": counts,
        "disclaimer": DISCLAIMER,
        "synthetic": True,
    }
