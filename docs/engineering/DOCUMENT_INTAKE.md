# Reviewed text and bounded PDF document intake

Status: PDF extension verified locally and in hosted Chromium on 3 November 2026 UTC;
draft/unmerged in [PR #189](https://github.com/OpenxIntelligence/open-intelligence/pull/189). Extends OI-006, OI-007,
OI-009 and OI-010; this is a bounded source-ingestion feature, not a new platform
architecture or clinical release.

## User outcome

Select a fictional patient case, upload a UTF-8 text record or bounded born-digital
PDF, inspect the original and its readable text, enter dates/document identity, and select exact passages
to record as source statements. Save it into the existing timeline, open the
original, and use the same source in questions, investigations and reports.
Users can save a record without selecting findings. No clinical facts are
inferred from unreviewed text.

## Architecture and reuse

The feature extends the existing `CaseStore` source owner. `source_versions`
retains the original bytes and SHA-256; `assertions` retains manually selected
source quotations and line numbers; the existing event ledger, amendment
lineage and downstream invalidation transaction remain authoritative. A small
extension record describes the intake method and filename. PDF sources additionally
own one immutable `source_text_renditions` child, keyed by the existing source version.
It preserves original/extraction hashes, extractor name/version/wheel/configuration,
physical-page count, unchanged per-page extracted strings and their hashes, numbered
page/global lines, and the LF-joined display rendition. Page numbers are physical
one-based indices, not printed labels; extraction lines are not original PDF byte
lines or guaranteed visual lines. There is no second
patient registry, source ledger, evidence store or review system.

The PDF extension is stacked on #173 at
`243bfec0fb36121868714dd36c6dd591243114da` (documentation follow-up to runtime
`fe8a6368245bb52944e6ebc7f3e6f5b43daf69d0`), whose text intake is based on verified PR #140, head
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
Alembic/PostgreSQL and React/Vite/TypeScript. This source-ingestion
contract and behavioral tests can move with that migration; this change does
not reopen stack selection or imply the migration is complete.

## Acceptance criteria

1. Preview accepts bounded `.txt` UTF-8 files and born-digital PDFs without the custom synthetic
   report header. It writes no source, assertion or event.
2. Save preserves the uploaded bytes, including BOM and CRLF, through restart
   and download. Original content is never replaced by extracted/normalized text.
3. Every chosen quote is an exact substring of the stated preview line. PDF
   confirmation binds the original hash and extraction hash, which includes the
   extractor/configuration, page text and anchors. Unsupported
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

Text and PDF originals: maximum 64 KiB, 512 preview lines and 30 selected
single-line passages, within the existing 128 KiB JSON request envelope.
PDFs permit at most 20 physical pages and 64 KiB total per-page extracted UTF-8
text. Oversized requests/extractions fail without truncation or clinical writes.
Image-only/nonblank unextractable pages, encrypted files (including empty open
passwords), interactive forms, annotations, actions, embedded/associated files,
parser warnings/repairs and unsupported formats
are rejected. Blank pages are retained explicitly. Extraction does not verify
visible text, reading order, tables or text-plus-image completeness. No OCR or
automatic clinical assertion extraction is performed. Metadata and passages
are manually confirmed; subject identity cannot be inferred from arbitrary text.

The exact pypdf parser runs in one fresh Python `-I -B` process per extraction,
outside any database write transaction. Resource ceilings are 5 CPU seconds,
10 elapsed seconds, 512 MiB address space and 512 KiB worker output. One worker
slot bounds concurrency; finite internal parser limits supplement these ceilings.
The worker receives original bytes through stdin and a minimal locale environment.
JBIG2 helpers and optional extras are disabled; audit hooks reject network,
subprocess and file-write operations. These hooks are not an OS sandbox or a
malware guarantee. Unsupported resource isolation or a missing/wrong parser
version fails closed while text intake remains usable.

Save recomputes the extraction and verifies both hashes. The original, frozen
rendition, selected assertions, receipt, events and invalidation commit under
the existing `BEGIN IMMEDIATE`. Update/delete triggers prevent modifying a
persisted rendition. Historical readers use that rendition without parsing;
an extractor/configuration change must not silently rewrite it. Rerendering an
existing original with a new extractor is not supported in this first revision.

Original downloads use `application/pdf` for PDFs and remain attachments with
`no-store`/`nosniff`. The viewer and Markdown export explicitly distinguish
original bytes from extracted text. Page anchors and extraction identity flow
through the current case, investigation, Composer and patient projections.
The existing numeric lab tool is restricted to its authored structured synthetic
measurement contract. Manually transcribed text/PDF measurements are held with
`manual_transcription_not_eligible`, preserving their manual/page/hash provenance;
the parser does not expand that tool's authority or establish a lab result.

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

### Hosted PDF acceptance

Verified implementation/workflow head: `afe89d390f665713acfca5cca58aae9d285ee1bb`.

- [Exact-head integration run 41553904095](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41553904095),
  job `125647955743`: **success**. Checkout equals the authored PR head. Python
  3.12.15, pypdf 6.21.4, Node 24.22.1, Chrome 156.0.8078.47.
- **398 Python/HTTP tests passed** in 51.565s; **64 JavaScript tests passed**;
  **80 offline checks passed, 18 optional HDF5 checks skipped**. The patient-data
  workflow guard, compilation and syntax checks passed.
- All five integration browser journeys passed: reviewed text/PDF intake;
  source-bound Composer/replay; numeric lab tool; durable work; rights-qualified
  broker. The new PDF journey selects physical page 2/global extraction line 3,
  preserves manual `not-assessed` status, downloads exact originals with PDF MIME,
  creates a source-linked human-authored report, records explicit demo review,
  introduces an amendment, retains stale history, and restarts the actual server.
  It verifies accessible page labels, a 390 px viewport and literal markup text.
  This PDF journey invokes no model; the separate Composer regression uses
  recorded replay. Neither is live-model or clinical validation.
- [UI run 41553903829](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41553903829),
  job `125647954254`: **success**, including 398 Python/HTTP tests and existing
  integrated, source-dialog race, keyboard and layout browser checks. It tested
  generated merge `d8fe55c55db86bbe342e20e8b8c44ac582d3ce45` into #173.
- Integration artifact `13193373812`, SHA-256
  `3ae9d98ddb2974c6db35427afa22a0a65592d53e7cba7652c1dfe5a97d779193`,
  and UI artifact `13194100080`, SHA-256
  `6cc0e3135a34fc692af78ff5549757c0a7c11fe5ca9d7d38888c37dd7b90ccc7`,
  were downloaded and verified. The UI source archive matched all 213 workspace
  files before this receipt update. PDF desktop/narrow screenshots were inspected.
  The intake receipt records `status=passed`, `restart_verified=true`, exact
  original download, two PDF versions, manual classification and no model call.

The initial head `95f4fb9a384bb92ac1231cab1a86b48314134d5c` was rejected before
jobs ran because the YAML plain scalar contained pip's `--only-binary=:all:`.
[Failed configuration run 41553646603](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41553646603)
remains inspectable. A workflow-only correction used block scalars; all seven
workflow files parsed locally, and the successful runs above verified the fix.

### Local PDF acceptance

PDF extension local run: **398 Python/domain/HTTP tests passed in 112.609s**,
including 17 extractor, 12 PDF store, 8 PDF HTTP and 9 lifecycle tests. All
**64 JavaScript tests** passed (22 source-reader, 17 intake, 15 line-comparison,
8 text-change, 2 model-refresh). Compilation/syntax and the current CI
patient-data boundary guard passed. The offline research suite ran 98 tests:
80 passed and 18 optional HDF5-environment checks skipped. No skipped parser
check is counted as a pass. Python 3.12.14; isolated pypdf 6.21.4 environment.

The executed matrix covers dual-hash/quote/case denial, exact original restart,
frozen reads without a parser, idempotency, immutable review, forced child-insert
rollback, amendment/model/snapshot staleness, every-consumer page provenance,
worker resource/format failures and subsequent recovery. Review also found and
fixed model-driven question closure and manual-measurement promotion into the
qualified numeric tool. The hosted two-page PDF browser workflow is established
by the separate execution receipt above.

The existing text feature passed hosted exact-head run
[41550282180](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550282180)
at `fe8a6368245bb52944e6ebc7f3e6f5b43daf69d0`: 349 Python/HTTP,
80 offline research/data-boundary checks with 18 optional HDF5 skips and 47 JavaScript tests, plus the text-intake
and four Composer browser journeys. UI run
[41550282107](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550282107)
also passed. The PDF extension adds independently authored PDF fixtures,
worker-limit/format tests, source/API integration checks, source-view guards,
and a real two-page upload → Composer → report → amendment → restart browser
journey. The earlier receipt below applies only to the text baseline.

The #173 UI run tested generated merge `9477738cf5a9472747b6bf4e209fcf427c31fb2d`
with Chromium 156.0.8078.47 and Python 3.13.17. The exact-head text artifact
`13191720636` has SHA-256 `19ac5e28c1106657db91ec69cfc1221b80d678cd35724531970c41d1fcf9d636`;
its digest and screenshots were checked in that source-owner work. The final
documentation-only head `243bfec0fb36121868714dd36c6dd591243114da` subsequently
passed [41550696219](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550696219)
and [41550696421](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41550696421).

### Exact dependency and source-rights receipt

- Package: `pypdf==6.21.4`, wheel `pypdf-6.21.4-py3-none-any.whl`.
- Wheel SHA-256: `33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c`.
- [Release/provenance](https://pypi.org/project/pypdf/6.21.4/) identifies source
  commit `b2c3fa2ee689f582a0de256a45e30bd96c68f807`.
- [Exact BSD-3-Clause license](https://github.com/py-pdf/pypdf/blob/b2c3fa2ee689f582a0de256a45e30bd96c68f807/LICENSE),
  Git blob `ab327d0312875458ba74983867f1b2622b6de39d`, is retained verbatim in
  `THIRD_PARTY_NOTICES/pypdf.txt`; the installed wheel notice matches.
- Hash-required wheel-only installation was executed in an isolated Python
  3.12.14 environment. Its only installed distributions were pip 25.0.1 and
  pypdf 6.21.4. The package declares no unconditional runtime dependency for
  Python 3.12; older-Python and optional-extra dependency graphs are not adopted.
- Recommendation: **EXTEND for this bounded synthetic intake**, not blanket
  legal clearance or production qualification. Retain the BSD copyright,
  conditions and disclaimer in source/binary distributions and do not imply
  endorsement. The project distribution license remains undecided.
- Current primary advisory review included
  [xref EOF loop](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5849-834g-hvw5),
  [page-tree memory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-cggf-277g-3q54),
  and [dictionary clone loop](https://github.com/py-pdf/pypdf/security/advisories/GHSA-mfr5-77xh-9j7h),
  fixed in this pin. This is not a claim that all future or unknown issues are
  absent; resource restriction and qualification remain necessary.
- [Extraction limitations](https://pypdf.readthedocs.io/en/6.21.4/user/extract-text.html)
  require original-document review. Code rights do not grant rights to uploaded
  files, embedded assets, patient records, model weights or datasets. All PDF
  fixtures here are independently generated from authored fictional strings;
  no external medical PDF or upstream patient/sample corpus was downloaded.

### Earlier text-only local receipt

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
hosted acceptance gate; the executed text-baseline result is recorded above.
The PDF extension requires its own exact-head receipt.

First hosted attempt at `98d7ea1c6068a806d428840a035d827777b24d97`
([run 41549856886](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41549856886))
passed the Python, offline and JavaScript checks, then exposed 14 px of intake
panel overflow at a 390 px viewport. The layout correction constrains fieldset
and native control widths; the strict browser assertion remains and passed in
the subsequent exact-head run. The failed first attempt remains inspectable.

### API

| Route | Contract |
| --- | --- |
| `POST /api/cases/{case}/documents/preview` | `{filename, content_base64}`; read-only, original-byte hash and numbered lines |
| `POST /api/cases/{case}/documents` | Same bytes plus `{metadata, findings, expected_sha256, confirmed_case_id}`; PDF additionally requires `expected_extraction_sha256`; atomic source/rendition/receipt/invalidation |
| `GET /api/cases/{case}/sources/{id}` | Original UTF-8 text or labeled frozen PDF extraction, identity and page anchors; no reparsing |
| `GET /api/cases/{case}/sources/{id}/download` | Same-case original bytes, safe attachment name, `no-store` and `nosniff` |

Metadata includes document reference, category, event/issue dates, optional
specimen/amendment, and `manual_transcription_confirmed: true`. Findings are
`{key, state, quote, line}`. Exact source evidence and user classification are
retained separately. Preview/commit JSON fields are strict; unknown fields,
duplicate keys, noncanonical base64 and over-limit requests fail closed.


### Patient-record projection convergence — 3 November 2026 UTC

[Draft PR #215](https://github.com/OpenxIntelligence/open-intelligence/pull/215),
based on #189, reuses #161's read-only World Model and Patient
view. It carries manual classification, frozen extraction identity and physical
page anchors through current findings, unresolved observations and historical
source references. Original bytes, document intake and snapshot/review storage
remain unchanged. Verification for this integration is maintained in
[SYNTHETIC_WORLD_MODEL_PROJECTION.md](SYNTHETIC_WORLD_MODEL_PROJECTION.md); the
#189 test counts above belong to its own exact source tree.

Verified runtime `284b9ac1be1e27ccc4863eaf60dfa7432e8d9d46` passed exact-head
[run 41562716040](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41562716040)
and [UI run 41562716468](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41562716468):
420 Python/HTTP tests, 123 JavaScript checks, 80 offline checks (18 optional
skips), five integration browser journeys and four UI journeys. The extended
PDF journey verifies page-two record/source jumps, manual status, rejected
forged-page projection, support/counterevidence, recorded replay, human report,
amendment, actual restart and replacement review preserving stale history.
No new source table, dependency, clinical authority or live model is added.
