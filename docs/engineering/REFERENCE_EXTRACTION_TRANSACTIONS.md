# Reference extraction transaction integrity

Backlog: **OI-006 — Persist immutable sources and typed assertions**.
Owner: the existing `CaseStore`/A1 reference intake path; no parallel ledger.
Candidate: PR #591. Synthetic engineering only; not the H1 PostgreSQL runtime.

## Behavior and reproduced defect

`record_extraction_proposal` already reserves the standalone writer before
checking source identity, current state, original hash, quotation and duplicates.
When an existing caller transaction was present, however, an insertion error on
the second field left the first field pending. A caller that caught the error
and continued could commit that partial batch without receiving its assertion
IDs. Retrying then rejected that first field as already asserted.

The nested path now uses a uniquely named savepoint around validation and the
whole insertion batch. A normal insertion failure rolls back only that batch.
Earlier caller writes, prior successful proposals, caller savepoints and the
caller's final commit/rollback ownership remain intact. A database-level whole
transaction rollback still takes precedence; cleanup preserves the original
error rather than trying to release a savepoint that no longer exists.

Field-level validation drops remain intentional partial acceptance and are
returned explicitly. This repair concerns an exception during an otherwise
accepted batch, not changing that kept/dropped contract. Read-only validation,
standalone writer reservation and exact-source checks are unchanged.

## Verification before publication

Baseline source: `45337c05ba6c647eb252f70838e3f72bb0d8af1e`.
The retained hosted merge checkout was
`c9ea1f7266c16f1008b6180a9c319078cc090df4`, with the identical tree
`310b9e8c7562d64cc5ed3b5fa641b7c67d346fae`.
Artifact `13555373539` from reference run `42327881106` was downloaded and
verified against SHA-256
`47a8fa5dd780bd9444c53cd95d7ec699679263d2c0b5ada2bf7bd8cce5c6af6c`.
Its 761 source files and modes reconstruct that tree exactly. Its archived
unit result is 1,266 tests in 172.124 seconds, OK. All five baseline workflows
completed successfully. These results are historical, not acceptance of the
subsequent savepoint repair.

Five new real SQLite regression methods cover failed-batch isolation, complete
retry IDs, rollback through a caller's savepoint, database-initiated rollback
with original-error preservation, and validation-error recovery.

Tests-first command:

```sh
PYTHONPATH=src:tests python -m unittest test_extraction_transactions -v
```

Before the repair: 15 tests, exactly two failures. The failed-batch test found
`accepted-first` still present; the retry test reported `finding_already_asserted`
for the orphaned first field. The existing ten tests and three new control cases
passed. No mocked database writes or sleeps are used.

After the repair:

```sh
PYTHONPATH=src:tests python -m unittest test_extraction_transactions test_data_integration test_interoperability test_cardiology_end_to_end -v
```

78 tests passed in 14.964 seconds, with no failures, errors or skips. The
15 transaction methods are included in that total, not additional tests.
Python compilation, both legacy JavaScript syntax checks and `git diff --check`
passed. A local full `unittest discover -s tests -v` attempt was terminated by
the 240-second execution limit before completing and is **not a pass**. The
local environment also could not acquire the existing hash-locked PDF parser
because package-network resolution was unavailable; no lock, version check or
PDF assertion was changed to work around that limitation.

## Remaining acceptance

Fresh hosted reference, browser, web, API/recovery and contract results must be
attributed to the new exact source or an explicitly identified merge checkout.
Independent review and merge remain outstanding. Keep draft, unmerged and
undeployed until those gates are satisfied. No schema, migration, dependency,
external data acquisition, model behavior or clinical capability is added here.
