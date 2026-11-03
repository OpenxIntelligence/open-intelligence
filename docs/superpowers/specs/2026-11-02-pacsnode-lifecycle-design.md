# B-06: retained-store imaging lifecycle experiment

## Intent and scope

Continue the authorized real-backend evaluation with evidence that original
fictional images and their existing source bindings survive orderly restart,
identical retries and conflicting SOP uploads. This is a bounded engineering
experiment, not adoption, patient authorization or a new custody service.

Base: PR #219, `b3b96462cfabd16e65ba4547f4e152df3ee52586`. Retain its #207 source
guard, #201 HOLD classifier, #137 fictional-data corrections and measured test
network confinement. Upstream remains `e9b4334477a66967d290add9e0b9afa068f59dc0`;
only the existing hash-pinned pydicom 3.0.2 core is used. H1 imaging/source/access
integration belongs to its concurrent owner. PR #220 already demonstrates a
limited retained-store restart while changing OIDC settings; this experiment
keeps settings fixed and adds explicit replay/conflict acceptance.

## Approach

Extend the existing confined evaluation runner with a separate lifecycle mode,
reusing its pinned binary, configuration and network evidence. A Python driver
owns two SIGINT stop/wait/restart cycles and keeps the same database, blob
directory and configuration. A separate protocol module uses existing
transport, independently authored fixture generation, CaseStore and source-bound
WADO checks. Its test expectations are temporary experiment files/state, not
an application ingestion manifest or parallel canonical ledger.

Alternatives considered: rerunning the original smoke probe would re-upload
objects and hide persistence loss; merging the OIDC experiment would add
unrelated configuration/authentication changes. The selected approach measures
one storage lifecycle while preserving existing owners and safety boundaries.

## Acceptance and failure evidence

1. Seed two objects exactly once and verify complete files, raw uncompressed
   pixels, exact UID inventory and source-bound receipts.
2. Stop with SIGINT and require successful exit; restart the same binary and
   storage. Reopen the same first-party ledger. Retrieve before any further
   STOW, requiring identical bytes, inventory and source state.
3. Replay identical files and require the same two SOPs and original bytes.
   This says nothing about duplicate upstream events or timestamp side effects.
4. Upload a changed-pixel object with the same UIDs. Observe target and sibling
   even if STOW rejects it. Original preservation must fail if bytes changed;
   the existing source guard must withhold a changed object.
5. Amend the source, restart again and reopen the ledger. An old binding and
   wrong-case binding must fail before HTTP. No new grant is inferred.

Every phase retains bounded digest/identity evidence. Incomplete runs cannot
pass. CLI exit 0 means this bounded lifecycle contract passed; 2 means the
experiment completed but a lifecycle criterion failed; 1 means incomplete.
The CI characterization may retain an explicit exit-2 conflict result, but
must preserve `lifecycle_acceptance_passed=false` and the blocker. Adoption
classification is always `HOLD_NOT_APPROVED`.

Orderly restart does not establish crash atomicity, power-loss durability,
backup restoration, event idempotency or production access control. Licensing,
default codecs, DICOMweb conformance and clinical gates remain independent.
