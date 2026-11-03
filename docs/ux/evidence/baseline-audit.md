# H1 React baseline verification and visual audit

Research date: 2 November 2026, America/New_York.
Source: hosted PR #200, commit `d8de9aaca352cc58b64e9e32440f4ea248b02cb8`, tree `f46b666e63dd1ae0d842f0480b5ab942dc16e8b9`.
The exact complete local Git tree and commit were verified before archiving. This baseline was archived from that commit into `validation/baseline` before product changes.

## Executed checks

| Check | Actual result | Limits |
|---|---|---|
| Exact locked package acquisition | `npm ci --omit=optional --ignore-scripts --no-audit --no-fund` passed, 18 packages installed | Used reviewed escalation, preserving inherited proxy. No lifecycle scripts or optional native packages. |
| Existing dependency rights gate | Passed: 18 installed packages, zero errors | Two optional packages explicitly uninspected; not a distribution or legal clearance. |
| Existing frontend client suite | **24 passed, 0 failed** | Covers client contracts, grants, transient state, scope changes and races. No clinical validation. |
| Existing TypeScript/Vite build | Passed | Vite 7.3.7; exact React/react-dom 19.3.1. |
| Existing actual browser journey | **Passed** against real FastAPI and disposable PostgreSQL 16 | Existing CDP/Chromium harness, no mock patient HTTP or mock database. |
| Supplemental screenshot observation | Passed on a second empty disposable PostgreSQL database | Same unchanged browser journey; separate observer captures additional source states. No production code changes. |
| Responsive width assertion | Passed at 390px | This assertion and screenshots do not establish WCAG compliance or comprehensive device coverage. |

Build output: CSS 6.11 kB / 2.00 kB gzip; JS 248.39 kB / 76.77 kB gzip; index 0.42 kB / 0.30 kB gzip. These are build payload sizes, not measured user latency or Core Web Vitals.

Executed browser sequence: API readiness → connect independent synthetic credential → create fictional identity → retry same idempotency key → deny read before grant → operator adds separate read grant → read canonical identity → import independent fictional source through existing API → inspect case and source metadata → render literal HTML-like text without execution → amend report and retain both versions → revoke source read and clear displayed sources → withdraw patient grant → expire credential → deny cross-organization read → verify reload clears state. The test also checks main/navigation accessibility landmarks and mobile page width. Logs are `baseline-browser.txt` and `baseline-capture.txt` beside this report. Screenshots are in `../screenshots/before/`.

## Accepted screenshots and findings

All images below were opened and inspected after capture. They show the actual built React UI against the existing API. The source statements and identities are independently fictional records produced by the pre-existing test.

| Step | Screenshot | Health and observations |
|---|---|---|
| 1. Entry and session connection | `01-entry-desktop.png` | Explicit environment boundary, labelled credential and patient fields, create disclosure. Three unconnected destinations occupy primary navigation beside the two implemented screens. |
| 2. Authorized identity open | `02-patient-open-desktop.png` | Registry metadata is visible and source read is not implied. Selected identity sits below repeated setup panels. Long opaque ID wraps mid-identifier, making it hard to scan. No actual metadata overlap was measured. |
| 3. Records loaded | `03-records-desktop.png` | Patient ID and case appear, current source state visible. Repeated technical caveats, load controls, case metadata and source metadata are stacked; the first source begins near the bottom of a 1100px viewport. |
| 4. Amendment returned | `04-amendment-desktop.png` | Prior version visibly becomes superseded. Current versus historical meaning is retained. The top viewport remains dominated by introductory content. |
| 5. Source history and statement | `05-source-history-desktop.png` | Original versions/hashes, supersession link, exact statement, source line and unreviewed status are preserved. Patient identity is absent from the visible viewport while reading source history. Hash metadata is expanded ahead of the quoted source statement. |
| 6. Mobile Records | `06-records-mobile.png` | Reflow has no horizontal page overflow in the existing test. At 390×844, navigation, headline and caveat consume most of the first screen; selected patient and actual records are below the fold. |
| 7. Overview mobile | `h1-mobile.png` | Labels and layout remain readable; initial screen likewise prioritizes introductory material over selected patient context. |

These are heuristic observations of a synthetic engineering workflow, not findings from patient or clinician participant research. No screen reader session, contrast audit, zoom audit, complete keyboard audit or broad browser matrix was performed here. No clinical safety or HIPAA conclusion follows from these checks.

## Runtime and reproduction qualifications

Used Node 24.22.1, the exact frontend lock, Python 3.12 and PostgreSQL 16.15. The 24 installed Python dependency versions match `apps/api/requirements.lock`; see `baseline-python-versions.json`. Version matching is not a replacement for wheel-hash or supplier-notice verification.

The browser journey used only a newly initialized loopback PostgreSQL instance and independently fictional test records. Ports 8000 and 4173 were checked before starting the test API and preview; existing services were left untouched. Each run used a fresh empty disposable database because the test has fixed case identifiers. No credentials were retained in these artifacts.

The test used the available Chromium executable with a new temporary profile. The local process used `--no-sandbox` because the executor ran as root; no product or deployment setting was changed. Local sockets required reviewed execution permission. Network package acquisition preserved the inherited proxy, used the exact lock, and disabled lifecycle scripts and optional native binaries.

Reproduction template, from a checkout of the historical baseline after completing the setup in `apps/api/README.md` and `apps/web/README.md`:

```sh
# OI_API_DATABASE_URL must name a fresh disposable oi_api_test database.
# python must select the environment with the locked backend dependencies.
PYTHONPATH=apps/api/src:src \
OI_API_ENVIRONMENT=synthetic \
OI_WEB_ARTIFACT_DIR=validation/before \
python apps/web/tools/browser_journey.py
```

The original exact local command used port 55439, the test role `oi_api`, and the fresh database `oi_api_test_ux_baseline`; no external account or patient credential was involved. This template omits machine-specific runtime and browser paths. The local raw audit remains archived separately; this durable copy normalizes paths without changing results or source attribution.

## Independent hosted evidence

The GitHub connector also reports exact-head workflow [41556723951](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41556723951) completed successfully for `d8de9aaca352cc58b64e9e32440f4ea248b02cb8`, with artifact `13194188735`. This confirms the reported workflow result; local screenshot findings above use screenshots captured in this audit run, not the hosted artifact. The artifact contents were not inspected and are not the basis of the local test claims.
