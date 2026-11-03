# Restored manual-selection reference acceptance

> Execute inline with `superpowers:executing-plans` under the existing continuation mandate.

**Goal:** Prove that exact source-owned manual passage references survive PostgreSQL restore with current authority and unchanged human attribution.

**Architecture:** Extend the existing source recovery probe from #362, as carried by #385 at `7494fa983a44b95a770f2ec48544d4fcd8bab613`. Exercise #385's existing GET resolver against actual restored databases, preserving the original document/source/question owners.

**Tech stack:** Existing Python 3.12, FastAPI, PostgreSQL 16 and Compose verification; no application, migration, dependency or UI changes.

**Spec:** `docs/superpowers/plans/2026-11-03-source-selection-reference.md` and `docs/engineering/H1_REVIEWED_DOCUMENTS.md`.

## Bounded design and constraints

The earlier document recovery checks cover originals and annotation histories, but not the new selection-reference HTTP envelope. Compare exact historical and current references for the existing independently authored text and two-page PDF fixtures. Preserve original/extraction/review hashes, selecting actor/time, revision, literal quotation and physical page. Only access receipt identity may differ after recovery.

Keep current/historical state outside the immutable anchor hash. Test the same selection key reused by a correction so the older revision cannot silently resolve to the latest quotation. Missing revisions/keys and a revision from another document must fail closed without effects. Require source-read, original-read and patient grants independently, including positive reads without import permission. Repeat after API/database restart and deny all references after restoring a revoked binding with every grant enabled.

Extend the existing complete-row/sequence oracle to account for selection-read receipts with exact patient/case/source/revision/key/hash scopes. The original database and the intermediate revoked database must remain untouched by reads of their restored copies. Preserve all five recovery gates and the seven-day artifact policy. Add selection evidence to the existing recovery JSON under version 2; do not introduce a second receipt artifact.

## Task 1 — restored references and proof

Files: `apps/api/tools/verify_sources_compose.py`, `apps/api/tests/test_source_recovery_assertions.py`, this plan, and the existing document/backlog records.

- [ ] Add local negative controls for changed anchor content even with a recomputed hash, wrong freshness, malformed receipts and wrong receipt revision/key/hash. Observe failure against a permissive assertion, then implement the exact comparison and rerun green.
- [ ] Capture and independently check historical/current references from the authored fixtures; reuse the selection key with a different quote during correction.
- [ ] Read all four references from the actual restored database and across both service restarts; account for each receipt and preserve all business rows/sequences.
- [ ] Exercise missing/cross-document references, wrong patient/case, changed purpose, missing independent grants and restored binding revocation; assert no effects.
- [ ] Record anchors/hashes and bounded acceptance flags in the existing recovery artifact; update scope records without claiming question/report integration.
- [ ] Run local suites and independent whole-diff review; publish a dependent draft and verify its actual hosted PostgreSQL/HTTP recovery result and retained artifact on one pinned head.

## Review focus

- Same key with a corrected quote must retain the older exact revision.
- Text page null and PDF physical page 2 must survive unchanged.
- Hash equality cannot substitute for current patient/original-read authority.
- Receipt events must match the actual requested revision and occur only in the restored copy.
- Rejected reads must neither create disclosure receipts nor consume business sequence values.

## Limits

Manual passage → canonical question → report integration remains separate. Existing structured-source question semantics must not silently classify a user-selected passage as a source-authored observation. No merge, deployment, clinical approval or real-patient input is part of this increment.
