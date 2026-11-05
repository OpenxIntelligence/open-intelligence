# H1 Question Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect case-owned fictional evidence, human-authored comparisons and immutable reports to existing canonical H1 source questions.

**Architecture:** Compose a PostgreSQL evidence adapter inside the existing source-owner transaction and case lock. Reuse the shared evidence parser and advanced pure rights functions; expose a separate exact evidence/report contract through the existing authentication foundation. Extend the current React question panel with scoped transient evidence state.

**Tech Stack:** Existing Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript; no new dependencies.

**Spec:** `docs/engineering/H1_AUTHORED_EVIDENCE_REPORTS.md`.

## Global Constraints

- Independently authored fictional data only; no patient-derived fixture, network acquisition or model call.
- Canonical H1 patient/case/question/source IDs and source snapshot meaning remain unchanged.
- Case-owned evidence only; no global catalog authority under a patient-scoped grant.
- New migration `0009_question_evidence` follows `0008_review_convergence`; preserve all older migrations.
- Follow-up `0010_authored_evidence_origin` preserves the published `0009` migration and binds exact creating-command identity without rewriting historical report bodies.
- Source-only brief and source packet meanings remain unchanged.
- No merge, deployment, clinical approval or external delivery.
- Preserve exact failed-check evidence; report skips separately from passes.

## Review Focus

- Changed content class must not authorize historical full-text quotations using abstract rights.
- Unicode quote offsets and JSON/body hashing must agree across Python and JavaScript.
- Uncertain writes must recover the same intent after a source refresh without duplicate assessment/report creation.
- Immutable old reports must remain historical and must be withheld after current rights withdrawal.
- Encoding and final same-bearer revocation must roll back writes and source-access receipts together.

### Task 1: Canonical evidence persistence, authority and report API

**Files:** Create `apps/api/src/oi_api/authored_evidence.py`, `evidence_report.py`, `authored_evidence_contracts.py`, `authored_evidence_routes.py`, `apps/api/migrations/versions/0009_question_evidence.py` and focused tests. Modify `access.py`, `contracts.py`, `patients.py` and readiness fixtures only as needed. Root supplies donor rights files.

**Interfaces:** All seven HTTP routes and exact shapes in the spec. Domain adapter owns evidence versions, withdrawals, assessments and immutable report snapshots; existing source owner owns locks, source custody, access receipt and transaction.

- [x] Write material failing parser/rights/report/contract tests and real PostgreSQL lifecycle/rollback/authority tests, using existing test harnesses.
- [x] Run local independent tests and capture the red result; record PG skips truthfully until hosted execution.
- [x] Implement append-only schema and bounded version/assessment/report adapter with exact idempotency and complete response preparation inside the transaction.
- [x] Implement shared human-only rights gates and deterministic literal report rendering; test historical class changes and Unicode quote offsets.
- [x] Implement independently authorized routes and coordinated readiness/manifest fixtures; preserve prior source APIs.
- [x] Preserve populated `0009` history through explicit command-origin backfill, reject ambiguous associations, and retain the legacy renderer while adding declaration values to new report text.
- [x] Run available API/reference tests and compile; retain actual logs. Root commits after integration to avoid shared-index conflicts.

### Task 2: Evidence inspection and authored comparison UI

**Files:** Create `apps/web/src/authored-evidence.ts`, `authored-evidence-panel.tsx`, scoped CSS and tests; modify `registry-client.ts`, `source-question-panel.tsx`, `main.tsx` and client tsconfig only as needed.

**Interfaces:** Strict decode/hash functions for exact Task 1 shapes; RegistrySession evidence state and methods over its existing bearer and scope generation. No independent credential store or persistence.

- [x] Write failing client tests for strict scope/shape/hash/Unicode validation and stale or withheld report handling.
- [x] Write failing session tests for late responses, current rights denial and uncertain-write exact retry across refresh/navigation.
- [x] Implement strict decoders, transient session operations and disclosures cleared by existing scope/navigation transitions.
- [x] Implement readable import/rights, assessment, withdrawal and report controls under the saved-question panel.
- [x] Run all client tests and locked production build; keep baseline behavior assertions unchanged.

### Task 3: Integrated browser, restart and exact-head verification

**Files:** Create `apps/web/tools/question_evidence_journey.py`; extend `browser_journey.py` and existing API recovery tools if needed. Update existing engineering/backlog records and this plan/spec with actual results.

**Interfaces:** Uses real seven-route API through built React and Chromium; artifact receipt includes exact question/source/evidence/assessment/report IDs, body/hash, original bytes, lifecycle and permission checks.

- [x] Author two fresh fictional evidence files and an explicit amendment, unrelated to real patient records.
- [x] Exercise import, support/contradiction proposals, selected report, actual fresh download, failed export, amendment/reassessment and withdrawal through actual UI/API.
- [x] Verify persisted reports and original associations after actual restart/restore; inspect exact download and narrow-screen screenshot.
- [x] Obtain independent whole-change review; fix substantive defects and verify targeted failures.
- [x] Publish draft branch/PR with immutable source tree mapping; run both exact-head hosted gates with no skipped PostgreSQL tests.
- [x] Verify artifact archive/checksum against final candidate and record failures/corrections, real test counts and limitations. Do not merge or deploy.

## Completion evidence

Runtime `e1170ddd69af5169027a35d1996163f959bbb503` (local equivalent
`4f34a719a880117bdf84b947a04bdb53590f7058`, tree
`be206c8b61a10d72662ca4d3c7b78fff90e4d8a1`) passed all three hosted workflows:
347 API/PostgreSQL tests without skips, 250 retained reference tests, 206 client
tests, production build, actual connected browser/download journeys and four
Compose recovery probes. Independent backend/client corrections were re-reviewed.
Both downloaded acceptance archives were checksum-verified; all 352 source files,
original/brief/report downloads and the 390 px captures were checked. The bounded
specification records the original failed candidate, repairs, exact run/artifact
IDs and limits. Final documentation-head verification is recorded in draft #300.
