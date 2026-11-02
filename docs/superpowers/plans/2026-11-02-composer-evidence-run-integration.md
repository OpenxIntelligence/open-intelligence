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

## Verified implementation receipt — 2 November 2026

**Integrated sources, exact provenance:** This branch starts at verified original [#90](https://github.com/OpenxIntelligence/open-intelligence/pull/90) head `26220a7a47a2a4e37ffe434e87b7dfa2f20523ac`, containing #68/#83/#72. It imports the entire `src/open_intelligence/store.py` blob **unchanged** from [#91](https://github.com/OpenxIntelligence/open-intelligence/pull/91) (upstream blob `c0616989846194c376722548f4616cbc2f14bd17`) only after confirming the target `store.py` blob was identical to the #68 parent `e7267b15466cf9f071d556b8d8e56cfeba90393f`. It also imports the original upstream six-test freshness suite `tests/test_composer_input_freshness.py` unchanged and adds a new cross-branch acceptance suite `tests/test_composer_run_full_integration.py`. No duplicate patient/state architecture, dependencies, model backend, migration or Next.js.

**Red baseline preserved:** At pre-integration head `4d9a39a62d7195b0c43e04b2d945a037212b47aa`, [GitHub Actions #41510066549](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510066549) returned **7 test failures** in new integration tests: previous model results remained current on new accepted source/evidence; existing durable numeric run freshness was independently functional. The untouched duplicate/quarantine tests passed. The red run is expected evidence, not a release pass.

**Green candidate:** Code head `0e902901847a8b4f834e4a9b7ffe7634bb7181c8`, tested against main's GitHub PR merge checkout `e4a6f60`. [GitHub Actions #41510331096](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510331096) **completed success**: 301 Python unit/HTTP tests, both original browser journeys, original Composer browser journey and durable Composer lab/run browser journeys succeeded. [UI-glance #41510331068](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510331068) and [Crossref #41510331107](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510331107) also completed success. Existing broader test suite still emits SQLite ResourceWarnings (16 unclosed-DB warning lines observed in the integrated run); no warning-free claim.

**What this proves:** The existing source/version, question/assessment, model-investigation and computed-run state are consistent for tested fictional input changes. Historical hypothesis/calc results remain inspectable but stale; only affected questions reopen; unrelated patient/question work and quarantined/duplicate reports do not falsely invalidate results. The HTTP workflow exercises actual local server endpoints and persistence, not a mocked widget.

**What remains unproven:** clinical/diagnostic correctness; actual clinician/patient authentication, revocable consent/PHI permissions, licensed current guidelines, real instrument/DICOM/genomics integration, patient-specific treatment recommendations, background run leasing/crash recovery, real hospital EHR, continuous event subscriptions, regulatory clearance or production reliability. Models and lab QC evidence were simulated/independently fictional and not medically verified. This is an engineering integration checkpoint, not clinical deployment.

**Merge/review gate:** This draft is a **test/integration branch**, not a new product service or alternative canonical architecture. Keep upstream ownership #68, #72, #83, #90 and #91; review #91's source-change fix then rebase the tool/work-journal stack on that fix (or apply it in a single reviewed integration). Re-run exact combined CI against newer main and any domain/review/care branches. Nothing has been merged or deployed by this work.
