# OI-20 verification and product-discovery annex — 2026-11-02

**Status:** Verified evidence where marked; all new architecture and requirements are PROPOSED FOR REVIEW, not adopted. This annex complements rather than replaces the existing Open Intelligence OI-00–OI-21 handbook, D1–D5 research gates, OI-16 mandate, OI-17 commercial rights policy, OI-06 clinical model, OI-04 experience research, OI-18 architecture options and OI-20's 76-row audit. It does not authorize human clinical use, clinical research, model deployment, major stack change or release.

**Observation time:** November 2, 2026, America/New_York.
**Verified GitHub main:** 6156fb50014b7ab9172d92c79eee591adf3486c2. **No local test execution** was conducted for this annex. Specific public CI receipts are identified below.

## 1. Existing sources, source-of-truth, and status semantics

- [OI-20 audit and its findings database](https://app.notion.com/p/ee53866f77ef82128797813cfee06927) and [individual findings](https://app.notion.com/p/40c3866f77ef8050ad9ff7277c89912b).
- [Founder-accepted OI-16 full first-party mandate](https://drive.google.com/file/d/1_OBrshpcETQ6lgrcts4JVaVo6kRce8Z0/view); [OI-17 adopted licensing policy](https://drive.google.com/file/d/15jhFNNeXxpmmYKgfEK2SYXzq6GIZlJrZ/view).
- [OI-06 data model](https://drive.google.com/file/d/1BnCIgXYYJ9Sk-SbOEazQeo5zwwoW_dzo/view); [OI-04 experience/IA research](https://drive.google.com/file/d/1ct91Pb4VIad05S_1hIaTyesnABD0xaH2/view); [OI-18 proposal](https://drive.google.com/file/d/1XgNBNmaSgksQTx189ctKf6Ahv4C2coXS/view); [OI-19 technology proposal](https://drive.google.com/file/d/1SBY-_MPrDvV2JyV6_abehV9gHOCFOI3I/view); [working Drive folder](https://drive.google.com/drive/folders/1O037nOW8L15vnsjGEWwETVKejyB71779).
- [Open Intelligence repository](https://github.com/OpenxIntelligence/open-intelligence); [existing implementation-status record](https://github.com/OpenxIntelligence/open-intelligence/blob/main/docs/IMPLEMENTATION_STATUS.md).

Interpretation: founder-accepted scope, safety boundaries and licensing policy constrain proposed designs; accepted scoped ADRs resolve later choices. A document can define desired behavior but cannot establish that code exists. A tested commit can prove bounded behavior but cannot prove clinical efficacy or legal release rights. Current authoring statuses should distinguish VERIFIED-REPO, VERIFIED-CI, VERIFIED-SOURCE, ACCEPTED-DECISION, PROPOSED, UNRESOLVED, BLOCKED and CLINICALLY-VALIDATED (none claimed here).

The November 2 founder direction **excludes Next.js**, including as a proposed new Open Intelligence frontend. OI-19's Next.js table and historic OI-05/12/13 build plan cannot override this instruction. No replacement frontend/backend/framework is approved by this annex. Older clinical-architecture diagrams, historical project names, and outside patient journeys remain complementary research, not canonical replacements.

## 2. Repository inspection: what exists and what does not

The main branch contains a dependency-light, local-only **Python standard-library HTTP application, SQLite case ledger, and original vanilla JavaScript/CSS user interface**. It also includes synthetic fixtures, tests and research tools. Observed app components include:

| File / component | Bounded built capability | Exclusions |
| --- | --- | --- |
| src/open_intelligence/__main__.py | Loopback HTTP surface and case, source, timeline, evidence, investigation, options and review endpoints | No production identity or remote EHR gateway |
| src/open_intelligence/store.py | Synthetic case state, source/version/claim and event persistence | Not an enterprise EHR or multi-tenant clinical database |
| src/open_intelligence/mission.py | Read-only source-backed Patient Mission workflow projection | Not clinical decision support, autonomous care or a second record |
| src/open_intelligence/timeline.py; changes.py | Chronology and amendment/change review | Not validated full bitemporal historical replay |
| src/open_intelligence/rights.py; patient_access.py | Synthetic provenance/access-boundary research | Not legally verified real patient consent enforcement |
| src/open_intelligence/investigation.py; discovery.py | Bounded research/investigation workflow | Not validated clinical treatment recommendations or verified trial eligibility |
| web/index.html; app.js; mission.js; CSS | Source-oriented synthetic clinician case workspace | Not final approved patient/clinician product navigation |
| examples/synthetic; tests; GitHub Actions | Artificial workflow probes and regression tests | Not representative clinical or security validation |

The exact observed [main commit](https://github.com/OpenxIntelligence/open-intelligence/commit/6156fb50014b7ab9172d92c79eee591adf3486c2) has passing GitHub-reported [synthetic workflow CI run 41474423149](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41474423149) and [Crossref metadata run 41474423273](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41474423273). Do not recycle test results from another SHA. Open draft PRs include [#49 policy/architecture](https://github.com/OpenxIntelligence/open-intelligence/pull/49), [#51 patient/source identity](https://github.com/OpenxIntelligence/open-intelligence/pull/51), [#48 patient chronology/review](https://github.com/OpenxIntelligence/open-intelligence/pull/48), and [#41 submission safety](https://github.com/OpenxIntelligence/open-intelligence/pull/41). Their individual test success is not evidence that all are safely integrated together.

The main branch was observed unprotected. A root application dependency manifest or release-specific SBOM was not observed. The file tools/research/requirements.lock is **research-only**, contains pinned external packages, and does not authorize production use of LangGraph or any transitive dependency. A distribution license has not been selected; no installed code, model weights, guideline content, images, fonts or terminology can be declared commercially cleared from this inspection alone.

## 3. Audit revalidation: critical and selected high-severity findings

| ID | Independent observation | Disposition / owner action |
| --- | --- | --- |
| AUD-001 | CONFIRMED. Current Python/SQLite/vanilla JS main conflicts with historical Next.js build docs; founder decision forbids Next.js | Scope OI-05/12/13 historic sections; date-stamp OI-00 and OI-13 actual main, intended feature PRs, tests and release branch. Finding not closed until canonical docs repaired |
| AUD-002 | NOT REPRODUCED. Connected Drive query filtered to trashed=true returned no accessible items; visible historical research folder has two files | Obtain original 56-item manifest with IDs, check account ownership and current status, prepare reversible archive restoration; do not infer recovered or deleted |
| AUD-003 | PARTIALLY VERIFIED. [Official Meta](https://dev.meta.ai/events/global-hackathon) and [organizer](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) call Indie individual/students, Startup teams/founders; Nov 4 due 9PM ET | Inspect accepted official rules and applicant portal for 4-person eligibility, team track, video length, evidence and media format. Public pages do not resolve them |
| AUD-004 | OI-20 shows OI-00 index ending at OI-15 despite OI-16–20 present | Update the existing index with current statuses after checking live exact document |
| AUD-005/006 | OI-05 self-precedence and conflicting tech suggestions in OI-18/19 | Record scope-limited precedence and commission framework/domain ADRs; do not silently adopt TS/Nest, FastAPI or other stack |
| AUD-007 | Agent counts and topology conflict across design docs | Evaluate deterministic, one agent+tools, specialist tool orchestration, parallel agents on the same tasks |
| AUD-011/012/015 | First-party LIS mandate and license policy conflict with old component and LIS suggestions | OI-16/17 supersession; component/version-specific rights and service boundaries; no automatic Orthanc/Medplum adoption |
| AUD-016–019 | Future clinical functions conflict with prototype-only hard limits | Keep Nov 4 synthetic/nonclinical; research future intended use, risk and authorization per function; physician review alone is not a regulatory exemption |
| AUD-025/050 | OI-19 C1–C12 are proposals, not verified modifications to decision register | Reconcile Ceph/Garage, Snowstorm, Valkey caches, DBOS, MCP, Ory, authorization, TimescaleDB, OHIF, Nest, Nextflow and Citus/LinuxForHealth by exact version and legal review |
| AUD-030/055/056 | OI-14 naming collision and inconsistent decision/ID systems | Use aliases and explicit redirects first; do not rename/delete historical records en masse |

**Not performed:** a 76/76 row-by-row independent audit, production SBOM, complete GitHub code review, library restoration, live patient integration, clinical study or full regulatory assessment. Unchecked findings remain OPEN, not resolved by this annex.

### Reversible recovery checklist (AUD-002)
Obtain drive-publish-state.json and the 56 original file IDs; query each in the account owning them. Classify recovered, present elsewhere, in accessible trash, permission-blocked or unrecoverable. For recoverable files, preserve original names/IDs/versions, restore only with appropriate authority into clearly marked historical archive, log before/after parent IDs and timestamps, and create an inverse move log. Verify count, hashes where available and references before any canonical promotion. No trash mutation or restore has occurred.

## 4. Proposed full product architecture, preserving accepted scope

This is an **additive contract map** to OI-16/18, not a new canonical decision. Every domain can be a first-party module or independently deployed service depending on measured transactions, isolation, regulation and load; do not assume microservices are inherently preferable.

| First-party bounded context | Owned operational truth | Key inbound and outbound contracts |
| --- | --- | --- |
| Patient, identity and authority | Identity matching, organizations, grants, revocations, representatives | SubjectBinding, AuthorityGrant, AccessDecision, identity review |
| EHR/EMR and oncology operations | Encounters, documented assessments, problems, orders, care plans | Encounter, Order, CancerEpisode, ClinicianReview |
| LIS/LIMS and pathology | Specimens, accession, custody, QC, verified results, diagnostic reports/slides | Specimen, AssayRun, ResultVersion, PathologyReport |
| RIS/PACS and imaging | Modality, study/series/instance, image bytes, reporting and measurements | ImagingStudy, ImageAsset, Measurement, Reading |
| Genomics and biological science | Assemblies, calls, transcriptomics, proteomics, biosample derivatives | MolecularAssay, VariantCall, MaterialLineage |
| Medication and therapy | Intent, plan, prescribed, dispensed, administered, toxicity, response/outcomes | Regimen, MedicationEvent, TreatmentOutcome |
| Patient/caregiver and care operations | Authorized communication, goals, PROs, referral logistics and task receipts | PatientGoal, SymptomReport, CareTask, CompletionReceipt |
| Research, trials and evidence | Versioned public and licensed sources, study/trial identity, provenance and rights | KnowledgeClaim, EvidenceSnapshot, TrialSiteStatus |
| Native intelligence | Question registry, temporal/world projections, model/tool contract, reviewable hypothesis | InvestigationRun, PatientWorldProjection, BiomedicalClaimGraph |
| Enterprise trust and platform | Identity policy, secrets, audit, outbox, storage, recovery, observability | EventEnvelope, AuditEvent, PolicyDecision |

**Core invariants:** source versions are immutable; every claim cites the exact version and relevant specimen/time; operational order is not completed administration; missing/pending/negative/contradicted are separate states; no unverified identity matching; consent content is not enforcement; a model hypothesis does not mutate clinical truth; permission revocation affects derived output; updated evidence invalidates only dependent conclusions; every human approval is bound to verified identity and scope.

**Proposed common contracts:** PatientIdentityBinding, AuthorityGrant, SourceArtifact and SourceVersion, Assertion and Interpretation, Specimen and AssayRun, EvidenceClaim, InvestigationRun, ReviewDecision and OperationalTask. Require subject + organizational scope, original source, event/issue/receipt/knowledge clocks, version, state, rights, agent or human actor and idempotent event ID. The Patient World Model is an access-filtered versioned projection, not a writable replacement for domain records. The Biomedical World Model records versioned evidence and uncertainty, not unlicensed full-text source material. Cross-domain events carry IDs, source version, subject, purpose and correction reference; a consumer must be idempotent and must not infer missing clinical data.

**Historical query acceptance:** snapshot as-known-at at T0 must exclude later-arriving T1 findings even if their medical event happened before T0. A version-changing report must preserve original observed contents. Current repo filtered status must not be mistaken for a complete bitemporal as-known-at implementation.

## 5. Canonical coverage reconciliation and remaining specification opportunities

**November 2 follow-up correction:** The 30 OI-DISC rows are **crosswalk aliases**, not 30 independently discovered requirements or a new product backlog. I compared them with the extensive existing OI-04, OI-06, OI-09, OI-10, OI-16 and OI-18 primary documentation. Most already have named contracts, sections, research tasks or evaluation metrics. The [companion CSV](oi20-requirements-traceability-2026-11-02.csv) now identifies canonical IDs for every row and a next **nonduplicate** acceptance task. The existing OI-06 specification already defines ENT-P01–P52 (proposed), the ValueStatus taxonomy (§8.1), bitemporal query contracts (§9.6) and twelve D2 gaps. OI-04 specifies patient-view PV-01–PV-10 and content-safety CS-01–CS-15. OI-09 contains evaluation metrics M1–M29. OI-16 already owns the sixteen first-party product domains PD-01–16 and shared platform foundations PF-01–10. Those structures are not replaced by this document.

**Evidence/classification rule:** `EXISTING_REQUIREMENT_PARTIALLY_BUILT` or `EXISTING_PROPOSED_DOMAIN_CONTRACT` in the CSV means that a requirement is already written, not that the feature is verified working. `ACTIVE_CODE` reflects ongoing draft PR #51/#53 with unmerged identity work and is not authorization to deploy. No OI-DISC item should become a canonical new requirement until an owner identifies a real missing contract or untested acceptance condition. The meaningful gap is usually **execution evidence and cross-domain boundary testing**, not another feature heading.

**Identity, source and time**
- OI-DISC-01: false patient/specimen binding quarantine and reversible adjudication, including two institutions with colliding identifiers.
- OI-DISC-02: purpose-, source-, role-, consent- and time-filtered read/derivative access with revocation propagation and audited break-glass.
- OI-DISC-03: distinguish event occurred, source issued, platform received, knowledge available and correction time; support genuine as-known-at replay.
- OI-DISC-04: represent missing, not assessed, pending, indeterminate, negative, conflicting and noncomparable values separately.
- OI-DISC-05/06: separate clinical order from execution, QC-verification, result report and correction; link order to accession/specimen/assay/author.
- OI-DISC-07/08: preserve original imaging/slide and variant reference build, transcript, specimen and time; no automatic cross-assay merging.
- OI-DISC-09: distinguish therapy plan, prescription, dispense, administration, adherence, toxicity, response and reason stopped.

**Biological and scientific intelligence**
- OI-DISC-10: inspectable, rights-qualified, versioned biomedical claim network with contradictions, retractions and applicability.
- OI-DISC-11: durable clinical/research question record with competing hypotheses and discriminating evidence.
- OI-DISC-12: optional diagnostic research planner weighs expected information gain against burden, cost, risk, delay and decision impact, without auto-ordering.
- OI-DISC-13: tissue/sample optionality graph links amount, processing, quality, permissions, remaining material, assay feasibility and deadlines.
- OI-DISC-14: therapeutic option portfolio records prerequisites, evidence class, lead times, access, uncertainty and authorized owner, not clinical ranking.
- OI-DISC-15: a public trial listing is a lead, not verified eligibility or site recruitment; track site contact and confirmation timestamp.
- OI-DISC-16: model registry of task, input modality, weights and data rights, evaluation population, output authority and failure modes.
- OI-DISC-17: event-driven selective re-evaluation including retractions, corrections, consent changes and new study publications.
- OI-DISC-18: governed experiment records contain hypotheses, planned measures, review and outcomes; research planning never equals clinical trial authorization.

**Experience, operations, validation and trust**
- OI-DISC-19: role- and health-literacy-appropriate explanations distinguish reported source, extraction proposal, research hypothesis and clinically reviewed finding.
- OI-DISC-20: clinician change queue links exact source diff, affected question, decision and review receipt.
- OI-DISC-21/29: care-navigation work tracks referral, appointment, travel, access, financial and language barriers to authorized completion receipts.
- OI-DISC-22: urgent safety detection is a separately qualified deterministic engine and escalation workflow, not an unconstrained research-agent reply.
- OI-DISC-23: compare automated outputs with deterministic/manual baselines; evaluate harmful leakage, error, abstention, latency and reviewer workload.
- OI-DISC-24/25: prevent PHI egress and mixing of synthetic, de-identified cohort and authorized real patient domains; minimize retention.
- OI-DISC-26/27: build-scoped SBOM/right/NOTICE gate and disaster recovery, event replay and history preservation.
- OI-DISC-28: machine-readable requirement → owner → contract → issue → commit → test → validation evidence.
- OI-DISC-30: validate ordinary oncology, recurrence, survivorship, caregiver and resource-constrained journeys alongside unusual high-resource cases.

### 5.1 Research-only contract candidate: adaptive diagnostic value-of-information investigation

**Status:** UNDER-SPECIFIED RESEARCH PROPOSAL (OI-DISC-12), tied to existing PF-04/05/08, PD-03/06/14, ENT-P07–P10/P51/P52, OI-06 D2G-01, OI-09 metrics and OI-10 clinical gates. It is **not an authorized clinical test-recommendation or order engine**; it must not select a test for a real person or emit a treatment/diagnostic verdict. New capabilities must be assessed against the older complementary experimental-loop research, not introduced as a parallel architecture.

**Scientific basis (separate from OI implementation evidence):**
- [Chen & Willan, Statistics in Medicine 2014, PMID 24403241](https://pubmed.ncbi.nlm.nih.gov/24403241/) derives value-of-information methods for assessing diagnostics and future research needs; it does **not** validate Open Intelligence.
- [Allenbrand, DECIDE-Lab, Diagnostics 2026, DOI 10.3390/diagnostics16152356](https://pubmed.ncbi.nlm.nih.gov/42587593/) describes a proposed Bayesian / sequential decision framework in illustrative simulations, comparing *decision-changing* usefulness, burden, delays and test properties. Its examples are methodological, not a qualified oncology test-selection policy.
- [Manski, diagnostic decisions under ambiguity, 2013](https://pmc.ncbi.nlm.nih.gov/articles/PMC3568364/) cautions against assuming reliable probability distributions or utilities where data and credible priors do not exist. For OI this means **abstain from a numeric value-of-information estimate** rather than fabricate probabilities.

**15-field implementation contract (proposed, not deployed):**

| Field | Required boundary |
| --- | --- |
| Purpose | Map what uncertainty a *research* question might be able to reduce and whether any future clinician decision could be affected; avoid reflexive more-testing bias |
| Users | Qualified clinician-researchers reviewing fictional cases first; no autonomous patient-facing deployment |
| Trigger / workflow | A question with documented alternatives and an accountable reviewer → proposed discriminating observation → source/rights/specimen feasibility → assumptions → counterfactual branches → explicit research worksheet → human research disposition |
| Inputs | Versioned Patient World Model snapshot, durable Question, existing source assertions, specimen inventory, permissible evidence, decision alternatives *as proposed by the qualified reviewer* |
| Owned state | \`DiagnosticResearchQuestion\` points to existing question ID; \`CandidateInformationSource\` retains exact evidence and assay identity; \`CounterfactualBranch\` records possible results, uncertainty and consequences; never edits the underlying clinical record |
| Output/UI | Show **"Unknown / cannot calculate"** if prerequisites are missing; explain which result might distinguish alternatives, and why evidence is too weak to compare options; show burden, time, access and specimen dependency separately |
| Data contracts | Subject/episode/specimen, issued/learned/valid times, measurement method/version, diagnostic result states (including failed or indeterminate), rights class, model/policy version and source citations |
| Architecture | Read-only research planner over existing question/provenance/specimen graph; a deterministic preflight validates inputs and authority, then optional isolated simulation, never a new patient state ledger |
| External interfaces | Optional future terminology, assay, evidence and scheduling contracts, all rights/authorization checked; no live clinical order interface |
| Intelligence | Deterministic baseline identifies unknown decision branches; model may propose *questions* and sources but never supply unverified test sensitivity, prevalence, patient risk or utility |
| Authority | Research reviewer can accept/reject a question for discussion; only separately authorized clinician workflows can request tests. Proposal ≠ clinical authorization |
| Evidence | Every assumption cites a source and version, with validated population and relevance; uncertain utility estimates and model applicability are visibly qualified |
| Failure behavior | Unsupported probabilities/harms/turnaround, stale evidence, unavailable tissue, unverifiable consent, unlicensed data, inconsistent time or uncertain identity → \`ABSTAIN_INSUFFICIENT_BASIS\` and a list of missing prerequisites |
| Verification | Adversarial fictional scenarios: clinically irrelevant additional information, uncalibrated likelihood, missing specimen, conflicting source, impossible timing, revoked permission and paper-only test; zero automatic orders; independent review of information and framing |
| Dependencies/status/priority | Research specification P2 for full product; no implementation before domain owners approve requirements and security/clinical boundaries; the Nov-4 synthetic demo has **no** automatic diagnostic test planning |

**Safety-critical reasoning rules for any future numeric research simulation:** The null strategy ("no additional test") must always be included; test performance is not identical to clinical utility; represent both false positive and false negative consequences; incorporate turnaround and delay rather than assuming information is free; do sensitivity/robustness analysis of assumptions and group/site differences. Never calculate a numeric expected benefit or "optimal test" if source-calibrated priors, likelihoods and reviewer-defined utilities are absent. Present conclusions as *hypothetical research comparisons*, never patient-specific clinical instructions. Any deployment with consequential clinical impact requires a separate FDA/intended-use and applicable jurisdictional review.

**Synthetic acceptance cases to add to existing evaluation owner (not proof of completion):**
1. A fictional proposed assay changes no permitted decision branch; the planner outputs "no demonstrated decision-changing information" rather than an ungrounded positive value.
2. An assay has attractive analytical accuracy but no verified specimen or no licensed clinical performance source; abstain and identify the exact missing evidence.
3. A later-amended source changes a critical assumption; previous research worksheet remains retrievable but marked stale, not silently updated.
4. Two fictional sites differ in access or turnaround; comparison exposes the difference instead of assuming universal availability.
5. Source identity is ambiguous or an evidence permission is revoked; the plan is unavailable to unauthorized users, including derived summaries.
6. A model invents a numeric probability or proposes an executable order; deterministic validator rejects it, and the rejection is included in the evaluation receipt.

**Promotion test:** establish a falsifiable incremental benefit over a simple human-authored "missing information and available research options" worksheet. If scientific estimates cannot be validated or reviewers gain no measurable benefit, keep this as a qualitative research gap-map instead of implementing an optimization engine.

## 6. Proposed single end-to-end fictional journey and negative-path acceptance

1. **Create** fictional patient and clinical role. Similar fictional identifiers deliberately provoke a false-match/quarantine test.
2. **Authorize** a scoped synthetic information-sharing and research permission; a later revocation must block dependent views.
3. **Import** a source-preserving pathology version, lab measurement, imaging report and medication history. Maintain real event date versus late receipt date.
4. **Normalize as proposals:** units, terminology and statements are reviewed; untested cannot silently become negative.
5. **Attach biology:** biopsy accession, derivative aliquots, QC status and variant evidence belong to correct episode and sample.
6. **Construct projections** from source-backed relationships; report gaps and contradictions without rewriting originals.
7. **Open a question** with hypotheses, unknowns, next discriminating inputs and evidence needs.
8. **Investigate** permitted publications/trials and computation, recording model version, source rights, uncertainty and provenance.
9. **Present conditional options** with prerequisites and access lead time, not treatment recommendations or automatic orders.
10. **Review** exact source and reasoning; separate demo acknowledgment from verified professional clinical approval.
11. **Coordinate** an authorized fictional referral/review task and require a completion receipt.
12. **Amend** the pathology source; preserve prior version and stale only dependent investigations, respecting prior knowledge state.
13. **Explain** patient/caregiver view with confidence and permission, without presenting hypotheses as diagnosis.
14. **Measure and reassess** a synthetic outcome and new knowledge snapshot, replaying prior states with frozen policy/model versions.

Acceptance cases: zero seeded cross-patient linkage; byte-for-byte recoverable original; repeat-import idempotency; qualified specimen and assay context; explicit unknowns; time leakage blocked; no unauthorized model egress; evidence rights honored; valid version-bound change review; denial on revoked grants; no unreviewed treatment, dosing, eligibility or emergency advice. This whole scenario is NOT implemented yet.

For independent public workflow research, [Sid Sijbrandij's public osteosarcoma portal](https://osteosarc.com/) documents multiple clinical and assay timepoints across institutions, including T0 Dec 2022, T1 June 2024, T2 Jan 2025 and T3 April 2025. This suggests useful synthetic tests for repeated biopsies, WES/WGS/WTS/scRNA assays, cross-lab comparability, changing options and longitudinal outcomes. Never enter his identifiable or unlicensed raw clinical data into the public software fixture and never treat one journey as proof of therapeutic benefit. Compare against routine and lower-resource journeys.

## 7. UI/UX blueprint to take into existing OI-04 and D4/D5

**Status:** Candidate information architecture, not approved navigation. Designed for computer/desktop workflows and accessible patient/caregiver views; not a forced mobile-first direction.

| Surface | User job | Essential data and controls |
| --- | --- | --- |
| Work queue | Respond to new evidence and unfinished tasks | Event, accountable actor, reason, due/urgency, source and review state |
| Patient overview and chronology | Understand known, unknown and evolving clinical state | Episode, goals, time-accurate timeline, changing source versions, provenance |
| Clinical records | Acquire and reconcile data | Source review, missing records, contradictory reports, data normalization status |
| Diagnostics | Interpret provenance, not invent meaning | Specimen, accession, quality, lab, image/slide/genomic asset and derived measures |
| Questions & research | Investigate unknowns | Competing hypotheses, tool receipts, scientific source and applicability |
| Option portfolio | Track investigational paths | Preconditions, evidence tiers, time constraints, permitted owner and blocked reasons |
| Clinical review | Decide what is safe to communicate | Exact change, source link, review role, approval or rejection and rationale |
| Care/clinical operations | Complete authorized follow-through | Referral, trial-site contact, scheduling, access barriers and receipts |
| Patient/caregiver | Understand and participate | Plain-language certainty, source, goals, permission, tasks and delegated access |
| Governance/evaluation | Assess trust and readiness | User/agent actions, rights, event history, release gates and unresolved risks |

Every surface requires distinct UI states for loading, no data, not tested, conflicting, incomplete, permission denied, stale, withdrawn and failed. Evidence status must be conveyed by readable wording and accessibility labeling, not color only. Existing OI-04 already holds extensive IA research: route new UI decisions there rather than duplicate.

## 8. Model/tool architecture experiment and failure tests

Compare four task topologies: deterministic baseline; one language model with tools and verifier; specialized computational services driven by a deterministic orchestrator; and parallel agents with scoped arbitration. Measure verified source fidelity, invalid identity joins, hallucinated dates, tool output provenance, permission violations, omission/abstention, cost, completion time, reviewer attention and clinical authority violations. More agents are not automatically better. Agreement between models that used the same source is not independent evidence. Any model output is typed proposal only; domain-owned authorized review governs promotion.

Require a model/provider registry describing intended use, population, exact license (including weights), request/response retention, permissions, provenance, failures and tests. Contrast LLM functions with deterministic algorithms and specialized biomedical models; no modality inference simply because an LLM can describe it.

## 9. Technology and rights disposition

| Layer | Research candidates, NOT selections | Gating tests |
| --- | --- | --- |
| Nov-4 code | Retain existing loopback Python/SQLite and vanilla JS foundation | Commit-specific CI, reproducible binary/source, synthetic-only safety |
| Future UI | Compare React+Vite, Angular and other non-Next.js architectures | Security, accessibility, source/asset rights, maintainability, workflow fit |
| Future backend | Evaluate Python, Go, Rust, Java, C# and domain-specific combinations | Throughput, transactional integrity, team skills, deployment and license |
| Interoperability | FHIR R4/mCODE, HL7v2, DICOMweb, OMOP projection | Source fidelity, terminology rights, conformance and access controls |
| Data | Transactional persistence, immutable object archives, events, graph/search projections | Bitemporal correctness, consent, recovery, tenant boundaries |
| Clinical/biological tools | DICOM/pathology/genomics, specialized models, deterministic methods | Exact code/weights/data license and clinical qualification |
| Evidence and agent systems | Versioned sources, first-party tool contracts | Source-rights, task permissions, evidence quality and evaluation |
| Production trust | Audited identity/authorization, secrets, observability, backups, SBOM | OI-17 G1–G10 and separate clinical/security release gates |

Permission to view a public source does not imply rights to redistribute its assets or use its models commercially. OI-17 requires pinned version, dependency tree, patent terms, notices, trademarks, security, data/terminology/weights and counsel review. Do not automatically clear Medplum, Orthanc, proprietary guidelines, restricted terminologies or model weights from a package license alone.

## 10. Primary-source checks informing research

- [HL7 FHIR R4 Provenance](https://hl7.org/fhir/R4/provenance.html): an explicit origin, transform, actor and entity model supports traceability, not automatic source integrity.
- [HL7 FHIR R4 Consent](https://hl7.org/fhir/R4/consent.html): a record of purpose- and actor-scoped policy choices; its specification does not provide runtime access enforcement.
- [HL7 mCODE implementation guide](https://hl7.org/fhir/us/mcode/): oncology exchange mappings, not a replacement for the full first-party EHR.
- [DICOMweb Part 18](https://dicom.nema.org/medical/dicom/current/output/html/part18.html): imaging query/retrieval/store interfaces, not a packaged PACS.
- [ClinicalTrials.gov study basics](https://clinicaltrials.gov/study-basics): last update posted versus last verified are different; study/site information is provisional until checked.
- [FDA final CDS guidance January 2026](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/clinical-decision-support-software) and [FDA clinical CDS FAQ](https://www.fda.gov/medical-devices/software-medical-device-samd/clinical-decision-support-software-frequently-asked-questions-faqs): intended use determines classification; time-critical and imaging functions need separate analysis, not a blanket human-in-loop exemption.
- [Meta event](https://dev.meta.ai/events/global-hackathon): 9 PM ET November 4 deadline and public Indie/Startup descriptions, not a substitute for accepted official submission rules.
- [Sid research portal](https://osteosarc.com/): single-case workflow reference, not clinical proof of treatment benefit.

## 11. Three horizons and work sequencing

**Horizon 1 — Nov 4 synthetic hackathon delivery.** Keep current case/records, source versions, chronology, evidence, investigation, review, option dependencies and clinician-facing demo, verified against a single integrated main/commit. No architecture rewrite. Record actual use of Meta tools if submitted; this repository inspection did not verify a Meta model invocation. Check accepted rules, track, video and presentation constraints. Add real integration, data, models or vendor code only when rights, purpose and tests are confirmed. The published submission cutoff is November 4 at 9 PM ET, and the internal board mentions noon freeze/6 PM target. Rehearse an actual fictional case amendment and source-evidence review. Label all nonclinical functionality accurately.

**Horizon 2 — Functional, connected patient-centered research product.** Identity/consent and acquisition contracts; domain-owned versioned source and Event/Time Model; longitudinal Patient World Model; inspectable Biomedical World Model; durable questions and controlled model/tools; clinician review; task completion receipts and outcomes; cross-domain LIS/pathology/imaging/genomics/treatment contracts. Acceptance is an end-to-end fictional event that is replayable, source-linked, rights-filtered and integrated, not only correct-looking screens.

**Horizon 3 — Complete first-party Open Intelligence ecosystem.** All operational healthcare verticals, multi-institutional interoperability, validated specialized biomedical models, experimental scientific workflows, patient and research services, enterprise reliability, safety/QMS and function-specific clinical/regulatory authorization. This ambition is not collapsed into the hackathon implementation.

**Actionable work order:** (1) freeze current main/CI and review draft PR #49/#51/#48/#41 against combined regression; (2) verify actual submission rules, track and asset rights; (3) reconcile Drive archive manifest; (4) fill OI-16 domain contracts and OI-06/04/09 missing acceptance gaps; (5) model one end-to-end synthetic case and negative-path tests; (6) run deterministic-versus-agent comparison; (7) resolve architecture ADRs after evidence; (8) bring externally reviewable fictional challenge packets to qualified collaborators when ready. Align all work with existing GitHub backlog/Notion roles rather than inventing parallel epics.

## 12. Traceability and completion standard

A separate companion CSV lists 30 **candidate** requirement IDs and points to current owners, code anchors or explicit missing implementation, negative tests and horizon. Before promotion, compare against existing REQ-, ENT-, INV-, PF-, PD-, ADR-, TEST- and D1–D5 records to avoid duplicates; preserve aliases to initial identifiers. Do not assert a criterion is satisfied without (1) accepted scope, (2) exact code/rights evidence, (3) negative-path tests at relevant SHA, (4) owner review and (5) independent clinical validation or regulatory clearance when appropriate.

**Remaining open:** all audit findings not explicitly rechecked, a production artifact SBOM, valid rights for every external binary and model, independent clinical safety and validation, ownership of archived trashed files, accepted Meta track and submission requirements, final backend/frontend/agent choices, true bitemporal replay and full-product end-to-end functionality.

**This annex contains no new code or dependency changes and makes no claim of new clinical or commercial readiness.**
