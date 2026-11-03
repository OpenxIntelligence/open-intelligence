# Connected document source accessibility implementation plan

> Execute inline with test-driven development. This is bounded reuse of #353, not a redesign.

**Goal:** Make structured-source reading in the current document/evidence/review workspace keyboard-operable and source-specific.
**Architecture:** Keep the existing React App, SourceReading and RegistrySession. Transfer only the source action labels and transient focus bookkeeping; preserve document intake, Review drafts and all domain owners.
**Tech stack:** Existing locked React/Vite/TypeScript; actual FastAPI/PostgreSQL 16/Chromium acceptance.
**Specification:** Existing #353 source-reading behavior at a71341d00b15dce1a95600c1a03b8fbe4c1c8ce1 and the user mandate to preserve working UX during convergence.

## Pinned inputs and scope
- Base #377 b13dd4810342d6a7ef08bbad53745502e0950801, tree ced2dd53450a576295b610c91b8240206e4c25a3.
- Donor #353 a71341d00b15dce1a95600c1a03b8fbe4c1c8ce1, hosted run 41710676401; no donor result substitutes for combined acceptance.
- No backend/session/API/schema/migration/dependency/permission or workflow changes. Independently fictional sources only.
- Preserve #377's reviewed-document empty-state copy and two newer disclosure assertions; never replace entire newer files with an older donor.

## Review focus
Exact source/version names; current and historical original focus; keyboard scrolling at 390px with enlarged text; removed-opener fallback; ordinary navigation must not replay prior focus. Existing case/denial/late-response tests remain active. No full accessibility or screen-reader certification.

## Task 1: Establish behavior before runtime adoption
- [x] Recover ZIPs, verify checksums and reconstruct the full base Git tree in an isolated local checkout.
- [x] Add #353's computed-name, focus/return and original-scroll browser assertions using the exact donor reading helper; retain the two current document-disclosure assertions in its caller immediately before execution.
- [x] Pass the existing fictional credential fixture to that helper, restoring its original grants in finally.
- [x] Publish tests-only checkpoint and observe expected missing accessible-name/focus failure in actual built-browser acceptance.

## Task 2: Reuse source-owner implementation
- [x] Transfer App-local focus bookkeeping and the callback's trigger argument, preserving all current document and review wiring.
- [x] Add source/version/line/finding accessible names and focus/scroll styles. Preserve the current document empty-state message.
- [ ] Re-run exact-head client/build/rights and actual PostgreSQL/FastAPI/Chromium journey; inspect retained artifact, source hashes and narrow-screen capture.
- [ ] Record source pins, actual failures/results and limitations in the existing continuity record/backlog and PR. Keep draft/unmerged/undeployed.

## Execution record
Base ZIP SHA-256: 622b5394eb535b7072f4c7cbdb2adf649256665e536eb7dabe0d8548d6c90e39.
Donor ZIP SHA-256: 2cf23c43955e86e19cf8fbec3d3c901a8dbd609d145d3b526ec782ecca945e3b.
Self-review only; no independent reviewer available in this execution. Full backend/restore acceptance belongs to #377, not this frontend delta. Hosted child acceptance is pending at this checkpoint.

Observed tests-first head 1753aec4c8f5885d294aded1fcd12758d009f5b4: hosted run 41712366005 passed all 415 client tests and build/rights, then failed at the missing computed original-action name `Inspect original v1: DOC-ONE`. Downloaded artifact 13268470956 SHA-256 a4a00fe56faec49d7b9852e1086294ff72227cc7258c91ce8893c68873eb64d1 and commit marker matched. This is the observed integration regression, not a donor result.

Local npm acquisition timed out at 25 seconds. The full local client attempt passed 403 controls but two renderer files could not load React (evidence-continuity-panel.test.mjs and question-evidence-panel.test.mjs). Global TypeScript was 5.8.3 rather than locked 5.9.3; no local full-build acceptance is claimed. All 13 local rights regression tests and the bounded data-entrypoint audit passed. Exact-head final hosted acceptance remains required.
