# Healthcare frontend redesign: delivery and verification

**Completed work:** frontend information architecture, patient presentation, clinical worklist, dedicated patient chart, visual system and responsive navigation.

**Baseline:** connected-workspace PR #166, `334d863b2206b290c02cd2606dcb93c93afe3a68`. **Branch:** `feat/healthcare-ux-redesign-20261102`. Research and the complete source audit were recorded before implementation. This is an isolated review candidate; its parent work has not been merged or deployed by this task.

## What changed

The former long page is now 21 focused presentation destinations. The original live controls and record renderers are retained. Navigation moves or reveals their existing nodes instead of creating a duplicate case store, report workflow or set of forms.

### Patient experience

The primary navigation is **Home, My record, Documents, Questions & reports, and Updates**. Research discovery remains a secondary tool. The link to workspace setup explicitly identifies it as a clinical preview destination.

Home prioritizes the selected record, three common actions, existing record counts, open questions and the existing explanation of updates/uncertainty. It does not invent appointments, prescriptions, results or diagnoses. The complete plain-language record retains source quotations and certainty, adds the existing guarded exact-source reader to each available finding, and groups previous record events in a native disclosure. Questions and saved report reading/export are separate destinations. Professional authoring and demo review acknowledgment are not displayed as ordinary patient controls.

### Clinical workspace and patient chart

The clinical entry is the existing all-case worklist, now searchable by the rendered case alias/reference. Source-event recency ordering and the existing counts are unchanged. Opening a row passes through the original case-switch guard and enters a dedicated chart.

The selected case banner and chart navigation are separate from application navigation:

| Chart group | Existing functionality retained |
|---|---|
| Overview | Current source/statement/question/review counts, original review state, short source preview and full-record path |
| Record | All reported findings, event timeline and source comparisons, plain-language record, Patient Mission, source-linked World Model, biological-asset provenance |
| Documents | All original source versions and readers, file intake, structured text imports and quarantine receipts |
| Investigations | Durable questions, manual drafts, bounded model investigation/Composer and saved reports/history |
| Evidence | Fictional evidence registration, applicability assessments, withdrawal, and all five option/dependency/task/threat/reviewer forms |
| Review | Updates since the existing review anchor and recent ledger activity |

Questions, drafting, model work and saved reports no longer compete in a single section. Existing generated report links reveal and focus the exact report. Setup progress links now enter the corresponding Questions or Reports page. Notices and dialogs remain outside the routed content so errors and source inspection are not lost when changing sections.

### Visual and responsive design

The design uses the existing system font and CSS token structure, with navy text, restrained teal actions/navigation, white content surfaces, quiet borders and explicit warning/error colors. No production dependency, external font or icon service was added.

Desktop has a persistent rail, a selected-case banner, six chart groups and contextual subsection links. The chart overview places source facts alongside review context. Mobile uses a real menu button, hides the closed rail from the tab order, and provides a labeled native chart selector. Patient subsection links remain available on narrow screens. Source text and identifiers wrap; exact-text comparison has contained scrolling. Controls have visible focus and a minimum 44px height.

The final browser journey checked primary destinations at **320, 390, 768, 1024 and 1440px**. No page-level horizontal overflow was found in those checks. The visual overview journey measured the first source-inspection action at **867.1px within a 900px-high desktop viewport**. This is a concrete observation for the tested fixture and viewport, not a claim for every possible record length.

## Preserved contracts and technical scope

- All **16 original forms** retain their original IDs, controls, native constraints and select values. A fixed baseline form manifest verifies this against the actual connected host output.
- All seven literal host-composition anchors are retained; both existing launchers still work.
- Backend product files, database/schema, API endpoints/contracts, authentication, authorization, business/data-processing rules, integrations and validation rules were not changed.
- A byte-for-byte comparison found **zero changed files among 103 protected non-frontend product files**, including all 16 files under `src/`.
- `intake.js`, `mission.js`, `world-model.js`, `composer.js`, `literature.js`, `workspace-entry.html` and `base.css` are also byte-identical to the baseline. The entry adapter only changes presentation handoffs and shortcut destinations.
- The original canonical `caseId`/`active` state, readiness checks, unfinished-narrative case-switch veto, original-source membership guards, async read protection, Composer fingerprint requirements and request payload construction are preserved.
- Same-case route and presentation changes retain unfinished text, selected question/source bindings and disclosure state. A successful different-case load dismisses only the now-resolved draft-switch warning; unrelated errors are preserved.

