# Open Intelligence — Healthcare Competitor Research and Frontend Design Implications

**Research date:** 2 November 2026, America/New_York  
**Scope:** Public evidence across 15 product families, covering the 13 requested general platforms plus two oncology platforms.  
**Status:** Research complete for this implementation cycle. Proposed requirements await reconciliation with the current repository and executed UI tests.  
**Evidence register:** [competitor-sources.json](competitor-sources.json), 50 entries including one excluded source.

## Decision value

The evidence supports a patient experience organized around understandable tasks and a clinician experience organized around work lists plus a patient-specific chart. A chart should keep identity, source, date and review state visible while allowing the user to open deeper records. The best opportunity for Open Intelligence is to make existing information and actions easier to find, verify and complete.

This is an analyst recommendation, not a measured claim that Open Intelligence already outperforms competitors. Public material supports useful patterns; it does not establish comparative task performance, clinical safety, screen-reader quality or production reliability.

Five recommendations should guide the frontend implementation:

1. **Separate global and patient context.** A clinician must know whether they are viewing a work list or one person's records. Patient identity should remain visible while moving between chart sections.
2. **Make the patient home a starting point for real tasks.** Prefer clear labels and meaningful groups. Surface existing next actions without inventing appointments, messages, unread counts or care recommendations.
3. **Preserve source meaning.** Imported, patient-reported, historical, unreviewed and unavailable information must retain the distinctions present in the existing data.
4. **Reduce repeated navigation without concealing functions.** Use a concise overview with direct links into complete records. Prefer predictable structure over a collection of disconnected dashboard cards.
5. **Keep the current stack unless an actual implementation problem warrants a change.** Competitor research does not justify a React, Next.js or component-library migration.

## 1. Research method and limits

Research used official product specifications, help articles, public developer documentation, source repositories, original peer-reviewed research, and review/community material. Technology claims rely on primary sources. The source register records URL, date where available, evidence type, retrieval method, confidence, verification scope, action and implementation status.

The evidence types have different meanings:

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| Official help or product specification | A documented workflow or supported capability | That every customer has enabled it; measured usability |
| Official developer documentation or source manifest | The named API, runtime or library in the documented scope | The full company's stack or every deployed product version |
| Vendor product page or announcement | What the vendor currently claims or markets | Independent improvement in efficiency, safety or outcomes |
| Original research | Findings in the stated population, version and setting | A current universal ranking of all products |
| User review or community comment | A reported experience and a hypothesis worth investigating | Incidence, causation, representative sentiment or reproducibility |

No authenticated competitor instance was accessed. Public help text and interface descriptions were reviewed; no hands-on competitor task audit, timed benchmark, device test or accessibility conformance assessment was conducted. Public screenshots and help examples are references, not evidence that a flow was executed.

Some Practice Fusion help pages returned a CSS error. Capterra and Software Advice pages sometimes returned unsupported content types when opened; relevant indexed excerpts are labeled accordingly in the register. Publication dates are null where the source did not state a reliable date. Search crawl dates are not publication dates.

## 2. Healthcare competitor landscape

The table records documented strengths worth studying and explicit limits on the evidence. “Not established” means this research did not verify the claim; it is not a negative product verdict.

