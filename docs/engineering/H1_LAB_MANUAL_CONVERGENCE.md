# Laboratory and manual-task migration convergence

4 November 2026. Bounded continuation of OI-006, OI-009 and GH-112; independently fictional data only.

The laboratory source candidate and the optional manual-passage task candidate both extend `0015_manual_report_context`. Neither published `0016` migration may be renamed or repointed. This candidate composes their existing owners and adds the no-DDL `0017_lab_manual_convergence` join. Current HTTP readiness requires that exact joined revision.

| Frozen input | Scope |
|---|---|
| [#469 at 8ff6e9e5a0389a1142ca479a6705c599cbda88e7](https://github.com/OpenxIntelligence/open-intelligence/commit/8ff6e9e5a0389a1142ca479a6705c599cbda88e7) | Verified laboratory source custody, exact original hashes, typed source-reported observations, amendment/retry and recovery |
| [#462 at d96809cdb663f7eafb076dd493bb8f56f17b3caa](https://github.com/OpenxIntelligence/open-intelligence/commit/d96809cdb663f7eafb076dd493bb8f56f17b3caa) | Optional exact manual-passage dependency on canonical care tasks, selective reassessment, stale completion denial; includes #457 storage ancestry |
| [main at a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709](https://github.com/OpenxIntelligence/open-intelligence/commit/a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709) | Accepted baseline inherited through #463; rechecked before composition |

## Resulting behavior

Both dependent schemas coexist under the existing patient, source, question and task owners. A task may explicitly bind an immutable manual-passage revision; an annotation correction marks that task for reassessment without attaching the same dependency to unrelated source-only tasks. The response exposes revision and freshness metadata, not the original quotation. Stale manual-dependent tasks cannot be marked completed.

Databases at either historical `0016` revision must explicitly upgrade before the current API serves them. The task owner's existing historical-migration allowance includes the published laboratory-only revision, which legitimately predates the manual child table. A missing child at the joined head, at the manual head or at an unknown revision remains an error.

## Acceptance

`test_lab_manual_convergence.py` checks the single graph and three actual PostgreSQL upgrade paths: populated laboratory-only, populated manual-task-only, and populated two-head databases. Existing rows and sequence positions must survive; the two-head join must leave columns, constraints, indexes, functions and triggers unchanged. Historical source bytes and exact command retries are checked through authenticated HTTP after upgrade. Removing the join must preserve both histories and disable readiness; the existing populated downgrade guards must still reject erasing either owner.

The new four-test migration suite and the inherited document/image historical-graph regression run before full API acceptance so migration failures surface early. The historical assertion explicitly checks the published manual-task migration rather than assuming the current head has one parent. All existing API/reference/browser, dependency-rights and seven HTTP/restart/backup/restore/revocation gates remain required. API timeout increases from 30 to 40 minutes because verified #469 run [41883746990](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41883746990) nearly consumed the previous budget. No assertion or recovery step is removed.

Local checks: eight pure FHIR parser tests, Python compilation, whitespace checks, one-head static graph and byte-for-byte preservation of both published migration files passed. Local checks do not substitute for PostgreSQL or Chromium. Combined hosted acceptance is pending at this source checkpoint; the draft PR records results tied to its exact head. Historical parent passes do not qualify this composition.

No dependency, external service, production identity mechanism, clinical interpretation, licensing decision or deployment is introduced. Review-return manual binding, clinical validation and production release remain separate work.


## Populated manual-task recovery on the accepted application

This section supersedes the pending-composition language above for the application
baseline, but does not claim acceptance of this new recovery composition. The
application was consolidated by #481 and is on `main` at
`62e218e1e2bd6996bb126fcc1ea956fcf18199e6`. The existing recovery-only draft #483
is being reconciled with that mainline; it is not a new runtime implementation.

### Preserved sources and bounded changes

- Main supplies the patient application, persistent fictional demo, laboratory
  workspace, all published migrations through `0017_lab_manual_convergence`,
  dependency locks, authority boundaries and all seven recovery stages.
- Recovery source: #483 at `076c08a67d9712a2e27ec188ed4c5f41509b8a11`. Its three
  verification files are retained byte-for-byte:
  `apps/api/tools/manual_task_recovery.py`,
  `apps/api/tests/test_manual_task_recovery_assertions.py`, and
  `apps/api/tools/verify_sources_compose.py`.
- Main's source recovery driver differs from the donor only by the nine added
  lines that invoke the populated-task recovery proof and retain its receipt.
  No existing assertion, timeout, workflow, runtime, schema or dependency changes.
- The current `docs/EXECUTION_BACKLOG.csv` is retained unchanged. Its newer
  accepted-demo notes must not be replaced with the donor's older pending notes.
  Work remains mapped to OI-006, OI-009, GH-112 and issue #442.

### Recovery behavior to establish on the combined head

The existing source Compose gate creates a separate fictional patient, one
canonical question, one saved manual-passage revision and two tasks: an explicitly
bound task and an unrelated source-only control. It restores readable, stale and
binding-revoked databases with actual PostgreSQL dump/restore, compares all owned
rows and sequence state, and exercises API/database restarts. A correction after
restore must stale only the bound task. Its attempted completion must have no
business effects; the source-only task must still complete. The canonical
question's structured source remains current, so its staleness cannot explain
selective denial. Exact retries and independent grant withdrawals preserve
identity and history without disclosing original quotations. The original
source database remains unchanged.

The `oi.manual-task-recovery/1` receipt is added to the existing source recovery
artifact only after every assertion passes. Negative controls reject lost
provenance, changed business rows, wrong or reused audit receipts, and sequence
drift. Read audits may change only as explicitly expected; no clinical approval
is manufactured.

### Evidence and acceptance boundary

The prior #483 source has recorded successful API/recovery run `41930712845`
and browser run `41930712898`; those are donor evidence, not qualification of the
new mainline composition. Its retained web archive SHA-256 was independently
recomputed as `17cefe6f37340bfba465a1ae40eac46e6fb9a82a0e5861b704a5988d43baffd6`.
The accepted #481 web archive independently matched
`e5d65fc26533c1de2c7afb98b708f332ac05777f626adebf84f24edf86f2887b`.
A Git comparison confirms main differs from that tested #481 source only in
three research documents; using the full main tree preserves all three.

Local continuation evidence: 13 existing recovery-assertion tests passed before
composition; all 17 recovery-assertion tests passed afterward. Python compilation
and whitespace checks passed. These are proof-helper tests, not a local database
or browser run. Docker/PostgreSQL are unavailable. A full local baseline API
attempt ran 257 tests with 67 errors and 27 skips in an environment missing
`pydicom` and using `pypdf` 5.9.0 rather than the pinned 6.21.4. The composed full
API diagnostic was interrupted without a final result. Neither is counted as
passing acceptance.

Fresh hosted validation must cover the exact reconciled commit: full hash-locked
API/PostgreSQL contracts, populated migrations, all seven restart/restore stages
including this populated dependency, original reference checks, React/rights/build,
actual Chromium and the persistent fictional demo. Preserve donor and main
ancestry and verify the final tree. New combined hosted results and independent
review remain pending at this source checkpoint; the draft PR records their
subsequent exact-head outcome. No merge to main, deployment, real patient data,
clinical validation or manual-dependent Review-return behavior is authorized.
