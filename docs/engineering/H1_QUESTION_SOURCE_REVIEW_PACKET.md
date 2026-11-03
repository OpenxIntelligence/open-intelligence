# Canonical question → original-source quotation review packet

**Status:** Draft synthetic engineering integration, unmerged. This is a
read-only original-source verification and evidence-inspection prerequisite,
**not** clinical evidence appraisal, a diagnosis, consent, medical advice,
signed review or live clinical deployment.

## Product journey

An authorized user can already inspect original fictional reports, prepare
source-scoped Composer context, save a persistent question and reopen it after
an amendment (#244). The missing step in this increment was a *question-bound,
originally authored source quotation* that reviewers can inspect independently
of a cached World Model response, without inventing any evidence relevance or
clinical conclusion.

The Investigations panel now exposes **Inspect verified source quote and
evidence gaps** on a saved question. On current sources it shows the literal
stored source line, reported status, document version, date, optional specimen
and a bounded list of related authored statements for the SAME explicit
specimen/event date/finding key. These are references, not ranked evidence.
If the original or overall source snapshot changes, the historical question
keeps its original anchor but the packet **withholds the stale quotation** and
directs the user to create a fresh source-anchored question.

The UI shows absent biomedical study appraisal, publisher rights, clinician
identity, consent and approval explicitly. Its source quotations are rendered
as React text, not HTML. The packet is cleared on patient/session changes,
navigation, source/question refresh, late response, denial or invalid packet.

## Exactly one source owner

The new `PostgresQuestionSourcePacket.read` takes the existing canonical
patient/case/source context as inputs. It uses
`PostgresSourceVersions.list_locked(...prepare_response=...)`, which already:
- holds the patient and qualified case binding lock for the caller's
  PostgreSQL transaction;
- checks exact source bytes/hash, source version chain and literal
  source-assertion key, state, line and quotation against the original;
- reserves an original source-read access receipt;
- refreshes actor/organization/patient/grant context before appending that
  receipt and committing.

It reads the already persisted `investigation.source_questions` with the
same patient, case and organization. It uses the canonical
`project_source_world_model` snapshot `oi.pg-source-world-model/1`.
An older question with a different source-fingerprint contract is always
reassessment-only; a matching raw SHA cannot silently promote it. There is
**no new SQL schema, patient/source/question model, evidence ledger, rights
provider, external network request or model runtime**.

The new read endpoint is

`GET /v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/source-review-packet`

and independently requires `patient_read`, `question_read`,
`source_read` and **`review_packet_read`**, with operations purpose and the
exact persisted patient/case/organization. The same bearer actor/grants
are rechecked after packet preparation within the source-owner transaction.
A failed authority or audit-event insert withholds the response.

The packet includes a stable SHA-256 of the deterministic source/quote,
current/historical flags and limitations, excluding its distinct per-request
access receipt. The client recomputes the content SHA before rendering. An
access receipt proves authorized preparation, **not** browser/network
delivery, clinician consent, downstream model execution or clinical review.

## Boundaries and tests

The packet returns ONE selected quote when current, and up to 16 related
same-specimen/date/finding source statements; the total and a truncation
flag prevent limited inspection from appearing exhaustive. No source quote
is returned for a stale/superseded question. No patient text or case
identifiers are sent to a publication search service. No third-party
article, guideline, image pixels or licensed text is added.

Actual PG16/FastAPI tests verify:
- exact original quote, line, version, hash and stable packet fingerprint
  with separate access receipts and no new question rows;
- historical source amendment with old-quote suppression and corrected new
  question; bounded same-specimen/date related source quotations;
- wrong patient/case, unknown question, denied independent action, research
  purpose, case revocation and quote leak prevention;
- failure of source-read audit insertion aborts disclosure.

Typed client tests check strict question/statement fields, packet SHA,
forged approval/rights/medical interpretation, denied reading, patient
switch and late response. Real headless Chromium on built React/FastAPI/PG16
checks original literal quotation (including markup-looking text),
amendment withholding, fresh replacement quote and permission revocation.
Inherited migration, backup/restore, source/question and Chromium tests must
also remain green at exact proposed PR head.

**Unimplemented:** qualified biomedical published evidence, scientific
applicability/bias grading, rights/redistribution grants, professional
credentials, real patient consent, signed/reviewer state machine,
source-specific medical applicability, validated model inference, clinical
decisions, PHI hosting and deployment. The nonterminal review-return owner
(#262) is separately converging canonical question data and is not modified
by this branch.
