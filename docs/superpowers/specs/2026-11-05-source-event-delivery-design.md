# H1 Source Event Delivery Design

## Scope, authority and baseline

The user's instruction to start the proposed outbox/relay increment authorizes
this bounded synthetic infrastructure continuation, including its additive
persistence contract. It does not grant blanket schema, clinical, identity,
external-service, merge or deployment authority. Continue the existing runtime
integration [PR #529](https://github.com/OpenxIntelligence/open-intelligence/pull/529)
under [#104 / WS-08 / CMP-11](https://github.com/OpenxIntelligence/open-intelligence/issues/104)
and the existing [#81 integration thread](https://github.com/OpenxIntelligence/open-intelligence/issues/81).
This advances PF-06, with existing PF-08 consumers and PF-10 controls. The entire
PF-01–PF-10 and PD-01–PD-16 product objective remains open.

The construction baseline is local merge
`cd10a828e499bf65dbbe8eb4ca77207710a5f2b7`: verified worker source
`2312755dc52260c3632c5801b1b7b68041671833` joined with accepted main
`aad241e5cce9a1bcff3e431d63cecd16e948d731`. Earlier #529 acceptance proves its
original tree, not this merge or the event-delivery addition. This document is an
implementation contract; no new acceptance result is asserted.

Reference lineage is [#70](https://github.com/OpenxIntelligence/open-intelligence/pull/70),
inspected at `b1b99b3095b33b8cd7352793c94990b852ea88f9`, and its
`docs/research/PLATFORM_EVENT_CONTRACT_IMPLEMENTATION.md`. That SQLite
`oi.domain-event/1` contract has namespace, subject-binding and authorization
references not supplied by the H1 source journal. Preserve it as reference
lineage. Do not overwrite #70 or claim that this adapter implements its general
wire contract.

## Behavior to establish

An accepted operations-purpose source import must durably record its delivery obligation in the
same transaction as the existing canonical journal event. A separately invoked,
currently authorized worker reconciles that patient's current case context
through the source/question owners and asks Composer to retire only outdated
queued/running work. Delivery can be retried after failure without losing an
obligation, duplicating an accepted effect, disclosing revoked content or
rewriting historical results.

This is at-least-once delivery with atomic, deduplicated consumer receipts. It
does not promise exactly-once execution or causal attribution from one source
event to every affected run. The event triggers reconciliation against the
current whole-case fingerprint.

## Contract and ownership

The narrow contract is **`oi.h1-source-context-event/1`**. Its producer is the
existing canonical `source.original.imported` journal event, validated against
the established source, case and patient owners. Its payload contains immutable
source ID/version and scope references; the authoritative source hash remains
with the source owner and is read through that owner's current projection. It
contains no source narrative,
bearer tokens, inherited grants or clinical conclusions. The existing journal
remains authoritative; the outbox is a dependent transport record.

| Owner | Responsibility |
| --- | --- |
| Existing source / identity owners | Preserve canonical source bytes and journal events; validate source, case, patient and organization bindings. |
| Platform: `source_event_delivery.py` | Coordinate outbox/delivery state, database leases, fencing, bounded retry and canonical audit through explicit callbacks. Own no Composer effects and import no domain consumer. |
| Questions: `PostgresSourceQuestions` | Produce the current whole-case source fingerprint through the existing `list_locked` path, preserving source-read audit and final current-authority checks. |
| Composer: `PostgresComposerRuns` | Compose the transport with its authorization, effect and receipt callbacks; change only its own eligible runs and write its own consumer receipts. |
| Questions/review: `event_worker.py` | Authenticate current runtime credentials, bind one patient/case/actor scope and execute one bounded delivery attempt. |

`PostgresComposerRuns.source_events()` is the composition entry point. It supplies
`authorize_scope_locked`, `consume_locked` and `receipt_locked` callbacks to the
platform transport. The concrete domain callbacks are
`consume_source_event_locked(delivery, *, recheck_authority)` and
`source_event_receipt_locked(claim)`. The questions owner exposes
`prepare_run_context_locked(patient_id, case_id, *, organization, actor, purpose,
recheck_authority, prepare_response)` for current context. Cross-owner writes
and reverse platform-to-consumer imports are prohibited.

## Atomic publication and historical backfill

Add `0020_source_event_delivery` immediately after `0019_composer_runs` and make
readiness require that exact head. The migration introduces:

- `coordination.source_event_outbox`: immutable journal-backed references.
- `coordination.source_event_deliveries`: actor-scoped per-event lifecycle.
- `coordination.source_event_delivery_events`: append-only transition history.
- `investigation.composer_source_event_receipts`: Composer-owned effect receipts.

A journal insertion trigger publishes selected source-import events in the
producer's transaction. Validation must agree with the canonical stored source
and its scope. Outbox failure rolls back the producer; a rolled-back import
cannot leave a transport obligation. Exact import replay must not manufacture
another journal event or outbox record.

Backfill selects existing `source.original.imported` journal rows and applies the
same strict binding validation to both existing source-owner purposes, operations
and research. Only validated operations events enter the Composer outbox. Valid
research imports retain their canonical source custody and journal history
without acquiring an operations delivery obligation. This purpose selection
must occur after lineage validation, for both live capture and historical rows.
A malformed selected historical event, including research history, fails the
upgrade; it is not silently skipped, repaired or converted to a fabricated
receipt. Unrelated event types do not enter this adapter. Existing originals,
commands, history and retry receipts survive the additive upgrade. Downgrade
must refuse to discard populated delivery history.

## Actor-scoped delivery and current authority

Each delivery is scoped to its event, consumer, patient/case and current
organization/actor/purpose. There is no global acknowledgment or cursor through
which one actor can consume another actor's obligations. An event or an embedded
authority reference grants no execution permission.

The worker requires purpose `operations` and the existing four actions:
`patient_read`, `question_read`, `source_read`, `source_brief_export`. It reads
credentials at runtime through `OI_API_EVENT_WORKER_TOKEN_FILE`, with the existing
`OI_API_ACCESS_FILE` fixture and database settings. It persists no credential or
delegation. Reauthentication must keep the original actor, organization and
purpose and still authorize the patient/case at the relevant transaction
boundaries. Wrong-patient, switched-actor, withdrawn or unavailable authority
cannot authorize consumption or receipt disclosure.

Invalid authority on an already claimed delivery, or an invalid event, produces
a bounded dead-letter outcome when the fenced transaction can record it safely.
Failure before an authorized claim is `blocked`; it must not manufacture a
claim, successful acknowledgment or result. A lost database connection can leave
a recoverable lease and is reported truthfully as `unavailable`.

## Claim, consume and acknowledgment

Claims use database time, row locking and a fresh token. A worker may finish only
its current, unexpired lease. A replaced or expired token cannot apply effects,
record an accepted receipt or acknowledge the delivery.

Each consume transaction follows this order:

1. Establish fresh authority and the existing patient/case scope locks, then
   lock and validate the delivery, lease and canonical event. Acquire owned run
   locks only after that order; do not invert it in receipt or failure paths.
2. Obtain the current whole-case source projection from the questions/source
   owners, with source access audit and final current authority.
3. Through Composer alone, select at most **100** matching actor-scoped runs
   whose state is `queued` or `running` and whose accepted fingerprint differs
   from the current fingerprint; make them `stale` with existing run history.
   The existing `composer.run.stale` canonical audit carries `source_event_id`,
   `delivery_id` and `delivery_attempt` so each effect resolves to its receipt.
4. Preserve current-fingerprint runs, terminal runs, accepted results and human
   follow-through tasks. Recheck locks/state so concurrent cancellation,
   completion or another worker cannot be overwritten.
5. Record the immutable consumer receipt keyed by **delivery plus attempt**.
   Commit effects, receipt and the delivery's acknowledgment/continuation state
   together, with canonical audit and final authority checks.

If more eligible runs remain, commit the bounded batch with a partial-success
receipt and requeue the delivery for another attempt. A larger case must not
expand one transaction beyond 100 affected runs or dead-letter merely because
it needs several successful batches. A zero-effect reconciliation may complete
when nothing remains; it is not evidence that the triggering event changed a run.

Receipt recovery after a lost response reauthorizes the caller before returning
the existing bounded receipt. It does not repeat effects or confer result-read
authority. A receipt's observed fingerprint describes the current source state
used for that attempt, not a claim that the historical triggering event caused
all changes.

## Retry and terminal outcomes

The consecutive-failure budget is **three**. Successful progress resets it;
partial-success batches may therefore require more than three total claims.
Retryable failures use a bounded delay. Three abandoned/expired claims without
progress exhaust the budget and dead-letter the delivery. Failure accounting
must not reset simply because another lease was acquired.

`claim_next` returns a running claim, no eligible work, or the explicit terminal
receipt produced when the third expired claim is dead-lettered. The worker must
expose that failure as `dead_letter`, not `idle`. Its bounded output states are
`delivered`, `queued`, `idle`, `fenced`, `blocked`, `dead_letter`, `unavailable`.
Do not include narrative, credentials or exception text in operational output.

Delayed or backfilled events always reconcile against the current context on
each attempt. An old event cannot stale a newer current-fingerprint run just
because that run was created after the event. Completed run/result history
remains immutable; existing fresh result-read checks continue to govern disclosure.

## Acceptance and evidence boundary

Tests must prove the actual PostgreSQL transaction boundaries, including direct
SQL constraint violations, not only mocked method calls. Required scenarios are:

- Same-transaction publication, rollback, exact import retry, strict valid
  backfill and upgrade failure on malformed selected history.
- Independent actor scopes; wrong patient/case/org/purpose; current authority at
  claim, consume and duplicate-receipt return; no persisted bearer.
- Concurrent claim, expired/replaced lease fencing, retry delay, three
  consecutive failures and explicit dead-letter after three expired claims.
- More than 100 affected runs across successful batches, failure-budget reset
  on progress, current/terminal/task preservation and receipt/ack parity.
- Lost response after committed consumption; receipt recovery without repeated
  effects; effect/receipt/audit/ack rollback on failure.
- Delayed historical events, a source change between claim and consume, current
  whole-case fingerprints, concurrent run completion/cancel and final authority.
- Real process interruption, PostgreSQL restart and populated dump/restore,
  including restored revoked access and unchanged original database state.

Existing architecture, API/PostgreSQL, reference, web/browser and recovery gates
remain required on the exact combined source. Record local skips and errors
separately. The implementation plan carries an evidence template; PR #529 remains
the living exact-source acceptance ledger. Passing earlier #529 or other draft
trees does not qualify this increment or a future laboratory/clinical merge.

## Explicitly remaining foundation work

This increment installs no scheduler, daemon, remote broker/consumer, general
event catalog, new API, Temporal, DBOS, model or cloud service. Service-delegated
authority, broad clinical/scientific event consumers, production identity and
consent, operational deployment and specialized scientific engines require
their own bounded work. Existing source/evidence/clinical owners and the full
patient-centered platform objective are retained.
