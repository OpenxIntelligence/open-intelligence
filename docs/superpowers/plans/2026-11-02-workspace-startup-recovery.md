# Workspace Startup Recovery Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task. Continue the authorized frontend repair without another routine approval round; obtain one independent whole-increment review before publication.

**Goal:** Recover first-load roster failures without reloading or losing creation intent and preserve the existing chart/intake workflow.

**Architecture:** The existing initializer owns initial membership and selection. Explicit startup phase/generation metadata reject obsolete reads; a global status/retry region remains reachable outside chart views. Existing canonical chart and full-worklist owners retain their contracts.

**Tech Stack:** Existing browser JavaScript/HTML and Python/Node/Chromium tests; no new dependency.

**Spec:** `docs/ux/2026-11-02-workspace-startup-recovery.md`.

## Global constraints

- Start from #183 `18c494fb998d1fe9878cce2ca730480f8ba60553`, preserving #166 base `334d863b2206b290c02cd2606dcb93c93afe3a68` and draft status.
- Runtime edits only in `web/app.js`, `web/index.html`, `web/workspace-entry.js`, and the existing creation-status integration in `web/intake.js`; reuse current action/notice styles.
- No backend, schema, API payload, authorization, review/processing rule, dependency or fixture change.
- Retain all 16 original form contracts and every existing substantive regression assertion.
- All new records and text are independently authored fictional examples.

## Review focus

1. A late startup or board success/error after a newer creation must not alter the accepted case, options, roster or status.
2. Repeated initialization must not multiply picker listeners or reset a ready chart, unfinished question or original selected File.
3. A saved creation followed by failed loading must remain recoverable through reads, with truthful messaging and no duplicate POST.
4. Empty state must be based on a successful roster read, and its refresh control must remain reachable after the connected setup redirect.
5. Startup status must not conflate roster availability with selected-chart readiness or clear another feature's notice.

## Task 1: Prove the missing recovery path

**Files:** create `tests/workspace_startup_recovery_journey.py`; add an optional unseeded-fixture choice to `tests/workspace_navigation_journey.py`.

**Interfaces:** use `browser_session`, real native controls, `Page.addScriptToEvaluateOnNewDocument` and independent HTTP persistence reads. Default existing harness behavior remains seeded and unchanged.

- [ ] Add initial HTTP/network failure, visible recovery, repeated retry, preserved route and one native selection-read assertions.
- [ ] Add empty, delayed creation, late failure/success, saved-creation activation, unrelated-notice and original-launcher scenarios.
- [ ] Run the smallest initial-failure scenario on unchanged runtime. Expected: actionable recovery is missing; preserve its report/screenshot.

## Task 2: Repair the existing startup owner

**Files:** modify the four runtime files listed above.

**Interfaces:** `initialize(preferredCaseId?)` establishes selection only before a case owner exists and returns whether its accepted initialization completed. The creation callback can return `false` to distinguish saved-but-not-activated creation; an undefined return preserves the existing success behavior for other consumers.

- [ ] Add explicit startup state and globally reachable loading/error/empty recovery controls.
- [ ] Bind selection once, replace options atomically, guard each asynchronous boundary and invalidate superseded initial board reads.
- [ ] Preserve the newly created case preference and finish deferred activation without another write.
- [ ] Integrate explicit startup state with the connected adapter, preserving the existing chart readiness and intake owner.
- [ ] Run all focused scenarios. Expected: every assertion passes with no captured application JavaScript errors.

## Task 3: Verify integration and publish

**Files:** extend `.github/workflows/ui-glance.yml`; update this plan, the report, convergence note, README and execution receipts.

- [ ] Run syntax, original form contracts, the full Python/HTTP and JavaScript suites. Expected: no regressions.
- [ ] Run the full existing browser workflow plus the new startup journey. Expected: all original navigation/case/scope/worklist assertions retained and passing.
- [ ] Complete independent whole-increment review and address material findings with failing/passing regression evidence.
- [ ] Inspect live #183/base before publication; publish with an expected-head lease, verify the exact source tree, and record actual hosted results in the PR.
- [ ] Keep #183 draft; no merge or deployment.

## Execution ledger

- Starting local checkout is clean on the existing task branch, matching live #183. Its exact-head hosted UI workflow is successful.
- Scope decision: close the explicitly recorded first-start gap before expanding patient summaries; live H1 reading and separate patient-summary owners are already active.
- Authorization: the user asked to continue the current frontend implementation. Existing session and repository instructions authorize routine reversible repairs and updating this draft; no new architecture or product-scope decision is being requested.
- Pre-flight: Task 2 consumes the fresh-page fault controls and startup acceptance scenarios from Task 1. Task 3 preserves those scenarios alongside the existing owners' regression gates; no interface conflict found.
