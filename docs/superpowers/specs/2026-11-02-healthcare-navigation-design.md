# Healthcare navigation design

Date: 2026-11-02. This pre-implementation proposal was prepared under the user's authorized frontend scope. The final implementation and verification receipt is [recorded separately](../../ux/healthcare-navigation-verification.md).

## Baseline and evidence

The implementation baseline is the connected intake composition in PR #166, commit `334d863b2206b290c02cd2606dcb93c93afe3a68`, tree `d7059e5c178e761e0987a67ff8c220f47e6da2f8`. The older main baseline is `24519839aa8ac1ea3aff88a956349ba72798a72a`. PR #167 is a competing, unmerged intake implementation; do not combine it with #166.

The inventory below comes from a read-only audit of the materialized source: `web/index.html`, `web/app.js`, `web/mission.js`, `web/world-model.js`, `web/composer.js`, `web/literature.js`, `web/intake.js`, `web/workspace-entry.js`, `web/workspace-entry.html`, and the existing route/composition code. Repository instructions, README, first-principles plan, and relevant backlog rows were consulted. Relevant work packages are OI-007 (questions/scoped review), OI-009 (amendments), OI-010 (connected demonstration), and OI-021 (derived options).

Pre-implementation evidence: **345 Python tests pass** on this baseline. At the source-audit checkpoint, local browser provisioning was still pending. The unchanged baseline was subsequently captured at desktop and mobile sizes with an installed Chromium browser. Final named JavaScript counts, browser evidence, and before/after captures are in the verification receipt. No actual patient records were acquired or used.

## Goal and boundaries

Replace the long mixed-audience document with familiar patient and clinician navigation while retaining every existing connected feature and its meaning. Patients need clear destinations for understanding their record, finding documents, raising questions, and reviewing changes. Clinicians need a workspace, a searchable existing case list, a selected-patient chart, and a separate research library.

- No backend, API, authentication, schema, or business-logic changes.
- Use the same permanent DOM nodes and existing handlers; no second case, source, question, evidence, or review store.
- Do not call `refresh()` for page-only navigation.
- Use existing served frontend assets; no new server pathname routes or asset-serving requirements.
- The patient/clinician switch is a development preview of presentation only; it grants no authority or access.
- Preserve synthetic-only scope, original-source traceability, separate uncertainty states, historical versions, and demo-review limitations.
- Public bibliography/literature metadata remains ephemeral and not case-linked.
- Do not fabricate appointments, messaging, medication management, profiles, professional authentication, clinical recommendations, or other absent capabilities.
- No actual patient data, patient-derived fixtures, or external commitments are introduced.

## Research and design implications

These are official published references for navigation patterns, not evidence that Open Intelligence has their services or security model. No signed-in vendor workspace was inspected. The decisions in the final column are our design inferences.

| Reference | Observed pattern | Application here |
|---|---|---|
| [UCLH MyCare Patient Companion][S1] | Patient homepage separates its main menu, frequent shortcuts, and a health-update feed. | Make patient destinations plain and stable; put current workflow orientation on Home, with documents and questions directly reachable. Do not copy the vendor's appointment or messaging capabilities. |
| [athenahealth: efficient practice-management workflows][S2] | Describes role-focused workspaces and surfacing work requiring attention. | Separate clinician worklist and patient chart; show only the existing recorded review/change states. Do not infer urgency or implement role authorization. |
| [NHS App release notes, 4.58, 19 March 2026][S3] | Documents a new Home screen and three primary areas: Home, Messages, and Profile. | Borrow the small, clearly named top-level navigation, not the unavailable Messages/Profile features. |
| [VA authenticated-home template][S4] | Distinguishes dashboard, category, feature, and detail pages, with tasks/status/navigation as goals. The page is explicitly a candidate target state. | Distinguish Workspace, Patients, Patient chart, and local chart sections. Treat this as design guidance, not a verified production screenshot. |

[S1]: https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/mycare-patient-companion
[S2]: https://www.athenahealth.com/resources/blog/athenaone-efficient-practice-management-workflows
[S3]: https://www.nhs.uk/nhs-app/about/nhs-app-release-notes/
[S4]: https://design.va.gov/templates/home-pages/authenticated

## Information architecture

Navigation labels are the user-facing contract. New fragment spellings are a frontend implementation choice; existing fragments must continue to work. All destinations use the same selected case and original nodes.

