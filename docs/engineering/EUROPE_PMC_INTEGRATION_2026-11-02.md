# Europe PMC discovery — integration and verification

## Contribution and preserved baseline

This increment adds public title-topic bibliographic discovery to the existing Open Intelligence bibliography panel, API and CLI. It advances OI-004's source-rights boundary and OI-008's explicit distinction between publication discovery and appraised evidence. It adds no package dependency, patient/source ledger, persistent citation import, case attachment or model call. The [adapter contract](../EUROPE_PMC_METADATA_BOUNDARY.md) describes the implemented behavior and source-rights evidence.

The publication candidate is based on the existing [safety reconciliation #137](https://github.com/OpenxIntelligence/open-intelligence/pull/137), exact authored commit `533afd3ca6dd0c011e2e47397d3d5cae04e62512`, tree `b7189613d1b9e9eca39a4501d9f9d3d7e3824cce`. Its main ancestor is `24519839aa8ac1ea3aff88a956349ba72798a72a`. All 21 files changed by #137 are preserved byte-for-byte; this feature does not replace its retirement policy, offline workflows, guard or scientific fixtures.

An earlier local retirement patch was superseded by #137 during the fresh repository check. In particular, #137 also retires cached case-specific single-cell analysis. That narrower local patch is not part of this publication. Historical artifact/cache disposition remains under [issue #122](https://github.com/OpenxIntelligence/open-intelligence/issues/122). No existing branch was rewritten or merged.

The broader selected engineering target is React/TypeScript/Vite with Python/FastAPI and PostgreSQL, as recorded in the inherited H1 decision. This implementation extends the current Python/SQLite/browser-JavaScript prototype. It does not perform that migration, approve exact future dependencies or introduce Next.js.

## Implemented behavior

The new panel accepts a literal public title phrase, an optional paired publication-date range and a result limit of 1–25. Live access is disabled by default and is independent of Crossref access. Operators enable it with `--enable-europe-pmc-live`; the offline example works without that flag.

The adapter uses one fixed HTTPS endpoint, one result page, an eight-second network-operation timeout, a 256 KiB response limit and a process-local concurrency/rate limit. Redirects and retries are disabled. Strict projection retains bibliographic identifiers, title, authors, journal and provider dates while dropping abstracts, book summaries, full text, arbitrary URLs and unknown fields. Returned results carry source identity, retrieval time, a query fingerprint and selected-metadata hashes. They remain transient, unappraised and rights-unassessed.

No patient/case context is automatically added. Syntax validation is not PHI detection; a live operator must supply public research topics. Offline examples are independently authored fictional citations without real publication identifiers or links. Metadata discovery does not confer article-content rights, establish patient applicability or create an evidence assessment.

Review identified an inherited malformed-client-JSON failure: a very large integer closed the HTTP connection. The shared decoder now maps JSON `ValueError` and `RecursionError` into the existing 422 invalid-input response. An actual local HTTP regression reproduces the former failure and verifies the corrected response without provider access.

## Pre-publication local verification

All 148 materialized baseline files were checked against #137's Git blob identities before the feature was overlaid. The [machine-readable receipt](EUROPE_PMC_VERIFICATION_2026-11-02.json) hashes 128 non-documentation source/fixture/workflow files before and after the final verification run. Those bytes did not change during verification. The local inspection commit is not the remote commit; the receipt records both separately.

| Check | Executed result |
|---|---|
| Application unit, HTTP and UI-function suite | 268 passed; zero skips |
| Europe PMC focused tests | 23 passed, included in the 268 |
| Research suite | 204 passed; zero skips |
| Retained single-cell/HDF5 tests | 25 passed, included in the 204 |
| CI data-boundary guard | Passed |
| JavaScript syntax | `web/app.js` and `web/mission.js` passed |
| Workflow YAML | All seven files parsed and contained jobs |
| Chromium journey Python syntax | Passed |
| Live provider contract | One public-topic request succeeded through the actual adapter; one projected citation returned |

The temporary scientific test environment used NumPy 2.3.5, h5py 3.15.1 and HDF5 1.14.6, matching the inherited pinned test dependencies. Product dependencies were not changed. Commands:

```bash
PYTHONPATH=/tmp/oi-hdf5-qa:src python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=/tmp/oi-hdf5-qa:src python -m unittest discover -s tools/research -p 'test_*.py' -v
python tools/audit_ci_data_boundaries.py
node --check web/app.js
node --check web/mission.js
python -m py_compile tests/browser_journey.py
git diff --check
```

The bounded live check ran on 2 November 2026 at 21:15:30 UTC with the public topic `melanoma` and `page_size=1`. It sent no patient context and did not fetch article text or invoke a model. The receipt retains result counts and hashes only. One successful request does not establish complete provider-schema compatibility, future availability, clinical usefulness or commercial/AI rights.

## Browser and hosted verification

The existing Chromium journey now exercises the actual offline publication panel: two fictional citations, absent publication links, disabled programmatic live submission, literal hostile text, no external browser fetch and 390-pixel overflow. This local environment could not install Chromium because the official download returned an unavailable-site HTML response. Consequently the scenario was not executed locally; the Node DOM harness is separate evidence.

The main-targeted draft PR is the hosted integration gate. Its description records the authored head, GitHub's actual checked-out merge revision, workflow results and browser outcome after execution. Prior #137 workflow success is baseline evidence, not proof of this new composition. Do not infer hosted success from this pre-publication local receipt.

## Remaining product integration

The current clinical, Composer, evidence-rights and knowledge work remains owned by its existing integration PRs. In particular, #140/#141 share the server and UI surfaces changed here; compose their changes deliberately rather than replacing those files. The new search results do not yet become case evidence. A future import must use the existing rights, source-version, applicability and human-review contracts.

The patient-to-investigation acceptance journey, production identity/consent, target-stack migration, clinical evaluation and deployment remain separate work. Synthetic software checks and bibliographic access do not complete those requirements.
