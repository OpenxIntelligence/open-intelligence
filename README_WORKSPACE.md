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

## Patient and care-team views

`web/views.css` and `web/views.js` regroup the same page into two views without changing any original file, API or saved record. Every original section is moved, never copied or removed, so its controls, saved state and element IDs keep working.

- **Care team.** Incoming board, then Overview (setup, intake, counts, reported findings, review status, next investigation), Records & timeline, Investigations, Evidence & research, Review & changes, and Options & tasks. "Needs review" offers a direct comparison of the amended report versions. Investigations follow the working order (question, model run, saved drafts), with the hand-written draft form in a collapsible section that opens when it holds unsaved text. Source and comparison views dock on the right as an inspector instead of covering the page.
- **Patient.** Overview, My reports, Research and My questions. These are read-only summaries of the same case state: what changed in an amended report, each result with its plain status and exact source line, connected fictional research, and question status. Care-team authoring tools are hidden, not removed.
- **Switching views.** The header's **Dev view** switch exists for development only; real deployments would sign each person in to their own view. `?role=patient` or `?role=careteam` selects a view. For a side-by-side demo, open both in two windows with `&live=1`. Each window then re-reads the selected case every few seconds, unless a draft is unsaved or a source view is open.

Not included yet: patient messaging, an AI assistant for patients, reviewer accept/reject decisions and drafts that cite exact lines. Each needs its own reviewed change.

```sh
PYTHONPATH=src python -m unittest tests.test_workspace_start_http -v
PYTHONPATH=src python tests/role_views_browser_journey.py
```

## Boundaries

Use **independently authored fictional data only**, not actual, public or disguised patient records. File intake currently accepts UTF-8 `.txt` files with LF line endings and the existing `OI-SYNTHETIC-REPORT/1` contract, maximum 64 KiB. CRLF, BOM, invalid UTF-8 and unsupported formats are rejected rather than silently normalized. There is no normal PDF/OCR extraction or clinical inference here. Source statements are authored annotations, not model discoveries. A checkbox cannot prove consent, identity or data rights.

The launcher binds only to loopback, does not enable live literature/Crossref, and clears inherited supported model-API credentials for this process. This is not production authentication, a PHI environment or a deployed clinical service. Actual identities, patient/proxy permissions, clinician approval, licensed scientific evidence, clinical evaluation and production operations remain separate integration gates.

The accepted H1 target remains FastAPI/PostgreSQL and React/Vite/TypeScript. This increment makes the existing stdlib/SQLite reference application operable end to end while preserving its canonical contracts; it does not claim that migration is complete. No project distribution license or third-party clearance is selected.

## Implementation ownership

The original `app.js`, `index.html`, HTTP handler, source parser, CaseStore, model workflow and review engine remain unchanged. `workspace_host.py` composes a trusted first-party HTML partial and serves three extra static assets; all application APIs are inherited. `workspace-entry.js` is the thin adapter to existing browser selection/render functions, not a second store. Missing template anchors fail explicitly, requiring reconciliation with the owner.

```sh
PYTHONPATH=src python -m unittest discover -s tests -p test_workspace_start_http.py -v
node --test tests/test_intake.js
PYTHONPATH=src python tests/workspace_start_browser_journey.py
```

The last command requires a Chrome/Chromium environment that permits loopback navigation. Hosted verification captures desktop/mobile screenshots, actual source, test logs and an incomplete source/declaration SBOM. Counts and claims must refer to the exact verified revision.
