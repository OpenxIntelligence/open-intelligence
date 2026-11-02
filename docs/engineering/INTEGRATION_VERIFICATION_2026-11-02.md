# Integrated investigation and review — verification receipt

Date: 2 November 2026. Scope: independently authored synthetic software workflow. This is not the complete MVP, clinical validation, production authorization or a deployment receipt.

## Reviewed composition and behavior

The product candidate preserves exact main `24519839aa8ac1ea3aff88a956349ba72798a72a`, reuses the reviewed changes from Composer #68, input-freshness #91 and knowledge-boundary #93, and adds a durable model-investigation-to-review handoff plus public metadata discovery. It is stacked on reconciled safety draft [#123](https://github.com/OpenxIntelligence/open-intelligence/pull/123), head `2d04daba74f89c6e1837b9059f05506a971ca571` (a documentation-only correction above code-verified `d35f54daaa64038dbc76360a93cc90ebd1e3c95c`). Source-owner branches and main are not merged by this work.

An investigation captures its case/question/input fingerprint before execution and rechecks it transactionally on save. Preparing its report validates citations and current dependencies, preserves original model output and model/mode/template provenance, and atomically creates one linked snapshot. Retries return the same snapshot. Generation and preparation leave review pending; only an explicit human demonstration acknowledgment changes question state. Source/evidence changes make the run and report stale while preserving earlier text, source versions and review events. A new run creates a distinct report.

The SQLite change adds nullable captured-context metadata and a one-to-one `investigation_review_drafts` link with provenance. Existing uncaptured runs remain readable and require rerunning before report preparation. This is an additive prototype migration, not a PostgreSQL migration. The ordinary manual-draft contract is retained; the internal generated-report path can preserve more than 50 canonical dependencies and can produce a source-free report only for a genuine abstention. No dependency list is silently truncated.

The new literature route is disabled by default. Explicit operator enablement and fresh public/human-authored attestations are required. The fixed Europe PMC adapter returns one bounded metadata page, rejects redirects, excludes abstracts/full text, preserves unknown integrity and unassessed rights, and never reads or writes patient/case state. It is discovery, not evidence appraisal. Safe HTTP logging avoids request lines, query strings, bodies and provider exception text.

## World Model and completed reassessment extension

The composed candidate also reuses source-owner #147 and #157's read-only World Model projection and inspector, with the missing JavaScript route and draft-vetoed case-switch race corrected. Its real HTTP test covers prepare, review, amendment, reassessment and replacement acknowledgment while source observations remain clinically unreviewed. The Mission projection now treats stale history as active review work only until its own question is addressed with a current reviewed-in-demo replacement. Missing question/review context stays actionable. Old source/report text, reviewer and time remain unchanged; the JSON adds explicit review history rather than stored workflow flags.

The [source-owner integration receipt](WORLD_MODEL_WORKFLOW_INTEGRATION_2026-11-02.md) records failing regressions, independent reviews and isolated checks. The table below is the **actual final combined local execution**, including both patches and the wording corrections. All 20 safety-prerequisite paths remain byte-identical. The new extended Chromium journey must pass at the final published head; its PR body and canonical roadmap hold that exact hosted receipt. Earlier `1bb4ff06` hosted results below are preserved as historical evidence only.

## Executed local gates

| Check | Actual result |
|---|---|
| Full application Python suite | **341 passed**, zero failures/errors/skips; 46.741 seconds |
| Full research suite under pre-discovery network/process denial | **219 passed**, zero failures/errors/skips; all **24 HDF5 tests executed**; zero attempted guarded effects |
| Direct JavaScript test execution | **63 named tests passed**: 7 handoff, 11 literature UI, 16 source-dialog, 15 source-line-diff, 8 text-change, 6 World Model inspector |
| JavaScript syntax | Eleven application/test files passed |
| Workflow/shell syntax | Six workflow YAML files and 31 shell run blocks validated in the final composition |
| Whitespace/conflict check | `git diff --check` passed |
| Source/declaration SBOM | Deterministic regeneration, JSON parsing, 34 input hashes and 94 distinct/resolved references verified; official CycloneDX 1.6 JSON Schema validation passed with zero errors using jsonschema 4.26.0, local schema references and enabled format checks |