## Executed verification

The tests use independently authored fictional fixtures and temporary databases. No real patient records, live model calls or live research-provider credentials were used.

| Verification | Actual result |
|---|---|
| Complete Python suite on final product files | **347 tests passed**, 58.129 seconds reported by unittest; no product file changed during the run |
| JavaScript checks, executed directly per file | **80 checks passed across 8 files**, including 9 new route contracts |
| Form/host preservation | **2 tests passed**: 16 baseline form contracts, unique IDs, original dialogs/observer anchors and actual host composition |
| Seven adapted existing Chromium journeys | **All passed**; all 145 original assertion statements retained |
| Existing visual overview journey | **14 checks passed**; exact-source action above the fold, source reader, keyboard disclosure, case isolation and 390px containment |
| New navigation journey | **792 recorded assertions passed** (776 connected, 16 standard launcher), 22 screenshots, zero captured application runtime/console errors; 19.733 seconds |
| Delayed same-case reload regression | Full main browser journey also passed with an intentional 800ms delay of the relevant local state response |
| Syntax and whitespace | `node --check` for changed scripts, Python compilation for browser tests, and `git diff --check` passed |
| Independent review | Four confirmed navigation/layout findings corrected; no unresolved material regression reported after targeted browser verification |

The new navigation journey exercises actual worklist clicks, case/document filtering, generated report links, patient/source/report controls, byte-identical downloaded export, preview switches, draft preservation, blocked and accepted case changes, browser Back, the skip link, mobile tab order and the standard launcher without intake nodes. Its captured application runtime and console error lists are empty.

The new journey also opens and submits all five Options disclosures, verifies invalid native submissions preserve canonical state, and checks persisted proposal, dependency, preparation task, threat and abstention results. Original source records and report review state remain unchanged, and Beta receives no Alpha options.

The existing journeys retain source-read cancellation and response-order tests; exact comparison and inert markup checks; question/manual draft/review/amendment flows; fictional evidence assessment/withdrawal; offline bibliography; duplicate and wrong-patient rejection; canonical Composer/replay/reassessment; Mission/World Model history; and empty-workspace creation through exact file intake and reload.

### Findings resolved during verification

1. The skip link initially changed the route through the hash listener. It now focuses the main landmark without changing the current page or selected case.
2. The initial exact-report navigation revealed its target and then reset focus to the page title. The controller now retains the detail-target intent. A real saved report remains focused and in view.
3. Old setup progress links still pointed Questions and Review to the formerly shared investigation section. The entry presentation adapter now maps them to the actual Questions and Reports destinations.
4. Moving questions out of the original two-column investigation grid left an unused column. Manual drafting now uses the available width.
5. A resolved case-switch veto remained prominent after clearing the draft and successfully loading another case. The presentation controller now dismisses only that resolved warning, verified while retaining the active veto and all original data guards.

### Baseline failures and test-harness corrections

Before product changes, the full Python baseline ran 345 tests and recorded two failing subtests in the literature lock check plus one workspace HTTP timeout. The literature test can observe a complete response before the server's `finally` block releases its lock. The targeted workspace timeout did not reproduce. No backend or existing Python test was changed to obtain a passing result. The final 347-test run passed; this does not establish that those pre-existing intermittent conditions are fixed.

The first new navigation run reproduced the real exact-report focus issue. Later test corrections waited for asynchronous case visibility and accounted for the explicitly labeled link from patient preview to clinical setup. These corrections did not weaken patient-only control checks.

One old main-browser waiter used the unchanged Alpha heading as proof that a same-case reload had finished. A bounded delayed-response reproduction showed that it could submit while `active` was null; the existing readiness guard correctly rejected the action. The test now waits for rendered/ready Alpha and a visible import field. Normal and delayed executions both passed with all duplicate/quarantine assertions retained.

Initial cloud-preview and unavailable-browser attempts are retained as failed environment attempts. Actual verification subsequently used official Chrome 156.0.8078.79 unpacked only into a temporary test directory. Earlier journey runs have their exact recorded product hashes; the final navigation run covers the final controller/CSS, and the final main journey covers the last notice/width changes. The earliest reader/comparison executions recorded post-run hashes only. No earlier run is represented as a measured before/after comparison when it was not one.

## Remaining limits

