# H1 document convergence implementation plan

> **For agentic workers:** Use the existing execution and verification workflow; preserve the source owners and the evidence limits below.

**Goal:** Prepare one reviewable synthetic candidate containing the existing reviewed-document workspace, restored-document HTTP proof, evidence/review chronology and status safeguards, shared-input CI coverage, and the accepted pinned-main reference fixes.

**Architecture:** Continue the single React application and canonical FastAPI/PostgreSQL owners from #354. Compose existing contributions through their actual ancestry; preserve document custody, immutable annotations, question/evidence/report ownership, and the single migration head. This is an integration contribution, not an architecture change.

**Tech stack:** Existing React/Vite/TypeScript and Python/FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL 16; exact existing dependency locks.

**Spec:** `docs/engineering/H1_EVIDENCE_CONVERGENCE_MERGE_GATE.md`; the supplied 3 November engineering handoff, sections 6A–6C; existing workspace #119 and acceptance #121.

## Global constraints

- Independently fictional engineering material only; no external clinical effect.
- Reuse #354 (`d9b81f08a97998e8f95d2a1cc7c43b4165e99862`) as the document-workspace base.
- Preserve #362 (`c7fd1bd865f4a8f42da1e515a2599431d14f0a8d`) restored-document tests and history; do not recreate that implementation.
- Reconcile #364 (`243d15fdaba112f93f7d3d258311d8b82e730015`) evidence chronology and truthful recovery status, and #367 (`bbf56762e73f50fbe6432768deb605ed03edf09b`) shared CI/documentation changes.
- Include a newer descendant only after identifying its owner, exact source and relevant evidence; record the decision.
- No new dependencies, alternate state owner, schema rewrite, clinical conclusion or main-branch merge.
- Manual text/PDF annotations remain explicitly attributed and excluded from structured-source question snapshots until a separately reviewed contract connects them.
- Parent results remain parent evidence. Combined-source acceptance must identify the tested commit and environment.

## Review focus

- Conflict resolution must preserve both reviewed-document controls and the composed source/evidence workflow.
- Source recovery must still verify restored originals, annotation history, exact retry and independent access rights.
- Failed/uncertain evidence writes must retain the exact original intent without falsely describing a report submission as a saved comparison.
- New frontend validation must preserve the backend's distinct authored-evidence and citation timestamp contracts.
- CI path coverage and retained acceptance scripts must survive composition; a passing sibling must not become combined verification by inference.

## Task 1: compose existing owners

**Files:** existing files changed by the selected source owners; the existing convergence gate and execution backlog; this plan.

**Interfaces:** Existing API contracts and `RegistrySession`; no new public interface.

- [x] Refresh main and current donor heads, inspect relevant diffs and ancestry, and read applicable instructions.
- [x] Create an isolated branch from #354 and run the existing client baseline (383 passed, no skips).
- [x] Compose #362, the selected #364 descendant, and #367; resolve only actual conflicts and preserve both histories.
- [x] Verify API domain code, migrations and dependency locks still match the document-workspace owner except explicitly recorded donor changes.
- [x] Record included/deferred contributions, original commits and the exact combined source identity in the existing convergence gate.

## Task 2: verify the combined behavior

**Files:** existing client/reference/API tests and browser/recovery harnesses; no duplicate tests that restate the merge.

- [x] Run the synthetic-data boundary audit, all client tests, rights checks, TypeScript/production build, and the reference regression suite.
- [x] Parse workflows and verify one coherent migration head without changing migration contents.
- [x] Run the API suite under its declared environment where available; report missing PostgreSQL/Docker/Chromium explicitly.
- [ ] Use exact published-source hosted API, client/browser and recovery gates if publication is available under session authorization. Retain failures and pending states without weakening acceptance.

## Task 3: independent review and concrete delivery

- [x] Request a fresh independent review of the combined diff and conflict decisions, with the review focus above.
- [x] Address material defects with reproducing behavior checks and rerun affected acceptance. No material defect was found; three historical-status documentation ambiguities were corrected without changing application or test bytes.
- [ ] Record actual results, source identity and remaining limits; prepare the concrete patch/draft for existing owner review.
- [ ] Report the live-state delta and next unresolved connection. Full MRT-01 and clinical readiness remain unestablished.

## Execution notes

- The initial reference-test invocation omitted `PYTHONPATH=src` and failed during imports (27 import errors). This was an invocation error, not an application defect; the correctly configured run is retained separately.
- Local runtime has Node/Python but no PostgreSQL, Docker or Chromium executables at setup. No substitute database will be presented as PostgreSQL acceptance.
- The handoff explicitly prioritizes blocking integration before a new document-to-question feature. This contribution follows that sequence.

- Inclusion ruling: #368 at `2d62b05357ad64524d561c2e05c903674cd4e54c` is an exact descendant of #364 with a completed successful web run 41703623630; include that owner instead of separately merging #364.
- Integration ruling: run review-draft browser boundaries before reviewed-document intake because the former requires two existing cases and the latter adds a third. Both implementations and all assertions are preserved.
- Initial deferral ruling (superseded for pinned main): current main, DOI and image/archive descendants were kept separate while the selected document composition was reviewed. The final inclusion ruling below incorporates the accepted reference fixes; DOI and image/archive work remains deferred.
- Final inclusion ruling: include #374 `95346a5104c608e4069f856dace7679eb8dcd683`, which preserves #372 strict follow-through validation and #368/#364 ancestry. Its shared-path workflow is already byte-identical to #367. Include accepted main `c4798ae85004713593f83458abd2102be6729095` by clean merge so the candidate tests the current pinned shared reference inputs. This is the candidate cutoff, not a claim about later moving branch heads.
- Local verification: intermediate 398 client and 304 reference passes were followed by 415 client and 351 reference passes after the final inclusions. All 13 rights controls, production build and exact-wheel rights checks passed. API discovery found 436 tests, with 109 passing and 327 intentionally skipped without PostgreSQL. Full hosted acceptance remains required.
- Independent automated review found no Critical/Important defect and independently passed 18 focused client controls plus nine recovery-oracle negative controls. This is not human owner approval.
- A focused independent review of the final #372/#374 and pinned-main additions through `805aa2ce2cf51f36f9fc6027f41fbf46b9804897` also found no Critical/Important defect; it checked shared imports and ownership, timestamp serialization, scoped browser fault injection, ancestry and retained browser ordering. Combined hosted acceptance remains distinct.
- Publication recheck found concurrent #354 `7b16a9a900737f07adb03e35362922c886424e9b`, already composing the same runtime owners and adding document-denial/late-inbox browser coverage. Preserve this new work rather than publish a divergent document owner. The dependent draft now targets that existing #354 branch and contributes accepted-main reconciliation, #374 ancestry and this verification record. Application and unit-test sources remain identical to the locally verified composition; the added browser helper requires this dependent head's own hosted acceptance.
- This committed plan is a prepublication checkpoint. The candidate's own PR receipt records the final published head, subsequent hosted acceptance and final delivery; preserving that record avoids changing tested source merely to mark checkboxes.
