# Patient Mission Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, read-only Patient Mission projection and portal panel over the existing synthetic case ledger.

**Architecture:** A new pure projection module consumes one `CaseStore.state()` snapshot and returns a typed workflow-oriented view. The existing local HTTP service exposes the projection; a small standalone browser script renders it without mutating canonical state or duplicating application logic.

**Tech Stack:** Python 3.11+ standard library, SQLite-backed existing `CaseStore`, dependency-free browser JavaScript, `unittest`, and dependency-free headless Chromium journeys.

**Spec:** `docs/superpowers/specs/2026-10-31-patient-mission-projection-design.md`

## Global Constraints

- Open Intelligence is the sole project name; historical CEVax material is not a separate current product.
- The capability is complementary and must reuse the current source/evidence/question/investigation/event contracts.
- Synthetic data only; no PHI, diagnosis, treatment recommendation, trial match, clinical decision, or clinical-validity claim.
- No new persistence schema, model provider, dependency, or external service.
- Projection code must be deterministic, read-only, case-scoped, source-linked, and explicit about limitations.
- PR #10 remains documentation-only and unmerged; implementation occurs on this separate branch and draft PR #38.

## Review Focus

- Empty and partially populated cases must not invent workflow or medical state.
- Cross-case assertions, questions, investigations, quarantines, or events must never appear.
- Malformed event-detail JSON must not break the mission endpoint or create a misleading material-change description.
- An amendment must surface only the investigations actually invalidated by the canonical store.
- Browser language must say workflow/review state, never patient condition, diagnosis, treatment, or clinical recommendation.

---

### Task 1: Pure Patient Mission projection

**Files:**
- Create: `src/open_intelligence/mission.py`
- Create: `tests/test_patient_mission.py`

**Interfaces:**
- Consumes: `build_patient_mission(state: dict) -> dict`, where `state` is the exact result of `CaseStore.state(case_id)`.
- Produces: the `PatientMissionProjection` contract defined by the spec.

- [x] **Step 1: Write failing tests** for empty state, seeded unresolved state, case isolation, malformed event details, and amendment-driven review state.
- [x] **Step 2: Confirm the red state.** Run `41269640207` failed because `open_intelligence.mission` did not exist while the existing suite remained green.
- [x] **Step 3: Implement** `build_patient_mission(state: dict) -> dict` and private deterministic helpers in `src/open_intelligence/mission.py`.
- [x] **Step 4: Verify** the task and full suite. Run `41269787960` passed compile, 43 unit/HTTP tests, JavaScript syntax, and the existing browser journey after correcting a flawed cross-case test sentinel.
- [x] **Step 5: Commit** the deterministic projection and tests.

### Task 2: Case-scoped HTTP endpoint

**Files:**
- Modify: `src/open_intelligence/__main__.py`
- Create: `tests/test_patient_mission_http.py`

**Interfaces:**
- Consumes: `build_patient_mission(state)` from Task 1.
- Produces: `GET /api/cases/{CASE-ID}/mission` returning JSON; existing unknown-case and host boundaries remain authoritative.

- [x] **Step 1: Write failing HTTP tests** for a seeded case, unknown case, and unexpected Host rejection.
- [x] **Step 2: Confirm the red state.** Run `41269841287` returned 404 for the absent route while the existing Host rejection passed.
- [x] **Step 3: Import** the projection helper and add the mission route after the existing case-state route.
- [x] **Step 4: Verify** the task and full suite. Run `41269912124` passed 46 tests and the existing browser journey.
- [x] **Step 5: Commit** the case-scoped endpoint.

### Task 3: Patient Mission portal panel

**Files:**
- Modify: `src/open_intelligence/__main__.py`
- Modify: `web/index.html`
- Create: `web/mission.js`
- Create: `tests/test_patient_mission_ui.py`
- Create: `tests/patient_mission_browser_journey.py`
- Modify: `.github/workflows/synthetic-tests.yml`

**Interfaces:**
- Consumes: `GET /api/cases/{CASE-ID}/mission`.
- Produces: a read-only panel showing status, counts, known statements, unresolved items, material changes, next actions, and guardrails.

- [x] **Step 1: Write failing static/UI tests** requiring the section, script, exact warning, and mission endpoint call.
- [x] **Step 2: Add a separate browser journey** verifying that the panel follows the selected case and shows amendment-driven review state.
- [x] **Step 3: Confirm the red state.** Run `41270022603` failed because `web/mission.js` did not yet exist.
- [x] **Step 4: Add** `/mission.js` static serving, the semantic HTML panel, and dependency-free rendering with stale-response protection.
- [x] **Step 5: Verify** JavaScript syntax, unit/HTTP tests, the existing browser journey, and the new Patient Mission journey. Run `41270150297` passed compile, both JavaScript syntax checks, 49 unit/HTTP tests, and both browser journeys.
- [x] **Step 6: Commit** the Patient Mission portal surface and verification workflow.

### Task 4: Boundaries, documentation, and final verification

**Files:**
- Modify: `README_IMPLEMENTATION.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/superpowers/plans/2026-10-31-patient-mission-projection.md`

**Interfaces:**
- Consumes: verified behavior from Tasks 1–3.
- Produces: accurate implementation status, limitations, external cross-references, and final test evidence.

- [x] **Step 1: Document** what the projection does and does not establish, including the local route and portal section.
- [x] **Step 2: Mark plan steps only where commits and workflow evidence support completion.**
- [x] **Step 3: Run final verification on the exact review state:** run `41270295553` passed Python compile, both JavaScript syntax checks, all 49 unit/HTTP tests, and both browser journeys; Crossref contract run `41270295565` also passed.
- [x] **Step 4: Keep the implementation in a separate draft PR to `main`.** Draft PR #38 is open and unmerged; PR #10 remains documentation-only.
- [x] **Step 5: Link draft PR #38 from the complementary Notion and Google Docs annexes without changing canonical architecture status.** PR #10 also records the bounded implementation reference.

## Verification Evidence

| Phase | Run | Result |
|---|---:|---|
| Projection RED | `41269640207` | Expected failure: module absent |
| Projection GREEN | `41269787960` | Compile, 43 tests, JS syntax, original browser journey passed |
| HTTP RED | `41269841287` | Expected failure: route absent |
| HTTP GREEN | `41269912124` | 46 tests and original browser journey passed |
| Portal RED | `41270022603` | Expected failure: renderer absent |
| Portal GREEN | `41270150297` | Compile, two JS checks, 49 tests, and both browser journeys passed |
| Final review-state GREEN | `41270295553` | Compile, two JS checks, 49 tests, and both browser journeys passed |
| Independent metadata contract | `41270295565` | Crossref metadata contract passed |

## Remaining Boundaries

Passing these synthetic checks does not establish identity, consent, PHI-grade access control, clinical ingestion, diagnosis, treatment selection, trial matching, acute-safety handling, therapeutic development, care realization, outcome attribution, professional validation, regulatory status, or fitness for real patient use.
