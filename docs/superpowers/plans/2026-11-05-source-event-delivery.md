# H1 Source Event Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish canonical H1 source-import obligations atomically and deliver them through current authority to bounded Composer freshness reconciliation.

**Architecture:** A narrow PostgreSQL H1 binding adapter reuses the canonical journal, source/question projection and Composer run owner. Platform transport accepts explicit owner callbacks and never imports a domain consumer. Delivery effects, owner receipt and acknowledgment commit together, with actor-scoped leases and recoverable retries.

**Tech Stack:** Existing Python/FastAPI/Pydantic/SQLAlchemy/Alembic and PostgreSQL 16; existing React/Vite/TypeScript acceptance application; no new runtime dependency.

**Spec:** [H1 Source Event Delivery Design](../specs/2026-11-05-source-event-delivery-design.md).

## Global Constraints

- Contract: `oi.h1-source-context-event/1`; producer: `source.original.imported`.
- Migration: `0020_source_event_delivery` after `0019_composer_runs`.
- Purpose: `operations`; actions: `patient_read`, `question_read`, `source_read`, `source_brief_export`.
- Maximum **100** affected Composer runs per consume transaction.
- Maximum **three** consecutive failures; successful progress resets that budget.
- No global acknowledgment/cursor, stored bearer, service delegation or clinical authority.
- Only outdated `queued`/`running` Composer runs may become `stale`; preserve current/terminal runs and human tasks.
- Preserve #70's `oi.domain-event/1` reference lineage; do not claim wire compatibility.
- Synthetic only; no new API, broker, Temporal, DBOS, scheduler, model, merge or deployment.
- Continue #529 under #104/PF-06/WS-08/CMP-11 and #81; no competing program or canonical state.
- The entire PF-01–PF-10 and PD-01–PD-16 objective remains open.

## Review Focus

- A delayed old event must use current case context and preserve newer current-fingerprint runs; Task 3 owns the regression.
- A lost response after consumer commit must recover the same receipt only after current authority, with no repeated effect; Tasks 2–3 own the regression.
- A valid case with more than 100 stale candidates must finish in bounded successful batches rather than exhaust a total-attempt cap; Tasks 2–3 own the regression.
- Repeated process death must eventually expose `dead_letter`, not masquerade as `idle`; Tasks 2 and 4 own the regression.
- Malformed selected historical journal rows must fail upgrade visibly instead of disappearing from a backfill; Task 1 owns the regression.

## Baseline and execution ownership

Start at `cd10a828e499bf65dbbe8eb4ca77207710a5f2b7`, the clean join of verified
#529 source `2312755dc52260c3632c5801b1b7b68041671833` and accepted main
`aad241e5cce9a1bcff3e431d63cecd16e948d731`. Previous acceptance is historical
evidence for its named source only. The user's start instruction covers this
scoped additive persistence and worker continuation; release decisions remain
separate. The coordinating implementation owner controls commits and publication
to existing draft #529 so parallel contributors do not publish competing trees.

## File responsibilities

| Path | Responsibility |
| --- | --- |
| `apps/api/migrations/versions/0020_source_event_delivery.py` | Atomic journal capture, strict backfill, transport lifecycle/history, owner receipts and database guards. |
| `apps/api/src/oi_api/contracts.py` | Exact readiness revision. |
| `apps/api/src/oi_api/source_event_delivery.py` | Platform transport constants, coordination class and `EventLeaseLost`; no separate contracts module or consumer import. |
| `apps/api/src/oi_api/source_questions.py` | Current source-context projection callback through existing owners. |
| `apps/api/src/oi_api/composer_runs.py` | Transport factory, authorized bounded effects and consumer receipt retrieval. |
| `apps/api/src/oi_api/event_worker.py` | Current-credential, one-attempt CLI in the questions/review owner. |
| `apps/api/tests/test_source_event_migrations.py` | Migration graph and real database integrity/upgrade tests. |
| `apps/api/tests/test_source_event_delivery.py` | Transactional publication/delivery, authority, retry, batch and recovery tests. |
| `apps/api/tests/test_source_event_worker.py` | CLI/current-credential and truthful-status tests. |
| `docs/architecture/engine_boundaries.json` | Declare platform transport and questions/review worker ownership/interfaces. |
| `.github/workflows/h1-execution.yml`, `.github/workflows/h1-api.yml` | Run focused and inherited acceptance on the exact source with PostgreSQL 16. |

The test paths above are the planned homes; retain an existing equivalent test
class when its owner already covers the behavior rather than duplicate it.

---

### Task 1: Atomic publication and protected persistence

