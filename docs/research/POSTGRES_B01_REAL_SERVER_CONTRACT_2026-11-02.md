# Open Intelligence — B-01 PostgreSQL domain-integrity execution gate

**Status:** Executable research implementation; **not** a chosen backend, released healthcare database, replacement patient registry, or approved migration.
**Scope:** OI-16 PF-01/PF-03/PF-04/PF-06/PF-10 and first-party PD-01; tests the boundary that the existing patient registry, encounters, immutable notes and shared domain outbox *could* preserve on PostgreSQL. Source of production behavior remains the independently tested SQLite implementations in unmerged PRs #85/#74/#70/#95. No library or database dependency is introduced into application runtime code by this PR.

## 1. Architecture and independent behavior under test

[Migration candidate `001_contract.sql`](../../tools/research/postgres_bakeoff/001_contract.sql) is a disposable *contract fixture* adapted from the existing original project contracts, not a second authoritative database. It creates logical database schemas `identity`, `auth`, `ehr`, `clinical_source`, `platform` under one PostgreSQL service. It deliberately preserves familiar field and entity names, opaque patient IDs, immutable source versions and corrected-notes history, and reference-only events.

| Invariant | Existing source contract | PostgreSQL negative test |
| --- | --- | --- |
| One opaque patient | `patient_registry.py` and PR #85 | Cross-patient row visibility and wrong-subject write denied |
| Scheduled care encounters | `clinical_encounters.py` and PR #74 | One patient can create; another cannot view or insert under wrong patient |
| Note-version preservation | PR #74 | DB trigger rejects historical UPDATE/DELETE, invalid supersession, missing correction reason |
| Source version retention | `store.py` and OI-06 | Corrected source creates a new row; earlier row cannot be mutated or deleted |
| Atomic patient event | `platform_events.py` / PR #70 | Outbox insert and clinical command roll back together on failure |
| Retry/command idempotency | PR #74 | Same request hash returns duplicate receipt; key reuse with different hash fails |
| Revocation and suspension | OI-10 PF-01/PF-02 | DB role-grant removal or suspended patient blocks reads and event operations |
| Two permissive Python drivers | OI-17 | `asyncpg` and `pg8000` both read the same authorized rows; neither sees the wrong patient |

**Executable paths:**
- `tools/research/postgres_bakeoff/001_contract.sql`: PostgreSQL DDL, CHECK/FK, RLS, immutable-history triggers, scoped primitive event enqueue, immutable command receipt function.
- `tests/test_postgres_contract_bakeoff.py`: real-server negative and positive assertions plus three static schema checks.
- `.github/workflows/postgres-contract-bakeoff.yml`: runs the same tests against **PostgreSQL 17.11 and 18.6** on isolated, ephemeral GitHub Actions service instances. Both drivers are installed only for this test job. Captures code SHA, image digest output, pip dependency list, tests and errors.

## 2. License gate (checked against official sources; no release approval)

| Component | Upstream source | Reported upstream license | Position under OI-17 |
| --- | --- | --- | --- |
| PostgreSQL | https://www.postgresql.org/about/licence/ | PostgreSQL License (permissive) | T1 candidate; vendor builds/extensions/managed hosting separately reviewed |
| asyncpg 0.32.0 | https://pypi.org/project/asyncpg/ and https://github.com/MagicStack/asyncpg | Apache-2.0 | T1 candidate for asynchronous APIs; package/wheel provenance must be pinned and scanned |
| pg8000 1.31.6 | https://pypi.org/project/pg8000/ | BSD-3-Clause | T1 candidate for pure-Python compatibility; inspect `scramp`, `python-dateutil`, transitive artifacts |
| Psycopg 3 | https://pypi.org/project/psycopg/ | LGPL-3.0-only | **T2 / hold for legal exception**, do not silently make the default driver |
| PostgreSQL Docker Official Image | https://hub.docker.com/_/postgres | Mixed container OS package licenses, distinct from PostgreSQL source | **Research-only image** until full image digest / SBOM and release obligations checked |

