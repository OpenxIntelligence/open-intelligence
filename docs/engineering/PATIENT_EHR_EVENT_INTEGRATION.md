# First-party integration checkpoint — Canonical patient → EHR → outbox → consumer

**Status: draft integration candidate. Not a new product architecture, not a merge instruction, and not a deployable clinical system.**

## Exact source composition
This integration branch is based on [patient identity owner PR #85](https://github.com/OpenxIntelligence/open-intelligence/pull/85), reuses byte-identical reviewed source/test/document blobs from [EHR PR #74](https://github.com/OpenxIntelligence/open-intelligence/pull/74) and [event transport PR #70](https://github.com/OpenxIntelligence/open-intelligence/pull/70), and adds `clinical_event_host.py` and an actual cross-module regression test. The upstream branches remain unchanged. Do not merge or cherry-pick this integration branch independently of owner review: it contains overlapping upstream source additions and must be reconciled before a production candidate.

## Actual executed workflow (fictional IDs only)
1. Trusted *test* policy allows an actor to create one opaque patient through `PatientRegistry`.
2. The same database connection is passed through `EventedClinicalHost` to the actual `ClinicalEncounters` service.
3. EHR commands persist a scheduled encounter, state transition, note draft and recorded attestation. `append_event` appends reference-only metadata into the same connection and enqueues `oi.domain-event/1` atomically.
4. A second receiving database applies four ordered events through `consume_ordered` to its own read projection. Retries are idempotent; changed subject or version is refused.
5. Restart, missing outbox table and patient suspension tests guard durable, fail-closed behavior.
6. No event exposes note text, diagnoses, medication dosing, demographic details or clinical source documents.

## Ownership and authority
- Patient identity ownership is in one registry; no `cases` table is introduced in the integrated database.
- EHR retains ownership of encounters, note versions and attestation records. An 'attested' code status represents an authored workflow event, **not a legally valid clinical signature**.
- The outbox carries metadata references only. `authorization_decision_ref=None` is deliberate: this synthetic policy does NOT issue qualified real-world access grants. No real patient data should be entered.
- A receiving domain must separately enforce trusted identity/issuer, purpose, consent, source and specimen/episode context. Strict event order is not proof of clinical correctness.
- No Next.js or third-party runtime dependencies introduced.

## Limits and next integration
This proves only the *patient → clinical encounter → event → receiving projection* contract using one SQLite-backed host and an independent receiving connection. It does not implement verified person matching, PHI protection, consent/proxy authority, cross-hospital reconciliation, production queue/broker, FHIR interoperability, LIS accession, pathology, radiology/PACS, genomics, clinical AI, or deployment. Clinical review and security validation remain external gates.

Next join [LIS PR #56](https://github.com/OpenxIntelligence/open-intelligence/pull/56) once its stacked patient-adapter requirements [#51/#53](https://github.com/OpenxIntelligence/open-intelligence/pull/53) are reconciled. Avoid competing patient identity or source databases. For each domain transition test the same patient/specimen/source identifier and actual executed states separately from orders and requests.

[Integration tracking #87](https://github.com/OpenxIntelligence/open-intelligence/issues/87) · [Notion architecture](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876).