| Product family | Relevant public evidence | Useful pattern for Open Intelligence | Weakness, uncertainty or transfer limit |
|---|---|---|---|
| Epic / MyChart | Broad patient tasks, shared records and family access [C01]; web-based clinician client [C02] | Distinct patient and professional surfaces; clear entry points into records | Deployment and available functions vary. Breadth alone does not establish easy navigation |
| Oracle Health / Cerner | External chart entries and reconciliation tasks [C04]; new portal announcement [C05] | Preserve provenance and clearly distinguish work requiring attention | Legacy Millennium and newer EHR/portal generations should not be treated as one fixed UI |
| MEDITECH Expanse | Chart widgets, external summaries, mobile work and patient self-service [C07, C09] | Adapt information density to the task and device | Vendor efficiency claims were not independently tested here |
| athenahealth / athenaOne | Detailed patient-banner, chart, search, visit-stage and mobile specification [C10] | Global work list → recognizable patient context → task-specific chart area | Specification demonstrates breadth, not the number of clicks in a local implementation |
| eClinicalWorks / healow | PRISMA record search, timeline and explicit external-record saving [C12] | Search and chronology should connect users to source records | Navigation and loading complaints appear in reviews; prevalence and version effects are unknown |
| NextGen Healthcare | Office portal help with task tiles, proxy selection and conditional features [C14] | Explain whose record is open and what the current account can do | Office and Enterprise are distinct products; portal capabilities depend on service configuration |
| Elation Health | Three-panel clinical console and patient communication [C16] | Keep useful context beside active work when space allows | Primary-care marketing does not establish oncology fit or mobile effectiveness |
| DrChrono / OnPatient | Invitation states, messaging, scheduling, forms and visit records [C18] | Show truthful progress and access states at existing workflow entry points | Native mobile availability does not establish feature parity or frontend framework |
| Tebra | Facesheet and record categories [C21]; patient portal with guest access [C22] | Concise chart overview, clear record sections, visible patient/account distinction | Available payments and portal sections depend on practice configuration |
| Practice Fusion | Charting and record sharing [C24]; documented summary beside encounter [C25] | Summary-to-detail organization that preserves active work | Encounter help could only be inspected through indexed content; no live flow claim |
| AdvancedMD | Configurable patient summaries [C27] and task/schedule dashboard [C28] | Make a dashboard lead into actual work | Customization and dashboard graphics can add complexity; that is a design risk to test, not a measured defect |
| Canvas Medical | Public chart/panel customization guides and patient-app code [C30, C32] | Modular chart presentation; a coherent patient surface can differ from clinician work | Reference app code is not evidence of the proprietary EHR's entire stack |
| NHS App | Published structure and navigation research [C33, C34] | Goal-oriented patient hubs, clear headings, deliberate progressive disclosure | UK service structure is not an oncology product template |
| Flatiron OncoEMR / CareSpace | Oncology chart, molecular profiling workflow, physician mobile access and portal [C37] | Keep relevant oncology source material near the chart task | Clinical decision support and treatment workflows are outside this redesign |
| Siemens / Varian ARIA | Oncology information and images across distinct professional roles [C38] | Preserve clinical context across record categories and roles | Radiation treatment planning is a specialized regulated workflow, not a frontend feature to copy |

## 3. Benchmark by requested UX dimension

This is a qualitative evidence matrix, not an unmeasured scorecard. Each row identifies a useful comparator and the validation Open Intelligence needs.

