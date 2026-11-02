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
(effect class A) entering at `draft` state; every non-emission is recorded in
`excluded` with a reason. Denied clinical effects stay denied: class C has no
auto environment, clinical language is rejected, and self-approval raises.

Input schemas (loop cycle 1 addition; authoritative form is the code
docstrings): R1 rows `{doc, cited_version, current_version, case_id,
question_id}` — emits when cited ≠ current. R2 rows `{doc,
specimens_by_version, case_id, question_id}` — emits when one document's
versions carry more than one specimen id. R3 rows `{assessment_ref,
evidence_ref, evidence_state, case_id, question_id}` — emits when
`evidence_state != "current"`.

Two honesty notes (loop cycle 1): (a) the "must pass
`independently-checked` and `human-review` before any ledger-adjacent use"
rule is procedural, not code-enforced — `transition()` permits the path but
nothing in the module gates downstream use on proposal state; the run
procedure must check. (b) Class A for case-bound candidates is deliberate:
the cases are fictional (`FIC-*`, no consent or PHI exists), the checks are
synthetic-engineering computations proposing version/identity/freshness flags,
and `permission_scope` records `fictional-case-review:{case}` for case-bound
rows vs `synthetic-engineering` for case-free rows. Genuinely consented
case-specific computation would be class B and is out of scope here.

## 3. Conditions to revisit model assistance

Run Gate 4; show a measured gap the rules cannot close; pass OI-011 rights +
task-contract review and OI-014 protocol approval; reuse the existing
`investigation.py` validation/guard path rather than a new model module.
Until then, model assistance stays deferred by this recorded decision.
