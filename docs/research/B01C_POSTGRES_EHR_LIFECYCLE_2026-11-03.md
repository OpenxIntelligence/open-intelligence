# B-01c: Existing EHR encounter and note workflows on PostgreSQL

Status: implementation candidate, not merged, deployed, clinically validated or a final database selection.
Parent: PR #148, head `19b1c1319ba543fd0e93744ea3425bd861b0f233`.
Original EHR behavior owner: PR #74, head `a1ce73e4bfa0eabee15e378968c424229a96cb02`.

## Actual implementation

`PostgresClinicalEncounters` runs the original `ClinicalEncounters` schedule, transition, draft, attestation and correction code. The shared implementation gains only `_execute`, `_insert_id` and `_command_transaction` hooks. No copied second workflow or patient registry is introduced. The original 18 SQLite encounter test methods are preserved. The parity child adds nine original source-authorization/integrity regression tests from PR #291 rather than replacing the tests or forking the state machine.

The PostgreSQL adapter uses the PR #148 canonical registry and its owned DB-API connection. All EHR writes, immutable command receipts and reference-only identity journal events share the registry transaction. `FOR UPDATE` on the canonical patient serializes competing commands and patient suspension; optimistic encounter/note revisions still reject stale writes. Identical retries reuse a committed result after reauthorization. Different patients do not share this row lock. This conservative granularity needs workload testing before production.

SQL execution accepts the small reviewed literal-free statement subset emitted by the shared domain, qualifies its four EHR tables explicitly, and converts bound markers to DB-API format. It is not a general SQLite emulation layer, accepts no user SQL, changes no driver-global configuration, and does not interpolate clinical content. Cursors are always closed. Returned dates remain JSON strings.

Migration `003_encounter_port.sql` adds operation, result and timestamp fields to the existing append-only EHR command table. It creates no new patient, source or EHR table. Historical B-01 hash-only receipts are not given fabricated outcomes: an overlapping key fails closed. Migration execution is separate from requests. PostgreSQL construction performs no schema writes.

## Authorization and transaction boundaries

The existing deny-by-default policy and patient-existence checks remain. PostgreSQL commands recheck policy inside the locked transaction and before commit. Reads recheck before returning their assembled result. Revocation detected there causes denial and, for writes, rollback of note/encounter, event and receipt. This narrows a race; it is NOT a distributed lock over an external policy service, authenticated clinician identity or consent implementation.

Attestation remains the original recorded domain state, not a legally valid professional signature. Notes do not become verified clinical conclusions. The adapter uses the existing local identity-domain journal; it does NOT yet connect EHR operations to a deployed broker, full PostgreSQL outbox delivery, source-provenance projection or LIS.

## Evidence and reproducibility

The original 18 SQLite encounter tests passed before changes. A new availability test failed because PostgreSQL encounter persistence was absent. After implementation, those original tests, original six registry tests and the availability test passed (25 local tests). A full local `unittest discover` run collected 279 tests and completed without failure, with 15 skips because PostgreSQL/driver services are absent. Existing broader-suite SQLite ResourceWarnings remain visible in the log. No local PostgreSQL success is claimed.

The inherited hosted PostgreSQL 17/18 matrix runs `test_postgres_*_bakeoff.py` with `PG_BAKEOFF_REQUIRE=1` and fails on any skip. New live tests exercise actual SQLite and PostgreSQL services: full note lifecycle and hashes, retry after reconnect, wrong patient, stale revisions, immutable history, event-failure rollback, concurrent duplicates and conflicting writers, pre-commit and pre-disclosure revocation, suspended-patient retry. Hosted results must be inspected at the exact new head before claiming a pass.

Run locally with a separately provisioned disposable database:

```sh
PYTHONPATH=src:tests:. PG_BAKEOFF_REQUIRE=1 PG_BAKEOFF_DSN='<controlled-test-dsn>' python -m unittest discover -s tests -p 'test_postgres_*_bakeoff.py' -v
PYTHONPATH=src:tests:. python -m unittest discover -s tests -p 'test_*.py' -q
```

Do not point the destructive research setup or invented fixtures at production.

## Verified B-01c integration continuation (3 November 2026)

