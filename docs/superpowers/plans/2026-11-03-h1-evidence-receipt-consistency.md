# H1 evidence save-receipt consistency implementation plan

> **For agentic workers:** use superpowers:executing-plans with regression-first verification.

**Goal:** A contradictory success response must not discard a comparison draft or its exact recovery intent.
**Architecture:** Extend the existing `QuestionEvidenceSession.#send` acceptance boundary, after decoding the receipt and checking request generation, before success publication. Preserve the existing unknown/retry owner; add no state or API.
**Tech stack:** Existing TypeScript/React/Vite client and Node tests; existing real FastAPI/PostgreSQL browser gate.
**Spec:** `docs/superpowers/specs/2026-11-03-h1-evidence-comparison-draft.md` plus the unchanged `apps/api/src/oi_api/authored_evidence_routes.py:prepare_json` wire contract.

## Global constraints
- Base is #348 at `297c9d4928105a77c9cf132a17b244409611c018`, Git tree `b515b6379e373f92176cc23afa2f145438b4c0b7`; #338 is already integrated. Do not duplicate it or modify either source owner.
- HTTP 201 and `duplicate:false` describes creation; HTTP 200 and `duplicate:true` describes a duplicate/recovered effect. Both are valid on first submission **or retry**. The client cannot infer whether an earlier ambiguous request committed.
- Contradictory pairs follow the existing unknown-outcome path: withhold receipt, retain exact frozen intent/draft, block replacement/edit/discard, and allow explicit identical retry. No automatic retry.
- No backend, schema, migration, permission, dependency, workflow or project-license change. Fictional engineering data only; no live medical inputs, model use, clinical approval, merge or deployment.

## Review focus
Contradictory receipts on all four commands; contradictory retry remains unresolved; valid creation on retry; draft loss; actual committed request recovery without a second effect. Preserve independent citation metadata and follow-through owners.

### Task 1 — client acceptance boundary
Files: `apps/web/tests/authored-evidence-receipt.test.mjs`, `apps/web/src/authored-evidence-session.ts`.
- [x] Add 22 cases using real RegistrySession/validators and existing fictional fixtures.
- [x] Run red: 10 fail with actual `saved` versus expected `unknown`; 12 valid-response/retry controls pass.
- [x] Reject only inconsistent status/duplicate pairs before clearing the draft or publishing success.
- [x] Run all client tests; record missing dependencies separately from behavioral failures.

### Task 2 — actual browser delivery fault
File: `apps/web/tools/authored_evidence_journey.py`.
- [x] Extend the existing observer to deliberately change only the duplicate bit on one real committed 201 assessment response. Retain actual server response separately and disclose the injected fault.
- [x] Verify unknown status, retained/locked draft, identical request bodies, recovered original assessment ID, exactly one persisted effect, and normal later comparison/report work. Retain the original post-commit lost-response test.
- [x] Run the unchanged hosted React/FastAPI/PostgreSQL gate on the published child; inspect archive and captures.

### Task 3 — verification and delivery
- [x] Self-review full delta and confirm unchanged source-owner files; no independent review claim.
- [ ] Record exact source tree, tests, environment limitations and failed attempts.
- [x] Publish as a draft child of #348 and leave main/parent untouched. Record evidence in the existing integration thread.

## Execution ledger
The #348 source archive digest matched its GitHub artifact digest and its reconstructed Git tree matched the authored commit. Local initial `npm test`: 327 passing executions plus two module-load errors (React absent); the full suite is not green locally. Global compiler is TypeScript 5.8.3, not locked 5.9.3. A bounded lockfile install attempt timed out without completion. Hosted pinned build remains required. These are environment failures, not the new red reproduction.

New receipt suite on unchanged runtime: 22 executed; 10 expected assertion failures, 12 passing controls. The eight import/assessment/withdrawal/report contradictory combinations and two draft-preservation cases reproduce the gap. Backend `prepare_json` already enforces the opposite mapping, and the separate metadata client already checks it. This is client response validation, not evidence that the genuine backend emits contradictory receipts or that source authority was bypassed.


## Hosted checkpoint and screenshot-driven correction

The current #348 parent advanced by documentation only to `d15aa208adcb13b3c0621cc44a384a8fa37affb3`; both published documentation files were retained unchanged and its ancestry joined without modifying the parent branch. Draft #359 was published at `fcbdff5b4368d3f61acfd267851b475b65f4655f`, tree `c3d69353b924deaf2d84bc4ab0a404c5ba5cabbf`.

Hosted run41679757003 completed successfully: 358 client checks, pinned production build, existing dependency gates and the full actual React/FastAPI/PostgreSQL journey. Artifact13252457052 SHA-256 `27d064d5bfb8f9d7acc63428f4a8311c8a4b1ec3e4335971c18009bd2b7173ea` matched; all412 source files and executable classifications matched local. Its actual committed assessment was delivered with a deliberately contradictory flag, then recovered with identical URL/body and original assessment ID, exactly one matching persisted comparison. All three downloaded report file/body hashes and original bytes were inspected. This is an injected delivery fault, not a genuinely contradictory backend response. No full API-unit or backup/restore rerun is claimed for this frontend child.

Screenshot inspection exposed inherited contradictory draft copy: it said "not saved as an assessment" beneath the unknown-outcome warning. The existing real-component rendering suite gained two tests using actual session transitions. Tests-first head `84c1e546d9ce58f93ec3642312124cd2167d73b7` and run41680616649 reproduced exactly those two failures, with358 other checks passing. Its downstream build/browser steps were skipped after failure, not counted as acceptance.

### Task 4 — truthful submission copy
Files: existing `apps/web/src/authored-evidence-panel.tsx`, existing `apps/web/tests/evidence-continuity-panel.test.mjs`.
- [x] Reproduce both saving/unknown copy failures through the existing pinned SSR test harness.
- [x] Show submission-in-progress or potentially-saved wording based on the actual write phase, rather than stale draft status. Preserve the same controls and memory-only lifetime.
- [ ] Run the unchanged full hosted client/build/browser gate on the final correction and inspect its new screenshot. Earlier success is not substituted for this final-head gate.

Self-review only. No independent review or production/clinical approval is claimed. No backend, schema, permission, dependency or workflow changed by either correction. The new rendering cases bring the total proposed addition to24 checks; their final passing result remains to be recorded.
