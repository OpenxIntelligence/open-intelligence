# Isolated PACSNode immutable SOP patch

This directory contains an Open Intelligence experimental correction to
`knopkem/pacsnode@e9b4334477a66967d290add9e0b9afa068f59dc0`. It is applied only
inside the existing synthetic standalone SQLite/filesystem evaluation.
PACSNode remains an unapproved candidate. This is not an upstream release,
an adopted application dependency, a general migration or clinical software.

## Provenance and rights

`pacsnode-immutable-sop.json` records the exact upstream commit, patch SHA-256,
changed file list and expected derived source hashes. CI verifies them, uses
the derived locked dependency graph, and records the compiled binary hash.
The patch changes dependency edges only to packages already resolved by the
upstream lockfile; no new crate version is selected.

The upstream copyright and declarations are reproduced unchanged in
`NOTICE.pacsnode` from that exact commit. Upstream declares MIT in NOTICE and
Cargo.toml, but does not provide a conventional root LICENSE at this pin.
This preserves the existing rights review limitation. The patch does not
select a distribution license for Open Intelligence or clear all upstream
dependencies, codecs, bundled assets or commercial use. No upstream affiliation
or endorsement is claimed. Default S3/MinIO deployment is excluded.

## Invariant

The filesystem BlobStore publishes a complete object through one atomic
no-replace claim per SOP UID, with persisted hierarchy and byte integrity
metadata. Both STOW and DIMSE use this store. Exact replay preserves the
existing content; different content or a different parent hierarchy conflicts.
SQLite identity guards keep existing instance and series parents immutable.
Both ingestion paths call `store_instance_hierarchy`; the SQLite override
rolls back all study/series/instance metadata changes when any part conflicts.
Other metadata backends retain a compatible sequential default and are outside
this standalone transaction guarantee. Filesystem publication still precedes
metadata; a failed metadata transaction may leave an unindexed immutable claim.
Legacy files without claims fail closed; no data migration is attempted.
Claims remain through deletion to prevent reuse of a SOP for different bytes.
Garbage collection and migration require a separate reviewed design.

The invariant concerns the representation submitted to storage. Default
compression/transcoding, S3 storage, event/timestamp idempotency, crash/power-loss
recovery and distributed transactions are not established by this patch.
The live test explicitly stores uncompressed Explicit VR Little Endian objects.

## Evidence

The original unpatched failure remains in PR #248 and
`examples/synthetic/pacsnode_lifecycle_failure_41570215759.json` at evaluator
commit `c7d6b18cb74fb1dc53e6af92b4cecb3ee08cb75d`, run `41570215759`.
The corrective workflow first proves a new independently authored storage
regression fails on that unchanged upstream. It then applies this patch and
requires the same regression, storage/metadata/API tests, concurrent real HTTP
uploads, exact post-conflict hashes, and retained-store restarts to pass.
Every evaluated build retains `HOLD_NOT_APPROVED`; the measured run belongs in
the PR and project records, not a hardcoded success claim in this source.
