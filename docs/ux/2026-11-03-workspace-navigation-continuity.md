# Workspace navigation continuity

3 November 2026. Frontend-only continuation of OI-009/OI-010 and the existing Product Research & UX Evolution report.

## Grounding

Pinned baseline: PR #382, `0e243e175dfdfe6e6d055531032c3dc284a1adc1`, tree `d26ea69dd77d1e71c3f669a141cec72957ae5f29`. The older supplied #181 identity-only handoff is historical. This baseline includes connected Records, Journey, Investigations and Review, source originals, ordinary text/PDF intake, comparison drafts and verification-return drafts. Patient/clinical reading layouts do not establish authenticated roles.

The existing [22-deliverable UX report](https://docs.google.com/document/d/1F6MWCvuJK4d4DGDst9xjcCg15CKi-4IuRJFllOGndxg/edit) remains the research index; its 15-family landscape, technology assessment, feature inventory and alternatives are not replaced. Its original #200/#218 inventory is historical and subsequent dated receipts describe incremental changes. The [canonical Notion record](https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f) remains the shared decision record.

## Current-run research

| Source | Evidence / date | Application |
|---|---|---|
| [NHS App navigation](https://design-system.nhsapp.service.nhs.uk/patterns/navigate-the-nhs-app/) | Official design guidance read 2026-11-03; publication date not shown; high confidence within documented scope | Keep task destinations recognizable and reachable; this is not proof of Open Intelligence usability. |
| [W3C focus not obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) | Official explanatory guidance read 2026-11-03; high confidence | Preserve measured header clearance and short-viewport fallback. |
| [W3C reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | Official explanatory guidance read 2026-11-03; high confidence | Keep navigation and content usable at narrow effective widths. |
| [SAFER Patient Identification](https://healthit.gov/resources/2025-safer-guide-patient-identification/) | Official page read 2026-11-03, last updated May 6, 2026; high confidence in source metadata | Keep authorized patient context visible. No new identification or clinical authority is introduced. |

## Audit checkpoint

The first commit only adds current-run desktop/mobile captures and DOM geometry to the existing actual PostgreSQL/FastAPI/React browser journey. No runtime file changes. Audit findings and implementation follow inspection of these captures.

Fresh local baseline: 415/415 client tests and production build pass, 13/13 rights controls pass. Local browser startup is blocked by socket permissions and PostgreSQL cannot assume its required nonroot account; no local connected-browser result is claimed. Hosted acceptance remains pending for this capture checkpoint. Previous PR results are historical evidence, not a new execution.

## Current feature map and presentation ownership

All rows below use the same synthetic operator session. Reading density is a preference; it does not authenticate a patient, clinician, caregiver, nurse or administrator.

| Location / source | Current behavior | Proposed location | Dependencies and regression risks |
|---|---|---|---|
| Overview / main.tsx | Connect/disconnect; exact patient open/create/recheck | Retain | RegistrySession; preserve credential clearing and request identity |
| Overview / patient-continuity-view.tsx | Resume questions, source reassessment counts and open records | Retain | Existing projection; no manufactured urgency or completion percentage |
| Shared header / main.tsx | Selected authorized patient, reading layout and API status | Retain | Patient response, ResizeObserver; no role or access inference |
| Workspace rail / main.tsx | Overview, Journey, Records, Investigations, Review | Retain one navigation owner | Existing dismissals and section-heading focus; no duplicate workflow |
| Records / SourceReading | Current/historical source versions, literal quotations, provenance and local filters | Retain beside original source | Same SourceIndex, current-only statements; filter state must survive presentation actions |
| Records / SourceIntake | Deliberate authored-format import with preview and receipt | Retain inside existing disclosure | File selection, confirmation and retry must survive disclosure/navigation rules |
| Records / ReviewedDocumentDisclosure | Ordinary text/PDF preview, immutable original and manual selection/correction history | Retain separate disclosure | Independently permissioned owner; manual selections are not structured clinical assertions |
| Records / original panel | Exact authorized original, keyboard scroll and close-to-opener focus | Retain | Preserve the #382 original focus and version-specific accessible names |
| Journey / WorldModelView | Source chronology, observations, disagreements and missingness | Retain | Existing read projection; no new clinical conclusion |
| Investigations / WorldModelView and question panels | Questions, original quotations, metadata citations, authored comparisons, briefs/reports and follow-through | Retain | Separate grants, in-memory drafts, exact retry intents; no implicit submit |
| Review / ReviewPanel | Nonterminal verification returns, reason drafts and immutable history | Retain | Same question and return owner; no professional-signature claim |
| Retained web/ application | Earlier Python/SQLite synthetic workflows | Retain unchanged | Not a second target frontend or a claim that migration is complete |

## Design alternatives under evaluation

1. Keep navigation at the document start and require scrolling back. It adds no control, but long source histories may increase the effort to change tasks; the new captures measure visibility, not user task time.
2. Add a small header link to the existing navigation landmark. It introduces no second menu, state owner, request or destination. Native fragment navigation can be checked for keyboard focus, reflow and state preservation.
3. Make the full rail permanently sticky or add another menu to the header. A sticky rail can require its own scrollbar at short heights; another menu duplicates controls and adds expansion/focus behavior. Neither is necessary until the smaller option is tested.

No new library is justified by these alternatives. Keep the exact React/Vite/TypeScript lock, CSS and native controls. The broader patient/clinician experience mandate remains open where actual role authority is absent.

## Observed finding and selected implementation

The fresh [baseline run 41714916358](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41714916358) passed at `263018c2636e132dd904ff9a0002012cd3f49690`. Its application files are unchanged from #382. Artifact `13269946798` was downloaded and SHA-256 verified as `4ab8a0191fe1723224bc47ef8a4fc4f7386e03dc18cf758c3891a349e5190c97`; the commit marker matches. Both newly captured bottom-of-Records screenshots were visually inspected.

| Step | Observed health | Evidence |
|---|---|---|
| 1. Open authorized synthetic sources and inspect current/historical originals | Inherited connected journey passed; literal sources and provenance retained | Current-run original-focus and quotation captures, browser log |
| 2. Read to the end of Records at 390px | Navigation problem: all five destinations are above the viewport | Scroll 2,724 CSS px; navigation bottom -2,498px; `workspace-navigation-bottom-390.png` |
| 3. Read to the end at 1280px | Same problem; the visible sidebar area contains no task destinations | Scroll 1,465 CSS px; navigation bottom -940.5px; `workspace-navigation-bottom-1280.png` |

The selected option is a **Change section** link beside the current section in the existing header. It targets the existing navigation landmark with native fragment/focus behavior. The five original buttons, callbacks and heading focus remain unchanged. A 44px minimum link height supports touch; visible focus and wrapping use the current styling. No modal, duplicate navigation, dependency, new browser storage or request is introduced.

The extended browser test checks native Enter and Tab, visibility, reflow, 320/390/1280 widths, a 320x256 short viewport, the unchanged mounted source panel, patient context, filter values and request count. The existing short-header nonsticky fallback remains: at very short/enlarged viewports the header can scroll away to preserve reading space. The link remains keyboard reachable; it is not claimed permanently visible in every viewport.

Final-candidate hosted checks and screenshot inspection are pending at this source checkpoint. Baseline software tests are not participant usability, full accessibility certification or clinical evidence. The separate full backend suite is not rerun for this presentation-only change.

## Boundaries and completion

Preserve the existing five destinations, callbacks, session, response validation, source versions, manual-document distinction, permissions, drafts and exact-intent recovery. No speculative appointment, messaging, medication or professional-signoff workflows. No dependency or backend change. The full initiative still requires genuine role authority from separately scoped work, participant studies, broader accessibility evaluation and remaining branch reconciliation; this increment cannot declare the entire redesign complete.