This is [draft child PR #301](https://github.com/OpenxIntelligence/open-intelligence/pull/301), stacked on original port [#290](https://github.com/OpenxIntelligence/open-intelligence/pull/290). Parent PR #290's real PostgreSQL 17.11 and 18.6 runs [41629516514](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41629516514) initially failed with `TypeError: tuple indices must be integers or slices, not str` in the SQLite oracle of the lifecycle comparison, **before the PG comparison was established**. The test-only correction sets `sqlite3.Row` on that raw SQLite oracle connection, matching the existing domain's named-row contract. No application source/identity record or clinical operation was changed by this fixture correction.

The new tests were run **before** the source repair. [Red PostgreSQL 17/18 run 41640715296](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41640715296) then passed the previously blocked full lifecycle comparison but reproduced **two explicit integrity failures on each server version**: a modified current note row was accepted for attestation and a modified historical row was disclosed. These were test-side altered *returned rows after real PostgreSQL reads*, not destructive edits to source database tables or real patient material. The corresponding [red UI/SQLite run 41640715388](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41640715388) reproduced nine original source-domain authorization/note-integrity failures; its separate Chromium startup also failed before a browser assertion, so no UI red behavior is claimed from that startup failure.

**Green implementation:** the original shared `ClinicalEncounters` domain now implements:
- A final host-policy check before persisting command/event/receipt; repeat-command receipts also require current authorization at disclosure.
- Final read-boundary checks before disclosing encounter listings and historical notes (the PostgreSQL adapter retains its own locked/transaction-end checks).
- Content SHA-256 verification for each current clinical note before subsequent revision/attestation and each historical version before disclosure. Failed integrity checks block publication or further mutation, not erase stored history.
- One shared implementation for SQLite and PostgreSQL; **no new master patient, second EHR, source ledger, schema, API, framework, provider or runtime dependency**. All note content in tests is independently authored fictional text.

At exact child head `b7dc6da07450b9bc7494949aba23cbf94b584cd3`, [real PostgreSQL 17/18 run 41640968947](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41640968947) completed **44 tests on each server, with no skips**. The two added integrity regressions now pass alongside actual concurrent command, patient-revision, immutability, source/permission and two-driver tests. [UI/general suite run 41640968951](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41640968951) passed **288 Python/HTTP tests (15 PG-only tests skipped there by design)**, 16 Node tests and existing Chromium source/keyboard journeys. PostgreSQL tests were executed separately with skip-forbidden CI; the 15 skips in the UI job must not be portrayed as PostgreSQL acceptance skips.

These are software test results, not evidence of real clinical accuracy, lawful attestation, publisher provenance or production-ready revocation. SHA-256 only detects mismatched stored content; a privileged party replacing both content and hash would require stronger source authenticity, custody and signature controls. External policy systems are not transactionally locked by these application rechecks.

The new child must remain draft and source-owner reviewed. Keep the original [#291](https://github.com/OpenxIntelligence/open-intelligence/pull/291) as evidence/ownership for the shared repairs; deduplicate it with this port in a reviewable integration, rather than merging two divergent versions of the clinical encounter module. Integration of LIS/source/Composer on PostgreSQL is the next dependency and is **not** established by this slice.

## Remaining acceptance gates

CI database roles are disposable privileged research roles. Non-superuser service roles, issuer/actor/consent authority, tenant isolation, encryption, clinical signatures, API/UI integration, FHIR mapping, actual source/LIS parity, event delivery, load tests and migration/backup/restore validation remain required. No new driver or runtime dependency is introduced; existing research pg8000/asyncpg versions and OI-17 rights gates remain unchanged. Never infer complete dependency/image or clinical clearance from database tests.

No main-branch merge, deployment, upstream PR modification, real patient input or named-person dataset is authorized by this increment. Deduplicate the imported original EHR module/test when PR #74 and registry PR #148 are integrated. This branch is a bounded step toward the first-party full platform, not a separate product.

References: [PR #148](https://github.com/OpenxIntelligence/open-intelligence/pull/148), [PR #74](https://github.com/OpenxIntelligence/open-intelligence/pull/74), [integration #87](https://github.com/OpenxIntelligence/open-intelligence/issues/87), [backend #59](https://github.com/OpenxIntelligence/open-intelligence/issues/59), [PostgreSQL explicit locks](https://www.postgresql.org/docs/18/explicit-locking.html), [pg8000 DB-API documentation](https://pypi.org/project/pg8000/).
