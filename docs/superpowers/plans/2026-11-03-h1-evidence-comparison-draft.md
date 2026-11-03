# H1 evidence comparison draft implementation plan

> **For agentic workers:** use superpowers:executing-plans task by task, with regression-first verification.

**Goal:** Preserve unfinished comparisons without retargeting or stale disclosure.
**Architecture:** One transient draft in the existing evidence session; UI edits and submits through that owner. No persistent browser or server state.
**Tech Stack:** Existing TypeScript/React/Vite and Node test runner.
**Spec:** docs/superpowers/specs/2026-11-03-h1-evidence-comparison-draft.md

## Global constraints
Only independently authored fictional inputs. Preserve source, question, evidence, report, rights and retry owners. No dependency, migration, endpoint, authorization or workflow change.

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
- [x] Produce portable Git patch, modified files, verification summary and execution ledger. Do not claim GitHub publication or hosted verification.

## Verification outcome and open gates
Local client suite: 236 passed (206 inherited plus 30 new), with TypeScript 5.8.3 and Node 22.16.0. Evidence/HTTP/content-rights/data-boundary Python subset: 25 passed. TSX syntax transpilation, browser-test Python compilation, the known-entrypoint policy scan and whitespace checks passed.

The editor and extended actual-server browser acceptance are implemented, but the updated browser journey was not executed. `npm run build` could not typecheck/build the React application because the locked React/runtime/type dependencies were not installed and registry resolution was unavailable. The installed TypeScript 5.8.3 differs from locked 5.9.3. The full reference Python invocation timed out at an existing evaluation-preflight test without a suite summary. No full-reference, real PostgreSQL, production-build, browser, hosted-CI or independent-review success is claimed.

- [ ] Run the unchanged locked dependency/notice installation and TypeScript 5.9.3/Vite build.
- [ ] Run the modified real React/FastAPI/PostgreSQL browser journey and full inherited gates on the same candidate.
- [ ] Obtain independent source-owner review and publish an appropriately based draft PR; do not merge/deploy automatically.

Self-review correction: current evidence remains selectable for separately authorized withdrawal when the original question is historical or quotation content is withheld. Two regression cases first failed before extracting the explicit selection-mode projection. This does not grant authority or enable a stale comparison.
