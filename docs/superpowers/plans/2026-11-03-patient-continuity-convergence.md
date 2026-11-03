# Patient Continuity Convergence Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or subagent-driven-development to implement the bounded tasks. Keep actual results and rulings below; do not infer acceptance from donor branches.

**Goal:** Deliver one verified preparation workflow from Overview and an authored source-linked question through inspection, verification return, authorized brief and reassessment.

**Architecture:** Merge #286 into the verified #276 foundation, retaining their canonical owners. Selectively preserve #278's applicable review-response/recovery corrections and close the inherited packet response-encoding gap inside the existing source transaction.

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

- [ ] Import exact #286 history into an isolated #276 checkout and record conflicts.
- [ ] Resolve each conflict by preserving both contracts; retain inherited tests and two real integration parents.
- [ ] Run existing client tests/build and API discovery as available; distinguish actual local passes from missing-PostgreSQL skips.
- [ ] Record donor equality for migrations, dependency locks and selectively copied artifacts.

### Task 2: Close the prepared-disclosure boundary

**Files:** `apps/api/src/oi_api/patients.py`; applicable #278 review-disclosure tests; new exact-source-packet disclosure regression file.

**Interfaces:** Existing GET source-review-packet, review inbox and return POST routes keep their OpenAPI models, fields, permissions and statuses. Their application-owned preparation callbacks construct validated JSONResponse bytes before final authority and commit.

- [ ] Add/reuse actual HTTP/PostgreSQL tests that mutate required authority during real JSON encoding, inject encoder failure, inspect durable events and probe held locks/visibility from another connection.
- [ ] Publish a tests-first checkpoint and observe meaningful hosted failures before the runtime repair; document any instrumentation correction.
- [ ] Preserve #278's review preparation correction and apply the same existing pattern to the packet route without introducing another source reader.
- [ ] Run focused/complete available checks and obtain task review. Actual PostgreSQL acceptance remains a hosted gate if unavailable locally.

### Task 3: Verify combined patient continuity and exact recovery

**Files:** `apps/web/src/registry-client.ts`, applicable donor client regressions, `apps/web/tools/source_questions_journey.py`, connected client tests.

**Interfaces:** Existing RegistrySession, question/packet/brief/return contracts and Overview projection remain authoritative. No new persistence or transport adapter.

- [ ] Reproduce same-case uncertain-return loss and preserve #278's exact intent/key recovery correction, including transient metadata failure and actual case denial.
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
