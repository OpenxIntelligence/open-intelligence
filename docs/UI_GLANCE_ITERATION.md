# Clinician glance iteration — 31 October 2026

Status: scoped implementation/review candidate, not an architecture or stack replacement.

## Intent

Apply the latest UI research's Glance → Inspect → Verify rule to the existing synthetic-only case workspace. The first screen should show what the available sources report and what review work remains before presenting a narrative-authoring form. Build on integrated PR #29; do not reopen the superseded #26/#27 UI tracks.

## Design and boundary

Keep the existing API, DOM data containers, source-version navigation, historical snapshots and corrected current-review counter. Move the source-reported findings into the opening view, keep their status words and exact source buttons, and put raw evidence registration/withdrawal inputs behind keyboard-operable native disclosures. Source text and uncertainty remain unchanged. No inferred diagnosis, stage, treatment response, age, clinical completeness percentage, priority score or clinical authority is added. No patient-facing view, role toggle, new model or framework.

Alternatives considered: a fresh dashboard or framework migration would duplicate existing state and lack an adopted contract; new summary cards would invent unsupported fields. Reordering the working source-backed components and reducing input-form density is the bounded choice for this iteration. The full S1–S6 specification and its proposed stack are not claimed implemented by this increment.

## Requirement crosswalk

- Latest UI spec 33 UP-01/02/03/10/12: named screen question; source facts first; in-place disclosure; exact source verification; human-authored proposals are not source observations.
- Existing OI-03.1 overview and OI-05.5 source-viewer intent: partial presentation improvements only. Their broader React/contracts/acceptance scope remains open.
- Keep the existing source-change explorer as a document comparison; do not relabel it as the complete human-anchored S7 changes-since-review service.
- Evidence tiers, patient releases, intake worklists and clinical interpretation remain outside this increment.

## Implementation plan

- [ ] Add a failing real-browser test: findings precede authoring in DOM and visual order, are reachable above the fold at 1440×900, retain direct source access, and preserve isolated-case switching.
- [ ] Capture baseline desktop/mobile screenshots from the actual seeded application; capture only independently authored fictional data.
- [ ] Update `web/index.html` and presentation CSS only as needed, retaining all existing action IDs and API contracts.
- [ ] Validate keyboard disclosure operation, 390px containment, clear fictional labels in source dialogs and print, and non-red clinical states.
- [ ] Run Python/HTTP, JavaScript syntax, existing complete Chromium journey and the new focused browser check; save screenshots and exact checked-out source for review.
- [ ] Record verified outcomes and remaining manual/clinical/accessibility limits. Keep the PR draft, stacked on #29, and never merge it automatically.

## Review focus

The current-question counter must not count every stale historical snapshot. Source comparison must remain version-specific. Reordering must not reset unfinished drafts, change case binding, break keyboard focus, or hide selected source versions. Native disclosures must not make actions unreachable. Screenshots and automated checks are not clinician validation, a WCAG conformance audit, or real-device evidence.

## CI-only dependency note

The screenshot artifact workflow uses GitHub's `actions/upload-artifact` pinned to `ea165f8d65b6e75b540449e92b4886f43607fa02` (v4 tag resolved 31 October 2026). Its repository LICENSE at that commit is MIT, copyright GitHub and contributors. It executes only on the CI runner; it is not shipped in the application. Existing checkout/setup-python actions are reused. This source-license inspection is not a full transitive supply-chain or release clearance. Artifacts contain synthetic screenshots and `git archive` of tracked source only, never local databases, environment variables or credentials.
