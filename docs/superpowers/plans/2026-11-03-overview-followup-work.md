# Overview follow-up work

## Purpose and scope

Expose existing saved-question follow-up work on the patient Overview so a person
can see recorded ownership, revisit timing and source changes across questions,
then continue in the existing Investigations workflow. This advances OI-007 and
OI-010 without adding an owner, task ledger, API, dependency or migration.

Base: draft PR #375, `1bdc44ac8507ec3a05398c3965bed5fcae0d59eb` on
`integration/h1-review-followup-chronology-20261103`. Separate active work handles
unsent task drafts (#379), report disclosure (#378) and source keyboard focus
(#353); this change leaves those implementation surfaces alone.

## Design

- Compose `projectFollowthroughAttention` into the existing Overview projection,
  requiring agreement with the selected, successfully loaded case.
- Show the existing five operational categories, the server's evaluation date,
  and at most three open tasks in server order. Describe preview coverage and
  recorded owners; do not imply clinical priority or complete care coverage.
- Preserve unknown, loading and unavailable states separately from a successful
  empty read. A failed task read must not erase independently readable questions.
- Refresh through `RegistrySession.loadFollowthrough(caseId)` and navigate with
  the existing Investigations action. Disable refresh during saving or unknown
  task writes and direct the user to the existing recovery controls.
- Keep all context in existing session memory. Patient/case/credential changes
  must remove earlier task content through the existing scope checks.

## Implementation and verification

1. Add focused projection and real React render tests; observe missing-feature
   failures before implementation.
2. Add the scoped card, callback wiring and responsive styling.
3. Extend the existing real Chromium/HTTP/PostgreSQL follow-through journey with
   Overview counts, refresh, navigation and denied/loading/scope behavior.
4. Run the complete web client test command, rights checks and production build.
   Run the existing hosted built-React/HTTP/PostgreSQL browser gate on the
   published exact head when local PostgreSQL/Chromium are unavailable. The
   backend and migrations are unchanged; separate API/restore suites are not
   claimed as rerun for this UI-only increment.
5. Independently review the patch, update the engineering evidence and backlog,
   publish a draft PR, and synchronize Notion and Drive with exact verification
   and remaining limitations. Merge and deployment remain subject to owner review.

## Acceptance

Two saved questions in one case contribute to the same Overview read. Counts
come from the canonical classification. Loading/denial never display zero as a
known result. A refresh is read-only; it does not resolve unknown writes. The
same saved tasks remain available in Investigations. Case/patient changes and
disconnect remove prior titles and owners. Independently fictional data only.
