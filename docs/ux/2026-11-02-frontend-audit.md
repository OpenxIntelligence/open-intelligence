# Frontend source audit and feature-preservation inventory

**Date:** 2 November 2026  
**Audited candidate:** connected-workspace PR #166, commit `334d863b2206b290c02cd2606dcb93c93afe3a68`  
**Documented main checkpoint:** `24519839aa8ac1ea3aff88a956349ba72798a72a` (`24519839`)  
**Scope:** source inspection and presentation planning only

## 1. Evidence, scope and baseline

The audit inspected the materialized PR #166 candidate before the proposed presentation redesign. Its local Git HEAD was checked as `334d863b2206b290c02cd2606dcb93c93afe3a68`. The main checkpoint above is the repository's documented comparison baseline; candidate functionality must not be described as merged main functionality or deployed software. This audit did not independently recheck the current remote main branch.

Read sources include `AGENTS.md`, `README.md`, `README_WORKSPACE.md`, relevant implementation and execution-audit documentation, `docs/FIRST_PRINCIPLES_PLAN.md`, applicable execution-backlog rows, and the frontend files below:

- `web/index.html`, `web/workspace-entry.html`.
- `web/app.js`, `web/intake.js`, `web/workspace-entry.js`, `web/mission.js`, `web/world-model.js`, `web/composer.js`, `web/literature.js`.
- `web/style.css`, `web/tokens.css`, `web/base.css`, `web/intake.css`.
- Read-only inspection of `src/open_intelligence/workspace_host.py` to identify the existing host's exact frontend-template anchors.

The audited application is one scrolling case workspace with hash anchors. The connected launcher composes case creation and original-file intake into that existing page. There are **16 forms: 14 in `index.html` and two in `workspace-entry.html`**. It is a vanilla HTML/CSS/JavaScript frontend over the existing local synthetic ledger. The documented React/Vite/TypeScript target is not the implementation delivered in this candidate.

This document contains no screenshot findings. The auditor did not run a browser journey or tests and did not edit application code, tests, backend files, or other documents. Source inspection establishes the implemented controls and their contracts; it does not establish their rendered appearance, successful live service execution, or clinical validity.

The planned work is a presentation preview. It must preserve backend behavior, APIs, authentication boundaries, validation, business rules and data processing. Preserve the original forms and their live DOM elements when changing layout. No appointment, medication-management, messaging/chat or administration feature is introduced by this inventory.

## 2. Proposed information architecture

Patient and clinician are presentation audiences. There is no verified user role, patient identity or clinical permission behind either view. The source has a static `data-audience="clinician"` attribute, but no role switch or authorization behavior. A new presentation selector must be described accordingly.

### Patient navigation

| Primary destination | Target | Existing content to retain |
|---|---|---|
| Home | `#patient-home` | New presentation landing surface for the existing case/workflow context. It must not invent patient facts or a second case state. |
| My record | `#patient-view` | The complete existing plain-language patient record, with chronology, reported findings, questions and uncertainty. |
| Documents | `#sources` | Existing source history and access to original versions; links to original-record intake and amendment import. |
| Questions & reports | `#questions`, `#reports` | Subnavigation to existing questions and saved reports/history. Preserve their original controls and original investigation anchor. |
| Updates | `#changes-since-review` | Existing anchored change listing and access to activity/version comparisons. |
| Workspace setup | `#workspace-start` | Existing connected setup/create/intake journey. |
| Research library, in secondary tools | `#bibliography` | Existing DOI and public-literature metadata discovery, independent of the case. |

`#patient-home`, `#questions` and `#reports` are proposed new presentation targets, not routes present in the audited baseline. Existing `#patient-view` remains the full plain-language record and is not replaced by a smaller home summary.

### Clinician navigation

Global navigation: **Patients/worklist** (`#incoming-board`), **Research library** (`#bibliography`), and **Workspace setup** (`#workspace-start`). Within the selected clinical chart:

