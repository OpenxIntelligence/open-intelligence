# Typed Question-Anchor Foundation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans; execute inline with TDD.

**Goal:** Establish strict shared source identity without changing existing wire
contracts or enabling an unqualified laboratory write.
**Architecture:** A pure immutable typed anchor contract is shared by Composer,
saved-question projection and follow-through integrity checks. Existing owners,
transactions and source custody remain authoritative.
**Tech Stack:** Existing Python/Pydantic/FastAPI; no new dependencies.
**Spec:** `docs/superpowers/specs/2026-11-05-question-anchor-foundation.md`.

## Global constraints
Synthetic inputs only. No migration, new route/grant, deployment or remote write
without a fresh branch read. Keep legacy hashes/payloads and published history.

## Review focus
Boolean-vs-integer identity; mixed text/FHIR anchors; scope/ref mismatch;
mutability/aliasing; preserving historical snapshots and request fingerprints.

## Task 1 — Strict contract and explicit adapters
Files: create `apps/api/src/oi_api/question_anchors.py` and
`apps/api/tests/test_question_anchors.py`.
- [x] Freeze representative baseline payloads/hashes before production edits.
- [x] Add failing tests for strict scoped text/FHIR variants, immutability,
  mixed/unknown fields, malformed references and missing required values.
- [x] Implement `parse_question_anchor(value: dict) -> QuestionSourceAnchor`,
  `anchor_from_preflight(prepared: dict) -> QuestionSourceAnchor` and
  `legacy_text_question_anchor(row: dict) -> TextLineQuestionAnchor`.
- [x] Run focused tests; inspect failures and confirm green after implementation.

## Task 2 — Integrate existing owners without wire changes
Files: `composer_preflight.py`, `source_questions.py`,
`question_followthrough.py`; tests `test_question_anchor_integration.py`.
- [x] Prove malformed legacy bool/float/string anchor values are wrongly accepted
  or not rejected by the baseline, using actual pure owner methods.
- [x] Validate Composer's selected identity before hashing the unchanged payload;
  validate saved-question and follow-through text identities before comparison.
- [x] Compare complete canonical JSON against baseline fixtures, including old
  intent/preflight hashes, current/stale question history and task output.
- [x] Run focused existing tests, full available API/reference commands,
  syntax/diff checks and record actual failures/skips/timeouts, not inferred passes.

## Task 3 — Evidence and project handoff
- [x] Self-review and recheck invariant coverage. Independent review remains open.
- [ ] Attempt existing GitHub/Notion/Drive read/update; do not overwrite unseen work.
- [ ] Provide a patch, tests, exact baseline/change identity, complete logs and
  open persistence/recovery gates. Do not describe local work as pushed.

## Execution receipt — publication checkpoint

- Baseline reconstructed from the verified PR #503 artifact: all 670 source files
  produce Git tree `fe8b6ef291a600f905a2207818094c94ca21c4f4`. Local reconstruction
  commit is not remote ancestry; the published child must name real parent
  `fcaf207d46b6fb99e735b0a417a5e2b552bcfa7e`.
- Baseline focused suite: 45 passed. Tests first: 24 new tests produced 34 expected
  assertion/subtest failures before implementation. After implementation, self-review found a duplicated saved-question list
  projection bypassing validation. A new regression reproduced four subtest
  failures. Listing now reuses the same validated projection as brief preparation.
  Final result: 25 new tests pass; combined focused suite 70 passed, zero
  failures/errors/skips.
- All 13 full canonical-JSON compatibility cases match the frozen parent outputs.
  They were independently regenerated against a clean baseline runtime after the
  change. Fixture SHA-256: `430b325cdf7e9a5746739b3777f521e361f68f0194a464c00c8e3dca100c0ec2`.
- Full local API: 294 entries, 66 missing-pydicom errors and 27 database skips.
  Clean baseline: 269 entries, exactly the same named errors/skips. Neither is a
  passing full suite. No dependency pin, permission or assertion was relaxed.
- Full original reference command attempted and interrupted by the execution
  environment before its terminal summary. It is incomplete, not passing.
- Changed Python files compile; whitespace checks pass. Self-review confirmed
  strict mixed-kind/type rejection and unchanged valid wire/hash history. There
  is no independent review or new PostgreSQL/recovery/browser acceptance here.
- GitHub access recovered after initial 502 errors. Fresh PR #503 lookup confirmed
  unchanged head; targeted open-PR search found no newer implementation of this
  anchor foundation. Publishing a separate draft leaves the verified parent intact.

### Next owner boundary

Do not enable laboratory question saves by loosening the current `source_line`
foreign keys. Review a new additive migration across the existing question and
follow-through owners, retain legacy hashes, implement typed save/read/revalidation
and downstream report/review paths, then prove populated upgrade, exact retry,
wrong scope/specimen, late revocation, amendment, restart/restore and actual UI
behavior. This foundation does not close #428/#425 or authorize clinical use.
