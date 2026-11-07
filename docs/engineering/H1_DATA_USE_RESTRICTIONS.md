# Purpose-scoped data-use restrictions

Construction increment under WS-02 / #98, OI-013 and PF-02. Parent is
#594 at 8ef436ee5b2d3835befd8c2783e4c0f94357789b. This is an administrative
restriction for independently fictional patients, not informed consent,
identity proofing, guardian authority or production authorization.

## Implemented candidate

The canonical patient registry owns decisions in its existing immutable event
journal (`identity.data_use.decided`). No new patient store, migration or
third-party dependency. A patient row lock serializes decisions; independent
purpose revisions and actor-bound request fingerprints make retries stable.
An old retry returns its historical receipt without reapplying that decision.
Current state must be read independently. Patient identity revision is unchanged.

POST `/v1/patients/{patient_id}/data-use` requires operations purpose,
`patient_read` and `data_use_manage`. The strict synthetic command includes
`request_key`, `expected_revision`, `target_purpose` (operations/research) and
`state` (restricted/unrestricted). Authority is refreshed after locking and
after response encoding; errors roll back the event. GET
`/v1/patients/{patient_id}/data-use/{target_purpose}` independently requires
`data_use_read` and `patient_read`. Credential and journal details are not returned.

The existing shared registry adapter checks the latest purpose restriction for
each protected action. Patient identity/status and restriction administration
remain readable with their separate grants. Restriction removes authority;
lifting one never supplies a missing grant. Unrecorded preserves existing
synthetic-fixture behavior and explicitly does not establish consent. All
responses keep `consent_established: false`. Unknown recorded states deny.

Overview exposes a deliberately read-only restriction inspector, with purpose
selection, denied/unavailable and unrecorded states. Patient changes and session
refresh/disconnection fence delayed responses. Mutation UI and its ambiguous
write recovery are not implemented in this increment; authorized mutations use
the API. Previously displayed data in other sessions is not remotely erased.

## Verification checkpoint

Local: 14 authority-port/OpenAPI/typed-contract tests passed, 719 client tests
passed, including delayed-response/strict-decoder and authentication-loss checks; TypeScript/Vite build,
61-module architecture check, Python compilation and synthetic boundary check
passed. Database methods are implemented but were skipped locally because no
PostgreSQL server is installed. New tests cover actual HTTP restriction/lifting,
independent grants, purpose/patient isolation, encoding/final-authority rollback,
concurrent retry, API restart, and queued/claimed/completed Composer work.
Added a real browser scenario for denied status permission, restriction/source denial, API restart, exact retry, lifting and an unchanged control patient. Hosted verification is pending; no PostgreSQL or browser acceptance is claimed.

Broader local API discovery ran 1,014 tests: 75 errors were socket PermissionError from the execution sandbox and 611 tests skipped for missing PostgreSQL. This run failed; it is not regression acceptance. The separate 14-test authority/contract run passed. The three new authority-port tests exercise all current data actions, fresh purpose-specific decisions, independent grants, malformed recorded state and cross-organization refusal. They use a database-port double and are not PostgreSQL execution evidence.

## Remaining foundation work

This is only the restriction part of PF-02. Positive consent decisions, evidence
of authorization, validity/expiry, delegated authority, granular data classes,
and a safe mutation/recovery UI remain unfinished. The existing Compose recovery harness now includes a restriction before API/database restarts and an actual pg_dump/pg_restore into a separate database. It checks denial, exact historical retry, changed intent, revoked manage grant, restored-only lifting, and unchanged source database. This harness compiles but its hosted execution, together with connected browser acceptance, is still pending.
Do not infer transaction-wide distributed revocation from callback checks:
existing action boundaries retain their own locking/refresh semantics.

The purpose projection uses the existing patient/event journal index and filters
purpose in JSON. This bounded synthetic candidate does not establish production
scale. No merge, deployment or clinical effects are authorized.
