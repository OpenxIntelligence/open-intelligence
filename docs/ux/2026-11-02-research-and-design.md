# Healthcare workspace UX: research and design

Date: 2 November 2026 (UTC), refined during implementation on 3 November. Status: implementation specification for the founder's frontend-only redesign request. This document records design decisions, not released functionality or permission to change backend contracts.

## Scope and baseline

The inspected product is Open Intelligence. Main is `24519839aa8ac1ea3aff88a956349ba72798a72a`. The implementation base is the latest connected-workspace candidate in PR #166, `334d863b2206b290c02cd2606dcb93c93afe3a68`, source tree `d7059e5c178e761e0987a67ff8c220f47e6da2f8`. This already composes source records, World Model, questions, investigations, review, amendments and empty-workspace file intake. The candidate is unmerged; using it does not merge or deploy its parent work. The new work has its own branch. Main and other owners stay unchanged.

All 222 baseline files were materialized and checked against their Git blob hashes. A later Git fetch confirmed the same remote revision. The complete frontend inventory is in [the audit](2026-11-02-frontend-audit.md). That audit identifies 16 existing forms, all original navigation targets, current request contracts and important DOM dependencies.

There is one existing vanilla HTML/CSS/JavaScript application. React/Vite/TypeScript is the accepted migration target, not the frontend delivered in this candidate. A framework migration would exceed this request. The current application has no real patient/clinician authentication, appointments, medication-management UI, care-team messaging or encounter-note editor. Separate draft backend work does not make those screens available here.

## Research method and limits

Reviewed official Epic MyChart, NHS, athenahealth and Elation public product/help documentation on 2 November 2026. This is source-grounded UX research, not an authenticated usability test of those systems. Do not infer exact current pixel layouts, availability at every provider or accessibility conformance from marketing pages. No personal medical records were accessed.

| Reference | Documented pattern | Adoption decision |
|---|---|---|
| Epic MyChart [R1, R2] | Patient health information and care tasks are organized into recognizable feature families. Messages are conversation-oriented where the provider supports them. | Use familiar patient destinations, concise summaries, and direct links to detail. Do not add messaging or appointment controls without existing workflows. |
| NHS App [R3, R4] | March 2026 navigation update emphasizes Home, Messages and Profile. Record information appears in prescriptions, appointments, results, conditions and documents. | Keep patient global navigation short. Present existing records in understandable groups rather than a full professional workbench on Home. |
| NHS App [R5, R6] | Repeat medicines can remain visible when a request is unavailable, with an explanation. Most messages are one-way; reply capabilities vary. | Preserve information and explain unavailable actions. Match actions to actual supported capabilities; do not manufacture a universal Reply, Refill or Book button. |
| athenaOne [R7] | Role-related work and a Clinical Inbox focus attention on relevant tasks, with schedule and chart access tailored to work. | A clinician starts from an actual case list/worklist. Preserve recorded states without inventing urgency, clinical priority or task ownership. |
| athenaOne [R8] | Charting uses meaningful sections, preparation and review within patient/encounter context. | Keep source facts and their history accessible while preparing an existing investigation. Distinguish source observations, hypotheses, drafts and review acknowledgments. |
| Elation [R9, R10] | Practice Home has patient search, queues and schedule; the patient chart has its own navigation and durable clinical context. | Separate application navigation from chart navigation. Keep the selected case obvious across chart sections. Use a direct path back to the case list. |
| NHS accessibility statement [R11] | Public accessibility documentation calls out labels, semantics, contrast and text resizing, and reports partial compliance. | Verify those requirements in our implementation; do not claim WCAG conformance from visual resemblance. |

Newer competitor AI timelines and unified worklists have alpha/beta availability caveats [R12, R13]. They are optional design references, not evidence of universally deployed functionality. This redesign does not introduce an AI-generated health summary or duplicate the existing source authority.

### Resulting design principles

1. Home answers where to continue and what has changed. It is not the whole record.
2. The worklist changes which person/case is open. Chart navigation changes the section of the same record. These scopes must look different.
3. The original source, source version and uncertainty remain reachable from every consequential statement.
4. Shared information may have different reading presentations; changing the presentation does not change permissions.
5. The complete workflow remains available through focused destinations and native disclosures. Fewer visible controls must not mean lost functionality.
6. Status text carries meaning independently of color. Draft, stale, unreviewed, unknown and unavailable remain distinct.
7. Responsive navigation changes structure: a compact mobile menu replaces a permanent desktop rail; chart sections wrap or use a native selector rather than overflowing.

## Existing UX findings

The source audit shows 14 original sidebar links (15 after intake composition) and one long document. Patient explanation, multi-case worklist, source facts, research authoring and review controls coexist. Biological-asset provenance has no sidebar entry. The same record is repeated as reported findings, plain-language findings and Patient Mission. These are useful representations, but their simultaneous display obscures the next task.

The application already has valuable foundations: exact source inspection, native dialogs, a source comparison view, differentiated uncertainty, immutable history, several loading/error states and stable form IDs. The redesign preserves those components and their event handlers.

