# H1 — durable source-linked investigation question intake

**Product status:** Draft, fictional-only engineering. No clinical release,
PHI, verified clinician, real consent or research-content rights. This is
the canonical PostgreSQL port of the existing first-party
`CaseStore.add_question` question-intake domain, NOT a replacement for
the clinical review owner or its pending/approval/signature ledger.

## Canonical source convergence — 3 November 2026

This branch reconciles the existing question owner in #238
(`2d90999078fb854fd665634c3001e68cfb6f2cca`) and its focused final-authority
follow-up #243 (`f7bbe4b07011596a7e5de9522e5531a89f53f40b`) with the verified
source/React owner #234 (`65eafebd9fda221dc79789619133c78c6d01dc60`). The existing
#223 Composer preflight remains the consumer; #216's competing World Model
representation is not imported.

The canonical context is `oi.pg-source-world-model/1.snapshot_fingerprint`.
It is distinct from each `ACCESS-*` read receipt and the source-index digest
recorded in the audit event. Preflight output uses
`oi.synthetic-source-composer-preflight/2`, declares
`source_snapshot_contract: oi.pg-source-world-model/1`, and carries its source
access receipt separately. The deterministic `preflight_sha256` excludes that
changing receipt. The question-history response uses
`oi.synthetic-source-questions/2` and records each row's fingerprint contract.

Preserve migration `0006_source_questions` and its question owner. A follow-up
migration records fingerprint provenance: existing rows retain the legacy
`oi.synthetic-postgres-world-model-sources/1` classification and always require
reassessment; new rows explicitly record the canonical contract. Do not rehash
or rewrite their immutable historical sources, question text or original hashes.

The source owner provides one transaction-required read path for validated
materialization, typed preparation, final authority refresh and read-receipt
append. The question owner uses it inside its existing sole transaction.
Independent question/Composer grants are refreshed before disclosure or commit,
including duplicate and post-event paths. Source read events are expected;
exactly one `investigation.question.created` event accompanies a new question.

**Tests-first evidence:** at `5f3925d9694911875e8c15662c22223de965db6c`,
[hosted run 41569238470](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41569238470)
ran 146 tests against PostgreSQL. The 145 inherited tests passed; the new
cross-branch acceptance failed at its first preflight request with HTTP 404
instead of 200, after successfully verifying the existing World Model's stable
fingerprint and changing receipts. No setup errors occurred. The subsequent
test steps cover save/retry, amendment conflict and historical reassessment.

