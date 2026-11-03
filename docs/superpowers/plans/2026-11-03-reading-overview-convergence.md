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
- [x] Run the actual combined hosted browser workflow; inspect screenshots and downloaded receipts.
- [x] Obtain independent review, verify parent bytes/modes, record exact head/tree/results and remaining boundaries.

## Execution ledger

Initial scope decision: selectively compose existing frontend owners on #305, preserving its parent stack. This advances the supplied convergence brief without combining backend migrations or creating another patient/source master.

Local baseline is a snapshot commit with the exact #305 tree; published commits will use the actual #305 remote parent. The snapshot SHA is not represented as the upstream commit.

The managed environment status capability and network-policy file are unavailable in this session. Repository operations use the connected GitHub API; local builds use the existing pinned dependency directory. No direct blocked network route is attempted.

RED evidence: hosted run [41655414937](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41655414937), test-only head `b5e406071697529e170f4ba5f51adf82d09f6ca6`, passed all 216 client checks and build, then failed the unchanged contextual round-trip assertion: `Contextual navigation must invalidate the prepared source packet`. The error occurs after returning to the mounted Questions panel through the in-page Review button. Product files match #305.

Independent projection review found a real downstream case mismatch: older source metadata for BETA can outlive a failed ALPHA World Model refresh while retaining ALPHA's uncertain return. The imported projection now follows the unchanged Review panel's case precedence before advertising recovery. The actual RegistrySession regression failed on the donor implementation (227/228 passed), then passed with the bounded projection guard (228/228 passed). Same-case metadata refresh restores the link and an explicit retry preserves the original body/key. RegistrySession and ReviewPanel remain unchanged.

Reassessment copy now states that source context needs reassessment rather than asserting that source bytes changed; legacy snapshot contracts can require reassessment without changed bytes. This is a presentation clarification, without count or status changes.

Local client verification: 228 tests passed, zero failures/skips. The initial 216-test parent and first imported 227-test runs also passed; counts are nested executions, not separate capabilities.

Independent whole-delta review of the complete implementation and browser probes found no Critical, Important or Minor findings. Review verified frontend-only scope and unchanged source-reading/follow-through helpers. All four modified/new Python browser helpers compile; whitespace checks pass.

GREEN evidence: hosted run [41657360248](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41657360248) passed on runtime head `f18876efe3609bd701857ef341ba0a5dfe005342`, tree `e8cc3c86cb3624114fc71da9dbc727a3033b0326`. This includes all 228 client tests, the TypeScript/Vite build, dependency gates, and the actual PostgreSQL/FastAPI/built-React browser journey. The new checks passed together with the inherited source reading, actual brief download, question review, follow-through, source amendment, permission withdrawal and session/case-boundary checks.

Downloaded artifact `13240901200` matches GitHub's SHA-256 `a7add36f1f0f9f040d6a0e26e23ffdb08866d2fa0bc1e36764bae3f1d9966a72`. Its commit marker identifies the runtime head, and all 346 archived source blobs and executable modes match the local runtime tree. Relative to #305, 333 of 340 existing files remain identical; the seven changed existing files are frontend source, frontend test/config or browser acceptance files. All protected owners remain identical.

Visual inspection covered Overview recovery at 320, 390 and 1440 pixels, patient reading at 320, clinical reading at 390, follow-through attention at 390, and the connected-question desktop view. The recovery action, visible focus ring and text remain contained. Independent receipt inspection confirmed exact 201-to-200 duplicate recovery with one durable receipt and zero navigation requests, both late-response suppression scenarios, and hashes/lengths of all four actual downloaded briefs. No blocking receipt gap was found.

The documentation closeout adds a bounded OI-010 evidence reference without declaring the full investigation workflow complete. See [the verification report](../../ux/2026-11-03-reading-overview-verification.md) and its compact JSON receipt. PR #308 remains a draft stacked on #305; no merge, deployment or clinical validation is claimed.
