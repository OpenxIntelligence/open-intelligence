# Restored document HTTP acceptance

> Execute this bounded continuation inline with `superpowers:executing-plans`.

**Goal:** Prove that source-owned reviewed text/PDF originals and immutable correction history are usable only with current authority after actual PostgreSQL restoration.

**Architecture:** Extend the existing source Compose probe on PR #349 at `03ccca85026c5d437a288f62c5b48f4a74054bfa`. Reuse its source owner, migrations, HTTP routes and independently authored fixtures. Recreate the same API against restored databases and confirm its configured engine target.

**Tech stack:** Existing Python 3.12, FastAPI, PostgreSQL 16 and Compose verification; no dependency or application changes.

**Spec:** `docs/engineering/H1_REVIEWED_DOCUMENTS.md`, specifically the documented restored-document HTTP gap; OI-006, OI-013 and GH-323 in `docs/EXECUTION_BACKLOG.csv`.

## Constraints and review focus

- Fictional data only; manual selections remain user-attributed and excluded from structured observations.
- Preserve all inherited source/restart/denial checks and all five CI recovery gates.
- Exact binary bytes, CRLF/Unicode text, frozen PDF physical-page anchors and correction identities must survive recovery.
- Read-only recovery must not alter business rows, prior events or non-access sequences. Returned receipts must belong only to the serving restored copy.
- Test independent read/original/import grants, changed patient scope/purpose, wrong case, and a revoked binding restored again; denial cannot be masked by a missing grant.
- No merge, deployment, clinical acceptance or manual-provenance promotion.

## Task 1: Extend actual restored-source acceptance

Files: `apps/api/tools/verify_sources_compose.py`, `apps/api/tests/test_source_recovery_assertions.py`, `.github/workflows/h1-api.yml`, and the existing reviewed-document/backlog records.

- [ ] Add controlled snapshot negative tests for changed history, unexpected business effects, wrong/missing/duplicate access receipts and sequence drift. Execute them against a deliberately permissive initial assertion, then implement the strict assertion and verify green.
- [ ] Extend snapshots to all application tables and sequence states. Reuse the evidence probe's explicit database recreation and engine-target verification pattern.
- [ ] Serve active restored text/PDF documents, exact original downloads, collection/history and exact original intake/correction retries. Verify current authority independently, restart both services and repeat.
- [ ] Revoke the binding on the restored copy, restore it again, verify target identity and deny reads/preview/import/retries with all grants enabled. Prove original and intermediate copies are unchanged.
- [ ] Emit a bounded JSON acceptance receipt into the existing workflow artifact. Update existing scope records without claiming hosted execution prematurely.
- [ ] Run focused local checks and an independent whole-change review. Publish a dependent draft and verify actual hosted PostgreSQL/HTTP/recovery results on its exact head.
