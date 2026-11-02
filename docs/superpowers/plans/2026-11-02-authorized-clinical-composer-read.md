# Authorized first-party clinical context → native Composer: integration plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prove that first-party canonical patient/EHR/LIS clinical context can be surfaced alongside source-bound native Composer, *only* through the existing reviewed patient–case and actor-purpose authority gates, with original evidence and review states intact.

**Base and scope:** Isolated exact head `d863bc2dc24dcf0a0b70972594768ebe19cd1d67` of existing first-party clinical continuity PR #95; add exact read-only `composer.py` source from #126, not a new Composer implementation. Existing registry, EHR notes, LIS, source ledger, evidence and domain outbox remain the sole owners; no second EHR, source store, UI, model runner or Next.js.

## Task 1 — Fail-first actual domain tests
- Add `tests/test_clinical_composer_authority.py` using existing `test_clinical_continuity.py` synthetic fixture and real SQLite EHR/source/LIS/registry/receiver, not fake assertions.
- Test valid authorization exposes exact case/question/source and pending clinical review without claiming clinical sign-off.
- Test wrong patient/case, denied actor/purpose, revoked case mapping, late conflicting source-adapter identity, and mid-read revocation fail closed.
- Test source change during Composer assembly refuses mixing old clinical snapshot and new source fingerprint.
- Verify tests fail without the module; keep CI red receipt.

## Task 2 — Add only one protected read adapter
- Add original `src/open_intelligence/composer.py` unchanged, from PR #126 source blob `b4dd9e9f22a1e475fb138848ddc6e15451098099`.
- Add `src/open_intelligence/clinical_composer_context.py`. `AuthorizedClinicalComposer(view: ClinicalContinuityView, store: LinkedLabCaseStore)`, `snapshot(patient_id,case_id,question_id,*,actor,purpose)`. Reject mismatched store/DB.
- First call existing `view.snapshot` to check actor/purpose/verified synthetic association, then source-bound `build_composer_context`, then re-check `view.snapshot` and Composer fingerprint *before response*. If either clinical reference view changed, caller lost authority, or evidence became stale, fail closed; do not mutate clinical state.
- Return a minimal sourced combined read projection, retaining explicit `review_pending` / `not_established`, original document/hash/line, and `not_a_distributed_atomic_snapshot`. Do not label patient identity or provider as truly verified.
- No new HTTP route, clinical order, provider call, model run, signed authority or PHI.

## Task 3 — Verify and coordinate
- Run full hosted unit/HTTP and browser CI at exact code SHA; inspect warnings and new actual-domain tests, preserve provenance to upstream #95 and #126. No automatic merge.
- Document review/merge dependencies and remaining work: trusted IdP/consent, two-DB consistency, authority on execution (not only read), approved commercial rights, real EHR interoperability, and medical validation.
- Existing Notion and Drive owners get a scoped implementation receipt after confirmed CI.
