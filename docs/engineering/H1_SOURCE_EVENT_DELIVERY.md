# H1 Source Event Delivery

**Dependent synthetic integration candidate; combined acceptance pending at
this source-publication checkpoint.**
[PR #565](https://github.com/OpenxIntelligence/open-intelligence/pull/565) remains
the upstream foundation owner. This dependent draft's PR maintains its own exact
combined-source test, hosted acceptance and landing ledger.
The event/execution donor at `79960c49f356e7a4259484f5d1523f9bda365887` is separately
verified in [PR #529](https://github.com/OpenxIntelligence/open-intelligence/pull/529).
That receipt does not qualify the clinical/laboratory/workspace composition or
its installed-schema upgrade automatically.

## Purpose and existing owners

This is the next bounded PF-06 / WS-08 / CMP-11 increment under
[#104](https://github.com/OpenxIntelligence/open-intelligence/issues/104) and
[#81](https://github.com/OpenxIntelligence/open-intelligence/issues/81). It records
an obligation when the canonical source journal accepts an operations-purpose
`source.original.imported` event
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

### Inspect the scoped backlog

Under #104 / PF-06 and OI-013, the operator can inspect delivery state using the
same separately supplied event-worker credential and current scope grants:

```bash
PYTHONPATH=apps/api/src:src python -m oi_api.event_worker --status \
  --patient PATIENT-EXAMPLE --case CASE-EXAMPLE
```

The JSON observation contains `observed_at` and counts for `unclaimed`,
`queued_ready`, `queued_waiting`, `running_active`, `running_expired`,
`delivered` and `dead_letter`. A single PostgreSQL snapshot and database-clock
instant classify that actor's obligations. Another actor's deliveries do not
consume this actor's unclaimed count. No source text, identifiers, lease tokens
or stored credentials are returned.

Inspection appends only an authorized-read audit event, with authority checked
before reading and again after audit insertion. It does not create a delivery,
claim work, renew a lease, reset a failure or retry a dead letter. `--once` and
`--status` are mutually exclusive. Exit zero means inspection succeeded, even
when its counts include dead letters; it does not declare the relay healthy.
Denied inspection returns only `blocked`; storage/provider failures withhold
counts. The existing `idle` execution result means no work was claimed in that
attempt, not that every obligation was delivered.

This bounded operational view adds no migration, scheduler, dependency or
general observability service. General replay and production
monitoring remain separate construction work. PostgreSQL and CLI acceptance
for this addition belongs to its dependent draft, not its parent's receipts.

### Inspect terminal failures

The same current actor/org/purpose/patient/case authorization protects a bounded
terminal-failure listing:

```bash
PYTHONPATH=apps/api/src:src python -m oi_api.event_worker --dead-letters \
  --patient PATIENT-EXAMPLE --case CASE-EXAMPLE --limit 20 --after-event 0
```

`items` contains delivery/event IDs, current revision, attempt/failure counts,
the terminal lifecycle reason code and `failed_at`. Source text, stored
credentials and lease tokens remain excluded. These operational identifiers
are disclosed only by this separately selected mode, not aggregate `--status`.
The command adds an authorized-read audit event and rechecks authority after
that insertion; revoked reads return only `blocked` and roll back the audit.
It never claims, retries or resets an obligation.

`--limit` is 1–100 (default 20). `--after-event` is a nonnegative PostgreSQL
bigint (default 0). Pass `next_after_event_id` for the next page; null means no
further row was seen in that query. Pages are live observations, not a frozen
multi-page snapshot. Restart at zero to refresh: an earlier event can become
terminal later, so this cursor must never be used as a durable delivery
watermark. All three command modes are mutually exclusive; pagination options
require `--dead-letters`. Exit zero means the read succeeded, not that failures
were repaired. Explicit recovery is described below. General event replay remains open under #104 / OI-013.

Use the existing [persistent demo setup](../H1_DEMO.md), dependency lock and
PostgreSQL 16 configuration. The event worker uses `OI_API_DATABASE_URL`,
`OI_API_ACCESS_FILE` and the same synthetic access provider as the application.
`OI_API_ENVIRONMENT` remains `synthetic`. It installs no grants or schema on
startup.

Apply the explicit additive migration through the normal migration command:

```bash
PYTHONPATH=apps/api/src:src python -m oi_api.migrate upgrade head
```

The application requires `0027_source_event_purpose`, the single successor of
`0026_integrated_core`. The existing 0026 no-DDL join retains
`0025_clinical_source_events`, `0023_composer_clinical_join` and
`0023_ehr_lab_ownership_join` as its three published parents.

All 42 migration files from upstream #565 source
`462e6c25f805089fadcb290567045447e6d627b7` remain unchanged, including 0020 and
0027. The published 0020 creates the delivery tables and its original
operations-only capture/backfill. This candidate does not replay #529's edited
version of that historical migration or add a 0028 successor.

The published 0027 installs the source-event binding resolver and replaces the
capture and outbox guard functions. On new writes, both `operations` and
`research` source events undergo canonical metadata/lineage validation before
only operations creates a Composer delivery obligation. Valid research custody
remains with its source owner. The migration performs no historical rescan,
backfill or row rewrite; existing originals, journals, outbox entries, deliveries,
lifecycle events and consumer receipts remain intact.

The supported upgrade scope covers fresh databases and published 0026
installations. Pre-0020 research journal history remains held by the original
backfill with atomic rollback and preserved rows/sequence state; a separate
legacy-adoption path is still required. The
[published construction contract](../implementation/SOURCE_EVENT_PURPOSE_REPAIR.md)
records that boundary.

Downgrading 0027 to 0026 restores the earlier capture/guard functions and removes
the binding helper. Research history is retained, but later research imports can
be refused until the explicit upgrade is applied again. The application requires
0027 for readiness. The original populated-history downgrade guards remain.

The original construction baseline remains
`cd10a828e499bf65dbbe8eb4ca77207710a5f2b7`, joining worker source
`2312755dc52260c3632c5801b1b7b68041671833` and accepted main
`aad241e5cce9a1bcff3e431d63cecd16e948d731`. Earlier combined clinical work remains
recorded in [#564](https://github.com/OpenxIntelligence/open-intelligence/pull/564).
This dependent draft composes the frozen upstream
[#565](https://github.com/OpenxIntelligence/open-intelligence/pull/565) with the
workspace donors; [implementation status](../IMPLEMENTATION_STATUS.md#current-integrated-h1-checkpoint)
pins its source, workspace, laboratory and accepted-main inputs.

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

A `fenced` response does not imply rollback of an earlier committed attempt;
its retained consumer receipt can still exist.

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
Repeating `--once` does not reopen a terminal delivery. An operator can explicitly
request another reconciliation after correcting an authority or transient failure.
Inspect `--dead-letters` first, then name that exact delivery, event and failed revision:

```sh
python -m oi_api.event_worker --recover DELIVERY-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA \
  --event-id 123 --expected-revision 7 --patient PATIENT-FICTIONAL --case CASE-ALPHA
```

The identifiers above are fictional examples; use the freshly inspected receipt.
The command requires the same independently supplied current worker authority and
four grants as ordinary delivery. Persisted-grant mode applies to inspection,
recovery and later execution. The actor, organization, purpose, patient, case,
consumer and source event retain their original identities. Changing actor does
not recover another actor's delivery.

Migration `0030_source_event_recovery` adds immutable recovery receipts after the
published `0029_patient_access` history. It changes no previously published
migration. A request atomically records `(delivery_id, failed_revision)`, queues
the next revision, resets consecutive failures and records attributable history.
Lifetime attempt counts and prior leases, failures and consumer receipts remain
inspectable. The database rejects resets without a matching recovery receipt or
lifecycle event. Populated downgrade is refused.

Only `retryable_failure`, `lease_expired` and `authority_unavailable` can be
recovered. `invalid_event` remains held for a separately verified integrity repair.
A stale revision or a delivery that was never terminal returns `conflict` and
exit 2. A `recovery_requested` response and exit 0 mean that the request committed;
they do not establish delivery or a successful domain effect.

If the response is lost, repeat the same delivery/event/revision. Current authority
is checked again before returning the immutable receipt with `duplicate: true`.
This retry does not reset a later attempt or a subsequent terminal failure. To
recover a later failure, inspect and explicitly request that new revision.
After a successful request, invoke ordinary `--once` to run the existing bounded
current-context reconciliation. It preserves its own fresh context and authority
checks, lease fencing and atomic receipts. This recovery path has no capability
to repeat an external effect or execute a different consumer.

The existing full PostgreSQL, populated migration, permissions, restart and restore
gates must qualify the combined source. The PR records exact-source results;
a parent pass alone does not qualify this new migration or recovery operation.

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

At this combined-source checkpoint those final receipts are pending. The
separately verified #529 donor retains its exact-source results, including
[155 focused tests](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42112478630)
and [878 API tests plus seven recovery gates](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42112478756).
Record the combined source/tree, counts, failures/skips, workflow links,
independent review and artifact checks in this dependent draft's PR. Preserve earlier failed and
source-specific receipts, including #565's earlier research-import error, with
their original scope.

No scheduler, daemon, remote broker/consumer, general event catalog, new API,
Temporal, DBOS, service-delegated authentication, production database roles,
model execution or cloud deployment is installed. Clinical and scientific
consumers, production identity/consent, real-PHI qualification and the remainder
of the full platform remain separate construction and release work.
