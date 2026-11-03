# Open Intelligence — Healthcare UX, accessibility and clinical-context research

Research date: **2 November 2026 (America/New_York)**  
Status: complementary research and frontend acceptance proposal; implementation and test results belong to the [consolidated engineering report](../2026-11-02-product-research-ux-evolution.md).

## 1. Decision and scope

Keep the accepted **React/Vite/TypeScript** frontend and the existing FastAPI/PostgreSQL contracts. Improve navigation, hierarchy, source readability, responsive behavior and status presentation without adding clinical interpretation, new permissions or backend capability. Next.js is excluded by the repository's accepted H1 decision.

The inspected H1 candidate at selected baseline d8de9aaca352cc58b64e9e32440f4ea248b02cb8 exposes an opaque fictional patient identity and authorized, read-only case/source projections. Its patient fields include patient ID, organization, registry status, revision and creation time. It does not supply names, date of birth, verified professional accounts, caregiver delegation, appointments, medication management or secure messaging. A redesign cannot turn these absent capabilities into working services. Patient and clinician layouts can be design directions; a reading-view selector is not an authorization role.

The relevant existing contracts are patient/case scope, immutable source identity and versions, source-reported assertions, review/authority and request/session state. These findings support the existing OI-009 correction-history and OI-010 connected-workflow work, and the H1/#119 frontend seam. They do not create a parallel roadmap or supersede existing owners.

## 2. Evidence and limits

Official standards and guidance establish requirements or recommended practices. Original usability studies establish findings within their studied settings. The interface decisions below are **design inferences** from that evidence and the inspected application; they are not results from Open Intelligence user research.

