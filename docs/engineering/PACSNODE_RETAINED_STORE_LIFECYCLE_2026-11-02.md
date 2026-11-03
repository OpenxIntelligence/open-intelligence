# B-06 — original-image lifecycle on retained PACS storage

## Decision value

This experiment distinguishes three operational properties: retrieval after an
orderly backend restart, byte/inventory preservation after an identical upload,
and protection of an original when an upload reuses its SOP identifier with
different pixels. The third property must not be inferred from the first two.

The implementation is an isolated extension of [PR #219](https://github.com/OpenxIntelligence/open-intelligence/pull/219)
at `b3b96462cfabd16e65ba4547f4e152df3ee52586`. It retains the existing CaseStore,
source-bound WADO guard, pinned fixture generator, namespace observations and
release-HOLD owner. No product schema, original-custody service, patient API,
authorization model or application dependency is added.

## Preserved original failure and corrective work

The original unpatched experiment at evaluator commit
`c7d6b18cb74fb1dc53e6af92b4cecb3ee08cb75d` completed in
[run 41570215759](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41570215759)
with **lifecycle acceptance false, exit 2**, and
`conflicting_sop_original_replaced`. After HTTP 200 for the conflicting upload,
the object returned under the same SOP UID matched the conflicting submission
exactly. The original-bound guard withheld it and the sibling remained intact.
The first restart and identical replay preserved both originals. The second
restart established amendment refusal before HTTP, not another full byte check.

The original numerical receipt is archived verbatim at
`examples/synthetic/pacsnode_lifecycle_failure_41570215759.json`, SHA-256
`a8dc80f1e5a6b0401cb8824a016e292b088dfca2bc75c55292160db7132e6063`.
The downloaded artifact ZIP digest was independently verified as
`aa7d5e5f24404926f21f1975ea38305cf05154ef8a279e17456b2f626deed7e3`.
These failed observations remain historical evidence after any later fix.

The user authorized a corrective storage experiment. Its
[design](../superpowers/specs/2026-11-02-pacsnode-immutable-sop-design.md) and
[plan](../superpowers/plans/2026-11-02-pacsnode-immutable-sop.md) require immutable
SOP publication, explicit conflicts, concurrency and post-conflict restart.
The isolated upstream patch and provenance live in `tools/imaging/patches`.
This builds a locally modified derivative of the same pinned source; no
upstream release or adopted application dependency is claimed.

The current hosted workflow enables `--immutable-write-checks` and requires
positive exit 0, four exact authored/winning objects, concurrent conflict and
identical upload checks, and three verified orderly restarts. The second
restart now retrieves all originals after conflicts, before further upload;
the third retains amendment refusal. It also runs the same independent Rust
regression before and after applying the patch. The following original
sequence/exit-2 characterization describes the preserved c7d6b18 experiment;
the corrective workflow no longer accepts a negative result as a passing fix.

## Current ownership

- #180 owns the initial real pinned STOW/QIDO/WADO original-byte experiment.
- #207 owns the pre/post source-freshness and original-digest WADO boundary.
- #219 combines that boundary with #201's HOLD classifier, network confinement
  and #137's fictional-data corrections.
- #220 already supplied a limited same-storage restart while enabling native
  OIDC. This continuation keeps configuration fixed and tests duplicate writes.
- PR #242's H1 original-image custody and source-access work remains the owner of
  trusted custody and actor/case/purpose grants. This experiment is not its
  replacement and does not reconcile the sibling OIDC branch into #219.

## Exact tested inputs and dependency boundary

The upstream source stays pinned to
`knopkem/pacsnode@e9b4334477a66967d290add9e0b9afa068f59dc0` and builds its locked
standalone SQLite/filesystem backend. Existing pydicom **3.0.2** is installed
with the repository's SHA-256 pin, without optional codecs. Its MIT/GDCM-derived
dictionary BSD terms and all upstream crate/asset/codec rights retain their
existing review status. Default MinIO deployment is excluded.

The fixture consists of the existing two independently authored fictional 2x2
CT Part 10 objects. Each contains eight bytes of uncompressed pixels. Original
bytes are generated once, retained as immutable expectations in memory, and
never reconstructed from backend output. The existing finite Explicit VR LE
fixture decoder is used for independent identity/pixel comparisons; it is not a
general DICOM parser or clinical image validator.

## Original unpatched executable sequence

1. Start the unchanged binary in a new Linux network namespace with only
   loopback and a new standalone configuration/storage directory. Require both
   HTTP and DIMSE listeners to belong to the measured process.
2. Seed the two objects once. Check exact QIDO row multiplicity, full object
   bytes, raw pixels and the existing source-bound read receipts.
3. Close the first-party ledger. Send SIGINT, wait for exit code 0, reap the
   process and verify both old listeners are unreachable. Restart the same
   binary in the same working directory with the same configuration hash.
4. Reopen the same first-party source database and require identical source
   state. Perform QIDO/WADO **before any further STOW**. Lost storage cannot be
   repaired silently by the test.
5. Replay the exact two original payloads and require the same two logical SOP
   rows and unchanged bytes. Duplicate upstream events/timestamps are outside
   this assertion.
6. Flip one pixel bit in the first object, preserving its UIDs, and submit it
   under the same SOP identifier. Retain the response status separately from
   observed stored state. Retrieve both target and sibling even if STOW rejects
   the request or QIDO fails. A changed object must be withheld by the existing
   original-bound read guard; the sibling must remain intact.
7. Amend the original report, close the ledger and restart the backend again.
   Reopen the ledger, verify the same superseded/current source history and
   require old-source refusal before any WADO request.

The process owner records before/after namespace, process/start identities,
socket ownership, configuration and binary hashes for each successful restart.
An ignored signal, unsuccessful shutdown or changed configuration cannot count
as an orderly restart. Cleanup may force termination, but that is not successful
restart evidence.

## Original receipt and characterization interpretation

`pacsnode-lifecycle.json` retains phase-specific source receipts, original and
returned hashes, exact logical inventory, upload statuses and process facts.
Artifacts exclude DICOM objects, source SQLite files, arbitrary response text
and unknown backend identifiers. Previous phase evidence remains available when
a later operation fails.

| CLI status | Meaning |
|---|---|
| 0 | All criteria in this bounded lifecycle experiment passed |
| 2 | Observations completed, but original/conflict protection failed |
| 1 | The experiment was incomplete or its evidence could not be established |

The hosted workflow permits exit 2 **only** when the complete receipt establishes
the specific changed-SOP overwrite, original-bound refusal, intact sibling,
successful retained-store restarts and all other required observations. It
prints the negative result and retains the original exit code. This is a
successful characterization of a failed acceptance criterion; it must never be
reported as a backend acceptance pass. A missing phase, unexpected blocker or
process/network failure remains failed CI.

`lifecycle_acceptance_passed` remains false for an overwritten original.
`classification` remains `HOLD_NOT_APPROVED` for every outcome. The separate
existing security/adoption assessment is not overridden. The accompanying draft
PR and its exact-head workflow artifact are the result record for a particular
execution; the source does not hardcode a successful external result.

## Upstream source findings confirmed by the original live run

The pinned [STOW route](https://github.com/knopkem/pacsnode/blob/e9b4334477a66967d290add9e0b9afa068f59dc0/crates/pacs-api/src/routes/stow.rs)
writes a blob before separate study, series and instance statements. The
[filesystem store](https://github.com/knopkem/pacsnode/blob/e9b4334477a66967d290add9e0b9afa068f59dc0/crates/pacs-fs-storage/src/fs.rs)
uses a direct overwrite, and the
[SQLite instance store](https://github.com/knopkem/pacsnode/blob/e9b4334477a66967d290add9e0b9afa068f59dc0/crates/pacs-sqlite-store/src/store.rs)
upserts on the instance UID. The original live receipt confirmed that a
conflicting upload replaces the object returned under the existing SOP UID.
The [shutdown handler](https://github.com/knopkem/pacsnode/blob/e9b4334477a66967d290add9e0b9afa068f59dc0/crates/pacs-server/src/main.rs)
uses `tokio::signal::ctrl_c`, so this experiment uses SIGINT.

## Remaining limits

Orderly restart is not crash atomicity, power-loss durability, backup restore,
physical deduplication or upstream-event idempotency. Concurrent-write evidence
belongs to the corrective experiment and its exact derived build receipt.
Two tiny fictional CT objects are not representative clinical imaging coverage.
Source freshness does not authenticate a caller or authorize direct PACS access.
QIDO/STOW conformance, default compressed storage, native patient/tenant policy,
full rights clearance and clinical intended use remain separate HOLD gates.

Backlog mapping: B-06 imaging decision gate; existing OI-006 original persistence,
OI-009 amendment/duplicate handling and OI-013 recovery/access requirements.
This contribution does not mark those wider milestones complete.
