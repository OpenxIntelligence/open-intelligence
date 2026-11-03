# H1 — Canonical PostgreSQL source-derived Patient World Model

Status: DRAFT, synthetic-only software engineering. Not a clinical service.
Owner dependency chain: PostgreSQL registry #172, binding #182, source #187, receipt #193, React Records #200/#209.

## Purpose
Open Intelligence must ultimately connect patient identity, clinical and biological observations, chronology, published biomedical evidence, human review and coordination. The clinical World Model and Composer/evidence/review workflow are already developed separately in the existing SQLite reference stack (#147/#156/#175/#210).

This H1 increment is only a read-only source-derived projection over the **single existing PostgreSQL original-source owner**. It is not another identity, record, clinical, evidence or review database. No new migration, model prompt, clinical assessment or decision engine is added.

Endpoint: GET /v1/patients/{patient_id}/cases/{case_id}/world-model
Contract: oi.pg-source-world-model/1
Permissions: existing patient_read AND source_read, exact patient, origin organization, active case binding, actor and purpose. This does not confer source_original_read.
Projection owner: apps/api/src/oi_api/source_world_model.py
Typed API: apps/api/src/oi_api/patients.py
Browser validator: apps/web/src/source-world-model.ts
UI: existing React Journey via RegistrySession and WorldModelView.

The handler invokes PostgresSourceVersions.list exactly once. That owner verifies the raw source history and complete current assertion inventory, then prepares the projection and typed response under its existing patient/binding locks. The final authority refresh and read-receipt commit occur after preparation. No second SQL truth is stored. See the [bounded source-integrity continuation](H1_SOURCE_PROJECTION_INTEGRITY_2026-11-02.md) for its tests-first evidence and exact-head verification boundary.

## Invariants

1. Current and superseded original versions are shown separately. Every current reported observation retains exact source ID, document version, SHA-256, statement and source line. Old originals remain history and are not rewritten.
2. Pending, indeterminate, not-reported, not-assessed and conflicting are unresolved *source-reported* statuses, never automatically treated as negative findings.
3. A source disagreement means a reported-versus-negative pair only for the same explicitly recorded specimen, event date and finding key. Null specimen IDs are not assumed identical; different dates are not fused. No clinical adjudication.
4. All displayed statements remain unreviewed with clinical_meaning=null. The API explicitly reports clinical_interpretation=false, research_review_invalidation_integrated=false and composer_execution_authorized=false.
5. A deterministic SHA-256 snapshot_fingerprint over patient, case, current exact source versions and observations changes on amendment. It is not a signature, permission token, approval or execution authorization. Future Composer execution must re-read source ownership and validate context under current authority at write/execution time.
6. Read permissions are server-enforced on every request, with patient/case/organization checks. The client rejects forged contract fields or mismatched anchors, clears stale projections on identity/source changes and drops out-of-order replies. Credentials remain in page memory, not URLs or storage.
7. React Journey is read-only. No model call, alerts, clinical operation, patient export or signed review. The rights-qualified evidence/report/review libraries in #210 have not been exposed through this H1 API.
8. The read receipt identifies authorized prepared source disclosure; it is not delivery confirmation or clinical approval. Integrity, preparation, final authority or audit failures withhold the view and commit no new read receipt. External authority is not transactionally locked with PostgreSQL or network delivery.
9. Opening/closing an original cancels a concurrent pending World Model read without stranding Journey in loading. Late replies cannot restore it, and recovery requires an explicit retry. Completed projections remain available across those actions.

## Reproducible acceptance

The H1 API workflow runs actual PostgreSQL 16, FastAPI and source-owner integration tests for first/empty source, source amendment, provenance/history, unchanged restart, source conflict, patient/case isolation, revoked rights and invalid fake approvals. The H1 frontend workflow builds pinned React/TypeScript and uses actual PostgreSQL/FastAPI/Chromium to exercise first World Model, amendment fingerprint change, historical preservation, inert source text, and source-read revocation.

Tests are software evidence on independently authored OI-SYNTHETIC-REPORT/1 files, not clinical accuracy, real patient identity, actual consent, legal data rights or production release. Exact CI commit/head must be checked; old branch tests do not validate the current head.

## Next gates

Reconcile original EHR/LIS/clinical SourceStore data contracts with the canonical PG patient and source domain without copying their authority. Add real governed question/investigation persistence tied to the same case and current source fingerprint, then connect existing biomedical content-rights checks, Composer v2, human review, report and follow-through. Real PHI requires separate clinical, legal, security and operational release reviews.

No Sid Sijbrandij patient data or derivative synthetic replicas are allowed. His publicly described methods remain product research inspiration only.
