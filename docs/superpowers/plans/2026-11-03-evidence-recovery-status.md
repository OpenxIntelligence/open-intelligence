# Truthful comparison recovery status continuation

> For agentic workers: use superpowers:executing-plans for this bounded continuation.

**Goal:** Keep retained comparison status truthful while any evidence action is pending, preserve both contradictory-receipt/chronology regression paths, and retain the existing patient-journey capability crosswalk.

**Architecture:** Extend the existing #363 convergence instead of publishing a second #355/#359 composition. Use the existing evidence panel, session and recovery controls. No new state owner, dependency, backend, schema, grant or workflow.

**Base:** #363 `ecadf0d45871e6581d65fa542390f2959ab26394`, tree `f73caaca42a5fe1728e852764851a3564bbe065a`. Its actual ancestry already includes #355 and #359/#348. The local snapshot reproduces all 419 blobs and modes; its local commit identity is not the upstream identity.

## Reconciliation and review

The original continuation was implemented against #355 and independently reviewed. A live audit then found #363 already published the same runtime integration. All 163 production/backend/workflow files in that tree exactly match the reviewed candidate. Keep #363's existing tests and historical records, and publish only the remaining additive delta on a new branch targeting #363.

The independent review found no Critical or Important defect and one Minor copy defect: an unrelated import with an unknown result caused a retained comparison to say it might already have been saved. Accept the correction because truthful save state is central to this task. Use wording about the pending evidence submission; the adjacent save status already identifies the exact action and question. Avoid introducing a second matcher for draft and intent identity. Locking, receipt verification and exact retry remain unchanged.

## Task 1: Complete the bounded delta

**Files:** `apps/web/src/authored-evidence-panel.tsx`, `apps/web/tests/evidence-continuity-panel.test.mjs`, new `apps/web/tests/evidence-recovery-chronology.test.mjs`, the existing evidence-continuity ledger, and the exact #360 patient-journey crosswalk.

- [x] Reconcile the complete #363 tree and confirm production equivalence to the reviewed integration.
- [x] Reproduce the inaccurate draft message using the real session, an unrelated lost import response, and the rendered composed panel.
- [x] Correct the pending/unknown message without changing save, disclosure or retry behavior.
- [x] Retain the two combined regressions for contradictory 201/200 receipts, invalid assessment chronology, exact retry and report access after a valid refresh.
- [x] Preserve `docs/research/PATIENT_JOURNEY_CAPABILITY_CROSSWALK_2026-11-03.md` byte-for-byte from #360 `f200dd107871d89703267ee0d1a14b2d1ca64d36`.
- [x] Run the complete compiled client suite, dependency gate, production build and protected-file comparison.
- [ ] Publish an isolated draft targeting #363; inspect the exact-head hosted PostgreSQL/FastAPI/built-React/Chromium journey and record its receipt in the PR body.

## Boundaries

Preserve existing branches and all #363 backend, migration, package/lock, chronology, dependency-gate and browser-journey code. Independently authored fictional inputs only. No merge, deployment, external messages or clinical approval. The hosted web journey is separate from standalone full API or backup/restore acceptance. Ancestor run results do not substitute for the new head's acceptance.

## Local checkpoint

The rendered import regression fails on exact #363 code with the inaccurate comparison-save claim; the other four rendered controls pass. With the two-line wording correction, all 375 compiled client tests and 13 filesystem dependency-gate tests pass, zero failures/skips/cancellations. The installed gate inspects 18 artifacts, explicitly leaves two optional artifacts uninspected, and reports no errors. TypeScript/Vite production build passes. The full base-to-candidate change is limited to the six paths above, including this plan. Exact-head hosted acceptance remains pending publication; record the actual result in the draft PR without a follow-up documentation-only source commit.
