# Source-Bound Native Composer Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the *existing* synthetic chart investigation UI a native Composer entry by showing the exact case/source/evidence/world-model context before execution and rejecting version-stale work at save.

**Architecture:** Reuse `CaseStore` for every authoritative source, question, assessment, and saved model hypothesis; reuse `build_patient_mission` as read-only world-model workflow projection; reuse the current `investigations` POST and fixed task templates. Add only a read-only `composer/context` projection, one server-controlled context fingerprint, a small preview inside the *existing* investigation form, and one atomic save check. No parallel agent runtime, chat history, patient store, source ledger, model or external search engine.

**Tech Stack:** Existing Python 3.13 stdlib/SQLite, vanilla JS, existing headless Chromium CI. No Next.js/new dependencies.

**Spec:** User Master Product & Engineering Directive §§4–6, 8–12, 15–16; PR #65 `docs/product/COMPOSER_COPILOT_WORKSPACE_SPEC.md` C0–C3 as proposal; accepted canonical architecture; current repo `src/open_intelligence/{store,mission,investigation}.py` and `web/index.html`.

## Global Constraints

- Existing PRs #49, #51, #53, #56, #64, #65 and #67 remain distinct; no unauthorized merges or editing other owners' branches.
- Founder intent is the full first-party EHR/LIS/PACS/AI healthcare system; this is a permanent integration contract, not a reduced product architecture.
- No Next.js, unreviewed package, real medical data, live model call, actual clinical authority or external guideline text.
- Render only existing active source-linked fictional statements, current human-authored synthetic assessments; preserve unknown/negative/contradicted distinctions and explicitly mark lack of live guideline/research access.
- Use exact patient/case, original source version, line, issue/event/receipt timestamps and a version fingerprint. Unknown and unavailable features must never appear executed or verified.
- Preserve the existing bounded template + replay/live opt-in and existing source viewer; do not create a second chatbot or generic task queue.

## Review Focus

1. A source amendment after preview must block a stale Composer task BEFORE replay or model call and must not persist it.
2. A source amendment DURING a model call must block saving that output atomically; it cannot become a current hypothesis.
3. A foreign question ID and wrong-case source must never be accessible in the preview.
4. Evidence withdrawal or source correction must change the context fingerprint, without silently dropping unrelated historical records.
5. Case/question switching in the real browser must clear pending context, ignore delayed responses, preserve keyboard focus and never run a task with another case's fingerprint.

---

### Task 1 — Executable contract tests first

**Files:** Create `tests/test_composer_context.py`, `tests/test_composer_http.py`.
**Interfaces:** `build_composer_context(store,case_id,question_id) -> dict`; `composer_context_fingerprint(store,case_id,question_id) -> str`; GET `/api/cases/{id}/composer/context?question_id={int}`; POST existing `/api/cases/{id}/investigations` with optional `context_fingerprint`.
- [ ] Write tests for current source/line/time/negative/uncertain, active evidence rights, one derived Patient Mission status, no cross-case leakage, no external content, stable fingerprint.
- [ ] Test stale preflight after amendment, stale save after simulated mid-model mutation, source rights withdrawal, missing question, existing POST without fingerprint remains backward compatible.
- [ ] Run hosted tests; preserve expected red result before code.

### Task 2 — One canonical context projection with fingerprint

**Files:** Create `src/open_intelligence/composer.py`.
**Interfaces:** functions above. Fingerprint uses deterministic JSON SHA-256 of target question, all current case source ids/hashes/metadata, current assertions and current eligible case+question evidence assessments. The preview may display an existing Mission projection but cannot write another patient record.
- [ ] Implement source-scoped read-only context and explicit unavailable-catalog/standard-of-care limitations; cap displayed previews to the same bounded task source set.
- [ ] Ensure fingerprint is computed from exactly the persisted state the model can read; if state changes during preview assembly, refuse/refresh.
- [ ] Test all exact supplied source references and rights filtering.

### Task 3 — Bind the *existing* investigation route to preview

**Files:** Modify `src/open_intelligence/__main__.py` and `src/open_intelligence/store.py`.
**Interfaces:** `CaseStore.save_investigation(..., context_fingerprint=None)` verifies fingerprint within a `BEGIN IMMEDIATE` transaction; preflight rejects stale hash before any live model request. No new actions/authorities.
- [ ] Implement GET preview and optional POST fingerprint; no new "composer run" route.
- [ ] Test red/green including in-flight source mutation and existing old-client compatibility.

### Task 4 — Minimal native UI enhancement and browser evidence

**Files:** Modify existing `web/index.html` and `web/app.js` minimally; create `web/composer.js`; add browser/source assertions.
- [ ] Render the version-bound preview inside the existing model-investigation section, show unavailable capabilities, citation anchors and review-required status.
- [ ] Prevent stale/unloaded preview submissions; update on question and case switches without relying on free-form chat or new backend.
- [ ] Run full unit/HTTP/JS/headless Chromium; record exact PR head and merge candidate; preserve caveats.

### Task 5 — Coordinate with full-system documentation

**Files:** Append evidence to the existing Notion architecture, UX, decisions and Google Docs engineering/clinical records; link PR #65 as the UI design owner, no duplicated roadmap.
- [ ] Map real functionality against user directive and current EHR gaps. Cite Sid source facts separately from modeled product requirements.
- [ ] Keep independent clinical review, rights, PHI, open-literature access and full first-party EHR/LIS/PACS as **unimplemented** until separately verified.
