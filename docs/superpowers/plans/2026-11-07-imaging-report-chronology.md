# Imaging report chronology implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a source-preserving, navigable Imaging report chronology in the existing patient workspace.
**Architecture:** Derive date groups from the already-authorized SourceIndex; render a separately scoped React panel and select an exact source using existing section filters. No new backend owner or derived clinical conclusion.
**Tech Stack:** React 19, TypeScript, Vite, Node tests, existing FastAPI/PostgreSQL browser harness.
**Spec:** `docs/superpowers/specs/2026-11-07-imaging-report-chronology-design.md`

## Global constraints
Fictional-only; preserve immutable original and authorization contracts; no changes to backend/schema/permissions/dependency or canonical ledger; no new AI/clinical conclusions; work on a dependent draft PR.

## Review focus
- A superseded report with a newer source-reported event date than a current report; chronology must sort dates, not status.
- Two independent report versions with identical event dates; preserve both and original order.
- A different source kind with the same document ID; it must not enter the imaging chronology.
- Case/credential change removes the previous source index; chronology must consume the current index only.
- Selecting an old source must not fetch historical image pixels or imply reviewed findings.

### Task 1 — pure chronology
- [x] Write failing tests of `buildImagingChronology(sources:readonly SourceVersion[])` in `apps/web/tests/imaging-report-chronology.test.mjs`.
- [x] Add `apps/web/src/imaging-report-chronology.ts` and include it in `apps/web/tsconfig.client.json`.
- [x] Verify pure tests and TypeScript compile.

### Task 2 — connected presentation
- [x] Write failing SSR tests in `apps/web/tests/imaging-report-chronology-panel.test.mjs` for grouping, source selection and empty state.
- [x] Add `apps/web/src/imaging-report-chronology-panel.tsx`, use it in `SourceReading` for the imaging kind, and style only its own CSS.
- [ ] Verify renderer tests and full local tests where available; record any absent locked dependencies.

### Task 3 — qualification
- [ ] Inspect diff for rights, clinical authority and migration invariants.
- [ ] Create an isolated draft on PR #610's verified exact head and run hosted build, client tests, actual browser and persistent demo.
- [ ] Record acceptance evidence or any unresolved check; do not merge or deploy.
