# Issue #20 — Gate 5: assistance justification + rule-assisted prototype

**Status:** research draft only, branch work. All data fictional. No model was
called, no provider selected, no new dependency added.

## 1. Decision

- **Model-assisted proposal generation: NOT justified yet.** Reasons recorded:
  1. The Gate-4 baseline has been designed but not run — there is no measured
     reviewer burden or error rate to improve on, so a model arm has no
     comparator (OI-011 requires baseline comparison first).
  2. No qualified provider, hosting/retention terms, or permitted-input
     review exists for this slice (OI-011 task-contract gate unpassed).
  3. No independent adjudication protocol run or governed retrospective packet
     exists for these scenarios (OI-014 gate unpassed).
  4. The existing `investigation.py` contract already bounds any future model
     use (fixed templates, citation resolution, language guard,
     hypothesis-only pending output); duplicating a second model path now
     would create the parallel ungoverned record system the boundary forbids.
- **Rule-assisted deterministic prototype: justified as a draft only**, because
  it is pure, stdlib-only, ledger-read-free, proposes version/identity/
  freshness flags that the existing deterministic invalidation already owns,
  and every candidate carries hypothesis + falsifier + versioned inputs +
  cutoff + receipt path. It cannot execute clinical effects, and denied
  effects stay denied (class C has no auto environment; self-approval raises).

## 2. Prototype location and shape

Code: `propose_version_checks` (R1), `propose_specimen_checks` (R2),
`propose_evidence_freshness_checks` (R3) in
[tests/research_issue20_draft.py](../../../tests/research_issue20_draft.py).
Pure functions over caller-supplied frozen dicts; no I/O, no DB, no imports
from `src/`; every emitted candidate is a validated `ExperimentProposalDraft`
(effect class A) entering at `draft` state, requiring the `independently-checked`
and `human-review` transitions before any ledger-adjacent use; every
non-emission is recorded in `excluded` with a reason. Denied clinical effects
stay denied: class C has no auto environment, clinical language is rejected,
and self-approval raises.

## 3. Conditions to revisit model assistance

Run Gate 4; show a measured gap the rules cannot close; pass OI-011 rights +
task-contract review and OI-014 protocol approval; reuse the existing
`investigation.py` validation/guard path rather than a new model module.
Until then, model assistance stays deferred by this recorded decision.
