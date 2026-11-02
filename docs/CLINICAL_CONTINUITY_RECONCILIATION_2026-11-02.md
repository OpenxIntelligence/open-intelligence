# Open Intelligence — one patient / EHR / LIS / source continuity contract

**Status: implemented, independently rerunnable first-party backend slice; draft integration PR #95 only.** This document extends, and does not supersede, OI-16 (PD-01, PD-03, PF-01–06), OI-06 original source/provenance rules, OI-10 access/consent boundaries, or OI-17 release and licensing controls. The full platform remains the product objective. No Next.js, real-patient data, licensed clinical content or new third-party package is used.

## Why this integration is needed

Previously passing code had **several independently correct but disconnected parts**: canonical patient creation (#85), EHR encounter/note history (#74), transactional events (#70/#95), actual lab orders/accession/QC/release (#56), reviewed patient-to-case links and pending lab-evidence projections (#94), and anchored clinical note-to-source associations (#124). A passing individual branch does not guarantee that a **single, authorized patient** can inspect these same original records without promoting stale findings, trusting an unreviewed source match, or creating a second Patient World Model.

This integration reuses the existing source-ledger and operational services. No patient copies, normalized clinical beliefs, attested clinician sign-offs, data imports or separate replacement agent architecture are created.

### Implemented components and ownership

| Component | Single owner / write authority | This integration |
| --- | --- | --- |
| Patient and status | PF-01 `PatientRegistry`, `identity_patients` | Opaque ID, deny suspended subjects |
| Original clinical observations | PF-03 existing `CaseStore` `source_versions` / `assertions` | Read/check exact original source and amended state, never duplicate |
| EHR encounter and authored note versions | PD-01 `ClinicalEncounters` | Read immutable versions, distinguish draft/attested/correction, prevent retroactive source-links |
| Lab orders, accession, verification and release | PD-03 `ClinicalLabOperations` | Check exact release→accession→specimen→QC→source→assertion and latest source/QC |
| Patient–case binding | PF-01/09 reviewed `CanonicalLabBridge` | Explicit qualified `(organization, system, source subject)` reviewed link; detect disagreement with already persisted adapter identities and fail closed |
| Transport and receiving evidence | PF-06 shared `platform_outbox` / `lab_world_model_review_candidates` | Verify event hash and exact original lab source receipt; receiver candidates remain pending, never clinical beliefs |
| Authored-note source provenance | PF-03 `ClinicalSourceProvenance` | Immutable note-version→source-version→assertion-line links; source amendments generate review-required read state |
| **New read interface** | First-party `ClinicalContinuityView` (new module) | Joins only references under independently checked patient, actor, purpose, lab and clinical source-binding policies; no second patient or source table |

### Integration sequence, using actual original services

1. The existing patient registry creates a stable opaque `PAT-*` identifier (the caller/test cannot infer identity from demographics); the EHR domain records an encounter and versioned authored note using the canonical host and transport, **not** the competing `EventedClinicalHost` from #89.
2. A trusted source-acquisition workflow would review a `(source organization, source system, local subject)` mapping to the same patient. Current tests provide an explicitly **fictional, non-verified** reviewer and test policy. Neither string is a credential or genuine consent.
3. The first-party LIS performs an order, specimen accession, QC and release; source/version events remain in `CaseStore`. Its `LinkedLabCaseStore` hook publishes strictly reference-only envelopes in the *same write transaction*.
4. The existing ordered lab consumer validates issuer, patient binding, case, original receipt, current source, latest QC and assertion, then creates a `pending` **review candidate** in a separately owned receiver connection; this does **not** make a medical conclusion.
5. The authored-note source service references the original source and exact assertion line only while the note version is an editable draft. The original source bytes and historical note text remain with their owning systems.
6. `ClinicalContinuityView.snapshot` independently checks authorization and the active patient–case binding. It returns EHR note/source **pointers**, lab pending review **pointers**, provenance freshness and the combined review queue. The lab candidate is rechecked against the authoritative outbox hash, original `events` release receipt, accession/specimen, assertions, source version, order source, and latest QC at **every read**. Both authorization/binding gates are rechecked before returning the combined response, so a revocation occurring between the source read and the receiver read fails closed. This still is not an atomic two-database snapshot.
7. A source amendment does not mutate a historical note or old lab release. The read view marks both `source_superseded_review_required`; a new source/report/QC/release creates a new pending item, without rewriting history. Changed QC similarly marks an old release `quality_changed_review_required`.

### Explicitly fail-closed identity reconciliation

`adapter_identity_bindings` (source ingestion) and `identity_case_bindings` (reviewed canonical patient↔case mapping) currently exist in two different bounded contexts. They have **different owners** and cannot be treated as competing patient registries. To close an observed safety gap, `CanonicalLabBridge` now validates both directions for an existing qualified adapter tuple *at bind time and on every subsequent read/command*. If the source adapter later associates the reviewed case with a different subject under the same organization/system, or associates the reviewed subject with another case, it raises `PatientRegistryDenied` and surfaces no patient evidence. It never automatically reassigns a patient or silently merges source identities. This is a compatibility guard, **not** permanent acceptance of two identity authorities. The ultimate PF-01/09 policy/API and migration remain an owner decision.

### Read result fields and boundaries

`oi.clinical-continuity-review/1` returns `{patient_id, case_id, encounters, note_versions, note_source_links, lab_evidence_candidates, review_required, patient_world_model_clinical_belief, source_coverage, snapshot_consistency}`. For lab candidates the source is `reported_state_as_stated`; `clinical_assessment='not_established'`. Freshness is calculated, never stored as a new clinical belief: `current_source_pending_clinician_review`, `source_superseded_review_required`, `order_source_superseded_review_required`, `quality_changed_review_required` (or defensive order cancellation handling). Every *current* candidate still needs an authorized human reviewer, not just an absence of conflict.

This is **not a globally atomic distributed snapshot**: the original source and receiver are separate SQLite connections. It is a read-only reconciliation, with original-case current state rechecked on read. A production federated snapshot, event-triggered invalidation of materialized projections, durable review disposition, host-side PHI policy/identity, encryption and audit remain P0 prerequisites for a real-patient release. Do not expose this read interface on the unauthenticated local demo HTTP server.

### Reuse and avoidance of duplicate implementations

- Imports original #94 `clinical_lab_bridge.py` with a targeted adapter-identity conflict guard. The original upstream source blob was `f0493b3ed0cdb0a8b76eac431591922c54b932da`. #94's original integration tests are reused, but pointed at #95's already-canonical `CanonicalEHRHost` rather than introducing a second event host.
- Imports original #124 `clinical_source_provenance.py` unchanged (source blob `1feb2bc8ae7845138e936b5994fbe2f745ec9aea`). Its test fixture is corrected to explicitly grant `patient_context.read`; the service's deny-by-default rule is unchanged.
- Adds **one** new pure read module `src/open_intelligence/clinical_continuity.py` and a separate acceptance suite `tests/test_clinical_continuity.py`; all new assertions operate against actual first-party DB services and independently authored fictional reports.
- Retains the first-party EHR/LIS/outbox sources from #95. Do **not** merge or vendor #89's `clinical_event_host.py` into this composition. Do not auto-close upstream PRs; reconcile file ownership and copy/squash dedup before final merge into `main`.

### Reproduced negative acceptance cases

- Amend a released laboratory report: old note/source anchors and old lab review candidate require review; old source and note versions stay immutable.
- QC changes after release: old candidate is no longer current; report's lab state is not inferred as valid.
- Issue a new release from corrected source: two historically distinct candidates with only the new source marked current pending human review.
- Reject a receiver candidate with changed specimen, a missing original outbox, edited outbox payload/hash, or falsified source event receipt.
- Reject an untrusted actor, wrong-purpose read, revoked reviewed case binding (including revocation during a combined read), or suspended/unknown canonical patient.
- Reject a later source adapter binding that conflicts with a previously reviewed patient–case mapping and vice versa.
- Do not leak original note body or invent clinical interpretation, diagnosis, laboratory safety conclusion, test eligibility or patient-specific treatment advice.

**Verification:** a clean composite of PR #95's passing archived source-under-test, #94's source and #124's source, with deterministic compatibility changes only, runs the current existing Python test suite and the additional full-journey tests. Record exact local totals and hosted CI separately: the *GitHub Actions checkout* may use a PR merge commit, distinct from the PR head. The prior #95 hosted workflow proved its earlier scope, not this new integration until this commit is built by CI.

### Remaining blocking production gates

Canonical verified identity and proxies, purpose/consent engine with durable signed decisions, authoritative patient↔source reconciliation and rollback semantics, PostgreSQL migration/domain privileges, strict operational authorization, signed note/clinical review, FHIR R4/HL7 contracts, lab analyzer/QMS and CLIA workflow validation, source amendment/invalidation events for durable projections, cross-database consistency, PHI security and region/purpose controls, accessibility, independent clinical evaluation, and explicit OI-17 supply-chain/license clearance. **No release or real-patient data is authorized by this work.**
