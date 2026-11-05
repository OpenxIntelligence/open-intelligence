# Governed H1 execution foundation

## Authorized scope and acceptance

The founder's continuation after the modular-engine increment explicitly asks
for infrastructure implementation. This plan implements the two next stages
already proposed: independent question/source contracts and one durable synthetic
worker. The bounded addition is a PostgreSQL continuation of the Composer run
contract, using the existing saved-question brief as its only executable kind.
It includes the additive migration and scoped run controls needed to exercise
that worker. Production deployment, new identity/delegation policy, clinical
logic, external services and model execution are outside this increment.

Baseline: accepted main `57b8fd9f2b201ab46d338743aaab9f3f980b8a59`, combined
with architecture PR #529 `0d2ee2651d29f21b52b3ee2e99ee51b0771ecba4`.
The existing plan, backlog and patient/source/question authority remain canonical.
Historical #90/#126 supply Composer lifecycle lineage, not installed H1 code.
Human follow-through tasks remain their own operational owner.

## Task 1 — isolate current contracts

- Move shared source/question/brief response contracts out of HTTP composition.
- Preserve imports through reexports, validation and the complete existing OpenAPI.
- Reconcile the owner catalog with the current source-anchor helper and remove
  the exact reverse-import exceptions eliminated by the extraction.

Acceptance: exact pre/post OpenAPI equality before new routes; current contract
tests and boundary gate pass. No wire representation changes.

## Task 2 — persistent Composer runs

Add one migration, `0019_composer_runs`, after `0018_laboratory_questions`.
Use the existing `investigation` schema and registry transaction/event owner.
No automatic schema installation, external broker or generic plugin loading.

### Storage interface shared by implementation tasks

`investigation.composer_tool_runs`:

- `run_id` text primary key, `RUN-` plus 32 uppercase hexadecimal characters.
- Immutable `patient_id`, `case_id`, `question_id`, `origin_org`, `actor`,
  `purpose` (`operations`), `kind` (`source-question-brief/1`).
- Immutable `source_snapshot_contract` (`oi.pg-source-world-model/1`),
  `source_snapshot_sha256`, `preflight_sha256`, `source_id`, `source_version`,
  `source_sha256`, `source_line`, `request_key`, `request_digest`.
- Unique `(origin_org, actor, purpose, request_key)`; question/source scope
  validated against the canonical question at insertion.
- `state`: queued/running/completed/blocked/stale/cancelled/failed.
- `revision` integer >= 1; `attempt_count` integer 0..3; `max_attempts` fixed 3.
- Nullable `lease_token` (`LEASE-` plus 32 uppercase hex), `lease_expires_at`.
  Both exist exactly when running. A new claim increments `attempt_count` and
  issues a new token; completion requires both and an unexpired database lease.
- `available_at`, `created_at`, `updated_at`: timestamptz, database clock.
- Terminal rows cannot be changed. Immutable intent cannot be changed. Only
  documented lifecycle transitions are allowed; revision advances exactly once.

`investigation.composer_tool_run_events`:

- `id` bigserial primary key; `run_id` foreign key; `revision`, `state`,
  `attempt_count`, `reason_code`, `created_at` (database clock).
- Unique `(run_id, revision)`; append only, including truncate rejection.
- Reason codes: queued, claimed, lease_recovered, retryable_failure,
  attempts_exhausted, completed, cancelled, source_changed,
  authority_unavailable, invalid_output.

`investigation.composer_tool_run_results`:

- `run_id` primary/foreign key; `result_json` jsonb; `result_sha256` lowercase
  hexadecimal SHA-256; `created_at` (database clock).
- One immutable result per completed run; no update/delete/truncate.
- Complete DTO is validated and bounded to the existing 65,536-byte brief
  envelope before storage. The database additionally bounds JSON text to
  131,072 bytes. A deferred consistency guard ties result existence to completed
  state at commit. The artifact digest covers canonical JSON, including the
  exact source read receipt and preparation time.

Runs and lifecycle history are inseparable at commit. Each application lifecycle
change also appends bounded reference metadata to the canonical identity domain
event journal. No token, source narrative or exception text enters audit metadata.
Downgrade refuses to discard populated execution history.

### Execution and authority

The worker polls one explicit patient/case scope for its freshly authenticated
actor/organization/purpose. It uses independently supplied local credentials,
never a bearer stored in a run. The existing patient_read, question_read,
source_read and source_brief_export actions remain necessary.

Claims are short transactions with SKIP LOCKED, database time, a bounded lease,
three attempts and bounded retry delay. Computation follows claim commit.
The existing brief owner validates the exact question and source snapshot.
Its prepared-response callback validates output and performs fenced result
persistence; final authority and audit-tail checks protect that transaction.
Cancellation or a replacement lease defeats an older completion. This is
at-least-once execution with one accepted terminal result, not exactly once work.

Result reads recheck current authority and the original source contract. An
amendment withholds the prior body while retaining immutable historical bytes.
An invalid or unavailable credential cannot grant durable delegated execution.
Expensive tools will require a separate frozen-input/publish interface; the
bounded current renderer retains the existing short source transaction.

## Task 3 — connected controls and operational acceptance

Retain the synchronous source-brief route. Add enqueue/status/cancel/result run
controls under the same patient/case/question scope and a separately runnable
`python -m oi_api.worker --once` entry point. Keep bodies bounded, responses
noncacheable and errors free of source text and credential material.

Tests must demonstrate idempotent/changed intent, concurrent claim, expired lease
recovery, stale worker fencing, cancellation, source amendment, grant revocation,
serialization/audit rollback, restart and real PostgreSQL persistence. PostgreSQL
acceptance must run without skips. Existing API, migration, frontend/browser and
backup/restore checks remain required; record exact hosted source identity.

## Execution ledger

- Repository merge: retained both architecture backlog additions and concurrent
  main backlog edits; no application conflict. Combined checkpoint `463c545`.
- Ruling: use the existing brief as the first executable kind and the Composer
  run lineage as its owner. Cost: no bioinformatics/model execution is qualified
  by this foundational workload; it establishes the execution path they need.
- Ruling: the founder's explicit proceed instruction authorizes this bounded
  worker and its additive synthetic persistence/control contract. Preserve all
  existing permissions and clinical semantics; no deployment is authorized.
- Pre-flight: contract extraction produces the independent brief DTO consumed
  by run validation. Migration and runtime share the exact storage fields above.
- Local environment has the existing hash-locked API dependencies. PostgreSQL
  and Docker are unavailable; package bootstrap failed on container privilege
  restrictions. Real database acceptance will be obtained in hosted PostgreSQL
  CI, and local skips will remain explicitly distinguished.
