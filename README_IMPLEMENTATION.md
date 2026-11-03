## Running the first implementation locally

This is an **original Python/SQLite synthetic prototype**. The text-only path uses the standard library. Bounded PDF intake adds the optional, exact-pinned `pypdf==6.21.4` dependency on Python 3.12+ and POSIX resource controls. No clinical backend, hosted model, or third-party UI library is required for this exercise.

For PDF intake and the complete test suite, first create a clean Python 3.12+ environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: --no-deps -r requirements-pdf.lock
. .venv/bin/activate
```

```bash
PYTHONPATH=src python -m open_intelligence seed
PYTHONPATH=src python -m open_intelligence serve
# Visit http://127.0.0.1:8765
```

To run the verification suite:

```bash
PYTHONPATH=src python -m compileall -q src
node --check web/app.js
node --check web/mission.js
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python tests/browser_journey.py
PYTHONPATH=src python tests/patient_mission_browser_journey.py
```

The browser journeys require an installed Chrome or Chromium executable. GitHub Actions runs all of these checks for the implementation pull request.

For the demonstration: create a question in `CASE-ALPHA`, save an investigation draft linked to the pathology document, acknowledge it in demo mode, load the example amendment, and import it. The prior investigation becomes `stale`, the question reopens, and the original source remains accessible. Draft a replacement against the amended document. `CASE-BETA` remains unaffected.

### Add an ordinary text or born-digital PDF record

The **Add a record** section accepts UTF-8 `.txt` files without a custom report
header, and bounded `.pdf` files with extractable text. Use `examples/synthetic/plaintext-record.txt`, which is independently
fictional. Preview the file, select exact source passages if needed, enter the
record's document reference/type/dates, and confirm its case and transcription.
The original bytes, including BOM and CRLF if present, remain unchanged. The
saved source appears in the existing timeline, source reader, question/draft
workspace and Composer. Download retrieves the original file, not generated
text. An amendment uses the same document reference and latest version number.

Selected passages and their statuses are explicitly labeled as manual entries,
with clinical review not performed, throughout patient views, AI inputs and
exports. They are not inferred or verified clinical facts. The existing
structured fixture importer is retained under **Structured development fixtures**.

The original file limit remains 64 KiB, with 512 lines and 30 selected single-line
passages within a 128 KiB request. PDFs additionally permit at most 20 physical
pages and 64 KiB of extracted UTF-8 text. The source reader distinguishes PDF
extraction from original text, shows page/extraction-line anchors, and retains
both the original-byte hash and extraction hash. A restricted worker parses
outside the server and database transaction; historical reads use the persisted
extraction without reparsing. Encrypted, unreadable, image-only, interactive-form
and over-limit inputs fail explicitly. Compare selected passages with the
original: reading order, tables, hidden text and visual completeness are not
established by extraction. OCR and post-save annotation editing are not
implemented. Saving an original with no passages does not allow adding
passages afterward in this version. See the [intake contract and verification
record](docs/engineering/DOCUMENT_INTAKE.md) for API, source ownership and limits.

**Scope and warnings:** this is local-only software with no authentication, no access controls suitable for PHI, no clinical inference, no live literature or trials, and no clinical review. Never insert real patient data. The supported structured test format is `OI-SYNTHETIC-REPORT/1`, not a general-purpose clinical document parser. Source statements are author-supplied within report bytes. There is no treatment recommender, trial matching, or AI agent. The demo reviewer acknowledgment cannot attest professional credentials. The engineering controls are not evidence of medical safety or regulatory status.

The project distribution license remains undecided. Public source visibility is not an open-source license grant. All test reports and UI code are independently authored for this repository.

## Patient Mission workflow projection

The portal now includes a read-only **Patient Mission** panel near the top of the existing case workspace. It projects the canonical case ledger into five workflow questions:

1. Where is this synthetic case workflow now?
2. What do the current authored sources report?
3. What remains unresolved, stale, or quarantined?
4. Which material source or evidence changes were recorded?
5. Which bounded workflow action is supported by the capabilities already present in the demo?

The JSON form is available at:

```text
GET /api/cases/{CASE-ID}/mission
```

The endpoint and panel do not create or persist a second patient record. They deterministically derive their contents from the current `CaseStore.state()` snapshot and preserve source-version and source-line references. Workflow states are limited to `awaiting_sources`, `ready_to_define_question`, `investigation_in_progress`, `review_required`, and `reviewed_in_demo`. These are **workflow/review states, not medical or patient-condition states**.

The panel automatically follows the selected synthetic case and refreshes after the canonical workspace changes. A source amendment can therefore move the projection to `review_required`, surface the exact stale investigation IDs, describe the recorded amendment, and suggest reconciliation as a bounded workflow action. Stale responses are discarded after case changes, and the test suite verifies that Alpha source text cannot appear in Beta's mission projection.

This slice does **not** add identity, consent, patient goals, PHI support, medication intelligence, acute-safety escalation, diagnostic inference, literature appraisal, trial matching, treatment selection, therapeutic development, care coordination, outcome interpretation, or platform learning. It is a source-grounded workflow orientation surface for the synthetic engineering reference only.

## Fictional evidence and case applicability slice

The evidence form supports only the explicit `OI-SYNTHETIC-EVIDENCE/1` format with `Rights: original-synthetic`. Use the bundled `examples/synthetic/demo-evidence.txt` text. That declaration is not legal clearance for arbitrary user-supplied text. No third-party paper, article body, guideline, or real oncology data is retrieved or reused.

The UI can register an original fictional evidence item, attach a manually-authored relationship and applicability assessment to a case-specific question, include selected assessments when drafting an investigation, inspect the exact source text/line/hash, and withdraw a fictional item. An explicit `Amends: EVIDENCE-ID@LATEST-VERSION` replacement or withdrawal flags every dependent investigation in every affected synthetic case as stale, while retaining older source versions for audit. Assessments for superseded/withdrawn evidence cannot be included in new drafts.

The labels `supports`, `contradicts`, and `applicable` are human-entered **fictional engineering data**, not determinations of evidence quality, clinical benefit, trial eligibility, or clinical relevance. The prototype has no clinician identity verification or legal rights-verification service. Never use real patient records or copyrighted publication text. Run the unit/HTTP tests before reviewing the UI; browser execution requires a separate interactive verification.

## Bibliographic metadata panel

The public bibliography panel is **not linked to the selected synthetic patient**. It displays an authored Crossref-format test record using an offline local JSON fixture. The local demo server denies live lookups by default. To explicitly enable an operator-requested DOI-only Crossref lookup:

```bash
PYTHONPATH=src python -m open_intelligence serve --enable-crossref-live
```

Optional: `--crossref-contact operator@example.org` adds the operator-supplied contact email to the DOI-only metadata request, not a patient address. Crossref's current [access policy](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) describes rate limits and polite contact requirements. The prototype enforces one concurrent DOI lookup and a conservative one-second gap.

Only the public DOI is transmitted to a fixed Crossref API endpoint, and only bibliographic metadata fields are rendered. Abstracts, article text, full-text links, evidence grades and patient identifiers are never included in the output. The UI does not attach metadata to a clinical assertion or claim patient relevance. Live service behavior and medical usefulness require separate evaluation. No patient data should ever be used in this demo.

## Meta investigation layer (Meta Model API, OI-008)

The investigation layer is the first visible Meta tool use in the
product. It is server-side only and bounded by design:

- `POST /api/cases/{case}/investigations` with
  `{"question_id": N, "template": "evidence-summary"|"timeline-gaps"|"evidence-applicability", "mode": "live"|"replay"}`
- `GET /api/cases/{case}/investigations` lists investigations;
  `GET /api/cases/{case}/investigations/{id}` returns one, always
  labeled `kind=hypothesis`, `review_state=pending`.
- Live mode calls Meta Model API (`muse-spark-1.3`) with a fixed
  template plus the case's current assertions and fictional evidence
  assessments; the operator key comes from `META_API_KEY` only.
  Without the key, live returns 503 and points at replay.
- Every model claim is validated before storage: citations must
  resolve, uncertainty must be low/moderate/high, and
  recommendation/treatment/dosing language is dropped by the guard
  and recorded. Claims that fail any check are dropped, never
  repaired. Empty results abstain with a reason instead of guessing.
- Replay mode serves the recorded fixture
  (`examples/synthetic/demo-investigation.json`) through the same
  validation, labeled `mode=replay`, `model=recorded-replay`.
- A source amendment marks the case's investigations stale, like
  drafts. See `docs/META_MODEL_API.md` for the provider record.

Run it locally:

```bash
PYTHONPATH=src python -m open_intelligence seed
PYTHONPATH=src python -m open_intelligence serve
# Create a question, then POST an investigation with mode=replay
# (offline) or mode=live (with META_API_KEY set in the server env).
```

Remaining proof step: a live-server run against the real API with
the operator key set, before the demo. The API completion itself
was verified separately on 2026-10-31.
