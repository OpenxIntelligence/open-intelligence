# H1 reviewed documents implementation plan

> Execute with superpowers:executing-plans; one final independent review.

**Goal:** Actual scoped preview, original custody, immutable passage correction and Records UI.
**Architecture:** Reuse canonical source_versions plus immutable source-owned children.
**Tech Stack:** Existing FastAPI/PG16/React/Vite; inherited hash-pinned pypdf 6.21.4.
**Spec:** ../specs/2026-11-03-h1-reviewed-documents.md

## Global constraints
Fictional only; 64 KiB/20 pages/512 lines/30 selections; no OCR/model/clinical
claims. Preserve existing source snapshots and source-authored semantics.

## Tasks
- [x] Port exact source validators/worker and PDF fixtures; add strict H1 document
  command contracts and tests. Run focused unit discovery: observe missing
  contract failures, implement and pass exact bytes/hash/shape cases.
- [x] Add 0012_reviewed_documents, immutable intake/rendition/revision children;
  implement source-owned preview/import/read/correction and explicit schema head.
  Test actual HTTP/PG no-write preview, raw original fidelity, exact retries,
  stale corrections, amendments/history, cross-case denial, final authority and
  encoding rollback. Retain all prior suites and populated migration evidence.
- [x] Mount scoped document routes with bounded ingress and independent original
  grant. Add Records document client/view, explicit file preview/save/correction,
  exact uncertain retry and context invalidation. Run client tests/build.
- [ ] Extend actual browser and recovery acceptance; publish draft and require
  exact-head hosted suites, inspect artifacts and independent whole-change review.

## Review focus
Historical retry must not rewrite earlier selection state. Filename must not
become a path/header injection. Mixed-format amendment must fail. Parser execution
must precede locks but follow authorization. Revoked or late responses must not
repopulate a different patient context. Manual findings must never masquerade as
source-authored statements. Documentation records each stage's actual scope.
