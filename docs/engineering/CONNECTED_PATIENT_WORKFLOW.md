# Connected patient workflow integration — 2 November 2026 local / 3 November UTC

## Scope
This candidate reconciles #175 (canonical patient/EHR/LIS/PWM, Composer v2, authorized evidence report and review receipt), #161 (source-linked patient record and question handoff), and #197/#174 (readable report, durable tasks, amendment attention, export freshness). It preserves existing owners rather than adding patient/source/evidence/review stores.

Source pins: #175 `1d5cd0502b5789371165539149dcecad8df5e551`; #161 `3df25cc417f308f7ea1247962656ffa2afc62d5d`; #197 `ad9713a443d2fe98e74f7d83605db776571e9929`. The four input tree hashes, including main `24519839aa8ac1ea3aff88a956349ba72798a72a`, are in `tools/compose_connected_patient_workflow.py`. Downloaded source archives were temporary PR merge checkouts; their complete Git tree IDs match the authored input commits.

## Reviewed conflict decisions
The existing CaseStore retains both its identity/revocation/review-receipt schema and the original follow-through schema. Investigation persistence keeps source-owner strict same-case question validation together with Composer v2 fingerprints and durable input receipts. The HTTP host exposes the original World Model and follow-through projections. Frontend refresh emits the report's invalidation/update events and performs the patient-record freshness checks. Both source-linked record UI and printable report remain accessible; print styles and patient-record styles are separate.

## New acceptance
`tests/test_connected_patient_workflow.py` uses the original #175 fixture and exercises the same question/source across its World Model, authorized prepared report, append-only returned receipt, readable case report and task history. An amendment flags open work, retains completed history and original bytes/hash, refuses the outdated evidence report, and survives reopening the store. Separate tests cover external-rights revocation and wrong-case task joins/mutations. Returned is nonterminal; task completion is recorded preparation, not clinical signoff or verified external delivery.

## Executed local evidence
- Three new cross-domain tests failed on #175 because the existing follow-through owner was absent, then passed after integration.
- Complete combined Python/domain/HTTP suite: **660 passed**, 41.281 seconds; command `PYTHONPATH=src:tests python -m unittest discover -s tests -p 'test_*.py' -v` with temporary databases in `/dev/shm`.
- All JavaScript suites: **87 passed**, 0 failed; `node --test tests/test_*.js`.
- Python compilation and JavaScript syntax passed. SQLite ResourceWarnings remain; memory-backed temporary files are not power-loss/disk-durability validation.
- Six original browser journeys were attempted locally. Managed Chromium refuses loopback pages; one attempt failed during DevTools startup. These are failed/uncompleted local browser gates, not passes. Hosted CI is required without weakening the assertions or security policy.
- Reproducible source recipe matches the tested source-owner bytes (aggregate SHA-256 `d97b838688c447f29fec035f363dfb5ba72d2bec9830a3c9f7fb10aa11364453`) and rejects a mismatched source tree before writes. It also refuses unrelated local content.

## Hosted gate and publication
The workflow checks out the exact PR head. On the one bootstrap branch it first creates a reproducible composition commit with pinned source-parent ancestry. Compilation, all application tests, all JavaScript tests, and the six original browser journeys must pass before a separate job can create a uniquely named integration branch. The create-only ref lease prevents overwriting an existing branch. No automatic PR merge, source-branch modification, production deployment or real-data operation is included. Receipts retain commit/tree, logs and source ZIP for seven days. Status at authoring: hosted verification pending; the subsequent PR/run receipts are the status authority.

## Limits
Synthetic reference prototype only. Domain authorization callbacks are not a production authenticated UI; the rights-qualified report remains a domain integration, not a newly exposed clinical endpoint. Existing sequential cross-store checks do not establish an atomic distributed snapshot. No real patient data, live model call, content-license grant, clinician approval, production identity/consent/tenancy, or clinical validity is established. The accepted H1 migration is not replaced. Further source-owner review is required before integration into main.

## Continuation: original intake and report convergence — 3 November 2026 UTC

This increment composes exact #210 `9735414c947c211ab20154638179d0be8ff2db32`
with #203 `f9ba8d66b56a7d6669ef0ffce902af6565e1b477` (extends #196/#179),
using shared #175 `1d5cd0502b5789371165539149dcecad8df5e551`. The imported
workspace host, batch-input owner and content-class rights retain their original
contracts and tests. CaseStore, clinical authority, original records, review and
follow-through schema remain unchanged. No new dependency or clinical route.

The new entry is `python run_open_intelligence.py --db PATH --port 8765`.
It starts empty without a seed command. Supported files are independently authored
`OI-SYNTHETIC-REPORT/1` UTF-8/LF text, not ordinary clinical documents or PDFs.
Selection/inspection is local; explicit confirmation permits sequential writes.
The original 20-file/64-KiB-per-file/1-MiB-batch bounds and individual receipts
remain. Unknown HTTP outcomes stop later writes and are never called rollbacks.

