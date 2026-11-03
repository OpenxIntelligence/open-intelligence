# PACSNode Immutable SOP Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement these bounded tasks with independent review.

**Goal:** Correct and demonstrate atomic immutable SOP storage in the pinned standalone PACSNode evaluation.

**Architecture:** Publish complete immutable filesystem objects through one atomic SOP claim, with persistent byte integrity metadata. Extend the existing evaluator and retain the original failure as historical evidence.

**Tech Stack:** Pinned Rust PACSNode, SQLite/filesystem, existing locked Rust dependencies, Python standard library and existing isolated hash-pinned pydicom 3.0.2.

**Spec:** `docs/superpowers/specs/2026-11-02-pacsnode-immutable-sop-design.md`

## Global constraints

- Upstream remains `e9b4334477a66967d290add9e0b9afa068f59dc0`; record the derived patch/build explicitly.
- Independently authored synthetic inputs only; no image objects in CI artifacts.
- No application dependency, patient authority, H1 custody or adoption change.
- Retain `HOLD_NOT_APPROVED`, the original c7d6b18 failure, and incomplete-run failures.

## Review focus

- Independent processes race for the same SOP: at most one conflicting payload wins.
- Same SOP with changed study/series: cannot bypass the canonical identity claim.
- Interrupted publication: no partial object or replacement can become visible.
- Identical replay and rejected conflict: original bytes and logical inventory stay exact.
- Post-conflict restart and source amendment: bytes persist and stale reads remain refused.

## Task 1: Shared storage invariant and Rust regressions

Files: pinned `pacs-fs-storage` implementation/tests and dependencies; `pacs-core` conflict error; `pacs-api` response mapping; SQLite immutable metadata guards. Package the reviewed changes in `tools/imaging/patches/pacsnode-immutable-sop.patch` with a digest manifest and notices.

- [ ] Run `oi_immutable_sop_red.rs` unchanged against the pinned original; require the specific assertion failure.
- [ ] Implement atomic SOP claim publication and explicit conflict mapping, with byte/hash verification and safe replay.
- [ ] Add meaningful concurrent, fresh-store, hierarchy-rebind and original-preservation tests.
- [ ] Run the unchanged red regression and affected Rust tests against the patch; require success and a locked dependency graph.

## Task 2: Corrective real HTTP lifecycle contract

Files: `pacsnode_lifecycle_evaluation.py`, `pacsnode_lifecycle_process.py`, their regression tests, and `run_confined_pacsnode.sh`.

- [ ] Extend `run_lifecycle_evaluation(..., immutable_write_checks=False)` with strict HTTP409, concurrent authored winner expectations, identical concurrency and retrieve-only checks after conflicts/restart.
- [ ] Add failing contract tests before implementation; keep safe partial receipts and independent tamper tests.
- [ ] Enable `--immutable-write-checks` in the corrective runner and require three verified process restarts.
- [ ] Run relevant Python tests and the application suite, reporting any environment skip explicitly.

## Task 3: Pinned hosted proof and permanent records

Files: existing PACS workflow, engineering record in this repository, patch provenance, and existing project records.

- [ ] Preserve the original failure receipt verbatim and link its original commit/run/digest.
- [ ] Apply the patch only after verifying upstream and patch hashes; record derived source, lock and binary hashes.
- [ ] Require positive lifecycle exit0 and every immutable-write prerequisite; preserve negative/incomplete receipts when a check fails.
- [ ] Inspect the exact-head hosted artifact, independently review the patch and result, and update PR #248 plus the existing registry/checkpoints with measured outcomes.
- [ ] Leave the PR draft/unmerged and adoption HOLD; report the exact bounded result and remaining gates.
