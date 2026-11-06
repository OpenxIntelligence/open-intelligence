# Software Bill of Materials (SBOM) — Open Intelligence demo, `main`

Scope: this inventory covers the current tree on `main` (HEAD
`4b13bc2`; refreshed 2026-11-05). It supersedes the 2026-11-02
revision, which described the pre-submission tree on the
`oi/safety-packet` branch. If the tree changes again, this packet
must be updated before it is used for a submission.

Top-up (2026-11-05): 682 files were added to `main` since
2026-11-02 — 397 under `apps/`, 181 under `docs/`, 57 under
`tests/`, 25 under `src/`, 6 under `web/`, 6 under `tools/`, 3 under
`examples/`, 3 under `.github/`, plus the repository-root
`requirements-pdf.lock`. (Counted with `git log --since=2026-11-02
--diff-filter=A --name-only main`; the count is files added, not net
growth.) The demo-asset inventory in `ASSET_CATALOG.md` is still
file-by-file; the non-demo growth is summarized by category below
and in the surfaces table, with safety-relevant new files named
individually. Nothing in the top-up adds a model path, a shipped
dependency to the legacy demo core, or a license decision. The one
new runtime dependency is the optional hash-pinned `pypdf` PDF
intake runtime (see below).

How this was produced: by reading the repository — workflow files,
import statements, `src/`, `tools/`, the `web/` directory,
`examples/synthetic/` plus `examples/patient-access/` — and by
running the full vanilla test suite on the refold base (`main`
`4b13bc2`: 772 tests, 17 failures, all pre-existing
`test_pdf_intake` failures from the missing local `pypdf`, zero
other failures) and `git` commands to measure what changed. Every
entry below says how it was verified. Anything not verified is
marked UNVERIFIED; nothing here is a guessed license or clearance.

## Product scope

Open Intelligence is a general, patient-centered intelligence
platform. Cancer bioinformatics is its starting domain, not its
definition. Nothing in this packet limits the platform to oncology.

## Runtime

### H1 API scope addition — issue #112

The historical demo inventory below covers the `src/open_intelligence`/`web`
prototype. The separate `apps/api` shell now has 26 pinned Python
packages in its inventory (was 24 at the 2026-11-02 revision),
including native components. Its exact review scope, hashes,
embedded-runtime notices and exclusions are maintained in
[`apps/api/dependency-license-inventory.json`](../../apps/api/dependency-license-inventory.json)
and [`THIRD_PARTY_NOTICES.md`](../../apps/api/THIRD_PARTY_NOTICES.md). Its first-party
gate generates a CycloneDX package inventory from checked wheel bytes. The H1
workflow and Dockerfile run that gate before installation. Neither this addition
nor a passing scan clears complete container/OS images or selects the project's
distribution license. The old standard-library-only description must not be
applied to `apps/api` or the separately recorded research tools.

The H1 PostgreSQL migration chain on `main` now ends at
`SCHEMA_REVISION = "0018_laboratory_questions"`. The 0016 fork (two
revisions, `0016_fhir_laboratory_sources` and
`0016_manual_task_dependency`, both descending from
`0015_manual_report_context`) is converged on `main` by
`0017_lab_manual_convergence`. The H1 React tree (`apps/web`,
`open-intelligence-h1-web` 0.1.0) has its own `package.json` and
`package-lock.json` and is installed with `npm ci` in `h1-web.yml`;
it is outside the legacy demo's standard-library claim and outside
the repository-root package-manifest guard, which checks the root
only.

| Component | Version / pin | Source in repo | License / notes |
|---|---|---|---|
| Python | 3.11+ claimed in `README_IMPLEMENTATION.md`; CI pins Python 3.12 or 3.13 per workflow (six 3.12/3.12.16 pins, three 3.13 pins across the nine workflows) | `.github/workflows/*.yml` | Python is a runtime, not a shipped dependency. |
| Legacy prototype core: Python standard library | No third-party application packages in `src/open_intelligence`, with one optional exception (see next row) | Legacy application and its standard-library tests; separate research packages and `apps/api` are outside this claim. | Standard library modules ship with Python. Repository-root package manifests remain absent except the single optional PDF lock below; the H1 API has its own reviewed lock under `apps/api`. |
| Optional bounded PDF intake runtime: `pypdf` | `pypdf==6.21.4`, hash-pinned, in the repository-root `requirements-pdf.lock` (install with `--require-hashes --only-binary=:all: --no-deps`) | `requirements-pdf.lock`; `src/open_intelligence/pdf_intake.py`, `pdf_worker.py`; `docs/engineering/DOCUMENT_INTAKE.md`; notice in `THIRD_PARTY_NOTICES/pypdf.txt` | BSD-licensed (notice on file). Runs only in a separate fresh process (`python -I -B` by absolute path, imports no application state) for bounded PDF text extraction. Not installed with the demo by default; without it the PDF intake tests fail (17 pre-existing `test_pdf_intake` failures on a bare checkout) and the intake route refuses PDF input. Not a renderer, OCR engine, malware scanner, or clinical interpreter. |
| Node.js (CI only) | UNVERIFIED — not pinned; the workflows run `node --check` and `node --test` on the runner's preinstalled Node, and `h1-web.yml` runs `npm ci` on it | `.github/workflows/synthetic-tests.yml`, `.github/workflows/ui-glance.yml`, `.github/workflows/h1-web.yml` | Used only to syntax-check JavaScript, run the JS source-reader tests, and install the H1 React tree in CI. Not part of the demo. |

