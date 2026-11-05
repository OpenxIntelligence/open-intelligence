# Release acceptance

Date: 2026-11-05. Scope: independently fictional H1 engineering consolidation.
No clinical validation, real-patient qualification, merge or deployment is implied.

## Source identity

Accepted-main input: `f188aecc70f3415741dac0e7dd5bf3f2d9fd02a9`.
The candidate preserves full #540 head
`299cfb54df8259c6d72ddd88f3e0c08ca3dda3f4` and #539 head
`917cc14bdc0f298bc33d06b09125cd4658205eec` as ancestors. It therefore retains
#536's laboratory/agent provenance and #537's EHR/laboratory migration join.
Final commit/tree and hosted receipts belong in the draft PR; a document cannot
contain its own commit hash. Recheck current main and all input branches before
any human-authorized merge.

Current draft: [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542).
Its test-first head `80660730df2b8a819aa37215e39bc7f9af55c0f7` has tree
`857a28f8fedc49dfeaa9cc2a262dc117db761461`, exactly matching the local source.
[Hosted red run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42096046609)
ran six real PostgreSQL joined-core tests: five passed and the new reviewed-document
regression failed with the expected HTTP 503 instead of 201. Additive 0022 now
aligns only the guard's source set with the existing canonical snapshot; its
downgrade restores the original 0021 function, without dropping its trigger.
Final repaired-head acceptance is required; the red run is not acceptance.

## Test-first integration evidence

The four existing #539 fixture/test files were added to #540 before integration.
Command (Python 3.12.14; installed exact API package tooling):

```sh
PYTHONPATH=apps/api/src:src:apps/api/tests python -m unittest test_question_anchors test_question_anchor_integration
```

Before owner integration: 25 methods ran, 38 assertion/subtest failures, no
reported test errors. This reproduced missing shared identity validation and
acceptance of coerced stored source identity. After merging #539's complete
history, all 25 methods pass. All 13 frozen legacy payload/fingerprint outputs
remain equal. This is pure projection/contract evidence, not database authority.

Two further mixed-anchor subtests first failed because the legacy/text-preflight
adapters accepted the laboratory owner's `observation_reference` alias. The
explicit mixed-field guard now rejects it; all 25 methods remain green and the
13 legacy compatibility fixtures remain unchanged.

## Baseline limitations

On the inspected main, full local API discovery executes 785 test methods with
477 PostgreSQL-dependent skips and 75 errors. The 75 recorded errors are
`PermissionError` from prohibited AF_UNIX socket creation. This is an incomplete
local run; it is not represented as a green API suite. PostgreSQL, Docker and a
Chromium executable are unavailable in this local execution environment. The
existing hosted CI provides these gates without changing dependencies or tests.

Local dependencies are reused from installed tooling with the identical web
package-lock (`b8a6bbf0…8c3b`), without a new dependency selection. See final PR
for completed candidate command results and exact lock hash.

Completed local candidate checks before the 0022 repair: 853 reference tests,
676 client tests, 13 rights tests, TypeScript/Vite build and synthetic data guard
passed. One initial client invocation hung and was interrupted; a complete
bounded run of all 676 tests passed with no timeout, cancellation or skip.
Candidate full API discovery: 832 methods, 75 AF_UNIX permission errors, 493
PostgreSQL skips. Neither incomplete API run counts as a pass. The added PG
regression makes subsequent discovery one method larger.

## Acceptance matrix

| Gate | Required evidence | Current state at document creation |
|---|---|---|
| Strict identity and compatibility | 25 methods and 13 frozen payloads | Passed locally |
| Migration graph | One head 0022, 0022→0021→0020→both published 0019 parents unchanged | Graph passed locally; populated hosted verification required |
| API/domain/authorization | Full pinned API suite, zero unexplained skips | Hosted exact-head run required |
| Populated upgrades | EHR-only, lab-only, both heads; original retries and independent revoked grants | Existing tests retained; hosted run required |
| Citation DB freshness | Independent source import; repeatable-read refusal; rollback and historical retry | Existing #540 regression retained; hosted run required |
| Reference regression | Complete original tests with exact failure disclosure | Candidate local/hosted results required |
| React/client/build/rights | Existing full tests, typecheck/Vite and installed notice inspection | Candidate run required |
| Browser | Original text/PDF, laboratory, images, questions/reports/tasks, amendment and authority loss | Exact-head hosted run required |
| Restart/restore | Seven existing full PostgreSQL restart/backup/restore stages with original rows/bytes and revoked access | Exact-head hosted run required |
| Independent engineering review | Source/migration/replay/authorization review | Required before acceptance |
| Clinical evaluation | Independently adjudicated intended-use corpus and protocol | Not performed |

## Reproduction and stop conditions

