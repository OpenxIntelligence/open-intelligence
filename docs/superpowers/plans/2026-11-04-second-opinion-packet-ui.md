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
- [x] Preserve the existing browser journeys; run pinned hosted client/build/rights/real PostgreSQL/Chromium acceptance on the new exact head.
- [x] Inspect the diff, downloaded artifact, source identities and desktop/mobile captures; distinguish self-review from independent review.
- [ ] Independent owner review and final integration approval remain open. No merge or deployment.

## Historical local evidence
- Base artifact independently downloaded: 5,628,780 bytes; SHA-256 `0001aa9c6a0f5c64f0e7c5a0c909d97ee5dd9a299ec637afea2d6db083266a19`; commit marker matches frozen base.
- Local baseline uses available TypeScript 5.8.3, not the pinned hosted version. `npm test`: 393 passes; three test-file processes cannot import the absent React/Vite dependencies. No PostgreSQL server is available locally. Hosted base workflows succeeded; those results do not qualify the new UI.
- Task 1: complete locally. Initial 22 missing-feature failures were observed before implementation. Three later scope/recovery regressions and four refused-retry cases were reproduced and repaired. Final focused suite: 32/32 passed, zero skips.
- Available full client run: 425 passed; four test-file processes failed because React/Vite are absent, including the three inherited baseline processes. This is not a passing full-suite claim. Actual installed-package audit and production build required hosted dependencies.
- 13 filesystem-rights unit controls, inherited synthetic-boundary audit, browser helper compilation and whitespace checks passed locally. Local TypeScript is 5.8.3; the successful hosted build uses the existing pinned toolchain.
- Ruling: keep the new packet controls over #447, not the separate #449 document/image agenda; avoid a second packet owner or an unverified branch merge.
- Ruling: four inherited 401-only branches spell the equivalent argument as literal 401; this does not change their conditions or authorization behavior. All published runtime/test source blobs matched the local tested tree before publication.

## Verified implementation/test checkpoint — draft PR #479

Verified head: `678f9e0fc3948462242253e91cf2639d607ab2fe`.
Verified tree: `0d013eb332f8a6eaa4b104adbfa75f369207c279`.
[Hosted run 41931036557](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41931036557), job `126927672373`, completed successfully on this exact head.

- **448 client tests passed**, zero failures, skips or cancellations, including 32 new packet session regressions and three new rendered-component tests.
- **13 filesystem-rights tests passed**. Actual installed inventory: 18 packages inspected, two omitted optional packages explicitly uninspected, zero gate errors. Stored npm audit: zero reported vulnerabilities.
- TypeScript/Vite production build, inherited synthetic-data boundary and backend wheel/dependency gate passed.
- The actual PostgreSQL 16/FastAPI/built React/Chromium journey passed all inherited flows and the new packet scenario. This is not a fresh standalone full API or backup/restore suite for this UI-only change.

### Patient journey observed
The UI started with no records or questions selected. Typing and Records/Overview navigation issued no packet write. Explicit selection and confirmation saved one packet. The browser then deliberately lost the real successful HTTP response after the database committed; recovery sent the same exact command and key, returning HTTP 200 with the identical packet ID instead of creating a second packet. Fresh GET returned one stored packet with the original SHA-256.

Withdrawing only packet-read permission cleared saved packet details while separately authorized questions remained. An explicit source amendment retained the original selected source ID, version 1, hash, question and line 8; the packet became `source_reassessment_required`. A delayed authorized read from the earlier case could not restore its packet after navigation. Desktop 1440px and mobile 390px containment passed. Browser storage stayed empty. External-request and clinical-approval fields remained false.

### Artifact and visual inspection
[Artifact 13371592783](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41931036557/artifacts/13371592783): 5,858,895 bytes; independently recomputed SHA-256 `c5fc077ec0d74d1436bcc85cf322c4f4b4494b0221b49a31a8f42cb08119c02f`. Its commit marker matches the verified head. All **444 source blob contents** match the local tested index; the local full tree hash matches the remote Git tree, covering paths and modes. The archive itself does not supply Unix modes, so no ZIP-mode claim is made. Retention ends 11 November 2026.

Read back client/build/rights/browser logs and `second-opinion-packet-receipts.json`. Inspected the 1440px and 390px screenshots for visible layout and wrapping; this is not an all-screen, screen-reader or accessibility-conformance audit. Minor copy polish remains: the saved-packet disclosure uses plural labels even at a count of one. No blocking layout failure was observed in these captures.

### First hosted failure and bounded repair
[Run 41930009050](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41930009050) on `6832bc5a72d3aa8c9cf5eb90b0cf12bbe69212f1` passed all 448 client tests, build and dependency gates. The browser reached actual packet save/recovery, reopen and independent read denial, then correctly received HTTP 409 because the new synthetic amendment omitted `Amends: PACKET-DOC@1`. The repair added that exact lineage to the fixture; application permission and amendment guards were not changed. The complete repaired journey passed on the checkpoint above.

Self-review and artifact inspection are complete; independent owner review is not claimed and remains open. This documentation-only receipt changes no runtime, tests, dependencies or workflow. The product remains synthetic-only, draft, unmerged and undeployed, with no recipient verification, record-completeness proof, clinical sign-off, external transmission or completed referral. Notion and Drive should mirror this bounded receipt, not describe the whole platform as complete.
