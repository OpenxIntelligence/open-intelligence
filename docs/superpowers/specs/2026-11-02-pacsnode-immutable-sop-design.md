# PACSNode immutable SOP storage correction

## Authorized intent and evidence

The user requested a storage-layer correction after PR #248 at
`c7d6b18cb74fb1dc53e6af92b4cecb3ee08cb75d` returned changed pixels under an
existing SOP Instance UID. The inspected real-backend run `41570215759`
completed with lifecycle acceptance false and exit 2. Its receipt is retained
verbatim in `examples/synthetic/pacsnode_lifecycle_failure_41570215759.json`.
The artifact archive SHA-256 is
`aa7d5e5f24404926f21f1975ea38305cf05154ef8a279e17456b2f626deed7e3`.

The required invariant is: new SOP creates immutable content, exact byte replay
preserves it, and different content under the same SOP is explicitly rejected.
Concurrent requests and requests after restart must obey the same rule.

## Approach and ownership

Implement a reviewable patch to pinned upstream
`knopkem/pacsnode@e9b4334477a66967d290add9e0b9afa068f59dc0`, applied only by the
isolated standalone SQLite/filesystem evaluation. Keep the upstream pin and
record the patch digest, derived source/lock hashes, and compiled binary hash.
This is an Open Intelligence experimental derivative, not an upstream release.
H1 original-image custody, source authority and patient grants remain owned by
PR #242; this adds no competing application ledger or identity model.

An in-process mutex cannot protect independent writers. Checking existence
before writing permits a race. Atomic creation of the final raw file alone can
expose partial content and only protects one composite study/series/SOP path.
The selected approach stages complete data and a persisted integrity claim,
then atomically publishes one canonical claim per SOP without replacement.
The filesystem BlobStore enforces this for every ingestion caller, including
STOW and DIMSE. A matching claim must match hierarchy, length, digest and bytes.
Only the winning or matching claim may publish the raw-DICOM retrieval alias.

SQLite instance identity and series parent links must reject conflicting
rebinding instead of silently updating an existing object. STOW and DIMSE use
`store_instance_hierarchy`; the SQLite override commits all three metadata
writes in one transaction, rolling back prior study/series changes on conflict.
The compatible default for other metadata backends is outside this guarantee.
Legacy unclaimed
storage fails closed; this task does not invent a migration. Retained UID claims
prevent conflicting UID reuse after deletion. S3 behavior is outside this patch.

## Observable contract

- Exact replay is a byte and logical-inventory no-op. Event/timestamp idempotency
  is separately unproven.
- A single-object conflicting STOW request returns HTTP 409. Multipart partial
  results must remain distinguishable from complete failure.
- Existing bytes and the sibling object remain exact after every rejected
  conflict. A global SOP cannot be rebound by changing study or series.
- Concurrent different-content creation has one acknowledged winner; expected
  bytes come from the authored submission, never from retrieval.
- Concurrent identical uploads preserve one logical object.
- A retrieve-only check after a subsequent orderly restart preserves all
  original/winning objects. Amendment refusal remains before HTTP.
- The OI read guard continues to check original digests; its own tamper
  regressions remain separate from backend rejection.

HTTP 409 and partial-success 202 follow the distinction in DICOM PS3.18
section 10.5.3, without claiming complete DICOMweb conformance:
https://dicom.nema.org/MEDICAL/DICOM/current/output/chtml/part18/sect_10.5.3.html

## Acceptance and limits

Run a regression against the unchanged pinned filesystem store first and retain
the expected assertion failure. Apply the digest-pinned patch and run the same
test plus independent concurrency, fresh-process, integrity and metadata tests.
The corrective real-backend lifecycle invocation enables immutable-write checks
and requires exit 0, all phase evidence, three verified orderly restarts and
unchanged source refusals. The prior negative result stays visible permanently.

`HOLD_NOT_APPROVED` remains mandatory even if this bounded correction passes.
PACS authorization, full conformance, dependency/asset rights and clinical
validation remain separate gates. Orderly restart and atomic publication do
not establish power-loss recovery, backup restore or distributed transactions.
A failed metadata transaction can retain an unindexed immutable filesystem
claim. It cannot replace an existing claimed object; reclaiming or migrating
such state requires a separate reviewed procedure.
