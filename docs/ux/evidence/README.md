# H1 frontend verification evidence

Date: 2 November 2026 (America/New_York).

This directory is the durable repository location for the bounded frontend redesign evidence. The main report distinguishes baseline, initial implementation and final verification. Do not infer a final pass from an initial log or from the presence of a screenshot.

## Available result summary

- [Retained-reference regression summary](reference-suite-summary.md): 245 tests actually passed; captured log fingerprint recorded.
- [Contrast measurements](contrast-measurements.md) and [machine-readable pairs](contrast-measurements.json): 25 normal-text and 9 enabled-control/focus/outer-state pairs; final stylesheet SHA-256 `2f50b7c13589525ec261875a3b35a4b0c8b1c0fe797f202b19d1fe5b501b9d86`.
- [Boundary comparison](boundary-report.json): protected files compared with explicit parent `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`.
- [Final browser result](browser-final.txt): the actual Chromium/FastAPI/PostgreSQL journey passed, including two-case isolation, long-record reflow, expired access with visible data, keyboard recovery and 320/390/768/1440px checks; zero uncaught JavaScript or console.error events.

## Evidence inventory

Historical baseline checks remain attributed to `d8de9aaca352cc58b64e9e32440f4ea248b02cb8`. The reconciled parent is `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`; its sole inherited change removes an unused duplicate parser. Final product/test code is preserved in local checkpoint `0b741bf8ef7987ab4396474e3fbf0fa4b0f7e053`. Publication may use a different commit for documentation-only changes; the boundary report records exact source/test hashes.

| Filename | Content | Status |
|---|---|---|
| `baseline-audit.md` | Exact #200 baseline, executed checks and screenshot observations | Saved; historical baseline |
| `reference-suite.txt` | Captured 245-test retained-reference log | Saved; executed result |
| `contrast-measurements.md` / `.json` | Actual stylesheet color samples and limitations | Saved; final CSS samples |
| `client-final.txt` | Final client-suite command/result | Passed: 24 tests |
| `build-final.txt` | Final TypeScript/Vite result and payload sizes | Passed: TypeScript and Vite |
| `rights-final.txt` | Existing unchanged dependency-rights gate | Passed: 18 installed, 2 optional uninspected |
| `browser-final.txt` | Actual Chromium/FastAPI/PostgreSQL final journey | Passed: final actual API journey |
| `upstream-reconciliation.md` | Exact one-commit parent drift and inherited unused-parser deletion | Saved; original drift analysis |
| `review-red-browser.txt` | Meaningful pre-fix browser assertion for both presentation defects | Saved; executed result |
| `boundary-report.json` | Comparison of restricted files with selected base | Passed at recorded file-hash snapshot |
| `review.md` | Independent findings, fixes and final check references | Maintained by implementation owner |

Use only independently fictional engineering records. Preserve failures and qualifications. No log or screenshot establishes real-patient authorization, clinical validation or full accessibility conformance.

## Failure evidence and baseline provenance

- `baseline-red-browser.txt` establishes that the first new UX regression failed against unchanged production because the selected-patient header was absent.
- `review-red-browser.txt` preserves both reproduced review findings: filter-clear focus loss and misleading Overview status while source records remained loaded.
- `long-source-red-browser.txt` preserves the reproduced 320px reflow failure for the long case label; the final browser result follows the scoped CSS fix.
- `baseline-browser.txt` and `baseline-capture.txt` contain the original passing real API journeys.
- `baseline-python-versions.json` records that all 24 installed backend dependency versions matched the lock; version matching does not replace wheel-hash or notice checks.
- Inspected images and SHA-256/dimension manifests are indexed in [screenshots](../screenshots/README.md).

## Execution qualifications

Used Node 24.22.1, Python 3.12, PostgreSQL 16.15, exact locked frontend packages and Chromium with a fresh temporary profile. The test database and credentials were independently fictional fixtures. A new disposable loopback database was used for each run. The local Chromium process used `--no-sandbox` because the executor ran as root; no product setting changed. Local socket access and exact-lock installation used reviewed execution permission while preserving the inherited proxy.

Command families actually executed: `npm run rights`, `npm test`, `npm run build`, `PYTHONPATH=src python -m unittest discover -s tests -q`, and `PYTHONPATH=apps/api/src:src OI_API_ENVIRONMENT=synthetic python apps/web/tools/browser_journey.py` with an explicit fresh `OI_API_DATABASE_URL` and screenshot output directory. Here `python` selects the isolated environment with the locked backend dependencies. The project READMEs own setup details.

Failure logs normalize only machine-specific checkout prefixes to repository-relative paths. Results, assertion messages and screenshot pixels are preserved. No access-file contents, bearer tokens, database passwords or external account credentials are included. Narrow secret-pattern scanning and manual screenshot review are evidence hygiene, not general secret-scanner certification.

Further documentation-only artifacts may follow this inventory. Any product/test change requires refreshing `boundary-report.json`. The final run is software engineering evidence, not real-patient authorization, clinical validation, full accessibility conformance or deployment approval.
