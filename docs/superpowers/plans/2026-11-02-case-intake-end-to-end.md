# Connected case intake implementation plan

**Goal:** A user can start from an empty local database, create a fictional case, select original report files, inspect individual import outcomes, ask a question, prepare/review an existing Composer report, and import a correction without terminal seeding.

**Architecture:** Extend the existing CaseStore case/import APIs and canonical case picker. Intake is an original browser controller, not a new patient registry, extraction engine, database or approval service. Stack on source-owner PR #158 (`1bb4ff06a5ab222d3561145e757226f671dbf3ea`) and preserve its safety prerequisite #123.

**Tech stack:** Existing standard-library Python/SQLite reference and first-party JavaScript; no new dependency. The accepted H1 FastAPI/PostgreSQL + React/Vite/TypeScript direction remains unchanged and this slice supplies behavior for migration parity; no Next.js.

**Spec:** Existing OI-006/007/009/010, docs/FIRST_PRINCIPLES_PLAN.md and docs/engineering/EXECUTION_AUDIT_2026-11-02.md. This is additive reference implementation, not the final navigation/design.

## Constraints
- Original fictional structured UTF-8 reports only; no PHI, patient-derived fixtures, PDFs/OCR or clinical extraction claim.
- Exact bytes must survive UTF-8 decoding/re-encoding; never trim, normalize or rewrite patient identifiers.
- Use existing server quarantine, duplicate, amendment and staleness rules; no competing imports or bulk transaction.
- At most 20 files per explicit batch, 64 KiB per file and 1 MiB total. Bound before read; sequential writes in supplied order; one case captured for entire batch.
- Network/invalid-response outcomes are unknown, not falsely rejected. Stop remaining writes until user refreshes/reconciles. No automatic retry.
- Current case cannot switch during a batch. Existing unsaved-work guard must apply before creating/selecting a case.
- Original evidence/model workflows remain reviewed proposals; replay is not live intelligence and acknowledgment is not clinical sign-off.

## Deliverables and checks
- [ ] Test-first file decoding and batch controller: bounds, original UTF-8, unsupported files, quarantine/duplicates, partial failure, ambiguous network result, cancellation, no patient-ID rewriting.
- [ ] Case-create and file-intake UI with explicit fictional-data attestation, staged file selection, per-file receipts, next-step links and case-lifecycle integration.
- [ ] Existing API static route for intake script only; no source schema/backend importer changes.
- [ ] Fresh-database Chromium journey: case creation → mixed source-file batch → question → replay → prepared report → explicit acknowledgment → correction → stale original → new report → restart persistence.
- [ ] Full application/JS regression, existing browser journeys and source inventory regeneration; exact-head hosted checks before claims.
- [ ] Publish reviewed diff as child of #158 without rewriting owner branches; update existing project records. Leave release/clinical/authentication gates intact.
