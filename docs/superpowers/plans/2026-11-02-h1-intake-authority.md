# H1 Intake Final Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Refuse source intake and record received writes if the original authority changes before their existing transaction commits.

**Architecture:** Extend PostgresSourceVersions.import_original and PostgresRecordRequests.receive with the established final-authority/prepared-response callback pattern. HTTP adapters validate and serialize their existing receipt before the final recheck. Preserve all existing storage owners, locks and events.

**Tech Stack:** Existing Python/FastAPI/Pydantic/PostgreSQL 16 with hash-locked dependencies; unchanged React/Vite client.

**Spec:** docs/superpowers/specs/2026-11-02-h1-intake-authority.md

## Global Constraints

- Exact source base: #244 `3b6c466950852c20f99d57a70dd196fd2862571a`, tree `3005aa34aea15413713c87a288619efb8fdeb030`.
- Independently authored fictional records only; no new dependency, schema migration, state owner, model or clinical authority.
- Preserve source bytes, hashes, immutable history, independent grants and existing successful statuses/idempotency.
- No main/shared-owner edits, merge, deployment, external notification or patient-data acquisition.

## Review Focus

- Duplicate/quarantine early returns must refresh authority even when no row is inserted.
- Denied amendments must roll back predecessor supersession, new assertions and source events together.
- An actor/organization/purpose change on the same bearer must not pass on unchanged action names.
- JSON serialization is application work: a late failure or permission change must precede commit.
- Receipt retries after an amendment may recover their historical pointer only with current independent authorization.

## Task 1: Reproduce intake and receipt races at the real persistence boundary

**Files:** Create apps/api/tests/test_intake_write_authority.py; this spec and plan.

**Interfaces:** Existing source-version HTTP fixture and real PG16 disposable database; no production changes.

- [ ] Add tests for revoked source_import/patient_read, patient membership and changed principal during import/amendment/quarantine/duplicates; assert expected HTTP refusal and exact unchanged database state.
- [ ] Add record receipt/new and duplicate tests for independently revoked receive/read grants and changed identity; assert zero new received events and legitimate restored retry.
- [ ] Add DTO/JSON failure and late-grant mutation tests; retain actual transaction and writer effects.
- [ ] Compile/discover locally and record PostgreSQL skips honestly; publish a tests-first draft and run actual PG16 acceptance.
- [ ] Inspect hosted red evidence for the intended permission/commit failures before runtime changes.

## Task 2: Extend the existing writer completion protocol

**Files:** apps/api/src/oi_api/sources.py, record_requests.py, patients.py, access.py documentation if needed.

**Interfaces:** Both methods require recheck_authority: Callable[[], None] and accept prepare_response: Callable[[dict], PreparedResponse] | None = None. Every successful return prepares the existing receipt, then invokes the callback inside the transaction. The routes pass prepared JSONResponse and their existing same-bearer reauthentication functions.

- [ ] Implement the completion path for every successful intake branch and both receive branches.
- [ ] Prepare validated JSON bytes/status before authority refresh; keep existing read/question behavior and independent authorization checks.
- [ ] Run local available tests and full hosted API/PG16 plus React/browser gates on exact head; resolve actual failures without weakening acceptance.
- [ ] Obtain independent whole-branch review; fix material findings with regression evidence.

## Task 3: Preserve reviewable evidence

**Files:** Existing H1 source/receipt documentation and implementation/backlog notes; this plan.

- [ ] Record actual tests-first failure and final exact-head results, source identity, dependency boundary and limitations.
- [ ] Verify hosted artifact head/source and final draft status; update PR receipt with final results.
- [ ] Keep the branch draft, unmerged and undeployed.

## Execution ledger

- 2 November 2026 ET: live #244 is implemented; #262 and the neighboring source-brief owner are active. Selected this existing-writer repair to avoid duplicate integration ownership.
- Local checkout is isolated; actual #244 commit/tree matches the GitHub Git object. Local PostgreSQL, Docker and Chromium are absent. Hosted workflows supply the required actual PG/browser acceptance.
- Ruling: keep existing read/question authority helpers unchanged and reuse them for write callbacks. This avoids unrelated authority refactoring; helper names remain historical.
- Ruling: prepare JSONResponse inside the owner transaction, extending DTO preparation through serialization. This closes the application work window without claiming atomic network delivery.
- Unchanged local base: 192 API tests discovered, 42 executed successfully and 150 skipped because real PostgreSQL is absent. New regression module: ten methods discovered, all ten skipped locally for the same explicit reason. Compilation and whitespace checks passed. Hosted execution is required for red/green evidence.
- First hosted red checkpoint `8c0c8655280e6b1ffb7dce9b5983b6237b4cb944`, run [41573301941](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41573301941): 202 actual API/PG executions; 33 failed assertions/subtests, zero test errors/skips. Entry-only authority was reproduced on import/amendment/quarantine/duplicate/receive paths. The unchanged React workflow passed.
- Test instrumentation correction: typed FastAPI responses bypassed JSONResponse.render on the unchanged base, so the render fault and lock hook did not fire. Those failures are not evidence that the old renderer threw or held/released a lock. Added receipt-constructor hooks that run on both old and new routes; moved the lock probe there. The new raw-response helper inspects unexpected plaintext errors, and refusal assertions now read durable state even if the HTTP status is wrong. Keep the candidate's separate explicit-render checks and the same refusal/rollback expectations.
