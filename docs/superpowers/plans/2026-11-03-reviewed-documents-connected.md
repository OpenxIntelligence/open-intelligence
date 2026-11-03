# Reviewed originals in the connected H1 workspace

## Goal and bounded design

Compose the existing reviewed text/PDF original workflow with the existing source-reading, question, evidence-report and follow-up workspace. This continues OI-006, OI-007, OI-009, OI-010 and OI-013 under `AGENTS.md`; it does not replace any canonical owner or establish a clinical release.

Pinned base: PR #335, `9d173843f924b40becba3a7dffd71717c12afb5d` (tree `57165fc8b1c6305336752eb948710a437eda9cf9`). Pinned donor: PR #323, `fcf8c984756b22ea536f4c8c8d287fd7afeed1ac` (tree `2a9872079c2b0bd7e18f6426296739ad70f0ad41`). Retain both commit ancestries and their migration history.

Use a separate native **Text and PDF originals** disclosure in Records, closed initially and keyed to the current patient/case. Its existing document workspace remains mounted when collapsed, so a selected file, frozen preview, manual selections and confirmation survive toggling. Keep the existing structured-record disclosure and source-reading controls. Opening or closing either disclosure must not issue a request or save a source.

Carry the donor's source-owned document tables, immutable original bytes, frozen line/physical-page anchors, append-only selection revisions, explicit save, fresh authorization and bounded downloads unchanged wherever the branches do not overlap. Preserve exact dependency versions, hashes and notices. Manual selections remain separately attributed and excluded from structured-source World Model observations and investigation snapshots. All input is independently authored fictional data.

## Implementation sequence

- [x] Inspect the pinned inputs, authority, existing owners and dependencies; isolate a new worktree.
- [x] Verify base client tests, build and dependency-rights gate: 300 passed, zero skipped; build and rights passed.
- [ ] Add actual-browser assertions first and observe the missing disclosure on the unmodified product.
- [ ] Compose the donor with the current main application and browser journey; add the small mounted disclosure.
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
