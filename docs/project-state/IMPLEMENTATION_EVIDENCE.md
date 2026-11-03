# Connected question workflow — implementation and evidence

Date: 3 November 2026. Candidate: [draft PR #287](https://github.com/OpenxIntelligence/open-intelligence/pull/287), stacked on #276. The ten assessment files describe the state before this implementation. This record describes the subsequent bounded change; current exact-head hosted conclusions belong in the PR's verification receipt.

## Verified implementation checkpoint

The complete runtime implementation is verified at remote commit [`f7b0f683ab64ba2de7363744b65b8e26528f3138`](https://github.com/OpenxIntelligence/open-intelligence/commit/f7b0f683ab64ba2de7363744b65b8e26528f3138), tree `a72d810aaf32a76f9c736aa1df4232e3bcd9ced0`. That tree exactly matches independently reviewed local commit `bd9b563cfca3cfaca51a58adb75c9e79209a1b02`. This evidence-only follow-up records completed results without changing the runtime, tests, dependencies or workflows.

| Gate | Observed result | Evidence |
| --- | --- | --- |
| API/PostgreSQL suite | **301 executions passed; zero failures/errors/skips.** Includes actual JSON-encoding authority, locks, audit/commit rollback, migrations, questions and returns. | [API run 41629005788](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41629005788), verified proposed checkout SHA. |
| Historical reference suite | **245 executions passed.** | Same API run; original behavior preserved. |
| Historical browser acceptance | Passed source comparison, review attention, keyboard/AX landmarks, case changes, amendment, export, fictional evidence/reference flows and narrow viewport. | Same API run; these reference capabilities do not imply H1 evidence integration. |
| Patient recovery probe | Passed scoped HTTP, cross-tenant denial, API/DB restart, dump/restore and next-request revocation. | Same API run. |
| Original-source recovery probe | Passed exact UTF-8 originals, amendment history, fresh authority, durable receipts, binding revocation and dump/restore. | Same API run. |
| Canonical review recovery probe | Passed stable provenance, same-key recovery, amendment history, independent grants, API/DB restart, binding revocation and dump/restore. | Same API run. |
| Client/build | **170 client tests passed; zero failures/skips.** TypeScript and Vite production build passed. | [Web run 41629005777](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41629005777). |
| Built React/API/PostgreSQL browser | Passed all donor flows and the added fourth-question quotation → verification return → revisit → fresh actual download journey. | Same web run; actual Chromium and disposable PostgreSQL 16. |
| Dependency gates | Existing backend 24-wheel/99-native/13-runtime-entry gate and web 18-installed-package gate passed; omitted optional packages retain their uninspected classification. | Both hosted runs; unchanged scoped development determinations. |
| Independent review | All three Important client findings and the Minor decoder finding resolved; no remaining Critical/Important blocker for this scoped fictional-data integration. Reviewer independently reran all 170 client tests and TypeScript. | Frozen repair tree above; retained limits below. |

The web evidence artifact is [`13227850139`](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41629005777/artifacts/13227850139), SHA-256 `3e99297c9e2e5281a733e3df235089966d358118228d9f7c69d326c34fb2d2fe`. Its `commit.txt` matches the verified remote head, and all **321** source files in its source archive were byte-compared with the local reviewed tree. The quotation, review-history and mobile brief screenshots were visually inspected. Artifact retention is seven days; commit, source, evidence summary and run links remain the durable trace.

Status: **fully implemented and tested for this bounded fictional-data contract; draft, unmerged and undeployed.** It is not completion of OI-008, the full clinical platform, production identity, WCAG qualification or clinical evaluation. Any later code change needs its own acceptance; documentation-only updates are distinguishable from the verified implementation checkpoint.

## Patient-facing behavior

One existing H1 patient/case workspace connects:

1. A literal user-authored question anchored to a current source version and line.
2. The canonical preflight and immutable saved question.
3. Separately authorized inspection of the original quotation, version, line and source digest.
4. An explicit nonterminal verification return with a reason and durable history.
5. A newly authorized source brief and actual text download for that same question.
6. Historical source/question preservation and deliberate reassessment after amendment.

The source packet and brief remain projections over the existing patient, case, source and question owners. A verification return records an operational request for independent verification; it does not establish professional review, clinical approval, external notification or a biomedical answer. Source inspection, queue reading, returning and exporting retain independent grants.

## Source-reuse manifest

| Source | Frozen identity | Reuse and reconciliation |
| --- | --- | --- |
| #276 integration base | `c154bfbc5f99f76801d37903959943659c0b6a71` | Preserve final intake/received-pointer authority, canonical review-return owner and source-linked brief. |
| #280 authored-question/packet donor | `e8d851e5c7769c31f429a3d1649c26402aa9de12` | Apply changes relative to parent #264 `e042f753eca85cca97e08fdbb3e07ea8263aae69`; reconcile shared API contracts, routes, client state and navigation rather than replacing whole shared files. |
| #278 selective repair donor | `b72560ac0f5e5005040b0fc660ce1650343611cf` | Reuse only review queue/return JSON preparation and uncertain-return recovery across same-case imports or transient case-metadata failure. No image or migration scope imported. |
| New packet authority acceptance | This candidate | Seven real PostgreSQL/HTTP methods observe both framework JSON encoding paths after actual bytes exist; test independent grants, identity/scope/expiry, failures, locks, rollback and restart. |
| New connected browser acceptance | This candidate | A fourth authored question is carried through exact source inspection, a durable return, re-reading and a fresh actual download. All existing donor checks remain. |

Four local donor blobs were independently matched to #278's hosted head before selective reuse: `patients.py` = `09f7411aea9f2f4ef3555c8697c58a387ec3597e`; `registry-client.ts` = `b0aaefcb0c68588a9e0a904f74a77e2ed92da5a0`; `review-client.test.mjs` = `dc19491d40deb7fab9be8e64d4dd29865f59fe29`; `test_review_disclosure_authority.py` = `f7383934d9d61cd56145fd5b3aa3ac138c62aae1`.

The imported review authority test's schema expectation is intentionally adapted from the image donor's `0009_image_review_merge` to this candidate's actual `0008_review_convergence`. This is a fixture adaptation, not a migration or a product fix. Its four methods require actual PostgreSQL acceptance in this combined branch.

## Observed failures before repair

### Client behavior

The baseline passed 106 client tests. Importing the donor authoring/packet and recovery tests first produced 22 failures in 135 executions. After reconciling #280, three failures remained: uncertain/saving return information was lost during same-case source import or a temporary case-metadata failure. Reusing the existing review owner's recovery changes brought all 135 tests to passing before publication of the first checkpoint.

### Actual PostgreSQL and JSON encoding

[Initial hosted API run 41626889941](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41626889941) verified checkout `878a03cb5ed27cbdde329d5aef0c28875d09c5a8` and ran 301 executions against PostgreSQL 16. It reported 17 failed assertions/subtests, with no skipped database cases:

- Thirteen packet assertions/subtests reproduced the actual encoding boundary. Encoding-time permission/identity/scope changes still returned HTTP 200; an encoder exception returned an unhandled HTTP 500; a successful access event was visible before JSON encoding finished; audit/commit failures occurred before the expected actual encoder observation.
- Four imported review methods stopped in setup because of the donor's image-specific migration-head assertion. Those four failures are **not** proof of a reproduced review authorization defect in this branch.

The packet fix constructs the complete `JSONResponse` inside `PostgresQuestionSourcePacket.read`'s existing preparation callback. The selected review owner repair does the same for queue and return responses. Typed validation, actual byte encoding, final refreshed request authority, audit/event append and commit now remain ordered inside the same existing transaction. New returns retain HTTP 201; exact duplicate recovery retains HTTP 200. OpenAPI response models remain available.

The source-linked brief already used governed JSON preparation and retains its existing behavior. This slice does not claim a global fix for other source/question/preflight DTO response boundaries.

### Actual built-browser integration

[Initial hosted web run 41626889989](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41626889989) passed client/build/dependency gates and the donor's actual source, authored-question, exact-packet and fresh-download journeys. It then failed an older review-harness assumption that the queue contained exactly two questions. The merged authoring journey creates three.

The corrected harness derives the exact persisted IDs from passively observed real brief responses, checks equality with the complete three-ID review queue, and selects the exact default-v2 question. It separately proves that returning that question leaves the authored question unreturned. The fourth-question connected acceptance runs only after all three-question checks finish. No backend response is fabricated by this helper.

### Independent code review

A fresh reviewer inspected the complete source change from #276 through local `050860c25406e1bb20ce1f1efa72f0ded3a4a7e3`. No critical issue or scoped backend transaction regression was found. Three important client behaviors were reproduced and accepted for repair:

- Refreshing the review inbox after temporary case/source metadata failure discarded the earlier return's captured key/reason, even though that user action remained available.
- Starting, resuming, editing or preparing another question draft could retain an earlier saved question's packet or permit its delayed response to return beside the new question context.
- Inherited brief/preflight failure resets discarded an uncertain return after same-case amendment conflicts or temporary failures. This was accepted into the current scope because it breaks continuity across the connected workflow.

The minor decoder finding was also accepted: a malformed packet with matching hashes could label a legacy fingerprint contract current. A new regression first failed with a missing expected rejection; the decoder now requires the canonical contract for a current quotation while retaining legacy anchors as history.

Review resolution and final executed counts belong in the exact-head PR receipt. These findings do not justify relaxing the independent permission, literal provenance or rollback assertions.

The client repairs were tested before implementation: the first fresh run had 156 executions, 140 passed and 16 failed on inbox/draft context; the additional brief/preflight run had 170 executions, 162 passed and eight failed. After the corrections, all 170 client tests and the production TypeScript/Vite build passed. The fixes preserve the original intent without authorizing a read when case metadata is absent, invalidate both saved-question readers on draft changes, and retain minimal same-case return recovery while clearing failed source previews. Authentication/authorization denial and patient/case/credential changes still discard recovery. Focused independent repair review and actual hosted acceptance subsequently passed at the verified checkpoint above.

### Explicit remaining review boundaries

An explicit patient reopen/read, page reload or credential replacement still resets in-memory recovery, even when the reopened patient ID is the same. Retention across those boundaries requires a separate, deliberately scoped recovery design. Unknown question-creation intent can still be cleared by world/case refresh or import; the current preservation repair targets verification returns. Immediate unchanged question-save retry remains covered, but broader question-create recovery is incomplete.

Other inherited DTO response routes remain separate final-encoding debt. Historical packet mode intentionally withholds the old quotation while preserving its anchor; access to historical original bytes requires its own grant. Same-question packet and brief may coexist, and denial of one independent action does not confer or automatically revoke another. Content hashes are change detectors, not signatures. An authorized preparation receipt does not prove client delivery or make the external fixture authority a distributed revocation transaction.

The donor packet test module retains imported/inherited test-bearing classes. Report suite totals as **executions**, not unique scenarios. Initial assessment snapshots and subsequent implementation evidence remain separate.

## Preservation and verification contract

- No new dependency, lockfile, notice, workflow or migration is required. Existing `0008_review_convergence` and all parent histories remain unchanged.
- Existing canonical patient, source, question, review-return and event storage code is preserved. The packet creates no table or alternate chart.
- The complete client suite and production TypeScript/Vite build must pass on the combined source.
- The existing API workflow must execute actual PostgreSQL tests, historical reference tests/browser journeys and patient/source/review recovery probes. Local database skips are never counted as acceptance.
- The built-React workflow must execute real API/PostgreSQL/Chromium journeys, literal downloads, permission denials, amendments and exact-question continuity.
- A fresh independent whole-branch review evaluates the combined change. Material findings must be resolved or explicitly retained as limitations before the final receipt.

The local executor has no supported unprivileged PostgreSQL process configuration. It can run non-database contracts, client tests, builds and reference regressions. Hosted disposable PostgreSQL is therefore required for the database and browser conclusions.

After the JSON/browsing changes at local code commit `050860c25406e1bb20ce1f1efa72f0ded3a4a7e3`, local verification passed 135 client tests, the TypeScript/Vite build, all 245 historical reference tests and the current-workflow data-boundary scanner. API discovery ran 301 executions: 51 passed and 250 database cases were explicitly skipped. Protected migrations, locks, dependency declarations, workflows and canonical source/question/review storage paths matched #276. Subsequent review repairs require their own updated verification receipt.

Exact commit/tree identifiers, run links, execution totals, review resolution and remaining limits are maintained in [PR #287](https://github.com/OpenxIntelligence/open-intelligence/pull/287). A passing parent or an earlier failed checkpoint cannot establish acceptance of a later combined head.

## Product status after this bounded implementation

This change advances OI-006/007/009/010/013 only within the described fictional source/question workflow. OI-008's scientific evidence investigation is still incomplete. It does not connect the separate reference evidence/report persistence, ordinary PDF correction history, imaging owner or patient overview merely by referring to those drafts.

Production identity and delegation, clinical consent and professional review, real provider connections, qualified evidence rights, broad document ingestion, operational clinical domains, accessibility qualification and clinical evaluation remain in [INCOMPLETE_FEATURES.md](INCOMPLETE_FEATURES.md) and [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md). The next convergence should port existing evidence/report owners through an explicit canonical H1 adapter, preserving source and question identity.
