# Healthcare navigation redesign: implementation and verification

Date: 2026-11-03. Scope: frontend presentation and its regression coverage.

The former continuous, mixed-audience workspace now has distinct patient and clinician navigation, a dedicated patient chart, and progressive disclosure of secondary details. Existing components, source records, form handlers, and services remain the implementation foundation.

This candidate builds on the connected intake implementation in PR #166: commit `334d863b2206b290c02cd2606dcb93c93afe3a68`, tree `d7059e5c178e761e0987a67ff8c220f47e6da2f8`. It does not combine the competing intake implementation in PR #167. The original 222-file snapshot was checked against its Git blob hashes before editing. The original backend, fixtures, and data-processing code are unchanged.

The [pre-implementation design and complete audit](../superpowers/specs/2026-11-02-healthcare-navigation-design.md) records the research sources, existing state owners, all 16 forms, composition constraints, and preservation requirements. The [implementation plan](../superpowers/plans/2026-11-02-healthcare-navigation.md) records the execution checklist.

## Research translated into the design

Official published guidance was used; no authenticated competitor account or private clinician environment was accessed. These are design inferences applied to this application's actual capabilities.

| Reference | Useful pattern | Application in this candidate |
|---|---|---|
| [UCLH MyCare / Epic MyChart patient companion](https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/mycare-patient-companion) | Separate stable navigation, frequently used tasks, and a feed of updates. | Patient Home provides direct access to records, documents, and questions, with recent activity and existing review status. |
| [athenaOne workflow guidance](https://www.athenahealth.com/resources/blog/athenaone-efficient-practice-management-workflows) | Distinguish the clinician's working context and work requiring attention from an individual record. | Workspace and Patients are global destinations; Patient chart owns its own local navigation and selected-record context. |
| [NHS App release notes](https://www.nhs.uk/nhs-app/about/nhs-app-release-notes/) | The March 2026 redesign documents a small set of primary destinations and frequent tasks on Home. | Use plain, stable labels and expose only services that this application implements. |
| [VA authenticated-home template](https://design.va.gov/templates/home-pages/authenticated) | Distinguish dashboard, category, feature, and detail levels. This reference is a candidate target state, not proof of universal deployment. | Separate global navigation, chart sections, and disclosures; keep loading, empty, and no-match states visible at their relevant level. |

The products' appointment, prescription, messaging, and professional-role capabilities were not copied into a frontend whose backend does not provide them. Patient and clinician presentation share the existing case owner, while labels and entry points reflect different tasks.

## Delivered information architecture

| Experience | Global navigation | Local organization |
|---|---|---|
| Patient | Home; My health records; Questions & reports; Documents; Updates; Workspace setup | Plain-language findings and uncertainty first; chronology and detailed source context expand on demand. Existing questions and saved reports share their original nodes with the clinician view. |
| Clinician | Workspace; Patients; Patient chart; Research library; Workspace setup | Workspace resumes recorded work. Patients searches actual labels/references. The selected chart has Overview, Timeline, Documents, Investigations, Evidence, Discussion options, and Updates. |

The patient Home shows current document, open-question, and saved-report counts; three direct tasks; the latest three recorded events; and the existing source-review state. Counts describe recorded data, not clinical urgency. The clinician Workspace shows available workspaces, open questions for the selected record, a chart continuation action, review changes, and records opened in the current session. The directory retains its original source-event ordering.

Desktop uses a persistent sidebar and a separate chart navigation row. Narrow screens use a native collapsible navigation menu and a horizontally scrollable chart navigation row. The selected record remains explicit on record pages. Forms, disclosures, buttons, source links, and focus indicators have consistent styling; inactive pages are hidden and inert.

## Existing features and their new locations

| Existing feature | Patient location | Clinician location |
|---|---|---|
| Case selection and current identity | Shared case selector; My record banner | Shared case selector; selected-patient chart banner |
| Incoming case board and existing Open action | Available through clinician preview | Patients, with local label/reference search |
| Source-linked findings, counts, review attention | Home summary and My health records | Patient chart → Overview |
| Patient-readable chronology, findings, questions, uncertainty | My health records | Explicit patient preview remains available |
| Patient Mission and World Model source/conflict/history inspector | My health records → Record status and source detail | Chart Overview → Record status and source detail; direct inspector link |
| Source timeline, record-type filter, amendments, original-version comparison | Plain-language chronology in My health records; full version-comparison workflow in clinician preview | Patient chart → Timeline |
| Durable questions | Questions & reports | Patient chart → Investigations |
| Human-authored investigation draft and source/evidence choices | Saved results remain readable in Questions & reports | Patient chart → Investigations |
| Composer, replay/live selection, context fingerprint, model history, report preparation | Saved results remain readable in Questions & reports | Patient chart → Investigations |
| Saved report history, citations, source inspection, export, original status | Questions & reports | Patient chart → Investigations |
| Explicit demo acknowledgment | Status is readable; action belongs to clinician preview | Patient chart → Investigations |
| Original documents, versions, dates, digests, exact text | Documents, with local search and version filter | Patient chart → Documents, with the same search/filter |
| Actual file selection, original preview, confirmation, import | Documents → Add a document | Patient chart → Documents → Add a document |
| Structured pasted-source import, explicit example, quarantine | Documents → Paste a structured source | Patient chart → Documents → Paste a structured source |
| Specimen/biological provenance and inventory assertions | Documents → Specimen and biological records | Patient chart → Documents → Specimen and biological records |
| Evidence registration, original-text inspection, assessment, withdrawal | Available through clinician preview | Patient chart → Evidence |
| Discussion option, dependency, preparation task, threat, reviewer action | Available through clinician preview | Patient chart → Discussion options; five separate disclosures |
| DOI and public-term citation metadata search/clear | Available through clinician preview | Research library; still independent of a patient record |
| Changes since review, original activity/event history | Updates | Patient chart → Updates |
| Fictional workspace creation and existing five-step journey | Workspace setup | Workspace setup; creation shortcut from Patients |
| Exact-source and comparison dialogs, global notices | Shared and kept outside hidden pages | Shared and kept outside hidden pages |

## Preservation and role handling

The original app has no authenticated patient/doctor role system. The selector is explicitly labelled **Preview experience**, with explanatory text that it presents the same fictional data without changing access. No authentication, authorization, or permission rule was introduced or altered.

The shell moves existing DOM nodes; it does not clone forms, reconstruct file inputs, or introduce another case store. All 16 forms and their controls retain object identity across page and preview changes. Shared questions, report history, Patient Mission, and World Model detail move between the appropriate destinations. Original observers, data bindings, payloads, and submission handlers remain attached.

Page navigation performs no canonical refresh or API write. Reopening the already-selected record through either the recent-record list or the directory also preserves inputs and selected-file previews. A real case change continues through the original guarded picker path. This preserves the existing guard's scope; it does not add autosave or promise that unsaved values survive a browser reload.

The seven literal host-composition anchors remain intact. Source and comparison dialogs remain body-level native dialogs, preserving exact text, Escape, close/cancel ordering, and source-version identity. No new server route, frontend framework, package, font, or external runtime asset was added.

## Changed files

| Frontend file | Change |
|---|---|
| `web/app.js` | Presentation shell, route/legacy-fragment resolution, same-node placement, actual-data summaries, local directory/document filters, navigation focus, same-case no-op selection. Domain submission handlers remain intact. |
| `web/index.html` | Preview selector, page heading, selected-record heading, chart navigation landmark, and loading status. Original form IDs and composition anchors remain. |
| `web/style.css` | Scoped sidebar/page/chart layouts, hierarchy, rows, disclosures, focus/current states, and responsive controls. |
| `web/intake.css` | Empty-state compatibility and narrow intake layout. |
| `web/workspace-entry.js` | Two presentation navigation calls connect the existing creation flow to setup and intake destinations. |

Test infrastructure: `tests/test_navigation_shell.js` and `tests/workspace_navigation_browser_journey.py` are new. `tests/browser_journey.py` and `tests/ui_glance_journey.py` now navigate to the relevant visible pages while retaining their original domain assertions. `.github/workflows/ui-glance.yml` runs the complete JavaScript suite and the navigation, connected-intake, Composer, Mission, source-dialog, existing workflow, and glance journeys. Documentation records the audit, mapping, implementation, verification, and relevant backlog evidence.

## Functional verification

All browser inputs are independently authored fictional examples. Browser: Google Chrome **156.0.8078.79**, running the real local app against temporary SQLite databases. No live model or public literature service was enabled.

| Check | Result and coverage |
|---|---|
| Python/HTTP regression suite | **345 passed**, same count as the baseline. |
| JavaScript suite | **80 passed**: 71 existing named checks and nine navigation checks. No failures or skips. |
| Navigation browser journey | **774 assertions passed**, including 51 responsive page checks and 26 final captures. All 16 forms and original observer targets retain their nodes. Page/preview navigation causes no API writes or case refreshes; the journey records only its five deliberate form POSTs. |
| Original integrated browser journey | Source drilldown, versions/comparison, keyboard/accessibility, case guard, questions/drafts, acknowledgment, amendment invalidation, historical export, evidence assessment/withdrawal, offline bibliography, duplicate rejection, quarantine, and narrow layout passed. All five discussion-option forms also submit through visible controls and are checked against rendered and durable records: proposal, exact-source dependency, human-owned task, unknown-date threat, and scoped reviewer abstention. |
| Connected workspace journey | Empty database → case creation → actual file selection and exact original-text import → timeline → question → replay → report → explicit demo review → amended file → stale/open state → replacement draft → reload passed. |
| Composer journey | Source-bound context, replay, review handoff, stale denial, case isolation, amendment/reassessment, World Model refresh, and historical report preservation passed. |
| Source-dialog journey | Actual Close, native Escape, A–B–A switching, out-of-order source reads, and unrelated-comparison rejection passed. |
| Patient Mission journey | Existing workflow-projection regression completed with exit status 0. |
| Glance/layout journey | **13 checks passed**. Findings visible, authoring mounted but hidden/inert, all five findings retain exact-source actions, native keyboard disclosure, case isolation, and desktop/mobile containment. The first exact-source action ended at **824.94 px** in the 1440 × 900 viewport, within the existing 900-pixel requirement. |
| Scope and composition | No diff in backend, runner, processing tools, or example fixtures. The existing composition function accepted all seven exact anchors and produced all 16 forms. JavaScript syntax and whitespace checks passed (recognizing the backlog CSV's existing CRLF endings). |

The navigation journey exercises all destinations at 1440, 390, and 320 pixels; checks DOM identity and source/evidence/Composer/file state; audits network requests; submits real questions, evidence, an assessment, and a draft; tests accepted and rejected case changes; and verifies browser history, disclosure deep links, late report anchors, both preview modes, and native mobile keyboard navigation. The only resource-level error observed was the pre-existing missing `/favicon.ico`; no new JavaScript exceptions or console errors were introduced.

### Review findings resolved

An independent source and Chromium review found four actionable navigation defects before delivery. Each was reproduced, corrected, and independently rechecked:

1. Reopening the selected chart unnecessarily dispatched a case change and cleared local inputs. Both recent-record and directory actions now navigate directly for the selected case.
2. Tab from the case picker targeted a link inside a closed mobile menu. It now reaches the visible Navigate summary.
3. Initial disclosure links could remain closed, including an intake initialization race. Resolution now waits for the existing entry adapter's ready state.
4. A startup `#main-content` URL skipped shell initialization. The skip-link shortcut now applies only after initialization.

Shared Mission/World Model nodes were additionally checked for object identity, contextual placement, preserved audience, and no refresh. The independent final review reported no outstanding blocker.

## Reproduce locally

The repository's existing Python and Node runtimes are sufficient for application/unit checks. Browser journeys also require an installed Chrome or Chromium binary. The browser is a verification tool, not an application dependency.

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/test_*.js
PYTHONPATH=src python3 tests/browser_journey.py
PYTHONPATH=src python3 tests/workspace_start_browser_journey.py
PYTHONPATH=src python3 tests/composer_browser_journey.py
PYTHONPATH=src python3 tests/patient_mission_browser_journey.py
PYTHONPATH=src python3 tests/browser_source_dialogs.py
PYTHONPATH=src python3 tests/ui_glance_journey.py
OI_UI_ARTIFACT_DIR=ui-artifacts/navigation python3 tests/workspace_navigation_browser_journey.py
```

The final navigation command supports `OI_CHROME_EXECUTABLE` for an explicit installed browser path. Its artifact directory contains the machine-readable report and viewport captures. CI uploads the corresponding fictional evidence and exact source under test.

For the UI, `python3 run_open_intelligence.py --db /tmp/oi-navigation-demo.sqlite --port 8931` opens the existing empty-workspace flow at `http://127.0.0.1:8931`. The existing synthetic seed command can populate a separate development database when desired.

## Captures and limits

Selected genuine browser captures accompany this receipt. The unchanged baseline was captured separately from the edited source. The after views use actual records, forms, and stored results from the fictional test application.

- [Original continuous desktop workspace](captures/before-desktop.png)
- [Clinician Workspace](captures/clinician-workspace.png)
- [Dedicated patient chart](captures/patient-chart.png)
- [Patient Home](captures/patient-home.png)
- [Patient Home at 390 pixels](captures/patient-home-mobile.png)

This is a frontend candidate, not a deployment, clinical validation, authenticated-role implementation, or cross-browser certification. Chrome desktop and narrow viewport behavior were exercised; Safari, Firefox, native mobile browsers, and a human screen-reader session were not exercised. Existing role/security rules, backend contracts, record-keeping logic, and domain uncertainty are preserved.
