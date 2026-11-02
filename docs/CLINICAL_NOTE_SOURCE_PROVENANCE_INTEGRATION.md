# Clinical note → canonical source provenance: first-party integration seam

**Status:** synthetic-only implementation candidate; stacked above canonical patient/encounter integration [PR #88](https://github.com/OpenxIntelligence/open-intelligence/pull/88), identity [#85](https://github.com/OpenxIntelligence/open-intelligence/pull/85) and encounter [#74](https://github.com/OpenxIntelligence/open-intelligence/pull/74). **No clinical signing, identity verification, PHI processing, EHR deployment or approved treatment function.** Preserve the existing first-party full-healthcare architecture and the temporary CaseStore as a synthetic source adapter.

## What is actually wired

`ClinicalSourceProvenance` joins **existing**:
- canonical, opaque patient IDs owned by `PatientRegistry`;
- immutable note versions and encounters owned by `ClinicalEncounters`;
- exact, original `source_versions` and assertion line references owned by `CaseStore`.

There is **no copied patient record, source byte store, extracted clinical fact or competing world-model ledger**. The only new table is an immutable *reference relationship* `clinical_note_source_refs`; all originals remain in their respective owner tables. It operates on the **same SQLite transaction host** as patient identity, clinical note and original source data.

### Required trust/authority boundaries

Both an actor/purpose/action authorizer and an independently established, revocable `patient_id ↔ synthetic_case_id` binding are injected. Missing or denied policy fails closed. Neither the temporary test predicate nor a similar patient name establishes real identity or consent. A suspended canonical patient is blocked. No public HTTP endpoint is added.

Only an existing **draft** or **draft correction** note version may gain a source reference. The exact source version must be *current*, bound to the explicit case, and contain the cited authored assertion line. Every link is append-only and creates a reference-only identity event within the same caller-controlled transaction; event failure rolls back both link and event. Repeating an identical link is an idempotent no-op. An attested version cannot acquire retrospective references, and no source link can confer clinical review authority.

### Source amendment semantics

An original pathology source amendment supersedes the previous source version in its existing owner. `note_sources` preserves the original source reference with original text/hash, dates, specimen and line, but changes the **derived** `provenance_state` from `current_source_unreviewed` to `source_superseded_review_required`. The historical signed note body/version is **not** rewritten. This reference is **not** automatically inherited by new or attested note versions, nor does an amendment automatically create a professional review/signature. Future EHR and Patient World Model projections may consume this explicit stale-reference indication after qualified authority validation.

## Combined patient-context read projection (synthetic only)

The same bridge now exposes `context_snapshot(patient_id, case_id, actor, purpose)` as an **authorized read-only projection** over clinical encounters, immutable note version metadata (not note bodies), original source/version metadata, current source-authored observations, and immutable note-to-source links. Its explicit contract tag is `oi.synthetic-clinical-context/1`; it is **not** a comprehensive Patient World Model, real clinician API or automated clinical interpretation. It keeps unknown/negative statuses and stale note-source references distinct, so a future Composer can receive a bounded, permitted view rather than a copied patient record. The method is not exposed through unauthenticated HTTP routes or a new UI.

A pathology amendment changes the current source assertion set and the derived `note_versions_requiring_source_review` list, while historical note SHA and earlier source versions remain unchanged. A new assertion does **not** silently become a professional conclusion or signed record.

## Runnable acceptance

`PYTHONPATH=src python -m unittest tests.test_clinical_source_provenance -v` with repository-root imports available, or standard repository discovery.

The actual tests cover: single source/version/line link; no duplicate reference on retries; note correction/attestation history retained; amendment staleness without rewriting the historical note; no cross-patient/cross-case source/note access; denied actors and revoked binding; blocked suspended patient; out-of-range assertion; audit-event transaction failure with rollback and retry; persistence after restart.

## Not solved by this slice

- Trusted real-world patient↔institution↔case matching or consent/delegation. Current mapping is an **injected synthetic test predicate**; production needs one owned, auditable, revocable authoritative binding, not a second registry.
- Full clinical-note lifecycle projection into an authenticated FHIR/clinical API, clinician verification or legally valid signature. `attest_note` is only the existing synthetic first-party domain state machine.
- General clinical document ingestion, source extraction, external guideline rights, specialist model reasoning, treatment execution or PHI-safe deployment.
- Automatic invalidation of every clinical interpretation and Patient World Model belief: currently only the **provenance reference's read-time freshness** changes. The full downstream dependency graph and review queue require a separately accepted integration with [#82](https://github.com/OpenxIntelligence/open-intelligence/pull/82), source ownership and clinical authority.
- Cross-domain transactional outbox [#70](https://github.com/OpenxIntelligence/open-intelligence/pull/70) integration: the link writes an identity-host event reference, not an externally delivered or recipient-acknowledged domain event.
- No final UI navigation, schema framework, DB production engine or model choice is adopted.

**Next gate:** reconcile [issue #87](https://github.com/OpenxIntelligence/open-intelligence/issues/87) and [#81](https://github.com/OpenxIntelligence/open-intelligence/issues/81) source-binding and authority semantics; then integrate a typed, version-bound read projection into the existing clinician workspace and Composer without any bypass of patient or evidence rights. Test after combining the *actual source and event branches* at an exact pinned head.