### Reproduced composition gaps and bounded corrections
- Intake's private fetch bypassed existing report write tracking. It now uses
  the host API with an optional raw HTTP envelope, preserving receipt classes
  while synchronously revoking the old report/download during writes.
- New workspace creation had a narrower dirty check than case switching. Both
  now use the existing protected fields plus all follow-through text/date fields,
  clear-due choice and unresolved writes. No draft is transferred to a new case.
- Composer emitted exact-source events with no receiver. The entry now routes
  only current same-case assertion anchors through the original source inspector;
  pending writes reject old actions. No new source cache or read authority.
- The preview did not observe source/evidence mutations. It now clears its
  fingerprint/actions, rejects obsolete reads and honors concurrent case/global
  write counts. A fresh context read is required; an old response cannot revive it.

### Executed evidence and boundaries
The untouched #210 baseline passed 660 Python tests locally. The missing-entry
test failed first; four real-client upload/report checks, three new-workspace/source
action checks and five additional preview/pending-write checks reproduced their
respective defects before the corrections. Final local application suite:
**686 Python/domain/HTTP tests passed in 33.620s**, **113 JavaScript checks passed**.
Counts overlap across focused suites. The first full Python attempt hit the local
90-second command deadline; the complete rerun above passed. Existing SQLite
ResourceWarnings remain. Temporary DBs in `/dev/shm` do not prove power-loss recovery.

Local Chromium failed before navigation because its root process could not start
with the normal sandbox. No new bypass was added. Hosted CI must exercise the
expanded empty-workspace journey plus all six original journeys on one exact
commit: actual disk files, original-source click, pending amendment, open/completed
tasks, real report download parity, unsaved-task veto, duplicate/quarantine, reload
and narrow layout. Hosted status at authoring is pending; PR/run receipts are the
completion authority. No independent external reviewer or clinical validation is
claimed.

This remains a loopback reference prototype. Content-specific rights are declared
provider inputs, not actual publisher grants. A visible Composer fingerprint is a
preview receipt, not a new authenticated clinical submission. Sequential checks
do not establish distributed atomicity or recall an exported file. H1 React/
FastAPI/PostgreSQL, PDF/intake correction and UX-redesign convergence remain separate
work. Main and source-owner branches are not merged or rewritten.

## Reviewed ordinary-text/PDF convergence — 2 November 2026 ET / 3 November UTC

Extends the existing #221 connected intake (`2a246b54bb29cbd844c77f06f8e3a20ddff8dcc7`) with the #215 original document/rendition and Patient Record owners (`3be1106b5cd34523c4746e2df6f123048beb5659`). No second patient, source, task, review or evidence ledger is introduced. Existing `source_versions`, source-owned intake metadata/frozen rendition children, assertions, questions, review receipts and tasks remain authoritative.

The incoming ordinary-document adapter is mounted as `document-intake.js`; the existing structured batch adapter keeps `intake.js`. Their distinct controls feed the same CaseStore. Composer is mounted once and its original inspector event is owned by the canonical application, not two listeners. Both launchers retain the shared pending-write/draft veto. A read-only PDF extraction preview is not a source write. A confirmed original save invalidates old report/download/Composer state before HTTP completes.

The existing World Model provenance validator is reused by knowledge and patient-report projections. User-selected classifications are not relabeled source-authored facts; missing or mismatched manual receipts/physical page anchors fail closed. Original SHA, frozen extraction SHA, transcription review SHA, physical page/global line/page line and extracted page hash survive into selected comparison packets and governed report hashes. Source-bound tasks retain original/extraction identities without inventing passage/page anchors. Returned review receipts remain nonterminal; completed tasks remain recorded statements, not verified external actions.

The existing real PDF browser acceptance now joins manual page-two selection to the same case's open/completed tasks and readable report, holds an actual amendment save to verify old actions are unavailable, downloads the exact accepted report, and retains old PDF/source/task/report history. Original source-owner PDF, Composer, evidence, numeric-hold, durable-run, patient-record, source-race and connected-intake tests are retained. Genuine PDF parsing requires the unchanged hash-pinned pypdf 6.21.4 runtime. No OCR, encrypted/active/image-only document support, general medical extraction or clinical accuracy is implied. Bounds remain 64 KiB originals,20pages,64 KiB text,512lines,30selected passages.

Local compilation and 172 JavaScript checks passed. Regression-first ordinary-text/report/route checks passed; the local environment has pypdf5.9.0 and could not install6.21.4, so PDF runs are explicitly unverified locally. A full local command exceeded its time limit. Hosted verification must install the pinned original runtime and run the entire combined suite/browser set. Exact head/tree, source archive and actual outcomes are recorded in the subsequent PR/run receipts, not inferred from source-owner test totals. Existing resource warnings remain.

Scope remains synthetic reference integration, draft/unmerged/undeployed. No independent external review, verified clinical actor/patient consent, production tenancy, real patient record, publisher grant or live model is established. The #183 redesign, #190 annotation revision workflow and H1 React/FastAPI/PostgreSQL migration remain separate source-owner work. Historical artifact/data purging is not claimed by the retained no-data CI guard.
