"""Snapshot review record contract, issue 120 (WS-11).

This is a pure, tested contract for recording a human review of a
snapshot with an explicit basis and provenance. It is NOT a new review
engine, and it does NOT change the existing demo acknowledgement in
CaseStore.acknowledge_demo_review, the option review in
CaseStore.review_option, or the durable review queue in PR 150.

Rules, fail closed:
- Only a snapshot in state "draft" can be reviewed. A stale snapshot,
  an already reviewed snapshot, or any other state is denied.
- Action must be "accepted" or "rejected". Anything else is denied.
- Basis must be a string of 10 to 300 characters. It is the reviewer's
  stated reason, not a clinical decision, and it must not be empty.
- Provenance must be a positive integer source version id. A missing,
  zero, negative, or non-integer provenance is denied.
- A review record never overwrites history: it returns a new record
  dict, it does not mutate the snapshot, and it never claims clinical
  authority, production authentication, or professional sign-off.
  Reviewer identity here is a label only, exactly as in the existing
  demo acknowledgement; real authentication is the issue 114 gate,
  not this record.
"""

from __future__ import annotations


def review_snapshot(snapshot_state, action, basis, provenance_source_version_id):
    """Return a review decision record, or a denial, for one snapshot.

    Returns a dict with ``allowed`` (bool), ``reason`` (str), and, when
    allowed, ``record`` (dict with action, basis, and provenance).
    Reasons: accepted, rejected, not_draft, invalid_action,
    invalid_basis, invalid_provenance.
    """
    if snapshot_state != "draft":
        return {"allowed": False, "reason": "not_draft"}
    if action not in ("accepted", "rejected"):
        return {"allowed": False, "reason": "invalid_action"}
    if not isinstance(basis, str) or not 10 <= len(basis.strip()) <= 300:
        return {"allowed": False, "reason": "invalid_basis"}
    if (
        type(provenance_source_version_id) is not int
        or provenance_source_version_id <= 0
    ):
        return {"allowed": False, "reason": "invalid_provenance"}
    return {
        "allowed": True,
        "reason": action,
        "record": {
            "action": action,
            "basis": basis.strip(),
            "provenance_source_version_id": provenance_source_version_id,
        },
    }
