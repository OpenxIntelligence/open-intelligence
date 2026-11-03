# H1 original disclosure implementation plan

**Goal:** Keep actual original-response preparation inside the existing final-authority transaction.
**Architecture:** Reuse source owner locks, prepared-response callbacks and source.original_read_authorized.
**Stack:** Unchanged H1 FastAPI/PostgreSQL/React locks.
**Spec:** ../specs/2026-11-03-h1-original-response-authority.md

- [x] Trace original route and compare index/brief/intake response boundaries.
- [x] Add real HTTP/PostgreSQL tests for late encoding revocation, encoding failure,
  DTO failure, held patient/binding locks, exact historical/current bytes and receipts.
- [x] Publish tests-only checkpoint and observe expected hosted failures.
- [x] Add optional prepare_response to sources.original; prepare ID/body before _read_receipt.
- [x] Construct the complete OriginalSource JSONResponse in the existing route callback.
- [ ] Run focused and complete hosted gates, independent review and artifact inspection.

Review focus: no post-commit DTO/encoding; same bearer/actor/org/purpose; current
and historical source reads; no original/credential leakage on errors; direct
callers retain dict compatibility. Only independently authored fictional fixtures.

Tests-only checkpoint: 4be6b896c17939fcffde6789d298d69f00f47d13,
hosted API run 41653615731, job 125977976834. All four new tests reproduced
the defects (18 failed subtests across current/historical originals); the suite
ran 351 tests. Late revocation returned 200; encoding failures returned an
unhandled 500; locks had been released; DTO failures left read receipts.
Local discovery ran 351 tests with 287 explicit PostgreSQL skips, so it is
not database acceptance evidence. Final hosted results and independent review
will be recorded on draft PR #304 against the exact published fix head.
