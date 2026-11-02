# Question-linked source review handoff

**Goal:** make the existing overview review status actionable: open question -> affected original report/evidence -> existing authoring form. This implements OI-007/OI-009 and the existing Notion source-to-review contract; not a new navigation or architecture.

**Base:** PR #48 at 82cebdce53031b0de4f681dd0d0a2189bc35de79. Keep it unmerged pending review. This separate stacked change must be reverified after its base is integrated into main.

**Design choice:** retain the existing sidebar/status and form rather than add a workspace or another review state. Derive rows from currentReviewQuestionIds, existing snapshots and source/evidence links. One row per open question, no cap. Compare only linked consecutive report versions; missing lineage remains unavailable. Show evidence withdrawal and rights changes separately from report amendments. Never expose broker excerpts. No model runs, network egress, saved drafts or review actions are triggered by navigation.

**Files:** web/mission.js (projection/render/navigation and coalesced observer of the existing accepted-render event list; one dynamic list inside current review status using existing classes), tests/question_review.test.js and Python wrapper (real functions in inert DOM), tests/question_review_browser.py (full click-through) and a narrow CI workflow.

## Acceptance and implementation
- [ ] Failing tests first: deduplication, historical-only state, report chain, missing lineage, evidence/rights changes, no truncation, inert text, case/refresh guard, unsaved-content guard, exact question selection without source replacement.
- [ ] Implement read-only projection and compact source actions in current sidebar. Keep counters, original data and uncertainty unchanged.
- [ ] Handoff focuses existing observations field only after explicit user action; refuses to replace another question's unfinished text or evidence selections. Source selections are unchanged and require manual reconciliation.
- [ ] Browser: amend source; see question; compare original versions from overview; open exact original; prepare draft; preserve wrong-case/unsaved guards; acknowledge replacement through existing controls; queue clears but history stays.
- [ ] Full unit/HTTP, JavaScript and hosted browser checks on the exact new head; preserve failures and scope limitations.

Not clinician authentication, clinical review, patient understanding, triage, permissions or production readiness. Existing final-design research gates remain in force. No runtime dependency or patient fixtures change.
