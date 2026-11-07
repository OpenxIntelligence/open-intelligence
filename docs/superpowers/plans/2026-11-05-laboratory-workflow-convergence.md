# Laboratory Workflow Convergence Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the integration and a fresh whole-branch reviewer. Preserve the existing contributor branches.

**Goal:** Deliver one reviewable candidate connecting saved laboratory questions, Overview, citations and original-result inspection with current main.

**Architecture:** Reuse canonical patient, source, question and evidence owners. Merge the frozen inputs and resolve their shared frontend, provenance and acceptance contracts without introducing a parallel ledger.

**Tech Stack:** Existing React/TypeScript/Vite, Python/FastAPI, PostgreSQL and locked dependencies.

**Spec:** `docs/superpowers/specs/2026-11-05-laboratory-workflow-convergence-design.md`

## Global Constraints

- No Next.js, new runtime dependency, real patient data, model execution or clinical approval.
- Frozen main and donor commits are recorded in the spec; contributor branches remain unchanged.
- No self-merge. Individual donor checks do not qualify the combined candidate.
- Preserve immutable source versions, typed Observation references and independent read grants.

## Review Focus

- A mixed text/laboratory case must not silently count only text questions.
- A changed source snapshot must invalidate a prior laboratory history read.
- Current cancer-episode metadata must remain part of source integrity and question preparation.
- Navigating Overview/Journey must not discard an uncertain saved citation or expose revoked history.
- Merging browser fixtures must retain both draft-recovery and citation/amendment checks.

### Task 1: Reproduce the missing integration and compose existing owners

**Files:** `apps/web/tests/laboratory-workflow-convergence.test.mjs`; shared paths from #518/#519/#521; existing source/question contracts and browser journey.

**Interfaces:** Consume `readLabQuestionList`, `patientContinuity`, `secondOpinionPreparation` and the existing canonical API routes. Produce the combined existing contracts, with no new public API.

- [ ] Add decoder-to-Overview regressions for a saved result, amendment, stale read and independent denial.
- [ ] Run `npx --prefix apps/web tsc -p apps/web/tsconfig.client.json` and the focused Node tests; observe absent laboratory integration failures on frozen main.
- [ ] Merge the three frozen donor heads in order, inspecting each conflict; keep both cancer-episode and typed laboratory behavior.
- [ ] Run all web client tests, rights checks and production build. Reproduce and fix actual combination defects.
- [ ] Extend the existing real laboratory browser journey to assert Overview counts, return to the saved question, citation inspection and amended history together.
- [ ] Commit implementation and exact local results.

### Task 2: Qualify the combined revision and reconcile records

**Files:** Existing H1 convergence record, first-principles plan status, demo guide and execution backlog; PR verification evidence.

**Interfaces:** Consume the combined source revision. Produce a draft PR with immutable source identity, scoped findings, verified results and unproven boundaries.

- [ ] Independently review the combined changes and resolve material findings with regressions.
- [ ] Push only the isolated candidate branch and create a draft PR targeting main.
- [ ] Inspect exact-head API/PostgreSQL, migrations, browser, restart and recovery CI; preserve failures and repair causes.
- [ ] Verify archived source identity and substantive acceptance receipts.
- [ ] Update the existing Notion and Drive records with actual outcome, ownership and next work.

## Execution evidence

Baseline main: 633 web client tests passed. The local API run executed 785 tests,
with 477 PostgreSQL-dependent skips and 75 errors in this restricted local
runtime; it is not API acceptance. Hosted PostgreSQL and browser qualification
is required. Record final results in the existing H1 convergence record and PR.
