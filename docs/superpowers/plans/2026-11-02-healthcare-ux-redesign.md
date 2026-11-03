# Healthcare UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The user has requested staged execution through implementation and testing; routine reversible work proceeds without another approval round.

**Goal:** Reorganize the existing Open Intelligence frontend into a focused patient presentation and a clinician worklist with a dedicated patient chart, preserving every existing workflow.

**Architecture:** Keep the current vanilla frontend, APIs, handlers and canonical state. Add an explicit presentation router inside the already-served app.js, move existing live DOM sections into focused workspaces, and refine the current CSS tokens/components. No backend or framework migration.

**Tech Stack:** Existing HTML, CSS, dependency-free browser JavaScript, Python/Node regression tests and existing real-browser harness.

**Spec:** `docs/ux/2026-11-02-research-and-design.md`; complete inventory `docs/ux/2026-11-02-frontend-audit.md`.

## Global constraints

- Base is PR #166 `334d863b2206b290c02cd2606dcb93c93afe3a68`; main and all other owner branches remain unchanged.
- Product changes are confined to `web/`; no backend, database, API, authentication, authorization, business/data-processing or validation changes.
- Preserve all 16 forms, IDs, field constraints, request payloads, handlers, source links and seven exact host template anchors.
- Patient/clinician selection is a presentation preview, not authentication. No new or simulated appointments, medicines, messages or encounters.
- No production dependency or remote font/icon assets.
- Same-case navigation moves/hides existing controls without resetting drafts or selections. Notices/dialogs remain global.
- Tests and documentation may be added/updated. Report actual execution and environmental limits.

## Review focus

1. An old or dynamically generated deep link must reveal the correct containing panel, including a report created after asynchronous data load.
2. A case-switch veto or failed load must not leave another case's actions presented as the newly selected case.
3. An empty connected workspace must still expose original case creation and file intake after routing/wrapping.
4. Route/view switches must retain form inputs, selected source versions, disclosure state and existing observer/event subscriptions.
5. Mobile navigation must preserve keyboard access, active patient context and error feedback without page-level horizontal overflow.

## Task 1: Preserve contracts and establish regression coverage

**Files:** create `tests/test_workspace_redesign.py`, `tests/test_workspace_routing.js`; later add `tests/workspace_redesign_browser.py`.

**Consumes:** the baseline `web/index.html`, connected `workspace_html()` and existing Node/CDP harness patterns.

**Produces:** tests for exact form/control contract preservation, all route destinations and aliases, layout/view visibility, actual empty/start/import/question/report workflows.

- [ ] Record existing test results and limitations before product changes.
- [ ] Write tests for missing presentation router and route mapping; execute to establish the expected failure.
- [ ] Capture baseline screenshots using the existing browser journey when a permitted browser runtime is available.
- [ ] Use a fixed baseline control manifest for meaningful preservation checks; do not test color strings or mirror router implementation.

## Task 2: Implement the two presentation shells and chart navigation

**Files:** modify `web/index.html`, `web/app.js`, `web/workspace-entry.js` (navigation-only handoff if required), `web/workspace-entry.html` (copy/presentation only if required).

**Consumes:** existing DOM nodes, canonical `caseId`/`active`, `readyCase()`, original rendering/selection handlers and form submissions.

**Produces:** a `workspacePresentation` controller with `navigate(target, options)` and route resolution; standard hash history, clear active states, persistent identity, case-list filtering, and separate patient/clinician entry views.

- [ ] Keep original static anchors and IDs; add shell landmarks, case banner, page title and navigation containers.
- [ ] Move existing live sections once. Split questions, manual drafting, model runs and report history into deliberate destinations without duplicate forms.
- [ ] Resolve all legacy IDs and `snapshot-*` aliases, open enclosing disclosures for deep links and maintain keyboard focus deliberately.
- [ ] Make worklist row opening enter the chart only after the existing case-change decision. Keep navigation/read state independent from authorization.
- [ ] Preserve input and selection state through same-case navigation and presentation switches.
- [ ] Run new routing/contract tests and existing JavaScript tests; verify the connected server still composes successfully.

## Task 3: Refine the design system and responsive layouts

**Files:** modify `web/tokens.css`, `web/style.css`, `web/intake.css` only as needed.

**Consumes:** Task 2 shell and route attributes; existing component class names and CSS tokens.

**Produces:** restrained navy/teal palette; readable patient pages; efficient clinician list/chart; consistent controls/states; responsive navigation and contained source viewers.

- [ ] Reuse the system font and tokens, add no production dependencies.
- [ ] Use contextual disclosures for long option/research forms and retain their state.
- [ ] Provide desktop rail/mobile menu, chart subsections and a narrow-screen section control.
- [ ] Correct the connected empty-state selectors for the new shell without changing intake behavior.
- [ ] Verify no page overflow at 320/390/768/1024/1440px and usable keyboard/focus/notice behavior.

## Task 4: Integration verification and handoff

**Files:** update affected UI tests only for intentional navigation changes; add browser journey and `docs/ux/2026-11-02-verification.md`.

**Consumes:** fully implemented frontend on the pinned base.

**Produces:** actual test results, before/after visual evidence, full changed-file list, source/API/form preservation evidence and a reviewable branch/draft PR.

- [ ] Run all existing Python and Node regression tests. Investigate failures without changing protected backend/logic.
- [ ] Exercise original-source viewing/comparison, question and manual draft creation, replay-to-report/review/amendment, exact file intake, duplicate/quarantine, old hashes, view changes, drafts and narrow layouts.
- [ ] Inspect actual screenshots and console/runtime errors. Clearly report any browser tests that cannot run.
- [ ] Compare protected files and request/validation contracts to the baseline.
- [ ] Request an independent branch review, resolve material frontend findings and rerun the affected checks.
- [ ] Record changed files, test counts/commands, limitations, branch/base and screenshots. Preserve the result as an isolated candidate; no merge or deployment implied.

## Execution ledger

- Research: official public sources reviewed for MyChart, NHS App, athenaOne and Elation.
- Source audit: complete candidate inventory, all forms, routes, APIs, state and host composition dependencies recorded before implementation.
- Baseline: exact source tree verified and branch fetched; source audit identifies absence of authenticated roles and several proposed portal features.
- Decision: use the connected candidate, preserve its owner contracts, and implement presentation separation only. A real permission boundary cannot be introduced in this frontend-only task.
- Initial browser limitation: cloud loopback unavailable and local Chromium not initially installed; do not count attempted commands as passed tests.
