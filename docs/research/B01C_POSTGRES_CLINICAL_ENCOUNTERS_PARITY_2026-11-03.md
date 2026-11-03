# B-01c — First-party EHR encounter/note behavior on PostgreSQL

**Status:** executable adapter and live-server verification candidate; **not** a production EHR, adopted database, clinical-signing system, or authority to use real patient information. Based on the accepted full Open Intelligence patient-centered, first-party product scope and its OI-17 permissive procurement gate. This work is stacked on B-01b (PostgreSQL PatientRegistry), B-01 (database contract), and preserves the original PD-01 code from [EHR PR #74](https://github.com/OpenxIntelligence/open-intelligence/pull/74).

## Actual implementation

`src/open_intelligence/postgres_encounters.py` adapts the *unchanged* first-party `ClinicalEncounters` state machine and its validation/fingerprint/authority semantics through `PostgresClinicalHost` and `_ClinicalSQL`. It does **not** implement a second clinical domain, source registry or patient master. Data remains on the same PostgreSQL connection as the canonical first-party `PostgresPatientRegistry` and `identity.identity_domain_events` in a single command transaction.

The temporary SQL adapter is deliberately narrow: known, constant-source SELECT/INSERT/UPDATE SQL only; explicit table allowlist; bound parameters; generated identifiers returned with PostgreSQL `RETURNING`; all results are materialized inside transactions; all writes require an active first-party transaction. The database's existing EHR patient foreign keys, note-lineage triggers, immutable prior versions, RLS policy *definitions* and B-01 patient tables remain in place.

### Correctness and safety design

- **Patient-scoped serialization:** each clinical command locks the canonical `identity.identity_patients` row using `SELECT ... FOR UPDATE`, rechecks active state and reauthorizes *after acquiring the lock*. Different request keys cannot silently race the same encounter revision; patient suspension interlocks with the command. This is intentionally conservative and may limit single-patient throughput; benchmark and refine when actual workflows justify it.
- **Original clinical behavior:** schedule → in-progress → completed/cancelled; optimistic revisions and forbidden transitions; authored note drafts, attestation record, post-attestation correction reason, immutable note-version history. Attestation is a *domain receipt*, not a legally valid professional signature.
- **Retry behavior:** the original command hash includes actor, purpose, action and structured parameters; the PostgreSQL command receipt stores exact serialized result and is immutable. An identical retry returns the same result after restart; different intent under the same key is rejected. A duplicate command uses the same row-locked patient transaction.
- **One event path:** the original domain invokes `PostgresClinicalHost.append_event`, which calls the existing first-party registry's domain-event journal using the **same transaction**. Neither note bodies nor clinical judgments are stored in event metadata. If appending an event fails, the encounter/note and the command receipt roll back.
- **History:** original note bodies, hashes, supersession identities and correction reasons remain linked in one schema. No clinical source assertion is inferred or promoted to a verified fact.
- **Permissions:** the host's policy callback must be injected. An absent, throwing, stale or unauthorized callback denies reads/writes. A patient row's continued active status is rechecked under lock. This is *not* real IdP/consent proof or protection against a caller running with uncontrolled PostgreSQL superuser privileges.

### SQL migration

`003_encounter_port.sql` *extends* the B-01 table `ehr.clinical_encounter_commands` with full first-party operation and serialized result receipts, without adding a second command table. The existing B-01 `reserve_command()` hash-only research records remain recognizable; the adapter fails if such an incomplete receipt is reused. The migration additionally enforces that note-header revisions increment exactly by one and cannot reassign encounter/note ownership. B-01 already enforces immutable note/source versions and note precursor lineage.

### Real-server matrix and acceptance cases

CI runs PostgreSQL 17.11 and 18.6 and research-only `pg8000==1.31.6` / `asyncpg==0.32.0`, alongside unchanged B-01/B-01b tests and all B-01c tests. The B-01c tests use actual DB transactions and SQL triggers, compare outcomes with the unchanged SQLite service, and reject:

1. Cross-patient access to encounter and notes.
2. Unknown, absent or throwing authorizer; inactive patient.
3. Illegal encounter transitions, optimistic-revision conflicts and silent post-attestation rewrite.
4. Duplicate command reused by different intent/actor.
5. Invalid note lineage, historical UPDATE/DELETE and command receipt mutation.
6. Event append failure that could otherwise commit an encounter or command without its event.
7. Concurrent identical requests (one row and event), and distinct concurrent transitions (one revision winner).
8. Historical note text leaking to reference-only event metadata.

Both separately built repository test suites must remain green. GitHub's PR checkout may be a generated merge SHA: record both the head and the tested Git file blob hashes. No run may be labeled passing until *both* actual PostgreSQL matrix jobs and repository-wide synthetic checks complete at the final commit.

## Boundaries and next work

This is an experimental **same-semantics** port, not a production persistence decision. The `ClinicalEncounters` source contains SQLite-shaped, first-party SQL; the narrow adapter is acceptable for testing but should be replaced with an explicit typed repository contract if the exact SQL surface grows. A production non-superuser/tenant-isolated DB role is absent. The current research service connects using disposable PostgreSQL admin credentials. Existing authorization callbacks are test stubs, not clinical-user authentication, signed consent, break-glass or regulated clinical signatures. Actual durable PF-06 outbox publication, PF-03 SourceVersion mapping, irreversible medical actions, migrations/rollbacks across real data, patient-encryption and disaster recovery are not proven. Do not expose this module through the unauthenticated demo server, use real patient information, or assert HIPAA/CLIA/FDA conformance.

The next integration step is to connect this PostgreSQL-backed EHR host to a first-party, authenticated and revocable domain-policy service; preserve original-source and event authority; then port clinical LIS and source provenance using the *same* one-patient identity rather than introducing another registry. Only independent, scoped approval can move to a regulated patient environment.

**Source trace:** [PR #74](https://github.com/OpenxIntelligence/open-intelligence/pull/74) ClinicalEncounters; [PR #148](https://github.com/OpenxIntelligence/open-intelligence/pull/148) PostgreSQL PatientRegistry; [PR #145](https://github.com/OpenxIntelligence/open-intelligence/pull/145) B-01 schema. These are upstream draft dependencies and must be deduplicated/reviewed before any final merge.
