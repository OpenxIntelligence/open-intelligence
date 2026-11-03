# PDF connected workflow implementation plan

> For agentic workers: execute with superpowers:executing-plans; use test-driven-development.

**Goal:** Extend #221 with the source-owned #215 ordinary-text/PDF intake and preserve manual/page provenance through report and follow-through.
**Architecture:** Existing CaseStore and clinical/knowledge/report/task owners; source/rendition extensions from #215. Distinct input adapters share one workspace and host mutation/draft lifecycle.
**Tech Stack:** Existing Python/SQLite/browser JS; optional hash-pinned pypdf worker. No H1 replacement.
**Spec:** docs/superpowers/specs/2026-11-03-pdf-connected-workflow-design.md

## Global constraints
Fictional inputs only; immutable originals; manual is not clinical; fail closed; no live model; no new dependencies beyond source-owned optional parser; no merge/deployment.

## Review focus
Missing original/extraction/page provenance; two colliding intake asset names; stale preview and in-flight writes; source amendments with historical tasks; rights-class/actor/case export denial.

## Tasks
1. Record red cross-domain acceptance on #221 for import_document plus follow-through/report. Reconcile backend source-owner files and tests with pinned #215. Preserve original authority and review schema and all inherited tests.
2. Extend existing patient/evidence projections only where new tests demonstrate manual/page attribution loss. Test exact original/rendition references, missing/forged provenance refusal, amendment and restart.
3. Mount renamed document intake alongside existing structured intake. Keep shared write tracking, source inspector and scope guards. Retain original source-owner client tests; add cross-adapter lifecycle regressions.
4. Extend the existing real PDF browser journey to task/report use; run full regression and existing browser gates on one exact tree, retain source artifacts, inspect screenshots and publish draft with exact-head verification.

## Evidence ledger
- #221 authored head 2a246b54bb29cbd844c77f06f8e3a20ddff8dcc7; source tree 85d2b15bba994233d277a94cefd7b8f9e05aa955 matched downloaded archive.
- Baseline full local suite: 686 passed in 31.203s (TMPDIR=/dev/shm); not power-loss durability evidence.
- #215 authored head 3be1106b5cd34523c4746e2df6f123048beb5659; UI source archive tree b03dc8a5d14f2bf7ca4c99a4c8b72491812015ee confirmed against the authored remote Git tree.
- Local installed pypdf is 5.9.0; do not weaken incoming 6.21.4 pin. Exact parser tests require the pinned environment.

- Regression-first: missing source-owner import, erased manual origin in patient/knowledge/authorized reports, duplicate Composer mounts, unguarded reviewed-document drafts, and preview/write lifetime were reproduced. The selected existing event-source and context route were reconciled rather than duplicated.
- 172 JavaScript checks passed locally. Focused ordinary-text/source/report/authority/route tests passed; local full-suite command timed out. A module-by-module pass exposed the unavailable exact PDF parser and one legacy missing-source regression, which was repaired without weakening manual provenance. Local PDF success is not claimed.
- Host transport keeps the existing single-question parameter guard; duplicate and blank-duplicate values fail before reading. One earlier new-test indentation error remains in the evidence log, corrected before the observed HTTP200 duplicate-parameter red result and passing rerun.
- Inline review only. Exact pinned-parser, full application and original browser gates remain required on the published candidate.
