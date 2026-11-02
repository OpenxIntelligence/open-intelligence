# Software Bill of Materials (SBOM) — Open Intelligence demo, branch `oi/safety-packet`

Scope: this inventory covers the current tree on this branch (current
`main` merged in; refreshed 2026-11-02). It supersedes the earlier
`main`-only revision (`46bb1db`), which excluded the investigation
layer, the investigation panel, the clinician glance, and the Patient
Mission projection. All of those have since merged and are covered
here, together with the timeline projection, the incoming board and
patient view, the What Changed panel, the discovery-rights linkage,
and the reviewed option/dependency view (routes, store tables, and
UI). If the tree changes again, this packet must be updated before it
is used for a submission.

Top-up (2026-11-02): six merged pull requests added 44 files — three
CI workflows, eight research probes plus a research-only requirements
lock and eight research unit tests, two offline evaluation tools, five
`tests/`, six docs/plan files, six `validation/iv01/` practice-packet
files, and five `validation/iv04/` preparation templates. Each is
covered by a row in the surfaces table below and an entry in
`ASSET_CATALOG.md`. All 44 are CI-only, test-only, research-only,
docs-only, or coordinator/blank-template material: none adds a demo
route, store table, UI panel, shipped dependency, model path, or
license decision. Existing entries are unchanged.

How this was produced: by reading the repository — workflow files,
import statements, `src/`, `tools/`, the `web/` directory, and
`examples/synthetic/` plus `examples/patient-access/`. Every entry
below says how it was verified. Anything not verified is marked
UNVERIFIED; nothing here is a guessed license or clearance.

## Runtime

### H1 API scope addition — issue #112

The historical demo inventory below covers the `src/open_intelligence`/`web`
prototype. The separate `apps/api` shell now has 24 pinned Python wheel artifacts,
including native components. Its exact review scope, hashes, embedded-runtime
notices and exclusions are maintained in
[`apps/api/dependency-license-inventory.json`](../../apps/api/dependency-license-inventory.json)
and [`THIRD_PARTY_NOTICES.md`](../../apps/api/THIRD_PARTY_NOTICES.md). Its first-party
gate generates a CycloneDX package inventory from checked wheel bytes. The H1
workflow and Dockerfile run that gate before installation. Neither this addition
nor a passing scan clears complete container/OS images or selects the project's
distribution license. The old standard-library-only description must not be
applied to `apps/api` or the separately recorded research tools.

| Component | Version / pin | Source in repo | License / notes |
|---|---|---|---|
| Python | 3.11+ claimed in `README_IMPLEMENTATION.md`; CI pins 3.13 in all three workflows | `.github/workflows/synthetic-tests.yml`, `.github/workflows/crossref-metadata.yml`, `.github/workflows/ui-glance.yml` | Python is a runtime, not a shipped dependency. |
| Legacy prototype: Python standard library | No third-party application packages in `src/open_intelligence` | Legacy application and its standard-library tests; separate research packages and `apps/api` are outside this claim. | Standard library modules ship with Python. Repository-root package manifests remain absent; the H1 API has its own reviewed lock under `apps/api`. |
| Node.js (CI only) | UNVERIFIED — not pinned; the workflows run `node --check` and `node --test` on the runner's preinstalled Node | `.github/workflows/synthetic-tests.yml`, `.github/workflows/ui-glance.yml` | Used only to syntax-check JavaScript and run the JS source-reader tests in CI. Not part of the demo. |

## First-party code shipped

