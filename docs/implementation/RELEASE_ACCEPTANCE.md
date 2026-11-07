# Release acceptance

For the saved episode-origin comparison continuation, qualification must show both
original keys returned after amendment, version-chain and cross-document refusal,
changed/untyped/unassigned/missing findings, and unchanged draft/reassessment state.
The real Chromium journey must reopen the exact third-version original after one
primary changes and the second key disappears. Existing source-original revocation,
concurrent creation, populated migration and restore gates remain mandatory. The
draft PR records the exact head and successful runs; local counts alone are not
PostgreSQL or browser acceptance.

This register applies to one candidate revision, use and deployment profile at a time. A draft pull request is inspectable source. Passing software checks authorizes no clinical use. Keep the commit, tree, dependency artifacts, check results, reviewer, decision date, use scope and open exceptions with every release record.

| Gate | Evidence required | Owner and decision |
|---|---|---|
| Synthetic engineering | Exact commit; clean migration and populated upgrade paths; no skipped required PostgreSQL cases; compiled UI plus real browser journey; all restore/revocation checks; no weakening of access, receipts or currentness; actual installed package gates. | Engineering reviewer inspects the exact workflow results. See [implementation status](IMPLEMENTATION_STATUS.md) for this candidate. Merge requires project authorization. |
| Dependency and distribution | Wheel and npm checks, container layers and build digests, transitive licenses/notices, vulnerability triage, source/weight/asset/content separation, chosen distribution terms and intended jurisdiction. | Rights and security reviewers approve the specific artifact and use. Local synthetic approval is narrower. |
| Operational staging | Issuer/tenant isolation, secrets and key handling, deny-default egress, instrumented availability, measured resource/load limits, crash/retry/restore and incident exercises with responsible operators. | Operations and security sign a named environment. Production setup is open. |
| Real patient data | Intended use, agreements, identity proofing, institutional scope, purpose/consent/delegation, revocation, access history, retention/deletion, approved jurisdictions and emergency procedures. | Data governance and accountable clinical organization explicitly accept the proposed use. Synthetic-only policy applies until then. |
| Clinical decision support | Independent adjudication under a frozen protocol; critical error counts by type, citation support, abstention, bias/representativeness, human override/review and change control. | Named clinical reviewers and authorized release decision. Engineering, a model score or a completed job cannot sign the clinical result. |
| Scientific results and discovery | Versioned input/reference/parameter/tool/container hashes, QC and negative controls; permitted dataset and model use; independently reproducible outcome or predefined tolerances. | Scientific reviewer identifies a research result and its limits. Promotion to clinical knowledge or treatment is a separate decision. |

Withhold release when a required suite skips its necessary backend, a result belongs to a different commit, a backup lacks original bytes or restores an expired grant, a run omits an expected source, or rights are unknown. Record the specific failing check and how to reproduce it. Remediation starts a new candidate evaluation. Separate approval is required for production deployment, real clinical use, external data sharing and irreversible operations.

For this synthetic build, retain the source commit, package locks, API BOM, web BOM and web notice inventory together. The combined verifier must reject a wrong archive digest, alias substitution, repeated or missing location, or inclusion of an omitted optional package. The hosted database image configuration must match the selected platform in the image register. A package or image identity alone leaves layer contents, vulnerability triage and distribution approval open.

## Clinical base acceptance record for #542

The following record belongs to the pinned clinical base. Its named revisions, gates and donor observations are retained for traceability. The current platform increment and its own acceptance are described above.

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

The first repaired head `6c98111460df07412766624407199f3abcb6b24a` passed all
six joined-core and five populated-parent checks, the full web/browser/demo gate,
676 client tests and 13 rights tests. Its complete API run executed 833 tests,
then failed with 29 setup/teardown errors because two old RESTRICT fixture
cleanups did not explicitly remove `require_lab_citation_current_sources()`.
No assertion failures or skips were reported. The fixture repair adds only that
declared function to both disposable cleanup lists; no CASCADE or production
guard change. Those affected migration suites now run in the early CI gate too.
Full acceptance, including all recovery stages, must rerun on the repaired head.

During the fixture-repaired run, main advanced to
`aad241e5cce9a1bcff3e431d63cecd16e948d731` (#538). Default-checkout workflows
therefore tested merge `f8740eb19380dcd229e0841c3a5d86edcbaea7b3`, tree
`eb91701414790a9b06e3079fdb377ca1dd0c0226`, which is different from proposed
head `7e8a37de` / tree `2540dac8`. Their 919 reference tests must not be
attributed to that proposed head. The latest candidate now merges the complete
accepted main explicitly and must rerun all exact-head acceptance gates. The
merge adds no new dependency and retains #538's reference checks and limitations.

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
