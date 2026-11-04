# Reviewed plain-text document intake

Status: UNVERIFIED — inspection-only partial rebase onto main 2451983; draft and
unmerged. Hosted engineering acceptance on this tree is NOT verified and is a
reviewer item. Extends OI-006, OI-007, OI-009 and OI-010; this is a bounded
source-ingestion feature, not a new platform architecture or clinical release.

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

UNVERIFIED on this tree. This partial rebase onto main 2451983 was checked by
inspection only; nothing was executed here, and no hosted acceptance on this
exact head is claimed. The reviewer runs the items below before any pass or
acceptance statement. These are synthetic engineering checks, not clinical
validation.

What inspection covers on this branch (only): the excluded-Composer manifest
(no `composer.py`/`composer.js` code, no `test_document_intake.py`, no Composer
workflow), the preserved amendment-gated investigation staleness, main-anchor
compatibility, and test-file presence/counts (14 intake HTTP tests for a
236 + 14 = 250 Python denominator; 6 intake JS UI cases). Presence and
arithmetic are not pass outcomes.

### Prior-stack history (NOT verification of this rebase)

The following was earned on the #140 stack by the #173 implementation at
`fe8a6368245bb52944e6ebc7f3e6f5b43daf69d0`, where Composer was present and the
three #140 anchors were unadapted. It is retained as provenance for what
motivated this rebase and must NOT be read as acceptance of this main-based
tree: [exact-head run 41550282180](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550282180)
reported 349 Python/domain/HTTP tests, 47 JavaScript cases, 80 offline checks
with 18 optional dependency skips, and five Chromium journeys, including the
intake journey (file selection, read-only preview, exact original byte
download, manual classification, question/Composer/draft/export, amendment
staleness, source history, field labels, 390 px layout, delayed case-switch
isolation); [UI run 41550282107](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550282107)
covered the generated merge `9477738cf5a9472747b6bf4e209fcf427c31fb2d` into
#140 (Chromium 156.0.8078.47 / Python 3.13.17); artifact `13191720636`
(SHA-256 `19ac5e28c1106657db91ec69cfc1221b80d678cd35724531970c41d1fcf9d636`)
and its inspected screenshots belong to that same stack. Earlier local and
first-attempt notes from that stack (349-count suite with 19 intake domain
plus 14 HTTP tests, 6 JS intake cases, 43 targeted domain/Mission/timeline/
change tests after the classification follow-up, and the 390 px overflow found
in [run 41549856886](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41549856886)
at `98d7ea1c6068a806d428840a035d827777b24d97`) likewise do not verify this
rebase. No live model or patient-data service was invoked there; none is
claimed here.

### Reviewer runs on this exact head (all UNVERIFIED until run)

1. `py_compile` + `node --check`; full Python suite (expected denominator
   236 + 14 = 250); JS intake UI suite (expected 6 cases).
2. `tests/document_intake_browser_journey.py` on Chromium; the two Composer
   gates skip by design on main (`#composer-context` absent, #140-stack-only)
   and the remaining intake flow must pass.
3. Confirm the three #140-anchor adaptations against #173's original hunks;
   confirm no behavior change to structured-fixture import.
4. Lead sequencing: #140 beneath for the excluded manifest; order against
   #337/#341 web-file changes. Record hosted results in the draft PR before
   any acceptance claim.

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