| Path | What it is |
|---|---|
| `src/open_intelligence/__main__.py`, `store.py`, `__init__.py` | Local case-ledger server and SQLite store. Serves only on `127.0.0.1` by default. `store.py` owns all ledger tables (cases, source versions, assertions, questions, snapshots, evidence, rights, discovery, investigations, options, biological assets; see the surfaces table below). |
| `src/open_intelligence/timeline.py` | Read-only timeline projection: ledger ordering, coverage gaps, and date conflicts. No writes, no model, no external fetch. |
| `src/open_intelligence/mission.py` | Read-only Patient Mission projection over `CaseStore.state()`: workflow states only, never a second patient record. |
| `src/open_intelligence/changes.py` | Read-only what-changed-since-review projection: new sources, amendments with a mechanical finding-key diff, stale investigations with cause, new questions. Reports ledger facts only. |
| `src/open_intelligence/investigation.py` | The ONLY module that can call a model: bounded Meta Model API investigation over fixed templates, with citation validation, a language guard, and offline replay. See "Optional model path" below. |
| `src/open_intelligence/discovery.py` | Deterministic fictional literature/trial discovery parser (`OI-SYNTHETIC-DISCOVERY/1`) with a fail-closed language guard. No fetching, no eligibility or efficacy inference. |
| `src/open_intelligence/rights.py` | Pure fail-closed rights gate for external evidence sources: a permission counts only when explicitly `allowed` for that item and use on an active record. No network, no database, no model. |
| `src/open_intelligence/patient_access.py` | Deterministic patient-directed access adapter contract in front of the existing `CaseStore` ledger. Creates no second ledger, no authorization system, and no live EHR integration. |
| `tools/crossref_metadata.py`, `tools/__init__.py` | DOI-only Crossref metadata adapter (see `docs/CROSSREF_METADATA_BOUNDARY.md`). Live lookup is operator-invoked and disabled by default. |
| `web/index.html`, `web/app.js`, `web/mission.js`, `web/style.css`, `web/tokens.css`, `web/base.css` | Demo UI. Only local resources are loaded or requested (`/style.css`, `/app.js`, `/mission.js`, `/tokens.css`, `/base.css` via a local `@import`, and relative `/api/…` paths). No external scripts, fonts, or stylesheets. The DOI anchor in the UI is a user-clicked outbound link with a `https://doi.org/` prefix check, not a fetched asset. |
| `tests/` (32 files) | Python unit/HTTP tests, headless-Chromium journey scripts, and JS source-reader tests. Test-only code, not part of the demo. |
| `docs/` and `validation/` | Project documentation and evaluation contracts, including `docs/CROSSREF_METADATA_BOUNDARY.md`, `docs/SYNTHETIC_EVIDENCE_CONTRACT.md`, `docs/META_MODEL_API.md`, `docs/DISCOVERY.md`, `docs/RIGHTS_BROKER.md`, `docs/TEMPORAL_REASONING.md`, `docs/CHANGE_COMPARISON.md`, `docs/UI_GLANCE_ITERATION.md`, and the unadjudicated `validation/iv01/` contracts. |
| `examples/synthetic/`, `examples/patient-access/` | Fictional demo inputs (see `ASSET_CATALOG.md`). |

## Covered demo surfaces (routes, store tables, UI)

Each row names the module, the HTTP routes served by
`src/open_intelligence/__main__.py`, the SQLite tables in
`src/open_intelligence/store.py`, and the UI panel in `web/`.

