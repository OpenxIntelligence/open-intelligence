# Durable second-opinion packet controls — implementation plan

> For agentic workers: execute inline with superpowers:executing-plans and test-driven-development.

**Goal:** Let an authorized synthetic patient explicitly select sources and saved questions, save one durable preparation packet through #447, and reopen its current or reassessment state.

**Architecture:** Extend the existing RegistrySession through a focused packet-session helper, using its credential transport, cancellation and scope. The PostgreSQL owner and routes in #447 remain unchanged. No recipient, transmission, referral or new clinical authority.

**Tech Stack:** Existing React/Vite/TypeScript and FastAPI/PostgreSQL; no new dependencies.

**Spec:** `docs/superpowers/plans/2026-11-04-second-opinion-packet.md` and the existing #391 preparation contract.

## Global constraints
- Frozen base: #447 `165f5c28a2fcf5550020e3657d9882096d0decf7`.
- Exact selected source versions, current question snapshot and explicit synthetic confirmation; no preselected material or automatic save.
- Memory-only selection and exact uncertain intent; fresh grants on every server request.
- Separate unchecked, loading, denied, verified-empty and historical states. Never label a saved packet as a sent request.
- Server bounds: 100 packets, 32 sources, 16 questions; 4 MiB list response.

## Review focus
Wrong patient/case and delayed A/B/A reads; denied independent packet access; committed response lost or receipt/HTTP contradiction; stale source or question between selection and save; malformed provenance, invalid timestamps or falsely true clinical/external flags.

## Task 1 — session and wire contracts
- [x] Add failing tests for strict packet decoding, explicit selection, exact retry and current-scope clearing using the real RegistrySession and protocol fixtures.
- [x] Implement `second-opinion-packets.ts` and `second-opinion-packet-session.ts`; wire their state/transport/reset into `registry-client.ts` without changing existing owners.
- [x] Run focused tests and the complete available client suite. Record local missing React/Vite packages separately from behavioral failures.

## Task 2 — connected preparation controls
- [x] Add rendered tests and actual-browser assertions for selection → persisted packet → reopen → amendment/revocation. Their execution requires hosted React/Vite and PostgreSQL; no local rendered-test RED result is claimed.
- [x] Add a semantic packet panel within existing Overview, with retained in-memory selections, explicit save/unknown recovery and authorized packet history.
- [ ] Preserve the existing browser journeys; run pinned hosted client/build/rights/real PostgreSQL/Chromium acceptance on the new exact head.
- [ ] Inspect the diff and artifact evidence; report self-review versus independent review honestly. Update existing Notion/Drive records with actual results and limits. No merge or deployment.

## Evidence ledger
- Base artifact independently downloaded: 5,628,780 bytes; SHA-256 `0001aa9c6a0f5c64f0e7c5a0c909d97ee5dd9a299ec637afea2d6db083266a19`; commit marker matches frozen base.
- Local baseline uses available TypeScript 5.8.3, not the pinned hosted version. `npm test`: 393 passes; three test-file processes cannot import the absent React/Vite dependencies. No PostgreSQL server is available locally. Hosted base workflows succeeded; those results do not qualify the new UI.

- Task 1: complete locally. Initial 22 missing-feature failures were observed before implementation. Three later scope/recovery regressions and four refused-retry cases were reproduced and repaired. Final focused suite: 32/32 passed, zero skips.
- Available full client run: 425 passed; four test-file processes failed because React/Vite are absent, including the three inherited baseline processes. This is not a passing full-suite claim. Actual installed-package audit and production build require hosted dependencies.
- 13 filesystem-rights unit controls, inherited synthetic-boundary audit, browser helper compilation and whitespace checks passed locally. TypeScript is the available 5.8.3; hosted pinned 5.9.3 remains required.
- Ruling: keep the new packet controls over #447, not the separate #449 document/image agenda; avoid a second packet owner or an unverified branch merge.
- Ruling: four inherited 401-only branches spell the equivalent argument as literal 401; this does not change their conditions or authorization behavior. All published runtime/test source blobs matched the local tested tree before publication.
- Hosted exact-head client/build/browser acceptance, screenshot inspection and independent review remain pending at this publication checkpoint. Self-review is not independent review.
