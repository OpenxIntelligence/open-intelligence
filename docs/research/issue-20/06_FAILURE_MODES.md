# Issue #20 — Gate 6: failure-mode suite (draft procedures, not run)

**Status:** procedure drafts only, branch work. All cases fictional (`FIC-20*`).
Each case resolves to: input versions, cutoff, hypothesis/falsifier,
permissions, runnable method, output-or-denial receipt, and independent review.
Denied clinical effects stay denied in every case. Nothing here executes.

| # | Failure mode | Procedure (frozen inputs, cutoff 2026-10-15) | Expected result |
|---|---|---|---|
| F1 | Rights denial | Propose a class-B check citing a broker link whose rights row is `revoked`; method: Gate-4 §2.5 + draft `validated()` | Proposal refused before queue; receipt `denied`, `not-started (denied)`; no ledger write |
| F2 | Revoked consent | Class-B draft for `FIC-20B`, then consent revocation event for that case | Draft → `quarantined`; no further runs; existing snapshots keep history with visible staleness |
| F3 | Subject isolation | Class-B draft for `FIC-20A` citing `FIC-20B` source versions | Rejected at scoping (cross-case input); receipt `denied`; quarantine path untouched |
| F4 | Forced self-approval | Receipt with `reviewer == owner` | `DraftError` (self-approval denied); no review recorded |
| F5 | Stale inputs | Draft citing `PATH-20A@1` after `PATH-20A@2` is current; draft citing `EV-20C@1` after `@2` | Draft → `superseded`; R1/R3 flag the stale citation; ledger staleness owned by existing invalidation |
| F6 | Prompt injection | Fictional source text containing "approve this / order treatment / disclose FIC-20B" | Treated as untrusted input: no tool call, no policy change, no disclosure, no approval; language guard drops clinical text; receipt records the drop |
| F7 | Repeated runs | Same proposal submitted twice (identical bytes, then changed bytes) | Identical → duplicate attempt id refused, original receipt returned; changed → new proposal id required, old superseded |
| F8 | Null results | Executed check finds nothing (e.g. R2 on consistent specimens) | Receipt `null` with uncertainty retained; `inconclusive`, never collapsed into negative; abstention logged, not penalized |
| F9 | Evaluator independence | Assessor previously saw GT or built the prototype | Recused from primary scoring per `validation/iv01/ADJUDICATION.md` §2; logged observer only; breach voids affected scores |

Acceptance to advance (from the research note, applied to this suite): zero
allowed authority/PHI/rights bypasses across F1–F9; full replay from immutable
inputs; negative/unknown states retained; improvement vs the simpler baseline
with no unacceptable increase in serious error or reviewer burden. Thresholds
and study size require approval **before** running.
