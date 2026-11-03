# Complete Question Workflow Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the integrating implementation and a fresh whole-branch review. Steps use checkbox syntax for durable tracking.

**Goal:** Connect custom source-linked questions, exact-source inspection, operational verification returns and freshly authorized briefs in the existing H1 patient application.

**Architecture:** Preserve #276's canonical PostgreSQL/source/review owners, reconcile #280's question and packet consumers, and selectively reuse #278's review-response/retry corrections. All disclosure preparation stays within the existing owner transaction for the packet, queue, return and brief endpoints in scope.

**Tech Stack:** Existing locked Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-03-complete-question-workflow.md`.

## Global constraints

- Preserve independently authored fictional-data boundary; no live clinical data or external clinical action.
- Preserve all existing canonical owners, schema revisions, lockfiles and third-party notices.
- No Next.js; no separate clinical ledger, production-auth claim or automatic clinical approval.
- Main and donor branches remain unchanged; publish only a new draft integration candidate after concrete validation.
- Initial ten-file project assessment precedes significant product changes; later evidence records do not rewrite the initial baseline.

## Review focus

- Actual JSON serialization failure or revocation must not occur after a successful audit receipt commits.
- Same token changing actor/organization/purpose/exact-patient grants during encoding must be denied.
- Delayed packet/brief responses for another question must never restore mixed context.
- An uncertain committed return must remain recoverable with the same request after same-case amendment or temporary case metadata failure.
- Independent source-inspection/queue/return/export permissions and old anchors must remain separate after amendment/restart.

## Tasks

### 1. Assessment and baseline

- [x] Inspect main, active owners, Notion, Drive, schema, configuration, dependencies and CI; record conflicts and coverage limits.
- [x] Create an isolated checkout from #276 and run client/build/API discovery and existing dependency gates.
- [x] Finish all ten requested assessment files with source links and explicit statuses before product implementation.

### 2. Reconcile existing question and review consumers

Files: `apps/api/src/oi_api/{access,contracts,patients}.py`, new donor `question_source_review_packet.py`; `apps/web/src/{registry-client,source-question-panel,source-quote-review-packet,main,world-model-view,styles}`; donor tests and `apps/web/tools/source_questions_journey.py`.

Interfaces: retain `RegistrySession`'s canonical source/question/brief/review state; add the donor's exact-packet decode/read methods and custom question draft methods. Reuse `PostgresQuestionSourcePacket.read(..., prepare_response, recheck_authority)` and all existing route operation IDs.

- [x] Import donor tests first; run the unchanged baseline client suite to observe missing authoring/packet behavior.
- [x] Apply #280's changes relative to #264 using three-way reconciliation; preserve #276's independent review/intake changes.
- [x] Import #278's byte-verified review disclosure tests and client exact-retry regressions; observe local client failures before applying those repairs.
- [x] Reconcile only #278's review JSONResponse and client recovery changes, with no images or migrations.
- [x] Run full client tests, TypeScript build, non-DB API checks and migration/owner preservation checks.

### 3. Govern actual source-packet response preparation

Files: packet route in `apps/api/src/oi_api/patients.py`; new `apps/api/tests/test_question_packet_disclosure_authority.py`; connected API/browser acceptance.

Interface: callback returns an already serialized `JSONResponse` from the same existing `PostgresQuestionSourcePacket.read` transaction; OpenAPI retains `QuestionSourceReviewPacket` schema. No new persistence.

- [x] Add actual PostgreSQL/HTTP tests for actual encoding, final grant withdrawal/identity change, encoder failure, held locks and failed audit/commit; unchanged donor must fail materially under hosted verification.
- [x] Add cross-owner lifecycle acceptance for a custom question, exact packet, return history, authorized brief, amendment and explicit retry; preserve all donor browser assertions.
- [x] Construct packet JSON inside `prepare_response`, before the owner refresh/audit/commit; retain headers and status.
- [x] Run full existing API/PostgreSQL and built-React/browser hosted gates on the exact candidate, with no DB skips counted as passes.

### 4. Review, evidence and durable handoff

- [x] Fresh whole-branch review of code, scope, donor preservation and failure-mode tests.
- [x] Correct material findings, verify relevant regressions, record any limitations/rulings.
- [x] Update existing owner contracts/backlog with actual evidence, source-reuse manifest and final verification receipt; preserve the initial assessment as initial state.
- [x] Publish/verify draft PR and record exact commit, executed gates, remaining platform gaps and next owner integration. Do not merge, deploy or send external messages.

## Completion receipt

[Draft PR #287](https://github.com/OpenxIntelligence/open-intelligence/pull/287), verified runtime commit `f7b0f683ab64ba2de7363744b65b8e26528f3138`, tree `a72d810aaf32a76f9c736aa1df4232e3bcd9ced0`: both hosted gates passed, including 301 actual API/PostgreSQL executions, 245 reference executions, 170 client tests, real browser journeys, and patient/source/review restart/restore probes. Independent review findings are resolved. [Complete evidence, source reuse and limitations](../../project-state/IMPLEMENTATION_EVIDENCE.md). Subsequent evidence-only documentation records these completed results; any later runtime change needs fresh acceptance.

## Initial execution ledger

- Baseline: 106 client tests passed; TypeScript/Vite build passed; API 246 executions, 51 passed/195 skipped without PG. Dependency gates: backend 24 packages, frontend 18 installed/2 optional uninspected.
- Ruling: PostgreSQL binaries exist but the executor maps only UID0 and cannot create a supported unprivileged server process. Respect runtime restrictions and use the existing hosted disposable PostgreSQL gates. Local skipped tests are not acceptance.
- Ruling: #278's queue/return serialization and exact-return recovery repairs are part of this connected workflow's preservation, not an image integration. The four relevant local donor blobs were verified against the remote #278 head before reuse.
- Pre-flight: #280 and #276 share `patients.py`, `registry-client.ts`, contracts and browser lifecycle. Preserve the union of independent permissions, handlers and state invalidation; do not replace whole shared files with a donor copy.
