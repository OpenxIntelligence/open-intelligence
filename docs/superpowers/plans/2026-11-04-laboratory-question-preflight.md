# Laboratory question preflight implementation plan

> Use superpowers:executing-plans task by task. Preserve tests-first evidence.

**Goal:** Prepare an exact typed laboratory context through the existing source owner.
**Architecture:** Extend Composer preparation; keep durable text questions unchanged.
**Tech stack:** Existing Python, FastAPI, Pydantic, PostgreSQL-owner contracts.
**Spec:** `docs/superpowers/specs/2026-11-04-laboratory-question-preflight.md`

## Global constraints
Fictional only; no new dependency/schema/permission/ledger; no invented text line;
no model or clinical approval; current authorization after complete serialization.

## Review focus
Wrong patient/case and foreign resource IDs; stale or superseded source; numeric
zero versus absent reason; response/receipt failure; unsupported request fields and
oversized bodies. Record unexecuted PostgreSQL/browser gates without inherited-green claims.

## Task 1: source-owned typed preparation
- [x] Add failing tests to `apps/api/tests/test_laboratory_question_preflight.py`.
- [x] Extend `apps/api/src/oi_api/composer_preflight.py` with a pure typed-envelope
  builder and `PostgresSourceComposerPreflight.preview_laboratory`.
- [x] Verify selection, identity, freshness, literal values, hash stability and
  delegation to the single source-owner transaction.

## Task 2: bounded authorized route
- [x] Add failing route/request-limit tests without claiming database integration.
- [x] Extend `laboratory_fhir_routes.py` with explicit typed request/response and
  `/composer/laboratory-preflight`; require source/composer grants, preserve final
  checks and serialize before receipt commit.
- [x] Add the path to `request_limits.py` and the existing exact OpenAPI allowlist.
- [x] Author actual PostgreSQL acceptance using the existing laboratory fixture.

## Task 3: verification and delivery
- [x] Run focused tests, source parser/integrity tests and full project discovery;
  record environment blockers, skips and failures rather than hiding them.
- [x] Self-review the complete diff; no independent review claimed.
- [x] Package an apply-checked patch, test logs and source identity.
- [ ] Publish through an authorized write path when available. No remote publication, merge or deployment is claimed.

## Verification limits
The 22 new focused checks and 23 inherited parser/integrity checks pass locally.
The five new real PostgreSQL/HTTP cases are authored but unexecuted; full API
discovery remains blocked by the same 65 missing-pydicom import errors and 27
skips as the baseline. Actual PostgreSQL/browser/recovery and independent review
remain required. See `docs/engineering/H1_LABORATORY_QUESTION_PREFLIGHT.md`.

Reference regression: 765 methods executed; nine failures and eight errors all
at the PDF dependency guard. All 17 failure/error entries reproduced on the
unchanged base (installed pypdf5.9.0 versus required6.21.4). No gate changed.
