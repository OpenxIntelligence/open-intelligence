# Open Intelligence — Frontend UX Evolution: Baseline Audit and Research Gate

**Status:** research and architecture proposal; not an approved framework migration or implemented redesign  
**Date:** 2026-11-02  
**Scope:** frontend-only research and subsequent isolated frontend changes; no production clinical-use claim  
**Source of implementation truth:** `main` at research time, read through GitHub; this is a partial static audit, not a running application assessment.

## 1. Context and guardrails

This work responds to the Product Research, UX/UI Redesign & Frontend Engineering directive. It supplements, rather than replaces, `AGENTS.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, `docs/UI_CHANGE_REVIEW_SPEC.md`, and the established case/source/review contract.

**Hard boundaries:** no changes to backend services, database structure, API endpoints/contracts, authentication/authorization, clinical business rules, record-keeping, integrations, or data processing. No real patient data, fabricated clinical actions, mock replacement for real application data, or claim of patient/clinician production access control.

The existing synthetic demo currently does not have verified real-patient authentication or clinical identity. Separate *presentation modes* in the demo must **not** be described as separate securely authorized accounts.

## 2. Verified code-level baseline

| Area | Observed fact | Source |
|---|---|---|
| Rendering | Static HTML and native DOM scripting, not a React/Next.js bundle | `web/index.html`, `web/app.js`, `web/mission.js` |
| Styling | First-party CSS tokens, base and style sheets | `web/tokens.css`, `web/base.css`, `web/style.css` |
| Global navigation | Single sidebar `#workspace-nav` with 14 anchor destinations | `web/index.html` |
| Mixed audiences | Clinician source/investigation workspace and plain-language `#patient-view` / `#patient-mission` share one document | `web/index.html` |
| Case switching | Selected fictional case, unsaved narrative guard, stale-response suppression, and dialogs | `web/app.js` |
| Patient overview | Same underlying case reports, findings, questions, uncertainty | `web/app.js` |
| Mission | Read-only synthetic case projection from existing mission endpoint | `web/mission.js` |
| Provenance | Exact source-version and source-line references; amendment/change comparison | `web/app.js`, `docs/UI_CHANGE_REVIEW_SPEC.md` |
| Browser testing | Python and Chromium journey files exist | `tests/browser_journey.py`, `tests/patient_mission_browser_journey.py`, `tests/ui_glance_journey.py` |

**Not yet verified:** a fresh local execution, rendered screenshots, comprehensive route/API inventory, every control and failure mode, responsive visual results, screen-reader results, elapsed task time, existing PR implementation differences, and actual clinical user feedback. No tests were run for this research document.

## 3. Product problem and design hypotheses

The current 14-destination sidebar conflates *role*, *workspace*, *patient record*, and *individual task*. Putting patient-friendly text on the same long page does not establish a coherent patient experience. Conversely, concealing a clinician section purely with CSS does not enforce access control.

Three product hypotheses to validate with actual workflow tasks:

1. Task-oriented application navigation will reduce unnecessary scanning compared with one long list of clinical features.
2. A persistent, clearly identifiable fictional case header plus a dedicated contextual record navigation will reduce wrong-context actions.
3. A plain-language patient journey built from the same source records will improve findability and comprehension **without silently losing provenance or uncertainty**.

These are hypotheses, not proven findings.

## 4. Alternative information architectures

### Concept A — Role-aware workspaces with contextual chart navigation (preferred for evaluation)

- **Patient presentation:** Overview; My Records; Timeline; Questions & Updates; Documents (only when functionality is actually present). Keep synthetic/unauthenticated warning prominent.
- **Clinician presentation:** Worklist; Cases; Investigations; Source & Evidence Review; Activity/Changes (map actual functions before implementing).
- **Inside selected case:** Overview; Source Findings; Timeline & Changes; Sources; Questions & Investigations; Evidence. Consolidate related tasks contextually instead of making all 14 peers.
- **Cross-cutting:** One selected-case identity, original data/provenance, existing API and validation, shared feedback, error handling, and design tokens.

**Strengths:** clear roles and context, preservable one-source ledger, suitable expansion to later authenticated roles. **Risks:** view state and focus restoration; URLs/back navigation; migrating long-page anchor tests; misleading role security if named carelessly.

### Concept B — Single task-centric case workspace with a patient reading mode

- Keep one application shell and an explicit clinician/research vs plain-language reading mode.
- Organize the selected case around three jobs: Understand; Investigate; Review Changes.
- Avoid separate role-specific applications until real authorization exists.

**Strengths:** smallest implementation footprint, least divergence of synthetic demo presentations. **Risks:** harder to scale to distinct patient/care-team workflows; contextual actions can remain too dense.

**Recommendation:** prototype Concept A with the clear **demo presentation** qualifier, evaluate Concept B as a lower-complexity baseline. Choose with measured completion and error data rather than aesthetics alone.

## 5. Source-informed healthcare design constraints

