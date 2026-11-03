# H1: canonical original source → non-executing Composer context preflight

**Status:** Synthetic-only, draft/unmerged integration candidate. This is a real
end-to-end software preflight, not an authenticated clinical investigation,
durable review receipt, model run or permission for healthcare use.

## What is connected

The existing first-party PostgreSQL H1 source owner (#187/#193), its bounded
source-derived Patient World Model (#216), and React Investigations are the only
source of patient/source truth here. A selected current World Model observation
has a canonical `PAT-*`, qualified `CASE-*`, `SRC-*` version, exact source line,
original SHA-256, reported state, date, and a source-set fingerprint.

**New API:** `POST /v1/patients/{patient_id}/cases/{case_id}/composer/source-preflight`

Requires independently authorized `patient_read`, `source_read` and
`composer_context_read` actions for the exact patient, organization, actor and
purpose. H1 accepts `operations` and `research` purposes for general records;
the clinical Composer source preflight is **operations-only**, the available
overlap with the original clinical authorizer. Research is never silently
relabelled as clinical authority.

The bounded request contains `synthetic:true`, exact selected source ID/line,
expected `source_snapshot_sha256`, and a single-line fictional question.
The backend calls the **existing** `PostgresWorldModelRead`, which already
verifies the qualified case and the original bytes + exact authored statement
lines under the existing PostgreSQL case lock. The requested fingerprint must
match the re-read canonical source set; otherwise **409, refresh required**.
An amended/superseded or missing selected source/line cannot be used.
Wrong patient/case, grant, actor, origin organization, or purpose is rejected.

The returned packet includes only the exact current original source statement,
its immutable version/hash/line, the question, the case-source snapshot SHA and
a deterministic preflight SHA. The latter is **not a credential** or durable
execution token. No new schema, patient/source/approval database, event, model
call, external content-rights grant, network request or research answer is
created.

## UI and clinical authority

React Investigations offers **Prepare source-only Composer context** on a
current source statement, using a transparent standard provenance question.
The packet is displayed as a bounded preview with its source identity and
hashes; no model execution, saved question or clinical approval button is
exposed. Loading another patient, switching navigation, refreshing sources or
receiving a denied/stale/invalid response clears the prior preview. No
unsubmitted free-text question is silently discarded by this initial UI.

The existing full Composer and durable review owners (#150/#165/#175/#210)
remain separate. Their contracts require evidence authorization, model and
tool receipts, patient-specific review permission, append-only review history,
and source-change reassessment. **This preflight does not satisfy or copy
those contracts.** It specifically returns:
`source_context_only:true`,
`model_execution_authorized:false`,
`biomedical_evidence_rights_verified:false`,
`durable_question_created:false`,
`durable_review_connected:false`,
`clinical_approval:false`.

The World Model read lock creates a consistent snapshot **during that read**,
not a distributed or perpetual lease. A source can be corrected immediately
after preview. Every future persistence, model execution or clinical-review
write must **recheck the canonical source fingerprint, patient binding,
independent rights and actor authority within its own transaction** and reopen
stale work rather than using this packet as a waiver. The output is a
source-only handoff candidate, not a medical interpretation.

## Acceptance

`apps/api/tests/test_composer_preflight.py` uses actual disposable PostgreSQL
16 and FastAPI to assert successful exact provenance with **zero new patient
events**, deterministic packet fingerprint, independently scoped
`composer_context_read`, wrong-case/patient/purpose denial, a change to the
source set requiring refresh, superseded source/line refusal, and revocation.
The locked React tests cover no implicit call, strict response shape,
fabricated clinical authority, stale source rejection and patient/session
switch clearing. Hosted Chromium checks original v1 → packet → amendment →
stale rejection → fresh v2 packet → grant revocation against the real API.
Inspect exact-head CI before claiming the full stack passes.

Remaining blockers: validated clinical identity/consent, least-privilege
database roles, PHI protections, trusted rights provider and publishing
rights, broad document ingestion, the actual clinical Composer question/run
and existing durable human review queue, clinical validation, branch
reconciliation, and approved deployment. No merge into main.