| Chart destination | Targets and subroutes |
|---|---|
| Overview | `#overview` |
| Record | `#assertions`, `#timeline`, `#patient-mission`, `#biological-assets`; retain World Model detail within its existing source projection |
| Documents | `#sources`, `#source-intake`, `#import` |
| Investigations | `#questions`, `#investigations` for the manual draft, `#model-investigation-heading`, `#reports` |
| Evidence | `#evidence`, `#options` |
| Review/history | `#changes-since-review`, `#activity` |

All existing capabilities remain reachable. Audience defaults change navigation and explanatory emphasis; they do not create permissions. Global case selection, notices and source dialogs must remain coherent across chart destinations.

## 3. Complete feature-to-navigation inventory

Source shorthand below: **I** = `web/index.html`; **A** = `web/app.js`; **E** = `web/workspace-entry.html`. Other script names are under `web/`. Audience means presentation suitability only: **P** patient, **C** clinician/research operator, **S** shared.

| Existing surface and source anchors | Existing functionality and actions | Audience | Planned location |
|---|---|---|---|
| I/A: header, `.brand`, `.skip-link`, `#main-content`, `#workspace-nav`, `.section-menu` | Brand-to-overview link; skip link; section anchors; current hash receives `aria-current="location"`; mobile disclosure behavior. | S | Persistent global shell and chart navigation. |
| I/A: `#case-picker`, `initialize()`, `renderIncomingBoard()` | List/select cases; canonical-state reload; narrative dirty guard may veto; special Tab-to-overview focus behavior. | S | Persistent selected-case context. |
| E, `workspace-entry.js`, `intake.js`: `#workspace-start`, `#new-workspace-button`, `#journey-steps` | Setup disclosure; five workflow progress links; empty-workspace orientation. | S | Workspace setup; entry from patient Home and global navigation. |
| E/`intake.js`: `#new-case-panel`, `#case-create-form` | Fictional alias/reference and confirmation; create workspace; inline progress/error/result. Creates a ledger case, not an account. | S | Workspace setup. |
| E/`intake.js`: `#source-intake`, `#source-upload-form`, `#source-preview-details` | Choose original `.txt`, inspect exact text/subject/byte count, confirm, explicitly import; duplicate/quarantine feedback. No automatic upload on file selection. | S | Documents → Add original records. |
| I/A: `#overview`, `#case-heading`, `#metrics`, `#review-attention` | Case heading; current sources, reported statements, open questions and active review-required counts; review state and navigation actions. | S | Clinician Overview; existing context informs patient Home. |
| I/A: `#incoming-board`, `#incoming-list` | All-case worklist ordered by most recent source event; current-source/open-question/stale-history counts; Open this case button. No triage priority. | C | Patients/worklist. |
| I/A: `#patient-view`, `#patient-timeline`, `#patient-findings`, `#patient-questions`, `#patient-uncertainty` | Full plain-language chronology, quoted findings and certainty, open questions, amendments and stale-history explanations. | P | My record, retained in full. |
| I/`mission.js`: `#patient-mission`, `#mission-status`, `#mission-summary`, `#mission-known`, `#mission-unresolved`, `#mission-changes`, `#mission-actions`, `#mission-guardrails` | Read-only workflow status/counts, current source statements, unresolved source states/questions/stale investigations/quarantines, changes, bounded next-action descriptions and guardrails. Action cards are not buttons. | S | Record → Patient Mission; patient context links remain available. |
| I/`world-model.js`: `#world-model-detail`, `#world-model-status`, `#world-model-summary`, `#world-model-observations`, `#world-model-conflicts`, `#world-model-history` | Lazy disclosure of exact source observations/version/line/hash/dates; source disagreements; review IDs and historical versions. First 30 observations/history items with explicit limit notices. | S/C detail | Record → Patient Mission → Source provenance detail. |
| I/A: `#assertions`, `#assertion-list` | Finding keys, source quotations, distinct certainty labels, exact-line source-inspection buttons; disabled unavailable-source control. | S | Record → Reported findings; patient record/document links. |
| I/A: `#timeline`, `#timeline-filter`, `#timeline-events` | All/pathology/imaging/molecular/laboratory/clinical/other filter; original event/specimen grouping; separate event/issue/receipt dates; inspect every version. | S | Record → Timeline. |
| I/A: `#source-change-list` | Source Change Explorer; affected snapshot/open-question counts; compare original versions; open earlier/current version. | S | Record → Timeline and Updates/Review links. |
| I/A: `#sources`, `#source-list` | Source/version history, current/superseded state, dates and SHA prefix; View original text. | S | Documents. |
| I/A: `#biological-assets`, `#asset-list` | Read-only asset lineage/episodes/specimen/pointers/creation anchor; inventory assertions for location, quantity, custody, consent and rights; explicit unknowns and stale provenance. | S/C detail | Record → Biological assets. This existing section was omitted from the original sidebar. |
| I/A: `#question-form`, `#question-list` within `#investigations` | Create durable question; display persisted question and state. No question edit/delete/manual-close control. | S | Proposed `#questions`; Questions & reports / Investigations. |
| I/A: `#draft-form`, `#question-choice`, `#source-choice`, `#evidence-choice` | Select question, exact source versions and optional assessments; author observations/hypothesis/gaps; save reviewable draft. | C | Investigations → Manual draft at retained `#investigations`. |
| I/A: `#snapshot-list`, dynamic `#snapshot-{id}` | Saved report/history, date/source IDs/state/origin; source/evidence citation readers; Markdown export; demo acknowledgment for drafts; stale-history explanations. | S read/export; C review | Proposed `#reports`; Questions & reports / Investigations. |
| I/A/`composer.js`: `#model-investigation-form`, `#model-investigation-heading`, `#composer-context`, `#composer-context-fingerprint` | Existing question/template/replay-or-live selection; canonical context preview/cutoff/fingerprint; exact-line source buttons; unavailable-tool status; gated run button. No free-text prompt or chat. | C | Investigations → Model-assisted research. |
| I/A: `#model-investigation-list` | Saved model runs, claims/uncertainty/citations/limits/abstentions/dropped-claim count; status/mode/template/model; Prepare review draft; generated-report link; stale-run explanation. | C; S resulting report | Investigations → Model-assisted research and Reports. |
| I/A: `#evidence`, `#evidence-tools`, `#evidence-import-form`, `#evidence-list` | Register authored fictional evidence; load example; list versioned fictional evidence; inspect originals. | C | Evidence → Sources. |
| I/A: `#evidence-assessment-form`, `#evidence-assessment-list` | Select question/current evidence; label relation/applicability; rationale; recorded assessments and freshness. | C | Evidence → Applicability review. |
| I/A: `#evidence-withdraw-tools`, `#evidence-withdraw-form` | Select current evidence and reason; withdraw/invalidate dependent drafts with history retained. | C | Evidence → Source actions. |
| I/A: `#options`, `#option-form`, `#option-list` | Propose discussion option from snapshot; description/epistemic state; derived epistemic/operational/review statuses; potential discussion deadline; dependencies/tasks/threats/review history. | C; S status reading | Evidence → Options & dependencies. |
| I/A: `#option-dependency-form` | Source/evidence-assessment/same-option-task/other-option dependency; optional lead time; sourced deadline/basis/anchor. | C | Evidence → Options & dependencies. |
| I/A: `#option-task-form` | Add human-owned preparation task with label/owner/optional lead time; read existing task status. No completion/reassignment/delete control. | C/S preparation | Evidence → Options & dependencies → Preparation tasks. |
| I/A: `#option-threat-form` | Add expiring-window/dependency-loss/evidence-withdrawal/other threat; optional sourced date/basis/anchor. | C | Evidence → Options & dependencies → Threats. |
| I/A: `#option-review-form` | Reviewer label; approve/reject/abstain/reconfirm/withdraw/expire; scope; optional replacement snapshot. Unverified demo action. | C | Evidence → Options & dependencies → Review. |
| I/A: `#bibliography`, `#bibliography-form`, `#bibliography-result` | Fictional metadata example; operator-enabled public DOI lookup; citation metadata/provider/retrieval date; canonical DOI link. Not case-linked or saved. | S | Global/secondary Research library. |
| I/`literature.js`: `#literature-search-form`, `#literature-results` | Authored public terms/fresh attestation; operator-enabled Europe PMC metadata; clear search; count/exclusion/integrity/rights display; canonical publication links. No case-derived query or persistence. | S | Global/secondary Research library. |
| I/A: `#import`, `#import-form`, `#report-text`, `#example-button`, `#quarantine-list` | Paste structured source; load example amendment; import result/stale count; wrong-subject quarantine entries. Retain alongside file intake. | S | Documents → Import text / amendments. |
| I/A: `#changes-since-review`, `#changes-anchor`, `#changes-disclaimer`, `#changes-new-sources`, `#changes-amendments`, `#changes-stale`, `#changes-questions` | Ledger facts since demo acknowledgment or case creation; new sources, mechanical finding-key/state differences, stale causes, new questions. | S | Patient Updates / clinician Review/history. |
| I/A: `#activity`, `#event-list` | Most recent 12 ledger event kinds/timestamps; also a supplemental-view refresh trigger. | S | Review/history → Activity; accessible from Updates. |
| I/A: `#source-dialog`, `#dialog-title`, `#dialog-context`, `#dialog-text`, `#dialog-close` | Exact original report/evidence modal; source-line highlighting; close/Escape; stale-read protection. | S | Global inspector reachable from all relevant destinations. |
| I/A: `#compare-dialog`, `#compare-title`, `#compare-context`, `#compare-before-title`, `#compare-before`, `#compare-after-title`, `#compare-after`, `#compare-close` | Consecutive linked-version comparison; deterministic text-only line differences; full originals; close/Escape. | S | Global comparison dialog. |
| I/A and supplemental scripts: `#notice` and local live status elements | Existing loading/success/error/unavailable/disabled/stale-selection/quarantine feedback. | S | Persistent visible notice area plus local status. |

