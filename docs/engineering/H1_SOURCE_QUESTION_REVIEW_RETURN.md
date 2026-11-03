# H1 — source-linked question review return, immutable history

**Status:** Synthetic-only, draft and unmerged. First-party owner-pattern
integration, **not** clinician signoff, an external review request, patient
consent, scientific evidence appraisal, or approved clinical action.

## Canonical convergence — 3 November 2026

This work preserves the existing review-return owner in #245 at
`82bc1a7c0e90dded501b2ea0d519ebe736ef4b2d` and connects it to #244 at
`3b6c466950852c20f99d57a70dd196fd2862571a`. It does not import the competing
World Model reader from #216. Current implementation and test results must be
verified on this convergence branch; upstream green CI is not that evidence.

**Tests-first evidence:** [run 41572461490](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41572461490)
checked out `6a0322781ae048067b359fb259bf4321c4f242ce` and ran 193 API/PG tests.
Exactly one failed: the new review-queue assertion received 404 Not Found after
successfully creating its canonical source question. The 192 inherited executions
passed. Implementation validation must be attached to the final PR head; the
initial RED run is not evidence that the new workflow is complete.

The original `0007_question_review_returns` and
`0007_question_snapshot_contract` histories remain unchanged. An explicit
`0008_review_convergence` revision joins both parents and records source
snapshot and queue-fingerprint provenance on receipt history. Existing rows
receive legacy defaults without rewriting their original values. New receipts
explicitly use `oi.pg-source-world-model/1` and
`oi.synthetic-source-review-return/2`. Legacy questions remain reassessment-only
even when their stored hash equals a canonical fingerprint. A legacy request
key conflicts with a new canonical intent; it is not silently relabeled.

The queue contract becomes `oi.synthetic-question-review-return-queue/2`.
A separate `access_receipt_id` records the source-access check. It never enters
the stable queue fingerprint or grants authority. Items and historical receipts
retain explicit `source_snapshot_contract` and `queue_fingerprint_contract`.
Preparation, typed DTO validation, final refreshed grants, the business event
and source-access receipt stay inside the existing source transaction.

Backlog coverage: OI-007 source-side verification, OI-009 second-time-point
reassessment and OI-013 isolation/recovery. No model, external evidence,
notification, clinical approval or new third-party dependency is introduced.

### Downstream boundary inspected before this slice

The newer #249/#250 evidence/report implementations retain the existing
`LinkedLabCaseStore`, clinical registry/laboratory/provenance connection,
integer question/assertion IDs, assessed evidence and permitted quotation
contracts. Their report/review handoff is a library boundary. PG `QUESTION-*`
and `SRC-*` IDs cannot be coerced or copied into those owners as an integration
shortcut. Their explicit persistence/adapter migration remains a separate gate.
The acceptance target is the existing source-verification return workflow.
The patient-specific scientific investigation and professional review loop
remain separate implementation gates.

The concurrently published [#260 image/question owner](https://github.com/OpenxIntelligence/open-intelligence/pull/260)
at `90dfe49fab082f3698fc82b3e8224cf7d30e5c4f` is a separate draft on the same
#244 base. Its `0008_merge_image_questions` and this branch's
`0008_review_convergence` require a later explicit merge and populated upgrade
proof from each head. Neither history should be renamed or replaced. That
combined runtime, its image permissions and image/return lifecycle are not
claimed by this contribution.

## Why this integration is necessary

The existing clinical reference work (#82 → #150/#165/#175/#210) derives its
review queue from canonical work and persists only immutable append-only review
receipts. Its original review adapter restricts a nonterminal return to a
separately authorized operation and checks an exact current item fingerprint
before the write.

H1 already owns the patient (`identity.identity_patients`), case binding
(`coordination.patient_case_bindings`), original source
(`clinical_source.source_versions` + assertions), canonical world model (#222/#234),
preflight (#223/#244), and durable source question (#238/#244). This PR ports **only
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
literal source quote/line/sha through the canonical source owner and shared
locked question projection before appending a return receipt and a single
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
recommendation button. Patient/source changes, disconnected sessions and denied authority clear the
cached queue. Same-patient workspace navigation preserves the in-flight intent
and captured reason; it does not manufacture a new request key. Unsubmitted
reason drafts are component-local and reset when leaving the Review workspace. A successful refresh
of the same case also preserves minimal uncertain intent while invalidating the
old queue. **Retry this exact return** uses the captured key, reason and fingerprint
to recover an already committed return even after amendment. A 409 response terminates a
stale/conflicting attempt without creating another key. Patient/case/credential
changes and authoritative permission denial discard it. All such state is in memory;
no retry survives reload or credential replacement.

## Proof and blockers

`apps/api/tests/test_canonical_review_flow.py` is the tests-first end-to-end
acceptance. `test_review_convergence_migration.py` exercises both original 0007
histories, exact old-field/event preservation, coincident legacy/canonical hashes
and new provenance through real API writes. `verify_reviews_compose.py` uses an
owned disposable project for actual HTTP, amendment/retry, independent grant
withdrawal, API/DB restart and pg_dump/restore SQL snapshot equality across questions,
receipts, source bytes/anchors and events. The restored database is inspected
directly; the probe does not restart the HTTP service against that restored copy. It is a recovery probe, not a clinical pilot.

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
