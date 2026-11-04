# Connected reading and evidence safety implementation plan

**Goal:** Carry the already verified citation-history and report-download corrections into the connected source-reading workspace.

**Architecture:** Preserve #319's canonical React/FastAPI/PostgreSQL application and all patient, source, question, evidence, review and follow-through owners. Selectively reuse six exact source/test files from #315 and #316; no migrations, dependency changes, new authority or clinical functions.

**Spec:** Existing `docs/FIRST_PRINCIPLES_PLAN.md` second-time-point/export invariants and OI-009/OI-010/OI-013. This continues the user's existing instruction to proceed with integration.

## Source pins

- Base #319: `2475d924fddef6792076bdf9039fad5be7312b7a` (hosted source archive).
- Citation contracts #315: `58bc5f7bc5b8c5ba39e4d93768031aa22cedacd9`.
- Report download #316: `66f44d42b8d47a1b6e8da0bb82f968de8de311dc`.

## Tasks

1. Establish the complete #319 source baseline in an isolated checkout; run its existing client tests.
2. Copy the two original donor test files first: `apps/api/tests/test_question_evidence_contracts.py` and `apps/web/tests/evidence-report-download.test.mjs`. Reproduce missing rejection/cover behavior without changing donor assertions.
3. Copy `apps/api/src/oi_api/evidence_contracts.py`, `apps/web/src/authored-evidence.ts` and #316's two browser helpers `authored_evidence_journey.py`/`evidence_continuity_journey.py`. Verify byte-for-byte donor SHA equality, narrow diff and unchanged UI/navigation/schema/permission owners.
4. Run complete client tests, TypeScript/Vite build and applicable local contract checks. Publish an isolated draft child of #319 and run unchanged hosted API/PostgreSQL/recovery and React/Chromium workflows against the exact combined head.
5. Independently review the delta; inspect actual workflow logs and artifacts. Record actual results in the PR and durable acceptance record. Keep prior failures and limits visible.

## Review focus

- Historical report downloads retain fresh reassessment status and exact original Unicode body/hash.
- Revoked/withheld export and changed patient context create no downloadable content.
- Invalid calendar/control-character citation timestamps fail during complete response preparation; valid original offset strings are preserved.
- Reading filters, collapsed import, draft preservation, exact source-to-question handoff, citation/report/task continuity and revocation continue through the built browser.
- Parent and donor branches remain unchanged. No merge, deployment, real data, model execution or professional approval is authorized by this engineering slice.

## Execution record

- Baseline: 274/274 client tests passed, zero skips.
- Local runtime lacks FastAPI/PostgreSQL dependencies; full HTTP/database evidence must come from hosted acceptance. A local standalone model probe is not a database pass.
- Decision: reuse corrected source owners unchanged instead of reimplementing their behavior. Preserve original architecture and separately attribute donor and combined-head evidence.

- Red: donor download tests ran on #319 behavior: 276 passes and exactly two missing-cover failures (278 total). A standalone model probe reproduced acceptance of `+05:99`. The complete donor API contract suite could not run locally because FastAPI/SQLAlchemy/PostgreSQL are absent.
- Green: all 278 client tests passed, zero failures/skips; pinned TypeScript 5.9.3 and Vite 7.3.7 production build passed. Five standalone timestamp checks and Python compilation passed. Local Pydantic is 2.14.1; this is not a pinned backend/HTTP/database pass.
- Source fidelity: all six reused files have exactly the original donor blob hashes. Existing main UI, session, reading component, database/migrations, grants, dependencies and workflows are byte-identical to #319.
- Hosted acceptance and independent review: pending at initial publication; record each exact-head outcome in the PR before completion.

## Verification continuation after two Chrome startup failures

The initial runtime `ca3bb8f201bb2dff386896f6a667c8390dfcc65d` passed its full React/PG16/Chromium workflow (41665786603), 278 clients, and artifact checks: 405 source files and three actual report downloads. Independent automated review found no blocking finding. API workflow 41665786647 attempts 1 and 2 each passed 416 PostgreSQL/API tests and 287 reference tests, then failed before the inherited Chrome DevTools endpoint became available. No recovery probe ran in either attempt. No application assertion failed, but the full API workflow was not successful.

Bounded scope extension: reuse all four unchanged files from diagnostic owner #317 `cc10d8cb229f0eb3552362cc75ca27ed8ee4962c`. Capture bounded escaped Chrome stderr and process exit status without changing sandbox settings, flags, 12-second deadline, browser assertions or cleanup. The four original subprocess/loopback tests first reproduced the missing helper in this checkout. This is instrumentation, not a claim to fix the unknown launch cause. Rerun the independent hosted checks on the resulting exact head and retain all failed attempts.

Concurrent #322 contains the same six original donor blobs on #318, while this candidate retains #319's import disclosure. These are overlapping candidates requiring one source-owner integration decision, not separate fixes to merge blindly. #328 attention and #330 client calendar validation remain separately owned and outside this runtime.
