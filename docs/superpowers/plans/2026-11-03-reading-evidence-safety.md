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
