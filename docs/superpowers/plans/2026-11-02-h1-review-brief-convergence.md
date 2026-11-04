# H1 review and brief convergence implementation plan

> Execute natively using superpowers:executing-plans; preserve original owner commits.

**Goal:** One canonical source/question workflow with independent operational returns and authorized source-only briefs.
**Architecture:** Compose existing owners; reconcile shared transport/state contracts without a new ledger.
**Tech Stack:** Existing FastAPI, PostgreSQL 16, React, Vite and TypeScript locks.
**Spec:** ../specs/2026-11-02-h1-review-brief-convergence.md

## Global constraints
Fictional inputs only. No new dependencies, clinical authority, merges into shared
branches or deployment. Preserve original migration bytes and both upstream tests.

## Review focus
- Mixed permission sets must not grant export through review authority.
- Read receipts must not invalidate content or bind an old question to a new source.
- Same-case source refresh must cancel brief work and preserve uncertain exact return intent.
- Historical return retries after amendment must not authorize stale brief generation.
- Browser helpers must exercise all existing assertions together, without weakening them.

## Tasks and execution ledger
- [x] Inspect current PR ownership, repository instructions and preserved contracts.
- [x] Merge #262 onto #265 in an isolated checkout; preserve actual parent history.
- [x] Compose #264; reconcile permissions/capabilities, full route/DTO blocks,
  bounded ingress, client reset counters, styles, docs and backlog rows.
- [x] Preserve #262 project_locked and #264 brief preparation; remove the invalid
  auto-merged references to rows/world in the list callback.
- [x] Run client suite and production build: 106 client checks pass; TypeScript/Vite pass.
- [x] Add cross-owner real HTTP acceptance in test_review_brief_convergence.py:
  same question return/export, amendment/restart/history and independent grants.
- [ ] Run combined PostgreSQL and browser acceptance on the published candidate.
- [ ] Review resolved diff, document exact results and remaining migration boundary.

Local API discovery before the new cross-owner tests: 244 executions, 51 passed,
193 skipped for unavailable PostgreSQL. Local PG startup failed because this
executor maps only UID 0; chown to the database user returned EINVAL. An earlier
server on localhost was unavailable. No skipped case is a database pass.

This is composition of existing implementations and tests, not new tests-first
implementation of their behavior. New cross-owner tests are acceptance checks;
any newly exposed defect must be reproduced before a focused repair.