## 4. All 16 existing forms and their contracts

Keep form IDs, field IDs, option values, original control nodes, event handlers, payload construction and validation unchanged. The HTML constraints listed here are not the whole validation contract: existing JavaScript and server validation continue to apply. Numbers below enumerate forms, not product steps.

| # | Form ID / owner | Existing fields and controls | Existing constraint or contract detail |
|---|---|---|---|
| 1 | `case-create-form` / E, `intake.js` | `case-create-alias`, `case-create-code`, `case-create-confirm`, `case-create-submit`, `case-create-status` | Required alias, max 65; required reference 2–40 with `[A-Z][A-Z0-9\-]{1,39}`; required fictional-data checkbox. JS rejects control characters and invalid reference/confirmation. |
| 2 | `source-upload-form` / E, `intake.js` | `source-file`, `source-upload-status`, `source-preview-details`, `source-upload-preview`, `source-upload-confirm`, `source-upload-submit`; contextual `source-intake-case` | `.txt`/text file picker; required confirmation; explicit submit initially disabled. Existing decoder requires 1–65,536 bytes, UTF-8, LF, exact format header and one unambiguous Patient header. Unsupported/BOM/CRLF/invalid content is rejected, not normalized. |
| 3 | `question-form` / I,A | `question-text`; Add question button | Required question, max 500. POST existing question payload. |
| 4 | `draft-form` / I,A | `question-choice`; dynamic source checkboxes under `source-choice`; assessment checkboxes under `evidence-choice`; `draft-observations`, `draft-summary`, `draft-assumptions`; Save investigation draft | Required question; observations required 10–1200; hypothesis max 1000; assumptions max 600. JS composes existing labelled summary and exact source/assessment IDs. Preserve stale selected IDs until explicit reconciliation. |
| 5 | `model-investigation-form` / I,A,`composer.js` | `model-investigation-question`, `model-investigation-template`, `model-investigation-mode`, `composer-context`, hidden `composer-context-fingerprint`, `model-investigation-run` | Required question/template; modes `replay`/`live`; run initially disabled until preview returns matching 64-character fingerprint. Fixed templates, no free-text prompt. |
| 6 | `evidence-import-form` / I,A | `evidence-text`, `example-evidence-button`; Register fictional evidence | Structured fictional evidence text; example fetch and existing global evidence-import payload. No new literature import semantics. |
| 7 | `evidence-assessment-form` / I,A | `evidence-question-choice`, `evidence-source-choice`, `evidence-relation`, `evidence-applicability`, `evidence-rationale`; Record fictional assessment | Required question/current source; rationale required 15–800. Relation values: `context`, `supports`, `contradicts`, `unknown`; applicability: `unknown`, `limited`, `applicable`, `not_applicable`. |
| 8 | `evidence-withdraw-form` / I,A | `evidence-withdraw-id`, `evidence-withdraw-reason`; Withdraw and invalidate drafts | Required current target; reason required 10–600. Preserve stale-target selection safeguards and dependent-invalidation response. |
| 9 | `option-form` / I,A | `option-snapshot-choice`, `option-label`, `option-description`, `option-epistemic`; Propose option for review | Required snapshot/label (max 120)/description (10–1000). Epistemic values `unknown`, `supported`, `unsupported`, `contradicted`. |
| 10 | `option-dependency-form` / I,A | `dependency-option-choice`, `dependency-kind`, `dependency-source-choice`, `dependency-assessment-choice`, `dependency-task-choice`, `dependency-option-target-choice`, `dependency-lead`, `dependency-deadline`, `dependency-basis`, `dependency-anchor`; Add dependency | Required owning option. Kinds `source`, `evidence_assessment`, `preparation_task`, `option`. Lead 0–3650; date optional; basis `unknown`/`sourced`; anchor max 300, with existing sourced-anchor rules. Preserve null payload fields for unused kinds. |
| 11 | `option-task-form` / I,A | `task-option-choice`, `task-label`, `task-owner`, `task-lead`; Add preparation task | Required option/label (max 120)/owner (max 80); optional lead 0–3650. |
| 12 | `option-threat-form` / I,A | `threat-option-choice`, `threat-kind`, `threat-description`, `threat-date`, `threat-basis`, `threat-anchor`; Add threat | Required option/description (10–500); kinds `expiring_window`, `dependency_loss`, `evidence_withdrawal`, `other`; optional date; basis `unknown`/`sourced`; anchor max 300 and existing sourced-anchor rules. |
| 13 | `option-review-form` / I,A | `review-option-choice`, `reviewer-label`, `review-action`, `review-scope`, `review-snapshot-choice`; Record reviewer action | Required option/reviewer (max 80)/scope (10–300). Actions `approve`, `reject`, `abstain`, `reconfirm`, `withdraw`, `expire`; optional replacement snapshot. Unverified label does not establish authority. |
| 14 | `bibliography-form` / I,A | `bibliography-doi`, `bibliography-example-button`, `bibliography-live-button`; `bibliography-mode`, `bibliography-result` | DOI required, max 256; live button disabled until operator status allows; example button independent of submit. Canonical DOI link allowed only under `https://doi.org/`. |
| 15 | `literature-search-form` / I,`literature.js` | `literature-terms`, `literature-public-attestation`, `literature-live-button`, `literature-clear-button`; `literature-mode`, `literature-feedback`, `literature-results` | Terms 3–240; existing JS requires fresh attestation, enabled operator status and no pending search. Existing payload is `{terms, human_authored:true, public_terms_only:true, page_size:5}`. |
| 16 | `import-form` / I,A | `report-text`, `example-button`; Import report; `quarantine-list` | Existing structured-text import and authored amendment loader. Preserve original text, result handling and quarantine behavior. |

