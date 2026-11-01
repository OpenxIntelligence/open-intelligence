# Source-line comparison implementation plan

Goal: make the existing Source Change Explorer show exact previous-only and updated-only report lines, without interpreting clinical meaning.
Spec: docs/UI_CHANGE_REVIEW_SPEC.md, next bounded improvement 1; OI-007/OI-009. Baseline: cf7c671fb9fe52ec310b128ceef393eb8f42c570 in draft PR #29.

## Scope and design
Extend the current read-only predecessor/successor viewer, preserving verified lineage, selected-case/read-intent guards, immutable source text and existing DOM/CSS. Use an original deterministic line-alignment function and inert mark/text nodes. No framework, third-party diff package, schema, model, vendor, clinical data, new architecture or source-authority change.

Exact line tokens retain newline and whitespace characters. The comparison reports previous-only and updated-only 1-based source line numbers, and highlights those lines in the two complete originals. Repeated lines are aligned deterministically. Pure formatting changes remain changes; equality never implies clinical equivalence. The UI must explicitly label this as text comparison, not clinical interpretation.

Bound the algorithm before allocation: at most 65,536 UTF-16 code units and 512 line tokens per source; dynamic-programming matrix at most 263,169 Uint16 cells. Inputs beyond limits keep both full original texts visible and state that highlighting was skipped; never imply no difference. Identical inputs within bounds report identical text only.

## Work
- [ ] Add failing Node tests and wire into existing CI.
- [ ] Implement pure compareReportLines and inert rendering in web/app.js; keep all other UI behavior.
- [ ] Test unchanged/insertion/deletion/replacement/repeated lines, Unicode, CRLF, blank/empty strings, final newline and bounds.
- [ ] Exercise real browser comparison, exact source preservation, no source-markup execution, fallback and 390px layout.
- [ ] Run full integrated CI and retain exact tested commit/run evidence.
- [ ] Update existing Notion and Google engineering documentation; keep PR draft pending review.

## Review focus
Wrong report lineage stays blocked. Older async responses cannot redraw. All source characters must survive rendering exactly. Missing source is not empty source. Expensive inputs fall back visibly. Highlight count is not a medical severity score. No clinical, legal, accessibility or production-readiness claim follows from passing tests.
