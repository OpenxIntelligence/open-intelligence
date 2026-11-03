# H1 Archive and Follow-through Implementation Plan

> **For agentic workers:** Use the execution and independent review workflow;
> preserve the file ownership assignments below.

**Goal:** Retrieve exact archived originals within the combined image, question,
verification-return, task and citation workflow, including restored HTTP access.

**Architecture:** Retain #313 as the base and reuse #312's optional trusted archive
seam. Reconcile the richer recovery scenario without replacing canonical owners.

**Tech Stack:** Existing Python 3.12/FastAPI/PostgreSQL 16 and React/Vite/TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-03-h1-archive-followthrough-design.md`

## Global constraints

- Synthetic-only; no new dependency, migration, permission or public API field.
- Preserve `0011_image_evidence_merge`, citation timestamps and all source owners.
- Fail closed on archive, custody, authority, response or receipt failure.
- Exact-head hosted verification; draft PR only, no merge or deployment.

## Review focus

- A configured archive failure must not fall back to intact local content.
- A permission/source change during I/O or response preparation must withhold bytes.
- Amendment/relink and exact historical retries must not rewrite task/citation history.
- Citation metadata revocation must remain independent from image grants.
- Restored archive reads must not mutate the original or revoked-copy database.

## Task 1: Reuse archive behavior and prove combined continuity

Owner: primary agent. Modify `apps/api/src/oi_api/{app,patients,images}.py`.
Reuse donor tests `test_private_image_reads.py`,
`test_archive_disclosure_authority.py`,
`test_archive_question_review_integration.py`, and the fixture correction in
`test_image_preparation.py`. Add `test_archive_image_evidence_integration.py`.

Interface: optional `create_app(..., image_archive=reader)` reaches only original
image retrieval; `reader.read(study_uid, series_uid, sop_uid)` returns exact bytes.

- [x] Run bounded archive behavioral tests against the base and record the missing seam.
- [x] Port the runtime seam without replacing richer route registrations.
- [ ] Prove archived reads, no fallback, amendment/relink, immutable task/citation
  history, independent grants and revoked metadata with the populated HTTP case.
- [x] Run meaningful local regressions; distinguish unavailable PG tests.

## Task 2: Preserve combined restart/restore proof

Owner: recovery agent, only `apps/api/tools/verify_images_compose.py` and
`apps/api/tools/archive_acceptance_app.py`.

- [x] Preserve #313's entire local recovery flow and schema/history assertions.
- [x] Add explicit controlled archive activation, canonical invocation tracing,
  restored-only receipts and refusal cases around the richer task/citation history.
- [ ] Check syntax locally; execute the actual Compose gate in hosted CI.

## Task 3: Review, verify and record

Owner: primary agent, with an independent reviewer.

- [ ] Review diff against both exact owners; verify migration and dependency files
  remain unchanged and preserve all five recovery gates.
- [ ] Publish an isolated draft PR against #313 after local verification and review.
- [ ] Inspect exact-head API, PostgreSQL, browser and recovery job logs; resolve
  failures and rerun required gates before claiming success.
- [ ] Update existing roadmap, contracts and engineering progress with exact
  evidence, limitations and the next integration owner; verify readback.
