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

## Source-entry keyboard continuation — 3 November 2026

Continues the same draft #386 and OI-010 after verified navigation head
`752e5b2767203099a08b26b035f9be24e9e99b97`. Newer second-opinion and
manual-provenance drafts remain separate; this is not their convergence.

### Fresh observed baseline

Capture-only head `bc069145411c16d193c82125143011d11ee005f5` passed
[run 41739329494](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41739329494).
Artifact `13280986919` SHA-256:
`e79f440b6ab9e415deb4f1c1b2b24f71d8524af33de7d6718053a1e047f5e40c`.
All 463 archived blobs and executable modes match the commit. Runtime files
are identical to the preceding verified head.

1. **Request source versions:** native Enter activates the actual case action.
   Its real PostgreSQL-backed request succeeds at both 390 and 1280 pixels.
2. **Enter the returned history:** focus has fallen to BODY when the trigger
   was disabled. The history heading begins at y=831.5 and y=839.65625
   respectively in 900-pixel viewports. Fresh screenshots were inspected.
   The records are present, but the requested reading destination has no
   focused entry point and sits near the bottom edge.
3. **Continue reading:** the next controls remain in normal document order.
   No claim is made that baseline records are inaccessible or that measured
   task speed/usability improved.

### Decision and acceptance

Focus the existing source-history heading after an explicit source-version
request succeeds for the same patient/case. Use its existing negative tabindex,
focus outline and sticky-header scroll clearance. This adds no visible control,
new destination, dependency or record request.

Alternatives considered: retaining the current BODY fallback leaves the observed
entry problem; adding another jump link needs another user action; making every
source-index update move focus would also move users after imports and unrelated
refreshes. The selected presentation-only intention is set exclusively by the
existing Inspect source versions button.

The intention is canceled on a different focus choice, section navigation,
disconnect, changed patient, or unsuccessful/other record operation. A late
response must not move focus away from a user's chosen control, including when
they have left and returned to Records. It is consumed once; a fresh explicit
action can still focus the returned history. Source loading, error handling,
permission checks and response validation remain owned by unchanged RegistrySession.

Fresh official [W3C focus-order guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-order)
and [focus-not-obscured guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)
were read on 3 November 2026. They support a logical, visible focus sequence;
this particular handoff is a design inference, not a prescribed pattern or a
claim that the baseline failed a specific WCAG criterion.

The browser acceptance uses native Enter/Tab, actual authorized source responses,
390/1280 widths and a 320×256 short viewport. It checks one GET/no writes, patient
identity, existing fresh-response filter reset, heading visibility and next-control
order. Delayed delivery retains each actual response/body/status and verifies
focus-choice and section-change cancellation. The inherited actual denial and
reauthorization path checks that failed entry cannot replay focus.

Local inherited 415 client tests, build and 13 dependency controls passed before
the change; the new behavior requires its own hosted result. Final acceptance
and screenshot inspection are pending at this source checkpoint and will be
recorded in the PR and canonical UX notes without claiming an unrun result.
No separate full API/recovery suite, independent reviewer, assistive-technology
participant study, full WCAG conformance or clinical validation is established.
Draft, unmerged, undeployed; independently fictional inputs only.

### Screenshot-driven refinement

The first focus implementation, `92d6580b3b72fcbf8ee5346f2dd05edb89ab39d5`,
passed [run 41740084294](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41740084294).
Artifact `13281131549` SHA-256
`205d66cadf89efa52c5ad8f95409983b9b7ef47ad2f3527c353dd451e8ba71f8`
and all 464 source blobs/modes were verified. All new focus, cancellation and
inherited connected assertions passed. Visual inspection nevertheless found
the heading remained at the same bottom-edge position on mobile and desktop:
focus alone does not scroll an already-visible element.

The refinement explicitly positions that heading at the start of the reading
area after focusing without automatic scroll. Root scroll padding supplies the
measured header clearance; this heading no longer doubles that padding with
an additional top scroll margin. The browser check now requires the heading
within 32px below the sticky header (or viewport top in the short-screen
fallback), as well as full visibility. This strengthens acceptance; it does
not change the request, focus-cancellation or permission behavior. Final
refined-head acceptance remains pending at this source checkpoint.
