"""D8 care-coordination referrals: referral status is tracked as a
product feature (program plan slice D8, design-first).

Design (drafted first, in this docstring and in the D8 section of
``docs/IMPLEMENTATION_STATUS.md``; the build implements exactly this
design and the draft PR is the vehicle for its correction):

A referral is a fictional, case-scoped record of a request to send a
question about the case to another team or specialty for input. It
records the request; it sends nothing, contacts no one, books
nothing, makes no appointment, and performs no handoff outside the
product. The receiving team is named only as a plain specialty label
(for example "cardiology") — never a real destination, address, or
contact.

* Lifecycle. Referral request → status → outcome:
  - ``requested``: the request is recorded with its question,
    specialty label, reason, and pinned materials.
  - ``acknowledged``: the receiving team confirmed receipt, recorded
    by the operator or clinician with an actor label and a reason.
    Only from ``requested``.
  - ``outcome_recorded``: the outcome arrived as a separate record
    (outcome kind + text + anchor). Only from ``acknowledged``.
    Terminal — further work is a new referral, never a reopen
    (mirroring the follow-through rule that completed work stays in
    history).
  Every transition appends one event row — who, when, why, and the
  previous and new status — and history rows are never updated or
  deleted.
* Outcome. Exactly one outcome per referral: a new referral is
  needed for follow-up, so no outcome can silently replace an
  earlier one (mirroring the second-opinion response rule). Outcome
  kinds are pinned:
  - ``accepted``: the receiving team took the referral on for review.
  - ``declined``: the receiving team declined it.
  - ``completed``: the consultation is done; the outcome text records
    what was returned.
  The outcome text is a plain description (10–2000 characters) and
  anchors to one current source version in this case, like a
  second-opinion response anchor. The outcome is a separate record;
  it never overwrites the request.
* Review/audit treatment (the second-opinion pattern, followed
  exactly). A referral carries ``review_state`` (``pending`` /
  ``reviewed_in_demo`` / ``needs_review``) alongside its status.
  Review is a demo acknowledgment: a reviewer label and a scope
  (10–300 characters) move ``pending`` → ``reviewed_in_demo`` and
  append one review event; review events are never updated or
  deleted. Review is refused while ``review_state`` is
  ``needs_review`` ("preserve it and create a new referral") or
  already ``reviewed_in_demo``.
* Amendment-awareness. Receipt of an amendment changes freshness
  and review status: when a pinned material source version — or the
  outcome anchor — is superseded, the referral's ``review_state``
  moves to ``needs_review`` (via ``_invalidate_care_records``,
  extended by this slice) and a ``referral_review_reopened`` event
  is recorded. The request, its materials, and its outcome stay
  visible with their own states; nothing is silently rebound.
* Materials. The request pins 1–50 unique current source versions
  in this case, exactly like a second-opinion request. A material
  that is missing, superseded, or from another case is rejected at
  creation.
* Role visibility. Case-scoped and role-gated from the start
  through the existing generic case gate — no new gate code: a
  patient reads only their own bound case (GET); writes
  (create/acknowledge/outcome/review) are operator/clinician only,
  so a patient POST is denied by role even on their own case; an
  auditor holds no case grants and is denied everywhere. The UI
  renders what the server returns and shows the denial text on a
  403.
* Text guard. Referral text is author-controlled, so the same
  narrow guard as follow-through tasks applies — reused, not
  forked: the validators below call the follow-through checks, so
  the specialty label, reason, outcome text, actor label, and
  reviewer label must not state a clinical recommendation, order,
  eligibility claim, diagnosis, or dose. Human review remains the
  gate; the disclaimer on every view states the boundary.
* What is NOT in this slice. No message, email, or handoff leaves
  the product; no link to a follow-through task or an appointment
  (no speculative coupling); no per-referral link to a snapshot (a
  referral is about a question, not a conclusion — the outcome
  anchors to a source version, like a second-opinion response); no
  C5 evaluation-harness probes yet (a follow-up could add
  referral-lifecycle probes).

Hard limits: no model call exists anywhere in this module (an AST
test pins that); no dimension module is imported (the follow-through
checks are the same care-coordination dimension's pre-existing text
guard, not a dimension slice module, and the guard is one canonical
rule — forking it would let the two drift); no vertical predicate
is read or moved. The module reads only the ledger and the store's
own list method.
"""

from __future__ import annotations

from .followthrough import (
    FollowthroughInputError,
    check_actor,
    check_task_text,
)

STATUSES = frozenset({"requested", "acknowledged", "outcome_recorded"})
OUTCOME_KINDS = frozenset({"accepted", "declined", "completed"})
CHANGE_KINDS = frozenset({"created", "acknowledged", "outcome_recorded"})

# A recorded outcome is terminal: the referral stays in history and
# further work is a new referral.
TERMINAL_STATUSES = frozenset({"outcome_recorded"})

DISCLAIMER = (
    "Fictional referrals only. A referral records a request to send a "
    "question to another team for input; the platform sends no message, "
    "books nothing, and contacts no one. An outcome is a separate record "
    "that never overwrites the request; a referral with a recorded outcome "
    "stays in history, and further work is a new referral."
)


class ReferralInputError(ValueError):
    """A referral request violates the referral contract."""


def _guarded(call):
    """Run a follow-through check, surfacing its failure as ours."""
    try:
        return call()
    except FollowthroughInputError as error:
        raise ReferralInputError(str(error)) from error


def check_specialty(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Specialty label", min_len=1, max_len=120))


def check_reason(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Referral reason", min_len=10, max_len=500))


def check_outcome_text(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Referral outcome", min_len=10, max_len=2000))


def check_actor_label(value: object) -> str:
    return _guarded(lambda: check_actor(value))


def check_change_reason(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Change reason", min_len=10, max_len=600))


def check_review_scope(value: object) -> str:
    return _guarded(lambda: check_task_text(
        value, "Review scope", min_len=10, max_len=300))


def check_outcome_kind(value: object) -> str:
    """A referral outcome kind is one of the three pinned kinds."""
    if value not in OUTCOME_KINDS:
        raise ReferralInputError(
            "Referral outcome kind must be accepted, declined, or completed")
    return value


def referrals_view(store, case_id: str) -> dict:
    """List this case's referrals with materials, outcome, and history.

    Sorted by referral id, oldest first — the order a reader follows
    "what was asked, what happened". Counts are derived, never stored.
    """
    listed = store.list_referrals(case_id)
    referrals = listed["referrals"]
    counts = {"requested": 0, "acknowledged": 0, "outcome_recorded": 0}
    for item in referrals:
        status = (item["current"] or {}).get("status")
        if status in counts:
            counts[status] += 1
    return {
        "case_id": case_id,
        "referrals": referrals,
        "counts": counts,
        "disclaimer": DISCLAIMER,
        "synthetic": True,
    }
