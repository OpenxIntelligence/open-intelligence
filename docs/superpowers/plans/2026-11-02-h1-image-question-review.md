# H1 image/question/review convergence implementation plan

> **For agentic workers:** Use the existing execution workflow, with independent
> migration and lifecycle tasks and a fresh final reviewer. Preserve existing owners.

**Goal:** Connect original image custody and canonical questions to immutable
operational verification returns in one verified H1 runtime.

**Architecture:** Join exact #263 and #262 histories, preserving source/question/
image/review/event ownership. Add one explicit no-DDL migration merge. Complete
review JSON response preparation within the existing final-authority transaction.

**Tech Stack:** Existing Python 3.12, FastAPI/Pydantic 2, Alembic/PostgreSQL 16,
React/Vite/TypeScript and locked code-only pydicom; no new dependency.

**Spec:** `docs/superpowers/specs/2026-11-02-h1-image-question-review-design.md`

## Global constraints

- Preserve exact parent SHAs and published migration bytes from the spec.
- Preserve independent grants, fixed original anchors and typed response schemas.
- Independently authored fictional fixtures only; draft/unmerged/undeployed.
- Actual hosted PostgreSQL tests must run without skips; keep all recovery gates.

## Review focus

- Existing populated history from either branch survives a missing sibling upgrade.
- Image activity does not silently make a verification return stale or current.
- Same-intent retry after amendment preserves historical receipt without approval.
- Grant/actor changes during real JSON encoding withhold response and new effects.
- API restored against a different database serves that copy's preserved history.

## Task 1: Converge published histories and contracts

Files: `apps/api/src/oi_api/{access,contracts,patients}.py`, existing API workflow,
`apps/api/migrations/versions/0009_image_review_merge.py`, migration tests and
the owner Compose helpers. Preserve all imported #262 frontend files.

- [x] Verify exact #263 tree and baseline API/settings contracts (10 pass).
- [ ] Merge #262 without replacing image grants or completed response callbacks.
- [ ] First demonstrate the missing single combined migration head in a graph test.
- [ ] Add explicit merge and populated parent-upgrade/rollback acceptance.
- [ ] Align current-readiness expectations and standalone recovery helpers only;
      retain historical revision expectations where they describe old states.

## Task 2: Prove one image/question/verification-return lifecycle

Files: new `apps/api/tests/test_image_review_integration.py` and existing
`apps/api/tools/verify_images_compose.py` (combined recovery extension).

Interfaces: existing source preflight/question APIs, image import/read APIs,
`GET /review-queue`, `POST /questions/{id}/return-for-verification`.

- [ ] Exercise a current image/report question, return receipt and independent grants.
- [ ] Assert image changes/reads preserve source/question/queue hashes.
- [ ] Amend source, retain historical anchors/receipts, explicitly relink image,
      retry original return, create a new question and new return.
- [ ] Exercise the same history through restart and an API attached to a restored DB.

## Task 3: Retain review authority through actual JSON encoding

Files: new `apps/api/tests/test_review_disclosure_authority.py`, review route
callbacks in `apps/api/src/oi_api/patients.py`.

- [ ] Add real-serializer authority/failure/locking/commit tests covering queue,
      new return, duplicate and post-amendment retry; observe both baseline
      Pydantic and prepared JSONResponse paths rather than assuming the encoder.
- [ ] Publish bounded tests-first draft checkpoint and inspect actual PG failures.
- [ ] Construct the complete validated JSONResponse in existing prepare callbacks;
      keep final authorization/audit/commit ordering and 200/201 semantics.
- [ ] Re-run exact-head hosted tests, resolving only concrete failures.

## Task 4: Review and publish evidence

- [ ] Independent whole-change code/migration review; address material findings.
- [ ] Full API/PG16, reference, browser, dependency and recovery workflows pass.
- [ ] Compare submitted source tree to local candidate and browser artifact.
- [ ] Update draft PR, existing Notion engineering and Drive engineering receipts.

## Execution notes

- Local #263 import is byte-exact (tree `e8ef9d6d49ea309b39961381648323617836a46e`).
- Baseline test invocation initially omitted PYTHONPATH and failed import; corrected
  invocation ran 10 contracts/settings tests successfully. This was setup evidence,
  not a product failure.
- User continuation and canonical records authorize this bounded implementation;
  no new architecture, dependency, merge or deployment decision is requested.