OCI image names are versioned for the experiment (`17.11-bookworm`, `18.6-bookworm`) but **not immutable digest-pinned**. The run records the resolved image digest. Neither a pinned pip version nor a permissive top-level license is a resolved dependency SBOM. Every release must pass the adopted OI-17 exact-version, binary, transitive, asset and security gate.

## 3. Real authorization boundaries

The SQL policy fixture uses disposable **database login roles**, per-patient test grants, purpose, status and `session_user`; the app role cannot write grants or outbox rows directly. The test therefore checks PostgreSQL's row and transaction controls, **not** verified clinical actor authentication, healthcare consent, treating-provider relationships, break-glass policy or PHI safety. The `oi.request_purpose` session setting is not a trustworthy identity assertion; it is filtered by the DBA-controlled grant ledger. A future production deployment must use a trusted, audited policy issuer that supplies patient, role, purpose and consent to the data access layer; patient-attributed credentials must never be derived from raw request-provided setting values. No real names, dates of birth, clinical results or medical records are permitted in this test.

PostgreSQL RLS does not apply to `TRUNCATE` or `REFERENCES`, and owners/superusers may bypass policies; implementation must ensure separate database owner/migrator and strictly least-privilege application roles. `FORCE ROW LEVEL SECURITY` is defense in depth, not enough on its own. Actual application sign-off, source-bound evidence and clinical validation remain separate.

## 4. Experimental evidence and decision criteria

- **Local pre-CI:** Python syntax and static SQL-contract tests can run without a database. If no PostgreSQL server/driver exists, integration tests are **skipped**, not reported as passing.
- **CI (real PostgreSQL):** `PG_BAKEOFF_REQUIRE=1` and installed asyncpg+pg8000 ensure all real-server tests execute; any skip is a **failure**. Workflows record exact Git SHA and test transcript. Re-run at the final PR head and inspect both major-version matrix results before any claim of passing PostgreSQL.
- **Not tested or claimed:** compatibility of all existing SQLite business operations; S3/DICOM, FHIR/HL7 conformance, encrypted PHI, full consent authorization, production scaling/latency/cost, relational migration with data, high availability, backup/restore, event broker replay, regulated clinical decision software, model-weight rights.

**Next acceptance B-01 step after this gate:** write a single first-party PostgreSQL adapter behind the existing `PatientRegistry`/`ClinicalDomainHost`/domain-event interfaces and rerun **all** old and new semantic regressions against it. Prove source amendment invalidation, pending lab status, and rights across transactions and connections; compare signed source/evidence snapshots rather than blindly importing SQLite tables. Keep the source of truth singular; do not create a PostgreSQL copy of the patient master with independent writable state.

## 5. Decision protocol

No founder choice is presumed. If the real PostgreSQL 17 and 18 CI test passes, that establishes **limited feasibility** of the tested invariants, not selection of PostgreSQL or a driver. Measure throughput/latency, operational cost, restore, RLS privilege audits, FHIR roundtrip and migration parity before accepting ADR-OI16-02/03/07. Compare at least asyncpg and pg8000 against Psycopg only with a separate OI-17 legal decision. Each candidate must have a checksum-pinned release lock, an artifact SBOM and an independently reviewed security/data-rights report.

**Related existing sources:** [OI-16 first-party mandate](https://drive.google.com/file/d/1_OBrshpcETQ6lgrcts4JVaVo6kRce8Z0/view), [OI-17 licensing policy](https://drive.google.com/file/d/15jhFNNeXxpmmYKgfEK2SYXzq6GIZlJrZ/view), [163-candidate backend screen #135](https://github.com/OpenxIntelligence/open-intelligence/pull/135), [integration PR #95](https://github.com/OpenxIntelligence/open-intelligence/pull/95), [technology selection issue #59](https://github.com/OpenxIntelligence/open-intelligence/issues/59).