Additional controls outside forms include case selection, timeline filtering, navigation/disclosures, all original-source/version-inspection buttons, comparison open/close, report export, demo acknowledgment, model-run review-draft creation, generated snapshot links, public citation links and the intake Create workspace opener. These are inventoried in the feature table and remain reachable.

## 5. Hash routes and ID preservation

The original sidebar links to:

`#overview`, `#incoming-board`, `#patient-view`, `#patient-mission`, `#assertions`, `#timeline`, `#investigations`, `#sources`, `#evidence`, `#bibliography`, `#import`, `#activity`, `#changes-since-review`, `#options`.

The connected host inserts `#source-intake` navigation. The progress journey additionally links to `#workspace-start` and `#model-investigation-heading`. The skip link uses `#main-content`; generated model-report handoff uses dynamic `#snapshot-{id}`. `#biological-assets` and `#world-model-detail` are existing meaningful targets even though neither has an original sidebar entry.

Preserve every existing target as a reachable anchor or compatible navigation destination. New presentation targets `#patient-home`, `#questions` and `#reports` must not remove or duplicate existing IDs. The baseline hash listener only marks active navigation and uses browser anchor scrolling; it does not implement route mounting, state resets or history rewriting. A presentation router must reveal the correct ancestor section before following an existing nested target, especially `#snapshot-{id}` and `#model-investigation-heading`.

