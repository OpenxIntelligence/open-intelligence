"""D9 care-coordination care-team collaboration: patient and team share
updates in the product, not outside it (program plan slice D9,
design-first).

Design (drafted first, in this docstring and in the D9 section of
``docs/IMPLEMENTATION_STATUS.md``; the build implements exactly this
design and the draft PR is the vehicle for its correction):

Two record kinds, one module — shared updates and handoffs. Both are
fictional, case-scoped records over the ledger. Nothing here sends a
message, email, or handoff outside the product; nothing books
anything or contacts anyone. The second-opinion and survivorship
patterns are the model: pinned materials, separate records that never
overwrite each other, append-only history, and ``review_state``
(``pending`` / ``reviewed_in_demo`` / ``needs_review``) with demo
review and amendment-driven reopening.

* Shared updates. A team update is a short dated note posted by the
  operator or clinician and visible to the whole team — including
  the patient on their own bound case. Fields: ``update_text``
  (10–1000 characters, descriptive-only), ``author_label`` (the
  person who posted it), and ``author_role`` (``operator`` or
  ``clinician``, taken from the session account at the route, never
  free text). An update pins no evidence and links no question: it
  is a note about the shared record, not a conclusion about it, so
  no amendment can reopen it — its review state is a demo
  acknowledgment only (reviewer label, scope 10–300 characters,
  ``pending`` → ``reviewed_in_demo``; review is refused once
  reviewed). The patient sees exactly the same shared record as
  the clinician; the role boundary is write access, not a hidden
  subset — that is the acceptance, "a clinician and a patient
  account see the same case with role-appropriate views".
* Handoffs. A handoff records a transfer of responsibility for a
  case question from one actor to another: the question, a
  ``from_actor`` and a ``to_actor`` (labels, 2–80 characters
  each), a reason in plain words (10–500 characters), and 1–50
  pinned current source versions as the handed-over materials
  (exactly like a referral's materials). Lifecycle:
  - ``open``: the handoff is recorded, awaiting the receiving
    actor's acknowledgment.
  - ``acknowledged``: the receiving actor confirmed receipt
    (actor label and reason, only from ``open``).
  - ``closed``: the receiving side recorded the handoff as taken
    up (actor label and closing note, only from ``acknowledged``).
    Terminal — further work is a new handoff, never a reopen
    (mirroring the follow-through rule that completed work stays
    in history).
  Every transition appends one event row — who, when, why, and the
  previous and new status — and history rows are never updated or
  deleted.
* Review/audit treatment (the second-opinion pattern, followed
  exactly). A handoff carries ``review_state`` alongside its
  status. Review is a demo acknowledgment: a reviewer label and a
  scope (10–300 characters) move ``pending`` →
  ``reviewed_in_demo`` and append one review event; review events
  are never updated or deleted. Review is refused while
  ``review_state`` is ``needs_review`` ("preserve it and create a
  new handoff") or already ``reviewed_in_demo``.
* Amendment-awareness. Receipt of an amendment changes freshness
  and review status: when a pinned handoff material is superseded,
  the handoff's ``review_state`` moves to ``needs_review`` (via
  ``_invalidate_care_records``, extended by this slice to return
  the invalidated handoffs alongside second opinions,
  survivorship items, and referrals; the import result gains
  ``invalidated_handoffs``). The handoff, its materials, and its
  history stay visible with their own states; nothing is silently
  rebound.
* Role visibility. Case-scoped and role-gated from the start
  through the existing generic case gate — no new gate code: a
  patient reads only their own bound case (GET); writes
  (post update, review update, create/acknowledge/close/review
  handoff) are operator/clinician only, so a patient POST is
  denied by role even on their own case; an auditor holds no case
  grants and is denied everywhere. The UI renders what the server
  returns and shows the denial text on a 403.
* Text guard. Team-collaboration text is author-controlled, so
  the same narrow guard as follow-through tasks applies —
  reused, not forked: the validators below call the
  follow-through checks, so the update text, author labels,
  handoff actors, reasons, closing note, and reviewer labels
  must not state a clinical recommendation, order, eligibility
  claim, diagnosis, or dose. Human review remains the gate; the
  disclaimer on every view states the boundary.
* What is NOT in this slice. No message, email, or handoff
  leaves the product; no link to a follow-through task or an
  appointment (no speculative coupling); no per-record link to a
  snapshot (a handoff is about a question, not a conclusion);
  updates carry no question link and no materials (a note about
  the shared record, not evidence about it); no C5
  evaluation-harness probes yet (a follow-up could add
  collaboration-lifecycle probes).

Hard limits: no model call exists anywhere in this module (an AST
test pins that); no dimension module is imported (the
follow-through checks are the same care-coordination dimension's
pre-existing text guard, not a dimension slice module, and the
guard is one canonical rule — forking it would let the two drift);
no vertical predicate is read or moved. The module reads only the
ledger and the store's own list methods.
"""

from __future__ import annotations

from .followthrough import (
    FollowthroughInputError,
    check_actor,
    check_task_text,
)

HANDOFF_STATUSES = frozenset({"open", "acknowledged", "closed"})
HANDOFF_CHANGE_KINDS = frozenset({"created", "acknowledged", "closed"})

# A closed handoff is terminal: the handoff stays in history and
# further work is a new handoff.
TERMINAL_HANDOFF_STATUSES = frozenset({"closed"})

AUTHOR_ROLES = frozenset({"operator", "clinician"})

DISCLAIMER = (
    "Fictional care-team records only. A shared update is a note the "
    "patient and team read in the product; a handoff records a transfer "
    "of responsibility for a case question. The platform sends no message, "
    "books nothing, and contacts no one. A closed handoff stays in history, "
    "and further work is a new handoff."
)


class TeamCollaborationInputError(ValueError):
    """A care-team record violates the collaboration contract."""


def _guarded(call):
    """Run a follow-through check, surfacing its failure as ours."""
    try:
        return call()
    except FollowthroughInputError as error:
        raise TeamCollaborationInputError(str(error)) from error


def check_update_text(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Team update", min_len=10, max_len=1000))


def check_author_label(value: object) -> str:
    return _guarded(lambda: check_actor(value))


def check_author_role(value: object) -> str:
    """An update author is the operator or the clinician on the account."""
    if value not in AUTHOR_ROLES:
        raise TeamCollaborationInputError(
            "Update author role must be operator or clinician")
    return value


def check_handoff_reason(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Handoff reason", min_len=10, max_len=500))


def check_change_reason(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Change reason", min_len=10, max_len=600))


def check_close_note(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Closing note", min_len=10, max_len=600))


def check_review_scope(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Review scope", min_len=10, max_len=300))


def care_team_view(store, case_id: str) -> dict:
    """One shared view: the team's updates and handoffs for this case.

    Sorted by record id, oldest first — the order a reader follows
    "what was shared, what was handed over". Counts are derived,
    never stored. The patient sees the same record as the clinician;
    the role boundary is write access, not visibility.
    """
    updates = store.list_team_updates(case_id)["updates"]
    handoffs = store.list_handoffs(case_id)["handoffs"]
    counts = {"updates": len(updates), "open": 0, "acknowledged": 0, "closed": 0}
    for item in handoffs:
        status = (item["current"] or {}).get("status")
        if status in counts:
            counts[status] += 1
    return {
        "case_id": case_id,
        "updates": updates,
        "handoffs": handoffs,
        "counts": counts,
        "disclaimer": DISCLAIMER,
        "synthetic": True,
    }
