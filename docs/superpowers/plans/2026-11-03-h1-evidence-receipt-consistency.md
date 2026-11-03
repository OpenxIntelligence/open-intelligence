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
- [ ] Reject only inconsistent status/duplicate pairs before clearing the draft or publishing success.
- [ ] Run all client tests; record missing dependencies separately from behavioral failures.

### Task 2 — actual browser delivery fault
File: `apps/web/tools/authored_evidence_journey.py`.
- [ ] Extend the existing observer to deliberately change only the duplicate bit on one real committed 201 assessment response. Retain actual server response separately and disclose the injected fault.
- [ ] Verify unknown status, retained/locked draft, identical request bodies, recovered original assessment ID, exactly one persisted effect, and normal later comparison/report work. Retain the original post-commit lost-response test.
- [ ] Run the unchanged hosted React/FastAPI/PostgreSQL gate on the published child; inspect archive and captures.

### Task 3 — verification and delivery
- [ ] Self-review full delta and confirm unchanged source-owner files; no independent review claim.
- [ ] Record exact source tree, tests, environment limitations and failed attempts.
- [ ] Publish as a draft child of #348 and leave main/parent untouched. Record evidence in the existing integration thread.

## Execution ledger
The #348 source archive digest matched its GitHub artifact digest and its reconstructed Git tree matched the authored commit. Local initial `npm test`: 327 passing executions plus two module-load errors (React absent); the full suite is not green locally. Global compiler is TypeScript 5.8.3, not locked 5.9.3. A bounded lockfile install attempt timed out without completion. Hosted pinned build remains required. These are environment failures, not the new red reproduction.

New receipt suite on unchanged runtime: 22 executed; 10 expected assertion failures, 12 passing controls. The eight import/assessment/withdrawal/report contradictory combinations and two draft-preservation cases reproduce the gap. Backend `prepare_json` already enforces the opposite mapping, and the separate metadata client already checks it. This is client response validation, not evidence that the genuine backend emits contradictory receipts or that source authority was bypassed.
