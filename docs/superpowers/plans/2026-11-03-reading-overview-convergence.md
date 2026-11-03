# Reading and Overview Convergence Implementation Plan

> **For agentic workers:** Use the executing-plans workflow for the bounded implementation, with independently delegated browser acceptance and final review.

**Goal:** Connect patient preparation and exact-return recovery to the current source-reading workspace and make all navigation clear prepared source views consistently.

**Architecture:** Reuse the read-only Overview projection/component and existing session dismissals. Preserve every backend and session implementation file from #305; no new authority or state owner.

**Tech Stack:** Existing React 19.3.1, TypeScript 5.9.3 and Vite 7.3.7; existing FastAPI/PostgreSQL 16 browser verification.

**Spec:** `docs/superpowers/specs/2026-11-03-reading-overview-convergence.md`

## Global constraints

- Base #305 exact head `aea88341e260a4829d5b1647d5395b78ca17bfa6`.
- Frontend only; no backend, schema, API, permission, domain, session, workflow or dependency changes.
- Preserve existing patient/clinical reading as presentation, not authorization.
- Independently fictional input only; draft/unmerged/undeployed.

## Review focus

- Contextual and same-section navigation must invalidate late quotation/brief deliveries.
- Overview recovery must not expose a different patient/case or silently retry.
- Unknown question history cannot become a zero count or clinical assurance.
- Reading filters and unrelated question/task drafts survive local navigation.
- Responsive focus remains visible below the measured context header.

## Task 1: Reproduce the navigation gap

**Files:** existing `apps/web/tools/question_review_journey.py`; specification and this ledger.

- [x] Inspect exact #305 source; compare all 340 archived file blobs and tree.
- [x] Run inherited `npm test`: 216 passed, zero failures/skips.
- [ ] Add the existing #288 contextual round-trip assertions to the actual browser journey.
- [ ] Publish a test-only draft checkpoint; observe the intended failure before changing product code.

## Task 2: Reuse Overview and common navigation

**Files:** `apps/web/src/main.tsx`, `patient-continuity.ts`, `patient-continuity-view.tsx`, `styles.css`, `apps/web/tests/patient-continuity.test.mjs`, `apps/web/tsconfig.client.json`.

**Interfaces:** `PatientContinuity({state,onNavigate})`; `patientContinuity(state:ViewState)`; existing `navigate(section:string)` and existing session dismissals.

- [ ] Import #294's tested projection/component and inherited scope/recovery tests; adapt tests to a direct projection-module import.
- [ ] Centralize both dismissals before the same-section navigation return; remove rail duplication; preserve focus.
- [ ] Add the existing continuity styles and render Overview before session setup.
- [ ] Run complete client suite and TypeScript/Vite production build.

## Task 3: Verify the combined user workflow

**Files:** existing connected browser helpers, a scoped Overview helper, and `apps/web/tools/browser_journey.py` only as necessary to invoke acceptance.

- [ ] Preserve all inherited reading/follow-through assertions; test same-response filters and draft retention.
- [ ] Test Overview draft resume/counts; exact-return recovery after source refresh; no POST from navigation.
- [ ] Hold real quotation/brief responses across contextual navigation and verify late-response suppression.
- [ ] Run the actual combined hosted browser workflow; inspect screenshots and downloaded receipts.
- [ ] Obtain independent review, verify parent bytes/modes, record exact head/tree/results and remaining boundaries.

## Execution ledger

Initial scope decision: selectively compose existing frontend owners on #305, preserving its parent stack. This advances the supplied convergence brief without combining backend migrations or creating another patient/source master.

Local baseline is a snapshot commit with the exact #305 tree; published commits will use the actual #305 remote parent. The snapshot SHA is not represented as the upstream commit.

The managed environment status capability and network-policy file are unavailable in this session. Repository operations use the connected GitHub API; local builds use the existing pinned dependency directory. No direct blocked network route is attempted.
