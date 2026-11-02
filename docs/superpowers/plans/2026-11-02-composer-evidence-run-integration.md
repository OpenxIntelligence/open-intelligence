# Composer + Durable Computation Evidence Freshness — Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that the same accepted source/evidence change correctly invalidates saved model hypotheses and saved deterministic computation runs, while preserving exact originals and unaffected patient/question state.

**Architecture:** Combine existing *unmerged* #90 (Composer context, deterministic lab tool, saved run journal; already includes #68/#83/#72) with #91's *tested* narrow CaseStore freshness correction. Own no new patient data model, source store, application route, model backend, framework or UI. Add one actual-application HTTP/SQLite integration regression to assert combined behavior. Do not modify upstream feature branches or merge automatically.

**Tech Stack:** Current Python stdlib SQLite, unittest, existing ThreadingHTTPServer, existing Chromium CI; no new package, no Next.js, fictional-only.

**Spec:** Existing founder full-first-party product mandate; `docs/engineering/DURABLE_COMPOSER_RUNS.md` (#90); `docs/superpowers/plans/2026-11-02-native-composer-context.md` (#68); review findings in PR #91.

## Global constraints

- Preserve `CaseStore` as this experimental application's canonical case/source/evidence record; `DurableComposerRuns` is a bounded journal, never clinical authority or second patient store.
- Target only synthetic authored `OI-SYNTHETIC-REPORT/1` and `OI-SYNTHETIC-EVIDENCE/1`. No actual patient or guideline data, live model calls, external links or commercial package adoption.
- Real EHR/LIS, identity, clinical reviews, PHI, regulatory clearance and production access stay unimplemented.
- No source deletion, historical model overwrite, counterfeited review, duplicate run on same idempotency key or cross-case data leak.
- Protect teammates' open branches (#68, #72, #83, #90, #91, #94, #95); do not merge or deploy.

## Review focus

1. A **new accepted source** stales the saved model hypothesis and completed numeric run simultaneously; old result remains traceable, question reopens, other case unaffected.
2. A **human-authored evidence assessment** is input to the model; adding it stales only that question's model work and its exact-context computation journal.
3. A **withdrawn/amended assessed evidence version** stales the old work but retains original assessment/receipts.
4. Duplicate or wrong-patient quarantined report does NOT invalidate unrelated output.
5. Browser and HTTP read paths show stale status; existing work does not silently re-compute or create a medical decision.

### Task 1 — Red cross-branch actual application tests

**Files:** Create `tests/test_composer_run_full_integration.py`.
- [ ] Test one case through CaseStore source → question → original replay/validated model → journal queue/execute → new source → stale model and run.
- [ ] Test assessment and evidence withdrawal with a second case/question control, historical receipts and exact source anchors.
- [ ] Test real local HTTP routes for preview, replay, enqueue/execute, original source import, read statuses.
- [ ] Verify RED against unmodified #90, and preserve exact CI link/error.

### Task 2 — Integrate already-verified #91 change

**Files:** Target only `src/open_intelligence/store.py` and `tests/test_composer_input_freshness.py` from the exact tested #91 head, after matching #90's store blob against #68.
- [ ] Preserve unchanged #90 work; apply tested CaseStore stale/reopen helper and six upstream regressions by exact source byte match; no parallel implementation.
- [ ] Run full exact-head hosted CI and existing Composer/lab/durable-run Chromium journeys.
- [ ] Review green source, question/evidence and computation state, cross-case isolation, warnings and test scope.

### Task 3 — Reviewable integration handoff

**Files:** Update this plan and existing Notion/Google Docs engineering records, link PR #68/#83/#90/#91.
- [ ] Link target PR with correct upstream dependency order and exact commit/test evidence.
- [ ] Keep source-rights, identity/authorization, failed leases, clinical validation and real first-party EHR/LIS gaps explicit.
- [ ] Do NOT mark upstream proposals merged, implemented on main or production ready.
