# Patient Continuity Convergence Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or subagent-driven-development to implement the bounded tasks. Keep actual results and rulings below; do not infer acceptance from donor branches.

**Goal:** Deliver one verified preparation workflow from Overview and an authored source-linked question through inspection, verification return, authorized brief and reassessment.

**Final architecture:** Adopt published #287 (`f7b0f683ab64ba2de7363744b65b8e26528f3138`) unchanged as the shared API/session foundation; reuse #286 Overview and extend the existing navigation and combined browser acceptance. The original #276/#286 convergence plan below is retained as execution history and is superseded where the live ownership ruling says so.

**Tech Stack:** Existing Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript.

**Spec:** `docs/superpowers/specs/2026-11-03-patient-continuity-convergence.md`

## Global Constraints

- Independently authored fictional records only; no real-person or patient-derived fixtures.
- No new dependency, permission, schema migration, clinical/evidence ledger, model execution or external notification.
- Keep source-only context, operational verification return and clinical approval distinct; clinical-approval flags remain false.
- Keep original migration files and dependency locks unchanged.
- Preserve exact patient/case/source/question identity, historical versions and independent grants.
- Work on an isolated branch; publish a draft PR with exact-head evidence; do not merge or deploy.

## Review Focus

- Response encoding after a transaction commits must not disclose source context under authority withdrawn during preparation.
- Import and metadata-refresh failures must not lose an uncertain return's exact retry identity.
- Cross-question selection and delayed responses must not combine one question's packet with another question's brief.
- Overview must preserve unknown/failed history and scope changes without reporting false completion or zero pending work.
- Amendment and application restart must preserve historical originals, question anchors and return IDs while refusing stale current disclosure.

### Task 1: Reconcile the existing owners

**Files:** overlapping API routes/contracts, shared `apps/web/src/registry-client.ts`, main/question/world-model views, inherited browser helper and existing engineering docs.

- [x] Import exact #286 history into an isolated #276 checkout and record conflicts.
- [x] Resolve each conflict by preserving both contracts; retain inherited tests and two real integration parents.
- [x] Run existing client tests/build and API discovery as available; distinguish actual local passes from missing-PostgreSQL skips.
- [x] Record donor equality for migrations, dependency locks and selectively copied artifacts.

### Task 2: Close the prepared-disclosure boundary

**Files:** `apps/api/src/oi_api/patients.py`; applicable #278 review-disclosure tests; new exact-source-packet disclosure regression file.

**Interfaces:** Existing GET source-review-packet, review inbox and return POST routes keep their OpenAPI models, fields, permissions and statuses. Their application-owned preparation callbacks construct validated JSONResponse bytes before final authority and commit.

- [x] Add/reuse actual HTTP/PostgreSQL tests that mutate required authority during real JSON encoding, inject encoder failure, inspect durable events and probe held locks/visibility from another connection.
- [x] Publish a tests-first checkpoint and observe meaningful hosted failures before the runtime repair; document any instrumentation correction.
- [x] Superseded by the live ownership ruling: adopt #287's complete API preparation correction/tests unchanged, with no second source reader.
- [ ] Run focused/complete available checks and obtain task review. Actual PostgreSQL acceptance remains a hosted gate if unavailable locally.

### Task 3: Verify combined patient continuity and exact recovery

**Files:** `apps/web/src/registry-client.ts`, applicable donor client regressions, `apps/web/tools/source_questions_journey.py`, connected client tests.

**Interfaces:** Existing RegistrySession, question/packet/brief/return contracts and Overview projection remain authoritative. No new persistence or transport adapter.

- [x] Reproduce same-case uncertain-return loss and preserve #278's exact intent/key recovery correction, including transient metadata failure and actual case denial.
- [ ] Exercise the combined client flow through authored question, packet, return, brief and Overview; retain cross-question stale-response assertions.
- [ ] Extend the actual database-backed browser journey through the same saved question, a real fresh download and amendment/reassessment with historical return/source preservation.
- [ ] Run the complete client suite and locked build; review the shared-session integration.

### Task 4: Review, publish and verify the final candidate

- [ ] Update existing status, backlog and relevant contracts with actual scope and source reuse.
- [ ] Obtain a fresh independent whole-branch review, resolve material findings and preserve test evidence.
- [ ] Publish draft with exact original parents and verify both final hosted H1 workflows on its head.
- [ ] Download the final artifact, verify checksum/commit/all archived source files, inspect relevant screenshots and actual downloaded brief bytes.
- [ ] Record final results and limitations in the PR receipt; leave draft and unmerged.

## Execution ledger