| Dimension | Evidence-backed comparator | What Open Intelligence should take from it | What remains unverified |
|---|---|---|---|
| Patient usability | NHS task-led hubs; MyChart patient study [C33, C40] | Name actions in patient language; make available records and next steps discoverable | Actual patient comprehension and time to completion |
| Clinician usability | athenaOne workflow specification; Elation console [C10, C16] | Keep patient context close to active chart work | Clinician task efficiency with OI's data |
| Navigation | NHS navigation guidance [C34] | Match destination titles to labels; avoid indiscriminate repeated links | Whether proposed OI groupings match users' mental models |
| Patient chart organization | Tebra facesheet; AdvancedMD summaries [C21, C27] | Show a concise overview with complete record access | Whether priority and density suit oncology workflows |
| Clinical workflow efficiency | Multi-site EHR task study [C39] | Test the implemented workflow, not only component appearance | Comparative efficiency versus competitor deployments |
| Dashboard design | AdvancedMD schedule and task emphasis [C28] | Every visible summary should lead to an existing action or record | Whether task charts help more than simple lists |
| Visual consistency | NHS published frontend components [C35] | Shared typography, spacing, focus and status conventions | Consistency across the full OI feature inventory |
| Accessibility | NHS accessibility statement and design research [C33, C36] | Define test scope; combine automated and manual evaluation | Competitor conformance and OI WCAG conformance |
| Mobile experience | DrChrono and MEDITECH mobile surfaces [C09, C19] | Preserve priority actions when layouts become narrow | Device-specific completion, keyboard and screen-reader behavior |
| Information density | Elation context beside work [C16] | Adapt density to role, task and screen width | Whether three panels improve OI task outcomes |
| Search | PRISMA search and timeline [C12] | Retain source and time context in existing search results | Recall, ranking quality and backend completeness |
| Documentation | athenaOne visit-stage specification; Practice Fusion encounter help [C10, C25] | Keep notes and the supporting record reachable together | Save, validation and conflict behavior in the actual OI implementation |
| Interoperability | Official FHIR documentation [C03, C06, C08, C11, C13, C15, C17, C20, C23, C26, C29, C31] | Make imported data understandable while preserving existing contracts | That any particular resource is complete, current or enabled |
| Performance | Actual task variability and navigation research [C39, C46] | Measure transition time, errors and recovery in representative journeys | Production latency or comparative product performance |
| Overall interaction complexity | Independent task studies plus review hypotheses [C39, C41–C44] | Reduce unnecessary context switches while retaining essential checks | Whether reduced clicking improves accuracy or comprehension |

## 4. Seven patterns worth carrying into implementation

### 4.1 NHS App: task intent should determine the starting point

NHS documents research behind its Home, Messages and Profile structure. It also notes that services depend on provider enablement. These are useful principles for Open Intelligence: organize what exists around users' goals, and distinguish unavailable services from empty data. The specific three-hub arrangement is not a mandatory template. [C33]

**Design inference:** a patient landing page should help someone resume an existing task or find a known record. It should not require browsing internal module names to discover the right place.

### 4.2 MyChart: record availability and onboarding are part of usability

The 2025 MyChart study involved 5,651 questionnaire respondents and 18 interviews at one Canadian hospital. Participants valued preparation for appointments; awareness, registration and access to desired information remained barriers. This is implementation-specific research, not a universal MyChart assessment. [C40]

**Design inference:** test whether an ordinary user can distinguish “no record exists,” “not available here,” “not yet loaded” and “request failed.” A polished empty panel does not resolve an access or completeness problem.

### 4.3 athenaOne: distinguish the day's work from one person's chart

The service specification organizes capabilities across visit stages and describes a patient banner, chart sections, patient search, documents and separate mobile experiences. [C10]

**Design inference:** global navigation should select a work area; chart navigation should select information within one patient. Opening records should not make the patient context ambiguous or leave the user uncertain how to return to the list.

### 4.4 Elation: contextual adjacency is useful, but density is conditional

Elation publicly positions its three-panel console as a way to retain clinical context. [C16]

**Design inference:** an overview beside a document can reduce the need to leave the active task. On smaller displays, the same content may need a single-column sequence, disclosure or contextual panel. Implement the relationship between context and work, rather than copying a fixed column count.

### 4.5 Oracle and eClinicalWorks: distinguish record access from reconciliation

Oracle documents a task for external information that may need reconciliation. eClinicalWorks describes keyword search, a timeline and explicitly saving an external record. [C04, C12]

**Design inference:** viewing imported information does not mean it has been reviewed, reconciled or adopted. Presentation should use the state already supplied by Open Intelligence, without inferring clinical acceptance from display or retrieval.

### 4.6 Tebra and NextGen: make person and capability context explicit

Tebra documents guest access alongside separate health records, documents and messages. NextGen's help describes proxy selection and features that vary with the portal subscription/configuration. [C14, C22]

