# Software Bill of Materials (SBOM) — Open Intelligence demo, main `46bb1db`

Scope: this inventory covers what the demo on `main` actually ships. It does
NOT cover unmerged pull requests (for example the Meta investigation layer,
the investigation panel, the clinician glance, or the Patient Mission
projection). When any of those merge, this packet must be updated before it
is used for a submission.

How this was produced: by reading the repository at `main` — workflow files,
import statements, the `web/` directory, and `examples/synthetic/`. Every
entry below says how it was verified. Anything not verified is marked
UNVERIFIED; nothing here is a guessed license or clearance.

## Runtime

| Component | Version / pin | Source in repo | License / notes |
|---|---|---|---|
| Python | 3.11+ claimed in `README_IMPLEMENTATION.md`; CI pins 3.13 | `.github/workflows/synthetic-tests.yml`, `.github/workflows/crossref-metadata.yml` | Python is a runtime, not a shipped dependency. |
| Python standard library only | No third-party packages | Import scan of `src/`, `tools/`, `tests/` on 2026-11-01: `argparse`, `base64`, `concurrent`, `dataclasses`, `datetime`, `hashlib`, `http`, `json`, `os`, `pathlib`, `re`, `shutil`, `signal`, `socket`, `sqlite3`, `struct`, `subprocess`, `sys`, `tempfile`, `threading`, `time`, `unittest`, `urllib`, plus first-party `open_intelligence` and `tools` | Standard library modules ship with Python. No `requirements.txt`, `pyproject.toml`, `package.json`, or `Pipfile` exists in the repo. |
| Node.js (CI only) | UNVERIFIED — not pinned; the workflows run `node --check web/app.js` on the runner's preinstalled Node | `.github/workflows/synthetic-tests.yml` | Used only to syntax-check JavaScript in CI. Not part of the demo. |

## First-party code shipped

| Path | What it is |
|---|---|
| `src/open_intelligence/__main__.py`, `store.py`, `__init__.py` | Local case-ledger server and SQLite store. Serves only on `127.0.0.1` by default. |
| `tools/crossref_metadata.py` | DOI-only Crossref metadata adapter (see `docs/CROSSREF_METADATA_BOUNDARY.md`). Live lookup is operator-invoked and disabled by default. |
| `web/index.html`, `web/app.js`, `web/style.css` | Demo UI. Only local resources are loaded (`/style.css`, `/app.js`). No external scripts, fonts, or stylesheets. DOI links in the UI are plain text links, not fetched assets. |
| `tests/` (6 files) | Unit, HTTP, and browser-journey tests. Test-only code, not part of the demo. |
| `docs/` | Project documentation, including `docs/CROSSREF_METADATA_BOUNDARY.md` and `docs/SYNTHETIC_EVIDENCE_CONTRACT.md`. |
| `examples/synthetic/` | Fictional demo inputs (see `ASSET_CATALOG.md`). |

## CI-only components (not shipped in the demo)

| Component | Pin | Notes |
|---|---|---|
| `actions/checkout` | `v4` in both workflows | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/checkout` repository before any external distribution. |
| `actions/setup-python` | `v5` in both workflows | License UNVERIFIED in this packet — read the `LICENSE` file in the `actions/setup-python` repository before any external distribution. |
| Runner OS | `ubuntu-latest` in both workflows | GitHub-hosted runner image; not shipped. Workflow permissions are `contents: read`. |
| Headless Chromium | Runner-installed, required by `tests/browser_journey.py` | Test-only. The journey code uses only the standard library (CDP over a WebSocket); no browser library is vendored or depended on. Not part of the demo. |

## What is deliberately NOT in the demo

- No model, model weights, or model API call on `main`. The demo runs
  without any model provider. (Model use exists only in unmerged work and
  is out of scope for this packet.)
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

- Default: none. The local server binds to `127.0.0.1` and the bibliography
  panel shows an offline local fixture.
- Opt-in only: a single DOI-only lookup to the fixed Crossref HTTPS host,
  invoked explicitly by the operator (`--live`). It sends only the supplied
  public DOI, rejects redirects, bounds response size and timeout, and does
  not retry. See `DATA_RIGHTS.md`.

## Re-verify before submission

1. Re-run the import scan and the `uses:` scan after any merge; update
   this file if either changes.
2. Read the license files of `actions/checkout@v4` and
   `actions/setup-python@v5` and replace the two UNVERIFIED entries.
3. Confirm the runner Node version if the submission claims a Node version.