Source review is complete. The existing real-browser glance journey subsequently passed with official Chrome unpacked to a temporary test directory, capturing desktop overview/source and 390px mobile overview. On the baseline desktop, manual investigation content begins roughly 5,912px down the document. The mobile screenshot shows navigation/help consuming much of the initial viewport. Initial cloud-browser preview and missing-browser failures are retained as environment evidence; the later successful run does not erase them.

## Approaches considered

| Approach | Consequence | Decision |
|---|---|---|
| Restyle the existing long page or group its sidebar | Low implementation effort, but patient/professional mixing and long-page navigation remain. Earlier PR #64 already explored sidebar grouping. | Insufficient for the requested redesign. |
| Migrate the frontend and introduce separate authenticated portals | Would depend on backend/auth and architecture work prohibited by this request. Risks replacing working handlers and unmerged owner work. | Out of scope. |
| Reorganize the current components into two presentation shells and a dedicated chart | Uses the current APIs and DOM owners, gives real task navigation, preserves all existing workflows, and can be verified incrementally. | Selected implementation approach. |

## Information architecture

### Patient presentation

| Primary destination | Contents and exact navigation |
|---|---|
| Home | New `#patient-home` presentation target: current case context, compact existing record counts, quick links, existing open questions and uncertainty/change explanations. Summary lists have a clear route to the full list. |
| My record | `#patient-view`: existing plain-language source findings and chronology. Secondary access to exact findings (`#assertions`), full timeline (`#timeline`), workflow status (`#patient-mission`) and biological assets (`#biological-assets`). |
| Documents | `#sources`, with all versions and original-reader actions retained. File intake (`#source-intake`) and structured text/amendment import (`#import`) remain available in the clearly labeled clinical preview. |
| Questions & reports | New `#questions` and `#reports` targets host the existing question form/list and saved report history. Patient reading does not expose professional authoring or demo acknowledgment as ordinary patient tasks. |
| Updates | `#changes-since-review`, with `#activity` as the event-history destination. Source-change comparisons remain available in Timeline. |
| Secondary tools | Shared `#bibliography` research discovery and an explicitly labeled link to clinical `#workspace-start` setup/help. These are not medical messaging or authenticated account settings. |

The patient Home does not manufacture next appointments, diagnoses, medicines, allergies or results. It presents the existing source record and workflow states. No mock dashboard data is introduced.

### Clinician presentation

| Application destination | Contents |
|---|---|
| Patients / worklist (`#incoming-board`) | Existing all-case worklist, searchable by the rendered alias/reference. Actual existing counts and source-recency ordering retained. Opening a row passes through the existing case switch and enters the selected chart. No triage priority is inferred. |
| Research library (`#bibliography`) | Existing DOI and Europe PMC metadata forms, with their current operator-enablement, public-input and rights limitations. It remains distinct from case-linked evidence. |
| Workspace setup (`#workspace-start`) | Existing create-case form and workflow orientation, with the original fictional-data contract and empty state. |

### Dedicated patient chart

Persistent case header: existing alias/name and case reference, selected-case control, clear return to Patients, and a small presentation/demo label. No invented date of birth, medical record number, demographic information or allergy warning.

| Chart destination | Secondary destinations |
|---|---|
| Overview | Existing record metrics and review state; concise workflow links. |
| Record | Reported findings, Timeline, plain-language record, Patient Mission / source-linked World Model, Biological assets. |
| Documents | Source/version history, original-file intake, structured text import/quarantines. |
| Investigations | Questions, prepare a manual draft, bounded model investigation, saved reports/history. |
| Evidence | Existing source registration, assessment and withdrawal; Options & dependencies retains all five proposal/preparation/review forms behind meaningful disclosures. |
| Review & history | What changed since review and recent ledger activity. |

Use normal navigation links for pages and native disclosures for advanced forms. Do not apply ARIA tab semantics to ordinary page navigation. The active application destination, chart group and subsection are separately identifiable. Existing deep links, including generated `#snapshot-{id}` and `#model-investigation-heading`, resolve to the containing visible workspace.

## Presentation and authorization

The audited app has no authenticated role provider. The switch must therefore say it changes a **presentation preview**. It does not grant access, change requests, attach an account, alter headers or suppress server checks. It must never be labeled as logging in as a clinician. Existing APIs remain the authority they currently are.

Professional authoring and demo review belong to the clinical presentation. A link to a clinical-only workspace can enter that clearly labeled preview because this is the existing unrestricted fictional environment, not a new privilege. Shared records, questions and report reading remain available in the patient presentation. Production role separation is a documented backend-dependent limitation and is not implemented here.

## Visual design direction

Preserve the existing system font stack and CSS token architecture. Use a quiet off-white application background, white content surfaces, dark navy text and a restrained teal accent for primary navigation/actions. Amber represents a recorded review warning; red is reserved for failures. Add no font, icon, component or runtime dependencies.