**Files:** Create the migration and migration tests; modify readiness in
`apps/api/src/oi_api/contracts.py`. Reuse the existing source journal producer;
do not add parallel import-path publication calls.

**Interfaces:** Consumes canonical `identity.identity_domain_events` rows for
`source.original.imported` and existing patient/case/source bindings. Produces
`coordination.source_event_outbox`, `source_event_deliveries`,
`source_event_delivery_events`, and Composer-owned
`investigation.composer_source_event_receipts` as specified in the design.

- [ ] Write a failing single-head/readiness test for `0020_source_event_delivery`
  with parent `0019_composer_runs`; run it before migration implementation.
- [ ] Add real-PostgreSQL regressions proving atomic import/event/outbox commit,
  producer rollback and one obligation for an exact accepted import retry.
- [ ] Add populated-upgrade regressions: valid historical selection backfills;
  malformed selected event, forged source/scope or missing canonical source
  rejects the upgrade; unrelated journal types remain outside this adapter.
- [ ] Implement the trigger and strict backfill without repairing historical
  records. Preserve existing originals, receipts and journal identity.
- [ ] Add direct-SQL mutation/transition/receipt-parity tests and populated
  downgrade refusal; implement the guards and immutable history.
- [ ] Run `PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests -p 'test_source_event_migrations.py' -v`.
  Graph tests must pass; database tests require real PostgreSQL and zero skips
  before their behavior is accepted. Record any local skip separately.
- [ ] Review/checkpoint this schema delta with the coordinating owner before
  dependent transport acceptance; do not merge or deploy.

### Task 2: Actor-scoped transport, leases and failure accounting

**Files:** Create `source_event_delivery.py` and transport tests in
`test_source_event_delivery.py`; update the architecture catalog.

**Interfaces:** The platform coordinator accepts `authorize_scope_locked`,
`consume_locked` and `receipt_locked` callbacks supplied by Composer. It exposes
`claim_next` and a fenced consume/failure lifecycle, exporting `EventLeaseLost`.
Claims identify one current actor/org/purpose/event delivery. `claim_next`
returns a running claim, `None`, or the explicit terminal receipt from exhausting
three expired claims. Consumer data and writes stay behind callbacks.

- [ ] Write failing tests for two actors independently receiving the same event,
  wrong patient/case/org/purpose, no global cursor and no persisted credential.
- [ ] Write failing concurrent-claim and fencing tests: a replaced or expired
  token cannot change effects, receipt or acknowledgment.
- [ ] Write failing tests for retry delay and three consecutive failures,
  including three abandoned leases returning `dead_letter` rather than `None`.
- [ ] Implement claims with database time, scoped row locks, lease tokens and
  append-only lifecycle history; do not import Composer into the platform module.
- [ ] Add the progress regression: a successful bounded continuation resets
  consecutive failures while lifetime claim numbers and history remain intact.
- [ ] Add atomic consume tests with injected callback/audit failures: effect,
  receipt and acknowledgment all roll back; an already committed receipt can
  be returned only through fresh authorization.
- [ ] Run the focused PostgreSQL suite with zero skips for acceptance; run
  `PYTHONPATH=apps/api/src:src python -m unittest discover -s tools/architecture -p 'test_engine_boundaries.py' -v`
  and the existing boundary command used by CI. Review/checkpoint the delta.

### Task 3: Current-context Composer consumer

**Files:** Modify `source_questions.py` and `composer_runs.py`; extend
`test_source_event_delivery.py` and reuse Composer fixtures.

**Interfaces:** Questions supplies
`prepare_run_context_locked(patient_id, case_id, *, organization, actor, purpose,
recheck_authority, prepare_response)` through its existing source `list_locked`
projection. Composer supplies `source_events()`,
`consume_source_event_locked(delivery, *, recheck_authority)` and
`source_event_receipt_locked(claim)`. Its factory binds those domain callbacks
to transport `authorize_scope_locked`, `consume_locked`, `receipt_locked`.

- [ ] Write failing tests in which source import leaves old queued/running runs
  eligible for staleness but current-fingerprint, completed, blocked, cancelled,
  failed and already stale runs and human tasks remain unchanged.
- [ ] Add delayed/backfilled-event and source-change-after-claim cases. Assert
  that comparison uses the current whole-case fingerprint on every attempt,
  not the triggering event's old snapshot or an assumed causal relationship.
- [ ] Add at least 101 eligible runs: the first transaction affects exactly
  100, records a partial receipt and requeues; the next completes the remainder.
  Exercise more than three successful batches without failure exhaustion.
- [ ] Implement current-context projection with source read audit and current
  authority. Composer alone locks and changes its selected runs and writes the
  receipt keyed by delivery plus attempt. Verify each existing
  `composer.run.stale` audit includes `source_event_id`, `delivery_id` and
  `delivery_attempt`, matching that receipt's evaluated fingerprint and count.
