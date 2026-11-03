# Connected reading and patient Overview convergence

## Intent and authorized scope

Continue the existing healthcare UX redesign on the latest connected React workspace. Patients should be able to resume an unfinished question, understand source reassessment, and find an interrupted verification return from Overview. Every route to a different section must clear prepared source quotations and briefs, including pending deliveries, while preserving authored work.

This is a frontend continuation of the supplied redesign brief. Backend, database, APIs, permissions, business rules and existing functions must remain unchanged. Existing patient/clinical reading layouts are presentation choices, not authenticated roles.

## Inspected source owners

- Base: PR #305, `aea88341e260a4829d5b1647d5395b78ca17bfa6`, tree `7ef9eb08115f12c027b18513808ceb6255369f67`. Its exact archived 340-file source tree is the local baseline.
- #305 includes #299 follow-through attention and #293 durable tasks. Preserve these owners and all source-reading checks.
- PR #288 supplies the existing shared-navigation clearing pattern and patient preparation projection.
- PR #294, `bcfa06a18761e395dc63176afcd14667e3a5dee3`, supplies the source-refresh recovery projection, Overview component and recovery acceptance. Import selected frontend files; do not merge its entire stack.
- PR #300 authored evidence and #298 governed metadata remain separate domain integrations. This increment does not combine migrations or claim those workflows are present.

## Approach

Reuse the existing Overview component and read-only projection inside #305's current shell. Centralize the two existing packet/brief dismissals in its navigation function before its same-section return. Retain heading focus, responsive header measurement, reading layouts and response-scoped filters.

A whole-branch merge would import unrelated backend histories. A new dashboard implementation would duplicate accepted frontend work. Selective reuse is the bounded implementation choice for this continuation.

The projection imports `ViewState` as a type only. Tests compile it directly; `registry-client.ts` stays byte-identical. Navigation must not submit a return, change a request key, read the API or reset a task/question draft.

## Acceptance

1. A contextual Investigations → Review → Questions round trip clears both prepared quotation and brief. Late actual responses cannot restore either after navigation.
2. Overview resumes the same literal unfinished question and distinguishes unchecked/unavailable history from a checked empty result, current questions and source reassessment.
3. An uncertain verification return remains discoverable after same-case source metadata refresh clears the World Model. Its shortcut must match the case the existing Review panel will open, including fallback to older record metadata after a failed refresh. The Overview link is neutral navigation; retry is explicit in the existing Review panel using the original intent.
4. Patient switch, disconnect, denied access, revoked case or contrary scope withhold the projection. No implicit clinical approval, delivery or notification is introduced.
5. Existing source filters, reading preference, follow-through filters and drafts, keyboard focus, source amendment, actual downloads and narrow layouts continue to pass.
6. All backend, session, domain, migration, contract, dependency and workflow files retain parent bytes and modes.

## Evidence and limits

Run the full existing client suite/build and actual PostgreSQL/FastAPI/built-React browser gate on one published draft head. Retain a failing browser reproduction of the contextual-navigation defect before the repair. Use independently authored fictional records only. Unit/client results do not substitute for the combined browser gate. No merge, deployment, clinical validation, production identity or broad accessibility certification is implied.
