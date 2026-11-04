# Investigation Review Handoff Implementation Plan

> **For agentic workers:** Execute this bounded task using test-driven development and fresh verification. The parent agent owns independent review and commits.

**Goal:** Prepare one durable, version-checked review draft from a current model investigation without implying human review.

**Architecture:** Reuse CaseStore investigations, questions, sources, evidence, snapshots and review events. Store a nullable captured Composer fingerprint on investigations and a one-to-one provenance link to an ordinary snapshot. Create snapshot and link under one SQLite write transaction; historical unbound runs remain readable but require a new run before handoff.

**Tech Stack:** Existing Python standard library, SQLite, HTTP handler and vanilla JavaScript; no dependencies.

**Spec:** Parent's bounded integration mandate, AGENTS.md, and OI-007/008/009/010 in docs/EXECUTION_BACKLOG.csv.

## Global Constraints

- Independently authored synthetic fixtures only; no live LLM calls or patient-data downloads.
- Preserve existing work and unmerged additive Composer/freshness/knowledge-context changes.
- No Next.js, framework migration, remote writes, alternate clinical model, or automatic review.
- Root owns web/index.html; this task changes only existing app.js UI behavior.
- Adopt/clinical/production readiness are not claimed; root owns commits and independent review.

## Review Focus

- Boolean, zero, negative, string and cross-case identifiers fail without content disclosure.
- Missing captured context, context drift, superseded sources and withdrawn/amended evidence cannot create a draft.
- Repeated/concurrent requests yield one snapshot and one link; an injected link-write failure rolls everything back.
- Model generation and draft preparation leave the question open; only existing explicit review changes it.
- Later input changes preserve original model output, snapshot text and review events while marking affected linked reports stale.

## Task 1: Persist and validate the handoff

**Files:** src/open_intelligence/store.py, src/open_intelligence/review_draft.py, src/open_intelligence/changes.py, tests/test_investigation_review_handoff.py.

**Interface:** CaseStore.prepare_investigation_review_draft(case_id: str, investigation_id: int, question_id: int) -> dict with investigation_id, snapshot_id, state, duplicate and provenance.

- [x] Write and run failing persistence tests for source/evidence citations, hypotheses/uncertainty/abstentions, restart, strict identifiers, stale/missing context, rollback, idempotency and retained review history.
- [x] Add migration and provenance association; refactor snapshot insertion into a transaction-owned helper; implement deterministic rendering and case/question/current-input checks.
- [x] Stop save_investigation from marking a question addressed; update the earlier draft freshness tests whose expectations encoded that bug.
- [x] Verify focused tests, including concurrent creation and failure rollback.

## Task 2: Connect the existing HTTP and UI workflow

**Files:** src/open_intelligence/__main__.py, web/app.js, tests/test_investigation_review_handoff_http.py, tests/test_investigation_review_handoff.js.

**Interface:** POST /api/cases/{case}/investigations/{id}/review-draft with strict question_id; 201 for creation, 200 for retry, 422 for invalid/stale requests. State/investigation responses expose provenance and linked snapshot state without changing original review_state.

- [x] Write and run failing real HTTP tests for replay -> handoff -> export -> explicit review -> amendment, wrong-case responses and malformed IDs.
- [x] Capture a server fingerprint before every run, including requests without a preview token; persist it only if inputs are unchanged after execution.
- [x] Add a single Prepare review draft action to current model cards; show existing link/state on retries, source/evidence readers for citations, and model provenance in generated reports/exports.
- [x] Exercise selected-case changes and stale async responses using the actual app.js functions with the existing no-dependency Node harness pattern.
- [x] Run PYTHONPATH=src python -m unittest discover -s tests -v, node --test tests/test_*.js, and the available canonical browser checks; report any unavailable gate.

## Verification evidence

- Initial persistence RED: missing handoff method plus the existing addressed-on-generation defect. Initial HTTP RED: absent route, uncaptured inputs and stale-input acceptance without a preview token. Initial UI RED: absent action functions.
- Focused persistence: 16 tests pass, including the old-schema migration, literal Markdown-like content, bounded report size, source/evidence amendment, withdrawal, rollback and concurrent retries.
- Real loopback HTTP: 4 tests pass. Live-mode provenance uses a stub at the model-call boundary; no live model call is made.
- JavaScript: all 46 repository tests pass, including 7 new tests of the actual action/list/citation functions.
- Final full Python regression: 299 tests pass in 33.972 seconds, including the linked-report stale-state projection through changes_since_review.
- A second read-only code-review pass found no blocking defects. Its minor finding that manual stale drafts incorrectly suggested a model rerun was corrected with separate wording for model-derived and human-authored drafts.
- `git diff --check` passes.
- Both `python tests/browser_journey.py` and `python tests/composer_browser_journey.py` were attempted. They fail at their explicit prerequisite check because no Chrome/Chromium executable is installed. Browser rendering/journey verification remains open; no browser dependencies were installed.

## Rulings and gaps

- Legacy investigations without a captured fingerprint are never backfilled with today's inputs; a new run is required.
- Idempotent retrieval of an already-linked current report is allowed after its explicit review; no new report is created. Stale runs/reports remain readable but cannot be handed off again.
- The existing model citation contract identifies a source version, not an exact claim span. Do not fabricate a line anchor; evidence assessments retain their actual statement-line reference.
- After independent edge-case review, the internal generated-report handoff preserves every canonical source and assessment dependency, including counts above 50. A source-free report is permitted only for a genuine abstained run with no accepted claims and at least one valid abstention. Public manual drafts retain at least one source, at most 50 sources/assessments, and a 3,000-character limit. Generated report text is bounded at 65,536 characters and rejects overflow without truncation.
- Original output and prepared-report hashes, replay/live mode, model identifier, template name, captured context and cited versions are retained. The pre-existing model runner does not provide immutable model-weight or prompt-template-version attestations.
- No verified clinician identity, clinical judgment, real-patient authorization, extraction qualification, or production hardening is added.
