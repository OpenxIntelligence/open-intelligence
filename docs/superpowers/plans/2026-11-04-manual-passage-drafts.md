# Retain unsaved manual passage selections

Bounded continuation of OI-007/008/009/013 on verified #419. Existing passage
selection state is component-local and is silently replaced on refresh or lost
on navigation. Retain only exact passage references and the inspected context
hash in RegistrySession memory. Keep quoted text server-owned and freshly read.

Implementation choice: extend the existing QuestionPassageClient, not a second
source owner. Browser storage and server autosave are outside this slice. An
unsaved selection is not a saved attachment or report input.

Acceptance:
- Additions and removals survive panel disposal, navigation and same-context
  refresh, with zero automatic writes.
- Resume reads the current manual context and every retained exact selection.
  No retained text is shown while checks are pending. Changed context/anchors
  block save and report binding until explicit discard/reselection.
- Denied access and patient/session changes clear unsent references. Late work
  cannot recreate a cleared draft. Temporary read failures retain references
  without displaying unverified quotations.
- Explicit save hands off to the existing immutable uncertain-command recovery;
  successful save and explicit discard clear the unsent draft.
- Tests first, full client/build/rights checks, independent source review, then
  the actual synthetic PostgreSQL/API/Chromium journey on the published head.

No backend, dependency, migration, grant, clinical status or model changes.
Synthetic software verification only; no main merge or deployment claim.