## First-party code shipped

| Path | What it is |
|---|---|
| `src/open_intelligence/__main__.py`, `store.py`, `__init__.py` | Local case-ledger server and SQLite store. Serves only on `127.0.0.1` by default. `store.py` owns all ledger tables (71 tables; see the surfaces table below). The B-01 fictional-actor gate lives in `__main__.py`: case routes require an `X-Fictional-Actor` header naming an actor with a live grant (`actor_grants`, deny-by-default), and every case access is written to `access_log`. The `access_log` table has no HTTP route or UI on `main`. |
| `src/open_intelligence/timeline.py` | Read-only timeline projection: ledger ordering, coverage gaps, and date conflicts. No writes, no model, no external fetch. |
| `src/open_intelligence/mission.py` | Read-only Patient Mission projection over `CaseStore.state()`: workflow states only, never a second patient record. |
| `src/open_intelligence/changes.py` | Read-only what-changed-since-review projection: new sources, amendments with a mechanical finding-key diff, stale investigations with cause, new questions. Reports ledger facts only. |
| `src/open_intelligence/investigation.py` | The ONLY module that can call a model: bounded Meta Model API investigation over fixed templates, with citation validation, a language guard, and offline replay. See "Optional model path" below. Verified: `META_API_KEY` / `api.meta.ai` appear only in this module and in `__main__.py` (environment read). |
| `src/open_intelligence/discovery.py` | Deterministic fictional literature/trial discovery parser (`OI-SYNTHETIC-DISCOVERY/1`) with a fail-closed language guard. No fetching, no eligibility or efficacy inference. |
| `src/open_intelligence/rights.py` | Pure fail-closed rights gate for external evidence sources: a permission counts only when explicitly `allowed` for that item and use on an active record. No network, no database, no model. |
| `src/open_intelligence/patient_access.py` | Deterministic patient-directed access adapter contract in front of the existing `CaseStore` ledger. Creates no second ledger, no authorization system, and no live EHR integration. |
| `src/open_intelligence/citation_verifier.py` | Identifier-level citation verification for the #224 evidence contract. Used by the investigation validator. |
| `src/open_intelligence/evidence_catalog.py` | Offline evidence metadata contract and isolated SQLite reference index. Supports the citation verifier; no HTTP route of its own. |
| `src/open_intelligence/clinician_overview.py` | Read-only clinician overview projection for the synthetic demo. |
| `src/open_intelligence/patient_attention.py` | Read-only patient attention projection over the existing case ledger. |
| `src/open_intelligence/owned_questions.py` | Read-only per-question gap rollup over the case ledger (B-06). |
| `src/open_intelligence/case_search.py` | Read-only case search and triage list over the existing case ledger. |
| `src/open_intelligence/provenance.py` | Read-only source provenance and amendment-history projection. |
| `src/open_intelligence/synthetic_metrics.py` | Read-only synthetic-fixture metrics projection over the case ledger. |
| `src/open_intelligence/followthrough.py` | Case follow-through tasks: human-owned records of agreed work. |
| `src/open_intelligence/scoped_review.py` | Scoped human review: per-snapshot scope notes, dissent, and handoff. |
| `src/open_intelligence/task_receipts.py` | Task completion receipts and derived dependency-loss flags (B-09). |
| `src/open_intelligence/patient_registry.py`, `src/open_intelligence/postgres_registry.py`, `src/open_intelligence/sql/patient_registry_postgres.sql` | Canonical patient reference registry; no PHI or identity proofing. The PostgreSQL port is B-01b research integration only, not a new identity owner, patient database, production authorization, PHI permission, or clinical signing mechanism. No vanilla HTTP routes. |
| `src/open_intelligence/document_intake.py`, `pdf_intake.py`, `pdf_worker.py` | Bounded document intake and explicit manual passage transcription; the PDF supervisor runs bounded `pypdf` text extraction in a separate fresh process. See the `pypdf` row above. |
| `src/open_intelligence/care_records.py` | Descriptive-only language guard for second-opinion and survivorship records. |
| `src/open_intelligence/packet.py`, `patient_report.py`, `synthesis.py` | Deterministic report/packet assembly and deterministic grouping of human-entered labels (`synthesis.py` never merges dissent into one verdict). |
| `tools/crossref_metadata.py`, `tools/__init__.py` | DOI-only Crossref metadata adapter (see `docs/CROSSREF_METADATA_BOUNDARY.md`). Live lookup is operator-invoked and disabled by default. |
| `web/index.html`, `web/app.js`, `web/mission.js`, `web/case_search.js`, `web/clinician-overview.js`, `web/consent.js`, `web/intake.js`, `web/provenance.js`, `web/report.js`, `web/style.css`, `web/tokens.css`, `web/base.css` | Demo UI. `index.html` loads eight local scripts only (`/app.js`, `/case_search.js`, `/clinician-overview.js`, `/consent.js`, `/intake.js`, `/mission.js`, `/provenance.js`, `/report.js`). All requests go to relative `/api/…` paths; verified by grep across all `web/*.js`: no `http(s)` URL appears except the `https://doi.org/` prefix check on the user-clicked DOI anchor, which is an outbound link, not a fetched asset. No external scripts, fonts, or stylesheets. The packet guard test checks `index.html`, the three stylesheets, and `app.js` + `mission.js` fetch targets; the six newer scripts were verified by the same grep for this refold (all targets relative `/api/…`). |
| `tests/` (82 Python files) | Python unit/HTTP tests, headless-Chromium journey scripts, and JS source-reader tests. Test-only code, not part of the demo. |
| `docs/` and `validation/` | Project documentation and evaluation contracts, including `docs/CROSSREF_METADATA_BOUNDARY.md`, `docs/SYNTHETIC_EVIDENCE_CONTRACT.md`, `docs/META_MODEL_API.md`, `docs/DISCOVERY.md`, `docs/RIGHTS_BROKER.md`, `docs/TEMPORAL_REASONING.md`, `docs/CHANGE_COMPARISON.md`, `docs/UI_GLANCE_ITERATION.md`, `docs/engineering/DOCUMENT_INTAKE.md`, and the unadjudicated `validation/iv01/` contracts. |
| `examples/synthetic/`, `examples/patient-access/` | Fictional demo inputs (see `ASSET_CATALOG.md`). |

