# H1 archive/disclosure convergence implementation plan

> Execute inline with superpowers:executing-plans and test-driven-development.

**Goal:** Unify #261 archive retrieval and #253 final prepared-disclosure authority.
**Architecture:** Preserve the source/image owner. Release locks around archive
I/O; complete bounded response preparation under the fresh post-fetch transaction.
**Tech Stack:** Existing locked FastAPI/Pydantic/PostgreSQL16 and React/Vite.
**Spec:** `docs/superpowers/specs/2026-11-03-h1-archive-disclosure-convergence.md`.

## Global constraints and review focus

Only independent fictional data. No new dependencies, migrations, stores,
permissions or live PACS integration. Draft/unmerged; main and both source-owner
branches untouched. A receipt is not evidence of delivery or atomic external
revocation. Review the two lock phases, byte equality, changed authority after
preparation, failed preparation and real deferred commit failure.

## Task 1: reproduce the archive disclosure gap

- [x] Add `apps/api/tests/test_archive_disclosure_authority.py` to pristine #261.
- [x] Exercise actual HTTP, existing fictional originals, real database locks
  from independent sessions, late authority, provider, constructor and commit
  failures; assert sanitized withholding and unchanged successful-read events.
- [x] Observe the hosted PostgreSQL test-only failures before modifying runtime.

## Task 2: compose the existing implementations

- [x] Reuse #253's source owner, source validation/tests, metadata preparation,
  original response callback, and backend-triggered React regression workflow.
- [x] Preserve #261's composition-root injection, tests and documentation.
- [x] In `images.py`, retain #261 preflight/lock release/fetch/revalidation, then
  execute #253 preparation/final authority/receipt/commit in its final transaction.
- [x] Wire `patients.py` original read to the same optional archive port. Keep
  all existing response bytes, headers, identifiers and grants.

## Task 3: verify exact combined head

- [x] Local syntax, whitespace, reference suite and source-integrity checks.
- [ ] Hosted complete API/PostgreSQL, source/image restart and dump/restore,
  retained browser journeys, and React/client/build/browser verification.
- [ ] Inspect exact-head source artifacts and evidence; record actual counts,
  failures, warnings, independent-review and private-PACS gates without overclaim.

## Execution ledger

- Isolated disposable reconstruction of #253 has exact Git tree
  `f1ab7443e93e12defef552d66daf3db7edef31a1`, verified from the earlier downloaded
  source artifact. Direct local GitHub DNS, pg8000, pydicom, Docker and PostgreSQL
  are unavailable; do not substitute local skips for hosted PostgreSQL evidence.
- Ruling: test-only branch starts at #261 to reproduce the remote-path gap;
  final owner-convergence commit includes #253 as a second parent. Neither parent
  branch nor main is merged or rewritten.

- Task 1 complete: hosted run 41576570150 at test-only head
  `1b34de32809890d7bab62f2c8ab87b1090ba7800` ran 205 tests with 11 assertion
  failures in five new methods, no setup/import errors. Seven late authority
  changes and one missing-provider case still disclosed bytes; preparation
  failure returned 500; locks were free during preparation; deferred commit
  failure preceded preparation. Suspension-during-fetch and all inherited tests
  passed. The six new tests were unchanged for the first combined candidate.
- Pre-flight interface: #261 optional archive feeds #253 original response
  callback. Preserve both: no transaction spans remote I/O; the fresh final
  transaction owns preparation, final authorization, receipt and commit.
- Task 2 implemented locally: app and archive tests reproduce #261 blob hashes;
  only image original composition and injection extend #253 runtime. All #253
  source/index/metadata guards and tests remain byte-identical.
- Baseline local reference run: 245 tests passed in 21.815 seconds. No local
  PostgreSQL, parser or browser runtime result is claimed.
- Local combined-candidate verification: 67 Python files compiled without
  bytecode writes; whitespace and CI data-path guard passed; 245 reference tests
  passed in 21.913 seconds; 15 source-integrity tests passed without skips.
- Whole-change self-review traced both transaction scopes, source/identity
  revalidation, exact-byte comparison, no-fallback behavior, preserved response
  headers and final-authority ordering. No separate reviewer tool is available;
  independent review remains pending, not silently claimed as complete.

- First combined runtime `f22b1a9bf5dd9d48c4de7fa163ec658069148fc2`:
  API run 41577320153 executed 228 tests; 227 passed and one failed only
  because the new helper expected the registry error for a missing authority
  provider. Actual HTTP was sanitized 503 `Access service unavailable`, the
  existing `authenticate_request` contract. All other new disclosure/lock/commit
  cases and all inherited tests passed. Subsequent workflow stages were skipped,
  so this run is not full backend acceptance.
- Correct only the test helper's exact expected detail for that provider case;
  retain strict 503, JSON shape, no-store, no receipt header, no sensitive content
  and unchanged database-event assertions. Keep registry-unavailable detail for
  construction/commit failures. No runtime change. The original red run remains
  valid: this provider case originally returned 200 before the status assertion.
- Web run 41577320172 at the first combined head passed 51 client tests,
  TypeScript/Vite and actual React/FastAPI/PostgreSQL browser journeys. Downloaded
  artifact 13204470641 has ZIP SHA-256
  `86a376b4b517b5883187a672c064e54868b0fc0871c6bc90f44349c0b0cbf1ed`;
  commit.txt and all 280 source files match the candidate. This is historical
  evidence; rerun both workflows on the test-corrected final head.
