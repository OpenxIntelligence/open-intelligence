# H1 original disclosure implementation plan

**Goal:** Keep actual original-response preparation inside the existing final-authority transaction.
**Architecture:** Reuse source owner locks, prepared-response callbacks and source.original_read_authorized.
**Stack:** Unchanged H1 FastAPI/PostgreSQL/React locks.
**Spec:** ../specs/2026-11-03-h1-original-response-authority.md

- [x] Trace original route and compare index/brief/intake response boundaries.
- [x] Add real HTTP/PostgreSQL tests for late encoding revocation, encoding failure,
  DTO failure, held patient/binding locks, exact historical/current bytes and receipts.
- [ ] Publish tests-only checkpoint and observe expected hosted failures.
- [ ] Add optional prepare_response to sources.original; prepare ID/body before _read_receipt.
- [ ] Construct the complete OriginalSource JSONResponse in the existing route callback.
- [ ] Run focused and complete hosted gates, independent review and artifact inspection.

Review focus: no post-commit DTO/encoding; same bearer/actor/org/purpose; current
and historical source reads; no original/credential leakage on errors; direct
callers retain dict compatibility. Only independently authored fictional fixtures.