## Covered demo surfaces (routes, store tables, UI)

Each row names the module, the HTTP routes served by
`src/open_intelligence/__main__.py`, the SQLite tables in
`src/open_intelligence/store.py`, and the UI panel in `web/`.
Routes are enumerated from `__main__.py`; tables from `store.py`.

| Surface | Module | Routes | Store tables | UI |
|---|---|---|---|---|
| Timeline projection | `timeline.py` | `GET /api/cases/{id}/timeline` | Reads `source_versions`, `assertions`, `events` only | `#timeline` panel with Source Change Explorer |
| Clinician glance | UI-only reorder over `/state`; no new module or route | `GET /api/cases/{id}/state` (existing) | Reads existing ledger tables | `#assertions` glance findings, `#review-attention`, glance guide |
| Clinician overview | `clinician_overview.py` | `GET /api/cases/{id}/clinician-overview` | Reads existing ledger tables | `#clinician-overview` panel (`web/clinician-overview.js`) |
| Patient Mission panel | `mission.py` (+ `web/mission.js`) | `GET /api/cases/{id}/mission` | Reads `CaseStore.state()` only | `#patient-mission` panel |
| Incoming board and patient view | UI-only over existing routes; no new module or route | `GET /api/cases`, `GET /api/cases/{id}/state` (existing) | Reads existing ledger tables | `#incoming-board`, `#patient-view` |
| Case search | `case_search.py` | UI over existing routes; no new route | Reads `cases` | `#case-search` panel (`web/case_search.js`) |
| Investigation panel | `store.py` questions/snapshots; `investigation.py` for model runs | `POST /api/cases/{id}/questions`, `POST /api/cases/{id}/snapshots`, `POST /api/cases/{id}/snapshots/{n}/review`, `GET /api/cases/{id}/snapshots/{n}/export`, `GET /api/investigations/templates`, `GET/POST /api/cases/{id}/investigations`, `GET /api/cases/{id}/investigations/{n}` | `questions`, `snapshots`, `snapshot_sources`, `snapshot_evidence`, `snapshot_broker_links`, `investigations`, `review_events` | `#investigations` panel (questions, drafts, history, bounded model investigation) |
| Question rollup and synthesis | `owned_questions.py`, `synthesis.py` | `GET /api/cases/{id}/questions/{n}/rollup`, `GET /api/cases/{id}/questions/{n}/synthesis`, `GET /api/cases/{id}/snapshots/{n}/synthesis`, `GET /api/cases/{id}/snapshots/{n}/synthesis-report`, `GET /api/cases/{id}/snapshots/{n}/synthesis-report-patient` | Reads `questions`, `snapshots` | Synthesis panels (hypotheses kept visibly separate from facts) |
| What Changed panel | `changes.py` | `GET /api/cases/{id}/changes-since-review[?since_event_id=N]` | Reads ledger tables only | `#changes-since-review` panel |
| Discovery-rights linkage | `discovery.py`, `rights.py`, `store.py` | `POST /api/discovery/imports`, `GET /api/discovery`, `POST /api/cases/{id}/discovery-links`, `GET /api/cases/{id}/discovery`, `POST /api/rights/sources`, `POST /api/rights/sources/{n}/revoke`, `POST /api/rights/sources/{n}/correct`, `POST /api/cases/{id}/broker-links`, `POST /api/cases/{id}/broker-links/{n}/review` | `discovery_items`, `discovery_links`, `discovery_link_broker_links`, `rights_sources`, `rights_permissions`, `broker_links`, `rights_events` | Evidence assessments reference broker links; no separate discovery panel |
| Reviewed option/dependency view | `store.py` option methods | `GET /api/cases/{id}/options[?snapshot_id=N]`, `POST /api/cases/{id}/options`, `POST /api/cases/{id}/options/{n}/dependencies`, `POST /api/cases/{id}/options/{n}/tasks`, `POST /api/cases/{id}/tasks/{n}/status`, `POST /api/cases/{id}/options/{n}/threats`, `POST /api/cases/{id}/options/{n}/review` | `options`, `preparation_tasks`, `optionality_threats`, `option_dependencies`, `option_review_events` | `#options` panel (discussion only; epistemic status kept separate from review status) |
| Option safety and discussion records | `store.py` option methods | `POST /api/cases/{id}/options/{n}/counterevidence`, `POST /api/cases/{id}/options/{n}/safety-flags`, `POST /api/cases/{id}/options/{n}/flags`, `POST /api/cases/{id}/options/{n}/dimension-notes`, `POST /api/cases/{id}/flags/{n}/resolve`, `POST /api/cases/{id}/dimension-notes/{n}/acknowledge` | `option_counterevidence`, `option_safety_flags`, `option_flags`, `option_flag_events`, `option_dimension_notes`, `option_dimension_events` | Option panels. Case-switch guard: the picker guard blocks a switch while a case-scoped narrative field is non-empty, and the clear loop empties it once a switch is allowed (`tests/test_case_switch_guards.py` passes on `main`). Known asymmetry, recorded here, not hidden: `evidence-withdraw-reason` and `option-description` are guard-only (a switch is blocked but the text is not cleared); `question-text` and `report-text` plus several date/trigger fields are clear-only; `evidence-text` is in neither by verdict. |
| Biological-asset provenance | `store.py` asset methods | `POST /api/cases/{id}/biological-assets`, `POST /api/cases/{id}/biological-assets/{n}/inventory-assertions` | `biological_assets`, `biological_inventory_assertions` | `#biological-assets` panel (provenance only; no files stored) |
| Biological explanations | `store.py` bio methods | `GET/POST /api/cases/{id}/bio-explanations`, `POST /api/cases/{id}/bio-explanations/{n}/assay-observations` | `bio_explanations`, `bio_assay_observations` | `#bio-explanation-list` |
| Patient-access adapter | `patient_access.py` (no HTTP routes; exercised by tests) | None | Uses existing `source_versions`, `quarantine`, `events` tables only | None |
| Visits and amendments | `store.py` visit methods | `POST /api/cases/{id}/visits`, `POST /api/cases/{id}/visits/{n}/amend` | `visits`, `visit_versions` | `#visit-list` |
| Consents | `store.py` consent methods | `GET /api/cases/{id}/consents`, `POST /api/cases/{id}/consents/{n}/withdraw` | `consent_records`, `consent_versions` | Consent panel (`web/consent.js`) |
| Patient goals and notes | `store.py` goal/note methods | `GET/POST /api/cases/{id}/patient-goals`, `POST /api/cases/{id}/patient-goals/{n}/status`, `POST /api/cases/{id}/patient-goals/{n}/amendments`, `GET/POST /api/cases/{id}/patient-notes`, `POST /api/cases/{id}/patient-notes/{n}/amendments` | `patient_goals`, `patient_goal_versions`, `patient_notes`, `patient_note_versions` | `#goal-list`, `#note-list` |
| Patient attention | `patient_attention.py` | `GET /api/cases/{id}/patient-attention` | Reads existing ledger tables | `#patient-attention` |
| Follow-through tasks | `followthrough.py` | `GET /api/cases/{id}/followthrough`, `GET/POST /api/cases/{id}/followthrough-tasks`, `POST /api/cases/{id}/followthrough-tasks/{n}/status` | `followthrough_tasks`, `followthrough_task_events` | Follow-through panel |
| Second-opinion requests | `store.py` + `care_records.py` language guard | `GET/POST /api/cases/{id}/second-opinion-requests`, `POST /api/cases/{id}/second-opinion-requests/{n}/response`, `POST /api/cases/{id}/second-opinion-requests/{n}/review` | `second_opinion_requests`, `second_opinion_responses`, `second_opinion_materials`, `second_opinion_review_events` | `#second-opinion-list` |
| Survivorship plans | `store.py` + `care_records.py` language guard | `GET/POST /api/cases/{id}/survivorship-plans`, `POST /api/cases/{id}/survivorship-plans/{n}/items`, `POST /api/cases/{id}/survivorship-items/{n}/review`, `POST /api/cases/{id}/survivorship-items/{n}/trigger` | `survivorship_plans`, `survivorship_items`, `survivorship_review_events` | `#survivorship-list` |
| Workspace questions | `store.py` | `GET/POST /api/cases/{id}/workspace-questions`, `POST /api/cases/{id}/workspace-questions/{n}/status`, `POST /api/cases/{id}/workspace-questions/{n}/links`, `POST /api/cases/{id}/workspace-questions/{n}/links/{n}/unlink` | `workspace_questions`, `workspace_question_links`, `workspace_question_history` | `#workspace-question-list` |
| Evidence assessments and withdrawal | `store.py` evidence methods | `GET /api/cases/{id}/evidence-assessments`, `GET /api/cases/{id}/evidence-quality`, `GET /api/evidence/{n}`, `POST /api/evidence/{n}/withdraw`, `POST /api/evidence/imports`, `GET /api/examples/amendment`, `GET /api/examples/evidence`, `GET /api/examples/wrong-patient` | `evidence_assessments`, `evidence_quality_assessments`, `evidence_versions`, `evidence_changes` | Evidence panels |
| Document intake and preview | `document_intake.py`, `pdf_intake.py`, `pdf_worker.py` | `POST /api/cases/{id}/imports`, `GET /api/cases/{id}/documents(/preview)?` | `document_intake_metadata` | Intake panel (`web/intake.js`). PDF text extraction is the optional `pypdf` runtime above. |
| Packet export | `packet.py` | `GET /api/cases/{id}/packet` | Reads ledger tables only | `#packet-summary` |
| Bibliography | `tools/crossref_metadata.py` | `GET /api/bibliography/example`, `GET /api/bibliography/lookup`, `GET /api/bibliography/status` | None (fixture/lookup only) | `#bibliography` panel |
| Synthetic metrics | `synthetic_metrics.py` | `GET /api/metrics/synthetic` | Reads ledger tables only | `#metrics` |
| Review queue and receipts | `task_receipts.py`, `store.py` | `GET /api/cases/{id}/review-queue`, `GET /api/cases/{id}/review-queue/receipts` | `review_receipts`, `review_events` | `#review-queue` panels |
| Scoped review | `scoped_review.py` | `GET/POST /api/cases/{id}/snapshots/{n}/scoped-decisions`, `scoped-dissents`, `scoped-handoffs` | `scoped_review_decisions`, `scoped_review_dissents`, `scoped_review_handoffs` | `#scoped-review-list` |
| Re-review tasks | `store.py` | `GET/POST /api/cases/{id}/re-review-tasks`, `POST /api/cases/{id}/re-review-tasks/{n}/close` | `re_review_tasks` | `#re-review-list` |
| Provenance | `provenance.py` | `GET /api/cases/{id}/provenance` | Reads ledger tables only | Provenance panel (`web/provenance.js`) |
| Patient report | `patient_report.py` | `GET /api/cases/{id}/patient-report` | Reads ledger tables only | Report panel (`web/report.js`) |
| Case portfolio | UI over existing routes | `GET /api/cases/{id}/portfolio` | Reads ledger tables only | `#portfolio-list` |
| Sources, quarantine, identity | `store.py` | `GET /api/cases/{id}/sources/{n}`, `GET /api/cases/{id}/sources/{n}/download`, `POST /api/cases/{id}/quarantine/{n}/correct`, `GET /api/cases/{id}/identity-qualifiers`, `GET /api/cases/{id}/limitation-notes` | `source_versions`, `quarantine`, `quarantine_corrections`, `identity_qualifiers`, `limitation_notes` | Source panels |
| CI-only research workflow (not shipped; runs probes that hit live public endpoints read-only) | `.github/workflows/public-research.yml` | None — CI job only | None | None |
| CI-only RNA workflow (not shipped; fixed-scope processed-RNA probe, aggregates only) | `.github/workflows/rna-analysis.yml` | None — CI job only | None | None |
| CI-only single-cell workflow (not shipped; research-only numpy/h5py install, aggregates only) | `.github/workflows/single-cell-analysis.yml` | None — CI job only | None | None |
| CI-only offline scientific-safety workflow (not shipped; restricted-entrypoint and probe regression tests, no network) | `.github/workflows/offline-scientific-safety.yml` | None — CI job only | None | None |
| CI-only H1 API workflow (not shipped; dependency gate + migration, synthetic only) | `.github/workflows/h1-api.yml` | None — CI job only | None | None |
| CI-only H1 web workflow (not shipped; H1 React build + journey, fictional only) | `.github/workflows/h1-web.yml` | None — CI job only | None | None |
| Complementary docs only (not shipped, no code): independent-evaluation playbook, a proposed protocol, not an authorization | `docs/INDEPENDENT_EVALUATION_COLLABORATION.md` | None | None | None |
| Complementary docs only (not shipped, no code): blank evaluation packet template, unexecuted, no data | `docs/evaluation/PACKET_TEMPLATE.md` | None | None | None |
| Complementary docs only (not shipped, no code): blank results-register header, no rows | `docs/evaluation/RESULTS_REGISTER_TEMPLATE.csv` | None | None | None |
| Complementary docs only (not shipped, no code): experimental-loop extension proposal, not adopted | `docs/research/EXPERIMENTAL_LOOP_EXTENSION_2026-10-31.md` | None | None | None |
| Complementary docs only (not shipped, no code): HL7/Nano/model-fabric evaluation addendum, research, not a decision | `docs/research/HL7_NANO_MODEL_FABRIC_ADDENDUM.md` | None | None | None |
| Complementary docs only (not shipped, no code): IV-01 packet implementation plan | `docs/superpowers/plans/2026-10-31-iv01-packet.md` | None | None | None |
| Offline evaluation packager (not served): stdlib-only, no network; validates/packages fictional IV-01 inputs; never opens the coordinator key | `tools/evaluation_packet.py` | None — CLI tool | None | None |
| Offline evaluation preflight (not served): stdlib-only, no network; checks recorded fields/fingerprints; writes, activates, contacts, and scores nothing | `tools/evaluation_preflight.py` | None — CLI tool | None | None |
| Test-only (not shipped): packaging mechanics for the fictional IV-01 packet, not clinical performance | `tests/test_evaluation_packet.py` | None | None | None |
| Test-only (not shipped): JSON-boundary CLI regressions with fictional parser fixtures | `tests/test_evaluation_packet_json_boundary.py` | None | None | None |
| Test-only (not shipped): fail-closed preflight readiness checks, not clinical assessment | `tests/test_evaluation_preflight.py` | None | None | None |
| Test-only (not shipped): IV-01 evidence replay through the existing CaseStore; labels are not clinical truth | `tests/test_iv01_evidence_replay.py` | None | None | None |
| Test-only (not shipped): IV-01 store replay of practice fixtures without changing the app | `tests/test_iv01_store.py` | None | None | None |
| Research-only probe (not shipped): hits live public endpoints read-only (GDC open case metadata, pinned NCI-GDC dictionary); metadata in memory, receipts only | `tools/research/clinical_semantics_probe.py` | None — CLI in CI | None | None |
| Research-only probe (not shipped): hits live public endpoints read-only (GDC public TCGA-LUAD/BRCA/LAML metadata); in-memory only, aggregate receipts | `tools/research/gdc_projection_probe.py` | None — CLI in CI | None | None |
| Research-only probe (not shipped): hits live public endpoints read-only (fixed osteosarc.com catalog, S3 listing); raw rows stay in memory, aggregate receipts | `tools/research/public_case_intake.py` | None — CLI in CI | None | None |
| Research-only probe (not shipped): hits live public endpoints read-only (fixed TCIA CSV/ZIP, GDC public TCGA-LUAD); raw data in memory, counts/schema/hashes only | `tools/research/public_evidence_probe.py` | None — CLI in CI | None | None |
| Research-only environment record (not application dependencies): exact pins from research run 41294219202, installed into /tmp/oi-research-env in CI only | `tools/research/requirements.lock` | None | None | None |
| Research-only probe (not shipped): hits live public endpoints read-only (five fixed S3 processed-RNA assets); no raw reads, matrices, or recommendations | `tools/research/rna_expression_probe.py` | None — CLI in CI | None | None |
| Research-only experiment (not shipped, no network, no model API): LangGraph/SQLite process-boundary checks on original fictional state; needs the research env | `tools/research/runtime_probe.py` | None — CLI in CI | None | None |
| Research-only probe (not shipped): hits live public endpoints read-only (one fixed public processed h5ad object); only aggregates leave RAM | `tools/research/single_cell_probe.py` | None — CLI in CI | None | None |
| Research-only probe (not shipped): hits live public endpoints read-only (ClinicalTrials.gov/NLM registry records); aggregate observations, no eligibility advice | `tools/research/trial_screening_probe.py` | None — CLI in CI | None | None |
| Test-only (not shipped): hand-derived fictional cases for the semantics probe; no patient records or model calls | `tools/research/test_clinical_semantics_probe.py` | None | None | None |
| Test-only (not shipped): original fictional fixtures for the projection probe; no patient records | `tools/research/test_gdc_projection_probe.py` | None | None | None |
| Test-only (not shipped): original fictional catalog fixtures; no copied clinical/genomic records | `tools/research/test_public_case_intake.py` | None | None | None |
| Test-only (not shipped): original fictional audit-calculation tests; no patient data | `tools/research/test_public_evidence_probe.py` | None | None | None |
| Test-only (not shipped): original fictional RNA fixtures; expectations independent of real-case values | `tools/research/test_rna_expression_probe.py` | None | None | None |
| Test-only (not shipped): original fictional meaning/attachment fixtures | `tools/research/test_semantic_evidence.py` | None | None | None |
| Test-only (not shipped): original fictional aggregate fixtures; no patient cell records embedded | `tools/research/test_single_cell_probe.py` | None | None | None |
| Test-only (not shipped): original fictional trial-registry tests; no true patient or trial records | `tools/research/test_trial_screening_probe.py` | None | None | None |
| Test-only (not shipped): restricted research entrypoints; named-person and public-case acquisition refusal | `tools/research/test_restricted_research_entrypoints.py` | None | None | None |
| Test-only (not shipped): named-person case data disabled in research paths | `tools/research/test_sid_case_data_disabled.py` | None | None | None |
| Coordinator material (not shipped, not for participants): IV-01 practice-packet readme; original AI-assisted fictional fixtures, not adjudicated cases | `validation/iv01/README.md` | None | None | None |
| Coordinator material (not shipped, not for participants): reviewer rubric/preregistration contract; methodology, not a validated instrument | `validation/iv01/SCORING.md` | None | None | None |
| Coordinator material (not shipped, not for participants): two fictional cases (CASE-EVAL-A/B), ten OI-SYNTHETIC sources, eleven receipts, three cutoffs | `validation/iv01/cases.json` | None | None | None |
| Coordinator-only key (not shipped, DO NOT INCLUDE in participant packets): designer reference, not independent ground truth | `validation/iv01/coordinator_key.json` | None | None | None |
| Coordinator material (not shipped): IV-01 protocol record, status not_activated, all thresholds null | `validation/iv01/protocol.json` | None | None | None |
| Coordinator material (not shipped): blank results header, no rows or outcomes | `validation/iv01/results_template.csv` | None | None | None |
| Blank preparation template (not shipped, no data, no authorization): IV-04 activation checklist, all decisions unmade | `validation/iv04/ACTIVATION_CHECKLIST.md` | None | None | None |
| Blank preparation template (not shipped, no data, no authorization): IV-04 roles/independence instructions, not an assessment | `validation/iv04/INDEPENDENCE_AND_ROLES.md` | None | None | None |
| Blank preparation template (not shipped, no data, no authorization): draft invitation, NOT SENT, recipient/scope unestablished | `validation/iv04/INVITATION_BRIEF.md` | None | None | None |
| Blank preparation template (not shipped, no data, no authorization): IV-04 handoff readme; drafting assets, no outreach or study | `validation/iv04/README.md` | None | None | None |
| Blank preparation template (not shipped, no data, no authorization): unapproved activity/authorization record, disposition not_reviewed | `validation/iv04/decision_template.json` | None | None | None |

