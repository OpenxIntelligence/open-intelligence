# Connected patient workflow integration — 2 November 2026 local / 3 November UTC

## Current increment: annotation revisions through governed reports

This continuation composes #229 at `abbe3bf981ac0583f59eab45d853edd7b01a6aa6` into the verified #235 owner at `4f96b835f1306e0f92b803cd20ca6e46e2180216`. The exact shared source ancestor is #215 at `3be1106b5cd34523c4746e2df6f123048beb5659`. All 250 #235 source blobs and its complete tree (`34af78b0794e65c37ef5a06ab56bfa8c81467c64`) were matched locally before composition; #229's tree is `3c996392cf584a0bcb5bee7682b8295e4b110a60`. Local snapshot commit IDs are not substituted for these published source parents.

### Corrected-selection contract

The existing append-only `document_annotation_revisions` owner supplies `annotation_revision_id`, `annotation_revision`, `initial_transcription_review_sha256`, and the effective `transcription_review_sha256` through the shared source validator, clinical context, Composer, Patient World Model, knowledge comparison, quotation packet, readable/governed report and prepared receipt. Initial intake confirmation, current selection review, document version, original bytes and frozen PDF extraction remain separate identities. Returning to an earlier selection creates a new revision even if its text and review digest recur.

Manual comparison proposals and selected evidence quotations now require both captured revision fields. This closes a concrete integration defect: SQLite can reuse the assertion row ID when corrections replace the current projection. An old ID alone must not retarget a proposal or an already-selected quote. Authored-source input shapes remain unchanged. Missing, malformed, stale or extraneous identity is refused; explicit reselection is required after a correction.

The existing receipt owner reconstructs its complete expected patient reference under the same `BEGIN IMMEDIATE`. Revision fields are strict positive signed 64-bit integers, not booleans/floats/strings. Missing or changed identity, including an A→B→A return to the same passage/hash, produces no receipt or event. A correction after a preparation receipt commits withholds the report body and preserves the nonterminal historical event; it is not a delivery or clinical approval.

Clinical note links add a nullable reference to the existing annotation history. New manual links retain their captured selection; removing/changing the current selection does not erase or rewrite an earlier note citation. Corrected, superseded and unbound legacy references have distinct review-required states. Legacy manual links lacking a captured revision remain visible without inventing an old quotation or classification. First-time note attachment also checks `expected_annotation_revision` under the existing write lock. Omission means initial revision 1; a corrected source requires explicit current revision. Existing links cannot be rebound; a new note version can cite the revised selection. No separate note/source history store is created.

Readable reports display the annotation revision/ID, initial and effective review hashes, original identity and physical PDF coordinates. The client refuses incomplete/mixed revision provenance before print or download. Earlier snapshot exports and downloaded reports retain their captured selections. Manual classification still does not establish clinical review.

### Verification record

The unchanged pinned PDF environment passed all 17 #235 governed/readable provenance baseline tests before integration. Default Python lacked the pinned parser; that failed setup was corrected by using the existing Python 3.12.14 / pypdf 6.21.4 environment, not by changing parser limits. The merged pre-fix source lost revision fields in #235's shared validator: the inherited nine-test PDF World Model suite exposed 48 failed assertions/subtests and one missing-field error. All nine then passed after integrating #229's checks into the shared owner.

New acceptance exercises correction, repeated selection content, stale comparisons and quotes, exact locked receipt validation, corrections at/beyond the receipt boundary, unchanged original bytes/history after restart, and preserved note links. Readable-report/client tests cover malformed IDs/hashes, mixed same-source revisions and cross-source revision reuse. The existing 11 browser journeys are retained; the two #229 text/PDF correction journeys join the same gate, with actual readable-report rendering and downloads added to the PDF journey. The complete local suite passed **871 Python/domain/HTTP tests in 319.662 seconds** and **193 JavaScript executions** with zero failures or skips. No SQLite ResourceWarning was emitted by this Python 3.12.14 run. The no-download guard and all five policy regressions passed; all 11 workflow YAML files parse. An independent reviewer found no blocking or minor finding and independently passed the 32 governed-annotation, clinical-annotation and readable-provenance checks. These focused executions overlap the full suite and are not extra distinct capabilities.

Local Chrome/Chromium is absent: the actual PDF browser command stopped before application interaction and is not counted as a pass. The published draft PR receipt records the subsequent hosted results at the exact candidate commit/tree; this document does not substitute a source-parent result for that execution. The UI and offline workflows now check out the exact PR head, and the no-download guard runs when any workflow is changed. The connected gate retains all 13 actual browser journeys and archives source, screenshots and receipts.

