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
- [x] Merge #262 without replacing image grants or completed response callbacks.
- [x] First demonstrate the missing single combined migration head in a graph test.
- [x] Add explicit merge and populated parent-upgrade/rollback acceptance.
- [x] Align current-readiness expectations and standalone recovery helpers only;
      retain historical revision expectations where they describe old states.

## Task 2: Prove one image/question/verification-return lifecycle

Files: new `apps/api/tests/test_image_review_integration.py` and existing
`apps/api/tools/verify_images_compose.py` (combined recovery extension).

Interfaces: existing source preflight/question APIs, image import/read APIs,
`GET /review-queue`, `POST /questions/{id}/return-for-verification`.

- [x] Add acceptance for a current image/report question, return receipt and independent grants.
- [x] Assert image changes/reads preserve source/question/queue hashes.
- [x] Add acceptance for source amendment, historical anchors/receipts and explicit image relinking,
      retry original return, create a new question and new return.
- [x] Extend the recovery probe through restart and an API attached to a restored DB.
      Actual execution remains part of Task 4.

## Task 3: Retain review authority through actual JSON encoding

Files: new `apps/api/tests/test_review_disclosure_authority.py`, review route
callbacks in `apps/api/src/oi_api/patients.py`.

- [x] Add real-serializer authority/failure/locking/commit tests covering queue,
      new return, duplicate and post-amendment retry; observe both baseline
      Pydantic and prepared JSONResponse paths rather than assuming the encoder.
- [x] Publish bounded tests-first draft checkpoint and inspect actual PG failures.
- [x] Construct the complete validated JSONResponse in existing prepare callbacks;
      keep final authorization/audit/commit ordering and 200/201 semantics.
- [ ] Re-run exact-head hosted tests, resolving only concrete failures.

## Task 4: Review and publish evidence

- [x] Independent whole-change code/migration review; address material findings.
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
- Independent review reproduced an inherited client defect: a same-case source
  import erased an uncertain verification-return intent. Two new regression tests
  failed with idle instead of unknown; retaining the matching case in the existing
  reset helper repairs both an already uncertain and still in-flight return. A
  third regression preserves clearing on import authority denial. All 98 client
  tests pass after this focused repair; no automatic retry is introduced.
- Follow-up review reproduced a successful import followed by source GET 503,
  missing case metadata and a case refresh erasing the same uncertain intent.
  The exact regression failed before repair. Missing metadata now keeps recovery
  unknown while requiring case recheck; successful recheck retains the same key
  only for an active mapping, and denied/removed/revoked contexts clear it. Seven
  new recovery and authority-boundary tests pass, including a late case response
  after patient change. The final local client suite is 105 passed, zero skipped;
  the final delta was independently reviewed without a material finding.
- Hosted tests-first head `05c6ef38dc8beddee064f97959035498751dad3e`,
  [API run 41576685948](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41576685948),
  ran all 314 tests with zero skips. Exactly 32 subcases in the four new review
  disclosure methods failed: 20 late authority changes, four encoder failures,
  four premature visibility/lock checks and four deferred-commit ordering checks.
  There were no test errors. All combined migration and image/review lifecycle
  tests passed. The same-head React/browser workflow passed its original 95 client
  tests and real PostgreSQL/FastAPI/built-React journey. Complete final-head results
  belong in PR #278 and the canonical engineering records after execution.
