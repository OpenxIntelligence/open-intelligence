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

How this was produced: by reading the repository — workflow files,
import statements, `src/`, `tools/`, the `web/` directory, and
`examples/synthetic/` plus `examples/patient-access/`. Every entry
below says how it was verified. Anything not verified is marked
UNVERIFIED; nothing here is a guessed license or clearance.

## Runtime

| Component | Version / pin | Source in repo | License / notes |
|---|---|---|---|
| Python | 3.11+ claimed in `README_IMPLEMENTATION.md`; CI pins 3.13 in all three workflows | `.github/workflows/synthetic-tests.yml`, `.github/workflows/crossref-metadata.yml`, `.github/workflows/ui-glance.yml` | Python is a runtime, not a shipped dependency. |
| Python standard library only | No third-party packages | Import scan of `src/`, `tools/`, `tests/` on 2026-11-02: `argparse`, `base64`, `concurrent`, `dataclasses`, `datetime`, `hashlib`, `http` (including `http.client`), `json`, `os`, `pathlib`, `re`, `shutil`, `signal`, `socket`, `sqlite3`, `struct`, `subprocess`, `sys`, `tempfile`, `threading`, `time`, `unittest` (including `unittest.mock`), `urllib`, plus first-party `open_intelligence` and `tools` | Standard library modules ship with Python. No `requirements.txt`, `pyproject.toml`, `package.json`, or `Pipfile` exists in the repo. |
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
