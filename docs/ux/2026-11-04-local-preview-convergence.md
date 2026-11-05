# Preserve local preview keyboard inspection in H1 convergence

4 November 2026. Bounded OI-009/010 frontend integration repair.

PR #353 merged at 33e4fc17494c8a4ea6c0b9714bcb9122a06cd2c1. Its final donor head 10a66e05024324684aca4ab0f934f94fb447b044 includes keyboard access to the unsubmitted local original preview. The inspected #413 head e3259bb2986206e4a7edf8bc3a29546471077beb retains the verified-original focus/scroll behavior but its local preview and import journey omit that final increment.

Restore only the preview's named region, tab stop and focus centering; extend the existing height bound to the intake preview; port the exact native-keyboard acceptance block into the current import journey. Preserve all other current file content. No source validation, file handling, confirmations, submission, API, backend, migrations, permissions, dependencies or newer document/manual-passage ownership changes.

Acceptance selects the real authored disk fixture, uses Tab/PageDown at 390px with enlarged text, requires the whole scroll area visible below patient context, then tabs to an unchecked confirmation. It verifies unchanged local text, disabled import and unchanged server source count before the existing explicit import/duplicate/amendment/quarantine checks continue. Existing combined frontend/browser acceptance must pass at this new commit; donor green results alone do not qualify the integration.

The immutable parent has passing frontend and reference UI workflows; its API/recovery workflow was still running when selected. This frontend-only repair does not claim overall #413 release acceptance. Exact result, artifact and final disposition are recorded in the draft PR and existing research documents. Synthetic data only; no clinical, production, full WCAG or cross-browser qualification.
