# Exact saved-question inspection from preparation

> **For agentic workers:** Use superpowers:executing-plans for this bounded task and one final independent source review.

**Goal:** Let a patient open each saved agenda question's attached records and reports, including after an attached passage correction, without searching the general question list.

**Architecture:** Extend the existing preparation row action. Reuse `onResumeQuestion(questionId)` and the parent App's scoped evidence read/focus behavior. Unfinished passage rows retain their distinct resume action. No new state owner or API.

**Tech Stack:** Existing React/TypeScript/Vite and PostgreSQL/FastAPI synthetic workspace; Next.js excluded.

**Spec:** Existing `docs/FIRST_PRINCIPLES_PLAN.md` shared brief and second-time-point requirements; OI-007/008/009. Parent #461 at `701afe959ecf8b3a5e58d1059b231d595fbba764`, tree `82e4d1d8079cada743f3fb85618010ee2f8b2e2b`; this contains #449 and the verified passage draft/refresh/resume work.

## Constraints and review focus

- Exact current patient/case/question only; hide actions when authorized question history is unavailable.
- Current primary source does not certify supplementary passage/report freshness. Keep the separate-check notice.
- Clicking is navigation and fresh authorized reading, never a task/passage/report write.
- Other questions must not inherit the selected question's passages or historical reports.
- Preserve unsent draft recovery, source denial, historical bytes, keyboard focus and existing owners.
- No backend, dependency, schema, grant or workflow changes; synthetic-only, draft, unmerged, undeployed.

## Task 1: Connect existing saved-question inspection

Files: `apps/web/src/second-opinion-preparation-view.tsx`; its rendered panel test; `apps/web/tools/question_manual_passages_journey.py`; this plan and the existing backlog.

Interface: `SecondOpinionPreparation` consumes `onResumeQuestion(questionId: string): void`; the parent already navigates to Investigations, rechecks evidence and focuses `manual-context-heading` only for the matching packet. Keep that handler unchanged.

- [x] Inspect current source/branches and prove #461 includes #449. Independently verify the downloaded parent artifact and all 657 source blobs/modes.
- [x] Add a rendered behavior regression: saved rows have one escaped, question-specific inspection action; draft rows keep resume; unavailable/foreign/disconnected contexts expose neither.
- [x] Extend the actual browser journey with two distinct saved questions after passage correction. Require fresh per-question reads, empty unrelated context, preserved historical report, stale-report controls and zero navigation writes.
- [x] Observe the new rendered test fail on the unchanged parent UI.
- [ ] Add the conditional saved-row action using the existing callback; run full hosted client/rights/build/browser acceptance.
- [ ] Independent review and exact artifact verification; record final results and limits in the PR, Notion and Drive.

The rendered test catches the missing ordinary saved-question action. The browser catches wrong-question routing, cached disclosure, lost correction status, missing focus and unintended writes. Existing parent tests cover uncertain-command and draft recovery. Full standalone API/restore verification is separate because backend bytes are unchanged.

## Verification checkpoint

Tests-first run [41883448597](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41883448597), head `0268f71bcf92ff1cf896d45482a1aff80dccb852`, passed 535 prior client tests and 13 rights controls. The one new rendered test failed with `0 !== 1` at the missing saved-question action. No tests were skipped; build/browser did not run after the expected failure.

The production change is only the preparation row conditional: saved rows use the existing callback, draft rows retain their existing recovery action. Parent navigation/session/source/permission/backend behavior remains unchanged. Local 55 projection/passage tests passed via Node transformation; full local npm test is blocked by absent `tsc`. This is not build evidence. Final exact-head hosted acceptance, source review and artifact checks remain pending at this source checkpoint; the PR final receipt records their outcomes without moving tested code.
