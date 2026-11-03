# Open Intelligence — connected development workspace

This branch joins the existing connected patient workflow (#221) and reviewed ordinary-text/PDF records (#215). It is a Python/SQLite/browser reference application, not the separate H1 React/FastAPI/PostgreSQL implementation and not a clinical release.

## Run locally

From this checkout with Python 3.10 or newer:

```sh
python3 run_open_intelligence.py
```

Open **http://127.0.0.1:8765**. The default database is `.local/workspace.sqlite`; `--port` and `--db` select alternatives. The default starts empty. `--with-examples` explicitly imports the existing independently fictional examples.

Ordinary text and structured fixtures use the existing standard-library services. PDF preview additionally requires the unchanged source-owner optional dependency in the same Python environment:

```sh
python3 -m pip install --require-hashes --only-binary=:all: --no-deps -r requirements-pdf.lock
```

No live literature or model provider is enabled by the launcher. It binds to loopback and clears the inherited supported model-API credentials for this process. These controls are not production authentication or authorization.

## One workspace, two original-record input paths

Create an independently fictional case in **Workspace setup & next steps**. Do not use actual, public, disguised or case-derived patient records.

**Add a record** accepts bounded ordinary UTF-8 text or supported text-bearing PDF files. Inspect the original text or frozen PDF extraction, confirm the selected case and metadata, and explicitly select exact passages and their classifications. Confirmation records manual transcription, not verified identity, consent or professional review. Original bytes and any frozen PDF rendition remain distinct. Findings keep their user-selected classification, transcription receipt, original hash and, for PDFs, physical-page/extraction-line/page-line and rendition hashes.

**Add original records** retains the source-owned structured batch adapter: `OI-SYNTHETIC-REPORT/1` UTF-8/LF `.txt` fixtures, 1–20 files, at most 64 KiB each and 1 MiB total. Its stricter BOM/CRLF rules are not applied to the ordinary-text adapter. Previewing a batch makes no import. Imported, duplicate, quarantined, rejected, unknown and unattempted outcomes remain distinct; an ambiguous result stops subsequent writes without automatic retries or an invented rollback.

Both adapters use the existing CaseStore/source owner. They do not create another patient or evidence ledger. Pending mutations clear obsolete report downloads and Composer previews. Case changes and new workspace creation preserve unfinished input rather than silently moving it to another case.

## Connected review and follow-through

Inspect findings in **Your record and open questions** and use their exact-source actions. Add a question in **Investigate a question**, inspect Composer's source-bound context, and use the explicitly labelled recorded replay where needed. A replay is an unreviewed demonstration, not live scientific inference, and does not close a question.

Prepare the report through the separate **Prepare a reviewable draft** form. The automatic model-run-to-draft feature from the original #166 stack is not included in this clinical composition. Inspect the saved report before any **Demo review acknowledgment**; that acknowledgment is not professional sign-off.

Use **Follow-through tasks** to record an owner, due date, question/source binding and progression. Completion records a statement by the operator, not an external action. These tasks are document-bound; the application does not fabricate an unrecorded passage or PDF-page anchor.

The plain-language report includes the existing source and task history, retaining manual-origin and PDF provenance. Its download uses the accepted displayed snapshot. An explicit source amendment preserves old originals and completed-task history, marks affected open work for reassessment, and invalidates outdated reports. Reopen the same database to retain its history.

## PDF limits

Original files are at most 64 KiB. PDFs are limited to 20 physical pages, 64 KiB extracted UTF-8 text and 512 extraction lines; manual review accepts at most 30 single-line passages. Extraction runs in the source-owned bounded worker and requires its exact pinned parser version. Unsupported encrypted/active-content/form/annotation or image-only/unextractable inputs are refused rather than silently converted. No OCR is provided. Extraction and page references do not establish visual fidelity, table interpretation or clinical accuracy. See `docs/engineering/DOCUMENT_INTAKE.md` for the maintained source-owner contract and full restrictions.

## Authority and release boundaries

The governed knowledge/evidence/report/review libraries retain separate actor, patient, purpose, content-class and export checks. They are not exposed as new unauthenticated clinical export endpoints. Browser demonstration review is distinct from the backend nonterminal returned-for-review receipt. Publisher permissions remain declarations in independently fictional fixtures, not actual content grants.

No real-patient deployment, production identity/consent/tenancy, clinical validity, professional signature or independent external review is established. The H1 migration, broader #183 workspace redesign and #190 annotation revisions remain separate integration work. Main and source-owner branches are not automatically merged.

## Verification

```sh
PYTHONPATH=src:tests:. python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/test_*.js
PYTHONPATH=src:tests:. python3 tests/document_intake_browser_journey.py
```

Full PDF tests require the exact parser; browser tests require Chrome/Chromium with loopback access. See `docs/engineering/CONNECTED_PATIENT_WORKFLOW.md` and the final PR verification receipt for exact source pins, observed failures, successful runs and retained artifacts. Separate or overlapping test totals are not additive.
