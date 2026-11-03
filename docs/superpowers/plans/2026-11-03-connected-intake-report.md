# Connected Intake and Report Implementation Plan

> For agentic workers: execute inline using superpowers:executing-plans and test-driven-development.

**Goal:** Connect the source-owned inspected multi-file intake to the verified patient record/report/follow-through tree.
**Architecture:** Reconcile #203 against common #175 into #210. Preserve domain modules and use the existing browser write and source-inspection owners.
**Tech Stack:** Existing Python standard library/SQLite and browser JavaScript; no dependencies added. H1 migration target unchanged.
**Spec:** docs/superpowers/specs/2026-11-03-connected-intake-report-design.md

## Global Constraints
Synthetic inputs only; no Next.js; no new authority/store; no automatic merge/deployment.
Untrusted original bytes and source identity are never rewritten. No claimed clinical validation.

## Review Focus
- In-flight or unknown import must invalidate the previous report without automatic retry.
- Concurrent case/global writes must share existing counts, not overwrite one another.
- New workspace and case switching must not discard unfinished follow-through inputs.
- Composer source actions must resolve only inside the currently accepted source context.
- Parent CI totals are not evidence for the combined source tree.

## Tasks
- [x] Record baseline; assert missing connected entry before integrating source-owner files.
- [x] Reconcile #203 source changes relative to #175, preserving #210 code and tests.
- [x] Add real-client timing regressions reproducing upload/report invalidation failure.
- [x] Route raw import responses through the existing api write-tracking boundary; retain per-file status and error semantics.
- [x] Add and verify scope/unfinished-work and Composer source-action regressions; repair only reproduced gaps.
- [ ] Run full Python/HTTP, all JavaScript, syntax and original/new browser journeys on one exact source tree.
- [ ] Update the existing connected implementation record and publish one isolated draft with exact verification receipts; no main merge.

## Execution receipt
Baseline #210 tree 9553a486c3811599368cf31212df030e37b72511:
660 Python/domain/HTTP tests passed locally in 31.654s using TMPDIR=/dev/shm.
This establishes regression baseline, not power-loss recovery or clinical safety.