## CI-only components (not shipped in the demo)

| Component | Pin | Notes |
|---|---|---|
| `actions/checkout` | `v4` in `synthetic-tests.yml`, `crossref-metadata.yml`, `ui-glance.yml`; SHA `11d5960a326750d5838078e36cf38b85af677262` in `public-research.yml`, `rna-analysis.yml`, `single-cell-analysis.yml`, `offline-scientific-safety.yml`, `h1-api.yml`, `h1-web.yml` | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/checkout` repository before any external distribution. |
| `actions/setup-python` | `v5` in `synthetic-tests.yml`, `crossref-metadata.yml`, `ui-glance.yml`; SHA `a26af69be951a213d495a4c3e4e4022e16d87065` in the six SHA-pinned workflows above | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/setup-python` repository before any external distribution. |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` (SHA pin) in `synthetic-tests.yml`, `ui-glance.yml`, `public-research.yml`, `h1-api.yml`, `h1-web.yml` | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/upload-artifact` repository before any external distribution. Preserves test logs and the archived source under test for 7 days. |
| Runner OS | `ubuntu-latest` in all nine workflows | GitHub-hosted runner image; not shipped. Workflow permissions are `contents: read`. |
| Headless Chromium | Runner-installed, required by the `tests/browser_*.py`, `tests/patient_mission_browser_journey.py`, and `tests/ui_glance_journey.py` scripts | Test-only. The journey code uses only the standard library (CDP over a WebSocket); no browser library is vendored or depended on. Not part of the demo. |

