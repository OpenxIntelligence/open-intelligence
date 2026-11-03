# H1 Workspace UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. User authorizes autonomous frontend execution; no further ordinary design approval gate.

**Goal:** Deliver differentiated patient/clinical reading layouts and a usable source chart on the existing H1 React/API integration.

**Architecture:** One unchanged `RegistrySession` remains the only API client/state owner. New components present its existing typed state; view/filter/focus state stays transient and does not grant access or reinterpret records.

**Tech Stack:** Existing React 19.3.1, Vite 7.3.7, TypeScript 5.9.3; CSS and native controls; existing Node/CDP checks.

**Spec:** `docs/ux/2026-11-02-h1-workspace-design.md` and the founder's attached frontend redesign directive.

## Global constraints

- No backend, database, API endpoint/contract, authentication, authorization, validation or clinical business-logic change.
- No new dependency, framework migration, external service or source of patient truth.
- Preserve all existing H1 actions and destinations and the retained `web/` reference application.
- Use actual API data; independent fictional records are only test inputs in disposable environments.
- Publish only executed checks with exact base/head evidence; preserve existing Notion/Drive material.

## Review focus

- Credential expiry while Records is open must expose a reconnect path and erase previous source content.
- Switching reading view or destination must not send a request or lose unfinished identity input.
- A filter must not leak across patients/cases or imply that hidden records never existed.
- Long source text, IDs and 320px layout must not obscure identity, focus or actions.
- Source history and quotations must retain exact version, status and line association after filtering.

## Task 1: Baseline and source inventory

Files: documentation and current-run screenshots only.

- [ ] Read actual H1 source, retained reference inventory, Notion/Drive decisions and primary research.
- [ ] Reproduce unmodified build/client checks and browser journey with real disposable PostgreSQL where the environment permits; record any baseline failures separately.
- [ ] Capture and inspect desktop/mobile baseline screenshots; record actual UI findings and bounded feature inventory.

## Task 2: Reading layouts and patient chart

Files: `apps/web/src/main.tsx`, `apps/web/src/styles.css`, `apps/web/src/records-panel.tsx`, presentation-only helper if needed; `apps/web/tools/browser_journey.py`, new browser assertion helper; frontend-only unit tests if derived filtering needs independent coverage.

Consumes: existing `ViewState`, `Patient`, `SourceIndex`, `SourceVersion` and `RegistrySession` public methods without modification.

Produces: `RecordsPanel({state, view, onOverview, onLoadCases, onLoadSources})`, where view is `patient | clinical`; native controls and unchanged session semantics.

- [ ] Add a meaningful browser assertion for persistent identity and two reading layouts; run it against the baseline and observe the absent behavior.
- [ ] Implement reusable records/chart presentation, local loaded-source filters and two intentional layouts; preserve exact existing call payloads and clinical wording.
- [ ] Exercise source history, literal quotations, no-match/clear filtering, navigation focus, narrow reflow, draft preservation, session expiry and denied reads using the existing real API test harness.
- [ ] Run full frontend client checks and TypeScript/build; review unrelated file boundaries.

## Task 3: Review, research record and publication

Files: `docs/ux/**`, `apps/web/README.md`, existing backlog evidence; no domain implementation changes.

- [ ] Obtain independent whole-change review and resolve material findings with regression coverage.
- [ ] Capture and visually inspect patient home, clinical chart, records/history and mobile screenshots; compare with the exact baseline.
- [ ] Consolidate the requested 22 research/product/design/QA outputs into a linked report with sources, confidence, dates, alternatives and decisions.
- [ ] Create an isolated draft PR against the inspected #200 source branch; verify its actual head and CI results, without merging.
- [ ] Append dated evidence to existing Notion UX/Roadmap and the existing Drive UX folder; preserve prior documents and link the exact PR and report.
- [ ] Report changed files, tests, scope proof and remaining unimplemented platform/user-study work honestly.