| Patient destination | Existing content and purpose |
|---|---|
| **Home** | Current document/question/report counts, recent recorded updates, source-review status, and direct tasks. Link to the original Patient Mission detail in My health records. |
| **My health records** | Plain-language patient view, reported findings, chronology, and access to source-backed detail; preserve uncertainty and the World Model disclosure. |
| **Questions & reports** | Existing durable questions, saved report history, source citations, export, and original report status. Clinician draft/Composer authoring and demo acknowledgment controls remain in the clinician preview. |
| **Documents** | Original-source history, explicit source intake, pasted-report import, historical versions, and quarantine feedback. |
| **Updates** | Changes since review and recent activity, with stale history distinguished from current unresolved work. |
| **Workspace setup** | Existing creation form and five-step journey; creation remains fictional workspace setup, not patient registration. |

| Clinician destination | Existing content and purpose |
|---|---|
| **Workspace** | Bounded summary and links to recorded work requiring review; no invented triage or task urgency. |
| **Patients** | Existing incoming board and picker; local search/filter over the already available fictional case labels/references. No new search API. |
| **Patient chart** | Selected case with local **Overview / Timeline / Documents / Investigations / Evidence / Discussion options / Updates** navigation. |
| **Research library** | Existing DOI and public-term metadata discovery, visibly independent of the patient chart. |
| **Workspace setup** | Existing creation and journey controls. |

Chart Overview owns existing findings, counts, review context, and the expandable Patient Mission/World Model source-projection detail. The same record-status component appears in My health records in patient preview. Timeline owns source chronology and the Source Change Explorer. Documents owns intake, originals, import, quarantine, and expandable specimen/biological provenance. Investigations owns questions, human draft, Composer, model runs, saved reports, review handoff, and exports. Evidence owns fictional sources/assessments/withdrawal. Discussion options owns all five option forms. Updates owns changes since review and activity. A section reused by both presentation modes is moved or shown as the same node, never cloned.

## Exhaustive feature and section preservation map

Line references identify the inspected #166 source, before implementation edits.

