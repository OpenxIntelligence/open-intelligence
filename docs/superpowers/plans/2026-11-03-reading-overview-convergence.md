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
- [x] Add the existing #288 contextual round-trip assertions to the actual browser journey.
- [x] Publish a test-only draft checkpoint; observe the intended failure before changing product code.

## Task 2: Reuse Overview and common navigation

**Files:** `apps/web/src/main.tsx`, `patient-continuity.ts`, `patient-continuity-view.tsx`, `styles.css`, `apps/web/tests/patient-continuity.test.mjs`, `apps/web/tsconfig.client.json`.

**Interfaces:** `PatientContinuity({state,onNavigate})`; `patientContinuity(state:ViewState)`; existing `navigate(section:string)` and existing session dismissals.

- [x] Import #294's tested projection/component and inherited scope/recovery tests; adapt tests to a direct projection-module import.
- [x] Centralize both dismissals before the same-section navigation return; remove rail duplication; preserve focus.
- [x] Add the existing continuity styles and render Overview before session setup.
- [x] Run complete client suite and TypeScript/Vite production build.

## Task 3: Verify the combined user workflow

**Files:** existing connected browser helpers, a scoped Overview helper, and `apps/web/tools/browser_journey.py` only as necessary to invoke acceptance.

- [x] Preserve all inherited reading/follow-through assertions; test same-response filters and draft retention.
- [x] Test Overview draft resume/counts; exact-return recovery after source refresh; no POST from navigation.
- [x] Hold real quotation/brief responses across contextual navigation and verify late-response suppression.
- [ ] Run the actual combined hosted browser workflow; inspect screenshots and downloaded receipts.
- [ ] Obtain independent review, verify parent bytes/modes, record exact head/tree/results and remaining boundaries.

## Execution ledger

Initial scope decision: selectively compose existing frontend owners on #305, preserving its parent stack. This advances the supplied convergence brief without combining backend migrations or creating another patient/source master.

Local baseline is a snapshot commit with the exact #305 tree; published commits will use the actual #305 remote parent. The snapshot SHA is not represented as the upstream commit.

The managed environment status capability and network-policy file are unavailable in this session. Repository operations use the connected GitHub API; local builds use the existing pinned dependency directory. No direct blocked network route is attempted.

RED evidence: hosted run [41655414937](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41655414937), test-only head `b5e406071697529e170f4ba5f51adf82d09f6ca6`, passed all 216 client checks and build, then failed the unchanged contextual round-trip assertion: `Contextual navigation must invalidate the prepared source packet`. The error occurs after returning to the mounted Questions panel through the in-page Review button. Product files match #305.

Independent projection review found a real downstream case mismatch: older source metadata for BETA can outlive a failed ALPHA World Model refresh while retaining ALPHA's uncertain return. The imported projection now follows the unchanged Review panel's case precedence before advertising recovery. The actual RegistrySession regression failed on the donor implementation (227/228 passed), then passed with the bounded projection guard (228/228 passed). Same-case metadata refresh restores the link and an explicit retry preserves the original body/key. RegistrySession and ReviewPanel remain unchanged.

Reassessment copy now states that source context needs reassessment rather than asserting that source bytes changed; legacy snapshot contracts can require reassessment without changed bytes. This is a presentation clarification, without count or status changes.

Local client verification: 228 tests passed, zero failures/skips. The initial 216-test parent and first imported 227-test runs also passed; counts are nested executions, not separate capabilities.

Independent whole-delta review of the complete implementation and browser probes found no Critical, Important or Minor findings. Review verified frontend-only scope and unchanged source-reading/follow-through helpers. Runtime browser results remain pending at this checkpoint. All four modified/new Python browser helpers compile; whitespace checks pass.
