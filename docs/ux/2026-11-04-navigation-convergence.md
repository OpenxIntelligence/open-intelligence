# Preserve navigation and source-entry focus in the combined H1 workspace

4 November 2026. Bounded frontend continuation of OI-010.

## Pinned inputs and observed omission

- Parent #443: `90fc861c46035d29876e4d2a779957b535b46037`, tree
  `e7ef89c256f59a41064f9102be530cfb6a263fec`.
- Its combined H1 parent #413: `e3259bb2986206e4a7edf8bc3a29546471077beb`.
- Navigation/source-entry donor #386: `93e0633e359914f1eacb0accff6a08ff94ef2c02`.
  GitHub now records it merged into its owning #382 branch at
  `d80ee49ccbda8e4add785e692aa06e3d321515fa` on 4 November 2026.
  This is not evidence of a merge to main or a deployment.

Direct source comparison shows the newer #413/#443 workspace lacks the donor's
Change section link, focusable navigation target, explicit source-entry focus
intention and both corresponding browser acceptance blocks. It retains newer
image dismissal and document/manual-passage workflows. #443 separately restores
keyboard access to the unsubmitted local original preview.

## Integration

Reuse #386's focused frontend behavior and browser assertions on #443:

1. Change section reaches the existing five-button navigation after long reading,
   preserving the mounted source panel, patient, filters and request count.
2. Inspect source versions focuses the returned source-history heading below
   patient context. Native Tab continues into existing controls.
3. Another focus choice, section change, disconnect, changed patient or failed
   record operation cancels the transient intention. Late responses do not replay
   it; a fresh deliberate request still works.

The only runtime conflict adaptation retains the newer
`session.dismissSourceImages()` in the navigation callback. The CSS additions
are inserted beside their existing rules while preserving current image styles
and #443's local-preview height bound. The source-entry browser helper and
reading acceptance retain the donor's exact behavior, not replacement tests.

Backend, migrations, API contracts, permission checks, RegistrySession, response
validation, clinical/business rules, dependencies, workflows, source owners and
the retained reference application are unchanged. This is a child proposal, not
a full merge of older code over the current H1 candidate.

## Acceptance and limits

Parent local baseline: 483 client tests and TypeScript/Vite build passed. The
existing build already reports a JavaScript chunk over 500 kB; bundle splitting
is a separate improvement, not a new dependency or change to this repair.

The combined head must pass the client/build/rights checks and actual
PostgreSQL/FastAPI/React/Chromium journey. Required assertions include native
keyboard navigation, mobile/desktop/short-height positioning, delayed-response
cancellation, denial/reauthorization, local-preview keyboard scrolling, and the
inherited document/image/manual-passage question/report and review journeys.
The exact combined artifact must match the source commit, and current-run
screenshots must be inspected. Donor green runs do not establish this result.

Final hosted results are pending at this source checkpoint; the PR and existing
Notion/Drive UX records will contain the immutable acceptance receipt. This
bounded frontend verification does not satisfy the parent integration's full
API/recovery, security/rights/source-owner review, or merge/release gates.
Independently fictional inputs only. No clinical validation, complete WCAG,
cross-browser or participant-study claim. Draft, unmerged and undeployed.
