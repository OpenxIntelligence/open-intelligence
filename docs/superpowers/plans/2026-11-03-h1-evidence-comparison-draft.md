# H1 evidence comparison draft implementation plan

> **For agentic workers:** use superpowers:executing-plans task by task, with regression-first verification.

**Goal:** Preserve unfinished comparisons without retargeting or stale disclosure.
**Architecture:** One transient draft in the existing evidence session; UI edits and submits through that owner. No persistent browser or server state.
**Tech Stack:** Existing TypeScript/React/Vite and Node test runner.
**Spec:** docs/superpowers/specs/2026-11-03-h1-evidence-comparison-draft.md

## Global constraints
Only independently authored fictional inputs. Preserve source, question, evidence, report, rights and retry owners. No dependency, migration, endpoint, authorization or workflow change in the product candidate.

## Review focus
Wrong-question reuse; old draft revived after denial; source/rights amendment while reading; pending-write discard; stale responses and component navigation.

### Task 1 — scoped session draft
Files: existing `apps/web/src/authored-evidence-session.ts`, `registry-client.ts`; new `apps/web/tests/authored-evidence-draft.test.mjs`.
- [x] Add behavior tests using original fixture/real RegistrySession; run red.
- [x] Implement draft selection/edit/save/discard and exact binding checks.
- [x] Run `npm test`; preserve all inherited checks.

### Task 2 — original editor integration
Files: existing `apps/web/src/authored-evidence-panel.tsx` and existing browser journey `apps/web/tools/question_evidence_journey.py`.
- [x] Replace only local comparison fields with session-bound draft controls.
- [x] Show resume/discard states without disclosing old content under another question.
- [x] Extend existing real-server browser acceptance for refresh, navigation and confirmed save.
- [x] Attempt full TypeScript/Vite build and relevant suites; record unavailable dependencies honestly.

### Task 3 — verification and delivery
- [x] Review all diffs and exact unchanged source-owner files.
- [x] Re-run full client and available reference tests; record skips and failures.
- [x] Produce portable Git patch, modified files, verification summary and execution ledger. At the initial checkpoint, publication and hosted verification were not available.

## Initial local-only checkpoint — retained failure history
Local client suite: 236 passed (206 inherited plus 30 new), with TypeScript 5.8.3 and Node 22.16.0. Evidence/HTTP/content-rights/data-boundary Python subset: 25 passed. TSX syntax transpilation, browser-test Python compilation, the known-entrypoint policy scan and whitespace checks passed.

At that checkpoint, the editor and extended actual-server browser acceptance were implemented, but the updated browser journey was not executed. `npm run build` could not typecheck/build the React application because the locked React/runtime/type dependencies were not installed and registry resolution was unavailable. The installed TypeScript 5.8.3 differed from locked 5.9.3. The full reference Python invocation timed out at an existing evaluation-preflight test without a suite summary. Those blocked attempts are not successes; the later hosted evidence below supersedes the unverified/publication statements in the initial plan and specification.

Self-review correction: current evidence remains selectable for separately authorized withdrawal when the original question is historical or quotation content is withheld. Two regression cases first failed before extracting the explicit selection-mode projection. This does not grant authority or enable a stale comparison.

## Resumed exact-source verification — 3 November 2026
The preserved patch was reapplied to the verified PR #300 parent `818c67fcb742941fe1588c4ee130ce07e15a814d`. Its exact tree was reconstructed locally and in hosted verification without changing the application implementation. The resumed local client run again passed 236 tests.

**Tested and published runtime:** `f844451994713af2c785cef2f1a445ae0cebbe36`; **tree:** `8d6e35e8dbc1a75d525f72fcec8a1279d96b327d`.

[Hosted verification and create-only publication, run 41667281757](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41667281757) completed successfully. Its read-only verification job executed the unchanged locked dependency installation, supplier-notice gates, all 236 client tests, TypeScript 5.9.3/Vite 7.3.7 production build, 347 real API/PostgreSQL tests (301.902 s, no skips), and 250 reference tests (9.767 s). The actual built React/FastAPI/PostgreSQL browser workflow passed the added unchanged-refresh and navigation/recheck draft assertions, with zero additional POSTs while editing; all inherited evidence/report/source/rights/retry checks and both original reference browser journeys passed. All four original Compose registry/source/review/evidence restart and dump/restore probes passed. The evidence probe establishes complete restored rows and sequence equality, not evidence HTTP against the separately restored database.

Downloaded artifact `13246268937`, 2,801,569 bytes, matched SHA-256 `280c700bca0b771ecc12980d15ccc5c9e2675fe0818356e423f9614b2376edb6`. Commit/tree receipts matched; all 355 archived source files and executable modes matched the local candidate. All 347 unmodified parent files remain unchanged. Evidence/report download receipts and mobile/desktop screenshots were inspected. The mission browser has an empty text log but exited successfully in the fail-fast gate; it is not represented as its own textual PASS receipt. The captured Python 3.12 API/reference logs contain no ResourceWarnings; this does not erase warnings in earlier Python 3.13 runs.

The workflow and encoded transport patch exist only on `work/h1-evidence-draft-verification-20261103`. They are absent from the product candidate and its ancestry. A separate gated write job published only a new branch. Main and the parent branch remain untouched. This documentation follow-up changes only this plan; runtime, tests, dependencies, migrations and product workflows remain identical to the tested tree. The ensuing PR workflow outcome must be recorded separately.

- [x] Run unchanged locked dependency/notice installation and pinned production build.
- [x] Run modified real browser journey, full inherited suites and recovery gates on the same candidate.
- [x] Publish the verified runtime to an isolated review branch.
- [ ] Obtain independent source-owner review. Review here was inline/self-review, not an independent external assessment.

Keep the candidate draft and unmerged. No deployment, real patient data, live model, clinical signoff, production identity/consent or full H1/PDF convergence is established.
