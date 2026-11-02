# Open Intelligence — B-01b: Native PostgreSQL patient-registry port and behavioral parity

**Status:** Actual source-code adapter, database migration and executable tests. **Proposed / unmerged**; not a completed platform migration, approved driver dependency or PHI/clinical release.

**Source hierarchy:** The existing first-party `PatientRegistry` in PR #85 (and integrated source in PR #95) is the **single owner** of first-party patient creation rules and API behavior. The PostgreSQL adapter imports its `_key`, `_digest`, `_now`, exception classes, and `PatientRegistry._allow`. This PR includes those unchanged upstream files only because PR #85 remains unmerged; remove duplicated commits when the owner branch is integrated. One underlying database/one canonical patient ID exists per configured deployment; SQLite and PostgreSQL are alternative persistence backends, not simultaneously running patient masters.

## Implemented

- `src/open_intelligence/postgres_registry.py`: synchronous `PostgresPatientRegistry` storage adapter using an injected non-autocommit DB-API connection. No runtime package import, migrations or network listener at module import. A tested research environment supplies `pg8000==1.31.6` (BSD-3-Clause) as the PostgreSQL DB-API driver.
- `tools/research/postgres_bakeoff/002_registry_port.sql`: an **additive** database schema migration layered over the prior passing B-01 `001_contract.sql`, **without** creating another patient table or replacing that clinical schema. Adds the original `identity_create_receipts` and `identity_domain_events` equivalents in schema `identity`, source-owned immutable triggers, qualified organization/receipt guard and original patient-identity immutability/monotonic suspension guard.
- `tests/test_postgres_registry_bakeoff.py`: checks the *same public first-party API* against the SQLite reference and live PostgreSQL. Reuses the same first-party authorization callback and idempotency payload digest. Comparisons cover create/deduplicate, subject/organization scoping, permission denial, purpose and actor conflicts, active/suspended state, immutable events and creation receipts, patient/origin identity immutability, same-tx event rollback and retry races.
- CI extends the original B-01 PostgreSQL 17.11/18.6 matrix; no new application/runtime install. Static checks run locally without a server; CI requires a live database and fails on any skipped B-01/B-01b test.

## Important ownership and security boundaries

| Question | Implemented in this PR | Remaining production gate |
| --- | --- | --- |
| Patient identity owner | Exactly one `identity.identity_patients` table and one opaque patient ID within a single PostgreSQL deployment | Verified identity proofing, cross-organization matching/reversal and patient relationships; no automatic merge |
| API and request semantics | Same `create_patient`, `get_patient`, `list_patients`, `suspend_patient`, `require_patient`, `append_event` signatures as first-party Python reference; imports canonical validators and policy-gate method | Clinical user login, scoped verified consent, capability-based policy decision and PEP, provider identity |
| Idempotency | `(organization,request_key)`/fingerprint; concurrent speculative patient is rolled back if other request wins | Review database isolation behavior and retry policies under realistic multi-instance loads |
| History | Append-only creation/event receipts, origin identity immutable; monotonic active→suspended state | Full account lifecycle incl legal holds, recovery, merge/unmerge, and deletion/retention jurisdiction |
| Events | Identity journal append uses caller-owned SQL transaction; if appending fails, patient/encounter write is rolled back | First-party `oi.domain-event/1` payload plus durable outbox inside the *same* PG transaction, delivery/idempotent consumer, amendment invalidation |
| DB roles | Disposable CI uses a privileged `postgres` account to install SQL and run the adapter. Original B-01 separately proves RLS using synthetic non-admin DB roles | Dedicated non-superuser identity-service account; secure stored functions and least-privilege grants; mapping between IdP/patient/role and policy/consent version |
| Existing clinical domain use | This slice validates **patient-registry operation parity only**, not direct use by the current SQLite `ClinicalEncounters`, LIS or CaseStore APIs | Domain-owned PostgreSQL repositories/ports, source transaction parity, migration/rollback and clinical functionality acceptance |
| Licensing | Uses only Python stdlib at import time; test runner uses pinned pg8000 and asyncpg research drivers | Package wheel/transitive NOTICE/SBOM/VEX, host OS/OCI image, no accidental LGPL driver or model/dataset dependency |

**No patient data:** All tests construct independently fictional IDs. No active patient system, human consent record, clinical signature, actual protected health information, research dataset, or external clinical connection is used. The domain remains **deny-by-default** when the trusted policy is absent or throws; passing code tests cannot establish authenticated or legally valid consent.

**Do not** expose this adapter to the current unauthenticated demonstration HTTP server. Do not treat successful database role tests as real person identity. A clinically deployed instance needs policy-/tenant-/purpose-aware credentials, structured audit/incident review, encryption/key governance, migration strategy and negative access testing before it can be considered for a regulated pilot.

## Falsifiable acceptance gates (B-01b)

1. PostgreSQL 17.11 and 18.6 service tests pass all original B-01 tests and new B-01b tests on both versions, with **zero skips** and without changing the release safety allowlist.
2. Each API-level public method mirrors the SQLite reference for accessible states and error categories, except opaque IDs/timestamps naturally differ. Same request/organization yields identical ID and one creation event; new actor/purpose on same request is rejected.
3. Concurrent same-key requests from independent PostgreSQL connections commit exactly one patient, one immutable receipt and one creation event; conflicting actor intents cannot share a receipt.
4. Failed event write undoes patient creation; a domain event and encounter in the same connection roll back atomically on failure. An event call without a transaction is rejected.
5. Direct database attempts to rewrite creation receipts, events, assigned organization/patient ID, or skip revision checks fail, even if the application forgets to validate them.
6. Independently verify final source/test/workflow blobs against GitHub Actions' checkout; log exact package versions and PostgreSQL image digests. This is **NOT** end-to-end clinical workflow parity.

## Why this order makes architectural sense

The existing working applications (patient registry, clinical encounters, LIS, source/audit records, Composer) already prove a bounded clinical evidence model on SQLite. Moving only the patient registry behind an interchangeable PostgreSQL connection is an incremental, inspectable path towards replacing SQLite **without rewriting patient logic, bypassing permissions, introducing another patient master or selecting an entire new architecture prematurely**. Follow with a separately tested `ClinicalDomainHost` EHR repository and transaction/outbox adapter, then source version and LIS persistence, then full end-to-end acceptance. Every step must retain one authoritative patient ID, source provenance, amendment history and human authority boundary.

## References

- [Canonical first-party PatientRegistry PR #85](https://github.com/OpenxIntelligence/open-intelligence/pull/85) and [EHR / LIS continuity integration PR #95](https://github.com/OpenxIntelligence/open-intelligence/pull/95).
- [Passing initial B-01 PostgreSQL schema contract PR #145](https://github.com/OpenxIntelligence/open-intelligence/pull/145).
- [OI-17 commercial and legal policy](https://drive.google.com/file/d/15jhFNNeXxpmmYKgfEK2SYXzq6GIZlJrZ/view).
- [OI-16 full first-party platform mandate](https://drive.google.com/file/d/1_OBrshpcETQ6lgrcts4JVaVo6kRce8Z0/view).
- [pg8000 1.31.6 on PyPI](https://pypi.org/project/pg8000/1.31.6/); [asyncpg 0.32.0 on PyPI](https://pypi.org/project/asyncpg/0.32.0/); [PostgreSQL license](https://www.postgresql.org/about/licence/).

All technology choices and numbers remain prospective until final artifact, compliance, test and architecture review. **No automatic merge/deploy.**
