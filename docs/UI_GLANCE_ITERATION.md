# Clinician glance iteration — 31 October 2026

Status: implemented and automatically verified on a draft review branch, not merged or deployed. This is not an architecture or stack replacement.

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

## Implementation record

- [x] Add and observe a failing real-browser test: findings precede authoring in DOM and visual order, are reachable above the fold at 1440×900, retain direct source access, and preserve isolated-case switching.
- [x] Capture baseline desktop/mobile screenshots from the actual seeded application, using independently authored fictional data only.
- [x] Update `web/index.html` and presentation CSS, retaining existing action IDs and API contracts. No application JavaScript or backend changes in this increment.
- [x] Verify native disclosure keyboard operation, 390px containment and fictional labels in source dialogs. Inspect actual desktop and mobile screenshots. Clinical freshness styles are calm amber; red remains for system errors.
- [x] Run Python/HTTP, JavaScript syntax, source-reader regressions and all three Chromium journeys. Save screenshots and exact checked-out source for review.
- [x] Record verified outcomes and remaining manual/clinical/accessibility limits. Keep PR #37 draft, stacked on #29; neither is merged by this work.
- [ ] Independent code/design review, full manual assistive-technology and zoom/reflow audit, rendered print review, representative real-device and clinician usability testing.

## Verification — completed

Code head: `68d685a3f61f92bff8b017f9f1d47d078b9ac70d`.
Tested integration checkout: `6302480844d87e000d42fa1813df13178873c89f`, against PR #29 base `cf7c671fb9fe52ec310b128ceef393eb8f42c570`.

[PR #37](https://github.com/OpenxIntelligence/open-intelligence/pull/37) is the incremental review artifact. [GitHub Actions run #41264189055](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41264189055), job `124723431752`, passed compilation, JavaScript syntax, **38 Python unit/HTTP tests**, **16 JavaScript source-reader tests**, and **three browser journeys**: the complete source/investigation/amendment lifecycle; asynchronous dialog and lineage regressions; and the new source-first layout/keyboard/mobile check. The focused check reports 13 passed assertions and no errors.

At the same 1440×900 viewport and original Alpha fixture, the bottom of the first exact-source action moved from **2993.92px to 739.94px**. All five source-reported findings retain exact-source actions. This is a layout measurement, not a measured reduction in clinician workload or improvement in patient outcomes. At 390px the page has no horizontal overflow; mobile source facts still follow the header, case controls and counts rather than fitting entirely into the first viewport.

[Verified screenshot/source artifact](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41264189055/artifacts/13066137062): desktop overview, source dialog, mobile overview, `verification.json`, exact commit and tracked source archive. Artifact SHA-256: `69a75e5e6b2bce04cad53972d706225427a24c9fffc87c8e8ba6c34515382193`. Downloaded bytes matched this digest; screenshots were visually inspected. CI artifact retention is seven days, so use the recorded commit to reproduce after expiry.

The initial red test exposed source facts below authoring, absent in-dialog fictional labeling and no technical-input disclosure. A subsequent test run also exposed an incomplete simulated Enter sequence; the final test sends the native character event and verifies actual focus and disclosure state. One earlier Chromium startup failed before the application opened; the complete final run passed without removing or weakening that journey. Local Chromium could not access the loopback application under this session's browser policy, so browser evidence comes from the CI runner, not a claimed local or real-device session.

## Review focus

The current-question counter must not count every stale historical snapshot. Source comparison must remain version-specific. Reordering must not reset unfinished drafts, change case binding, break keyboard focus, or hide selected source versions. Native disclosures must not make actions unreachable. Screenshots and automated checks are not clinician validation, a WCAG conformance audit, or real-device evidence. No complete patient-facing view, authenticated clinician role, clinical correctness, release-rights clearance or production readiness is claimed.

## CI-only dependency note

The screenshot artifact workflow uses GitHub's `actions/upload-artifact` pinned to `ea165f8d65b6e75b540449e92b4886f43607fa02` (v4 tag resolved 31 October 2026). Its repository LICENSE at that commit is MIT, copyright GitHub and contributors. It executes only on the CI runner; it is not shipped in the application. Existing checkout/setup-python actions are reused. This source-license inspection is not a full transitive supply-chain or release clearance. Artifacts contain synthetic screenshots and `git archive` of tracked source only, never local databases, environment variables or credentials.