## Optional model path (merged; bounded and off by default)

- The ONLY model-touching module is
  `src/open_intelligence/investigation.py`, served through
  `POST /api/cases/{id}/investigations` with `mode` `live` or
  `replay` and rendered in the `#investigations` panel. No model
  weights are shipped, and no other module calls a model.
- Live mode sends one bounded POST to the fixed host
  `https://api.meta.ai/v1/messages` (model `muse-spark-1.3`),
  using an operator-supplied `META_API_KEY` from the server
  environment only. The key is never stored, logged, committed, or
  sent to the browser. Without the key the route returns 503 and
  points at replay mode.
- There is no free-text prompt: the prompt is assembled server-side
  from a fixed template (`TEMPLATES` in `investigation.py`) plus
  the fictional case's own assertions and evidence assessments. The
  payload carries only the fictional case id, the question text, and
  source/assessment statements — no patient-like fields, no real
  data, no credentials.
- Every returned claim is validated before storage (citations must
  resolve to a current source version or an assessment for the
  question; uncertainty must be low/moderate/high; treatment
  recommendation/therapy selection/dosing/diagnosis language is
  dropped by the guard and recorded as dropped, never repaired).
  Stored output is always `kind=hypothesis`,
  `review_state=pending` — a proposal for review, never a
  conclusion or recommendation.
