# PDF annotation revisions through governed reports

Date: 2 November 2026 America/New_York (3 November UTC).

## Intent and existing authority

Continue the supplied #235 handoff by composing #229's saved-passage corrections into the existing patient/source/evidence/report/review owners. The patient can correct a selection, inspect what changed, and explicitly prepare a new report without changing an earlier report or note's cited basis. This is bounded continuation under the existing platform mandate, not a new architecture selection.

Base #235: `4f96b835f1306e0f92b803cd20ca6e46e2180216`, tree `34af78b0794e65c37ef5a06ab56bfa8c81467c64`. Annotation owner #229: `abbe3bf981ac0583f59eab45d853edd7b01a6aa6`, tree `3c996392cf584a0bcb5bee7682b8295e4b110a60`. Shared source ancestor #215: `3be1106b5cd34523c4746e2df6f123048beb5659`, tree `b03dc8a5d14f2bf7ca4c99a4c8b72491812015ee`.

## Approach

Compose the two source owners, retain #235's shared provenance validator and report receipt transaction, and move #229's revision checks into that validator. Reimplementing annotation history would duplicate the source authority; exposing a new H1 report transport now would combine a separate authorization migration with this source-identity task. Neither is needed here. This implementation choice follows the handoff's named next dependency.

## Required behavior

- Manual source/assertion/context/report references carry `annotation_revision_id`, `annotation_revision`, `initial_transcription_review_sha256`, and the effective `transcription_review_sha256`, in addition to existing original and PDF extraction/page provenance.
- Revision IDs and numbers are positive signed 64-bit integers, never booleans; hashes and source/receipt associations are checked. A return to an earlier selection is a new revision even if its text and review hash recur.
- Manual comparison proposals and selected evidence quotations must identify their captured annotation revision. An old assertion integer is insufficient because the current assertion projection can reuse IDs after a correction. Authored-source inputs keep their existing shape.
- The existing review receipt transaction reconstructs the actual current reference under its write lock. Missing, altered, stale, malformed or extraneous fields produce no receipt/event. A concurrent correction cannot rebind prepared work.
- Readable reports preserve original attribution and explicitly distinguish initial transcription confirmation, effective selection revision and clinical review not performed.
- Clinical note source links capture their annotation revision. Later changes/removal retain the captured passage, mark the link for review and never silently transfer it to the current selection. Legacy manual links with no captured revision remain visible and explicitly unbound/review-required; no historical annotation is invented.
- Earlier snapshot exports, original bytes, intake receipts and stored review events remain recoverable after corrections and restart. Existing content-specific rights, patient/case isolation, final authority rechecks and source amendment behavior remain enforced.

## Constraints and exclusions

Use independently authored fictional records and evidence only. No live medical model, patient record, patient-derived fixture, research acquisition, new dependency or distribution-license change. Reuse `pypdf==6.21.4` and the existing hash lock. Keep draft and unmerged. The local Python/SQLite surface remains the behavioral reference; authenticated H1 report transport is separate. H1 #234 now has implemented and verified runtime behavior at `65eafebd9fda221dc79789619133c78c6d01dc60`; do not repeat the older tests-only status.

## Acceptance

Reproduce missing revision validation before repair. Exercise both text and actual two-page PDF correction, A→B→A, stale proposal/quote/receipt refusal, zero-write failure, historical note/report preservation, restart, current readable report provenance and current permission withdrawal. Run the complete Python/HTTP and JavaScript suites, retained browser journeys plus the two annotation journeys, and the offline no-download guard. Report actual checks and limitations without claiming clinical validation.