Final implementation evidence belongs in [draft PR #244](https://github.com/OpenxIntelligence/open-intelligence/pull/244)
and the existing engineering progress records. Upstream success is not evidence
for this branch. The separate migration test upgrades an actual legacy row,
compares every original field, and requires reassessment even when its stored
hash happens to equal the canonical fingerprint.

Backlog coverage: OI-006 provenance, OI-007 persistent questions, OI-009
reassessment and OI-013 authorization/recovery. This slice adds no model,
licensed knowledge, clinical review owner or new dependency. Clinical evidence
investigation and report/review convergence remain separate.

## Patient value and exact scope

A patient/care-team member using the synthetic React Investigations workspace
can inspect the authorized, original-source World Model, prepare an exact
source/version/line Composer preview and deliberately **save the associated
question** to one durable PostgreSQL record. They can reopen saved questions
after server restart and inspect whether the original source set still matches.

A changed or superseded original does not silently replace or approve
the historical question. Its derived status becomes
`source_reassessment_required`, while its original `SRC-*`, SHA-256,
version, line, case, question text and preflight hash remain unchanged.

**No human review has been submitted**. `human_review_state: not_submitted`
and `clinical_approval: false` mean exactly that. This is a source-linked
question waiting for a future, independently authorized clinical review
handoff. It is not a finding, order, signed report, recommendation or model run.

## First-party ownership and migration

- `identity.identity_patients` remains the single H1 patient registry.
- `coordination.patient_case_bindings` remains the unique qualified
  case-to-patient mapping with explicit revocation.
- `clinical_source.source_versions` / `clinical_source.assertions` remain
  the ONLY original source and authored statement owners, preserving exact
  bytes, SHA-256 and historical amendments.
- `investigation.source_questions` is the first PostgreSQL persistence port
  of the existing CaseStore question-intake record. Alembic
  `0006_source_questions` owns its explicit schema, patient/case/original
  foreign keys, idempotency constraint and immutable row guards.
- Every successful new question inserts exactly ONE
  `investigation.question.created` entry into the EXISTING append-only
  `identity.identity_domain_events` journal in the SAME PG transaction. No
  second event broker, approval table or review ledger was added.

## API contract

`POST /v1/patients/{patient_id}/cases/{case_id}/questions` requires
`patient_read`, `source_read`, `composer_context_read`, and a separate
`question_create` grant, the precise patient ID, persisted organization,
trusted actor, **operations purpose**, active patient and case mapping.

The explicit request includes:
`synthetic: true`, stable `request_key`, source `SRC-*`, original
line, question text, original source-set fingerprint, and exact
`preflight_sha256` from the prior source-only Composer preflight.

The writer re-reads the validated canonical source index inside the same
patient/source-binding transaction, using the shared source-owner locked path.
It projects the current World Model, verifies original hashes and the complete
literal finding inventory, recalculates the Composer packet, checks its exact
fingerprint and current grants, then writes question and event atomically.
A correction racing a write must be serialized by the original source's
case lock. Request keys are unique per patient; same-intent retry returns
the original question ID, including after a later amendment, while
changed-intent key reuse is rejected. On event write failure, the question
insert rolls back.

Idempotent retries apply to canonical-contract rows. A legacy row is retained as
history, but cannot be silently reused as a canonical request; its existing
request key conflicts and a newly prepared intent needs a new key.

`GET /v1/patients/{patient_id}/cases/{case_id}/questions` separately
requires `patient_read`, `source_read`, and `question_read`.
Its current-versus-reassessment status is a *read-time projection* under
the same qualified source lock. It never promotes a stale source to current,
does not show unreviewed source text from the question row, and does not
assert that a reviewer has accepted work. The original question remains
durable when its source is superseded.

The current projection is conservative: any change to the complete current case
snapshot requires reassessment, even when the selected anchor itself remains.
Dependency-specific narrowing is not implemented. Other cases stay isolated.
The bounded list refuses more than 250 rows; pagination is not yet provided.

## UI contract

The existing React Investigations view now provides **Save source-linked
question (no clinical approval)** from an explicit, authorized current
Composer preflight. A request key remains stable for retries of the SAME
prepared question in the same in-memory session. An unknown network outcome
is not shown as a successful write. The user can refresh saved history to
confirm whether the original question was committed. No key/credential,
patient data or question text is placed into browser storage.

Saved question IDs and source-reassessment warnings remain visibly distinct
from clinician approval. Changing patients, source generation, credentials or
authorization clears cached question history and prepared content; the
authoritative questions remain in PostgreSQL. Navigation between workspaces
for the same patient retains that context and an in-flight save, so changing
sections does not discard its idempotency key or manufacture a new intent.

This initial UI offers the transparent standard source-provenance question.
The typed API supports a bounded custom question, but editable browser
drafting and a safe discard guard must be integrated before exposing free
text input that could otherwise be lost on case switching.

## Tests, limits, release gates

`apps/api/tests/test_source_questions.py` exercises real disposable
PostgreSQL 16, idempotency and concurrent identical submissions,
immutability, cross-patient and purpose isolation, source/version
amendments, event-write rollback, restart and reassessment projection.
Client tests verify source-authority denials, unknown response retry with
same key, forged approvals/status rejection, correction and patient switch.
Real Chromium creates v1 question, confirms re-open, imports v2,
observes the historical question's new reassessment status, saves a v2
question, and checks independent question-read revocation.

All request and list operations are synthetic-only. They do not validate
clinical correctness or publisher rights and they do not integrate the
original `UnifiedClinicalReview` or durable review receipt owner
(#150/#165/#175/#210). A future genuine review request must use their
one authorized review state machine, authenticate the professional reviewer,
enforce consent and content rights, and perform its own write-time source,
policy and identity checks; do not treat the question receipt as approval.

The test database user is a superuser; tests do not prove least-privilege
service roles, row-level security, real identity consent, PHI encryption,
clinical audit access, interoperability, actual hospital records or
licensed guidelines. All ancestor branches remain draft/unmerged.
