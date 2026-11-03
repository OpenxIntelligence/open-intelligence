# H1 — source-linked question review return, immutable history

**Status:** Synthetic-only, draft and unmerged. First-party owner-pattern
integration, **not** clinician signoff, an external review request, patient
consent, scientific evidence appraisal, or approved clinical action.

## Why this integration is necessary

The existing clinical reference work (#82 → #150/#165/#175/#210) derives its
review queue from canonical work and persists only immutable append-only review
receipts. Its original review adapter restricts a nonterminal return to a
separately authorized operation and checks an exact current item fingerprint
before the write.

H1 already owns the patient (`identity.identity_patients`), case binding
(`coordination.patient_case_bindings`), original source
(`clinical_source.source_versions` + assertions), world model (#216),
preflight (#223), and durable source question (#238). This PR ports **only
the nonterminal source-question review-return semantics** into that same
PostgreSQL `investigation` domain. It does not copy the SQLite clinical
review database, evidence assessment engine or signed review/decision state.

## One review receipt owner, derived queue

Alembic `0007_question_review_returns` creates only
`investigation.question_review_receipts`, an immutable, FK-bound record
with one allowed `action='returned'`. The queue itself is always derived
from the already persisted `investigation.source_questions` and current
original-source version; **there is no review_queue table**.

The row has an exact question ID, canonical patient/case/organization,
actor/purpose, stable request key + intent hash, source set fingerprint,
queue item fingerprint and bounded visible reason. The database trigger
verifies current case/source/question matching at insert; update and delete
are denied. The application also holds the existing qualified case-binding
row lock, which source amendment and revocation take, and checks a
literal source quote/line/sha through `PostgresWorldModelRead.read_locked`
before appending a return receipt and a single
`identity.identity_domain_events` event in **one transaction**.
If event append fails, the receipt is rolled back.

Two new source-patient API operations:

- `GET /v1/patients/{id}/cases/{case_id}/review-queue` needs patient read,
  question read, source read, and independent `review_queue_read`.
- `POST .../questions/{question_id}/return-for-verification` needs patient
  read, question read, source read and independent `review_return`.
  The caller submits an exact current queue SHA-256, a reason and a request
  key. The only allowed result is a **nonterminal returned receipt**,
  not verified review, acknowledgment, clinical approval or notification.

For each question the derived view distinguishes:

- `awaiting_independent_verification`: source is still exact/current and no
  return receipt matches this version.
- `returned_for_independent_verification`: an immutable returned receipt
  matches this question and version. This **does not** mean a clinician or
  institution has been notified.
- `source_reassessment_required`: the original or source snapshot changed.
  The old receipt remains historical but never carries forward as a current
  review result. A corrected source requires a new exact preflight and saved
  source-linked question.

An uncertain response can be retried with the original request key and
intent; the same receipt is returned without another event. New keys against
stale sources are denied. A changed request intent is denied. A case-binding
revocation suppresses reads and new writes without silently erasing history.

## UI behavior

The original React patient workspace now has **Review**, a source-case-scoped
inbox and append-only return history. It shows source identifiers and
question provenance only after current authorization, and makes the
nonterminal boundary conspicuous. The reason is an editable bounded field
with an explicit fictional example; there is **no** clinician approval,
signature, model run, evidence export, external transmission or treatment
recommendation button. Switching patient, disconnected session, navigation,
failed or revoked permission clears the cached queue. A previously committed
return can be recovered after an uncertain network response with the same key.

## Proof and blockers

`apps/api/tests/test_question_review_returns.py` verifies real PostgreSQL
16/FastAPI, exact source and patient binding, idempotency including concurrent
calls, mutation denial, rollback on failed event, source amendment and
historical returns, case revocation, and independently revoked read/write
grants. Typed client tests reject fabricated clinical approval or a corrupted
queue/receipt; the real Chromium journey covers the entire patient/source →
saved question → derived review inbox → immutable return → rights revocation.

**Still deliberately absent:** professional verification and identity,
clinical consent, actual provider notification, real source/distribution
rights, source-appraisal/quote report, licensed external evidence, clinician
assignment, evidence/clinical approval, model run, signed decision, patient
medical actions, production PHI/RLS/encryption and deployment. The SQLite
clinical review owner remains a separately draft source; its full state
machine must be reconciled before any production review or merge. A successful
hosted synthetic CI run verifies software behavior, not clinical authority.