| Surface | Module | Routes | Store tables | UI |
|---|---|---|---|---|
| Timeline projection | `timeline.py` | `GET /api/cases/{id}/timeline` | Reads `source_versions`, `assertions`, `events` only | `#timeline` panel with Source Change Explorer |
| Clinician glance | UI-only reorder over `/state`; no new module or route | `GET /api/cases/{id}/state` (existing) | Reads existing ledger tables | `#assertions` glance findings, `#review-attention`, glance guide |
| Patient Mission panel | `mission.py` (+ `web/mission.js`) | `GET /api/cases/{id}/mission` | Reads `CaseStore.state()` only | `#patient-mission` panel |
| Incoming board and patient view | UI-only over existing routes; no new module or route | `GET /api/cases`, `GET /api/cases/{id}/state` (existing) | Reads existing ledger tables | `#incoming-board`, `#patient-view` |
| Investigation panel | `store.py` questions/snapshots; `investigation.py` for model runs | `POST /api/cases/{id}/questions`, `POST /api/cases/{id}/snapshots`, `POST /api/cases/{id}/snapshots/{n}/review`, `GET /api/cases/{id}/snapshots/{n}/export`, `GET /api/investigations/templates`, `GET/POST /api/cases/{id}/investigations`, `GET /api/cases/{id}/investigations/{n}` | `questions`, `snapshots`, `snapshot_sources`, `snapshot_evidence`, `snapshot_broker_links`, `investigations`, `review_events` | `#investigations` panel (questions, drafts, history, bounded model investigation) |
| What Changed panel | `changes.py` | `GET /api/cases/{id}/changes-since-review[?since_event_id=N]` | Reads ledger tables only | `#changes-since-review` panel |
| Discovery-rights linkage | `discovery.py`, `rights.py`, `store.py` | `POST /api/discovery/imports`, `GET /api/discovery`, `POST /api/cases/{id}/discovery-links`, `GET /api/cases/{id}/discovery`, `POST /api/rights/sources`, `POST /api/rights/sources/{n}/revoke`, `POST /api/rights/sources/{n}/correct`, `POST /api/cases/{id}/broker-links`, `POST /api/cases/{id}/broker-links/{n}/review` | `discovery_items`, `discovery_links`, `discovery_link_broker_links`, `rights_sources`, `rights_permissions`, `broker_links`, `rights_events` | Evidence assessments reference broker links; no separate discovery panel |
| Reviewed option/dependency view | `store.py` option methods | `GET /api/cases/{id}/options[?snapshot_id=N]`, `POST /api/cases/{id}/options`, `POST /api/cases/{id}/options/{n}/dependencies`, `POST /api/cases/{id}/options/{n}/tasks`, `POST /api/cases/{id}/tasks/{n}/status`, `POST /api/cases/{id}/options/{n}/threats`, `POST /api/cases/{id}/options/{n}/review` | `options`, `preparation_tasks`, `optionality_threats`, `option_dependencies`, `option_review_events` | `#options` panel (discussion only; epistemic status kept separate from review status) |
| Biological-asset provenance | `store.py` asset methods | `POST /api/cases/{id}/biological-assets`, `POST /api/cases/{id}/biological-assets/{n}/inventory-assertions` | `biological_assets`, `biological_inventory_assertions` | `#biological-assets` panel (provenance only; no files stored) |
| Patient-access adapter | `patient_access.py` (no HTTP routes; exercised by tests) | None | Uses existing `source_versions`, `quarantine`, `events` tables only | None |
| CI-only research workflow (not shipped; runs probes that hit live public endpoints read-only) | `.github/workflows/public-research.yml` | None — CI job only | None | None |
| CI-only RNA workflow (not shipped; fixed-scope processed-RNA probe, aggregates only) | `.github/workflows/rna-analysis.yml` | None — CI job only | None | None |
| CI-only single-cell workflow (not shipped; research-only numpy/h5py install, aggregates only) | `.github/workflows/single-cell-analysis.yml` | None — CI job only | None | None |
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
| `actions/checkout` | `v4` in all three workflows | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/checkout` repository before any external distribution. |
| `actions/setup-python` | `v5` in all three workflows | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/setup-python` repository before any external distribution. |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` (SHA pin) in `synthetic-tests.yml` and `ui-glance.yml` | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/upload-artifact` repository before any external distribution. Preserves test logs and the archived source under test for 7 days. |
| Runner OS | `ubuntu-latest` in all three workflows | GitHub-hosted runner image; not shipped. Workflow permissions are `contents: read`. |
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
4. This refresh was produced by reading files only: no test suite,
   browser journey, or `git` command was run to verify it (the
   sandboxed shell cannot mount proc). Re-run the suite — including
   `tests/test_safety_packet.py` — before submission.
5. Top-up note (2026-11-02, read from the workflow files): the three
   new workflows pin
   `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` and
   `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065`
   by SHA rather than the `@v4`/`@v5` tags asserted in
   `tests/test_safety_packet.py` (`KNOWN_ACTIONS`), so that guard's
   workflow-pins invariant no longer matches the tree. This is
   reported here explicitly; the workflows and the guard are left
   untouched. The research-only `tools/research/requirements.lock`
   is not one of the root package-manager filenames the guard
   checks, and no new files were added under `examples/` or `web/`,
   so those invariants are unaffected. Like the refresh above, this
   top-up was produced by reading files only — no test suite or
   `git` command was run. Re-run the suite before submission.