The current ONC landing page labels the set the **2025 SAFER Guides** and was last updated 27 February 2026. The linked individual PDFs retain **August 2024** footer dates. Record both facts rather than assigning a false publication date. The guides expressly do not establish legal compliance. [SAFER overview](https://healthit.gov/clinical-quality-and-safety/safer-guides/)

AHRQ-funded original research used laboratory, interview, eye-tracking and simulated clinical tasks to study fragmented versus composable EHR displays. It supports investigating fewer context switches and better access to related information. The report notes small samples, technical problems, training differences and additional research needs. It does not prove that this redesign improves patient outcomes or that every single-screen interface is superior. [Original final report, 2021](https://digital.ahrq.gov/sites/default/files/docs/citation/r01hs023708-senathirajah-final-report-2021.pdf)

No patient or clinician interviews were conducted in this research pass. No clinical validation, HIPAA determination or complete WCAG conformance claim is made.

## 3. Healthcare research matrix

All frontend recommendations in this table are pending implementation verification.

| Finding | Verified source | Frontend implication for existing H1 | Boundary and confidence |
|---|---|---|---|
| Patient identity needs a stable, visible place throughout patient work. | SAFER Patient Identification, practices 1.2–1.3, pp. 11–12. | Keep the supplied patient ID and organization in the chart header and clearly distinguish the selected patient from the session context. | High confidence in guidance; source fields are limited to opaque fictional identity. Do not fabricate names, photos or DOB. |
| Record context is lost when related information is scattered across screens. | AHRQ-funded original 2021 report, abstract, methods and limitations. | Keep selected case, document version, statement and source anchor close together; retain a clear return to the source list. | Moderate applicability inference. Measure navigation and task completion; do not claim proven clinical benefit. |
| Result lifecycle, amendments and dates matter independently. | SAFER Test Results, practices 2.1–2.3, 2.7. | Preserve current/superseded state, version links, event date and issue date as separate visible concepts. | High guidance confidence. Display only statuses the API supplies. |
| A result without a flag is not necessarily normal. | SAFER Test Results, practice 2.6. | Preserve existing reported-state text. Empty data should say “Not recorded” or the actual supplied state. | No new interpretation of laboratory values, urgency, risk or normality. |
| Patients need navigable information and understandable communication. | SAFER Clinician Communication, practice 1.4, pp. 12–14. | Use readable labels such as “Records” and “Source details”; explain unreviewed quotations close to the content, not only in a global banner. | High guidance confidence; exact wording is a design proposal, not tested patient feedback. |
| Inbox organization should support relevant work and reduce burden. | SAFER Clinician Communication, practice 2.1. | Apply task-first hierarchy to existing request/status screens; do not populate a fictional inbox. | Messaging is not connected in current H1; implementation deferred. |
| Provenance describes how a resource came to exist, who was involved and which version it concerns. | HL7 FHIR R4 Provenance, scope and usage. | Show source ID/version and dates separately from review state. A hash is an integrity identifier, not clinical verification. | High confidence in standard semantics; this does not claim the current API is a complete FHIR implementation. |
| Privacy obligations cannot be replaced by presentation choices. | HHS minimum-necessary guidance. | Preserve server access checks, refusal behavior and clearing of stale patient content. Keep sensitive content out of screenshots and research unless independently synthetic. | The standard has explicit treatment and individual-disclosure exceptions; do not present universal minimization as a legal rule or UI hiding as access control. |

Primary healthcare sources:

- [SAFER Patient Identification PDF](https://healthit.gov/wp-content/uploads/2025/01/Safer-Guide-6.-Patient-Identification-Final.pdf)
- [SAFER Test Results Reporting and Follow-Up PDF](https://healthit.gov/wp-content/uploads/2025/06/SAFER-Guide-8.-Test-Results-Reporting-Final.pdf)
- [SAFER Clinician Communication PDF](https://healthit.gov/wp-content/uploads/2025/06/SAFER-Guide-1.-Clinical-Communication-Final.pdf)
- [HL7 FHIR R4 Provenance](https://hl7.org/fhir/R4/provenance.html)
- [HHS minimum-necessary guidance](https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/minimum-necessary-requirement/index.html)

## 4. Frontend acceptance criteria

These are testable proposals. “Preserve” means retain the existing API/client behavior and verify it through the redesigned surface; it does not authorize changes to authentication, authorization, validation or clinical logic.

| ID | Acceptance criterion | Verification method | Basis |
|---|---|---|---|
| UX-01 | The currently loaded patient ID and organization remain visible in the patient workspace and Records view. A failed new selection does not leave the prior identity looking current. | Existing session/browser journey plus screenshots during patient change and denial. | SAFER patient identity; existing H1 scope contract. |
| UX-02 | Global workspace navigation and the selected patient's chart navigation are distinguishable by labels and hierarchy. | Landmark/name inspection; keyboard walkthrough. | Design inference from identity continuity and fragmentation research. |
| UX-03 | Source document title/ID, version, source state and relevant dates can be inspected without losing the selected patient/case context. | Authorized-source browser journey. | SAFER result display; FHIR provenance. |
| UX-04 | Event date, issued time and registry-created time retain their original meanings. Formatting must not invent precision or a timezone absent from the supplied value. | Fixture assertions against source text and UI labels. | Existing source and temporal contracts. |
| UX-05 | Source-reported quotations remain literal text with source line and review status. Current, historical, missing and unreviewed do not collapse into “verified.” | Existing hostile-text and source-version tests; visible-state review. | Existing source/review contract; FHIR distinction. |
| UX-06 | Starting a request has a visible in-progress state. Failure never shows a saved/success state. Retry uses the existing action and idempotency behavior. | Existing refusal, retry and late-response scenarios. | User mandate and existing client state contract. |
| UX-07 | Distinguish loading, a successful empty case/source response, and no local filter matches from the error messages the existing client actually supplies. Preserve combined permission/unavailable and validation/network explanations; do not infer a narrower failure cause. | Exercise supported client states and compare displayed copy with the unchanged client contract. No invented backend error distinction or inferred absence of disease. | User mandate; explicit missingness invariant; builder review against RegistrySession. |
| UX-08 | Every navigation button, form, disclosure and source-detail control is operable with keyboard alone; no keyboard trap is introduced. | Tab/Shift+Tab, Enter/Space and Escape where relevant. | WCAG 2.1.1; use native HTML controls first. |
| UX-09 | Keyboard focus is visible and not completely hidden beneath sticky headers, footers or overlays. | Screenshots at desktop and narrow widths while tabbing; programmatic geometry as a supplement. | WCAG 2.4.7 and 2.4.11. |
| UX-10 | Normal text meets 4.5:1 contrast; eligible large text meets 3:1. Required component boundaries/states meet applicable non-text contrast requirements. | Computed-color checks for actual tokens; visual review of interactive states. | WCAG 1.4.3 and 1.4.11. |
| UX-11 | Color is accompanied by state text or another non-color cue for selected/current/superseded/error/loading indicators. | Remove color mentally or inspect grayscale; check accessible names. | WCAG 1.4.1. |
| UX-12 | Pointer targets satisfy the 24×24 CSS-pixel AA rule or a documented exception. Aim for 44×44 for primary controls as a product decision. | DOM bounding boxes and spacing inspection at narrow widths. | WCAG 2.5.8; 44×44 is the enhanced AAA target, not the AA minimum. |
| UX-13 | Ordinary content reflows at 320 CSS pixels without loss or page-wide horizontal scrolling. Genuine two-dimensional content may use a bounded scroll area. | 320px viewport, equivalent 400% zoom check and long-ID fixtures. | WCAG 1.4.10 and its exceptions. |
| UX-14 | Inputs have persistent visible labels. Existing validation failures identify the problem in text and preserve entered values where existing behavior allows. | Label associations, missing/invalid input scenarios; no validation-rule changes. | WCAG 3.3.1–3.3.2. |
| UX-15 | Non-focus-changing loading, success and error messages are exposed to assistive technology without announcing the entire workspace on every render. | Inspect live regions; manual screen-reader pass before a full accessibility claim. | WCAG 4.1.3. |
| UX-16 | New controls do not disable paste or obstruct password-manager input. Existing authentication behavior remains intact. | Read-only login UX inspection; document existing restrictions for separate scope. | WCAG 3.3.8; no authentication redesign authorized. |
| UX-17 | Opening/closing a native disclosure keeps its accessible name and focus behavior intact; hidden details remain reachable by keyboard. | Keyboard and accessibility-tree inspection. | Native semantics; keyboard/focus requirements. |
| UX-18 | A mobile menu or disclosure never hides the only route to existing functionality. If a wide data table remains, it does not force the entire application to scroll horizontally. | Supported navigation inventory across viewport sizes. | Reflow; user's feature-preservation requirement. |
| UX-19 | A reading-mode choice changes wording/density only. It neither claims professional identity nor changes grants, permitted requests or loaded data. | Request/client diff review; rerun access/clearing regressions. | Existing authorization boundary and user mandate. |
| UX-20 | Error and unavailable states offer a concrete existing action, such as retry or return to patient overview, without suggesting unsupported scheduling, messaging or clinical support. | Interact with every recovery link/button. | User mandate; task-completion inference. |

WCAG references (the normative [WCAG 2.2 Recommendation](https://www.w3.org/TR/WCAG22/) is dated 12 December 2024; the Understanding pages below are informative explanations):

- [Keyboard 2.1.1](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html)
- [Focus Visible 2.4.7](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)
- [Focus Not Obscured 2.4.11](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)
- [Contrast 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
- [Non-text Contrast 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
- [Use of Color 1.4.1](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html)
- [Target Size 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
- [Reflow 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html)
- [Error Identification 3.3.1](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html)
- [Labels or Instructions 3.3.2](https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html)
- [Status Messages 4.1.3](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)
- [Accessible Authentication 3.3.8](https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html)

This is a scoped checklist for the changed experience, not the complete WCAG standard. Automated browser checks only cover some failures; manual assessments and inclusive user testing are still needed. [Playwright accessibility testing guidance](https://playwright.dev/docs/accessibility-testing)

## 5. Role-sensitive journeys

These are product hypotheses and frontend directions. They must be reconciled with actual supported roles before implementation. They do not invent user research, actual patient accounts or professional authority.

| Audience | Intended job | Presentation direction | Current H1 limit |
|---|---|---|---|
| Patient | Understand what records are available and where a statement came from. | Plain labels, record/source list, readable quotation, visible date/version and review state. Keep detailed identifiers available in a disclosure. | Fictional identity only; no diagnosis summary or live clinical explanation. |
| Authorized clinician | Inspect source context accurately and move between case, document history and statements. | Denser source list; source/version/specimen/date metadata adjacent to quoted content; stable chart scope. | No professional identity verification or clinical sign-off. |
| Authorized caregiver | Understand whose record is being viewed and the scope of delegated access. | Clear “viewing records for” context when supported by canonical authority data. | Delegation is absent; do not implement a caregiver selector or grant flow. |
| Researcher/coordinator | Inspect existing source evidence without confusing extraction with interpretation. | Exact source anchors and version provenance; clear access/refusal/status. | Do not add a new role, research authorization or data export pathway. |

A useful wording distinction is “No sources were returned for this case,” not “No health problems.” A current document version is not automatically a reviewed conclusion. A successful registry read is not proof of present clinical completeness. These distinctions come from existing product invariants, not a new medical rule.

## 6. Information-architecture alternatives

### Concept A — Purpose-specific entry, shared patient chart

A patient-facing reading view emphasizes available records and understandable source content. A care-team reading view emphasizes case selection, source versions and inspection. Both lead into the same patient-scoped chart and canonical data. Global navigation stays visually separate from chart sections. Unconnected functions retain truthful status rather than appearing populated.

### Concept B — One universal object explorer

A single dense workspace lists patients, cases, documents, versions and assertions with shared filters. It is efficient for technical source investigation but asks every user to understand the object model and version vocabulary immediately.

| Criterion | Concept A | Concept B |
|---|---|---|
| Patient learnability | Better fit to plain-language entry and progressive disclosure. | Requires knowledge of technical source objects. |
| Professional efficiency | Good if source details stay adjacent and context persists. | Strong for repeated source inspection. |
| Information density | Adjustable by presentation without duplicating data. | Dense by default; weaker on small screens. |
| Accessibility | Familiar sections and native controls; fewer simultaneous navigation targets. | Larger tables and complex keyboard patterns can create more implementation work. |
| Clinical context | Patient/case header remains primary. | Easy for object metadata to dominate the patient context. |
| Scalability | Existing domain sections can grow behind a stable chart shell. | More objects increase filter and navigation complexity. |
| Preservation | Existing actions/sections map into the same canonical workflow. | Preserves data but may force a disruptive navigation change. |
| Implementation complexity | Modest presentation refactor if session/client code is retained. | Risks replacing the current workspace with a new explorer. |
| Main risk | Superficial role switching could imply unavailable authorization. | Technical vocabulary and cognitive load for patients. |

**Recommendation: Concept A**, implemented only with current data and behavior. Use technical metadata disclosure inside the chart to retain the strongest part of Concept B. The reading modes must be clearly described as presentation choices while H1 lacks real roles. This recommendation is a heuristic design decision, not a validated usability ranking.

## 7. Design-system direction

Use an authored set of CSS custom properties for surfaces, text, borders, focus, status, spacing and typography. Define shared primitives for section headings, buttons, labeled fields, status notices, key-value metadata, source rows and disclosures. Reuse existing React state and event handlers.

Choose system fonts, readable base text, restrained surfaces and borders, and a single high-contrast interaction accent. Avoid making every metadata field a card. Put current task and selected patient first; place dense identifiers within inspectable source details. Use text labels for statuses. Long opaque IDs and hashes must wrap or scroll in their own bounded region without widening the app.

A 16px base size, comfortable line height, 4/8px spacing increments, and 44px primary controls are proposed design defaults, not WCAG requirements. Determine breakpoints from content failures; explicitly inspect 320px, a typical mobile width, tablet and desktop. Preserve keyboard-visible focus and reduced-motion preferences if motion is added. The redesign needs no decorative imagery or external font dependency.

## 8. Validation and evidence plan

The inspected frontend already has TypeScript checks, Node client tests, a rights gate and a standard-library CDP browser journey exercising actual FastAPI/PostgreSQL integration. Extend that harness instead of adding a new test framework for this slice.

Record before/after screenshots with exact commit, viewport, route, scenario and data provenance. Inspect the screenshots before accepting them. Preserve credential and authorization clearing tests, literal hostile-text rendering, amendment history and read-only source inspection. Compare changed-file paths against frontend/documentation scope and review the diff for accidental client/API behavior changes.

Measure navigation steps, whether source context remains visible, task success/failures, console errors, response/loading behavior, built asset size and overflow using the same scenario and machine. Do not infer improved speed from screenshots or reduced code. A user study should later measure patient comprehension and professional task performance; only report those results after running it with appropriate participants and authorization.

The research agent executed no product tests and claims no implementation passes. The engineering report must update each adopted criterion with executed evidence, unresolved failures and limits.
