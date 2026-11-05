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

## Acceptance matrix

| Gate | Required evidence | Current state at document creation |
|---|---|---|
| Strict identity and compatibility | 25 methods and 13 frozen payloads | Passed locally |
| Migration graph | One head 0021, both published 0019 parents unchanged | Candidate verification required |
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
to `0021_lab_citation_freshness`; do not auto-upgrade a populated clinical service.
Use the committed `.github/workflows/h1-api.yml` and `h1-web.yml` for pinned
PostgreSQL and actual Chromium acceptance. Never skip an existing recovery stage,
weaken authorization or infer combined success from successful donor runs.

Hold acceptance on unexplained failures/skips, missing source/migration ancestry,
changed preserved payload hashes, broken original recovery, stale write acceptance,
revoked-data disclosure or any failed exact-head gate. A failed gate requires a
reproducing regression and bounded repair before expanding the clinical domain.

Production readiness additionally requires independently accepted identity,
consent, operational controls, rights and clinical intended-use evaluation.