- Replay mode (`mode=replay`) serves the recorded human-authored
  fixture `examples/synthetic/demo-investigation.json` through the
  same validation and guard, labeled `mode=replay`,
  `model=recorded-replay`, so the demo runs fully offline.

## What is deliberately NOT in the demo

- No model weights, no agent framework, and no other vendor's model
  or hosted AI. The only model use is the bounded Meta path above,
  which is off unless the operator supplies a key (per
  `docs/META_MODEL_API.md`).
- No third-party UI library, clinical backend, hosted API, or professional
  license is required (per `README_IMPLEMENTATION.md`).
- No fonts, images, icons, audio, or video assets. The `web/` directory
  contains only HTML, JavaScript, and CSS authored for this repository.
- No database file is shipped. The SQLite database is created at runtime
  under `.local/` when the local server is seeded; it is not committed.
- No project distribution license is selected. Public repository visibility
  is not a license grant (per `README.md` and `AGENTS.md`). This packet
  does not choose a license.
- No real accounts, roles, or sessions on `main`. The B-01
  fictional-actor gate (header, deny-by-default, grants) is the only
  access control on `main`; real accounts arrive with PR #515 (see
  `README.md`).

## External network use at runtime

- Default: none. The local server binds to `127.0.0.1`, the bibliography
  panel shows an offline local fixture, and model investigation runs in
  replay mode without a key.