| Existing surface / IDs | Audience and retained behavior | Owner reference |
|---|---|---|
| Header, `case-picker`, `workspace-nav`, `main-content`, `notice` | Shared identity, case context, navigation, skip link, global status feedback. Keep one case picker. | `index.html:18`; `app.js::initialize`, `notice`, `focusOverviewFromCasePicker` |
| `overview`, `case-heading`, `metrics` | Shared case label and existing source/finding/question/review counts; current navigation actions. | `index.html:60`; `app.js::render` |
| `assertions`, `assertion-list` | Clinician detail/shared source facts; each finding retains certainty and exact-line inspection. | `index.html:73`; `app.js:409` |
| `review-attention`, its heading/summary, glance guide | Recorded freshness and source-review guidance; links to real investigations, timeline, and originals. | `index.html:82`; `app.js:370` |
| `incoming-board`, `incoming-list` | Clinician/operator list sorted by latest source-event date; Open this case uses the picker handler. | `index.html:101`; `app.js::renderIncomingBoard` |
| `patient-view`, `patient-timeline`, `patient-findings`, `patient-questions`, `patient-uncertainty` | Patient-facing read-only projection of the same facts, with pending/indeterminate/conflicting states intact. | `index.html:106`; `app.js::renderPatientView` |
| `patient-mission`, `mission-status`, `mission-summary`, `mission-known`, `mission-unresolved`, `mission-changes`, `mission-actions`, `mission-guardrails` | Patient/shared workflow projection. Next-action cards describe existing workflow; they are not executed actions. | `index.html:115`; `mission.js::renderMission`, `renderActions` |
| `world-model-detail` and its status/summary/observations/conflicts/history | Shared expandable provenance projection; source disagreements remain unadjudicated, historical versions remain inspectable. | `index.html:134`; `world-model.js::refresh`, `render` |
| `timeline`, `timeline-filter`, `timeline-events`, `source-change-list` | Shared record-type filter, grouped events, every version's original text, consecutive-version comparison, affected draft counts. | `index.html:149`; `app.js::renderTimeline`, `renderSourceChanges` |
| `investigations`, question/draft panes, `question-list`, source/evidence choices | Shared question capture; clinician/research authoring bound to exact source versions. | `index.html:177`; `app.js:773`, `781` |
| `snapshot-list`, generated `snapshot-ID` | Shared saved reports, source-bound export, model-origin citations, separate demo acknowledgment, stale historical snapshots. | `index.html:216`; `app.js:523`, `downloadSnapshot`, `appendReviewCitations` |
| `model-investigation-heading`, model form/list, `composer-context`, fingerprint, run button | Bounded template/replay/live selection; exact preview anchors; current fingerprint gate; hypothesis history; prepare review draft. | `index.html:220`; `composer.js`; `app.js::loadModelInvestigations`, `prepareModelReviewDraft` |
| `sources`, `source-list` | Shared all-version source history, dates/digest, original text inspection. | `index.html:239`; `app.js:395` |
| `biological-assets`, `asset-list` | Clinician/research read-only provenance and inventory assertions; unknown and stale states retained. No file-management/shipping actions. | `index.html:243`; `app.js::renderBiologicalAssets` |
| `activity`, `event-list` | Shared last 12 event names/times; also an observer target for Mission and World Model. | `index.html:247`; `app.js:573` |
| `evidence`, evidence disclosures/lists | Clinician/research fictional evidence registration, exact text, human applicability assessment, withdrawal with dependent invalidation. | `index.html:253`; `app.js:828` |
| `options`, `option-list`, `option-disclaimer` | Clinician/research discussion proposals, dependencies, preparation tasks, threats, scoped review, derived states/history. | `index.html:297`; `app.js::renderOptions` |
| `bibliography`, DOI result/status, literature result/status/feedback | Public metadata example/lookup/search/clear and canonical external links. No case linkage, saving, full-text appraisal, or treatment inference. | `index.html:357`; `app.js::renderBibliography`, `initializeBibliography`; `literature.js` |
| `import`, `report-text`, `example-button`, `quarantine-list` | Shared/operator original structured-text import and explicit amendment example; quarantine remains visible. | `index.html:387`; `app.js:808` |
| `changes-since-review`, anchor/disclaimer and four result lists | Shared read-only new sources, mechanical amendment differences, stale causes, and new questions since recorded anchor. | `index.html:403`; `app.js::loadChangesSinceReview`, `renderChangesSinceReview` |
| `workspace-start`, `new-case-panel`, `journey-steps`, `new-workspace-button` | Shared fictional workspace creation and journey projection. Preserve empty-state onboarding. | `workspace-entry.html:1`; `intake.js::journey`, `mount`; `workspace-entry.js` |
| `source-intake`, selected-case label, file/preview/confirmation/status controls | Shared explicit UTF-8 `.txt` intake, local original-text preview, no automatic upload, duplicate/quarantine feedback. | `workspace-entry.html:19`; `intake.js::decodeSource`, `mount` |
| `source-dialog`, `compare-dialog` and all title/context/text/close nodes | Shared global modals; literal source text, exact-line highlights, before/after text, Escape/close cancellation. Keep outside hidden pages. | `index.html:417`; `app.js::openSource`, `openEvidence`, `openComparison` |

### All 16 forms and actions

Preserve each original form, control ID, validation rule, payload, and submit handler. The first two exist only in the composed entry host.

| Form ID | Retained inputs and operation | Handler |
|---|---|---|
| `case-create-form` | Alias, uppercase reference, fictional-data attestation; create case. | `intake.js:51`; `workspace-entry.js:17` |
| `source-upload-form` | Pending validated original text and fresh confirmation; case source import. | `intake.js:84` |
| `question-form` | Question text; durable case question. | `app.js:773` |
| `draft-form` | Question, source IDs, evidence IDs, observations/hypothesis/assumptions; save snapshot. | `app.js:781` |
| `model-investigation-form` | Question, template, replay/live mode, current fingerprint; bounded run. | `app.js:1322` |
| `evidence-import-form` | Original fictional evidence text; register global evidence version. | `app.js:834` |
| `evidence-assessment-form` | Question, evidence version, relationship, applicability, rationale; record assessment. | `app.js:843` |
| `evidence-withdraw-form` | Current evidence and reason; withdraw and invalidate dependents. | `app.js:858` |
| `option-form` | Snapshot, label, description, epistemic state; propose discussion option. | `app.js:870` |
| `option-dependency-form` | Option, dependency kind/target, lead time, sourced date/basis/anchor. | `app.js:883` |
| `option-task-form` | Option, label, human owner, lead time; preparation task. | `app.js:903` |
| `option-threat-form` | Option, kind, description, sourced date/basis/anchor; optionality threat. | `app.js:917` |
| `option-review-form` | Option, reviewer label, action, scope, replacement snapshot; recorded review action. | `app.js:932` |
| `bibliography-form` | Public DOI; operator-gated metadata lookup. | `app.js:1063` |
| `literature-search-form` | Public human-authored terms and fresh attestation; metadata search. | `literature.js::search` |
| `import-form` | Original structured report text; case source import. | `app.js:812` |