## 6. Existing frontend API calls

`C` means `/api/cases/{case}`. These are observed frontend calls, not proposed endpoints. The shared `api()` helper uses GET when no payload is supplied and POST with JSON when one is supplied. Supplemental scripts also use direct fetch for their existing read/search contracts.

| Method and path | Frontend purpose |
|---|---|
| `GET /api/cases` | Case picker and worklist. |
| `POST /api/cases` | Connected intake creates a fictional case. |
| `GET C/state` | Canonical case render; per-case worklist summary. |
| `GET C/sources/{id}` | Original source/version inspection and comparison. |
| `POST C/imports` | Existing paste and file-intake source imports. |
| `GET /api/examples/amendment` | Authored example amendment text. |
| `POST C/questions` | Persist question. |
| `POST C/snapshots` | Human-authored draft with exact dependencies. |
| `POST C/snapshots/{id}/review` | Explicit demo review acknowledgment. |
| `GET C/snapshots/{id}/export` | Existing source-linked Markdown export. |
| `GET /api/investigations/templates` | Bounded model templates. |
| `GET C/composer/context?question_id=…` | Current source/evidence preview and fingerprint. |
| `POST C/investigations` | Run existing bounded replay/live investigation. |
| `GET C/investigations` | List persisted model investigations. |
| `GET C/investigations/{id}` | Inspect persisted run detail. |
| `POST C/investigations/{id}/review-draft` | Existing model-run-to-reviewable-snapshot handoff. |
| `GET C/mission` | Read-only workflow orientation. |
| `GET C/world-model` | Read-only original-source projection. |
| `GET C/changes-since-review` | Read-only anchored change listing. |
| `GET /api/examples/evidence` | Authored fictional evidence example. |
| `POST /api/evidence/imports` | Register global fictional evidence. |
| `GET /api/evidence/{id}` | Original fictional evidence text. |
| `POST C/evidence-assessments` | Case/question-specific evidence assessment. |
| `POST /api/evidence/{id}/withdraw` | Global evidence withdrawal and dependent invalidation. |
| `POST C/options` | Propose option from existing snapshot. |
| `POST C/options/{id}/dependencies` | Add dependency. |
| `POST C/options/{id}/tasks` | Add human-owned preparation task. |
| `POST C/options/{id}/threats` | Add optionality threat. |
| `POST C/options/{id}/review` | Record existing scoped demo-review action. |
| `GET /api/bibliography/status` | Read operator-enabled DOI lookup availability. |
| `GET /api/bibliography/example` | Fictional metadata example. |
| `POST /api/bibliography/lookup` | Public DOI-only metadata lookup. |
| `GET /api/literature/status` | Read operator-enabled literature-search availability. |
| `POST /api/literature/search` | Independently authored public-term metadata search. |

