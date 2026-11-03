# H1 source-question / review-return authorization convergence

**Scope:** Synthetic-only engineering reconciliation stacked on source-owned
[#245](https://github.com/OpenxIntelligence/open-intelligence/pull/245)
(review queue + returned-only receipts) with exact source-owned
[#243](https://github.com/OpenxIntelligence/open-intelligence/pull/243)
(late question/Composer reauthorization) imported without rewriting its
original blobs. **Draft, unmerged, not a clinical deployment.**

## Why it matters

The established H1 API checks each scope when a request starts. However, source
projection and source-binding locks may delay a response, and the operator
fixture's actor, purpose, organization or allowed actions may change meanwhile.
An authorization captured at request entry is **not** sufficient to release
question history or create an append-only verification-return receipt after
revocation.

Review Queue is **still projected** from
`investigation.source_questions`; there is **no second queue table**.
`investigation.question_review_receipts` is the existing #245 immutable
returned-only receipt owner, not a competing approval state machine.
`identity.identity_domain_events` remains the single append-only domain
journal for actual question and review-return writes. Original source custody,
case binding, patient identity and source-preflight data owners are unchanged.

## Exact reconciliation

- Reuse #243's original `source_questions.py` and
  `test_source_questions.py` Git blobs, including forced final authority checks
  on new writes, idempotent duplicate returns, history and Composer preflight.
  These source-owned files were absent from #245's changed-file set and their
  pre-import blobs matched the shared #238 ancestor.
- Reuse #243's `final_question_authority` helper in the existing H1
  `patients.py` route composition: reauthenticate the **same original bearer**
  against the current synthetic grant; require the original actor,
  organization and purpose to match; revalidate every named operation and
  `patient_read` against the same patient and persisted origin.
- For `GET /review-queue`, reauthorize `patient_read`, `source_read`,
  `question_read` and `review_queue_read` **after** the source/question/return
  projection, before leaving the existing PostgreSQL source transaction.
  A changed actor/grant refuses the response; it does not deliver a cached
  question or historical return reason.
- For `POST .../return-for-verification`, reauthorize `patient_read`,
  `source_read`, `question_read` and independent `review_return`
  on a same-key/idempotent receipt replay; on a new return **before INSERT**,
  in a same-key conflict winner path, and **after append_event but before
  COMMIT**. Revocation on the last path aborts the PostgreSQL transaction,
  rolling back both receipt and original event.
- Preserve the original source-case row lock, current-versus-superseded
  fingerprint, patient-scoped request-key uniqueness, source-reassessment
  derivation and immutable `returned`-only receipt guard. No clinical
  terminal action or authority is added.

## Targeted negative acceptance

`apps/api/tests/test_question_review_returns.py` adds four actual PostgreSQL
HTTP races using the existing injected fictional access-file provider:
review-inbox grant revocation after source projection; review-return grant
revocation after projection; revocation after event append (must roll back
both rows and event); and same bearer reassigned to a different actor before
a duplicate receipt response (must not disclose existing receipt ID).
The four #243 tests for source-question and Composer late authority are also
retained exactly. Successful normal authorized replays are controls.

The standalone #245 hosted checks passed on its own head, and #243 passed on
its separate head; **neither independently proves this combined source tree.**
The complete H1 PostgreSQL/API suite, locked dependency gate, inherited Python
reference suite, real Chromium patient/Review workflows, API restart,
PostgreSQL dump/restore and next-request revocation must be run on this
branch's **exact head**. Do not claim a pass until observed.

## Clinical and integration limits

This remains an *operator-originated nonterminal verification return*:
`reviewer_identity_verified=false`,
`external_notification_sent=false`,
`clinical_approval=false`. The actor label is **not** a verified clinician.
No reviewer signing, acknowledged/reviewed clinical decision, signed report,
biomedical publisher rights, consent, model inference, real-PHI deployment or
medical advice is supplied. Provider revocation can still occur **after** the
last access check; an already returned response cannot be recalled. A truly
atomic identity-provider/DB security boundary and least-privilege database
roles are unqualified.

**Open parallel architectural reconciliation:** draft #234/#244 uses a
different source-read receipt / World Model representation and introduces
`0007_question_snapshot_contract`; draft #242 adds sibling migration
`0006_image_custody` independently of this branch's
`0006_source_questions`. Do not naively merge or rename these revisions.
A future owner-approved convergence must choose one canonical source contract,
adopt both migrations with explicit Alembic reconciliation, retain original
provenance/authorization receipts and rerun a new combined exact-head
PostgreSQL/React/Chromium/backup-restore gate. Neither project branch or main
was modified by this integration.