Also retain card actions for demo acknowledgment (`app.js:542`), model-to-review handoff (`prepareModelReviewDraft`), export, source/evidence inspection, version comparison, explicit example loading, metadata clearing, and canonical external links. Do not relabel a demo acknowledgment as professional sign-off.

## Implementation contracts and failure prevention

1. **Permanent nodes.** `app.js` is the state owner (`caseId`, `active`, `refreshSequence`, `renderedCaseId`). The entry adapter uses its bare global symbols. Do not change script module scope, clone forms, duplicate IDs, unmount inactive content, or serialize original nodes through `innerHTML`.
2. **Observer targets.** Keep the same `event-list`, `model-investigation-question`, `case-heading`, `source-list`, `question-list`, and `snapshot-list` elements. Mission, World Model, Composer, and entry have direct references/MutationObservers. Hide page containers without disabling their existing data/render lifecycle.
3. **Unsaved work.** Same-case navigation and preview switching retain every input, selected source/evidence binding, file preview, and disclosure state. The existing case-switch guard checks only `draft-observations`, `draft-summary`, `draft-assumptions`, `evidence-rationale`, `evidence-withdraw-reason`, and `option-description`; preserve it without claiming general autosave or unload protection. Accepted case switches retain existing reset behavior.
4. **Data freshness.** Keep `readyCase()`, refresh/source/model sequence checks, Composer fingerprint validation, and source-lineage checks. Do not call `refresh()` for page-only navigation; its renderer rebuilds select options, including the model question. Navigation must not issue writes.
5. **Anchors and focus.** Resolve old hashes to the owning visible page, including `#overview`, `#main-content`, `#workspace-start`, `#source-intake`, `#model-investigation-heading`, and dynamic `#snapshot-ID`. Handle direct load, back/forward, click, and late-rendered targets. Reveal the page before scrolling/focusing. Keep the skip link, current-page indication, visible focus, keyboard operation, and mobile navigation usable. Inactive pages must not expose tabbable controls.
6. **Global dialogs and notice.** Keep source/comparison dialogs outside hidden pages and preserve native Escape behavior. Make existing global feedback visible from each page. Do not attach a generic modal `close` listener that invalidates a newer read; existing code intentionally uses `cancel` and explicit close controls.
7. **Empty startup.** The composed entry sets `body.dataset.workspaceState`. `intake.css:14` currently hides direct `.main` children except overview/setup/notice. Adapt frontend selectors to the new wrappers so empty startup, first creation, and loading transitions remain usable.
8. **Host composition.** `workspace_host.py::workspace_html` performs seven exact, single-occurrence replacements. Preserve these literals in `index.html`: the original `/style.css` link; `/app.js` script; `/literature.js` script; `<body>`; the paragraph prefix `<p class="muted tiny">Fictional case data stays`; `<a href="#sources">Sources and findings</a>`; and the original six-space-indented metrics div. Runtime reparenting can reorganize them without backend edits.
9. **Existing serving/security boundary.** `/` and `/index.html` serve the document; static assets use an allowlist. Implement shell code in existing `/app.js`, using existing CSS assets. Keep loopback Host/Origin checks and same-origin CSP untouched. The preview switch must never be presented as access control.

## Acceptance and evidence to produce

- Both agreed navigation systems and every local Patient chart section are reachable at desktop and narrow widths; all 16 original forms and card actions remain connected.
- Old section hashes and generated snapshot links reveal their owning page, including reload/history and a target created after initial render.
- Same-case page/preview changes preserve form values, source/evidence selection, and selected-file preview without an API refresh or write.
- Accepted/rejected case switches, delayed responses, source dialogs, original-text comparisons, and Composer fingerprint gates retain their behavior.
- Empty workspace creation, original import, question, replay investigation, report handoff, demo review, amendment, and stale historical export work through the composed host with independently authored fictional inputs.
- Patient search filters existing labels/references locally; no results, urgency, counts, or capabilities are invented.
- Record actual Python and JavaScript results; distinguish named checks from test-file counts. Capture desktop/mobile views if a local browser becomes available; state the exact browser blocker if it does not.
- Obtain an independent final review focused on feature preservation, navigation/accessibility, and absence of backend/API/auth/business-logic changes. This review does not create a new user-approval requirement.