Preserve the important distinction between global evidence records and case/question-specific assessments. Do not make bibliography or literature results case-linked, persistent, or evidence-appraised through a presentation change. The connected launcher keeps live Crossref/literature disabled and clears its supported model credentials; visible live-mode controls are not evidence of a live capability in that launch configuration.

## 7. State, permissions and unsaved edits

### Canonical state and asynchronous protection

`app.js` owns `caseId`, `active`, `refreshSequence` and `renderedCaseId`. `readyCase()` rejects writes until the selected case has matching loaded and rendered state. Source reads use `sourceReadSequence` plus active-case checks so an older request cannot overwrite a newer read intent or a different case. Comparison revalidates consecutive version lineage, document/type/event/specimen identity, and active membership before fetching originals.

`modelInvestigationSequence` and `modelViewIsCurrent()` guard asynchronous model/run rendering. The Composer has its own request sequence and resets its fingerprint/run button when scope changes. The model submission requires the existing fingerprint; a stale-Composer error refreshes canonical state and dispatches `oi:composer-refresh`. These behaviors must not be replaced by presentation-owned copies of patient/source/research state.

The original frontend contains no `localStorage`, `sessionStorage`, separate browser ledger, account-session store, `pushState` or `replaceState` route layer. Original source/model output is rendered as text, not interpreted as HTML. Source comparison remains a deterministic text operation, bounded at 65,536 characters or 512 lines for highlighting; complete originals remain visible when highlighting is skipped.

