"""Issue #20 research draft: proposal/receipt types + ledger-state mapping.

FICTIONAL RESEARCH ONLY — branch work, NOT core, NOT imported by src/.
Do not import this module from src/open_intelligence/. No database access,
no migrations, no model calls, no new dependencies (stdlib only: dataclasses, re).

Every proposal and receipt produced here is a CANDIDATE for human review, never
a clinical fact, diagnosis, treatment order, or eligibility determination.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --- Effect classes (from the experimental-loop research note) ---
EFFECT_CLASSES = frozenset({"A", "B", "C", "SIMULATION_ONLY"})
# A: synthetic/general computational engineering (auto-runnable only within
#    budget/tool/environment controls). B: authorized case-specific computation
#    (candidate artifact only). C: external physical/clinical work (humans own
#    every order/execution; AI drafts handoffs at most). SIMULATION_ONLY:
#    explicitly labeled planning-only; did not execute.

PROPOSAL_STATES = frozenset({
    "draft", "scoped", "authorized", "queued", "running", "result-ready",
    "independently-checked", "human-review", "accepted-as-evidence",
    "rejected", "inconclusive", "quarantined", "canceled",
    "budget-exhausted", "superseded",
})

# Allowed forward transitions for the draft proposal lifecycle. Terminal:
# accepted-as-evidence, rejected, inconclusive, quarantined, canceled,
# budget-exhausted, superseded. Re-entry only via a NEW proposal id.
# Any non-terminal state may move to superseded when an invalidation event
# (source/evidence/rights change, tool revision, cutoff change) lands; the
# draft never auto-rebases onto new inputs. (Loop cycle 1 fix: result-ready
# and the other non-terminal states previously had no superseded edge, so
# invalidate_on_event()'s "supersede" mapping was unreachable from them.)
PROPOSAL_TRANSITIONS = {
    "draft": {"scoped", "canceled", "quarantined", "superseded"},
    "scoped": {"authorized", "rejected", "canceled", "quarantined", "superseded"},
    "authorized": {"queued", "canceled", "quarantined", "superseded"},
    "queued": {"running", "canceled", "budget-exhausted", "quarantined", "superseded"},
    "running": {"result-ready", "canceled", "budget-exhausted", "quarantined", "superseded"},
    "result-ready": {"independently-checked", "quarantined", "canceled", "superseded"},
    "independently-checked": {"human-review", "quarantined", "canceled", "superseded"},
    "human-review": {"accepted-as-evidence", "rejected", "inconclusive", "quarantined", "superseded"},
}

# Existing ledger states this draft maps onto (observed in store.py; the draft
# never adds, renames, or migrates them).
LEDGER_QUESTION = frozenset({"open", "addressed"})
LEDGER_SNAPSHOT = frozenset({"draft", "reviewed_in_demo", "stale"})
LEDGER_SOURCE = frozenset({"current", "superseded"})
LEDGER_EVIDENCE = frozenset({"current", "superseded", "withdrawn"})
LEDGER_RIGHTS = frozenset({"active", "revoked", "superseded"})

_CLINICAL_LANGUAGE = re.compile(
    r"\b(recommend\w*|prescrib\w*|eligible|diagnos\w*)\b"
    r"|\bshould\s+(receive|undergo|get|start|take)\b"
    r"|\bmust\s+(receive|undergo)\b"
    r"|\bbest\s+(treatment|therapy|option|drug)\b"
    r"|\border\s+(this|the)\s+(treatment|therapy|procedure)\b"
    r"|\bstart\s+treatment\b",
    re.IGNORECASE,
)


class DraftError(ValueError):
    """A draft proposal/receipt violates its own research contract."""


def _require_fictional_case(case_id: str | None) -> str | None:
    if case_id is not None and not case_id.startswith("FIC-"):
        raise DraftError("case-bound drafts use fictional FIC-* cases only")
    return case_id


def _no_clinical_language(text: str, field_name: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise DraftError(f"{field_name} is required")
    if _CLINICAL_LANGUAGE.search(text):
        raise DraftError(f"{field_name} must not state clinical advice, diagnosis, or eligibility")
    return text.strip()


@dataclass(frozen=True)
class ExperimentProposalDraft:
    """Minimal candidate proposal. Immutable; revisions are new ids."""

    id: str  # e.g. ISSUE20-P-001
    case_id: str | None  # FIC-* or None for case-free engineering checks
    question_id: int
    hypothesis_ids: tuple[str, ...]
    kind: str  # e.g. source-version-compare, specimen-identity-check
    stated_prediction: str
    falsifier: str  # negative control / what would disprove it (required)
    input_refs_and_versions: tuple[str, ...]  # e.g. ("PATH-20A@2", "EV-20C@2")
    as_known_at: str  # frozen cutoff, YYYY-MM-DD
    intended_decision_relevance: str  # which review this might inform, no orders
    method_ref: str  # runnable procedure reference (gate-4 design section)
    run_environment: str  # isolated digital env label; class C has no auto env
    permission_scope: str  # case consent/purpose or "synthetic-engineering"
    rights_status: str  # e.g. original-synthetic / rights-row id + state
    expected_signal: str
    measurement_plan: str
    uncertainty_limits: str
    estimated_budget: str  # compute/time/cost note, no execution by itself
    effect_class: str  # A | B | C | SIMULATION_ONLY
    owner: str  # human owner label
    proposal_state: str = "draft"

    def validated(self) -> "ExperimentProposalDraft":
        if self.effect_class not in EFFECT_CLASSES:
            raise DraftError("Unknown effect class")
        if self.proposal_state not in PROPOSAL_STATES:
            raise DraftError("Unknown proposal state")
        _require_fictional_case(self.case_id)
        _no_clinical_language(self.stated_prediction, "stated_prediction")
        _no_clinical_language(self.falsifier, "falsifier")
        _no_clinical_language(self.intended_decision_relevance, "intended_decision_relevance")
        if not self.hypothesis_ids:
            raise DraftError("At least one hypothesis id is required")
        if not self.input_refs_and_versions:
            raise DraftError("Input refs with versions are required")
        if not re.fullmatch(r"202\d-\d\d-\d\d", self.as_known_at):
            raise DraftError("as_known_at must be a YYYY-MM-DD cutoff")
        if self.effect_class == "C" and self.run_environment.strip().lower().startswith("auto"):
            raise DraftError("Class C work has no automatic execution environment")
        return self


@dataclass(frozen=True)
class EvaluationRunReceiptDraft:
    """Immutable record of one attempt (including denial/null). One per attempt."""

    proposal_id: str
    attempt_id: str  # unique per attempt; repeats never reuse ids
    actual_execution_state: str  # executed | denied | failed | null | simulation_only
    input_digests: tuple[str, ...]  # sha256 of each frozen input
    source_and_code_versions: tuple[str, ...]
    environment: str
    parameters_seeds: str
    started_ended: str  # ISO interval or "not-started (denied)"
    cost_record: str
    observed_metrics: str
    uncertainty: str
    comparator: str  # baseline arm from the gate-4 design
    reproduction_status: str  # reproduced | not-yet-reproduced | not-reproducible
    independent_verification: str  # verifier label or "pending"
    invalidation_dependencies: tuple[str, ...]
    reviewer: str
    review_decision: str  # pending | accepted | rejected | inconclusive

    def validated(self, owner: str) -> "EvaluationRunReceiptDraft":
        if self.actual_execution_state not in (
            "executed", "denied", "failed", "null", "simulation_only"
        ):
            raise DraftError("Unknown execution state")
        if self.reviewer.strip() == owner.strip():
            raise DraftError("Self-approval is denied: reviewer must differ from owner")
        if self.actual_execution_state == "denied" and self.started_ended != "not-started (denied)":
            raise DraftError("Denied runs record not-started (denied)")
        return self


def transition(proposal: ExperimentProposalDraft, to_state: str) -> ExperimentProposalDraft:
    """Return a new draft in `to_state` if the transition is allowed."""
    allowed = PROPOSAL_TRANSITIONS.get(proposal.proposal_state, set())
    if to_state not in allowed:
        raise DraftError(
            f"Transition {proposal.proposal_state} -> {to_state} is not allowed"
        )
    return ExperimentProposalDraft(
        **{**proposal.__dict__, "proposal_state": to_state}
    )


def ledger_mapping() -> dict[str, dict[str, str]]:
    """How draft states map onto (not into) the existing investigation ledger.

    Pure documentation-as-data: no ledger rows are read or written. A refreshed
    computation NEVER flips a snapshot to reviewed; only the existing scoped
    human review does that.
    """
    return {
        "draft": {"question": "open (unchanged)", "snapshot": "none yet",
                  "rule": "drafting a proposal changes no ledger state"},
        "scoped": {"question": "open (unchanged)", "snapshot": "none yet",
                   "rule": "scoping records relevance; ledger untouched"},
        "authorized": {"question": "open (unchanged)", "snapshot": "none yet",
                       "rule": "authorization is a permission gate, not a conclusion"},
        "queued": {"question": "open (unchanged)", "snapshot": "none yet",
                   "rule": "queueing changes no ledger state"},
        "running": {"question": "open (unchanged)", "snapshot": "none yet",
                    "rule": "execution runs isolated; ledger untouched until review"},
        "result-ready": {"question": "open (unchanged)", "snapshot": "none yet",
                         "rule": "results are candidates; no snapshot created automatically"},
        "independently-checked": {"question": "open (unchanged)", "snapshot": "none yet",
                                  "rule": "checker differs from proposer; still no ledger write"},
        "human-review": {"question": "open until the EXISTING review acts",
                         "snapshot": "a human may then author a normal draft snapshot",
                         "rule": "only create_snapshot + acknowledge_demo_review change ledger state"},
        "accepted-as-evidence": {"question": "addressed ONLY via the existing review path",
                                 "snapshot": "reviewed_in_demo ONLY via the existing review path",
                                 "rule": "this label is metadata; the ledger transition is human-owned"},
        "rejected": {"question": "open (unchanged)", "snapshot": "none",
                     "rule": "rejection is recorded on the draft, not the ledger"},
        "inconclusive": {"question": "open (unchanged)", "snapshot": "none",
                         "rule": "null/unknown retained; never collapsed into negative"},
        "quarantined": {"question": "open (unchanged)",
                        "snapshot": "existing quarantine table owns wrong-subject bytes",
                        "rule": "draft quarantined; ledger quarantine path unchanged"},
        "canceled": {"question": "open (unchanged)", "snapshot": "none",
                     "rule": "terminal; restart requires a new proposal id"},
        "budget-exhausted": {"question": "open (unchanged)", "snapshot": "none",
                             "rule": "terminal; restart requires a new proposal id"},
        "superseded": {"question": "open (unchanged)", "snapshot": "none",
                       "rule": "input/rights change supersedes the draft; ledger staleness rules own snapshots"},
    }


def invalidate_on_event() -> dict[str, str]:
    """Which external events supersede a draft proposal (pure mapping)."""
    return {
        "source_amendment": "supersede drafts citing the superseded source version",
        "evidence_amendment_or_withdrawal": "supersede drafts citing that evidence version",
        "rights_revocation_or_correction": "supersede drafts depending on that rights row",
        "consent_revocation": "class-B drafts for that case become quarantined; no further runs",
        "tool_or_model_revision": "supersede result-ready drafts; receipts keep old version pinned",
        # No ledger operation reassigns a specimen (amendments cannot change
        # it; assets are immutable), so this trigger is paper-only: it fires
        # only if a future scoped decision ever introduces such an event.
        "specimen_reassignment": "supersede drafts citing the reassigned specimen link",
        "cutoff_change": "supersede; a new as_known_at requires a new proposal id",
    }


# --- Gate 5: deterministic rule-assisted candidate generator (draft only) ---
# Pure functions over caller-supplied frozen dicts. No I/O, no DB, no model
# calls, no ledger writes. Model-assisted generation is NOT included: it is
# not justified yet (see docs/research/issue-20/05_ASSISTANCE_JUSTIFICATION.md).

@dataclass(frozen=True)
class CandidateSet:
    proposed: tuple[ExperimentProposalDraft, ...]
    excluded: tuple[dict, ...]  # each: {candidate_kind, reason}


def _base_proposal(seq: int, case_id: str | None, question_id: int,
                   kind: str, prediction: str, falsifier: str,
                   inputs: tuple[str, ...], cutoff: str,
                   relevance: str, method_ref: str,
                   effect_class: str, owner: str) -> ExperimentProposalDraft:
    return ExperimentProposalDraft(
        id=f"ISSUE20-P-{seq:03d}", case_id=case_id, question_id=question_id,
        hypothesis_ids=(f"ISSUE20-H-{seq:03d}",), kind=kind,
        stated_prediction=prediction, falsifier=falsifier,
        input_refs_and_versions=inputs, as_known_at=cutoff,
        intended_decision_relevance=relevance, method_ref=method_ref,
        run_environment="isolated-stdlib-check",
        permission_scope="synthetic-engineering" if case_id is None
        else f"fictional-case-review:{case_id}",
        rights_status="original-synthetic",
        expected_signal="a reviewer-readable flag with exact version anchors",
        measurement_plan="compare flag targets against ISSUE20-GT/1 (§3 quantities)",
        uncertainty_limits="flags are candidates; absence of a flag is not proof of absence",
        estimated_budget="negligible compute; reviewer minutes dominate",
        effect_class=effect_class, owner=owner,
    ).validated()


def propose_version_checks(frozen_versions: list[dict], cutoff: str,
                           owner: str, seq_start: int = 1) -> CandidateSet:
    """Rule R1: flag any citation of a superseded version as current.

    frozen_versions: [{doc, cited_version, current_version, case_id,
    question_id}]. Pure; never reads the ledger.
    """
    proposed: list[ExperimentProposalDraft] = []
    excluded: list[dict] = []
    seq = seq_start
    for row in frozen_versions:
        if row["cited_version"] != row["current_version"]:
            proposed.append(_base_proposal(
                seq, row.get("case_id"), int(row["question_id"]),
                "source-version-compare",
                f"Citation {row['doc']}@{row['cited_version']} may be stale; "
                f"current is {row['doc']}@{row['current_version']}.",
                f"Show the citing draft already references "
                f"{row['doc']}@{row['current_version']}.",
                (f"{row['doc']}@{row['cited_version']}",
                 f"{row['doc']}@{row['current_version']}"),
                cutoff,
                "inform the existing scoped review of which version is current",
                "gate-4 §2 step 5", "A", owner))
            seq += 1
        else:
            excluded.append({"candidate_kind": "source-version-compare",
                             "reason": f"{row['doc']} citation already current"})
    return CandidateSet(tuple(proposed), tuple(excluded))


def propose_specimen_checks(frozen_docs: list[dict], cutoff: str,
                            owner: str, seq_start: int = 100) -> CandidateSet:
    """Rule R2: flag same-document versions with differing specimen ids."""
    proposed: list[ExperimentProposalDraft] = []
    excluded: list[dict] = []
    seq = seq_start
    for row in frozen_docs:
        specimens = row.get("specimens_by_version", {})
        if len(set(specimens.values())) > 1:
            proposed.append(_base_proposal(
                seq, row.get("case_id"), int(row["question_id"]),
                "specimen-identity-check",
                f"Document {row['doc']} versions carry differing fictional "
                f"specimen ids; they must not be treated as one specimen.",
                "Show all cited versions share one specimen id.",
                tuple(f"{row['doc']}@{v}" for v in sorted(specimens)),
                cutoff,
                "inform the existing scoped review that specimens must stay distinct",
                "gate-4 §2 step 5", "A", owner))
            seq += 1
        else:
            excluded.append({"candidate_kind": "specimen-identity-check",
                             "reason": f"{row['doc']} specimens consistent"})
    return CandidateSet(tuple(proposed), tuple(excluded))


def propose_evidence_freshness_checks(frozen_links: list[dict], cutoff: str,
                                      owner: str, seq_start: int = 200) -> CandidateSet:
    """Rule R3: flag assessments pinned to superseded/withdrawn evidence."""
    proposed: list[ExperimentProposalDraft] = []
    excluded: list[dict] = []
    seq = seq_start
    for row in frozen_links:
        if row.get("evidence_state") != "current":
            proposed.append(_base_proposal(
                seq, row.get("case_id"), int(row["question_id"]),
                "evidence-freshness-check",
                f"Assessment {row['assessment_ref']} cites fictional evidence "
                f"{row['evidence_ref']} whose state is {row['evidence_state']}.",
                "Show a reassessment on the current evidence version.",
                (str(row["evidence_ref"]),), cutoff,
                "inform the existing scoped review that reassessment is needed",
                "gate-4 §2 step 5", "A", owner))
            seq += 1
        else:
            excluded.append({"candidate_kind": "evidence-freshness-check",
                             "reason": f"{row['assessment_ref']} already current"})
    return CandidateSet(tuple(proposed), tuple(excluded))


# No __main__ runner, no tests, no unittest discovery (filename has no test_
# prefix by design). This module is imported only by future isolated research
# harnesses on this branch, never by src/.
