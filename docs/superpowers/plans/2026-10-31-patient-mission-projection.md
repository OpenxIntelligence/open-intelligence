# Patient Mission Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, read-only Patient Mission projection and portal panel over the existing synthetic case ledger.

**Architecture:** A new pure projection module consumes one `CaseStore.state()` snapshot and returns a typed workflow-oriented view. The existing local HTTP service exposes the projection; a small standalone browser script renders it without mutating canonical state or duplicating application logic.

**Tech Stack:** Python 3.11+ standard library, SQLite-backed existing `CaseStore`, dependency-free browser JavaScript, `unittest`, existing headless Chromium journey.

**Spec:** `docs/superpowers/specs/2026-10-31-patient-mission-projection-design.md`

## Global Constraints

- Open Intelligence is the sole project name; historical CEVax material is not a separate current product.
- The capability is complementary and must reuse the current source/evidence/question/investigation/event contracts.
- Synthetic data only; no PHI, diagnosis, treatment recommendation, trial match, clinical decision, or clinical-validity claim.
- No new persistence schema, model provider, dependency, or external service.
- Projection code must be deterministic, read-only, case-scoped, source-linked, and explicit about limitations.
- PR #10 remains documentation-only and unmerged; implementation occurs on this separate branch.

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

- [ ] **Step 1: Write failing tests** for empty state, seeded unresolved state, case isolation, malformed event details, and amendment-driven review state.
- [ ] **Step 2: Run** `PYTHONPATH=src python -m unittest tests.test_patient_mission -v` and confirm failure because `open_intelligence.mission` does not exist.
- [ ] **Step 3: Implement** `build_patient_mission(state: dict) -> dict` and private deterministic helpers in `src/open_intelligence/mission.py`.
- [ ] **Step 4: Run** the task test and then `PYTHONPATH=src python -m unittest discover -s tests -v`; require zero failures.
- [ ] **Step 5: Commit** `feat: add deterministic patient mission projection`.

### Task 2: Case-scoped HTTP endpoint

**Files:**
- Modify: `src/open_intelligence/__main__.py`
- Create: `tests/test_patient_mission_http.py`

**Interfaces:**
- Consumes: `build_patient_mission(state)` from Task 1.
- Produces: `GET /api/cases/{CASE-ID}/mission` returning JSON; existing unknown-case and host boundaries remain authoritative.

- [ ] **Step 1: Write failing HTTP tests** for a seeded case, unknown case, and unexpected Host rejection.
- [ ] **Step 2: Run** `PYTHONPATH=src python -m unittest tests.test_patient_mission_http -v` and confirm the endpoint returns 404 before implementation.
- [ ] **Step 3: Import** the projection helper and add the mission route after the existing case-state route.
- [ ] **Step 4: Run** the task test and full suite; require zero failures.
- [ ] **Step 5: Commit** `feat: expose patient mission projection endpoint`.

### Task 3: Patient Mission portal panel

**Files:**
- Modify: `src/open_intelligence/__main__.py`
- Modify: `web/index.html`
- Create: `web/mission.js`
- Create: `tests/test_patient_mission_ui.py`
- Modify: `tests/browser_journey.py`

**Interfaces:**
- Consumes: `GET /api/cases/{CASE-ID}/mission`.
- Produces: a read-only panel showing status, counts, known statements, unresolved items, material changes, next actions, and guardrails.

- [ ] **Step 1: Write failing static/UI tests** requiring the section, script, exact warning, and mission endpoint call.
- [ ] **Step 2: Extend the browser journey** to verify the panel follows the selected case and shows amendment-driven review state.
- [ ] **Step 3: Run** the new tests and confirm they fail because the portal surface is absent.
- [ ] **Step 4: Add** `/mission.js` static serving, the semantic HTML panel, and dependency-free rendering with stale-response protection.
- [ ] **Step 5: Run** `node --check web/mission.js`, all unit/HTTP tests, and `PYTHONPATH=src python tests/browser_journey.py`; require zero failures.
- [ ] **Step 6: Commit** `feat: add patient mission portal panel`.

### Task 4: Boundaries, documentation, and final verification

**Files:**
- Modify: `README_IMPLEMENTATION.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/superpowers/plans/2026-10-31-patient-mission-projection.md`

**Interfaces:**
- Consumes: verified behavior from Tasks 1–3.
- Produces: accurate implementation status, limitations, and test evidence.

- [ ] **Step 1: Document** what the projection does and does not establish, including the local route and portal section.
- [ ] **Step 2: Mark plan checkboxes only for steps supported by actual commits and workflow evidence.
- [ ] **Step 3: Run** `PYTHONPATH=src python -m compileall -q src`, `node --check web/app.js`, `node --check web/mission.js`, `PYTHONPATH=src python -m unittest discover -s tests -v`, and `PYTHONPATH=src python tests/browser_journey.py`.
- [ ] **Step 4: Open a separate draft PR to `main`** and verify the pull-request workflow result; do not merge.
- [ ] **Step 5: Link the implementation PR from the complementary Notion and Google Docs annexes without changing canonical architecture status.
