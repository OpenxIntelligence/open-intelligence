# Question manual passages implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Carry exact manual record passages into existing canonical questions and preserved evidence reports.

**Architecture:** Add an immutable reference-set child to the existing question owner. Resolve all text through the source owner under its case lock, and extend the existing report snapshot/renderer without rewriting historical reports.

**Tech Stack:** Existing Python/FastAPI/PostgreSQL and React/Vite/TypeScript; no new dependencies.

**Spec:** `docs/engineering/H1_QUESTION_MANUAL_PASSAGES.md`.

## Global constraints

- Independently authored fictional records only; no real patient inputs.
- At most 20 exact references per set; preserve published migrations.
- User-selected annotations never become source-authored observations.
- Preserve exact retries, historical bytes and independent original-read authority.
- No merge, deployment, model execution or clinical approval.

## Review focus

- Same-key annotation correction must not silently retarget a saved quotation.
- Removal must not disclose old report text without current original-read authority.
- Revocation after encoding or an audit callback must roll back every side effect.
- A second writer must not overwrite an inspected context set.
- An old response must not refill another patient, case or question panel.

## Tasks

### 1. Canonical question passage references

Files: new `question_passages.py`, `question_passage_contracts.py`, `question_passage_routes.py`, additive `0013_question_passages.py`; mount in `patients.py`.

Interface: GET/POST `/questions/{question_id}/manual-passages`; POST carries synthetic flag, request key, expected context hash and up to 20 source/annotation/key/hash references. GET returns the selected immutable set with source-owned resolved anchors, independent freshness and a context hash.

- [ ] Write and run failing HTTP acceptance for attach/read, exact retry, changed intent, stale replacement, cross-scope references and authorization rollback.
- [ ] Implement immutable persistence, locked source resolution, bounded history and compare-and-swap updates.
- [ ] Verify focused tests and commit.

### 2. Preserved report context

Files: `authored_evidence.py`, `authored_evidence_contracts.py`, `authored_evidence_routes.py`, `evidence_report.py`; additive migration extends renderer compatibility.

Interface: optional expected manual-context hash in report command; versioned nested manual context in new report snapshots; existing report API and legacy snapshots remain compatible.

- [ ] Add failing tests for frozen quotation/attribution, correction invalidation, stale report rejection, legacy report compatibility and revoked original-read.
- [ ] Implement v3 literal rendering, immutable-source verification and current-context comparison; preserve exact command recovery.
- [ ] Run focused API/contracts tests and commit.

### 3. Existing workspace and combined verification

Files: new `question-passages.ts` and `question-passages-panel.tsx`; existing registry transport and evidence panel/session/parser; client and actual browser tests.

- [ ] Add failing client checks for strict provenance, foreign scope, uncertain retry and late responses.
- [ ] Add bounded passage selection/editing in the existing evidence workspace and bind report creation to the inspected context hash.
- [ ] Run client suite/build/rights checks and actual PostgreSQL HTTP/browser acceptance.
- [ ] Extend restored database coverage for context revisions and report continuity.
- [ ] Obtain fresh independent review, fix material findings, publish a draft PR with exact-head verification and update backlog/limitations.