### Existing unsaved guard

Case switching is blocked when any of these six fields has non-whitespace text:

- `draft-observations`
- `draft-summary`
- `draft-assumptions`
- `evidence-rationale`
- `evidence-withdraw-reason`
- `option-description`

`workspace-entry.js` uses the same six-field predicate before creating/switching to another workspace. A veto restores the previous picker value and displays the existing save-or-clear notice. There is no general `beforeunload` guard, no dedicated discard/save-confirmation dialog, and no universal dirty-form tracking. Other unfinished controls fall outside this guard. Do not claim comprehensive unsaved-change protection.

On a same-case refresh, the manual draft preserves exact selected source IDs, including superseded selections, and warns that a human must reconcile them. Evidence selections are scoped to the chosen question. An obsolete evidence selection with a drafted rationale is retained visibly for reconsideration. An obsolete withdrawal target is not silently replaced by a different current item. Preserve the original nodes and selection logic.

The file-intake module keeps pending decoded content, creating/importing flags, a request sequence, shown-case ID and source-presence state. Scope changes clear the file, preview and confirmation. No selected file is uploaded until explicit submission. Public literature search separately tracks enabled/pending/generation state; changing terms clears attestation and invalidates results; clearing search invalidates pending output. Do not merge these independent state machines into the case state.

### Permission truth

The audited page statically declares `data-audience="clinician"` and `data-density="comfortable"`; neither is read as an authorization rule. Patient prose and clinician/demo actions coexist. There is no user authentication, patient login, clinician verification, role assignment, consent management, token storage, permissions editor or credentialed signature in this frontend. A reviewer label is unverified input. A fictional-data checkbox is not identity, consent or legal authorization.

The planned patient/clinician navigation is a presentation preview only. It must not create an impression that switching modes grants or removes server authority.

## 8. Host template and DOM coupling

### Exact connected-host anchors

`src/open_intelligence/workspace_host.py::workspace_html()` reads the original `index.html` and requires each of the following strings to occur exactly once. Otherwise it raises `ValueError('Workspace owner template changed; entry requires reconciliation.')`. Because backend changes are excluded, retain these strings verbatim during the frontend redesign:

```html
<link rel="stylesheet" href="/style.css">
<script src="/app.js" defer></script>
<script src="/literature.js" defer></script>
<body>
<p class="muted tiny">Fictional case data stays
<a href="#sources">Sources and findings</a>
      <div class="metrics" id="metrics" aria-live="polite"></div>
```

The final metrics anchor includes six leading spaces. The fictional-data paragraph anchor is intentionally a prefix. The host injects intake CSS, `intake.js` before `app.js`, `workspace-entry.js` after `literature.js`, body workspace state, Create workspace, Add original records navigation and the entire setup/intake partial. `workspace-entry.html` is not a standalone page. The standard prototype page and connected launcher therefore have different entry surfaces while sharing the existing application logic.

### Live DOM and event dependencies

