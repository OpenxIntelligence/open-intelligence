# Source-line comparison implementation plan

Goal: make the existing Source Change Explorer show exact previous-only and updated-only report lines, without interpreting clinical meaning.
Spec: docs/UI_CHANGE_REVIEW_SPEC.md, next bounded improvement 1; OI-007/OI-009. Baseline: cf7c671fb9fe52ec310b128ceef393eb8f42c570 in draft PR #29.

## Scope and design
Extend the current read-only predecessor/successor viewer, preserving verified lineage, selected-case/read-intent guards, immutable source text and existing DOM/CSS. Use an original deterministic line-alignment function and inert mark/text nodes. No framework, third-party diff package, schema, model, vendor, clinical data, new architecture or source-authority change.

Exact line tokens retain newline and whitespace characters. The comparison reports previous-only and updated-only 1-based source line numbers, and highlights those lines in the two complete originals. Repeated lines are aligned deterministically. Pure formatting changes remain changes; equality never implies clinical equivalence. The UI must explicitly label this as text comparison, not clinical interpretation.

Bound the algorithm before allocation: at most 65,536 UTF-16 code units and 512 line tokens per source; dynamic-programming matrix at most 263,169 Uint16 cells. Inputs beyond limits keep both full original texts visible and state that highlighting was skipped; never imply no difference. Identical inputs within bounds report identical text only.

## Work
- [x] Add failing Node tests and wire into existing CI.
- [x] Implement pure compareReportLines and inert rendering in web/app.js; keep all other UI behavior.
- [x] Test unchanged/insertion/deletion/replacement/repeated lines, Unicode, CRLF, blank/empty strings, final newline and bounds.
- [x] Exercise real browser comparison, exact source preservation, no source-markup execution, fallback and 390px layout.
- [x] Run full integrated CI and retain exact tested commit/run evidence.
- [x] Update existing Notion and Google engineering documentation; keep PR draft pending review.

## Observed verification

Test-first run [41269035211](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41269035211) failed all 15 new acceptance tests before the implementation existed.

[Integrated run 41269632107](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41269632107) passed 23 line-comparison tests (including 400 generated source pairs and an independent algorithmic oracle), 16 existing source-view concurrency/identity tests, 38 Python unit/HTTP tests, compilation/syntax, and three Chromium journeys. The new browser check imports the authored amendment and verifies exact highlighted originals, inert source markup, oversized fallback, identical-state reset, close/reopen and 390px containment. [Crossref run 41269632139](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41269632139) also passed.

Verified feature code: `22b4106e292296038a3b712a2d9462ffec6f4dd9`. Tested merge checkout: `caa1ce4aebf4ca1520070705591b30510a60a799`, against main `46bb1db45fac002eda5886bd17caf59af2acbbc5`. Later documentation commits do not retroactively change the recorded test identity. These are UI-branch checks, not evidence that separate evaluation PR #24 is integrated.

Existing documentation updated: [Notion product experience](https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f) and [Engineering Progress Google Doc](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit).

## Review focus and remaining gates
Wrong report lineage stays blocked. Older async responses cannot redraw. All source characters must survive rendering exactly. Missing source is not empty source. Expensive inputs fall back visibly. Highlight count is not a medical severity score. No clinical, legal, accessibility or production-readiness claim follows from passing tests.

The full-product/whole-patient requirements research gate remains authoritative: this bounded prototype capability does not approve final information architecture, navigation, visual design or clinical workflows. Independent code review, manual assistive-technology/zoom/real-device checks, clinical usability and legal/real-data authorization remain outstanding. PR #29 stays draft and unmerged.
