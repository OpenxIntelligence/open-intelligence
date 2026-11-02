# Source-quoted review parent freshness integration

> Execute inline with superpowers:executing-plans; no separate agent review is claimed.

**Goal:** Carry the existing #132 final-read repair into its downstream #143 source-quoted review handoff and prove the combined behavior.
**Architecture:** Preserve every domain owner and the existing read-only EvidenceReviewPacket. Reuse the exact three upstream files from commit 864e1f703c6ada019ddd23dd15e4fb2933515285; add only downstream tests and integration evidence. Do not merge either PR into main.
**Tech stack:** Existing Python standard library, SQLite and GitHub verification workflows; no new runtime dependency.
**Spec:** docs/engineering/SOURCE_QUOTED_EVIDENCE_REVIEW_INTEGRATION.md; OI-008/009/013/018; parent PR #132 and child #143.

## Boundaries and source evidence

- Open Intelligence is the current project. This is a complementary integration, not a new architecture, source ledger or consent system.
- Original fictional records, evidence and actor callbacks only. No PHI, public patient records, model call, external data retrieval, clinical conclusion, signature or license clearance.
- Baseline child 83a52eee04136bdc8a0a973e760593079768a3d9, exact source tree 24d79cbac5eafe4d212a6f353985c8bda27d46fd recovered from CI artifact #13177285715. Archive SHA-256 f2bb5dbeb74b756b28d396870d3029bbfc7ac4bc6ef29fcee4f7538224739afc verified; local git write-tree matches.
- Corrected parent source from artifact #13177755687, SHA-256 9988ec84041092a6b68df2234daf71e5a0bf375a4e5c8946573bdbcbcfe57fc9 verified. Parent #132 remains owner of the repair.

## Execution ledger

- [x] Read current PRs, root instructions, requirements, implementation and source/test ownership; create isolated local worktree from exact baseline archive.
- [x] Execute baseline quote-review suite: 16 executions passed, including imported upstream test cases.
- [x] Add seven downstream tests at the fourth/final provider call in EvidenceReviewPacket.preview. Observe four actual behavioral failures with three preservation controls passing on the old inherited parent.
- [x] Reuse the corrected parent files byte-for-byte. Do not reimplement the repair or change the quote-review production module.
- [x] Verify seven downstream tests and seven inherited parent regressions locally; both pass. Compile and JS syntax pass. A bounded local full-suite attempt reached the execution limit; it is not reported as a passing full run. Exact-head hosted full Python/HTTP verification remains required.
- [ ] Preserve exact source and hashes; publish only to existing draft branch with expected-head protection. Inspect exact-head hosted suites/browser results before asserting success.
- [ ] Update existing Notion/Google engineering records and PR review evidence; no release approval or automatic merge.

## Review focus

Report amendment or new report during the final provider read must not yield a stale quote-review packet. QC and note changes require full clinical projection checks, not only report hashes. Existing binding revocation must still deny. Unrelated-case changes must not leak or block this case. Stable outputs must retain exact quotations, original anchors and pending status without database writes or execution authority. Fresh explicit retry after an amendment may return the new context; it is not automatic clinical reassessment.

## Limits

This reproduces and corrects a deterministic callback boundary, not all distributed races. The packet remains a sequential non-atomic preflight, not proof of freshness at later use, clinical entailment, publisher rights, verified clinician identity or consent. Downstream consequential operations require their own current authority/source/rights checks. All tests are authored and executed by the same assistant; independent human code/security/clinical review is still required.
