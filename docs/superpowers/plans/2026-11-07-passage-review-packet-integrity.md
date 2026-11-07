# Passage review preparation integrity implementation plan

> Execute inline with test-driven development; preserve the existing canonical owners.

**Goal:** Verify the exact content and original-selection identity of a passage review-preparation packet before displaying it or constructing a later Review-return.

**Spec:** `AGENTS.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, existing `oi.pg-passage-review-preparation/1` contract in `question_evidence.py`, and PR #645. OI-007/OI-009/OI-013.

**Architecture:** Keep the existing Python/FastAPI/PostgreSQL and React/Vite/TypeScript owners. The client must recompute the server's existing SHA-256 contract (sorted compact JSON with Python's default ASCII escaping, excluding only the fresh source-access receipt and the digest itself), compare every original-selection field with the already verified saved passage, and keep asynchronous verification inside the existing generation fence. A matching hash is not authorization or a signature.

**Global constraints:** Independently fictional data only; no new dependency, permission, API, schema or clinical function; no merge/deployment. Preserve original text, user choice, current/historical state and rights redaction.

## Ruling and owner reconciliation

The previous candidate `27f5928cb27c7af3676fdf32bddc22517f6d1467` passed frontend run 42348691207 and API/recovery run 42348691121 (including seven recovery stages). Source inspection identifies an untested prerequisite: the packet decoder checks only the digest's format and selected quote/line/revision, not its actual digest or complete original identity.

#580 at `b18d54e25c5a50f9d47f0a15ebac4677698164f3` owns optional manual context attached to structured-question Review receipts, with its own `0019_review_manual_dependency` history. #587 at `35808cb455962682e252f58013e977f6c930c334` owns laboratory-inspection Review returns and changes the shared receipt provenance constraint and insert guards in `0026_laboratory_review_returns`. #645 has `0019_reviewed_questions` and `0020_passage_citations`. These are different anchors, not interchangeable receipt implementations. Do not invent a competing receipt table or silently reuse a migration number. Close the packet-integrity prerequisite before adding a write based on its identity. Shared migration composition and Review-return implementation remain next work, not delivered here.

## Task 1 — verified decoder and UI binding

- [x] Reproduce rejection failures against unchanged decoder: valid-looking wrong digest, changed metadata, rehashed page/original/version/reviewer fields, coerced enums and stale-to-current promotion.
- [x] Add positive independent Python-compatible hash fixtures including accented, Arabic and supplementary Unicode and fresh receipt churn.
- [x] Make the decoder asynchronous, verify actual packet content, require the full previously verified selection, reject non-string enums, and return a frozen defensive copy.
- [x] Thread the verified selection through saved-question state and await validation before the generation check.
- [x] Run focused regressions and the full client command; record environmental failures separately.

## Task 2 — connected browser proof and publication

- [x] Extend the existing fictional PDF browser journey: corrupted digest and rehashed source substitution clear the old preparation; unchanged authorized reread restores it.
- [x] Add a browser scenario holding actual hashing, changing local intent, and requiring late verification not to restore obsolete display.
- [ ] Compile Python harness, check diff, review all changed code and publish only a guarded candidate branch/PR.
- [ ] Inspect exact-head hosted build/browser/demo results and record API/recovery status without inheriting older results.

## Review focus

Unicode escaping must match the existing server rather than change it. A correctly rehashed substituted original still fails source binding. Known historical selections cannot be promoted. New rights redaction may remove metadata without losing immutable citation identity. Promise completion after context invalidation must not restore display.

## Baseline

Unchanged local client command: 597 passed; six React-dependent files fail module loading because the pinned React packages are absent. Local TypeScript is 5.8.3, not pinned 5.9.3. No missing dependencies or tests are bypassed; hosted pinned execution remains required. Source restored from artifact 13564618093 with verified SHA-256 `19ca5488ef74e2d47628450e394a94a0e3f3966b2170497b9352ddd273d9e12e`. Container is isolated; local snapshot Git history is not upstream history.

## Executed local evidence

Twenty of the initial 23 independent decoder cases failed against the unchanged implementation; three passed. After correction and two asynchronous boundary cases, all 25 new cases passed. The combined focused decoder/evidence/passage command passed 43 tests, zero failures/skips. Full `npm test` ran 622 passing tests and the same six baseline missing-React module errors: evidence-continuity-panel, laboratory-world-panel, patient-continuity-panel, question-evidence-panel, second-opinion-agenda-panel and source-images-panel. This is not a full local suite pass. Python compilation and `git diff --check` passed. The connected browser checks are authored, not locally executed; pinned hosted verification remains required. No independent reviewer approval is claimed.