- [ ] Add lost-response and duplicate-receipt recovery tests; fresh authorized
  recovery returns the same receipt and does not repeat effects. Revocation or
  actor switch denies recovery and never releases source/result content.
- [ ] Add concurrent completion/cancel and final-authority/audit failure tests;
  preserve terminal history, rollback partial effects and fence old workers.
- [ ] Run focused delivery and inherited Composer PostgreSQL suites; review
  the owner boundaries and checkpoint the combined transport/consumer delta.

### Task 4: Bounded worker and actual interruption/recovery

**Files:** Create `event_worker.py`; extend worker and delivery tests; update
`h1-execution.yml` and the existing API gate only as needed for actual coverage.

**Interfaces:** The CLI follows the existing worker pattern:
`PYTHONPATH=apps/api/src:src python -m oi_api.event_worker --once --patient PATIENT --case CASE`.
It reads `OI_API_EVENT_WORKER_TOKEN_FILE` with existing `OI_API_ACCESS_FILE` and database
settings, composes `PostgresComposerRuns.source_events()` and reports only
`delivered`, `queued`, `idle`, `fenced`, `blocked`, `dead_letter`, `unavailable`.

- [ ] Write worker tests for missing/invalid credentials, wrong scope, actor
  changes between checks, a revoked claim, dead-letter return from `claim_next`
  and a database exception whose commit status is unknown.
- [ ] Implement one bounded current-authority attempt without a scheduler,
  stored bearer, new route, broker or inferred successful acknowledgment.
- [ ] Add a real process-kill/restart test: commit a lease, kill the claimant,
  reclaim after expiry and reject its obsolete token. Exercise third-expiry
  dead-letter reporting rather than only successful restart.
- [ ] Add populated PostgreSQL 16 dump/restore acceptance with outstanding and
  completed deliveries, immutable receipts, exact retries, restored revoked
  access and an unchanged original database. Use matching version-16 clients.
- [ ] Run `PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests -p 'test_source_event_worker.py' -v`
  and the real-PostgreSQL delivery suite; collect truthful failures/skips.
- [ ] Review/checkpoint operational behavior and wire exact source collection
  into the existing hosted acceptance workflow.

### Task 5: Combined verification and bounded publication

**Files:** These design/plan documents and existing implementation/engineering
records, updated by the coordinating owner only after actual evidence. No new
roadmap or canonical document is required.

**Interfaces:** Consumes the exact combined Git source/tree and real job logs,
artifacts and independent review. Publishes bounded receipts in existing #529;
previous static-checker/worker/laboratory receipts retain their original scope.

- [ ] Run migration, transport, owner-consumer, worker and architecture checks;
  reproduce/fix meaningful failures without weakening authority or invariants.
- [ ] Obtain independent review of publication atomicity, SQL integrity,
  callbacks/ownership, revocation, batching and retry/receipt semantics.
- [ ] Freeze one candidate, verify current-main reconciliation, and run the
  existing full API/PostgreSQL, reference, web/browser and recovery workflows.
  A donor pass or locally skipped database test is not combined acceptance.
- [ ] Inspect terminal hosted results and source manifests/archives. Record
  exact source and tree, counts/skips, recovery behavior and unresolved findings.
- [ ] Update existing #529 and authorized canonical records with the result;
  leave the PR draft/unmerged/undeployed and full PF/PD construction unfinished.

## Evidence ledger — publication checkpoint

This template deliberately asserts no new passing tests. Implementation is in
progress. Record intermediate RED results and subsequent corrections rather than
rewriting them as passes. PR #529 remains the living exact-source acceptance ledger.

| Receipt | Required record | Current status |
| --- | --- | --- |
| Source | Commit, full tree, accepted-main input and comparison | Baseline pinned above; final candidate not yet qualified |
| Migration | Graph, populated upgrade/backfill, malformed history, direct SQL integrity | Pending execution evidence |
| Transport/consumer | Counts, failures/skips, actor isolation, atomicity, 100-run batches and retries | Pending execution evidence |
| Worker/recovery | Current credentials, actual kill, restart, populated dump/restore and restored denial | Pending execution evidence |
| Combined regressions | Exact API/reference/web/browser/recovery workflow URLs and terminal outcomes | Pending execution evidence |
| Independent review | Reviewer scope, findings, reproductions and corrections | Pending review evidence |
| Artifact parity | Archived source/receipt content matched to the tested tree | Pending verification |
| Release | PR status and explicit remaining foundation/clinical/production work | Draft continuation; no merge/deployment/clinical claim |