Use `docs/H1_DEMO.md` for the persistent synthetic application. Explicitly migrate
to `0022_lab_citation_source_scope`; do not auto-upgrade a populated clinical service.
Use the committed `.github/workflows/h1-api.yml` and `h1-web.yml` for pinned
PostgreSQL and actual Chromium acceptance. Never skip an existing recovery stage,
weaken authorization or infer combined success from successful donor runs.

Hold acceptance on unexplained failures/skips, missing source/migration ancestry,
changed preserved payload hashes, broken original recovery, stale write acceptance,
revoked-data disclosure or any failed exact-head gate. A failed gate requires a
reproducing regression and bounded repair before expanding the clinical domain.

Production readiness additionally requires independently accepted identity,
consent, operational controls, rights and clinical intended-use evaluation.

## Lab and imaging extension: evidence to record separately

The parent for this extension is #542's `6c98111460df07412766624407199f3abcb6b24a`, with readiness at `0022_lab_citation_source_scope`. The preceding #540 source `299cfb54` passed the [web job](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42093139717); its [API job](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42093139840/job/127476452372) ran 807 tests with 29 errors caused by the shared migration fixture leaving the new `investigation.require_lab_citation_current_sources()` function behind. Recovery did not run in that job. #540 later added scoped cleanup at `0a210cbc`. These donor receipts do not describe the current source. The six-method [test-first #542 run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42096046609) reproduced a different business-rule defect; keep both regressions distinct.

| Acceptance handoff | Required evidence for the actual extension revision |
|---|---|
| Engineering / laboratory | Inspect a multi-result fictional report with a missing value, negative result and zero. Verify exact source-reported values/units, independent observation identity, source version and permission; keep a withheld/unsupported case visible as such. Test duplicate/missing/malformed identity without silently replacing the report. |
| Engineering / imaging | Exercise only supported image metadata/links using current patient, case, source version and fresh independent grants. Test revoked/changed scope, empty/missing fields, a changed image selection and stale/out-of-order UI responses. Preserve exact original custody; no diagnosis or diagnostic-grade viewer claim. |
| Source reproducibility | Record tested source SHA and tree, exact parent/owner histories, lockfile digests, environment/tool versions, check run IDs, pass/fail/skip counts, screenshot/probe retention and residual issues. Match any merge-ref run to its tested tree. A docs-only change is not evidence of a runtime behavior. |
| Operations and independent review | Require complete API/database/migration/recovery and browser gates on the candidate, not just successful build/client results. Identify who reviewed wrong-scope, stale response, anchor integrity, retries and migration recovery; record outstanding findings and retest disposition. |
| Distribution, production and clinical use | Separate decisions by responsible rights, operations, privacy/security and clinical authorities; record approved scope, reviewer, date, result, open risks and expiry. All remain on hold absent independent evidence. Research code licenses, green CI and a fictional run cannot approve these decisions. |

Use the [test protocol](TESTING_AND_EVALUATION.md), [operating procedures](DEPLOYMENT_AND_OPERATIONS.md), [security control owners](SECURITY_AND_GOVERNANCE.md) and [AI evaluation plan](AI_EVALUATION_PLAN.md) when preparing that record. No new deployment, provider call, clinical evaluation or tool adoption is implied by this extension.

## Verification of draft #546

The earlier manual upgrade instruction for the parent applies to #542. This branch requires `0023_dicom_mr_custody`, directly after `0022_lab_citation_source_scope`. The migration constrains SOP class and modality together. An existing MR original prevents downgrade. The PostgreSQL tests exercise preservation of populated CT history, refusal of a mismatched direct database insert and preservation of MR history on a refused downgrade.

The initial diagnostic UI commit [84656be6](https://github.com/OpenxIntelligence/open-intelligence/commit/84656be68972d99a28fb0f833278ba7be9f185e1) passed its [web workflow](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42097733451). It predates MR and the service-section expansion. The parent [#542 API job](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42096660696) failed in test fixture cleanup after passing its early joined-core check. This branch brings forward the two precisely named fixture drops from [#540's repair](https://github.com/OpenxIntelligence/open-intelligence/commit/0a210cbc05db8f0b146c04863b954c5b72d83eac). Application migrations are cumulative. No test was disabled.

The locally executed Python reference suite passed 853 tests. The first local API run on the initial diagnostic code ran 838 tests with 75 AF_UNIX permission errors and 496 skips in this host. Local results do not establish the PostgreSQL/Compose gates. A client concurrency regression also exposed a fixed 10 ms sleep in the inherited test; the fixture now waits for the actual transport call before it tests the pending-state behavior.

For current combined results, use the commit-specific web and API workflow links in [the draft pull request](https://github.com/OpenxIntelligence/open-intelligence/pull/546). The API job runs the real migration and rollback tests plus all seven recovery exercises; the web job runs the actual laboratory and original-image journeys. A source change requires a fresh run. Human release review follows engineering verification.
