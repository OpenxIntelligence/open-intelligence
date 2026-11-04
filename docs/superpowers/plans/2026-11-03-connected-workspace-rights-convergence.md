# Connected workspace rights convergence implementation plan

> Execute inline using executing-plans and test-driven-development; preserve independently owned drafts.

**Goal:** Carry the verified #339 installed-package identity and evidence-boundary correction into #348's connected source/question/evidence/report/follow-up application.

**Architecture:** Reuse the exact donor gate, its 13 filesystem tests and its existing npm/CI invocation. Keep one application and all existing source/domain owners; no dependency additions or new license approval.

**Tech stack:** Existing Node/React/TypeScript/Vite and unchanged FastAPI/PostgreSQL 16.

**Specification:** #339 at d694db4ca12206e815d6045b73baa9b6f7394290; current base #348 at d15aa208adcb13b3c0621cc44a384a8fa37affb3. Existing AGENTS.md, dependency-license inventory and H1_EVIDENCE_CONTINUITY.md remain authoritative within their scopes.

## Global constraints

Preserve the package lock, dependency versions, source/runtime, patient/World Model/evidence models, API, migration and grant definitions. Independently authored filesystem fixtures only. No merge, deployment, license selection or clinical approval. The unrelated donor research crosswalk remains separately owned and is not imported.

## Review focus

Ordinary/scoped/nested/npm-alias identities must remain supported. Wrong identity or license must fail. Noncanonical paths and symlinked directory/manifest/notice evidence must fail without outside bytes. Missing optional packages remain explicitly uninspected; malformed installed optional packages fail. Preserve false commercial-release/native-linkage approval flags.

## Task 1 — integrate one existing gate and its acceptance

Files: apps/web/tools/license-gate.test.mjs (new unchanged donor); apps/web/tools/license-gate.mjs, apps/web/package.json, .github/workflows/h1-web.yml (donor logic with terminal blank lines normalized after verifying no unrelated parent changes); this plan (execution receipt).

- [x] Copy only the donor tests and run `node --test tools/license-gate.test.mjs` against the current gate. Expect eight rejection controls to fail and five compatibility controls to pass. Record actual output.
- [x] Copy the donor gate (terminal newline normalized) and minimal original npm/CI wiring; run all 13 filesystem tests. Expect zero failures/skips. Verify package-lock bytes unchanged.
- [x] Review the full delta and assert all application/backend/contract/migration files match the base. Record no independent-review claim unless actually obtained.
- [ ] Publish one isolated draft child on the exact #348 head, preserving donor attribution and existing source branches; do not merge either source PR.
- [ ] Require exact-head hosted locked-dependency, 336-client-test, build and actual PostgreSQL/FastAPI/Chromium acceptance. Preserve any failures and report unexecuted gates honestly.

## Execution evidence

Recovered base artifact 13249843810 (SHA-256 d3ca8bb3ce67510490bdbb7f76203d5369f3a284639ddf07487c8e35c489e9e6) and donor artifact 13248725004 (SHA-256 e78cc7a597ef0e8490b0fe28f90d672899d1b930b8236ea5b3696b25edb688ec); both checksums and commit markers verified. Base archive reconstructs Git tree 57cb9614b0297ac74812d09c0a40b959498d1de7 exactly (410 files).

RED: unchanged current gate ran 13 original donor filesystem tests: five compatibility passes, eight expected rejection failures. GREEN: copied donor gate passes 13/13 with zero failures/skips. Tests are byte-identical to the donor. Node syntax checks pass; package lock is byte-identical.

Local full `npm test`: 327 passed, two test-file failures because React is not installed in this isolated executor (evidence-continuity-panel.test.mjs and question-evidence-panel.test.mjs); no skips. Local global TypeScript is 5.8.3, not the locked 5.9.3, so this is not pinned-toolchain acceptance. Hosted workflow must supply the unchanged locked dependencies, complete all 336 inherited client tests and execute the actual browser/API journey. No local API/PostgreSQL or browser pass is claimed.

Ruling: normalize only terminal blank lines in the three donor implementation/wiring files so diff whitespace checks pass; no statements, conditions, tests, schemas or source policy change. Do not import the unrelated research crosswalk. This is source composition and self-review, not independent approval, legal clearance or a hostile concurrent-filesystem sandbox.