The eight CI-boundary tests are included in the 341 application total; do not add them again. The HDF5 dependencies are research-test-only NumPy 2.3.5 and h5py 3.15.1. The application adds no third-party runtime package, model weights or patient dataset. See [SBOM scope and unresolved licenses](../safety-packet/SBOM.md) and [safety reconciliation evidence](DATA_BOUNDARY_RECONCILIATION_VERIFICATION.md).

The safety prerequisite at `d35f54daaa64038dbc76360a93cc90ebd1e3c95c` subsequently passed all six hosted workflows: [research](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41526097873), [RNA](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41526097996), [HDF5](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41526097955), [Crossref](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41526097876), [UI glance](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41526097896), and [ledger/Chromium](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41526097894). Ledger attempt 1 passed 244 Python tests but Chromium did not start before application interaction. Only that failed job was retried at the unchanged head; attempt 2 passed. These results cover the prerequisite, not the new product candidate's own hosted gate.

Commands:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
node --test tests/test_*.js
for test_file in tests/test_*.js; do node "$test_file" || exit; done
for script in web/*.js tests/test_*.js; do node --check "$script" || exit; done
OI_REQUIRE_HDF5=1 python tools/verify_offline_research.py . tools/research 'test_*.py'
python tools/generate_source_sbom.py --as-of 2026-11-02 --check
git diff --check
```

The research command requires the pinned fixture dependencies. Local execution supplied them through an isolated scratch path and used `python -S`; the guard was installed before dependency/repository imports. The SBOM includes the generation-time HEAD, branch, working-tree and runtime observations, so those fields intentionally change when the source checkout or runtime changes. Its production-file hashes identify the captured inputs independently of that pre-build context.

## Independent review and regressions

Review checked atomicity, concurrent retries, rollback, source/evidence staleness, strict case/question identity, immutable history, inert report rendering and metadata transport/rights boundaries. It found and corrected two concrete gaps: source-free/large-dependency report handoff and Unicode/overlong Composer identifiers. Tests first reproduced both failures. The offline knowledge helper is explicitly documented as requiring an unchanged canonical store snapshot; it is not an authorization layer for arbitrary assembled dictionaries.

The boundary review also found fixtures sharing archival case metadata. The safety prerequisite replaces those with newly authored numeric matrices and reserved synthetic origins, retires case-configured inspection, and preserves the newer main acquisition denials. A synthetic label or a passing test alone is not provenance proof.

## Live and browser observations

One live, manually authored generic metadata query succeeded at `2026-11-02T20:27:39Z`: three accepted MED records, API version 6.9, zero exclusions, no patient context and no abstract/full-text retention. The [exact bounded receipt](../research/LITERATURE_LIVE_METADATA_RECEIPT_2026-11-02.json) establishes transport/schema compatibility for that observation only. No live model was called; model workflow tests use explicit replay or mocked transport.

Local browser execution was unavailable: no Chrome/Chromium executable was installed, and a temporary Playwright browser download returned an invalid archive. Published candidate `1bb4ff06a5ab222d3561145e757226f671dbf3ea` subsequently passed [hosted ledger/Chromium 41527551989](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41527551989) and [UI glance 41527551944](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41527551944), both attempt 1. The Composer journey actually executed prepare → explicit review → amendment → stale report → new run/report → preserved historical export. Ledger executed 325 Python and 57 JavaScript tests; UI repeated the 325 Python tests, ran 16 source-dialog tests and passed 13 layout checks. Do not sum the repeated Python suites. GitHub checkout merge `56ba6eacbda02b6b4acfd145fea9d8198e9c7d9a` and the published head have the same tree `a8455b54b589a7733e487661edf2de93be0a32c3`. Nonfatal SQLite ResourceWarnings and Action Node deprecation notices remain visible in the logs. These results qualify that head only, not later changes or clinical use.

## Release and product limits

Current scope is a local synthetic reference workflow. Verified identity, consent/delegation, production access control, ordinary PDF/OCR ingestion, clinical extraction, real clinician authority, licensed full-text/guideline appraisal, target-stack migration, model evaluation, backup/recovery qualification and deployment remain incomplete. Source-version citations do not prove claim support or clinical applicability. Model/template identifiers do not provide immutable provider weight or prompt-template attestations.

Historical artifacts, caches, logs and patient-data retention remain open under issue #122. This receipt does not establish HIPAA/GDPR conformity, medical-device status, legal licensing clearance or approval for real-patient use. Main/fallback and the accepted H1 FastAPI/PostgreSQL 16 and React/Vite/TypeScript direction remain distinct from this unmerged candidate.
