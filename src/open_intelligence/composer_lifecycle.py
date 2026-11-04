"""Composer investigation lifecycle contract, issue 118 (WS-09).

This is a pure, tested contract for the bounded Composer flow in
issue 118: selected finding -> question -> evidence -> proposed next
steps, with explicit running, stale, and held states and a durable
receipt. It is NOT a model call, NOT a new patient store, and NOT the
rights broker in PR 140 or the quoted evidence handoff in PR 143.

Rules, fail closed:
- An investigation starts in state "running" when created with a
  finding key, a question, and at least one evidence source version id.
- Evidence must be added only while the investigation is running.
  Adding evidence to a stale or held investigation is denied.
- An amendment to any cited source version marks the investigation
  "stale". A stale investigation cannot add evidence or produce next
  steps until it is revalidated with a replacement source version.
- A held investigation is paused by an explicit hold reason of 10 to
  300 characters. A held investigation cannot add evidence or produce
  next steps until it is released.
- Next steps are produced only from a running investigation, and the
  durable receipt is a fingerprint of the finding, question, evidence
  source version ids, and next steps. The receipt never claims clinical
  authority, and next steps are proposed steps only, never treatment
  selection, ranking, dosing, eligibility, diagnosis, or prognosis.
- Empty finding, empty question, empty evidence, or an empty hold
  reason are all denied.
"""

from __future__ import annotations

import hashlib
import json


def _fingerprint(finding_key, question, evidence_ids, next_steps):
    payload = json.dumps(
        {
            "finding_key": finding_key,
            "question": question,
            "evidence_ids": sorted(evidence_ids),
            "next_steps": list(next_steps),
        },
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ComposerInvestigation:
    """In-memory lifecycle for one bounded Composer investigation."""

    def __init__(self, finding_key, question, evidence_ids):
        if not isinstance(finding_key, str) or not finding_key.strip():
            raise ValueError("Finding key is required")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question is required")
        if not evidence_ids:
            raise ValueError("At least one evidence source version id is required")
        self.finding_key = finding_key
        self.question = question
        self.evidence_ids = list(evidence_ids)
        self.state = "running"
        self.hold_reason = None

    def add_evidence(self, source_version_id):
        if self.state != "running":
            return {"allowed": False, "reason": f"cannot_add_evidence_when_{self.state}"}
        self.evidence_ids.append(source_version_id)
        return {"allowed": True, "reason": "evidence_added"}

    def amend_source(self, source_version_id):
        if source_version_id in self.evidence_ids:
            self.state = "stale"
            return {"allowed": True, "reason": "marked_stale"}
        return {"allowed": False, "reason": "source_not_cited"}

    def hold(self, reason):
        if not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 300:
            return {"allowed": False, "reason": "invalid_hold_reason"}
        self.state = "held"
        self.hold_reason = reason.strip()
        return {"allowed": True, "reason": "held"}

    def release(self):
        if self.state != "held":
            return {"allowed": False, "reason": "not_held"}
        self.state = "running"
        self.hold_reason = None
        return {"allowed": True, "reason": "released"}

    def revalidate(self, replacement_source_version_id):
        if self.state != "stale":
            return {"allowed": False, "reason": "not_stale"}
        self.evidence_ids.append(replacement_source_version_id)
        self.state = "running"
        return {"allowed": True, "reason": "revalidated"}

    def next_steps(self, steps):
        if self.state != "running":
            return {"allowed": False, "reason": f"cannot_produce_next_steps_when_{self.state}"}
        if not steps:
            return {"allowed": False, "reason": "empty_next_steps"}
        return {
            "allowed": True,
            "reason": "next_steps",
            "receipt": _fingerprint(
                self.finding_key, self.question, self.evidence_ids, steps
            ),
            "steps": list(steps),
        }