**Design inference:** labels such as “My records” should refer to the actual viewed person, especially when an authorized caregiver is involved. Existing backend access decisions remain authoritative. The interface must not suggest a capability exists merely because it appears in a competitor.

### 4.7 Oncology tools: preserve domain context without importing clinical behavior

OncoEMR brings profiling-related work into the chart. ARIA connects oncology information and images across professional roles. [C37, C38]

**Design inference:** Open Intelligence should make existing pathology, imaging, laboratory, molecular and evidence records reachable in context. The lesson is continuity of information. It does not authorize new ordering, staging, treatment-selection or dose-calculation logic.

## 5. Weakness and opportunity analysis

### What the evidence supports

| Finding | Strength and limit of evidence | Frontend response | Validation |
|---|---|---|---|
| EHR performance depends on implementation as well as vendor | A 2018 study compared standardized tasks across four sites using two vendors; results varied within and between vendors. Historical emergency-care scope [C39] | Evaluate the actual OI paths and configurations | Time, completion, errors and screen transitions |
| Navigation and loading can frustrate users despite broad functionality | Individual eCW reviews report difficulties, alongside favorable reviews [C41]; indexed Capterra and Software Advice material corroborates the existence of similar complaints [C42, C43] | Predictable navigation; clear loading and failure states; preserve context during recovery | Slow-network and failed-request journeys |
| Adding cross-links everywhere can make structure less clear | NHS navigation guidance cautions against repeated destinations used to compensate for poor core journeys [C34] | Give functions a clear home and add contextual links sparingly | First destination choice, backtracking and lost-place observations |
| More accessible records do not automatically become understandable | MyChart study reports information-availability and access barriers in one implementation [C40] | Explain state in plain language while keeping original information visible | Patient interpretation checks; no invented clinical explanations |
| Fewer clicks alone is an incomplete goal | Navigation-path research examines transitions and task performance [C46] | Reduce unnecessary transitions while retaining identity and confirmation checks | Compare accuracy and recovery alongside interaction count |

### How review sources were handled

G2 review content was inspected beyond its generated summary. Some users describe the same product as easy to use while others describe lag or navigation difficulties. This inconsistency is useful: it warns against turning a review-site average into a universal UX verdict. [C41]

Capterra and Software Advice content was used only as indexed, self-selected feedback. These platforms may syndicate reviews; repeated descriptions across them are not automatically independent participants. The review material helps define things to test, not estimate how many users encounter a defect. [C42, C43, C45]

Reddit comments were used only as anecdotal issue discovery. A clinician discussion mentioning click burden is not proof of a reproducible product defect. [C44]

A retrieved Capterra “Epic” listing mixed healthcare comments with comments about a children's reading app. Its aggregate score was excluded because entity identity was not reliable. [C47]

No numerical vendor ranking, market-share claim, unsupported “best UX” verdict or comparative patient-safety claim is made.

## 6. Competitor technology research

### Verified technologies versus unknown internals

The table deliberately separates public platform/interface evidence from actual framework evidence.

