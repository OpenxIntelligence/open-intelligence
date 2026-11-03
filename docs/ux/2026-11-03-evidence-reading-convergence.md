# Connected evidence workspace: reading convergence

Research and implementation date: 3 November 2026, America/New_York.
Existing work: OI-007, OI-009 and OI-010. This is a frontend-only continuation of the existing product research program, not a replacement architecture or completed clinical platform.

## Baseline and source ownership

- Implementation parent: #314, `4bbd74c364983152c158a03a8efd8273ee323f10`. The actual downloaded source archive and commit marker come from run 41659720068, artifact 13241611192, SHA-256 `ca945590b07744821bfd0cd8ee668f9f214fdf00500ba0b27f7f8fa7850052d3`.
- Reading donor: #305, `aea88341e260a4829d5b1647d5395b78ca17bfa6`. Artifact 13238971872, SHA-256 `7ae4a1f989a41a6e2fa2168b873452d25000aafe0118da472886acd174d6486b`, verified on download. Only the source-reading presentation, header/focus behavior, related CSS and reading acceptance helper are reused.
- Existing Notion: https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f
- Existing full 22-deliverable research report: https://docs.google.com/document/d/1F6MWCvuJK4d4DGDst9xjcCg15CKi-4IuRJFllOGndxg/edit
- #308/#309 already address related navigation on the reading branch. #314 already has the combined evidence-aware navigation handler. Preserve that handler, including metadata and authored-evidence dismissal; do not replace it with the older donor handler.

## Audit and current feature map

The source and archived actual-browser screenshots were inspected. This baseline is an artifact review, not a newly conducted hands-on competitor study or a new baseline browser run. `h1-records-desktop.png` and `h1-records-mobile.png` show lengthy source metadata and setup copy preceding source reading. Code confirms that quotations are in a separate list after all versions, filters are absent, the header lacks active-patient context, and Overview's identity copy incorrectly says no record is loaded even when sources are loaded.

| Existing location | Existing capability / owner | Presentation change | Regression boundary |
|---|---|---|---|
| Overview | Session connection, identity creation/read/recheck; RegistrySession | Active authorized patient in shared header; truthful loaded-source wording | Credential lifecycle, grants, create request key and all validation unchanged |
| Overview | PatientContinuity, draft continuation, scoped counts | Preserve component and navigation | No projection, recovery or business-state changes |
| Records | Case mappings and SourceIntake | Preserve all controls and receipts | No upload, encoding, original-byte or uncertain-response changes |
| Records | Current/historical versions and source assertions | Group literal quotations with their source; local metadata/version filters; native provenance disclosure | Same SourceIndex; current assertions never relabelled historical |
| Records → Investigations | Ask about this statement | Keep existing action beside each eligible current quotation | Same beginQuestionFromSourceReading method; no new save/model/authority behavior |
| Journey | Source-linked World Model | Preserve component | Same loaded projection, clocks and missingness |
| Investigations | Authored questions; metadata citations; authored evidence; reports; follow-through | Preserve all owners and actions | No decoder, session, permission, download or durable-state changes |
| Review | Verification return/history and exact retry | Preserve component | Same request key, intent, scope and independent grants |
| Shared navigation | Canonical callbacks dismiss prepared content | Retain all four existing dismissals; add heading focus | Same-section navigation still dismisses before returning |
| Retained web/ reference | Existing synthetic reference workflows | No changes | Not claimed migrated, retired or removed |

These are operator-controlled fictional workflows. Patient and clinical *reading layouts* do not create account roles. Appointments, messaging, medication management, signed notes and professional clinical review are not manufactured to satisfy a navigation mockup.

## Research, alternatives and decision

The existing report covers 15 product families, competitor technology unknowns, qualitative benchmarks, weaknesses, guidance and frontend technology choices. Reuse it without converting marketing descriptions into hands-on measurements. No representative participant research or comparative task timing was performed here.

| Rechecked source | Date / evidence class / confidence | Finding and relevance | Action / status |
|---|---|---|---|
| https://design-system.nhsapp.service.nhs.uk/patterns/the-structure-of-the-nhsapp/ | Read 2026-11-03; official published research summary; high confidence in stated scope; publication date not shown | NHS reports task-oriented use and navigation research. This is evidence about its app, not proof of Open Intelligence outcomes. | Preserve existing task destinations; improve continuity within them. Implemented candidate; usability benefit unmeasured. |
| https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum | Read 2026-11-03; official guidance; high confidence; publication date not established | Sticky content must not entirely obscure keyboard focus. | Reuse measured header clearance and nonsticky fallback; test short viewports. |
| https://w3c.github.io/wcag/understanding/reflow.html | Read 2026-11-03; official guidance; high confidence; publication date not established | Reflow must keep content and functionality available at narrow effective widths. | Test both layouts at 320/390/768/1280px, long identifiers and doubled text. This is not full zoom/conformance certification. |

Two viable structures were considered: (A) keep the combined app's separate source metadata and findings lists, adding only an index; (B) reuse the already tested source-adjacent reading component and preserve all existing combined actions. A is smaller but retains distance between quotation and provenance. B is selected as the implementation decision because it restores existing validated presentation work without introducing a second source store or dependencies. A third possibility, separate patient/clinician application shells, is deferred because genuine account authority is not supplied by this baseline.

Retain React/Vite/TypeScript, native controls and existing CSS. No dependency adoption, Next.js migration, external service, new validation or backend change. Existing styling tokens and source-reading densities are reused. Copy corrections describe available behavior and avoid a claim of clinical approval.

## Plan and acceptance

1. Freeze downloaded #314 baseline and inspect existing source/visual evidence.
2. Reuse #305 reading/header presentation only; carry the existing #314 question action into the source row. Preserve every combined-owner callback and busy guard.
3. Extend the existing actual PostgreSQL/FastAPI/built-React journey with reading acceptance, direct reconnect/denied-read/reset checks, native keyboard source-to-question activation and new screenshot evidence.
4. Run the complete inherited client/build/rights/browser workflow at the published exact head. Preserve baseline tests; report failures before fixes and limits honestly.
5. Compare all other paths byte-for-byte and by executable mode against #314. Keep backend, APIs, database, contracts, session, dependencies, workflows and clinical/business logic unchanged.
6. Append verified results to the existing Notion and Google research records. Keep original specifications/history and branch owners intact.

## Verification status

Implementation and tests are being prepared. Parent/donor passing runs are historical evidence only and do not verify this combined change. No merge, deployment, independent participant study, complete accessibility certification, clinical validation or full-initiative completion is claimed.
