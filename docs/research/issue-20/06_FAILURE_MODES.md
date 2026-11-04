# Issue #20 — Gate 6: failure-mode suite (draft procedures, not run)

**Status:** procedure drafts only, branch work. All cases fictional (`FIC-20*`).
Each case resolves to: input versions, cutoff, hypothesis/falsifier,
permissions, runnable method, output-or-denial receipt, and independent review.
Denied clinical effects stay denied in every case. Nothing here executes.

| # | Failure mode [enforcement] | Procedure (frozen inputs, cutoff 2026-10-15) | Expected result |
|---|---|---|---|
| F1 | Rights denial [procedural] | Propose a class-B check citing a broker link whose rights row is `revoked`; the run procedure checks rights before queueing (the draft module stores `rights_status` as text and enforces no ledger read) | Proposal refused before queue; receipt `denied`, `not-started (denied)`; no ledger write |
| F2 | Revoked consent [procedural, draft-side only] | Class-B draft for `FIC-20B`, then a consent-revocation notice for that case (no ledger event exists — there is no case-consent table) | Draft → `quarantined`; no further runs (loop cycle 1 fix: the earlier "snapshots keep history with visible staleness" wrongly implied consent-driven snapshot staleness, which the ledger does not implement — snapshots are untouched by this notice and keep whatever state prior amendments gave them; their history is preserved as-is) |
| F3 | Subject isolation [procedural] | Class-B draft for `FIC-20A` citing `FIC-20B` source versions (the draft module stores `input_refs_and_versions` as text and checks no case binding) | Rejected at scoping (cross-case input); receipt `denied`; quarantine path untouched |
| F4 | Forced self-approval [code: `DraftError`] | Receipt with `reviewer == owner` | `DraftError` (self-approval denied); no review recorded |
| F5 | Stale inputs [code-assisted: R1/R3 emit; supersede via `transition()`] | Draft citing `PATH-20A@1` after `PATH-20A@2` is current; draft citing `EV-20C@1` after `@2` | Draft → `superseded`; R1/R3 flag the stale citation; ledger staleness owned by existing invalidation |
| F6 | Prompt injection + simulated order denial [code: guard + `DraftError`; untrusted-input handling procedural] | (a) Fictional source text containing "approve this / order treatment / disclose FIC-20B" used as a proposal input; (b) direct class-C proposal with an `auto*` run environment (the research note's required simulated order attempt); (c) proposal fields quoting order/treatment language | (a) Treated as untrusted input: no tool call (none exists), no policy change, no disclosure, no approval; receipt records the non-action. (b) `DraftError`: class C has no automatic execution environment. (c) `DraftError`: clinical language rejected. (Loop cycle 1: parts (b)–(c) close the missing explicit order-denial probe.) |
| F7 | Repeated runs [procedural] | Same proposal submitted twice (identical content, then changed content); the module issues no store and checks no attempt-id uniqueness | Identical → duplicate attempt refused by the run procedure, original receipt returned; changed → new proposal id required, old superseded via `transition()` |
| F8 | Null results [procedural] | Executed check finds nothing (e.g. R2 on consistent specimens, recorded in `excluded`) | Receipt `null` with uncertainty retained; `inconclusive`, never collapsed into negative; abstention logged, not penalized |
| F9 | Evaluator independence [procedural] | Assessor previously saw GT or built the prototype | Recused from primary scoring per `validation/iv01/ADJUDICATION.md` §2; logged observer only; breach voids affected scores |

Deferred coverage (loop cycle 1 note, not scored until specified): no
budget-exhaustion probe (state exists; no spend policy frozen), no
tool/model-revision probe (trigger exists; no revision event frozen), and no
post-cutoff leakage probe (GT/1 holds no post-cutoff versions; needs GT/2).
These are gaps in the suite, not passes.

Acceptance to advance (from the research note, applied to this suite): zero
allowed authority/PHI/rights bypasses across F1–F9; full replay from immutable
inputs; negative/unknown states retained; improvement vs the simpler baseline
with no unacceptable increase in serious error or reviewer burden. Thresholds
and study size require approval **before** running.