- 2026-11-03: Live audit found #276 already composes #265/#262/#264. #280 and #286 add authoring/inspection/Overview; their exact hosted runs pass. No published convergence with #276 exists at inspection. #278 owns later applicable review/response/recovery corrections.
- Ruling: integrate #276 and #286, selectively reuse #278 review corrections, and keep image migration separate — this connects the patient preparation path without importing unrelated schema convergence; later image integration remains a separately verified task.
- Ruling: use the standing continuation mandate for routine isolated implementation and draft publication — no new architecture, service or clinical function is selected, and main/owner branches remain untouched.
- Local source copies match #276's exact commit/tree and #286's exact commit/tree. Local-only fetching reported a shallow-root warning; the actual shared ancestor resolves to #264. Preserve the incoming published boundary rather than inventing history.
- The initial explicit merge retained both route/grant contracts, both UI panels and the shared session readers. All 133 existing client checks and 10 API contract checks passed; locked TypeScript/Vite build passed after the existing offline, omit-optional install.
- Reused #278's ten client recovery regressions. Before its correction, 140/143 checks passed and three failed: unknown or in-flight return intent became idle during same-case import, including temporary metadata failure. The exact donor session patch then passed all 143 checks.
- The combined browser fixture now authors the first question before its original download and return, then amends that source and preserves the original history. It adds a contextual-navigation clearing assertion and carries the third authored question through an additional return and actual fresh download. The old two-item review assertion is strengthened to the exact three known question IDs; source/version/line and independent-permission assertions remain.
- Added eight actual PostgreSQL disclosure methods: four selectively adapted from #278 and four for exact-source packets. Donor adaptations are the retained `0008_review_convergence` head and durable-state inspection before failure assertions. Local focused discovery imported all eight but skipped their PostgreSQL bodies. Runtime API preparation is intentionally unchanged for a hosted tests-first checkpoint.
- Published tests-first #288 head `61a4734138c6961e221a9a14b833a325c0c516c0`, tree `42ae4c2b53a8a9c8d2d3eacd9118e1ea5f609714`, with real parents #276 and #286. Full local API discovery ran 298 methods: 51 passed, 247 explicitly skipped for absent PostgreSQL.
- Actual browser run `41627928286` at that head passed all 143 client tests and the locked build, then failed the new contextual-navigation assertion: returning from Review through its own link retained the prepared source packet. Centralizing navigation clearing repairs that observed path without resetting authored draft or return intent.
- Ruling: #287 appeared after the audit and overlaps backend convergence — adopt its eventual published immutable implementation and narrow #288 to #286 Overview, contextual navigation and combined acceptance. Do not edit the other owner's working tree or implement a competing API repair. Earlier tests-first evidence stays historical; the final scope and exact parent will be recorded after the upstream head is published.

- Final owner adoption: published #287 `f7b0f683ab64ba2de7363744b65b8e26528f3138`, tree `a72d810aaf32a76f9c736aa1df4232e3bcd9ced0`, matches local immutable `bd9b563cfca3cfaca51a58adb75c9e79209a1b02`. Restored its API, session, tests and browser runner before reapplying only the Overview delta and navigation fix. Removed the overlapping added API test file and duplicate combined browser variant; their diagnostic history remains in the tests-first commit.
- Final scope check: API, migrations, source/domain code, inherited reference tests, workflows, locks, packet decoder, browser runner and shared project assessment are identical to #287. The session differs only by the Overview re-export. The three standalone Overview artifacts are identical to #286. See `docs/engineering/H1_PATIENT_CONTINUITY_SOURCE_REUSE.json`.
- Local final candidate: 178/178 client checks, locked TypeScript/Vite build, notice gate (18 installed, two optional uninspected, no errors), browser-script compilation and whitespace checks pass. API discovery runs 301 methods: 51 pass and 250 skip without local PostgreSQL. Hosted acceptance remains required.
- Focused review of the immutable navigation correction found no substantive defect: all section callbacks invalidate pending/prepared packet and brief views, without clearing authored drafts or uncertain return intent. The unchanged contextual-navigation red assertion remains in the adopted browser helper.
- The final combined acceptance extends #287's existing fourth-question helper through Overview resume and current/reassessment counts, then links its actual question, source, return and fresh download in one artifact. No parallel helper or backend implementation is retained.
- Publication and final verification receipt: complete fresh whole-delta review, publish with the current #288 head and actual #287 head as parents, run both hosted gates on the exact candidate, verify the downloaded archive and screenshots, and retarget the draft to #287. Record the final immutable receipt in the PR so a documentation-only receipt does not create an untested replacement head.