- Epic MyChart's public feature documentation organizes patient needs around health records, messaging, appointments, family connections, and access to notes, but these cannot be presented as implemented Open Intelligence functions unless backed by current data/actions: https://www.mychart.org/Features
- ONC 2025 SAFER Guides emphasize patient identification, test-results follow-up, and clinician communication: https://healthit.gov/clinical-quality-and-safety/safer-guides/
- WCAG 2.2 is a relevant accessibility evaluation baseline: https://www.w3.org/TR/WCAG22/
- Existing internal UI contract requires inert original report text, exact source-line links, retained historical versions, visible stale review states, no clinical-inference promotion: `docs/UI_CHANGE_REVIEW_SPEC.md`.

**Research remaining:** direct source-backed workflow reviews of NHS App, athenaOne, Oracle Health, Elation, Canvas and others; independent clinical usability literature; substantiated recurring user criticism, with isolated online opinions distinguished from repeatable evidence; competitor stack provenance (verified vs inferred vs unknown).

## 6. Initial feature relocation map — provisional, not complete

| Existing anchor | Provisional destination | Preservation risk |
|---|---|---|
| `#overview` | Case Overview | case identity, counts and hero actions |
| `#incoming-board` | Clinician Worklist | current source-event recency is NOT medical urgency |
| `#patient-view` | Patient Records / Overview | plain language must preserve certainty and versions |
| `#patient-mission` | Patient Journey / Updates | read-only projection; no clinical recommendations |
| `#assertions` | Case > Reported Findings | exact original statement and source line |
| `#timeline` | Case > Timeline | event / issue / receipt distinction, amendment grouping |
| `#investigations` | Case > Questions & Investigations | drafts, permissions, saved state, linked versions |
| `#sources` | Case > Original Documents | original source text and read-only comparison |
| `#evidence` | Case > Evidence Review | source permissions, quotation checks and scope |
| `#bibliography` | Evidence > Bibliography | metadata is not proof of case-specific applicability |
| `#import` | Case > Updates | preserve current import and existing validation |
| `#activity` | Case > History | durable chronological receipts |
| `#changes-since-review` | Case > Review Changes | stale references and historical provenance |
| `#options` | Investigation > Options | research options must not become medical advice |

This maps entry points, not every button, form, dialog, state, or test. Complete a line-item control inventory before moving markup.

## 7. Proposed implementation sequence (not executed)

1. **Baseline gate:** inspect all active UX PRs and current main, enumerate every frontend ID, event handler and API call, run existing synthetic/Chromium tests, capture screenshots at desktop/tablet/390px, document defects and branch head.
2. **Navigation shell:** introduce progressive disclosure while keeping all existing DOM IDs, form names, fetch calls and existing interactions; preserve meaningful hash/deep links and focus order. Do not claim a secured role switch.
3. **Persistent selected-case context:** ensure case identity remains apparent during source dialogs and after navigation; preserve asynchronous case-binding and unsaved-draft guard.
4. **Patient / clinician presentation separation:** reorder existing read-only case facts without duplicating datasets or changing routes and contracts; prove uncertainty preserved.
5. **Chart context:** introduce nested navigation for existing record categories only; no invented encounters, appointments, prescriptions or messaging.
6. **Design system:** consolidate tokens, empty/loading/error states and native controls; dependency evaluation before adopting libraries.
7. **Regression gate:** test all existing workflows plus keyboard focus, Escape, scrolling, responsive reflow, no exposed restricted data, no clinical meaning drift, compare baseline screenshots, and prove only allowed frontend files changed.

## 8. Acceptance and measurements

| Criterion | Measurement |
|---|---|
| Reach core records | Steps and elapsed time from selected case to exact source line |
| Detect an amendment | Correctly identify changed version and affected stale draft |
| Avoid wrong case action | Wrong-case writes blocked during switching and in-flight requests |
| Understand uncertainty | Participants differentiate 'not reported', 'pending', 'conflicting', 'stale', and 'reviewed' |
| Retain feature parity | Every inventoried control has accessible equivalent and passing journey |
| Accessibility | WCAG 2.2 AA-oriented automated **and manual** checks; no unearned conformance claim |
| Technical boundary | Repository diff contains no backend, database, API, identity, validation, or clinical-rule modifications |
| Performance | Before/after navigation, rendering and large-record responsiveness measurements |

## 9. Decision log

- **D-UX-01 — Preserve current implementation until workflow evidence supports replacement.** No automatic Next.js/React migration. Alternative is a full framework rewrite, rejected *for this initial slice* due to risk without measured benefit.
- **D-UX-02 — Evaluate two IA concepts.** Favor role-aware workspace exploration, but do not conflate role presentation with access control.
- **D-UX-03 — Provenance first.** Source statement, original version, uncertainty, and amendment history cannot be reduced to decorative badges.
- **D-UX-04 — No new functionality by navigation illusion.** Menu labels must reflect what already works. Appointments, messaging and prescription workflows are research references unless verified implemented.
- **D-UX-05 — Incremental review.** Use isolated branch/PR, preserve original screens until parity evidence, do not merge automatically.

## 10. Scope and verification receipt

This document is the only proposed artifact in this initial research commit. **No application code, tests, API, database, authentication, authorization, or clinical business logic has been modified.** This is not a claim that the existing frontend has been redesigned or its current automated tests have been freshly executed.

Research is preliminary. The next gate is a complete code-and-browser feature inventory, competitor evidence ledger, and screenshot baseline before implementation.
