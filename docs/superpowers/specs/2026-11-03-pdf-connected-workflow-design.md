# Reviewed documents in the connected patient workflow

Continue the user-approved #221 workflow by integrating #215's existing ordinary-text/PDF intake and manual-source provenance. The target is one source → question → review → task → amended-source history, not a new patient/source/task system or a complete production product.

## Approach
Use #221 as the parent and reconcile #215 against the common main behavior reference. Preserve clinical/rights/task owners from #221 and original/rendition/manual-provenance owners from #215. Rename the colliding PDF intake asset to `document-intake.js` (its original JavaScript global is already distinct) while retaining the structured batch owner. Mount both supported input contracts in the same existing workspace, with shared mutation/draft guards. Do not combine #183's broad redesign or H1 migration in this increment: each changes a separate integration boundary and remains separately owned.

## Required behavior
- Ordinary UTF-8 text and bounded born-digital PDFs use #215's exact originals, immutable frozen renditions, explicit case/transcription confirmation and manual selected passages.
- Readable patient and governed evidence reports retain manual classification origin, original/extraction/page hashes and physical-page/extraction-line anchors. A user-selected status is not a source-authored fact or clinical approval.
- Source amendment marks dependent work stale, reopens questions and flags open tasks while preserving completed task/source/report history and exact original bytes across restart.
- Preview does not mutate case state; save invalidates reports/Composer before any write. Unsaved reviewed documents veto case/workspace changes. Late source/preview responses cannot revive old case state.
- Keep existing content-specific rights and report/read/export/review gates. No privileged clinical route is added.

## Constraints
Independently authored fictional data only. Existing optional pypdf 6.21.4 hash pin, notices and worker isolation only; no OCR, new parser/version, general PDF acceptance or real patient deployment. Unsupported parser/resource environment fails closed. Preserve existing source-owner tests. Draft publication only; do not merge or deploy.

## Acceptance
One combined tree passes the full Python and JavaScript suites, retained browser journeys and an extended original PDF journey proving page anchors, task history, report/download parity and amendment/restart. Negative cases include wrong patient, missing/forged provenance, revoked evidence rights, unknown save outcome and delayed responses. Report local limitations and failed runs without hiding them. Review is inline unless an independent reviewer is actually available; no invented review.
