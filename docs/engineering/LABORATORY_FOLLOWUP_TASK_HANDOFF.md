# Laboratory follow-up task handoff

Bounded continuation of OI-008 on connected candidate #624 at
`631c3e0cea30d4b859a2e428d200d352c97c6567`, tree
`fb4dd9cef6f6713f6390d4559c665ad75253f473`.

## Patient behavior

Overview already shows recorded follow-up beside a selected laboratory result.
“Open task history and actions” now opens that task in the existing Investigations
follow-up workspace. A fresh read must match the patient, case, task, question and
immutable laboratory origin. The task heading receives keyboard focus. A source
amendment preserves the original reference and displays the current reassessment
state. Newer task revisions and recorded history come from the canonical owner.

The entry contains only in-memory identity references and the prior access receipt.
It carries no copied task content and grants no authority. Denial, a missing task,
changed origin or mismatched scope displays unavailable. Other tasks are not
substituted. Explicit “Show all follow-up work” returns to the authorized list.
Navigation, patient changes and case changes clear the targeted entry. Delayed
reads retain the existing RegistrySession cancellation and scope fences.

All status changes use the existing task form, validation, attributed reason,
revision checking and exact uncertain-write recovery. Merely opening a task sends
no browser mutation. Completing reassessment-required laboratory work stays
blocked. Clinical interpretation, professional approval and external communication
remain separate authorities.

## Acceptance

- Client regressions cover fresh receipts, stale question objects, changed origin,
  missing and mismatched tasks, legacy contracts, unknown writes, permission denial,
  disconnect and late responses after a patient switch.
- Rendered controls show only the selected task, preserve canonical history/actions,
  escape source-derived text and withhold unrelated task bodies.
- The actual PostgreSQL/FastAPI/Chromium journey must assign and acknowledge work
  reached from preparation, reopen it after amendment, preserve an unsent reason,
  block stale completion, deny/recover task access, focus the correct heading,
  preserve exact original reopening and emit zero mutations for inspection.
- Run the locked dependency-rights gate, complete client suite, production build,
  existing browser journey and persistent fictional demonstration on this source.

No backend, database schema, dependency or rights policy changes. This dependent
draft preserves the #624 source unchanged outside the listed UI, test and document
files. Main reconciliation and final combined API/migration/restore qualification
remain with the connected foundation owner. Parent and donor passes do not qualify
this new source. Hosted results and exact source identity are recorded in the PR.

All fixtures are independently authored fiction. No real patient data, clinical
validation, main merge or deployment is included.
