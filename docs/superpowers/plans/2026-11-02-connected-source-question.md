# Connected Source Question Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** One source-linked question authoring, inspection and rechecked brief workflow.
**Architecture:** Reconcile existing child features over their shared canonical source/question owner. No replacement domain models or permission shortcuts.
**Tech Stack:** Existing locked Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript.
**Spec:** docs/superpowers/specs/2026-11-02-connected-source-question.md

## Global Constraints
- Independently authored fictional inputs only.
- No dependency, schema, clinical authority or main-branch change.
- Preserve each donor's tests and existing permission/receipt boundaries.
- Local toolchain checks are supplemental; exact locked PG16/build/browser results require executed hosted acceptance.

## Review Focus
- Delayed quote or brief for a different saved question must never restore a mixed view.
- Permission to inspect does not imply permission to export, and conversely.
- Amendment must retain old question/source history, suppress old current quote and block stale export.
- Draft edits must not overwrite an uncertain saved intent.
- Preview and downloaded bytes must match the literal saved question and source.

### Task 1: Establish failing convergence acceptance
- [x] Preserve donor custom-question and packet tests on unchanged #264 and observe missing behavior.
- [x] Add combined client tests for one question and cross-feature selection/races.

### Task 2: Reconcile source, client and UI
- [x] Three-way merge inspected #268 and #266 changes against #244.
- [x] Resolve conflicts without replacing source/question/brief owners.
- [x] Preserve all independent grants, test methods and migration bytes.
- [x] Add minimal selection/race protection demonstrated by regression tests.

### Task 3: Execute connected acceptance
- [x] Extend apps/web/tools/source_questions_journey.py for custom question -> packet -> actual brief download.
- [x] Run all available local API/client/reference checks, recording skips and toolchain differences.
- [ ] Publish isolated draft candidate and run exact-head hosted API/PG16 and React/browser gates.
- [ ] Download evidence, inspect actual captures and verify source hashes.

### Task 4: Record actual outcome
- [x] Update existing question/brief contracts and backlog with convergence status and limitations.
- [ ] Preserve patch, failure evidence, source manifests and exact acceptance results.
- [ ] Keep draft/unmerged; independent review remains separate.

## Execution rulings

Ruling: Preserve #264 CI files unchanged; full API discovery already includes all imported packet tests, while the combined browser traverses the endpoint. No inherited test or gate is removed.

Ruling: The mixed-question race is fixed in the shared RegistrySession selection, not by adding a second backend ledger or blocking independent permissions. Three new assertions failed before the fix.

Ruling: Keep the source writers and #266 typed packet transport unchanged. Broader final-authority and serialization-boundary reconciliation remains explicit rather than silently claimed complete.

Ruling: Shell GitHub DNS is unavailable. Publish only the exact hashed source tree to a new create-only branch; no main/owner-branch update or merge. Source transport must not execute application code with a publication credential. Actual verification runs under read-only CI.
