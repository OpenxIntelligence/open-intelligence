# H1 Source Event Delivery

**Implemented synthetic candidate; acceptance pending at this source-publication
checkpoint.** [PR #529](https://github.com/OpenxIntelligence/open-intelligence/pull/529)
maintains the living exact-source test, hosted acceptance and landing ledger.
Earlier verified worker results do not qualify this addition automatically.

## Purpose and existing owners

This is the next bounded PF-06 / WS-08 / CMP-11 increment under
[#104](https://github.com/OpenxIntelligence/open-intelligence/issues/104) and
[#81](https://github.com/OpenxIntelligence/open-intelligence/issues/81). It records
an obligation when the canonical source journal accepts `source.original.imported`
and lets a currently authorized worker reconcile affected pending Composer runs.
The source, question, Composer, review and human follow-through owners remain
canonical. The entire PF-01–PF-10 and PD-01–PD-16 objective remains unfinished.

The narrow adapter is `oi.h1-source-context-event/1`, with consumer
`composer-source-context/1`. Its outbox carries immutable source ID/version and
scope references, not copied source content or a second authoritative source hash.
Current fingerprints and hashes come through the source/question owners. This
does not claim wire compatibility with #70's general SQLite `oi.domain-event/1`
contract, whose namespace, subject-binding and authority references differ.

## Prepare the existing synthetic environment

Use the existing [persistent demo setup](../H1_DEMO.md), dependency lock and
PostgreSQL 16 configuration. The event worker uses `OI_API_DATABASE_URL`,
`OI_API_ACCESS_FILE` and the same synthetic access provider as the application.
`OI_API_ENVIRONMENT` remains `synthetic`. It installs no grants or schema on
startup.

Apply the explicit additive migration through the normal migration command:

```bash
PYTHONPATH=apps/api/src:src python -m oi_api.migrate upgrade head
```

The application requires `0026_integrated_core`, joining the clinical
execution head with `0020_source_event_delivery`. That historical revision captures new source-import events and
strictly backfills selected historical source-import events against their
canonical source/patient/case bindings. Malformed selected history fails the
upgrade rather than being silently omitted or repaired. Existing originals and
run history are retained; populated delivery history cannot be discarded by
downgrade.

The construction baseline is
`cd10a828e499bf65dbbe8eb4ca77207710a5f2b7`, joining verified worker source
`2312755dc52260c3632c5801b1b7b68041671833` and accepted main
`aad241e5cce9a1bcff3e431d63cecd16e948d731`. The combined laboratory, encounter and execution migrations and verification results are tracked in [draft #564](https://github.com/OpenxIntelligence/open-intelligence/pull/564).

## Run one bounded attempt

Supply the path to a current credential file explicitly for this worker:

```bash
export OI_API_EVENT_WORKER_TOKEN_FILE=/path/to/current-event-worker.token
PYTHONPATH=apps/api/src:src python -m oi_api.event_worker \
  --once --patient PATIENT_ID --case CASE_ID --lease-seconds 30
```

Replace the path and opaque IDs with the configured synthetic fixture's values.
Keep the actual token outside repository files, command arguments and output.
The event worker does **not** fall back to `OI_API_WORKER_TOKEN_FILE`, which is
the separate Composer computation worker's setting.

The current credential must authorize the selected patient/case, purpose
`operations` and all four existing actions: `patient_read`, `question_read`,
`source_read`, `source_brief_export`. Runtime checks reread the credential and
provider, require the original actor/organization/purpose and enforce current
scope. A recorded event, original importer or stored delivery is not a durable
grant or delegated service identity. No bearer credential is persisted.

`--once` processes at most one delivery attempt and one bounded consumer batch;
it does not drain the case. Repeat deliberately when work remains. The lease
defaults to **30 seconds** and accepts integer values **1–300 seconds**. There is
no lease-renewal command or background scheduler in this increment.

## Read the operational result

The command prints bounded JSON without source text, credential values or raw
exception details. An attempt count and invalidated-run count appear when the
outcome has those receipts.

| Status | Meaning | Exit code |
| --- | --- | --- |
| `delivered` | This attempt committed its consumer receipt and finished this actor's delivery. A zero-effect reconciliation is valid. | 0 |
| `queued` | A bounded batch made progress with more work remaining, or a retryable failure was requeued with a delay. | 0 |
| `idle` | No claim is eligible for this current actor/scope now. It is not proof that all actors' work is complete or that no delayed/dead-letter work exists. | 0 |
| `fenced` | The claim expired or was replaced; this attempt did not obtain a new accepted effect/acknowledgment. | 0 |
| `blocked` | Current scope or authority could not authorize a claim. | 2 |
| `dead_letter` | This actor's delivery became terminal because authority/event validation failed or the consecutive-failure budget was exhausted. | 2 |
| `unavailable` | Configuration/database/transport failed or the caller could not establish the commit outcome; no success or rollback is inferred. | 2 |

Delivery is per actor, organization, purpose and event. Another actor's receipt
does not acknowledge this actor's work. A lower journal event ID committed later
remains discoverable because delivery uses no global sequence cursor.

## Batches, retries and immutable receipts

The consumer obtains the **current whole-case source fingerprint** on each
attempt and changes at most **100** outdated `queued` or `running` Composer runs.
Current-fingerprint and terminal runs, accepted result bytes and human tasks stay
unchanged. A delayed or backfilled event is a reconciliation trigger; it is not
proof that this historical event caused every change in the current context.

Effects, the Composer-owned receipt keyed by delivery plus attempt, and the
transport's acknowledgment/continuation commit atomically. Partial success
records a receipt and requeues the remainder. Lost-response receipt recovery
reauthorizes the original scope and returns the existing receipt without
repeating effects or conferring result-read access.

Each affected run's existing `composer.run.stale` audit event includes
`source_event_id`, `delivery_id` and `delivery_attempt`, linking the run change
to its delivery without introducing another event type. The consumer receipt
records the evaluated fingerprint and affected-run count; this trace does not
turn the historical source event into a claim of sole causation.

The failure budget is **three consecutive failures**, not three lifetime claims.
Successful progress resets it, so larger cases can finish through several
100-run batches. Retryable failures have bounded backoff; abandoned expired
leases also count. The third consecutive expired claim returns `dead_letter`
explicitly instead of reporting idle. An obsolete token cannot publish an
effect, receipt or acknowledgment.

Dead-letter state is specific to this actor's delivery and preserves its history.
There is currently **no dead-letter replay/reset command**. Repeating `--once`
does not reopen it. Inspect the original source/journal and delivery/receipt
evidence through authorized engineering access; a replay workflow requires a
separate reviewed contract.

## Correctness while the worker is stopped

**Existing fresh-source and current-authority checks remain the correctness
gate.** Event delivery advances pending-run state and does not replace the
Composer owner's enqueue, completion or result-disclosure checks. An idle,
delayed, stopped or dead-lettered event worker cannot make a stale result
disclosable. Historical completed receipts and result bytes remain preserved.

Transaction ordering is current authority and patient/case locks, then delivery
lock/fence, then consumer-owned run rows. The platform module owns coordination
and canonical audit only. Composer supplies authorization/effect/receipt
callbacks, while the questions owner preserves source access audit and final
authority around current-context projection.

## Verification and remaining operational work

The [design](../superpowers/specs/2026-11-05-source-event-delivery-design.md) and
[implementation plan](../superpowers/plans/2026-11-05-source-event-delivery.md)
define the required publication rollback, strict backfill, actor isolation,
fencing, duplicate receipt, bounded batch and authority cases. Actual PostgreSQL,
process-kill/restart and populated version-16 dump/restore acceptance must be
recorded for the final combined source. Local database skips are not passes.
The existing full API/reference/web/browser/recovery gates remain required.

At this source checkpoint those final receipts are pending. Record later exact
source/tree, counts, failures/skips, workflow links, independent review and
artifact checks in PR #529; do not rewrite earlier failed or source-specific
receipts as successful combined evidence.

No scheduler, daemon, remote broker/consumer, general event catalog, new API,
Temporal, DBOS, service-delegated authentication, production database roles,
model execution or cloud deployment is installed. Clinical and scientific
consumers, production identity/consent, real-PHI qualification and the remainder
of the full platform remain separate construction and release work.
