# Reading continuity on the current source-question workspace

Design and acceptance date: 2 November 2026, America/New_York.

## Purpose and existing ownership

Carry the useful reading improvements from #218 into #271 without replacing the newer source intake, original inspection, source-derived Journey or explicitly authored questions. This advances OI-007/009/010 presentation and #119; it does not complete the clinical platform.

The original candidate parent was `96361fc053e9deea99996c96850eb51075cff1e6`. During setup the upstream branch advanced to `5f53cfcec1002ef756a043d0e3865b39cc1be481`, adding grouped navigation and mobile target checks. Those changes were inspected and preserved. Both independent author branches remain untouched. The comparison baseline for this continuation is the latter SHA.

## Design choice

A wholesale #218 merge would replace newer main.tsx and lose intake/original/question wiring. Keeping the newer UI untouched would leave source quotes detached from their versions and lose the earlier reading affordances. The selected approach is a focused adaptation of presentation only: one source-reading component, response-scoped filters, a patient/clinical reading preference, visible identity, heading focus and status semantics. React/Vite/TypeScript and all dependencies stay unchanged.

Patient reading places literal quotations beside each source with dates and clear current/historical state. Clinical reading exposes specimen and provenance detail more densely. Both display the same source statements and preserve uncertainty; neither changes the actor, permission or available operations. Global Overview/Journey/Records/Investigations/Review labels and new navigation groups remain stable.

Filters only search already-loaded metadata. Their scope is the exact existing source response reference, not a second record store. Navigation and reading preferences retain them; replacing or removing the response resets the visible controls immediately. No browser storage or additional request is introduced. Clearing a no-match filter returns focus to the filter input.

The existing original-inspection button stays next to its source. The existing intake component and all canonical session callbacks remain unchanged. Historical source rows do not borrow current quotations. Context remains visible when there is enough height; an oversized header returns to document flow rather than covering the task.

## Acceptance and implementation sequence

1. Add real-backend browser acceptance before product changes; preserve its meaningful failure.
2. Adapt source-row presentation and response-scoped UI state without touching API/session/validation.
3. Add reading controls, navigation focus, readiness semantics and responsive header behavior.
4. Run existing 81 client tests, rights gate, build and the complete PostgreSQL/FastAPI/Chromium journey on the exact combined source head.
5. Inspect fresh source-reading screenshots and compare every changed path against the parent. Record failures and evidence limits.

Checks cover current versus historical filtering, literal quotation/source association, navigation and reading changes without HTTP requests, no-match recovery, native keyboard disclosure, source refresh reset, 320/390/768/1280 widths, short height and doubled text. Inherited actual-browser checks retain source intake, original reads, amendments, independently scoped questions, stale responses, expiry/reload and denial.

## Boundaries

Only frontend presentation, frontend tests and this documentation may change. No backend, schema, migration, API, registry session, source contract, permission, validation, business/clinical logic, dependency, reference-app or workflow change is included. No new account roles, clinical approval, model execution, real records, external service, merge or deployment.

This is engineering acceptance with independently authored fictional records. It is not patient/clinician participant research, screen-reader certification, complete WCAG conformance, a measured performance improvement or clinical validation.

## Results

Pending combined-head execution. The test-only hosted run 41575383455 (head b66160cf4c981b8aa98bb0d178c8b6322bd883c8, job 125717554465) reached the real-backend browser and failed as intended: `Loaded source versions need a response-scoped filter`. This is the preserved pre-implementation failure. An inherited intake-test selector matched the complete text `Overview`; upstream navigation now adds an Identity and access hint. It is updated to the existing explicit nav-overview test ID, preserving the same return-to-overview action. The inherited local 81-test suite, dependency rights gate and production build passed before presentation changes. Local PostgreSQL and Chromium are unavailable; actual-backend acceptance uses the existing hosted workflow, whose results must be inspected rather than inferred from parent runs.