| Product | Publicly verified technology or architecture within scope | Unknown or not verified here |
|---|---|---|
| Epic | Hyperdrive web-based client and Windows-native plugin infrastructure; SMART on FHIR/OAuth integration [C02, C03] | MyChart frontend framework, UI library, state system and production testing stack |
| Oracle Health | Millennium FHIR R4 patient API and US Core profile [C06] | New EHR/portal frontend framework, component library and underlying model implementation |
| MEDITECH | Greenfield patient-facing FHIR R4 and scheduling APIs [C08] | Expanse frontend language/framework, component library and rendering architecture |
| athenaOne | HL7, CCD and FHIR interoperability [C11] | Frontend framework and database internals; athenaPractice documents are not substituted |
| eClinicalWorks | Official FHIR application integration surface [C13] | Current EHR/healow JavaScript framework, state management and UI libraries |
| NextGen | Separate Office and Enterprise API programs; Office patient-access FHIR [C15] | Which frontend implementation applies to each generation and deployment |
| Elation | Public API, HL7 and FHIR integration documentation [C17] | Proprietary console framework and design-system implementation |
| DrChrono | Web/iPad/iPhone API product scope; ConnectEHR-mediated FHIR workflow [C19, C20] | Native languages, web framework and internal data architecture |
| Tebra | Published patient FHIR guide [C23] | EHR/portal framework, state manager, database and current production dependency versions |
| Practice Fusion | Published FHIR patient-app surface [C26] | Frontend framework, current component architecture and runtime dependencies |
| AdvancedMD | FHIR R4, OAuth 2.0 and SMART App Launch documentation [C29] | Frontend framework and task-dashboard visualization library |
| Canvas proprietary platform | Python SDK; sandboxed plugins; Django ORM classes over read-only views; FHIR R4 [C31, C49] | The entire proprietary EHR stack; SDK technologies are only scoped evidence |
| Canvas public reference mobile app | Manifest lists React Native, Expo, TypeScript, TanStack React Query, React Hook Form, FlashList and AJV [C50] | Current production adoption; the manifest is not a recommendation to install those historical versions |
| NHS App frontend library | npm distribution, Sass styles and optional Nunjucks macros [C35] | Every native or embedded service's implementation |
| OncoEMR | Official product evidence for chart, mobile and portal surfaces [C37] | Frontend framework, backend language, visualization/state/testing stack |
| ARIA | Documented DICOM-compliant planning-system relationship [C38] | Current frontend framework, database implementation and client tooling |

**Do not infer technologies from page appearance.** A vendor's marketing website, help center or recruiting advertisement may use a different stack from its clinical application. FHIR describes an interoperability contract, not a React component tree. “Cloud” and “mobile” do not identify a programming language.

The Canvas mobile repository has an Apache-2.0 license at its root [C32]. That is evidence about that repository only. No general license conclusion is made about all dependencies, the proprietary Canvas EHR or any other vendor.

### Implications for Open Intelligence's framework decision

There is no evidence-based reason to migrate the current application merely because some reference software uses React Native or a public design system provides Nunjucks macros. Existing rendering boundaries, test infrastructure and real defects should drive the choice.

For this frontend-only scope, the preferable baseline is:

- Keep the current runtime, routing contracts and API behavior.
- Establish shared tokens and reusable presentation components in the existing architecture.
- Introduce a library only for a concrete capability that is difficult to implement correctly, after compatibility and licensing review.
- Keep authentication, permissions, persistence and clinical validation outside the redesign changes.
- Evaluate component behavior in the actual application before assuming a library supplies accessible usage by default.

These are engineering recommendations derived from the scope, not claims about a competitor's superiority.

## 7. Candidate requirements and decision log

| ID | Proposed decision | Evidence/rationale | Rejected alternative | Status |
|---|---|---|---|---|
| CR-01 | Patient home uses understandable groups of existing tasks | NHS task research; no invented backend capabilities [C33] | Exposing every internal module as a peer destination | Ready for repository mapping |
| CR-02 | Clinician workspace and patient chart have visibly distinct scopes | athenaOne patient-context specification [C10] | Mixing the patient selector into unrelated global actions | Ready for repository mapping |
| CR-03 | Chart overview preserves record provenance and status | Oracle external-record documentation [C04] | Displaying imported information as implicitly verified | Preserve existing fields |
| CR-04 | Use direct summary-to-detail links | Tebra overview and records structure [C21] | Replacing complete records with a summary-only surface | Ready for repository mapping |
| CR-05 | Adapt contextual panels to available width | Elation adjacency pattern is useful but mobile benefit is unmeasured [C16] | Copying a fixed three-column layout everywhere | Requires responsive tests |
| CR-06 | Search results keep enough identity, date and source to orient users | PRISMA pattern and OI traceability requirements [C12] | A generic search list without source context | Use existing search only |
| CR-07 | Measure completed tasks, errors and recovery, not only clicks | Independent navigation research [C46] | Declaring success because a screen looks cleaner | Requires executed baseline and follow-up |
| CR-08 | No framework migration based on competitor stacks | Most internal stacks remain unknown; public code is narrowly scoped | Adopting a large dependency set without application evidence | Recommended |
| CR-09 | Show existing unavailable/error states truthfully | Patient-access findings and configuration-dependent portals [C14, C40] | Invented upcoming events, sample clinical values or falsely successful actions | Required scope constraint |
| CR-10 | Retain oncology context using current record categories | Oncology product patterns [C37, C38] | Adding treatment recommendations or duplicating clinical workflows | Required scope constraint |

