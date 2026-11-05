# Reviewed originals in the connected H1 workspace

## Goal and bounded design

Compose the existing reviewed text/PDF original workflow with the existing source-reading, question, evidence-report and follow-up workspace. This continues OI-006, OI-007, OI-009, OI-010 and OI-013 under `AGENTS.md`; it does not replace any canonical owner or establish a clinical release.

Pinned base: PR #335, `9d173843f924b40becba3a7dffd71717c12afb5d` (tree `57165fc8b1c6305336752eb948710a437eda9cf9`). Pinned donor: PR #323, `fcf8c984756b22ea536f4c8c8d287fd7afeed1ac` (tree `2a9872079c2b0bd7e18f6426296739ad70f0ad41`). Retain both commit ancestries and their migration history.

Use a separate native **Text and PDF originals** disclosure in Records, closed initially and keyed to the current patient/case. Its existing document workspace remains mounted when collapsed, so a selected file, frozen preview, manual selections and confirmation survive toggling. Keep the existing structured-record disclosure and source-reading controls. Opening or closing either disclosure must not issue a request or save a source.

Carry the donor's source-owned document tables, immutable original bytes, frozen line/physical-page anchors, append-only selection revisions, explicit save, fresh authorization and bounded downloads unchanged wherever the branches do not overlap. Preserve exact dependency versions, hashes and notices. Manual selections remain separately attributed and excluded from structured-source World Model observations and investigation snapshots. All input is independently authored fictional data.

## Implementation sequence

- [x] Inspect the pinned inputs, authority, existing owners and dependencies; isolate a new worktree.
- [x] Verify base client tests, build and dependency-rights gate: 300 passed, zero skipped; build and rights passed.
- [x] Add actual-browser assertions first and observe the missing disclosure on the unmodified product.
- [x] Compose the donor with the current main application and browser journey; add the small mounted disclosure.
- [ ] Verify client tests, build, rights, PostgreSQL API, reference implementation, connected browser and recovery on the published combined head.
- [ ] Complete independent review and inspect hosted screenshots and retained evidence.
- [ ] Update the existing continuity/backlog records and the draft PR with exact results and limits.

## Acceptance

1. Source reading remains visible with both import controls collapsed on a populated case.
2. Actual keyboard interaction opens/closes the document disclosure; hidden controls cannot satisfy the browser journey.
3. Collapse/reopen preserves the same selected File, preview, manual quotation and checked confirmation, without a request or persisted source.
4. Preview stays nonpersistent. Explicit save preserves the exact PDF, page-two anchors and immutable correction history; binary download matches original bytes.
5. Existing question, citation, report, amendment and follow-up acceptance runs in the same built application.
6. Case/patient changes, session reset and completed authorization denial clear scoped material; late responses cannot restore it.
7. Migration, hash-locked dependency review, database recovery and actual HTTP checks retain their exact scope. Document HTTP after API restart is distinct from HTTP against a restored database.

## Verification record

The final PR records the tests-first failure, immutable combined commit, run attempts, artifact identity, independent review, and unresolved limitations. Synthetic engineering results do not establish real-patient authorization, extraction quality on unfamiliar documents, scientific validity, professional review, or production readiness.

- Tests-first published commit `75365e8532267ac31c4103cea8f9eea3b4591d24`, [React run 41675233846](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41675233846), attempt 1, job 126053951348: 300 client tests, build and dependency gates passed; actual PG/API/Chromium failed specifically with `AssertionError: Reviewed originals start collapsed beside the structured import` before production composition.
- The inherited structured-intake denial test now waits for the completed denied response before later journeys restore grants. The document journey explicitly opens native details and checks visible controls, avoiding hidden programmatic-click false positives.
- A synthetic structured source and reviewed PDF share the same case. The browser compares the structured index before and after manual annotation correction; it must remain unchanged.
- Initial combined head `51cdc6fd6281d0361c371a25cb00cef0167b880f` passed [React run 41676109720](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41676109720), including the new PDF journey. Its artifact SHA-256 was verified and all 427 archived source files matched the commit; desktop collapsed controls and 390px document layout were inspected. This is an intermediate receipt, not a substitute for the corrected final head.
- Independent review exposed document denial retaining shared source content and a late original restoring after denial. Eight new regressions/controls in tests-only `a2e56de42dd26da45c266fc9f5ec8b84da4e2c17` produced six expected failures before the fix. Corrected local client suite: 315 passed, zero skipped. Final browser acceptance also requires whole-scope clearing and empty reauthorization.
- The inherited reference-UI parser-install YAML failed to parse; its block-scalar correction preserves the exact command. The final UI workflow must run successfully; a zero-job failed suite is not acceptance.
- Local reference suite: 304 passed. Document wire contracts: 4 passed. Exact-wheel rights gate: 25 packages, 13 embedded runtime components, 99 supplier native components, within the recorded synthetic-development scope; installation has no broken requirements.
- This source checklist is a pre-publication checkpoint. The final immutable head, all run attempts, independent review and completion of the remaining hosted/visual gates are maintained in PR #349's verification receipt without rewriting the tested source merely to add its own SHA.
