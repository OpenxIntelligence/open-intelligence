# Composer selected-source snapshot binding Implementation Plan

> For agentic workers: execute task-by-task with regression-first verification.

**Goal:** Reject a Composer preflight whose selected finding is not the exact finding in the supplied, decoded patient/case snapshot.

**Architecture:** Extend the existing `decodeComposerPreflight` boundary; retain the source World Model, question, source and authorization owners. Do not create a parallel context store, add dependencies, or change server contracts.

**Tech Stack:** Existing TypeScript and Node test runner.

**Spec:** Living Patient G02/G04/G07/G18, LP11/LP20; existing OI-006/007/009/013; Notion engineering page 40a3866f77ef8197ae65e727c8907eb3. The supplied notes require one patient/date/finding context and preserved source provenance.

## Global Constraints

- Independently fictional inputs only. No dataset or model calls.
- React/Vite/TypeScript H1; no new runtime dependency, migration, permission or state owner.
- Preflight stays source-context-only; no model-execution or clinical authorization.
- Main pinned to f8ff4f4cea8dbfa1ee81cf33308e10af8aff29c4 for this candidate.
- Local retrieval is a hash-verified three-file source subset, not a full clone. Container cannot resolve github.com; full locked-build/browser/API verification must remain separately reported.

## Review Focus

- A mismatched response and requested observation may agree with each other while both disagree with the current snapshot.
- An amended source must not admit the old selected observation even with the new snapshot hash.
- A structurally equal copy must work without relying on JavaScript object identity.
- Missing/unassigned/assigned oncology context and specimen identity must remain distinguishable.
- Existing question, patient/case, fingerprint and clinical-authority checks must not weaken.

## Task 1: Bind selection to the current snapshot at the existing decoder

Files: modify `apps/web/src/composer-preflight-view.ts`; create `apps/web/tests/composer-snapshot-binding.test.mjs`.

- [x] Write tests using the actual `parseSourceWorldModel` and `decodeComposerPreflight`, including mismatched source/line/version/hash/specimen/context and an amendment.
- [x] Compile the retrieved modules and run Node tests on unchanged baseline; observe assertion failures for the new boundary, not import errors.
- [x] Resolve exactly one source/line observation from `world.observations`; compare response to both that canonical finding and requested observation using the existing strict anchor decoder.
- [x] Recompile and run all new tests. Verify the old baseline fails again, then restore and repeat passing tests.
- [x] Attempt the repository test command, report the source-subset/toolchain limits without claiming full-suite acceptance.
- [ ] Publish only a new draft branch/PR from the pinned base. Do not merge. Record actual evidence and remaining checks in the existing Notion engineering page.

## Executed local evidence and limits

- Focused regression set: **35 tests**. Unchanged parent decoder: 14 passed, 21 failed with missing expected contract rejection. Patched decoder: 35 passed, zero failures/skips. Restoring the parent decoder reproduced the same 21 failures; restoring the patch restored all 35 passes.
- Strict compilation of the three actual TypeScript modules passed with Node v22.16.0 and preinstalled TypeScript **5.8.3**. The repository pins **5.9.3**; this is not the locked project build.
- Exact parent blob checks: composer-preflight-view.ts `684281f4e4a546b36bbbb2d2e40d33e59165dfc2`; source-contracts.ts `c0646f51790e96b05d1df556fc594bd6553cede9`; source-world-model.ts `29ff76aa7b8939621c8f7f4289fa0c00f05baaf5`. The latter two are unchanged.
- `npm test` was attempted with exact upstream package.json and tsconfig.client.json in the source subset. It stopped with TS18003 because the full registry-client/second-opinion entrypoints are not present. No existing project test was executed by that attempt. Container DNS prevented a full GitHub clone; connector retrieval provided only the stated files.
- `git diff --check` passes. Self-review covered canonical membership, requested selection, exact clones, two sources at the same line, null specimen, amendment and missing/assigned/unassigned episode context. Independent review remains outstanding.
- This is a decoder-level defense-in-depth repair. Existing session and backend authorization remain separate; no end-to-end disclosure or backend authorization defect was demonstrated. A decoded snapshot is the input contract, not a new authority token.
- Not implemented here: full temporal replay or cutoff selection, laboratory/FHIR selections, specimen graphs, 3D rendering, Copilot execution, datasets or clinical review. No schema, API, permission, dependency or state owner changed.
- Full locked frontend suite, production build, PostgreSQL/browser acceptance, independent review, merge and deployment remain separate gates. Publication state and any subsequent hosted evidence belong in the draft PR and existing engineering page.
