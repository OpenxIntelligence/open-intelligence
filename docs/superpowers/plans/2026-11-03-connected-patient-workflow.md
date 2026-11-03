# Connected Patient Workflow Implementation Plan

> Execute inline with test-driven development; no subagent tool is available.

Goal: combine existing patient record, source-bound evidence review, readable report and durable follow-through on one tested source tree.
Architecture: keep #175's existing canonical domain stores and authorization boundaries; reconcile #161's source-linked record UI and #197/#174's report/task owners. No parallel ledger or unauthenticated clinical-authority claim.
Tech stack: existing Python/SQLite and browser JavaScript reference application.
Spec: ../specs/2026-11-03-connected-patient-workflow-design.md

## Constraints and review focus
Synthetic inputs only; no new dependency, provider, patient data or main merge. Preserve exact sources and distinct clinical/research statuses. Exercise cross-case joins, source amendment, rights withdrawal, stale-response races and restart. Local copied-artifact commits are not upstream SHAs.

## Task 1 — connected domain regression and source reconciliation
- [x] Attempt original #175 baseline; local runs timed out. Retain historical 599-test hosted receipt separately; do not claim a fresh local baseline pass.
- [x] Add test_connected_patient_workflow.py using the existing #175 integration fixture. Assert the existing task API is present (red on #175), persist source/question-bound tasks, prepare the authorized report/returned receipt, compare the source-backed World Model and readable report, amend and reopen attention without rewriting history, revoke rights, and reopen CaseStore.
- [x] Reconcile source-owner files with three-way merge using main snapshot; inspect all conflicts explicitly. Carry original tests unchanged except compatibility fixes justified by new functionality.
- [x] Run all Python and JavaScript owner suites and cross-domain test.

## Task 2 — browser continuity and publication evidence
- [ ] Run original patient-record and report/follow-through browser journeys on the combined tree, plus original source/mission journeys. Repair integration-only defects with regression-first evidence.
- [ ] Review diff and source manifests, record actual results and limitations.
- [ ] Publish a draft isolated candidate and exact-head workflow; leave source branches/main unchanged. Report unrun/failed gates explicitly.

## Executed evidence and publication ruling
The three new tests failed on the unintegrated #175 source, then passed after source reconciliation. The complete combined application suite passed 660 Python/domain/HTTP tests and 87 JavaScript tests locally. Counts are from one tree, not the sum of source branches. Python retained SQLite ResourceWarnings.

All six local browser attempts failed: managed Chromium blocks loopback pages (and one launch failed at DevTools startup). No browser policy or test was relaxed. Hosted browser verification is required.

Ruling: publish the byte-verified composition through a source-pinned CI recipe because this session has connector GitHub access but no working shell GitHub network. The read-only test job creates and tests one commit; a separate publication job may create only a new isolated branch after every gate passes. No source branch or main is updated. The published application must contain the resolved source files, not merely this recipe.