## 8. What this research cannot finish by itself

The implementation must establish the actual role model, current feature inventory, source data, screens, supported actions and regression boundaries from the repository. No unsupported clinical role, appointment system, message service or patient identity mechanism should be added to satisfy a proposed navigation diagram.

The remaining direct research is narrowly actionable:

1. Run representative patient, caregiver and clinician tasks on the implemented interface with appropriate authorization.
2. Observe whether users can identify the current patient and source of a record without prompting.
3. Test keyboard navigation, focus movement, reading order, zoom, touch targets and narrow-screen behavior.
4. Exercise delayed requests, empty data, authorization failures and unsuccessful saves without altering backend rules.
5. Record measured task completion, errors, backtracking and recovery. Preserve screenshots of the executed OI flows.
6. Add authentic user findings when available; keep heuristic and simulated findings labeled until then.

This research does not claim HIPAA compliance, clinical validation, WCAG conformance or production readiness. Those conclusions require evidence beyond a frontend redesign.

## Source register

Each source below has a corresponding structured entry in competitor-sources.json. Dates are supplied only where stated by the publication or document. All were researched on 2 November 2026 US Eastern. “Search excerpt” entries were reviewed in retrieval output but not successfully opened in full; this is reflected in the machine-readable register.

- **[C01]** [Explore MyChart](https://www.mychart.org/l/en-us/explore/) — Epic/MyChart; official product documentation; publication date not stated; opened.
- **[C02]** [Hyperdrive](https://open.epic.com/Hyperdrive) — Epic; official developer documentation; publication date not stated; opened.
- **[C03]** [Explore by interface type: FHIR](https://open.epic.com/Interface/FHIR) — Epic; official developer documentation; publication date not stated; search excerpt.
- **[C04]** [Oracle Health EHR introduction](https://docs.oracle.com/en/industries/health/oracle-health-ehr/ehrug/introduction.html) — Oracle Health; official product documentation; publication date not stated; opened.
- **[C05]** [Patient Portal generally available](https://www.oracle.com/news/announcement/oracle-health-ai-powered-patient-portal-generally-available-2026-08-12/) — Oracle Health; official product announcement; 2026-08-12; opened.
- **[C06]** [Millennium FHIR R4 patient endpoints](https://docs.oracle.com/en/industries/health/millennium-platform-apis/mfrap/api-patient.html) — Oracle Health; official developer documentation; publication date not stated; search excerpt.
- **[C07]** [Expanse for Physicians](https://ehr.meditech.com/ehr-solutions/expanse-for-physicians) — MEDITECH; official product marketing; publication date not stated; search excerpt.
- **[C08]** [Greenfield Workspace](https://ehr.meditech.com/ehr-solutions/greenfield-workspace) — MEDITECH; official developer documentation; publication date not stated; search excerpt.
- **[C09]** [Expanse Ambulatory Care](https://ehr.meditech.com/ehr-solutions/expanse-ambulatory-care) — MEDITECH; official product marketing; publication date not stated; search excerpt.
- **[C10]** [athenaOne Base Service Description, Summer 2026](https://www.athenahealth.com/sites/default/files/media_docs/athenaOne-Service-Description.pdf) — athenahealth; official product specification; 2026-07-22; opened.
- **[C11]** [FAQ](https://www.athenahealth.com/about/faq) — athenahealth; official product documentation; publication date not stated; search excerpt.
- **[C12]** [PRISMA](https://www.eclinicalworks.com/products-services/interoperability/prisma/) — eClinicalWorks; official product marketing; publication date not stated; opened.
- **[C13]** [Interoperability Solutions](https://www.eclinicalworks.com/products-services/interoperability/) — eClinicalWorks; official product documentation; publication date not stated; search excerpt.
- **[C14]** [NextGen Office Patient Portal Overview](https://www.community.nextgen.com/mtknowledge/articles/Knowledge/NextGen-Office-Patient-Portal-Overview) — NextGen; official help documentation; updated 2025-05-17; opened.
- **[C15]** [API overview](https://www.nextgen.com/api) — NextGen; official developer documentation; publication date not stated; search excerpt.
- **[C16]** [EHR product](https://www.elationhealth.com/platform/ehr/) — Elation; official product marketing; publication date not stated; opened.
- **[C17]** [Integrations](https://www.elationhealth.com/integrations/) — Elation; official developer documentation; publication date not stated; search excerpt.
- **[C18]** [OnPatient Basics](https://support.drchrono.com/home/200027209-onpatient-basics) — DrChrono; official help documentation; updated 2025-05-23; search excerpt.
- **[C19]** [Why use DrChrono's API?](https://support.drchrono.com/home/201883240-why-use-drchrono-s-api) — DrChrono; official developer documentation; publication date not stated; search excerpt.
- **[C20]** [FHIR API FAQ](https://support.drchrono.com/home/19311277515291-fhir-api-faq) — DrChrono; official help documentation; publication date not stated; search excerpt.
- **[C21]** [Clinical Patient Management](https://helpme.tebra.com/Clinical/Patient_Management) — Tebra; official help documentation; publication date not stated; opened.
- **[C22]** [Patient Experience: Patient Portal](https://helpme.tebra.com/Clinical/Patient_Management/Patient_Portal/Patient_Experience%253A_Patient_Portal) — Tebra; official help documentation; updated 2025-12-19; opened.
- **[C23]** [FHIR API User Guide](https://www.tebra.com/wp-content/uploads/2025/05/Tebra-FHIR-API-User-Guide.pdf) — Tebra; official developer documentation; publication date not stated; search excerpt.
- **[C24]** [Medical Charting](https://www.practicefusion.com/emr-medical-charting/) — Practice Fusion; official product marketing; publication date not stated; search excerpt.
- **[C25]** [Encounter improvements](https://practicefusion.my.site.com/partnerkb/s/article/Preview-the-recent-improvements-to-the-Encounter) — Practice Fusion; official help documentation; publication date not stated; search excerpt open failed.
- **[C26]** [FHIR API Get Started](https://www.practicefusion.com/fhir/get-started/) — Practice Fusion; official developer documentation; publication date not stated; search excerpt.
- **[C27]** [Patient Cards](https://www.advancedmd.com/emr-ehr-software/patient-cards/) — AdvancedMD; official product marketing; publication date not stated; search excerpt.
- **[C28]** [EHR software](https://www.advancedmd.com/emr-ehr-software/) — AdvancedMD; official product marketing; publication date not stated; search excerpt.
- **[C29]** [FHIR implementation](https://fhir.advancedmd.com/fhir) — AdvancedMD; official developer documentation; publication date not stated; search excerpt.
- **[C30]** [Guides](https://docs.canvasmedical.com/guides/) — Canvas Medical; official developer documentation; publication date not stated; opened.
- **[C31]** [FHIR API introduction](https://docs.canvasmedical.com/api/) — Canvas Medical; official developer documentation; publication date not stated; search excerpt.
- **[C32]** [Open source mobile patient app](https://github.com/canvas-medical/mobile-patient-app) — Canvas Medical; official source repository; publication date not stated; opened.
- **[C33]** [The structure of the NHS App](https://design-system.nhsapp.service.nhs.uk/patterns/the-structure-of-the-nhsapp/) — NHS App; official design research; publication date not stated; opened.
- **[C34]** [Move between areas of the NHS App](https://design-system.nhsapp.service.nhs.uk/patterns/navigate-the-nhs-app/) — NHS App; official design research; publication date not stated; opened.
- **[C35]** [Installing NHS App frontend with npm](https://design-system.nhsapp.service.nhs.uk/get-started/installing-with-npm/) — NHS App; official developer documentation; publication date not stated; opened.
- **[C36]** [Accessibility statement](https://www.nhs.uk/nhs-app/about/privacy-legal-information/nhs-app-accessibility-statement/) — NHS App; official accessibility statement; updated 2025-12-22; search excerpt.
- **[C37]** [OncoEMR](https://flatiron.com/oncology/oncology-ehr) — Flatiron; official product marketing; publication date not stated; opened.
- **[C38]** [ARIA OIS](https://www.siemens-healthineers.com/radiotherapy/software-solutions/aria-ois) — Siemens/Varian; official product marketing; publication date not stated; opened.
- **[C39]** [A usability and safety analysis of electronic health records: a multi-center study](https://pmc.ncbi.nlm.nih.gov/articles/PMC7646875/) — Cross-vendor usability; original peer reviewed research; 2018-07-02; search excerpt.
- **[C40]** [Patient Experiences and Perspectives When MyChart is Introduced in a Large Community Hospital](https://www.jmir.org/2025/1/e66353) — MyChart patient research; original peer reviewed research; 2025-01-23; opened.
- **[C41]** [G2 eClinicalWorks user reviews](https://www.g2.com/products/eclinicalworks/reviews?page=5&qs=pros-and-cons) — eClinicalWorks reviews; user reviews; publication date not stated; opened.
- **[C42]** [Capterra eClinicalWorks reviews](https://www.capterra.com/p/120360/eClinicalWorks/reviews/) — eClinicalWorks reviews; user reviews; publication date not stated; search excerpt open failed.
- **[C43]** [Software Advice eClinicalWorks reviews](https://www.softwareadvice.com/medical/eclinicalworks-profile/) — eClinicalWorks reviews; user reviews; publication date not stated; search excerpt open failed.
- **[C44]** [How do you feel about Epic and what are your gripes with the software?](https://www.reddit.com/r/medicine/comments/1uxef2n/how_do_you_feel_about_epic_and_what_are_your/) — Clinician community; community anecdote; publication date not stated; search excerpt.
- **[C45]** [Software Advice Elation reviews](https://www.softwareadvice.com/medical/elation-emr-profile/reviews/) — Elation reviews; user reviews; publication date not stated; search excerpt open failed.
- **[C46]** [A micro-analytic approach to understanding electronic health record navigation paths](https://pubmed.ncbi.nlm.nih.gov/32937215/) — Cross-vendor workflow research; original peer reviewed research; 2020; search excerpt.
- **[C47]** [Capterra Epic reviews](https://www.capterra.com/p/126804/Epic/reviews/) — Excluded source; excluded mixed entity reviews; publication date not stated; search excerpt.
- **[C48]** [SDK Data](https://docs.canvasmedical.com/sdk/data/) — Canvas Medical; official developer documentation; publication date not stated; search excerpt.
- **[C49]** [The Canvas SDK](https://docs.canvasmedical.com/sdk/) — Canvas Medical; official developer documentation; updated 2026-10-07; opened.
- **[C50]** [Public mobile patient app package manifest](https://github.com/canvas-medical/mobile-patient-app/blob/main/package.json) — Canvas Medical; official source repository; publication date not stated; opened.

