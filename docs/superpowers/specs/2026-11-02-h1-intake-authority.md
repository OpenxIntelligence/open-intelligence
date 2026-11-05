# Final authority for H1 source intake and record receipt

## Intent and ownership

Continue the verified patient-source-question foundation in #244 at
`3b6c466950852c20f99d57a70dd196fd2862571a`. Source reads and question persistence
already refresh the original bearer before completion. Source import and the
existing record-request received pointer currently depend on entry-time grants
and construct their response after their owner transaction has committed.

Establish the same final authority boundary for these two existing writers before
the governed report handoff depends on them. Preserve one patient registry,
case binding, source owner, request owner and immutable event journal. This is a
bounded repair under the existing engineering mandate, not a new architecture.

## Behavior

- Import, amendment, newly quarantined original, duplicate original and duplicate
  quarantine all prepare their response and refresh authority before the existing
  source-owner transaction commits. An amendment denial restores its predecessor
  to current and leaves no new source, assertion, quarantine row or event.
- A record received pointer and its idempotent retry follow the same boundary
  inside the existing request/source locks. Denial appends no received event.
- Use the same original bearer. Require unchanged actor, organization and purpose,
  current patient membership, patient_read, and the independently required action
  grants: source_import for intake; record_request_receive and source_read for
  received pointers. Expired/absent authority and provider failure fail closed.
- Prepare validated JSON bytes and HTTP status under the transaction, before the
  final authority check. DTO construction, JSON rendering and event failures roll
  back. Response transport occurs afterward and is not proof of delivery.
- Preserve existing source/reference IDs, exact bytes/hashes, amendment rules,
  quarantine semantics, successful HTTP statuses and duplicate outcomes. A restored
  legitimate grant may retry; earlier committed history is never removed.

## Approach and alternatives

Reuse each writer's existing transaction and add mandatory recheck_authority plus
optional prepare_response callbacks, following the existing source/question
pattern. The HTTP adapter prepares JSONResponse before invoking the final grant
check. Keep existing read/question helpers unchanged; use their established
reauthentication checks for these writes as well.

A route-only recheck after calling the writer is insufficient because the write
has committed. A second permission store or a new receipt table would duplicate
existing authority/history and is unnecessary. Broad PostgreSQL governed-report
migration is separate: #262 owns review convergence and the active source-brief
owner already handles source-only report transport.

## Acceptance and limits

Actual PostgreSQL 16 plus HTTP tests must withdraw grants or change identity after
real database work, check both the response and durable rows/events, and prove a
restored-authority retry. Test duplicate and quarantine paths, late JSON rendering,
provider failure, amendment rollback, and independently required grants. Do not
replace PostgreSQL persistence with mocks. Test hooks preserve the actual operation
and only change the operator-controlled fictional credential fixture at a defined
boundary. Keep inherited API, migration/recovery, reference and React/browser gates.

No new dependency, migration, clinical state, model or patient data. This improves
last-check behavior for the synthetic authentication adapter; it cannot make an
external grant service and PostgreSQL/HTTP delivery atomically revocable. Revocation
after the last successful check and ambiguous network delivery remain explicit
limits. Main and other owners remain unchanged; publish an isolated draft only.
