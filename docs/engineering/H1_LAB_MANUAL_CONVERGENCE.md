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
