# Open Intelligence — Product Research & UX Evolution

**Research and design date:** 2 November 2026, America/New_York  
**Scope:** frontend-only improvement of the selected #200 H1 React workspace snapshot

**Original audit baseline:** [PR #200](https://github.com/OpenxIntelligence/open-intelligence/pull/200), commit `d8de9aaca352cc58b64e9e32440f4ea248b02cb8`, tree `f46b666e63dd1ae0d842f0480b5ab942dc16e8b9`  
**Reconciled implementation parent:** `68935c9fc60ef229aa9ff6cc4238153dc01a9b91` (upstream unused-parser cleanup; final boundaries compare with this parent)  
**Status:** research, source inventory, frontend implementation and final local verification complete for this bounded cycle; [draft PR #218](https://github.com/OpenxIntelligence/open-intelligence/pull/218) is published and unmerged. Hosted CI passed on the published implementation head in [run 41564125200](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41564125200); later documentation-head checks remain separately visible in [PR checks](https://github.com/OpenxIntelligence/open-intelligence/pull/218/checks). Existing-workspace documentation publication is in progress.

## Outcome and interpretation

The useful next step is to make the existing H1 patient and source workflows easier to understand and inspect. The selected design keeps one canonical session/client and presents two reading layouts: a patient view with plain language and a clinical view with denser source context. A persistent selected-patient header separates identity from workspace navigation; a dedicated chart keeps source versions, literal reported statements and provenance together.

This is an implemented frontend increment over existing services, not a new account model or a completed clinical platform. The selected #200 source snapshot supports fictional identity creation, authorized identity reads, case mappings and read-only source history. Journey, Investigations and Review remain explicitly unconnected in this React lane. The broader reference application remains present in `web/`; this work does not remove or claim migration of its features. Parallel request and intake increments are identified separately in §14.

The redesign adds no production or development dependency. It preserves React/Vite/TypeScript, the current native controls and existing browser harness. The final scope comparison found all 198 protected files byte- and mode-identical to the reconciled parent, including API contracts, schemas, authentication, authorization, validation, clinical rules and the source ledger. The exact comparison and its limits are recorded in §21.

### Source baseline and upstream reconciliation

The original screenshots and baseline executions remain attributed to `d8de9aaca352cc58b64e9e32440f4ea248b02cb8`. During development, [PR #200 advanced by one cleanup commit](https://github.com/OpenxIntelligence/open-intelligence/compare/d8de9aaca352cc58b64e9e32440f4ea248b02cb8...68935c9fc60ef229aa9ff6cc4238153dc01a9b91) to `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`. Its sole change deletes 133 lines in the unused alternate `apps/web/src/source-model.ts` module; no production or test consumer was found. The live `RegistrySession` continues to use `source-contracts.ts`.

The local implementation parent was advanced to that commit without restoring the deleted file. This inherited cleanup adds no user-facing feature, endpoint, grant, dependency or changed live validation behavior. Final scope evidence compares against the reconciled parent. It must not misattribute the upstream deletion to this UX change or relabel the older baseline executions as runs against the newer parent.

### Evidence classes

- **Implemented:** visible in the inspected code, with the relevant file identified.
- **Executed:** a check actually ran; this report names its scope and limits.
- **Documented public capability:** a vendor or standards body describes it; this is not a hands-on product test.
- **Research finding:** an original study's finding in its stated setting.
- **Design inference:** a reasoned decision for this product, not a user-study result.
- **Pending:** not yet verified or not available in the current code.

No patient or clinician participant study was conducted. No performance superiority, clinical safety, HIPAA compliance or WCAG conformance claim is made.

## Deliverable index

The requested 22 outputs are covered below and in the linked supporting research. They share one report so that feature truth, design decisions and validation do not diverge across duplicate documents.

| # | Required output | Evidence and status |
|---|---|---|
| 1 | Healthcare Competitor Landscape | §1; [15-family landscape](research/competitor-research.md); public research |
| 2 | Competitor Technology Stack Research | §2; narrowly scoped verified technologies and unknowns |
| 3 | Competitor UX/UI Benchmark | §3; qualitative criteria, no invented scores |
| 4 | Competitor Weakness and Opportunity Analysis | §4; study findings separated from anecdotes |
| 5 | Healthcare UX Research | §5; official guidance and original research |
| 6 | Clinical Workflow Research | §6; current H1 tasks and preserved reference contracts |
| 7 | Patient Experience Strategy | §7; implemented reading layout, no patient account claim |
| 8 | Doctor Experience Strategy | §8; implemented clinical reading layout, no clinician authority claim |
| 9 | Clinical Safety and Human Factors | §9; concrete presentation boundaries |
| 10 | Accessibility Research | §10; criteria and limited verification scope |
| 11 | Privacy and UX Considerations | §11; unchanged server/client authority |
| 12 | Frontend Technology Evaluation | §12; [full candidate evaluation](research/frontend_technology_evaluation.md) |
| 13 | Design System Proposal | §13; implemented component/token conventions |
| 14 | Existing Application Audit | §14; exact baseline and current-run screenshot observations |
| 15 | Complete Feature Inventory | §15; H1 actions and all 16 retained reference section IDs |
| 16 | Current UX Problems | §16; findings tied to observed baseline steps |
| 17 | Proposed Information Architecture | §17; selected shared-chart structure |
| 18 | Patient Chart Design | §18; source fields, states and absence limits |
| 19 | Design Alternatives and Decision Log | §19; three considered alternatives and rationale |
| 20 | Frontend Implementation Roadmap | §20; completed scope and remaining work |
| 21 | QA and Regression Testing | §21; executed baseline and final local checks, separate hosted CI status |
| 22 | Final Product UX Evaluation | §22; bounded assessment and remaining evaluation |

Supporting evidence:

- [Healthcare competitor research](research/competitor-research.md) and [50-entry source register](research/competitor-sources.json), including one explicitly excluded source.
- [Healthcare UX, accessibility and clinical-context guidance](research/healthcare_ux_guidance.md).
- [Frontend technology evaluation](research/frontend_technology_evaluation.md) and [guidance/technology source register](research/guidance-sources.json).
- [H1 workspace design decision](2026-11-02-h1-workspace-design.md).
- [Implementation plan](../superpowers/plans/2026-11-02-h1-workspace-ux.md).
- [Durable verification index](evidence/README.md) and [screenshot index](screenshots/README.md).
- Repository truth: [main.tsx](../../apps/web/src/main.tsx), [records-panel.tsx](../../apps/web/src/records-panel.tsx), [registry-client.ts](../../apps/web/src/registry-client.ts), [source-contracts.ts](../../apps/web/src/source-contracts.ts), [styles.css](../../apps/web/src/styles.css), [reference index](../../web/index.html).

## 1. Healthcare Competitor Landscape

Research covers Epic/MyChart, Oracle Health/Cerner, MEDITECH Expanse, athenahealth/athenaOne, eClinicalWorks/healow, NextGen Healthcare, Elation Health, DrChrono/OnPatient, Tebra, Practice Fusion, AdvancedMD, Canvas Medical and the NHS App. Flatiron OncoEMR/CareSpace and Siemens/Varian ARIA add oncology-specific context.

The strongest transferable patterns are clear patient task entry, a recognizable distinction between cross-patient work and the selected chart, direct access from a summary to its underlying record, and source context near the active task. None implies adding appointments, medication management, messaging or clinical decisions to an application that does not implement them.

The [full landscape table](research/competitor-research.md#2-healthcare-competitor-landscape) records each product's documented capabilities, useful pattern and uncertainty. Public documentation and interface examples were examined; no authenticated competitor instance was used, no clinical workflow was timed and no vendor accessibility rating was assigned.

## 2. Competitor Technology Stack Research

Public technical evidence is narrower than a company's complete stack:

| Product group | Verified scope | Information still unknown |
|---|---|---|
| Epic | Hyperdrive web-based client and Windows-native plugin infrastructure; public FHIR integration surface | MyChart framework, component library, state management and testing implementation |
| Oracle, MEDITECH, athenahealth, eClinicalWorks, NextGen | Documented FHIR or other interoperability interfaces, with product-specific differences | Proprietary frontend frameworks and full production architectures |
| Elation, DrChrono, Tebra, Practice Fusion, AdvancedMD | Public APIs or patient-app integration documentation | Current internal UI libraries, mobile languages and runtime dependency versions |
| Canvas | Python SDK, sandboxed extensions and documented ORM views; separate public mobile reference manifest includes React Native/Expo/TypeScript | Entire proprietary EHR stack and production adoption of the reference app |
| NHS App | Public frontend library uses npm/Sass with optional Nunjucks macros | Every native or embedded service implementation |
| OncoEMR and ARIA | Public product surfaces; ARIA's documented DICOM relationship | Current frontend, state and visualization stacks |

See the [verified-technology table and sources](research/competitor-research.md#6-competitor-technology-research). A website's appearance, marketing-site JavaScript or a company's general job listing cannot establish the clinical application's stack. FHIR is an interoperability contract, not evidence of React.

**Decision:** retain the already accepted React/Vite/TypeScript frontend. No competitor finding supplies a reason to replace it.

## 3. Competitor UX/UI Benchmark

The benchmark is qualitative because no comparable end-to-end tasks were executed across vendor deployments. The [complete matrix](research/competitor-research.md#3-benchmark-by-requested-ux-dimension) covers patient/clinician usability, navigation, chart organization, workflow efficiency, dashboards, consistency, accessibility, mobile, density, search, documentation, interoperability, performance and interaction complexity.

| Pattern | Relevant evidence | Bounded Open Intelligence application |
|---|---|---|
| Task-oriented patient home | [NHS App structure research](https://design-system.nhsapp.service.nhs.uk/patterns/the-structure-of-the-nhsapp/) | Make Home and My records prominent; group unconnected destinations separately |
| Patient context distinct from work list | [athenaOne service description](https://www.athenahealth.com/sites/default/files/media_docs/athenaOne-Service-Description.pdf) | Separate workspace navigation from the selected-patient chart |
| Related information adjacent to active work | [Elation product description](https://www.elationhealth.com/platform/ehr/) | Wide clinical source layout with responsive stacking |
| Summary to complete record | [Tebra patient-management documentation](https://helpme.tebra.com/Clinical/Patient_Management) | Overview action opens source records; details remain available |
| Imported information retains provenance | [Oracle EHR documentation](https://docs.oracle.com/en/industries/health/oracle-health-ehr/ehrug/introduction.html) | Preserve source/version/date and unestablished review state |
| Search with record context | [eClinicalWorks PRISMA](https://www.eclinicalworks.com/products-services/interoperability/prisma/) | Filter only already loaded sources, retaining selected patient/case |

Vendor pages establish documented or marketed patterns. The application choices in the final column are design inferences, not proof that copying a pattern improves outcomes.

## 4. Competitor Weakness and Opportunity Analysis

The research supports investigating navigation burden, fragmented context, access/onboarding friction and the gap between data availability and comprehension. It does not support a universal ranking of EHR usability.

Original studies have more weight than anonymous comments but still have setting/version limitations. A [multi-center EHR usability and safety study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7646875/) and [navigation-path research](https://pubmed.ncbi.nlm.nih.gov/32937215/) support measuring tasks and errors rather than judging only visual style. A [2025 MyChart patient study](https://www.jmir.org/2025/1/e66353) describes access and information-availability experiences in one hospital, not every MyChart deployment.

G2, Capterra, Software Advice and Reddit supplied anecdotal hypotheses. They were not counted as independent representative samples; syndicated reviews may overlap. One Capterra “Epic” listing mixed a healthcare product with a children's reading app and was excluded.

The opportunity is to reduce avoidable context switching while preserving identity, complete source history, honest error states and accessible navigation. The implemented candidate addresses those presentation problems. Reduced task time or improved patient comprehension remains to be measured.

## 5. Healthcare UX Research

The [healthcare guidance report](research/healthcare_ux_guidance.md) translates official sources into 20 scoped acceptance criteria.

- [SAFER Patient Identification](https://healthit.gov/wp-content/uploads/2025/01/Safer-Guide-6.-Patient-Identification-Final.pdf) informs persistent identity and clear selection. H1 only supplies opaque fictional IDs and organization; no name, photograph or date of birth is invented.
- [SAFER Test Results](https://healthit.gov/wp-content/uploads/2025/06/SAFER-Guide-8.-Test-Results-Reporting-Final.pdf) informs separate event/issued/received dates and visible result/version states. It does not authorize new interpretation, urgency or normality.
- [SAFER Clinician Communication](https://healthit.gov/wp-content/uploads/2025/06/SAFER-Guide-1.-Clinical-Communication-Final.pdf) informs readable communication and task organization; no messaging feature is added.
- [AHRQ-funded display research](https://digital.ahrq.gov/sites/default/files/docs/citation/r01hs023708-senathirajah-final-report-2021.pdf) informs adjacent context and fewer unnecessary screen transitions. Its sample/training/technical limitations prevent a broad clinical-benefit claim.
- [FHIR R4 Provenance](https://hl7.org/fhir/R4/provenance.html) informs distinctions among source identity, version, origin and review. H1's custom projection is not described as a full FHIR implementation.

The SAFER landing page labels the set “2025 SAFER Guides” and was updated in February 2026; individual linked PDFs retain August 2024 dates. Both facts are preserved in the source register. The guides do not themselves establish legal compliance.

## 6. Clinical Workflow Research

The actual H1 workflow is **connect synthetic credential → open an exact patient identity → check permitted case mappings → inspect source versions and current source-reported statements → recheck access or open another patient**. Creation is a separate operation and does not grant read permission.

The existing source contract supports document history and reported-state preservation, not a physician encounter, signed clinical note, prescription, administered therapy or diagnostic conclusion. The frontend therefore improves source inspection without presenting it as an operational EHR encounter.

The retained reference app contains broader synthetic question, draft, evidence, option and amendment workflows. Their current locations appear in §15. This redesign preserves those files and does not place simulated equivalents into H1.

Clinical workflow questions for later research include how an authorized clinician reconciles conflicting sources, when a patient wants greater detail, and how a professional recognizes the difference between source transcription and an accepted interpretation. These require appropriately authorized participant evaluation. No answers are fabricated from the design.

## 7. Patient Experience Strategy

The patient reading layout begins with understandable tasks: **Home**, **My records**, and a visible selected-record identity once the existing server permits it. Session setup and fictional creation remain available, while the main work area prioritizes opening and inspecting the record.

Source statements use the label “What the report says,” preserve original text and show their reported state, source line and “Clinical review: not established.” Technical identifiers, SHA-256, receipt date, specimen and supersession references remain directly reachable in a native disclosure.

This layout is a presentation preference in a development workspace. It is not a patient account, proof that the viewer is the patient, caregiver delegation or new permission. The screen explains that changing the reading view does not change access. H1 does not supply appointments, medications, messages, health summaries, unread counts or verified diagnoses; none are fabricated to fill a dashboard.

## 8. Doctor Experience Strategy

The clinical reading layout emphasizes **Workspace**, **Source records**, exact identity, case mappings and source context. At sufficient width, case selection sits beside the source history; smaller widths stack these regions. Specimen and case-system details are more immediately visible.

It uses the same RegistrySession, requests, parsed response and available actions as the patient reading layout. Changing view must neither fetch data nor change grants. A clinical label does not assert that the viewer is a credentialed physician.

Patient search currently means entering an exact opaque patient ID. There is no backed population search, recent-patients list, schedule, unfinished clinical documentation queue or clinical-signature workflow. Those product needs belong to future domain work and cannot be solved by relabeling a button.

## 9. Clinical Safety and Human Factors

The implemented presentation follows these bounded invariants:

| Invariant | Visible behavior | What it must not imply |
|---|---|---|
| Identity follows the loaded response | Header uses `state.patient`, never the editable input | Typing an ID does not select or authorize it |
| Source version differs from clinical conclusion | Current/superseded source labels remain explicit | “Current” does not mean correct, normal or clinically reviewed |
| History remains inspectable | All versions are available; filters are reversible | A filter does not delete history or update clinical truth |
| Literal statements keep their anchors | Quotation, source version and line remain adjacent | Formatting is not interpretation |
| Missing means only what the response supports | Empty cases, empty source list and no local matches have different wording | No returned source does not mean no illness or no prior care |
| Access failure clears affected data | Existing client refusal/race behavior remains authoritative | A local view choice is not access control |
| Acknowledgment follows actual outcomes | Existing create response and retry behavior preserved | An uncertain write never says saved |

**Historical quotation limit:** the active source contract supplies quotations only for current versions. An earlier version's row explicitly says that this response does not provide its historical quotations. It must not suggest that the historical report contained no findings.

**Original-byte limit:** this H1 UI shows source metadata and reported statements, not original-document bytes. The unused alternate `source-model.ts` existed at the original audit baseline and was subsequently removed upstream; it is absent from the reconciled parent. The active `source-contracts.ts` parser remains unchanged. No original-document fetch is added.

The human-factors rationale is to reduce memory and comparison burden while preserving the information needed to detect mistaken context. No clinical error-rate improvement has been measured.

## 10. Accessibility Research

[WCAG 2.2](https://www.w3.org/TR/WCAG22/) is the target reference. The scoped checklist addresses keyboard use, visible/unobscured focus, labels, status messages, noncolor state cues, contrast, reflow and target size.

Implemented conventions include semantic main/navigation landmarks, a skip link, native buttons/inputs/selects/disclosures, explicit labels, live status regions and destination-heading focus after navigation. Source text renders as text, not HTML. Opaque IDs and long hashes wrap without requiring page-wide horizontal scrolling.

The design uses 44px primary control heights as a product target. WCAG 2.2 AA's [target-size criterion](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) is 24×24 CSS pixels or an applicable exception; 44×44 is not falsely represented as the AA minimum. Responsive checks target 320, 390, 768 and 1440px. A 320px viewport check alone is not the complete equivalent of a manual 400% zoom assessment.

Static color calculations against the final stylesheet found all **25 sampled normal-text pairs above 4.5:1** and all **9 sampled enabled-control/focus/outer-state pairs meeting 3:1**. The stylesheet SHA-256 is `2f50b7c13589525ec261875a3b35a4b0c8b1c0fe797f202b19d1fe5b501b9d86`. The active navigation border is **2.49:1 against the selected interior fill** and **3.99:1 against the outer rail**; both values are retained for contextual review. Decorative separators and disabled controls were not treated as tested enabled-input boundaries. See the [measurements and interpretation](evidence/contrast-measurements.md).

Automated browser checks, static color calculations and screenshots do not establish complete conformance. Screen-reader behavior, comprehensive keyboard operation, zoom, forced colors, contrast in every dynamic state and inclusive user comprehension remain separately assessable. The exact executed checks are recorded in §21; unexecuted checks are not passed by implication.

## 11. Privacy and UX Considerations

The existing server remains responsible for authorization. RegistrySession retains tab-memory credentials, request scope guards, no-store/omit-credentials requests, disconnect/reload clearing and denial behavior. This redesign leaves that code unchanged.

The UI distinguishes “credential present” from server-granted access. Only a successful patient read yields a selected-patient header. A 401 triggers the existing disconnect/error path. Other case/source errors clear the affected records; source denial must not falsely state that patient identity itself was revoked. A previously successful read is a snapshot; the UI does not claim continuously pushed revocation.

[HHS minimum-necessary guidance](https://www.hhs.gov/hipaa/for-professionals/privacy/guidance/minimum-necessary-requirement/index.html) informs disciplined data exposure, with its stated treatment and individual-disclosure exceptions. Hiding controls does not supply privacy enforcement or HIPAA compliance.

All engineering screenshots and browser records use independently authored fictional identities and sources. No real medical data, private correspondence, connector credentials or raw private project documents are included in this report.

## 12. Frontend Technology Evaluation

The [full technology comparison](research/frontend_technology_evaluation.md) evaluates every named candidate and its documented license scope.

| Area | Current or considered tools | Decision |
|---|---|---|
| Runtime/build | React 19.3.1, react-dom 19.3.1, TypeScript 5.9.3, Vite 7.3.7 | Retain exact existing versions and lockfile |
| Build suppliers | esbuild-wasm 0.28.2; @rollup/wasm-node 4.67.4 | Preserve reviewed overrides |
| Framework alternative | Next.js | Excluded by accepted project decision |
| Styling | CSS custom properties, CSS Modules, Tailwind | Refine authored tokens/classes; no CSS framework migration |
| Components | shadcn/ui, Radix, MUI, Ant Design, React Aria | Research candidates; native elements suffice for this slice |
| Tables/charts | TanStack Table, Recharts, ECharts | No demonstrated need in this source-inspection task |
| Forms/validation | React Hook Form, Zod | Preserve existing forms and validation; no replacement |
| Component docs | Storybook | Defer until component breadth warrants it |
| Testing | Playwright, Vitest, React Testing Library | Retain Node tests and existing Chromium/CDP harness |
| Accessibility scanner | axe-core | MPL-2.0, not a permissive-license dependency; not added |

Public license declarations are not whole-distribution clearance. MUI core and commercial MUI X editions differ. A copied shadcn component still brings dependency and source obligations. The source registers preserve upstream URLs and verification limits.

**Actual additions/removals:** no dependency is added or removed by the implementation candidate. No external font, hosted service, image package or new analytics is introduced. The system-font fallback remains; listing Inter in CSS does not download it.

## 13. Design System Proposal

The design system is a bounded refinement in [styles.css](../../apps/web/src/styles.css), not a separate package.

| Convention | Implementation |
|---|---|
| Text and surfaces | Ink `#172e35`, muted `#52665e`, paper white, canvas `#f5f6f3`, soft `#edf3ef` |
| Action and navigation | Brand `#174b48`, rail `#143631`; selected state has text/border treatment |
| Boundaries and focus | Line `#d3ddd6`, control line `#7c9185`, focus `#97621e`; visible focus outline |
| Error | Danger `#773b2c`, danger surface `#f8ede7`; message and border accompany color |
| Rhythm | 16px base text, 1.55 line height, restrained 8px spacing basis and 10px panel radius |
| Typography | System UI stack; local Georgia heading treatment in patient view, sans-serif clinical headings |
| Responsive layout | Content-led breakpoints at 1200 and 760px; wrapping metadata/actions; stacked narrow source layout |
| Motion | No required animation; reduced-motion rule suppresses motion if present |
| Forms | Persistent labels, existing limits/validation, 44px primary controls, text errors |
| Status | Visible words for source/registry/current/superseded/error state; no color-only clinical meaning |

Reusable presentation units are `RecordsPanel` and `SourceRow`, plus shared heading, panel, badge, status, action, metadata, disclosure and empty-state classes. Both reading layouts reuse the same components and data. The session panel is rendered consistently where reconnection is needed. No modal or custom ARIA grid is added.

Component rules: preserve original values and status vocabulary; render literal content through React text nodes; give each section a heading; use a definition list for key/value metadata; keep current source statements near their version; use native `details/summary` for optional provenance; preserve a direct clear/retry/return action. A source hash is never styled as a clinical validation badge.

These token values describe the verified implementation. The sampled contrast measurements in §10 apply to the final recorded stylesheet hash; any later color change requires remeasurement of the affected pair. The final long-identifier wrapping correction changes layout without introducing a new color or dependency.

## 14. Existing Application Audit

The baseline was archived from exact PR #200 before product changes. The application ran against actual FastAPI and a disposable PostgreSQL 16 database with independently fictional records. The baseline audit contains seven accepted screenshots, all opened and inspected by the capturing agent.

| Audit step | Screenshot evidence | Observed health |
|---|---|---|
| 1. Entry/session | `01-entry-desktop.png` | Fields are labelled; working and unconnected destinations compete at the same level |
| 2. Authorized identity | `02-patient-open-desktop.png` | Registry metadata is accurate; selected identity follows repeated setup panels |
| 3. Records loaded | `03-records-desktop.png` | Correct scope/state; first source begins near the bottom of a 1100px viewport |
| 4. Amendment | `04-amendment-desktop.png` | Superseded history retained; introductory material dominates the first viewport |
| 5. Source detail/history | `05-source-history-desktop.png` | Exact provenance remains; selected-patient identity is out of view while reading sources |
| 6. Records mobile | `06-records-mobile.png` | 390px reflow has no page overflow; useful record content is below extensive introduction |
| 7. Overview mobile | `h1-mobile.png` | Readable labels; introductory content precedes selected context |

The screenshot filenames above are indexed in the [durable screenshot location](screenshots/README.md); the accepted baseline audit and logs are indexed in [verification evidence](evidence/README.md). This is a heuristic audit of an executed synthetic workflow, not patient or clinician feedback. It found hierarchy/context opportunities, not measured clinical errors. No metadata overlap was measured and none is claimed.

Documentation reconciliation preceded changes. At the initial audit, historical project documents described identity-only React #181 and proposed Next.js screens, while the selected source baseline #200 already connects Records and the accepted stack excludes Next.js. This report uses the actual code for inventory and preserves older documents as dated history. It does not publish their private contents.

**Concurrent feature branches:** a final documentation check identified [draft PR #205, Records to obtain](https://github.com/OpenxIntelligence/open-intelligence/pull/205) at `37e1b4d00aa9b9dd0bdbf2b0a121b2c87d72cad5` and [draft PR #209, inspect-before-import and original viewer](https://github.com/OpenxIntelligence/open-intelligence/pull/209) at `aa44084866451ac106de9dc117c7e20224b77032`. Public PR metadata confirmed both open, draft and unmerged on the same #200 parent. Their request-read and original-source features are separate from the inspected #200 workspace snapshot. This report does not attribute their functionality or test totals to this redesign. Combining the branches requires deliberate source-owner reconciliation and a fresh integrated browser run; the existing request, import and original-viewer work must be preserved.

## 15. Complete Feature Inventory

### Active H1 features and actions

All current H1 users are synthetic operators using existing credential/grant contracts. “Patient” and “clinical” below are reading layouts, not account roles. `main.tsx` owns navigation/forms; `RegistrySession` owns existing requests and transient data; `source-contracts.ts` validates active case/source responses; `RecordsPanel` owns presentation only.

| Feature / current location | Existing behavior and dependency | Redesign location/presentation | Regression risk and verification |
|---|---|---|---|
| API readiness / top bar | GET `/health/ready`; checking/ready/unavailable; bounded request | Same state, concise indicator | Do not confuse API readiness with patient permission |
| Credential connection / Overview | Local syntax check; token held in memory; server grants checked per action | Session panel; same form also accessible after disconnect on another destination | Token must not enter storage, URL or logs |
| Disconnect and page hide | Clears session, patient, case/source data; cancels in-flight work | Same action; returns to Overview | Old responses must not repopulate cleared state |
| Exact patient open / Overview | GET `/v1/patients/{id}`; previous context clears before read | Plain patient-ID form; no invented name search | Invalid/wrong-scope/denied/delayed responses cannot restore old context |
| Patient identity / Overview | Supplied ID, organization, status, revision, created time | Patient card plus persistent selected-patient header | Display actual loaded response, not unsent ID input |
| Access recheck | Reuses exact patient read | Header and Overview actions | Request clearing and grant checks remain unchanged |
| Fictional identity creation | POST `/v1/patients`; existing confirmation and stable request key | Native disclosure on Overview | No implicit read grant, double creation or false save |
| Same-key retry / create receipt | 200/201 response distinguishes original/duplicate; unknown outcome permits same-key retry | Existing receipt and clear retry guidance | Preserve uncertain outcome and idempotency meaning |
| Start another creation | New key only after existing successful receipt | Same explicit action | Must not silently replace retry key after uncertainty |
| Five existing destinations | Overview, Records, Journey, Investigations, Review; local React state | Working Home/Workspace and Records emphasized; other three retained in “Not connected” group | Every existing destination remains reachable |
| Reading layout | New local patient/clinical presentation preference | Named select; explicit no-access-change explanation | No requests, grants, source changes or input loss |
| Patient-chart navigation | New presentation of existing Overview/Records destinations | Separate labelled chart nav after authorized read | Scope remains the same across destinations |
| Case mappings / Records | GET `/v1/patients/{id}/case-bindings`; active/revoked mappings | Linked cases in patient view; case mappings in clinical view | Empty/error/revoked are distinct; revoked row cannot load sources |
| Source metadata / Records | GET `/v1/patients/{id}/cases/{caseId}/sources` after active mapping | Dedicated source history, case/date/version context | Wrong patient/case and malformed response stay rejected |
| Source version history | All returned current/superseded versions, IDs, SHA, specimen and dates | Version rows with optional provenance details | Keep history and exact field meanings; no original-byte claim |
| Current source statements | Literal statement, finding key, reported state, source line and unestablished review | Statement adjacent to its exact source version | Escape HTML-like content; never attach current quotes to old version |
| Local source filter | New filter of loaded metadata only; document/type/dates/source/specimen fields and version state | Labelled search/select, count and Clear filters | No API or patient-state mutation; no match does not mean no data |
| Case/source refresh | Existing explicit load methods clear previous result and check permission again | “Check authorized cases” and “Inspect source versions” | Preserve source/identity clearing boundaries |
| Error recovery | Existing client messages and action methods | Global/records status with reconnect, reload cases or return actions as applicable | Do not infer narrower causes than the client supplies |
| Keyboard/focus/reflow | Existing semantic foundation, improved presentation | Skip link, destination heading focus, disclosures, wrapping controls | Preserve input state and avoid obscured focus |
| Unconnected-workspace pages | Existing three placeholders | Explicit not-connected state and return action | No fabricated clinical data, tasks or action completion |

The H1 source response intentionally limits case mappings to 256, source versions to 256 and current assertions to 512, with a bounded JSON reader. These are existing client contracts, not a reason to add pagination or reinterpret truncation. No new backend search, ordering contract or clinical filtering is introduced.

### Actual client and UI states

| State family | Supported states | Presentation rule |
|---|---|---|
| API | checking, ready, unavailable | Readiness is service availability only |
| Session | disconnected, idle, reading, creating, ready, error | Busy actions reflect real operations; no fabricated progress |
| Connection validation | malformed credential, valid-format credential held | “Connected” is not proof of an action grant |
| Patient validation/read | invalid opaque ID; permitted read; denied/unavailable; unverified response | Previous patient/source state clears before new selection |
| Identity creation | pending; created; original receipt recovered; conflict/refused; unknown outcome | Unknown response retains same-key retry guidance |
| Records loading | idle, loading-cases, loading-sources, ready, error | Distinguish loading from successful emptiness |
| Case results | no mappings; active; revoked | No mapping does not mean no clinical history |
| Source results | no sources; populated; current; superseded | Current version is not medical approval |
| Statement availability | current supplied quotations; no current quotations returned; historical quotations not supplied | Say only what this response contains |
| Local filtering | all; narrowed; no match; cleared | Loaded records are unchanged |
| Workflow availability | connected Overview/Records; unconnected Journey/Investigations/Review | Planned domains do not masquerade as populated features |
| Presentation | patient; clinical | Layout and wording only, same data and access |

**Error granularity:** the existing client combines some causes. Case failure may say “unavailable or permission changed”; source failure may combine unavailable/denied/revoked; catch paths combine invalid response and service failure. The UI must preserve those honest combined descriptions. It cannot reliably distinguish a network outage, malformed response, missing source or revoked mapping in every path.

### Retained reference application: all 16 section IDs

Source-based inventory from [web/index.html](../../web/index.html). This page declares a clinician audience and explicitly states that it has no patient login/identity verification. The table records rendered sections and their existing scripts/forms; it does not claim migration or newly execute every legacy workflow.

| Section ID | Current feature/presentation | Audience / dependency | Status in this redesign |
|---|---|---|---|
| `overview` | Case heading and overview | Shared synthetic case projection; `app.js` | Retained unchanged |
| `assertions` | Source-reported findings | Shared source/assertion projection | Retained unchanged |
| `review-attention` | Investigation freshness/attention within overview | Clinician demonstration; question/draft freshness | Retained unchanged; not a peer global route |
| `incoming-board` | Incoming synthetic worklist | Clinician demonstration; existing case data | Retained unchanged |
| `patient-view` | Plainer rendering of the same sourced facts | Patient-oriented projection inside clinician page | Retained; not a patient account |
| `patient-mission` | Read-only synthetic workflow projection | Shared case/mission projection | Retained unchanged |
| `timeline` | Events and Source Change Explorer | Source versions/change state | Retained unchanged |
| `investigations` | Question creation, source-linked drafts, saved history and bounded model-investigation form | Existing question/draft/model handlers | Retained; unconnected in H1 |
| `sources` | Source history and source-viewer entry | Canonical source ledger | Retained unchanged |
| `biological-assets` | Biological-asset provenance | Synthetic asset references; no stored assay files or shipment | Retained unchanged |
| `activity` | Recent activity | Existing event projection | Retained unchanged |
| `evidence` | Fictional evidence import, assessments and withdrawal controls | Existing evidence/research handlers | Retained; not migrated |
| `options` | Options, dependencies, tasks, threats and review forms | Existing option/coordination handlers | Retained; no treatment recommendation |
| `bibliography` | DOI bibliography discovery form | Existing bibliographic service; not case-linked | Retained unchanged |
| `import` | Synthetic source-import form | Existing source ingestion | Retained; not a new H1 upload |
| `changes-since-review` | Review-oriented source-change presentation | Existing change/review projection | Retained unchanged |

Two native dialogs, original-source and version comparison, remain outside that section count. The reference page has 14 navigation anchors; section count and top-level navigation count are different. No feature is removed because it does not fit the H1 design.

## 16. Current UX Problems

The baseline findings motivate concrete changes:

| Finding | Evidence | Candidate response | Outcome still requiring evaluation |
|---|---|---|---|
| Technical setup/caveats push active source work down | Baseline Records desktop/mobile | Move selected identity up; concise scope note; metadata disclosure | Whether patients comprehend the shorter presentation |
| Identity is absent while reading lower source history | Baseline source-history screenshot | Persistent patient context | Final sticky-header/focus checks passed at 320/390/768/1440px |
| Working and unconnected areas have equal emphasis | Baseline entry/navigation | Separate working destinations from the “Not connected” disclosure | Discoverability of retained planned areas |
| Hash/technical metadata precedes useful statement | Baseline source-history screenshot | Statement adjacent to version, provenance available on demand | Clinician ability to verify source without extra burden |
| A single reading layout serves different tasks | Source inspection and existing blueprint mismatch | Shared patient/clinical layouts | Actual task performance for each audience |
| Source lists lack local narrowing | Baseline source version list | Reversible loaded-source filters | Behavior on larger realistic synthetic collections |

These are observed layout issues and design hypotheses. The report does not invent user quotations, frustration ratings or time savings. It does not treat every technical field as clutter; source identity, dates, reported state and review limitations remain inspectable and meaningful.

## 17. Proposed Information Architecture

The selected structure keeps a single shared source authority:

| Level | Patient reading view | Clinical reading view | Data/behavior |
|---|---|---|---|
| Workspace | Home; My records | Workspace; Source records | Existing Overview/Records destinations |
| Reading preference | Patient view / Clinical view | Same selector | Local layout only |
| Patient chart | Overview; Records | Overview; Records | Appears only after authorized patient read |
| Context | Selected opaque patient; organization; registry state | Same identity with clinical emphasis | Actual loaded response |
| Records | Linked cases → source history → statement/source details | Case mappings beside source history when wide | Same existing read contracts |
| Additional destinations | Journey; Investigations; Review | Same | Reachable and explicitly not connected |
| Session/creation | Existing credential/open/create actions | Same actions | No new account or clinical process |

This structure adapts to later connected domains without pretending they exist now. New appointments, messages, medication management, physician schedules and patient population search require separately owned backend/domain work and are not added.

## 18. Patient Chart Design

A selected-patient header remains independent of the editable patient-ID form. It carries the returned ID, origin organization and registry status, plus the existing recheck action. Chart navigation separates the patient's Overview and Records from the wider workspace.

The Records view uses explicit stages: no patient selected; cases not loaded; loading; returned mappings; case chosen; source history; optional provenance. Current and earlier versions retain separate rows. Each source keeps document ID, version, type, event date, issue date, receipt date, specimen when supplied, source ID, SHA and supersession relationship.

Literal current quotations sit with their version and source line. The clinical view emphasizes source context; the patient view changes labels and metadata density. Neither rewrites a reported statement or interprets its medical meaning.

The local filter applies only to the fetched response. It exposes result counts, a no-match message and Clear filters. A new source response resets filters; switching reading layout does not modify data. Original document bytes, historical quotations, clinical reconciliation and research-review invalidation are not supplied by this active H1 response and remain explicitly unavailable.

## 19. Design Alternatives and Decision Log

Three approaches were compared in the [design decision](2026-11-02-h1-workspace-design.md):

| Alternative | Benefit | Tradeoff | Decision |
|---|---|---|---|
| One dense universal dashboard/object explorer | Many objects directly visible; useful for technical inspection | Higher entry burden, competing context and difficult narrow layouts | Rejected as default; preserve detailed inspection inside records |
| Separate patient and clinician applications | Independent audience layouts | Duplicated state/client, invented role assumptions and larger regression surface | Rejected for current scope |
| Shared canonical session, two reading layouts, patient chart | Audience-specific priorities with one set of source/authority contracts | Must clearly prevent a view choice implying professional permissions | Selected |

Selection criteria were learnability, source-verification efficiency, accessibility, patient context, scalability, implementation complexity and feature preservation. The chosen option best fits the existing narrow H1 API without multiplying state or adding a migration. This is an engineering/design judgment, not a measured usability ranking.

| Decision | Rationale / evidence | Implementation status |
|---|---|---|
| D-UX-01 Keep React/Vite/TypeScript | Accepted architecture; current code and dependency gate | Preserved |
| D-UX-02 No added dependency | Native controls solve this scope; existing tooling works | Preserved in candidate |
| D-UX-03 Separate workspace/chart context | SAFER identity guidance; baseline lost-context observation | Implemented |
| D-UX-04 Two reading layouts, no role switch | Different audience tasks; no verified roles in backend | Implemented |
| D-UX-05 Make working areas primary | NHS task-navigation research; baseline equal emphasis | Implemented |
| D-UX-06 Keep statements/source version adjacent | Provenance semantics; baseline metadata hierarchy | Implemented |
| D-UX-07 Preserve historical quotation limit | Active parser accepts current-source assertions only | Explicit copy implemented |
| D-UX-08 Preserve combined error causes | Actual RegistrySession contract; builder review | Required and documented |
| D-UX-09 Filter loaded metadata only | Useful presentation improvement without backend search | Implemented |
| D-UX-10 Retain all reference features | Current user boundary and source-owner architecture | Reference files identical to parent; 245 reference tests passed |
| D-UX-11 Publish one cohesive report | Existing documentation already has owners and historical layers | Report assembled; external writes pending |

## 20. Frontend Implementation Roadmap

### Completed for this cycle

Research covered the named market, technology options and official healthcare/accessibility guidance. Existing Notion/Drive organization was inspected before proposing publication. The exact H1 baseline was run and captured; current source behavior and the retained reference app were inventoried. Alternatives were documented and a frontend-only design selected.

The implementation reorganizes `main.tsx`, refines `styles.css`, extracts `records-panel.tsx`, and extends the existing browser journey with `workspace_ux_checks.py`. Final local client, build, rights and actual browser verification passed after the independent review fixes and long-identifier wrapping correction. The retained reference suite also passed. Evidence and reviewed screenshots are indexed in §21.

### Remaining gates in this cycle

1. Finish attaching the durable documentation and screenshot package to published draft PR #218, recording publication revisions and hosted CI separately from the completed local checks.
2. Publish the reviewed report in the existing UX documentation area and append concise verification links to existing project records.
3. Preserve the exact source/test hashes in the boundary report through any documentation-only publication update.

### Later product work, outside this frontend-only change

Reconcile the existing request and source-intake branches into this workspace through their current owners; connect investigations and review through their domain owners; establish real account/consent/professional authority separately; research complete patient/clinician journeys with participants; evaluate source-scale performance; introduce complex components only for demonstrated requirements. This preserves the wider first-party oncology platform ambition without presenting absent functions as completed or commissioning duplicate intake work.

## 21. QA and Regression Testing

### Executed baseline

The exact #200 source archive ran before product changes:

| Check | Result | Limit |
|---|---|---|
| Locked install | Passed; 18 packages | Optional packages and lifecycle scripts omitted |
| Existing dependency-rights gate | Passed; zero errors | Two optional packages uninspected; not legal/distribution clearance |
| Existing frontend client suite | **24 passed, 0 failed** | Contract/session tests; no clinical evaluation |
| TypeScript/Vite build | Passed | Build success is not browser or usability proof |
| Actual Chromium journey | Passed against FastAPI and disposable PostgreSQL 16 | No mocked patient HTTP or database |
| Supplemental baseline capture | Passed on a separate disposable database | Same synthetic workflow; no production data |
| Existing responsive assertion | Passed at 390px | Not full device/zoom/WCAG coverage |

Baseline built payloads: CSS **6.11 kB** (**2.00 kB gzip**); JavaScript **248.39 kB** (**76.77 kB gzip**); index **0.42 kB** (**0.30 kB gzip**). These are build sizes, not measured latency, interaction speed or Core Web Vitals.

The baseline browser exercised connect, fictional creation, same-key retry, denial before an independent grant, successful identity read, independently authored source import through the existing API, source inspection, literal HTML-like content, amendment/history, source-grant withdrawal, patient-grant withdrawal, expiry, cross-organization denial and reload clearing.

### Initial implementation verification

The initial implementation passed **24 client tests**, a TypeScript/Vite build and an expanded actual Chromium→FastAPI→PostgreSQL journey. That checkpoint preceded the later review fixes; final results are recorded separately below.

The expanded harness checks reading-layout changes with no API request/data mutation, persistent patient context, retained unsubmitted patient-ID input, explicit unconnected destinations, heading focus, literal source association, provenance disclosure, filter/no-match/clear behavior, historical source handling, responsive containment at 320/390/768/1440px, skip-link operation and client-clearing behavior. The final executed run additionally covers two-case source/filter isolation, stress-length identifiers and quotation text, sticky-focus geometry, and expiry after records were visibly loaded.

### Retained-reference regression and independent review

The retained Python/SQLite reference suite was actually executed during this redesign cycle: **245 tests passed**, with the log reporting **131.713 seconds**. This checks existing reference code, not 245 new tests or 245 patient participants. It is separate from the 24 H1 client tests and the actual H1 browser/API journey; counts are not combined into a misleading single coverage number. The captured reference-log SHA-256 is `94652238ebc95a2445a3431d6213d47d5a747117e02c1b937a5726599dd239b0`. See the [reference result summary](evidence/reference-suite-summary.md).

Independent source/interaction review and targeted browser checks identified concrete issues that were corrected before final verification:

| Finding | Consequence | Final local resolution |
|---|---|---|
| Overview retains the identity-read status after source records are loaded | The message can falsely imply no clinical/source record is loaded | Presentation condition corrected; final regression passed |
| Clear filters removes its own currently focused button | Keyboard focus may fall to the document rather than remain at the filter | Explicit filter-input focus restoration implemented; final keyboard regression passed |
| Existing expiry test did not require sources to be visible before expiry | A passing test could miss source-content clearing on the Records surface | Previously visible source precondition and expiry on Records added; final clearing check passed |
| Long case heading overflows at 320px | A valid opaque identifier can force horizontal page overflow | Heading children receive width limits and wrapping; final 320px stress check passed |

The first two presentation bugs were reproduced together in an actual browser assertion: “Clearing filters must return keyboard focus to the source filter; Overview must not claim no records are loaded while retaining source records.” Narrow UI corrections restore focus to the source-filter input and suppress the stale identity-only message when a source response remains loaded. The expiry scenario now requires previously visible source content before exercising credential expiry. The [failing review check](evidence/review-red-browser.txt) and [final passing run](evidence/browser-final.txt) preserve the reproduction and resolution.

A separate [long-source failing check](evidence/long-source-red-browser.txt) found the case eyebrow extending to 354.95px in a 320px viewport. The correction applies `min-width`, `max-width` and `overflow-wrap` to the section-heading children. The final run passed with two cases, 40-character case/document identifiers, a 128-character organization identifier and a 1,200-character quotation. No truncation or semantic shortening of source content was introduced.

An earlier targeted rerun timed out before real proxied API readiness; that earlier environment-startup failure did not itself reach or reproduce the defects. Preserve the distinction between that attempt, the later meaningful failing assertion and the final corrected run. These are engineering review findings, not claimed clinical incidents.

A separate screenshot/contrast review inspected all eight final images and found the selected identity visible in desktop and mobile source-reading captures, with no additional serious visual issue identified in those images. The 390px capture observer was aligned below the sticky header. The 320px stress capture is a scrolled state, so it demonstrates wrapping and persistent context rather than the entire source in one viewport. The initial mobile page remains relatively tall, so improved task speed is not claimed. See the [screenshot index](screenshots/README.md) and [review qualifications](evidence/contrast-measurements.md).

### Final local verification record

| Gate | Current status |
|---|---|
| Validated local product-source checkpoint | Commit `0b741bf8ef7987ab4396474e3fbf0fa4b0f7e053`, tree `0ab810415d82f04bc8b37d5bea01ac214a63188d`; reconciled parent `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`; later documentation-only publication has a separately recorded remote head |
| Published implementation checkpoint | [Commit `4718c9003193bd936ecede16ae180adfbd41e9a9`](https://github.com/OpenxIntelligence/open-intelligence/commit/4718c9003193bd936ecede16ae180adfbd41e9a9) has the same validated tree `0ab810415d82f04bc8b37d5bea01ac214a63188d`; subsequent documentation-only commits and hosted runs are separate receipts |
| Final client run | **24 passed, 0 failed, 0 skipped**; [client log](evidence/client-final.txt) |
| Final TypeScript/Vite build | Passed; CSS **15.23 kB / 3.94 kB gzip**, JavaScript **258.12 kB / 78.93 kB gzip**, index **0.42 kB / 0.30 kB gzip**; [build log](evidence/build-final.txt) |
| Final unchanged rights gate | **18 installed, 2 optional uninspected, errors `[]`**; [rights log](evidence/rights-final.txt) |
| Final actual browser journey | Passed against actual FastAPI/PostgreSQL 16; identity/create/retry, current and amended source history, literal quotations, revocation, cross-organization isolation, two-case source/filter isolation, long-content reflow, expiry clearing previously visible records and reload; [browser log](evidence/browser-final.txt) |
| Independent review / resolved findings | Stale Overview status, Clear filters focus and 320px long-heading overflow reproduced and corrected; stronger expiry precondition passed |
| Final runtime-console result | No `Runtime.exceptionThrown` or `console.error` event observed during the executed journey |
| Final contrast/keyboard/reflow findings | 25 text + 9 enabled control/focus/outer-state contrast samples measured; tested keyboard recovery, landmarks and sticky-focus geometry passed at 320/390/768/1440px; full zoom/screen-reader/forced-colors evaluation not executed |
| Final screenshot review | Eight final fictional-data images inspected; [before/after evidence](screenshots/README.md) |
| Changed-path and restricted-file comparison | **PASS: 198 protected files identical, no protected differences or unapproved changed paths**; [boundary report](evidence/boundary-report.json) |
| Draft PR and hosted CI | [PR #218](https://github.com/OpenxIntelligence/open-intelligence/pull/218) is published, draft and unmerged; hosted CI passed on implementation head `4718c9003193bd936ecede16ae180adfbd41e9a9` in [run 41564125200](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41564125200), job 125681401811. Decoded job logs confirm the exact checkout, 24 passing client tests and actual PostgreSQL browser PASS. Artifact 13197808926 metadata was inspected; its archive was not downloaded. See [receipt](evidence/hosted-implementation.json) and [PR checks](https://github.com/OpenxIntelligence/open-intelligence/pull/218/checks) for later documentation-head verification |

### Technical integrity

The changed product/test files are `apps/web/src/main.tsx`, `apps/web/src/styles.css`, `apps/web/src/records-panel.tsx`, `apps/web/tools/browser_journey.py` and `apps/web/tools/workspace_ux_checks.py`. Remaining changes are documentation and evidence. No runtime or development dependency changed.

The [final local boundary comparison](evidence/boundary-report.json) confirms that `apps/api/**`, `src/**`, migrations, `registry-client.ts`, `source-contracts.ts`, dependency manifests/lockfiles, CI workflows and retained `web/**` match the reconciled parent `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`. All 198 protected files are byte- and mode-identical, with no unapproved changed paths. The upstream-deleted `source-model.ts` remains absent. The report records SHA-256 values for the five changed product/test files; any later publication must preserve those values or regenerate the comparison. This is a source-boundary result, not clinical validation or proof of every possible runtime behavior.

No patient or physician study, full screen-reader review, complete WCAG audit, clinical validation, production-load benchmark, merge or deployment is claimed.

## 22. Final Product UX Evaluation

**Current assessment:** the verified implementation addresses the observed presentation opportunities while staying within the actual H1 feature set. It supplies different patient/clinical reading priorities, a persistent identity context, a dedicated source chart, source-adjacent statements, inspectable history and reversible filtering. It also keeps unsupported workflows honest and preserves the current contracts. Final local engineering checks passed; they do not establish measured user benefit.

**Publication status:** the final local implementation, review fixes, screenshots and boundary evidence are complete. Draft PR #218 is published and unmerged, with its implementation tree matched to the validated local tree. Hosted CI passed on the published implementation checkpoint; [PR checks](https://github.com/OpenxIntelligence/open-intelligence/pull/218/checks) record any later documentation-head verification separately. Existing-workspace report publication is in progress. The broader mandate's two fully operational patient/clinician products cannot be completed through frontend changes alone while real account authority, clinical actions and several workflows are absent. This report distinguishes the functioning reading experiences from those product gaps.

Future user evaluation should ask participants to identify the selected patient, find the current report, distinguish an earlier version, explain whether a quotation is clinically reviewed, inspect its source line/provenance, recover from no filter matches, and recover after access failure. Measure correct completion, consequential errors, backtracking, comprehension and actual time. Use appropriately authorized fictional study material; do not invent results or recruit/contact people without authorization.

The remaining accessibility work should include a complete keyboard path, screen-reader reading order and announcements, zoom/forced-colors behavior, contrast across interactive states and inclusive comprehension. Performance work should measure realistic source counts and actual interaction latency, not infer improvement from smaller files or cleaner screenshots.

The final result should be judged by whether a user can reliably find and verify the right information while maintaining context. Research and design choices support that goal; only executed engineering evidence and subsequent participant evaluation establish how far it has been achieved.

