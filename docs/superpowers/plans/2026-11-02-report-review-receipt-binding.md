# Report-to-review receipt binding

**Goal:** Connect the existing permission-scoped report to the existing nonterminal evidence-review receipt, preserving exact hashes and source versions without adding a patient, evidence, report or review store.
**Scope:** Original synthetic first-party integration; existing PR #154 report owner and #150/#82 review owner. Read-only text report becomes an explicit nonterminal review request, never approval or delivery proof. No new HTTP endpoint, identity service, clinical role claim, schema, runtime dependency, Next.js or actual patient data.
**Baselines:** #154 `5db96198d7ad1b17701f5b772b84a740b4ece768`; #150 `2307d11a0c4504796e3c522086dbbeb21d81a545`; common #143 `6062293a7cc0152f7863d6c3cd0b9b3cdf31eb4c`. Three-way file comparison found no differing concurrent modifications. Preserve upstream files outside the explicit extension.

## Design and alternatives

Use the original CaseStore review receipt and its same-transaction event to record only prepared-report body/packet SHA-256 and exact patient assertion/source reference. A second report ledger or an unauthenticated download endpoint is rejected. Existing artifact body is not persisted. Existing ordinary receipt callers retain behavior. This is a host-callable bridge, not an authenticated application API.

The integration renders with the existing export gate, requires an explicit separate review-return grant, verifies the exact packet hash again at handoff, records a `returned` receipt only if the selected patient source and evidence queue fingerprint are still current inside the existing write transaction, and revalidates the report/rights before returning text. The audit link means **prepared report reference**, not confirmed disclosure, delivery or clinical review. A final denial after the nonterminal write retains that historical receipt but returns no text. External rights/clinical stores are not an atomic transaction.

## Work and acceptance
- [x] Reproduce truthy nonboolean review grants using actual fixtures and provider-access spy; deny strictly unless callback returns True.
- [x] Write report handoff regressions before implementation: independent read/export/write gates; exact packet/report hashes; source/evidence mismatches; same-transaction rollback; fresh connection; no clinical state promotion; final-rights denial; positive and unrelated-case controls.
- [x] Extend existing review receipt with optional validated reference-only audit metadata and in-transaction selected-source fence; no migration or new table.
- [x] Extend the existing review handoff with optional expected-packet binding; no new approval action.
- [x] Implement a small ReportReviewHandoff orchestrator over the original objects. Do not accept caller-authored report bytes as trusted output.
- [ ] Run focused, upstream and full synthetic regression; inspect hosted exact-tree artifacts if publishing succeeds. Do not conflate test execution with independent clinical evaluation.
- [ ] Record actual failures, limits and source hashes; keep draft and unmerged pending owner/security/clinical review.

## Review focus
Source change after preview; grant returning a truthy nonboolean or raising; evidence export rights differing from reading rights; a caller attaching hashes to an unrelated source; audit write failure; report becoming withheld after a durable nonterminal receipt; copied text and authority labels; dependence on separate external state. Receipt delivery retries are not automatically idempotent: each explicit library call is a separate return request, and no network endpoint or retry policy is introduced.

## Publication shape

This PR is a pinned **composition/patch candidate**, not an automatically active report API. Existing report PR #154 is the branch base. The dedicated workflow overlays the five unchanged #150 review-owner files only after comparing them to common #143 source. It stages the explicit owner-extension patch and the two source/test payloads, runs full regression, and archives the actual staged tree. Ordinary parent/UI checks do not exercise the staged new behavior; only the dedicated composition workflow does. No remote branch/ref, patient data or runtime deployment is modified by the workflow. Owner review must integrate the staged patch before any merge or application adoption.

Local results: 12/12 new tests; 23/23 existing review-owner tests; original report checks 15/15. Full combined application suite 489 test executions passed; focused counts overlap the full suite. The nonboolean grant regression produced four unauthorized nonterminal receipts on the old code; missing module failures established the unimplemented integration. No actual clinician review, user interface, patient permission or publisher grant is established.
