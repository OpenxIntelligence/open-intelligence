# Connected patient preparation and source authority

## Goal and engineering choice

Connect the verified patient Overview, authored questions and exact-source inspection to the existing intake-authority, operational verification-return and authorized-download foundation. A person should be able to resume preparation, inspect the original statement, record why independent verification is needed, download a freshly authorized brief, and understand what changed after an amendment in one workspace.

This is bounded continuation under the standing product mandate. The engineering choice is an explicit integration of existing owners. Leaving the features on separate branches would not establish the combined workflow; replacing their stores or contracts would discard verified behavior. No new product architecture, permission, dependency, clinical action or migration is selected.

## Pinned ownership

| Role | PR and exact commit |
| --- | --- |
| Integration base: intake, canonical questions, review returns and briefs | #276 `c154bfbc5f99f76801d37903959943659c0b6a71` |
| Authored questions, exact-source packets and Overview continuity | #286 `eb3cff81a4edeaf433d25cc069c9894c3bc52d0b`, including #280 `e8d851e5c7769c31f429a3d1649c26402aa9de12` |
| Shared ancestor | #264 `e042f753eca85cca97e08fdbb3e07ea8263aae69` |
| Selective correction donor: actual review JSON preparation and uncertain-return recovery | #278 `b72560ac0f5e5005040b0fc660ce1650343611cf` |

The image custody/migration integration in #278 remains its own lane. Only its applicable review-response and same-case recovery corrections belong here, with exact reuse or an explicit adaptation recorded.

## Required behavior

1. Preserve one patient, case, original-source, question and return-receipt owner. Keep both actual integration parents and all inherited source identities, events, permissions and amendment semantics.
2. Overview distinguishes unfinished, uncertain and confirmed questions and last-read current versus reassessment state. Failed or unknown history is not zero. Navigation preserves the same patient's draft and clears prepared sensitive views as required by the existing session contract.
3. One authored saved question can be inspected, returned for independent source verification and downloaded as a source-only brief. Selecting another question must invalidate mismatched pending/prepared packet or brief responses.
4. A source amendment preserves original questions, return receipts and already downloaded files. Current disclosure and new work use current context; historical exact-return retries recover their original receipt without silently retargeting it.
5. Exact-source packet and review response JSON bytes are prepared inside the existing source transaction, before the same-bearer final authority check and commit. Preparation, final authority or commit failure withholds the response and rolls back attempted effects. Required permissions remain independent.
6. Same-case import and temporary metadata failure preserve an uncertain/in-flight review return's exact intent and idempotency key. Actual patient/case/permission loss clears sensitive state and prevents stale responses restoring it. Recovery is explicit; no automatic return POST.
7. Preserve all inherited regression and browser assertions. Add meaningful combined acceptance and actual encoding-time denial/rollback checks where existing evidence is insufficient.

## Global constraints

- Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript remain the existing stack; Next.js is excluded.
- Independently authored fictional records only; no real-person or patient-derived fixtures.
- No new dependency, permission, schema migration, clinical/evidence ledger, model execution or external notification.
- Keep source-only context, operational verification return and clinical approval distinct; clinical-approval flags remain false.
- Keep original migration files and dependency locks unchanged.
- Preserve exact patient/case/source/question identity, historical versions and independent grants.
- Work on an isolated branch; publish a draft PR with exact-head evidence; do not merge or deploy.

## Acceptance and limits

Run the combined client suite and locked build, the full hosted API/PostgreSQL suite without skips, inherited reference/browser checks, and existing recovery gates. Extend the real PostgreSQL/FastAPI/built-React journey through Overview, authored question, exact inspection, verification return, fresh download and amendment/reassessment. Inspect final screenshots and verify downloaded bytes plus the archived source identity.

This is source preparation software, not licensed biomedical investigation, professional review or #249 PDF/report parity. Synthetic fixture authority is not production identity or consent. The final authority check cannot create atomic revocation across an external provider, PostgreSQL and HTTP delivery; a committed receipt is not delivery confirmation. Existing downloaded copies cannot be recalled. Main retirement and historical-data cleanup remain separate.