### Boundaries and current H1 dependency

Only independently authored fictional records/evidence and the existing labelled recorded replay are used. No new dependency, live model, patient-derived data, rights grant, source acquisition or clinical action is introduced. The existing PDF limits and manual numeric HOLD remain. Source, evidence, question, report, receipt and follow-through owners remain shared.

H1 #234 has advanced beyond the older tests-only audit below. Its source-fidelity/authority implementation at `65eafebd9fda221dc79789619133c78c6d01dc60` passed [API verification](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41568014664) and [React verification](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41568014897), extending #222. This continuation does not duplicate that owner or claim authenticated governed-report transport, production authorization, clinical validation or deployment. Repository-wide workflow administration and historical data/artifact cleanup remain outside this branch's completed evidence.

## Historical #235 increment: reviewed PDF provenance through governed reports

This increment builds on #210 at `9735414c947c211ab20154638179d0be8ff2db32`, selectively incorporates #203 at `f9ba8d66b56a7d6669ef0ffce902af6565e1b477` for content-specific evidence rights, and composes the PDF/patient-record behavior from #215 at `3be1106b5cd34523c4746e2df6f123048beb5659`. All three source PRs remain separate, draft and unmerged. The #210 source artifact was checksum verified and all 215 files matched its official Git blobs; all 223 local #215 files matched their pinned Git blobs before composition.

The patient-facing value is continuity: one reviewed document can remain traceable through the clinical context, Patient World Model, investigation, evidence comparison, readable report, governed evidence report and review history. The implementation reuses existing patient, EHR, LIS, source, evidence, question, report, receipt and follow-through owners.

### Source and report contracts

- Authored structured-text sources retain their original four-field prepared source reference: assertion ID, source-version ID, original SHA-256 and global line.
- Manually transcribed text additionally retains `classification_origin`, `annotation_method`, `clinical_review` and `transcription_review_sha256`. The status is user-selected and clinical review is `not_performed`.
- PDF passages additionally retain `text_origin`, `extraction_sha256`, `source_page`, `page_line` and `page_text_sha256`. An extraction line is not represented as a line in the original PDF bytes.
- The existing World Model receipt/anchor validation is shared through `source_provenance.py`; the projection contract is preserved. Knowledge context, Composer alignment, quotation packets, rendered reports, clinical source/note links and prepared-report receipts carry the same provenance.
- Readable local reports display manual status and PDF source coordinates. The governed report binds the richer patient reference through existing packet/body hashes, content-specific rights checks, independent export/review-return permissions and final context rechecks.
- `CaseStore.add_review_receipt` derives the current reference from original assertions and the immutable intake receipt/rendition under its existing `BEGIN IMMEDIATE`. A missing, relabeled, mismatched, extraneous or malformed field is rejected before receipt/event persistence. It does not open a nested `state()` transaction.
- Receipt events retain reference/hash metadata, not the report body or quoted clinical content. Report preparation and return remain nonterminal. A final permission failure withholds the report body while preserving an already committed preparation receipt.

### Composition decisions

The existing #210 identity, authority, clinical integration and follow-through methods remain. The PDF child tables, immutable extraction/receipt behavior, UI and pinned `pypdf==6.21.4` dependency are reused from #215. No new ledger, clinical interpretation, report schema or source store is added; the existing source schema gains only the previously tested PDF/intake child tables required by that source owner.

The numeric Composer retains #210's rights-broker fingerprint binding and #215's exclusion of manual numerical passages from its qualified calculation contract. Existing text Unicode source rendering, case/race guards, readable-report export and follow-through routes are preserved. The local HTTP host does not expose the governed report service.

Five obsolete live-research CI steps were present in the #210 baseline. The existing no-download guard first failed on them. This candidate replaces them with offline boundary tests; all five guard regressions then passed. No patient-data acquisition command was executed. This branch correction does not close the separate historical repository/artifact audit or change main.

### Acceptance and verification

`tests/test_pdf_governed_report.py` uses the existing canonical patient/EHR/LIS fixture, then creates an independently authored two-page PDF in the same `LinkedLabCaseStore`. It exercises manual/PDF provenance through clinical context, Composer, World Model, content-specific permitted evidence, exact quotation packet, governed report and persisted nonterminal receipt. It also covers manual plain text and legacy authored sources; missing/mismatched/relabeled provenance; actual-source verification at receipt write; source amendment; independent actor/purpose/export restrictions; late evidence-rights withdrawal; and preserved sources/receipts after close/reopen.