- Opt-in only, Crossref: a single DOI-only lookup to the fixed Crossref HTTPS host,
  invoked explicitly by the operator (`--live`). It sends only the supplied
  public DOI, rejects redirects, bounds response size and timeout, and does
  not retry. See `DATA_RIGHTS.md`.
- Opt-in only, model: a single bounded investigation POST to the fixed Meta
  API host, only when the operator supplies `META_API_KEY` and selects live
  mode. See "Optional model path" above and `DATA_RIGHTS.md`.

## Re-verify before submission

1. Re-run the import scan and the `uses:` scan after any merge; update
   this file if either changes.
2. Read the license files of `actions/checkout@v4`,
   `actions/setup-python@v5`, and the pinned
   `actions/upload-artifact` revision and replace the three UNVERIFIED entries.
3. Confirm the runner Node version if the submission claims a Node version.
4. This refresh was verified by running the full vanilla suite on the
   refold base (`main` `4b13bc2`, 2026-11-05): 772 tests, 17
   failures, all in `test_pdf_intake` (missing local `pypdf`, a
   pre-existing environment gap, identical to the pre-change
   baseline), zero other failures — including
   `tests/test_safety_packet.py` and
   `tests/test_case_switch_guards.py`, which both pass.
5. Correction to the 2026-11-02 revision's §5 note: the guard's
   workflow-pins invariant DOES match the tree now. The guard
   (`tests/test_safety_packet.py`, `KNOWN_ACTIONS`) was updated to
   include the SHA pins used by the research/H1 workflows, and the
   distinct `uses:` pins across all nine workflows are exactly those
   five entries. The 2026-11-02 claim of a mismatch is withdrawn.
6. Coverage limit, recorded here: the guard's fetch-target check
   covers `app.js` and `mission.js` only. The six newer scripts
   (`case_search.js`, `clinician-overview.js`, `consent.js`,
   `intake.js`, `provenance.js`, `report.js`) were verified for this
   refold by grep (no `http(s)` URL in any of them; all request
   targets relative `/api/…`), not by the guard. If a later merge
   adds a fetched resource to one of those files, the guard will not
   catch it.
