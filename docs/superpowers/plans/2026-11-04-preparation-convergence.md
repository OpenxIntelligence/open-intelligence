# Preparation in the combined H1 workspace implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task, with one final independent source review.

**Goal:** Make the existing second-opinion preparation agenda available alongside the combined H1 document, image and manual-passage workspace.

**Architecture:** Reuse #408's read-only projection over the existing patient, case, question and follow-through reads. Preserve #413's newer source/image, FHIR preview, report and session owners. No second ledger, permission or write path.

**Tech Stack:** Existing pinned React/TypeScript/Vite and FastAPI/PostgreSQL 16; no dependency change; Next.js excluded.

**Spec:** `docs/FIRST_PRINCIPLES_PLAN.md`, especially the shared brief, scoped authority and second-time-point requirements; backlog OI-007/009/010/013. Donor #408 describes the existing preparation scope.

## Global constraints

- Independently fictional fixtures only; no clinical approval or real-data activation.
- Base #413: `e3259bb2986206e4a7edf8bc3a29546471077beb`, tree `305dbbc98ab90711dbf1553c264c17bc89d22653`.
- Donor #408: `07cd593430d837dac5e097d15487ce99ac2c4108`; donor baseline #398: `a85d30f5563d763507c64d91ec3c70100b446fc3`.
- Retain exact source/question/task provenance, unknown-vs-empty, separate grants, literal saved text and uncertain-command recovery.
- Keep backend, migrations, dependency manifests, permissions and workflows byte-identical to the base.
- Draft only; this work does not merge or deploy either parent.

## Review focus

- A question may be readable while its task history is denied: show question, withhold task counts and owners.
- Manual passages may be corrected while the primary source stays current: require a separate passage/report freshness check.
- Unsent task fields must survive same-case navigation but never appear as recorded preparation work.
- A late response after case or authority changes must not restore another context's data or cleared draft.
- Preparation navigation during a lost passage-save response must retain the exact recovery command without adding task writes.

## Task 1: Compose and verify the existing preparation behavior

**Files:** `apps/web/src/main.tsx`, `styles.css`, new `second-opinion-{preparation.ts,preparation-view.tsx,agenda.css}`; existing follow-through client/browser tests; new second-opinion tests; `tsconfig.client.json`; this plan, preparation evidence and backlog.

**Interfaces:** Consume `RegistrySession.snapshot(): ViewState` and `patientContinuity(state)`. Reuse `secondOpinionPreparation(state)` and `SecondOpinionPreparation({state,onNavigate})`; navigation reuses existing routes and creates no requests or referrals.

- [x] Compare exact source trees before composing. Parent artifact SHA-256 and all 646 Git blobs/modes verified.
- [x] Preserve current A/B/A case-switch assertions and image reader CSS; add donor preparation assertions. The current RegistrySession already contains the donor's draft protections; do not replace it.
- [x] Run the tests-first browser journey on the unchanged UI: expect missing preparation agenda.
- [x] Add the existing projection, view and styles, preserve current main rendering, and add donor client tests and compiler entrypoint.
- [ ] Run focused session/projection tests; full hosted client/rights/build/actual PostgreSQL-FastAPI-Chromium gate. Parent results do not qualify this composition.
- [ ] Independent whole-change review, resolve material findings, inspect retained source identity and receipts.
- [ ] Record exact source/run identities, limitations and scoped acceptance in PR and canonical progress records.

## Execution record

Pre-flight: one task, shared existing ViewState interface; no new producer/consumer contract.

Ruling: retain #413's final case-switch sequence, which checks empty case B then restored case A with four tasks; do not substitute #408's older sequence. This preserves the newer parent acceptance and its correct active-case counts.

Ruling: do not replace historical engineering logs or the execution backlog with donor copies. Add one current bounded record so unrelated accepted work remains intact.

Local full `npm test` is blocked because the pinned TypeScript toolchain is not installed in this fresh checkout. Node TypeScript transformation can run focused behavior checks but is not typechecking or build evidence; hosted verification remains required.

Tests-first hosted run 41827963055 at `6db0214f9909c4ec1c157d4a88fdf5bcf22cd4c9`: 483 client tests, 13 rights controls and production build passed. The actual browser failed with `Timed out waiting for saved preparation question`, confirming the missing view. No assertions were weakened.
