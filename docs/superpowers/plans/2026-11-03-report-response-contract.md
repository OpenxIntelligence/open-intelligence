# Readable report response contract implementation plan

> **For agentic workers:** Use superpowers:executing-plans; preserve existing report and source owners.

**Goal:** Refuse malformed readable-report responses before rendering, printing or creating a download, without changing source/domain semantics.

**Architecture:** Validate the existing server response envelope inside `web/report.js` before `renderReport`. Keep request generations, pending-write tracking, Blob lifetime and exact accepted text unchanged. Do not add a second renderer, source ledger or clinical authority.

**Tech stack:** Existing dependency-free browser JavaScript; existing Node DOM/timing harness and hosted full Python/PDF/Chromium acceptance.

**Spec:** OI-007/OI-009/OI-010 and the existing connected workflow contract. The server's `build_patient_report` already provides the fields below; the client must not silently coerce malformed values into a printable report.

## Constraints and review focus
- Independently authored fictional data only; no new dependencies or runtime medical inference.
- Require `fictional === true` and the existing recorded-data-only `generated_from` value.
- Require typed, nonempty report metadata and a coherent event-id/time pair; accept null/null when no event was recorded.
- Require nonempty, uniquely identified sections aligned with `section_ids`, arrays of typed display entries, and coherent item/citation counts.
- Permit additive fields, including separately owned source-reference/revision metadata. Envelope validation does not authenticate source references or prove semantic agreement between sections and downloadable text.
- Reject before allocating a Blob; keep old URLs revoked and permit explicit recovery. Error responses must not echo arbitrary backend content into the patient view.
- No main merge, deployment, production or clinical approval.

## Steps
- [x] Recover and hash-verify PR #250 final authored tree and its hosted acceptance archive.
- [x] Run the unchanged complete JavaScript suite: 172 passed.
- [x] Add negative response-contract cases: 24 failures on the baseline; two additional same-realm transport/JSON failures reproduced separately.
- [x] Add minimal validation and retain request/write lifecycle behavior.
- [x] All 199 JavaScript checks and 33 Python report/HTTP tests passed locally; compile, syntax, data guard and whitespace checks passed.
- [ ] Update existing draft #250 with an expected-head lease; require hosted exact-head full suite and browser evidence before completion.

## Current baseline
PR #250 head `82f066d089c5770a891a2d1e0329df6a8771e3cd`, tree `4acaf0713a74792b3361b7ff00575784de5a9fc5`. Hosted run `41570357014` succeeded with 859 Python executions, 172 JavaScript checks and 12 browser journeys. Offline research: 80 passed and 18 optional skips. This run's artifact digest and complete archived Git tree were independently checked in this continuation.

## Verification qualifications
Two original intake test responses were incomplete renderer-only stubs. They now include the fields the actual server already supplies; their original write-lifetime assertions are unchanged. Transport error regressions use the browser-client VM realm, avoiding a false pass from `instanceof Error` across realms. All 27 added cases are authored fixtures.

This change does not port #249 annotation revisions or its source-reference validator, alter any server/source schema, or validate clinical correctness. The complete pinned-parser/PDF/browser run remains the hosted gate; the local environment has a different parser and is not represented as full PDF acceptance. No independent external reviewer is available in this continuation; review is inline.
