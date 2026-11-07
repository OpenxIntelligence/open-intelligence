# H1 execution capability catalog

Workstream: #103 L1; OI-009/OI-013. Baseline: #584 at
`37063baa4e93b8a48dad4e76fdabbdde438352b3`. This is a bounded continuation of the
existing [durable execution](H1_DURABLE_EXECUTION.md), not a new agent runtime.

## Inspect without executing

```sh
PYTHONPATH=src:apps/api/src python -m oi_api.worker --capabilities
```

The command needs the existing Python runtime dependencies but no credential,
patient, case or database connection. It returns contract
`oi.execution-capability-catalog/1`, a deterministic SHA-256 of the registration
metadata, `runtime_readiness: not_checked` and `authorizes_execution: false`.
Mixed inspection and execution arguments are rejected. Existing `--once
--patient ... --case ...` invocation and live authority checks remain required
for execution.

Only **source-question-brief/1** is registered. Its owner is questions-review,
its input contract is `oi.pg-source-world-model/1`, its output contract is
`oi.synthetic-source-brief/2`, and its required actions are patient_read,
question_read, source_read and source_brief_export. Listing is not permission,
clinical qualification, worker liveness or confirmation of a healthy database.

## Registration and execution

The platform owns immutable `CapabilityDescriptor` / `CapabilityCatalog` value
objects in `oi_api.execution_capabilities`. The Composer owner constructs its
catalog in `oi_api.composer_capabilities`; there is no public registration route,
module-path loading, shell command, external service or credentials in it.
Duplicate identities, malformed contracts and unknown versions fail closed.
There is no latest-version inference. Input and output copies cannot mutate
registrations. A catalog accepts at most 128 descriptors, each with at most 32
unique action names; these limits bound metadata, not runtime resource use.

New enqueue and completion require an enabled exact registration and the declared
input contract. Stored-result validation also checks its declared output
contract and retains all prior exact question/source/lease/authority checks.
The worker refuses a disabled registration before reading a credential or
claiming queued work. Disabling is a code-owned release change, not a live
control-plane command. All worker/API processes must run compatible releases;
this catalog does not provide atomic cross-process hot revocation.

An exact already-committed enqueue retry still recovers its receipt under current
authority. Disabling does not erase the version's registration, original results
or lifecycle history. A retained completed result may still be read if the
existing authority and source-freshness rules allow it; revocation still denies
access. Removing a historical descriptor entirely is not a supported retirement
path. A new kind additionally needs reviewed implementation, persistent/wire
contracts and qualification; metadata alone never supplies an executor.

## Evidence and limits

Local focused tests: 25 passed. Architecture tests: 31 passed, with the boundary
gate covering 63 modules/10 owners and retaining 86 legacy symbol imports.
The three actual-PostgreSQL retirement/result/retry tests are implemented but
not locally executed because the qualified imaging dependency and PostgreSQL
runtime are absent. Full local API discovery failed: 393 tests, one failure,
88 errors, 27 skips; the missing `pydicom` import prevents application-backed
coverage. The exact-head hosted gates, not parent passes, must qualify this tree.

The metadata hash is not a binary signature and is not added to persisted runs.
Existing run-kind pins and stored-result digests remain unchanged. No migration,
new dependency, HTTP wire contract, model call, plugin marketplace, scientific
pipeline or clinical capability is introduced. Independent review, production
identity/delegation, broader engine registration, deployment and clinical
qualification remain outstanding. Draft/unmerged/undeployed.
