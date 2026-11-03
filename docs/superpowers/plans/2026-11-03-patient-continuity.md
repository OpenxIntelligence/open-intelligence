# Patient continuity overview implementation plan

Goal: let a patient resume existing preparation from Overview without reconstructing navigation.

Architecture: read-only projection of RegistrySession. No new persistence, backend grants, clinical tasks or network reads. Build on PR #280 at e8d851e5c7769c31f429a3d1649c26402aa9de12; preserve independent integration owners. Maps to OI-007, OI-009, OI-010 and the founder's patient-centered direction.

Scope: one Overview panel with explicit patient/case scope, known versus unchecked question counts, amendment reassessment, and draft/save recovery navigation. Use current React/TypeScript and existing styles. Treat last-read state as such; never claim complete coverage or clinical urgency. The panel is not a care plan or clinical review queue.

- [x] Add behavioral projection tests: no patient/disconnect/suspended; unknown versus empty; current versus reassessment; wrong patient/case; failed/loading reads; saved versus unsaved/uncertain drafts.
- [x] Implement patient-continuity.ts and the Overview component. Navigation retains existing state and dismisses sensitive prepared views as current navigation does.
- [x] Extend real PostgreSQL/built-React browser journey to check current/reassessment overview and draft resume.
- [ ] Run all client tests, production build and browser acceptance when available; record exact-head limits. Publish a draft stacked PR, no merge/deployment.

Review focus: mixed case state, false all-clear, stale count after permission failure, falsely unsaved confirmed question, and navigation losing an uncertain save. Existing server checks remain authoritative.
