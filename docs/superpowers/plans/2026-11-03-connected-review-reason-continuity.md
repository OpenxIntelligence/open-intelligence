# Connected verification-reason continuity implementation plan

> Execution: continue the approved convergence mandate in an isolated candidate; no owner branch or main is changed.

**Goal:** preserve the exact unfinished verification-return reason while inspecting sources in the current H1 workspace, without persisting it or implying a submitted review.

**Architecture:** retain one App-owned presentation draft hook from #324, while RegistrySession continues owning submitted/uncertain intents and exact retries. Current source, evidence comparison, chronology, report and follow-through owners from #364 stay intact.

**Tech stack:** existing locked React/Vite/TypeScript, FastAPI/PostgreSQL and Chromium harness. No new dependencies.

**Source specification:** #324 at runtime `0d08fa657c0416201536a84da9af60a8f8be7b53`; current base #364 at `243d15fdaba112f93f7d3d258311d8b82e730015`. Existing AGENTS.md and FIRST_PRINCIPLES_PLAN.md remain binding. OI-007/009/010/013 stay incomplete program work.

## Constraints and review focus

- Fictional inputs only; no patient data, model, professional approval, merge or deployment.
- Backend, API, migrations, session, rights, dependency locks, workflow, and chronology/assessment behavior must remain byte-identical to base.
- Same patient/case navigation retains text without submitting it; A/B/A, denial and disconnect must clear it.
- A fresh independent Review authorization restores editability after a prior World Model failure.
- Submitted/uncertain captured text and request keys keep priority over presentation drafts.

## Task 1: reproduce on the composed workspace

- [x] Recover both exact hosted source artifacts and confirm base tree `cdb0a67b2d64ab905ba21c30cf9bdfc15dd9d3db` (422 files).
- [x] Compare the two UI files and three browser helpers. Differences are the scoped donor behavior; no current application functionality is replaced.
- [x] Copy donor `question_review_journey.py`, `connected_question_review_journey.py`, and `browser_journey.py` unchanged as a tests-first checkpoint. Existing current helper bodies are preserved with additive assertions.
- [x] Run existing exact-head H1 web workflow before UI adoption. Expected failure: same-context navigation loses the authored reason.

## Task 2: selective adoption and acceptance

- [x] Reuse only donor `main.tsx` and `review-panel.tsx` after the behavioral failure is observed. All five donor application/helper files must match their original blobs.
- [ ] Run the full client suite, dependency controls, production build and actual PG16/FastAPI/Chromium journey at the final candidate.
- [ ] Inspect source equality, source-boundary scanner, screenshots and recovery JSON; retain failed and passing run identities.
- [ ] Record the bounded OI-009 continuation and final verification in this plan/PR, without marking the wider backlog item complete or relabelling donor/parent evidence.

## Execution record

Current source and donor ZIP digests were verified. The base Git tree reconstructed exactly. Local pinned npm acquisition did not complete within its bounded attempt; no local full client/build/database pass is claimed. Hosted tests remain required. No independent reviewer is available in this executor; source composition receives self-review and remains draft pending independent review.

Tests-first head `0ab977747a410fb1943bc96109b03d70dafa7f84`, hosted run 41702800047, reproduced the exact reason-loss assertion in the actual PG16/FastAPI/Chromium journey after all 375 client tests, build and dependency gates passed. Red artifact SHA-256: `39c838f84aba6c5ae984748fa3bbea972d4b51634a7569a757ba38859db0f4b2`. The five selectively adopted runtime/helper blobs match #324 exactly. Local reference suite: 287 passed in 21.182 seconds; existing SQLite ResourceWarnings remain. An earlier 18-second reference run was interrupted and is not counted as a pass. Local client attempt: 363 passing controls and two file-load failures from unavailable React (`evidence-continuity-panel.test.mjs`, `question-evidence-panel.test.mjs`); global TypeScript is 5.8.3, not the locked toolchain. Final hosted pinned acceptance remains required.

Ruling: retain the existing canonical continuity ledger and execution backlog byte-for-byte. This scoped plan and its linked PR provide the additive OI-009/010 receipt; no whole-workstream completion or competing roadmap is claimed. Final hosted verification must close the pending checklist through a PR receipt tied to the exact source head.