- `app.js` attaches many listeners immediately through `el(id).addEventListener(...)`; deleting a required node can halt application initialization.
- `workspace-entry.js` directly uses existing `api`, `readyCase`, `caseId`, `active`, `initialize`, `refresh` and `renderIncomingBoard`. Its observer watches `#case-heading`, `#source-list`, `#question-list`, `#snapshot-list`.
- `mission.js` and `world-model.js` observe child mutations on `#event-list`. Its role extends beyond visible activity rendering.
- `composer.js` observes `#model-investigation-question` child changes; the canonical renderer remains its question owner.
- `oi:composer-open-source` dispatches source/line/case intent to the existing inspector; `oi:composer-refresh` updates a stale context preview.
- The case-picker key handler looks for `.rail nav a[href="#overview"]`.
- The original mobile section menu is controlled by a 60rem media query and a nav click listener.
- Intake CSS includes `body[data-workspace-state="empty"] .main > :not(#overview):not(#workspace-start):not(#notice)`. Changing direct-child wrappers can unintentionally hide the setup UI.
- Native dialog close/Escape invalidates read intent. Do not bypass the source-read gate when adding navigation shortcuts.

Move original live nodes instead of cloning forms or creating duplicate IDs. Preserve observed elements, all field IDs, events, active-case context and script order. Keep the global notice visible across presentation destinations. A route must expose the correct ancestor before scrolling to a nested original anchor. Preserve keyboard focus and source-dialog reachability when introducing the new navigation.

## 9. Delivered candidate, separate drafts and absent functionality

The documented main checkpoint `24519839` and the audited PR #166 candidate are distinct source states. The candidate includes connected entry and research/workflow integration; its availability in this checkout does not establish merge, deployment or current-main status. Repository acceptance of FastAPI/PostgreSQL and React/Vite/TypeScript is an architectural target, not evidence that this frontend has migrated.

The repository's execution audit describes separate historical clinical drafts #70, #74, #56, #85, #89, continuity draft #95, and later clinical-to-Composer/knowledge drafts #130/#132. Their patient/EHR/LIS/outbox/integration descriptions must not be counted as delivered screens in this candidate. This audit did not fetch or inspect those separate branch implementations. The same execution audit identifies reused Composer/context-related draft inputs; source ownership and integration status should remain explicit rather than treating all historical draft work as one shipped application.

The following are absent from the audited frontend:

| Capability | Observed boundary |
|---|---|
| Appointments/calendar | No booking, reschedule, cancellation or calendar workflow. |
| Medication management | No medication CRUD, prescribing, refill, reconciliation, administration or pharmacy UI. Synthetic medication fixtures or source modules do not constitute these screens. |
| Messaging/chat | No patient-care-team inbox, conversation thread, send action, chat composer or messaging notifications. The question Composer is a bounded investigation context preview. |
| Authentication/administration | No registration, login/logout, reset, clinician verification, role/permission administration, patient/proxy assignment or account-management UI. |
| Operational clinical systems | No encounter/note editing, orders or EHR/LIS write-back interface. |
| General document ingestion | No PDF/OCR/scan/general document extraction. Intake accepts the existing authored structured UTF-8 text contract. |
| Scientific/clinical integrations | No live guideline search, trial-matching UI or scientific-computation execution UI. Composer explicitly exposes unavailable tool status. |
| Clinical attestation | No credentialed review or signature. Demo acknowledgment and unverified labels remain explicitly bounded. |
| Question/asset/task CRUD | No question editing/deletion/manual closing, biological-asset creation/editing, preparation-task completion/reassignment/deletion or source-record deletion controls. |

Preserve the research capabilities that do exist: exact-source inspection, version comparison, biological provenance, World Model projection, Mission workflow orientation, bounded model runs and durable review handoff, fictional evidence assessment/withdrawal, options/dependencies/tasks/threats/scoped demo review, DOI discovery and Europe PMC metadata discovery. Metadata is not literature appraisal; an option is not a treatment recommendation; source amendments are not automatically new biological events; a presentation-mode switch is not authorization.

## 10. Frontend redesign acceptance boundaries

This audit provides a preservation inventory, not completed verification. Subsequent implementation review should establish that the proposed patient and clinician destinations reveal every original feature, all 16 original forms and original hash targets remain usable, empty/populated/loading/error states retain their controls, and moved forms retain state/handlers without changing payloads or validation. Source dialogs, exact provenance, amendment/stale history, report export and research discovery require particular attention because navigation must not obscure them.

Browser screenshots, keyboard/mobile journeys and any executed software checks belong in a separate verification record tied to the exact redesigned revision. None are claimed by this source audit.