The meaningful red phase exposed both loss of manual provenance and a legacy-only prepared reference being accepted for a real PDF. The initial report tests and direct downgrade test passed after the contract/write changes. An independent alignment test also exposed original SHA/document/version disagreement between knowledge and Composer. That correction passed its regression, and all 12 new governed PDF-report tests passed in 21.020 seconds. The focused 38-test readable-report/HTTP suite and 41-test intake/Composer/HTTP suite passed.

Final combined local verification: **797 Python/domain/HTTP tests passed in 324.468 seconds**, with no failures or unclosed-database ResourceWarnings in the captured run; **144 JavaScript tests passed**, zero failed or skipped, in 4.415 seconds. Commands: `PYTHONPATH=src:tests python -m unittest discover -s tests -p 'test_*.py' -v` using the hash-locked PDF virtual environment, and `node --test tests/test_*.js`. The five CI no-download policy regressions are included in the Python suite. All 11 workflow YAML files parse. These are software regressions on fictional data, not clinical validation.

`tests/test_patient_report_manual_provenance.py` verifies manual/PDF wording, exact source references, authored compatibility and the existing local report HTTP/text-export path. The extended document-intake browser journey retains the earlier actual PDF upload, source jump, evidence, recorded replay, review, amendment and restart checks while adding readable report/follow-through coverage.

The first hosted connected run [41567236186](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41567236186), at `cb1d38f78ddc5440fd583442ceaf569290ca07eb`, passed all 797 Python tests, all 144 JavaScript tests and the six retained #210 browser journeys, then failed the existing 390px Patient View overflow assertion in the PDF journey. The screenshot isolated #210's printable-report link: its global no-wrap button style exceeded the narrow panel, and the existing patient-record-item wrapping rule did not apply to this sibling link. A scoped max-width and wrapping rule corrects that link; the browser assertions remain byte-identical. This failed run is not counted as passing integrated acceptance. Its artifact checksum was verified before inspection.

The independent UI run [41567236197](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41567236197), report/export run [41567236147](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41567236147) and offline boundary run [41567236241](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41567236241) passed that initial candidate. The UI and offline jobs checked out GitHub's temporary merge commit; its tree matched the candidate exactly.

Hosted verification of the narrow-link correction is pending at this checkpoint. [Draft PR #235](https://github.com/OpenxIntelligence/open-intelligence/pull/235) records the final exact-commit workflow receipt. The connected gate retains all six #210 browser journeys and all five #215 PDF/Composer/rights journeys; it archives source, logs, screenshots and receipts. Earlier 660-test results below belong to #210 and are not results for this increment.

### Remaining boundaries

Only independently authored fictional sources and evidence are used. No Sid data, real patient-derived synthetic data, live model, scientific efficacy claim, licensed guideline content, clinical sign-off or real clinical action is involved. The PDF parser keeps its existing 64 KiB / 20-page / 512-line bounds and no-OCR limits. It runs in a constrained process, not an operating-system security sandbox.

This is source-level integration of the Python/SQLite reference, not the completed H1 migration. The newer #222 source-authority owner preserves `oi.pg-source-world-model/1`; #234 targets convergence with #216's validation/transaction protections but was tests-and-plan only at the audit. #223's authenticated source-only preflight is not governed-report transport. #229's later annotation revision identity is not incorporated here and must be bound through the report/receipt contract before corrected selections from that branch are supported. These existing owners should be reconciled rather than creating another World Model or report service.

Main at `24519839aa8ac1ea3aff88a956349ba72798a72a` has no Sid acquisition in the inspected RNA/single-cell workflow paths, but its public-research workflow still declares three probes that fetch public individual-level TCIA/GDC clinical and specimen records. Reading those scripts established their behavior; no probe or medical-input endpoint was executed. Public trial-registry metadata retrieval is a separate activity and is not patient-record acquisition. #219 and this candidate retire their inherited probes, but neither is merged. Administrative workflow enablement and historical data/artifact cleanup remain unverified.

Governed report transport, production identity/consent, real-patient security, external publisher grants, clinical validation and release authorization remain separate gates. No source branch or main is merged or closed by this package.

---

## Historical #210 composition receipt

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
