# Clinical knowledge final-read consistency repair

**Goal:** Reject a stale clinical/evidence packet when the last external provider read overlaps a patient-source, EHR-note or LIS-quality change.
**Scope:** Bounded repair inside existing draft PR #132. Reuse #130/#95/#124/#93 owners. No new architecture, schema, runtime package, patient store, provider, endpoint or permission grant.
**Baseline:** PR head `1e992ea1a0608962fb6f36d06ebb093c092cccf2`; original adapter blob `e51a02bf522b4ee61dfd06f100364ecc36056707`. Authenticated CI artifact #13174872232 SHA-256 `6adf91afa3c77ce881e1e449f8aaf9ac8049bc124ea7793a8d37a5091b3a2fc8` was checked before extracting original source.
**Requirements:** existing OI-008/009/013/018; connected first-party patient/source/clinical-evidence work #81/#87. Preserve explicit pending-review and non-atomic-read disclaimers; no real or public patient data, retrieval, model execution or clinical conclusion.

## Cause

The clinical/source fingerprint was checked before the second provider call. Equal external metadata/rights payloads allowed a source amendment, new record, revised note or failed QC arriving during that last call to escape patient-context validation. Final permission checks and alignment of already-captured assertions did not detect those changes. This is a deterministic callback-boundary gap, not a claim to solve all distributed races.

## Execution and acceptance

- [x] Read original authority, source, knowledge and clinical/LIS code and existing tests.
- [x] Run the existing focused knowledge/clinical tests: 24 executions passed (includes imported upstream test cases).
- [x] Add seven real-module regressions: amendment with fresh retry; new source; QC change; note revision; binding revocation; unrelated-case update; stable read-only control.
- [x] Correct one new fixture's encounter key to the actual returned encounter ID before interpreting its failure. On the unchanged implementation, four behavioral failures and three passing preservation controls were observed.
- [x] After the last provider call, repeat the complete existing authorized clinical Composer snapshot and compare with the previously accepted snapshot. Return and align the final view; preserve final access checks. No automatic retry or new clinical write.
- [x] The seven regressions pass; related knowledge/clinical-authority suites pass 61 test executions; Python compile and original JavaScript syntax pass locally.
- [ ] Confirm exact pushed head and hosted full-suite results; local full-suite attempt reached its execution limit and is NOT reported as passing.
- [ ] Independent code/clinical review and parent-stack reconciliation before merge.

## Review focus and limits

Full clinical projection, not just source hash, is required to catch QC/note changes. Only the affected patient context is compared; unrelated-case work must not force rejection. A fresh explicit retry after amendment can return new source state, always pending human review. Rights records and actor callbacks remain synthetic declarations, not verified publisher licenses or clinical credentials. One additional clinical snapshot costs extra reads. No distributed atomicity is established: data, permissions or rights can change after any preflight; consequential consumers must independently revalidate at use. No merge, clinical deployment or data-use authorization follows from tests.
