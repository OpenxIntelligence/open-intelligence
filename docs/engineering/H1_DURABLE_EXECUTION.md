# H1 durable Composer execution

**Status — 5 November 2026:** implemented candidate; real PostgreSQL and hosted
acceptance are pending. Full process-kill and backup/restore acceptance is still
being built. Database-dependent tests skipped locally are unexecuted coverage,
not passing database tests. No deployment or clinical qualification is claimed.

This increment makes one existing deterministic source-question brief executable
through a durable PostgreSQL run and a separately invoked worker. It continues
the accepted H1 patient/source/question owners and the
[modular-engine sequence](MODULAR_ENGINE_BOUNDARIES.md), without creating another
patient master, source ledger or human follow-through system.

The implementation starts from accepted main
`57b8fd9f2b201ab46d338743aaab9f3f980b8a59` and architecture candidate
[#529](https://github.com/OpenxIntelligence/open-intelligence/pull/529).
[The execution plan](../superpowers/plans/2026-11-05-governed-execution-foundation.md)
records the authorized scope and acceptance requirements. An exact final source
revision, test results and hosted receipts must be added after verification.

## Lineage and ownership

Historical [#90](https://github.com/OpenxIntelligence/open-intelligence/pull/90)
and [#126](https://github.com/OpenxIntelligence/open-intelligence/pull/126) provide
the native Composer run-contract lineage. They are unmerged candidates, not an
installed H1 execution owner. This is their deliberate PostgreSQL continuation
within the existing `investigation` schema. The human-owned follow-through and
preparation-task ledgers retain their separate meanings; recording a person's
task as done does not enqueue or complete a worker run.

Shared source/question/brief response types are extracted into
`apps/api/src/oi_api/source_question_contracts.py`. Existing imports are retained
through reexports. The execution DTOs live in `composer_run_contracts.py`, the
persistent owner in `composer_runs.py`, HTTP composition in
`composer_run_routes.py`, and the process entry point in `worker.py`.

The only executable kind is **`source-question-brief/1`**. It renders the existing
source-only brief for a saved text-source question with an exact source-line
anchor. Laboratory Observation questions, model calls, bioinformatics pipelines,
delegated agents and external actions are not execution kinds in this candidate.
The existing synchronous brief route remains available.

## Authority and immutable intent

Enqueue, status, cancellation, execution and result access require the existing
`patient_read`, `question_read`, `source_read` and `source_brief_export` grants,
the exact patient/case scope and purpose **`operations`**. Runs are bound to the
requesting actor, organization and purpose. Another actor's patient access does
not confer ownership of that run.

The worker supplies its own current credential at runtime. It rereads the token
file and reauthenticates at authority checkpoints; the actor, organization and
purpose must continue to match. No request bearer or inherited permission list
is persisted in a run. There is no durable delegation grant or new identity
provider. The configured authentication fixture remains synthetic.

Each run pins the canonical patient, case and question; source-snapshot contract
and fingerprint; preflight fingerprint; exact source ID, version, SHA-256 and
line; executable kind; and request key/digest. The source owner validates those
references before the intent is inserted. The unique request scope is
`(origin_org, actor, purpose, request_key)`: an identical authorized retry returns
the same run, while reuse with a changed intent is rejected. A retry still
passes current source and authority checks.

## Persistence and lifecycle

Readiness requires PostgreSQL 16 at **`0019_composer_runs`**, directly after
`0018_laboratory_questions` in this candidate's migration graph. Startup does not
apply migrations. The migration adds three owned tables:

| Table in `investigation` | Responsibility |
| --- | --- |
| `composer_tool_runs` | Immutable intent, current lifecycle revision, bounded attempt count and lease |
| `composer_tool_run_events` | Append-only event for every lifecycle revision |
| `composer_tool_run_results` | One immutable, digested JSON brief for a completed run |

Database guards reject changed intent, invalid transitions, deletion of run
history and mutation or truncation of events/results. Deferred consistency
checks require each run revision to have its matching event and require a result
exactly when the run is completed. Each application transition also appends
bounded reference metadata to the canonical identity-domain event journal in
the transaction. Bearers, source narrative and exception details are excluded
from that metadata. Downgrade refuses to discard populated execution history.

| State | Meaning |
| --- | --- |
| `queued` | Available for a claim after its database-clock availability time |
| `running` | A claimed attempt with a token and database-clock lease expiry |
| `completed` | One accepted immutable brief and result digest were committed |
| `blocked` | The held attempt encountered unavailable authority |
| `stale` | The held attempt's pinned source context changed |
| `cancelled` | An authorized cancellation ended queued or running work |
| `failed` | Invalid output or exhausted attempts ended the run |

A short claim transaction uses `FOR UPDATE SKIP LOCKED`. Each claim increments
the attempt count and issues a new token. The default lease is 30 seconds; the
supported range is 1–300 seconds. There are **at most three attempts total**.
Retryable failures return to `queued` with a bounded delay; an expired running
lease can be reclaimed until the attempt limit is exhausted.

Completion checks the current token, attempt and unexpired lease. Cancellation
or a replacement lease fences an older worker from accepting a result. Terminal
rows are immutable; cancelling a terminal run returns its existing status.
This is at-least-once execution with one accepted terminal result, not a promise
that computation executes exactly once.

Claim commits before computation. The current bounded renderer uses the existing
brief owner's short source transaction for source validation, response preparation,
fenced result persistence, final authority checks and audit commit. Expensive or
external tools will need a separately qualified frozen-input/publication contract;
this transaction pattern is not a general long-running computation interface.

## Result integrity and fresh access

The stored brief must match the immutable question and source pins. Its canonical
JSON digest covers the actual saved response, including the original source-read
receipt and preparation time. Result access verifies that digest, revalidates
the source contract and obtains a fresh authority receipt before disclosure.
The outer result receipt is current; the brief retains its historical receipt.

An amendment can therefore withhold a previously completed result body without
rewriting its original bytes or changing the historical `completed` row to
`stale`. Status alone is not proof that a result is currently releasable.
Revoked or mismatched authority withholds access. Responses remain bounded and
noncacheable. Every run status carries `model_executed=false` and
`clinical_approval=false`.

## HTTP controls

All paths below share the prefix
`/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/runs`.

| Method and suffix | Behavior |
| --- | --- |
| `POST` at the prefix | Enqueue: 201 for a new run; 200 for an identical authorized retry |
| `GET /{run_id}` | Read scoped run status |
| `POST /{run_id}/cancel` | Cancel queued/running work or return existing terminal status |
| `GET /{run_id}/result` | Read a completed brief after fresh authority, source and integrity checks |

Enqueue requires `synthetic: true`, `request_key`,
`source_snapshot_contract: "oi.pg-source-world-model/1"`,
`expected_source_snapshot_sha256` and `expected_preflight_sha256` from the
authorized saved-question context. Cancellation requires `synthetic: true`.
The caller does not supply an executable module, arbitrary prompt, output body
or another actor's credentials. Denied run access is reported as unavailable.

## Run one worker attempt

Use the existing [API setup](../../apps/api/README.md) and
[fictional application guide](../H1_DEMO.md) for the locked dependencies,
synthetic PostgreSQL database, access fixture and saved source question. Apply
the candidate's migration explicitly, using the same Python environment as the
API:

```bash
PYTHONPATH=apps/api/src:src python -m oi_api.migrate upgrade 0019_composer_runs
PYTHONPATH=apps/api/src:src python -m oi_api.migrate current
```

The worker uses existing `OI_API_DATABASE_URL`, `OI_API_ENVIRONMENT=synthetic`
and optional `OI_API_CONNECT_TIMEOUT_SECONDS` settings. Set `OI_API_ACCESS_FILE`
to the synthetic authentication fixture and `OI_API_WORKER_TOKEN_FILE` to an
operator-controlled file containing the worker's current bearer. Keep credential
contents out of commands, logs and the repository. These settings identify
credentials; they do not grant access to a patient or delegate another actor.

After enqueueing a run, set `OI_RUN_PATIENT_ID` and `OI_RUN_CASE_ID` to its existing
fictional identifiers, then run from the repository root:

```bash
PYTHONPATH=apps/api/src:src python -m oi_api.worker \
  --once --patient "$OI_RUN_PATIENT_ID" --case "$OI_RUN_CASE_ID"
```

`--lease-seconds` optionally selects a duration from 1 to 300. `--once` is
required: each process claims at most one eligible run for that actor and scope.
It emits only a bounded JSON operational status and, where available, attempt
count. It never prints the brief or credential. `idle` means no run was claimed;
`unavailable` can leave a claim awaiting lease recovery and does not prove that
work rolled back. A recurring scheduler or service manager is not installed.

## Verification record and remaining acceptance

Implementation and tests are present, but this document records **no passing
real-database or hosted result yet**. The current local environment cannot run
PostgreSQL; database-dependent skips must remain explicit. Relevant coverage is
in `test_source_question_contracts.py`, `test_composer_run_contracts.py`,
`test_composer_run_worker.py`, `test_composer_run_routes.py`,
`test_composer_runs_postgres.py` and `test_composer_run_migrations.py` under
`apps/api/tests`.

Before accepting the candidate, record the exact source revision and combined
results for populated migration, lifecycle/history/result guards, duplicate
intent, concurrent claims, lease expiry, stale-worker fencing, cancellation,
source amendment, credential/grant changes, serialization/audit rollback and
actual PostgreSQL persistence. Full process-kill/restart and populated
backup/restore acceptance is still being built. Existing API, frontend/browser,
reference and recovery regressions remain required; prior branch receipts do
not qualify this composition.

No new model, delegated agent, external broker, cloud platform or orchestration
framework is adopted. The worker is one synthetic execution foundation, not
completion of the fifteen proposed engines, production identity/consent,
clinical decision support or a deployed release.
