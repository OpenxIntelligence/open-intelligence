# Laboratory comparison table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a compact, source-preserving table to the existing laboratory browser.
**Architecture:** A pure display projection selects source indices and bounded pages. Existing React rows and table rows share one provenance component and the original callbacks. No canonical state is added.
**Tech Stack:** Existing React 19.3.1, Vite 7.3.7, TypeScript, Node tests; browser checks use the archived exact React runtime.
**Spec:** `docs/superpowers/specs/2026-11-06-laboratory-comparison-table-design.md`

## Global Constraints
Unchanged patient/source/authority owners; no runtime dependencies or backend changes; independently fictional fixtures; no clinical interpretation; do not modify donor branches or main; publish only an isolated draft after local review.

## Review Focus
Exact zero/negative/textual numeric values; different units under one code; reused local observation/specimen references; filter/page retention and short result sets; keyboard/mobile rendering and source actions.

### Task 1: Pure display projection
Files: create `apps/web/src/laboratory-result-view.ts`, `apps/web/tests/laboratory-result-view.test.mjs`; add module to `tsconfig.client.json`.
- [x] Write tests for exact filtering, source-local contexts, ordering, literal values, absence, empty results, page bounds and immutability; run red.
- [x] Implement `laboratoryContextKey(result)`, `selectLaboratoryResults(results, filters, page)` with index-based output and summary; run green.

### Task 2: Connected compact view
Files: update `apps/web/src/laboratory-result-browser.tsx`, `apps/web/src/styles.css`, and existing renderer tests.
- [x] Browser regression must fail because Table view does not exist.
- [x] Add pressed-state layout buttons, current-record counts, semantic table, shared provenance and bounded pagination. Default cards remain unchanged.
- [x] Verify browser filter retention, actions, mobile scroll, source clearing and escaped text. Run all executable existing client tests. Record unrun full-build/database gates explicitly.
- [x] Package source patch, tests, screenshots and verification receipt without publishing or merging.

## Connected-product continuation — 6 November 2026

Base: PR #602 `2e37d7579f3d748dfe2918a1ec4d02872e0e625c`, tree `1582c686199ad7e4ba873c48063b26f895e145a6`. Its archive was reconstructed to the same Git tree before changes.

- [x] Reconcile the earlier local patch with the connected-product foundation, preserving all API, schema, source, question, follow-through and suspension owners.
- [x] Scope compact-view styles to `laboratory-result-browser.css`, imported by the existing component; retain the integrated shared stylesheet byte-for-byte.
- [x] Run the executable client checks and review the full diff.
- [ ] Publish an isolated dependent draft; run the unchanged pinned-toolchain, rights, build and real API/browser workflows on its exact commit.
- [ ] Record actual final results and remaining gates. No merge or deployment.

Ruling: the earlier local-only packaging boundary was a delivery checkpoint, not a permanent ban on an isolated review branch. The user's continuation request advances the missing hosted checks without modifying accepted code.
