# Open Intelligence — connected development workspace

This extends the existing application, not a second patient record or replacement architecture. Start without seeding a database or installing third-party packages:

```sh
python3 run_open_intelligence.py
```

Open **http://127.0.0.1:8765**. Python 3.10 or newer is required. The default database is `.local/workspace.sqlite`. Another port or path can be selected with `--port` and `--db`. `--with-examples` explicitly imports the existing fictional Alpha/Beta examples; the default starts empty.

## Complete development journey

1. Create a workspace using a fictional alias and an uppercase reference. For the supplied authored examples, use `CASE-START`.
2. Add `examples/synthetic/workspace-start-original.txt` through **Add original records**. Inspect the unchanged source text and confirm it is fictional before import. Source identity, original bytes, timeline, findings and missingness use the existing ledger.
3. Add a question in **Investigate a question**, inspect its source-bound Composer context, and run **Replay**. Replay is a recorded demonstration, not a live model.
4. Select **Prepare review draft** on the run. The existing backend creates a versioned report with its original source dependencies; generation does not constitute review.
5. Inspect the report and use its explicit **Demo review acknowledgment**. This is not clinician credentialing or a clinical signature.
6. Import `examples/synthetic/workspace-start-amended.txt`. The original remains accessible, affected reports become stale, and the question reopens. Explicitly run a new investigation and prepare its new draft; previous history is not overwritten.
7. Reload the page or restart the program using the same database. Case, sources, questions, report versions and review history persist.

The same existing workspace contains patient-oriented wording, source history, research/evidence assessment, bibliography, timeline, worklist and review history. Availability of a control is not evidence that hospital integration or clinical reasoning is implemented.

## Track source acquisition and amended receipts (draft extension)

The optional **Records to obtain** section records fictional source-acquisition tasks *inside the same case database*. Enter the requested record, expected fictional organization and document category; this does not contact an institution or establish that a test is clinically indicated. Request creation is idempotent under its scoped stable request key. No external records-request communication is implemented.

After a matching original is imported, choose its exact **current source version** and click **Mark received with selected original**. This records the canonical source version in the request and appends an event to the existing case event ledger; mere filename matching is not treated as verified receipt. A cancelled request cannot be fulfilled. If the linked source is later amended, its historical receipt is preserved and the status becomes `source_superseded_reconciliation_needed`; select the updated version explicitly to reconcile it. An amendment never silently updates an old receipt. The original report remains available.

The APIs in this synthetic-only stage are `GET/POST /api/cases/{CASE}/record-requests`, `POST /api/cases/{CASE}/record-requests/{ID}/receive` and `POST /api/cases/{CASE}/record-requests/{ID}/cancel`. There is no provider authentication, patient identity validation, consent, outreach, medical-record release authorization, PHI protection or external source verification. The accepted FastAPI/PostgreSQL and React/Vite contracts must absorb this first-party operational behavior after owner review; SQLite is only the existing local reference implementation.

Verification on this branch includes `PYTHONPATH=src python -m unittest discover -s tests -p test_record_acquisition.py -v` and the existing full workspace browser journey extended through request, receipt, amendment, manual reconciliation and reload. Only exact-head executed results establish software pass status.

## Boundaries

Use **independently authored fictional data only**, not actual, public or disguised patient records. File intake currently accepts UTF-8 `.txt` files with LF line endings and the existing `OI-SYNTHETIC-REPORT/1` contract, maximum 64 KiB. CRLF, BOM, invalid UTF-8 and unsupported formats are rejected rather than silently normalized. There is no normal PDF/OCR extraction or clinical inference here. Source statements are authored annotations, not model discoveries. A checkbox cannot prove consent, identity or data rights.

The launcher binds only to loopback, does not enable live literature/Crossref, and clears inherited supported model-API credentials for this process. This is not production authentication, a PHI environment or a deployed clinical service. Actual identities, patient/proxy permissions, clinician approval, licensed scientific evidence, clinical evaluation and production operations remain separate integration gates.

The accepted H1 target remains FastAPI/PostgreSQL and React/Vite/TypeScript. This increment makes the existing stdlib/SQLite reference application operable end to end while preserving its canonical contracts; it does not claim that migration is complete. No project distribution license or third-party clearance is selected.

## Implementation ownership

The original case/source/review data owners remain authoritative. This extension adds a bounded operational request table to the original CaseStore schema, case-scoped HTTP routes in its existing handler, and a separate UI partial; it does not introduce a patient or source ledger. `workspace_host.py` composes a trusted first-party HTML partial and serves three extra static assets; all application APIs are inherited. `workspace-entry.js` is the thin adapter to existing browser selection/render functions, not a second store. Missing template anchors fail explicitly, requiring reconciliation with the owner.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_workspace_start_http.py -v
node --test tests/test_intake.js
PYTHONPATH=src python tests/workspace_start_browser_journey.py
```

The last command requires a Chrome/Chromium environment that permits loopback navigation. Hosted verification captures desktop/mobile screenshots, actual source, test logs and an incomplete source/declaration SBOM. Counts and claims must refer to the exact verified revision.
