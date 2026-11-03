# Record intake and follow-up convergence

**Goal:** Bring the verified record-import disclosure into the combined source-reading, evidence-report and follow-up workspace.

**Authority and design:** Continue the founder-authorized bounded H1 integration under `AGENTS.md` and `docs/FIRST_PRINCIPLES_PLAN.md`. Use existing React/Vite/TypeScript presentation and the existing FastAPI/PostgreSQL source, question, evidence, report and task owners. This is a composition of accepted engineering behavior, not a new architecture or clinical release.

**Pinned inputs:** Remote base #328 `5a188d4e18e4d80bc2ba1d662c966abc3096301f`, tree `269ce69e54fa1338dbfa87ae6e043b36f11d6ba6`; donor #319 `2475d924fddef6792076bdf9039fad5be7312b7a`, tree `b87461e4ff32bc2088678055e9c6fbf03f2fdf29`. Local snapshots have different commit metadata but their complete trees match these published trees. Publication must use the remote #328 commit as parent.

## Scope and decisions

- Reuse the exact 13-line `RecordImportDisclosure` owner and the existing `SourceIntake`; populated cases start collapsed, empty cases expanded.
- Native disclosure toggles keep the selected file, preview and confirmation mounted. An explicit import remains the only write.
- Keep the current combined application and all follow-up attention behavior. Do not replace it with the donor's older application tree.
- Preserve the newer terminal-denial synchronization in the combined reading journey. Apply only the donor's added disclosure assertions to that helper.
- Preserve backend bytes, migrations, dependencies, permissions, question/evidence/report owners and source identity. Keep all independently authored synthetic fixtures and no external patient data.
- Keep ongoing #324 review-draft, #327 imaging, #329 source-reading and #330 chronology work outside this bounded composition.

## Task 1 — Demonstrate the composition gap

- [x] Verify the complete base and donor trees and run the base client suite.
- [x] Port the donor's existing real-browser intake assertions plus only its two reading-disclosure assertions.
- [x] Run actual PostgreSQL/API/React/Chromium acceptance; observe failure at the missing collapsed disclosure before product changes.

## Task 2 — Compose and verify

- [x] Add the exact donor component, its existing main wrapper and CSS; retain the current session and reading owner.
- [x] Run the complete local client suite, production build and existing dependency gate.
- [ ] Verify the combined actual browser journey on the final published head; maintain its final receipt in PR #335.
- [x] Request and complete an independent code review of the small diff.
- [ ] Inspect final hosted desktop and narrow-browser captures; record the outcome in PR #335.
- [ ] Publish a draft child of the unchanged #328 head, verify the exact published head, and extend the existing continuity evidence with actual results.

## Review focus

1. Empty versus populated source indexes must initialize the disclosure correctly.
2. Native keyboard closing and reopening must retain exact selected bytes, preview and confirmation without an HTTP write.
3. Patient/case scope changes and failed access must keep existing reset/withholding behavior.
4. Existing source reading, exact original access, evidence reports and task attention must coexist in the same journey.
5. The transplant must retain the current terminal authorization-denial wait and all newer parent safety fixes.

## Execution ledger

- Started November 3, 2026. Current work is an isolated local checkout. Existing owner branches and main are not being edited.
- Local base tree verified against the GitHub #328 commit metadata; local donor snapshot `d7097ef18ef4af64697ec70f6742d744c5612276` tree verified against GitHub #319.
- Direct Git object reconstruction was not used: API timestamps omit original commit serialization details. Source-tree identity is verified explicitly; publication will retain the actual remote parent.

- Baseline: 300 client tests passed, zero skips; production build and dependency gate passed (18 installed, two optional uninspected, no errors).
- Tests-first hosted run [41668978841](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41668978841) at `9c7c27a1df2861eb7d5433327d8e64ff96d9c5f2` failed specifically with `AssertionError: Loaded records start with the import form collapsed`; all preceding build, dependency and database steps passed.
- Production implementation now reuses all three donor code blobs exactly, after verifying their predecessor main/CSS bytes match this combined parent.

- Implementation verification: 300/300 local client tests, production build and dependency gate passed. A fresh read-only review found no Critical/Important/Minor findings and independently checked the exact donor bytes and preserved stronger denial wait.
- Publication preparation checkpoint: the remaining hosted/visual checklist items are verified and recorded on PR #335 after this source snapshot is committed. Chromium is the supported browser gate; broader browser coverage is not inferred.
