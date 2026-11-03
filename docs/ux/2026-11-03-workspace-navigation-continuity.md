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

## Boundaries and completion

Preserve the existing five destinations, callbacks, session, response validation, source versions, manual-document distinction, permissions, drafts and exact-intent recovery. No speculative appointment, messaging, medication or professional-signoff workflows. No dependency or backend change. The full initiative still requires genuine role authority from separately scoped work, participant studies, broader accessibility evaluation and remaining branch reconciliation; this increment cannot declare the entire redesign complete.
