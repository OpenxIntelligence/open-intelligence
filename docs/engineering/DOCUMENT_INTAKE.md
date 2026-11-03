# Reviewed plain-text document intake

Status: implemented locally; hosted acceptance pending, 2 November 2026. Extends OI-006, OI-007,
OI-009 and OI-010; this is a bounded source-ingestion feature, not a new platform
architecture or clinical release.

## User outcome

Select a fictional patient case, upload an ordinary UTF-8 text record, inspect
the original, enter its dates and document identity, and select exact passages
to record as source statements. Save it into the existing timeline, open the
original, and use the same source in questions, investigations and reports.
Users can save a record without selecting findings. No clinical facts are
inferred from unreviewed text.

## Architecture and reuse

The feature extends the existing `CaseStore` source owner. `source_versions`
retains the original bytes and SHA-256; `assertions` retains manually selected
source quotations and line numbers; the existing event ledger, amendment
lineage and downstream invalidation transaction remain authoritative. A small
extension record describes the intake method and filename. There is no second
patient registry, source ledger, evidence store or review system.

This implementation is based on verified PR #140, head
`4578c0a76b99daccb1195a2eb599dca4de936f0d`, to preserve its original-source,
rights-aware Composer, browser freshness and no-patient-data safeguards. It is
a feature branch, not another integration branch. PR #151 remains the existing
clinical/Composer convergence work; its store changes must be reconciled by
the source owner when this feature is incorporated. Do not replace that branch's
canonical identity/adapter transaction with this reference store wholesale.

Concurrent work discovered before publication: #166 and #167 already add
empty-case entry and file choosers for the existing custom structured-report
contract; #171 extends #166 with records-to-obtain tracking. This feature adds
the ordinary-text/manual-transcription source contract those paths do not
support. Reuse the selected connected-entry owner when consolidating the UI;
do not adopt two launchers, case creators or source ledgers. #172 connects the
existing PostgreSQL patient registry to H1 and remains separately owned.

The accepted H1 working target remains Python/FastAPI/Pydantic/SQLAlchemy/
Alembic/PostgreSQL and React/Vite/TypeScript. This dependency-free ingestion
contract and behavioral tests can move with that migration; this change does
not reopen stack selection or imply the migration is complete.

## Acceptance criteria

1. Preview accepts bounded `.txt` UTF-8 files without the custom synthetic
   report header. It writes no source, assertion or event.
2. Save preserves the uploaded bytes, including BOM and CRLF, through restart
   and download. Original content is never replaced by extracted/normalized text.
3. Every chosen quote is an exact substring of the stated source line. Unsupported
   bytes, invented quotes, malformed fields, stale amendments and changed hashes
   fail without partial writes.
4. The user explicitly confirms the target case and transcription. This is
   neither identity proofing nor credentialed clinical approval.
5. Exact retries are idempotent. Reusing identical bytes with altered annotation
   semantics is rejected; old confirmations are not silently rewritten.
6. An amendment preserves the old original, adds a new version, and uses the
   existing transaction to invalidate dependent work and reopen review.
7. The UI safely renders source text, preserves case scope across asynchronous
   responses, and connects successful intake to original inspection, timeline,
   questions and existing source-supported reports.
8. Automated backend, HTTP, JavaScript and real-browser checks use independently
   authored fictional inputs and no live biomedical/model service.

## Current boundaries

UTF-8 plain text only: maximum 64 KiB, 512 logical lines and 30 selected
single-line passages, within a 128 KiB JSON request envelope. Oversized envelopes
are rejected without truncation and the draft is retained. No PDF, OCR, image
interpretation or automated extraction.
Metadata and passages are manually confirmed; subject matching cannot be
inferred from arbitrary text. No new third-party component is introduced.

Post-save annotation editing is not implemented. Saving without passages is an
original-only organizational workflow; uploading the same bytes with different
annotations is rejected. A future append-only annotation-review/correction
contract must preserve the original and historical confirmations. Never alter
original bytes merely to bypass this limit.

The current local application remains synthetic-only and loopback-only. It has
no real user authentication, production consent service or clinical validation.
It must not receive real patient data. A later authenticated host must supply
trusted identity/permissions through the canonical patient/adapter owners.

## Verification receipt

Local application suite: 349 Python/domain/HTTP tests passed, including 19 new
intake domain tests and 14 real HTTP tests. Six direct JavaScript intake cases
pass. Existing source reader, line comparison, text-change and model-refresh
JavaScript checks also pass. The no-patient-data CI guard passes. A focused
follow-up carries manual classification into Patient Mission, timeline and the
change-review projection; all 43 targeted domain/Mission/timeline/change tests
passed after that follow-up. The mismatch test inspects every projected path.

Independent review found and prompted corrections for out-of-range source IDs,
lost manual classification provenance, and delayed case-switch UI actions.
Original-byte retention, transaction rollback, concurrent amendments, stale
model/snapshot handling and legacy v2 fingerprint compatibility are covered.

Local Chromium is unavailable. `tests/document_intake_browser_journey.py` is the
hosted acceptance gate, including real file input, source modal, export,
amendment, case isolation, accessibility labels and a narrow viewport. Its
execution result must be recorded separately on the exact feature commit.

First hosted attempt at `98d7ea1c6068a806d428840a035d827777b24d97`
([run 41549856886](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41549856886))
passed the Python, offline and JavaScript checks, then exposed 14 px of intake
panel overflow at a 390 px viewport. The layout correction constrains fieldset
and native control widths; the strict browser assertion remains. Subsequent
exact-head browser results must establish the corrected workflow.

### API

| Route | Contract |
| --- | --- |
| `POST /api/cases/{case}/documents/preview` | `{filename, content_base64}`; read-only, original-byte hash and numbered lines |
| `POST /api/cases/{case}/documents` | Same bytes plus `{metadata, findings, expected_sha256, confirmed_case_id}`; atomic source/receipt/invalidation |
| `GET /api/cases/{case}/sources/{id}/download` | Same-case original bytes, safe attachment name, `no-store` and `nosniff` |

Metadata includes document reference, category, event/issue dates, optional
specimen/amendment, and `manual_transcription_confirmed: true`. Findings are
`{key, state, quote, line}`. Exact source evidence and user classification are
retained separately. Preview/commit JSON fields are strict; unknown fields,
duplicate keys, noncanonical base64 and over-limit requests fail closed.
