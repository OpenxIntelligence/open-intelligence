# Worklist Currentness Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task. The user has authorized continuation of the existing frontend implementation; routine reversible work proceeds without another approval round.

**Goal:** Keep patient worklist summaries consistent with accepted chart state and provide an explicit, recoverable full-list refresh.

**Architecture:** Project the accepted canonical response into its keyed worklist row. Retain `renderIncomingBoard(cases?)` as the full-list read owner, with a separate generation and per-row revisions to reject obsolete results. Preserve existing chart state, forms and data contracts.

**Tech Stack:** Existing dependency-free browser JavaScript/HTML/CSS, Python/Node tests and real Chromium harness. No new dependency.

**Spec:** `docs/ux/2026-11-02-worklist-currentness.md` and Gate 2 of `docs/ux/2026-11-02-forward-convergence.md`.

## Global constraints

- Start at #183 `725b7f78b77ac247b97a0c0df71caf5575ac0b5c`; preserve its #166 parent and draft status.
- Runtime changes are confined to `web/`; backend, schema, API payloads, authorization, business rules, model behavior, dependency versions and existing fixtures remain unchanged.
- Reuse accepted case state and existing roster/state endpoints. No competing store, polling or optimistic count arithmetic.
- Preserve all 16 original forms and their native validation; add only a non-submit action outside those forms.
- New test data must be independently authored fictional text.

## Review focus

1. A delayed full-list success or error must not overwrite a case projected since that read began, even after selecting another case.
2. Shared evidence invalidation must refresh all affected case summaries; case-local actions must not add a redundant full sweep.
3. Current-source count and event-date order must distinguish amendments, new documents, duplicate bytes and wrong-case quarantine.
4. Search, button focus, unfinished work and chart readiness must survive list refresh and partial failures.
5. A successful canonical load must replace an obsolete summary error; neither zero counts nor a success message may stand in for a failed read.

## Task 1: Establish the actual worklist regression

**Files:** create `tests/workspace_worklist_journey.py`.

**Interfaces:** consume `Journey`, `browser_session` and the existing form/API contracts. Produce a JSON verification report under `OI_WORKLIST_ARTIFACT_DIR`, including assertion results, browser errors, screenshots and failure diagnostics.

- [x] Add real form-driven question/review/amendment and source-order checks, preserving historical stale semantics.
- [x] Add controlled delayed/full-list and failed-summary paths, with actual retry and navigation controls.
- [x] Run the journey against the starting runtime; retain the stale-count failure and positive controls.

## Task 2: Synchronize rows through existing state ownership

**Files:** modify `web/app.js`, `web/index.html`, `web/workspace-entry.js`; adjust `web/style.css` only if the existing action styles do not reflow.

**Interfaces:** `projectIncomingCase(state)` consumes only a response accepted and rendered by `refresh()`; `renderIncomingBoard(cases?)` consumes an optional already-read roster or reads the existing roster endpoint. Both use one summary projection. Full-list requests cannot mutate chart state or its request sequence.

- [x] Extract the four existing summary calculations, add exact row identity/revision metadata, and preserve Open-button nodes during updates and sorting.
- [x] Call the row projection only after the guarded canonical success path has rendered its accepted response.
- [x] Guard full-list reads with an independent generation and row revisions; retain newer rows when older results or errors complete.
- [x] Add `#worklist-refresh` and `#worklist-status`, with loading/partial-failure recovery and existing search/filter behavior. New roster entries must remain openable.
- [x] Remove redundant connected post-intake full reload, and refresh the full worklist after successful shared evidence import/withdrawal.
- [x] Run the focused journey, correct product defects, then obtain an independent review of state ownership and races.

## Task 3: Verify integration and publish the existing draft

**Files:** update `.github/workflows/ui-glance.yml`, this plan, the worklist report and its evidence artifacts; update `README_WORKSPACE.md` and the currentness note in the convergence report.

**Interfaces:** preserve existing CI steps and exact-source/runtime fingerprints; add the focused worklist journey and report to hosted artifacts.

- [ ] Run original form contracts, JavaScript suites, full Python suite and existing browser journeys that cover the modified surfaces.
- [ ] Run responsive navigation across both launchers and the case/scope continuity journeys. Keep all existing substantive assertions.
- [ ] Verify protected paths and whitespace; record actual results and failures in reproducible evidence.
- [ ] Publish to #183 only after inspecting its live head; preserve parent/draft status and verify the new hosted run's exact source tree.
- [ ] Update the PR with the behavior, evidence and bounded currentness guarantee. Do not merge or deploy.

## Execution ledger

- Task 1 complete: hosted run 41565780861 reproduced the unchanged runtime defect (12 assertions, 11 passed, one stale-question-count failure).
- Task 2 complete: the repaired runtime passed hosted run 41566509936 (13 scenarios, 387 assertions); independent read-only code/test review found no material blocker.
- Task 3 local gates complete: 347 Python/HTTP tests, 80 named JavaScript tests, original form contracts, syntax and whitespace checks. Full hosted integration and publication are recorded live in PR #183 after this source snapshot is committed.
- Execution decision: local Chrome was blocked before application loading and sandbox escalation was automatically rejected; use the existing authorized GitHub runner. No local browser pass is claimed and no local policy bypass was attempted.