Desktop uses a stable 232–248px rail, a compact header, a clear page title and a content region with readable line lengths. Patient pages use more space and plain-language labels. The clinician worklist uses aligned rows and modest density. Patient-chart navigation sits below the identity banner, visibly separate from the rail. Borders and spacing establish grouping; avoid decorative gradients and shadow-heavy card stacks.

Buttons, fields, disclosures, notices, status pills, dialogs and empty states retain coherent sizing and visible focus. Aim for controls at least 44px high, 16px mobile form text, text wrapping for identifiers and source content, and contained overflow inside exact-text comparisons. Labels and help text remain programmatically connected. Do not truncate medical source statements without an explicit full-record path.

At narrow widths, use a real menu button with `aria-expanded`, hide closed navigation from keyboard focus, and expose all destinations through the menu. The chart navigation has a labeled compact native select when the wide layout would wrap excessively. Preserve the active case and page title. Respect reduced motion. Verify reflow at 320, 390, 768, 1024 and 1440px and zoom/text-size behavior where tooling permits.

## Engineering boundaries and integration decisions

- Product changes are confined to existing `web/` assets. Backend, database, APIs, payloads, authentication, authorization, validation and data-processing functions remain unchanged.
- Preserve all 16 form IDs and field names, constraints, enum values and handlers. Move live nodes; do not clone forms or maintain a second case store.
- Preserve all seven literal `workspace_host.py` composition anchors. No server changes are needed to serve a new file: navigation code lives in the already-served `app.js`, styles in existing stylesheets.
- Keep notices and dialogs outside routed panels. A failed request must not leave its only feedback in an invisible destination.
- Navigation hides/shows existing panels without rerendering their forms. Unfinished text and choices survive same-case navigation and view changes. Existing case-switch guards continue to decide whether a case change is allowed.
- Retain the vanilla fallback and connected launcher. Empty-database setup must stay reachable after content is reorganized.
- New filtering only changes presentation of existing rendered cases/documents. It does not alter backend queries, sort semantics or clinical interpretation.
- New UI wrappers do not create diagnosis, medication, allergy, appointment or message data from source quotations.

## Acceptance and remaining limits

The implementation must show distinct patient and clinician entry points, a separate case chart, complete feature coverage, working old/new deep links and history, visible errors, preserved same-case draft state and original-source actions. All original form/API contracts and all protected non-frontend product source files must compare unchanged against the base. New responsive and interaction checks should exercise real application behavior, not only source-text matching. Run existing regression tests and report exactly what passed, failed or could not run.

This work cannot establish authenticated patient/clinician permission separation, real-patient readiness, missing clinical operations or independent healthcare usability validation. Those are documented limitations, not reasons to insert simulated workflows.

## Official references

- R1: [Epic MyChart feature families](https://www.mychart.org/l/en-us/explore/).
- R2: [Epic MyChart messaging](https://www.mychart.org/l/en-us/help/messaging/).
- R3: [NHS App release notes](https://www.nhs.uk/nhs-app/about/nhs-app-release-notes/), navigation update 19 March 2026, v4.58.
- R4: [GP health records in the NHS App](https://digital.nhs.uk/services/nhs-app/nhs-app-features/gp-health-records-in-the-app).
- R5: [Prescriptions in the NHS App](https://digital.nhs.uk/services/nhs-app/nhs-app-features/prescriptions-in-the-nhs-app).
- R6: [NHS App messaging behavior](https://digital.nhs.uk/services/nhs-app/nhs-app-features/notifications-and-messaging-in-the-nhs-app).
- R7: [athenaOne role-specific workflows](https://www.athenahealth.com/resources/blog/athenaone-efficient-practice-management-workflows), 15 April 2025.
- R8: [athenaOne charting improvements](https://www.athenahealth.com/resources/blog/5-ways-athenaone-makes-charting-easier), 4 December 2025.
- R9: [Elation Practice Home](https://help.elationhealth.com/articles/practice-home-introduction).
- R10: [Elation Patient Chart](https://help.elationhealth.com/articles/Patient-Chart-Introduction).
- R11: [NHS App accessibility statement](https://www.nhs.uk/nhs-app/about/privacy-legal-information/nhs-app-accessibility-statement/).
- R12: [athenaOne AI-native announcement](https://www.athenahealth.com/about/press-releases/ai-native-ehr-capabilities-athenaone), 13 August 2026; selected features described as alpha or approaching alpha.
- R13: [Elation Unified Worklist](https://help.elationhealth.com/articles/unified-worklist-guide), documented beta availability.

## Independent design review adjustments

Preserve natural keyboard order instead of the old forced Tab jump to a potentially hidden sidebar link. Make the brand destination audience-aware. Mark dynamically generated demo acknowledgment controls as clinician-presentation actions while retaining shared report text, citations and exports. Add exact-source inspection to the existing plain-language finding cards through the guarded original inspector. Verify both standard and connected launchers; hide connected-only links when their nodes do not exist. Provide a direct saved-report destination after manual drafting. These are presentation changes only.