1. **Presentation separation is not an authorization boundary.** The inspected application has no authenticated patient/clinician roles. The visible selector is explicitly a preview. Real patient/clinician access separation requires separately authorized backend/auth work.
2. **Absent workflows remain absent.** Appointments, medication prescribing/management, care-team messaging, encounter-note editing and account settings were not in this candidate. No placeholder or mock versions were introduced.
3. **The established record/ingestion contract remains limited.** Original `.txt` source ingestion and existing structured imports are retained; PDF/OCR and general clinical extraction were not added.
4. **Existing worklist refresh semantics remain.** Counts can remain stale until the existing initialization/intake refresh owner runs. This predates the redesign; no second data-fetch owner was introduced.
5. **Validation scope is bounded.** Chromium automation, DOM/accessibility-tree checks and visual screenshot inspection were completed. This is not a full WCAG audit, screen-reader study, clinician/patient usability study, or Safari/Firefox/physical-device certification. Live external services were not exercised. Chrome process stderr contains environment DBus/TLS/shutdown messages separately from the empty application error lists.

## Review artifacts

- [Research, IA and design decisions](2026-11-02-research-and-design.md)
- [Complete original feature audit and feature-to-navigation map](2026-11-02-frontend-audit.md)
- [Staged implementation plan](../superpowers/plans/2026-11-02-healthcare-ux-redesign.md)
- [Clinical worklist screenshot](images/2026-11-03-clinician-worklist.png)
- [Patient chart screenshot](images/2026-11-03-clinician-chart.png)
- [Patient home screenshot](images/2026-11-03-patient-home.png)
- [Mobile patient home screenshot](images/2026-11-03-patient-mobile.png)
- [Raw execution evidence archive](evidence/2026-11-03-validation.zip)

## Reproduce

From the repository root, with Python, Node and Chrome/Chromium available:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_*.js
PYTHONPATH=src OI_UI_STANDARD_SMOKE=1 python3 tests/workspace_navigation_journey.py
PYTHONPATH=src python3 tests/browser_journey.py
PYTHONPATH=src python3 tests/browser_source_dialogs.py
PYTHONPATH=src python3 tests/browser_text_changes.py
PYTHONPATH=src python3 tests/composer_browser_journey.py
PYTHONPATH=src python3 tests/patient_mission_browser_journey.py
PYTHONPATH=src python3 tests/ui_glance_journey.py
PYTHONPATH=src python3 tests/workspace_start_browser_journey.py
```

`node --test` aggregates these files; running each test file directly with Node (for example, `node tests/test_workspace_routing.js`) reveals the 80 individual checks. `OI_UI_ARTIFACT_DIR` selects the new journey's screenshots/report directory. Chrome installation is a test-environment prerequisite, not a new application dependency.

## Complete changed-file inventory

The following manifest covers added and modified files relative to the pinned implementation base. No original feature file was deleted.

<!-- Changed-file manifest is generated from the final branch below. -->

| Status | File |
|---|---|
| Added | `docs/superpowers/plans/2026-11-02-healthcare-ux-redesign.md` |
| Added | `docs/ux/2026-11-02-frontend-audit.md` |
| Added | `docs/ux/2026-11-02-research-and-design.md` |
| Added | `docs/ux/2026-11-03-verification.md` |
| Added | `docs/ux/evidence/2026-11-03-validation.zip` |
| Added | `docs/ux/images/2026-11-03-clinician-chart.png` |
| Added | `docs/ux/images/2026-11-03-clinician-worklist.png` |
| Added | `docs/ux/images/2026-11-03-patient-home.png` |
| Added | `docs/ux/images/2026-11-03-patient-mobile.png` |
| Modified | `tests/browser_journey.py` |
| Modified | `tests/browser_source_dialogs.py` |
| Modified | `tests/browser_text_changes.py` |
| Modified | `tests/composer_browser_journey.py` |
| Added | `tests/fixtures/workspace-form-contracts.json` |
| Modified | `tests/patient_mission_browser_journey.py` |
| Added | `tests/test_workspace_redesign.py` |
| Added | `tests/test_workspace_routing.js` |
| Modified | `tests/ui_glance_journey.py` |
| Added | `tests/workspace_navigation_journey.py` |
| Modified | `tests/workspace_start_browser_journey.py` |
| Modified | `web/app.js` |
| Modified | `web/index.html` |
| Modified | `web/intake.css` |
| Modified | `web/style.css` |
| Modified | `web/tokens.css` |
| Modified | `web/workspace-entry.js` |
