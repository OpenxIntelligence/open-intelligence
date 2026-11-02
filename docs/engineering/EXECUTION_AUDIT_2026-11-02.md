# Open Intelligence — execution audit, 2 November 2026

**Outcome:** preserve the existing platform work and finish one usable patient identity → original documents → Patient World Model → permitted evidence → investigation → sourced report → human review → reassessment path. The local candidate closes one durable investigation/report handoff; it does **not** complete that MVP or establish production or clinical readiness.

**Checkpoint:** repository inventory observed at `2026-11-02T19:52:20.731Z`; main was subsequently rechecked unchanged. The combined candidate passed 341 application Python tests, 219 guarded research tests and 63 named JavaScript tests. The public metadata route/UI and safety reconciliation are implemented; hosted browser/CI evidence remains a separate gate. Safety draft #123 is published at `2d04daba74f89c6e1837b9059f05506a971ca571`; the product candidate is stacked on that reviewed prerequisite. See [combined verification](INTEGRATION_VERIFICATION_2026-11-02.md). No merge, deployment, legal clearance or clinical-use approval is claimed.

## 1. Authority and verified state

The [first-principles plan](../FIRST_PRINCIPLES_PLAN.md), [execution backlog](../EXECUTION_BACKLOG.csv), [contributor instructions](../../AGENTS.md), [data-exclusion policy](../METHOD_REFERENCE_NOT_CASE_DATA.md), and existing versioned domain/rights contracts remain the authorities. This audit reconciles evidence; the appendices are complementary research. Notion's [Identity/precedence page](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f) and [Decisions 03](https://app.notion.com/p/40a3866f77ef81e08a12fd4921e19629) record accepted decisions; document-reported implementation claims still require repository verification. See the [documentation audit](../research/DOCUMENTATION_AUDIT_2026-11-02.md) for source timestamps and conflicts.

| Evidence layer | Verified observation | Limit |
|---|---|---|
| Main | [`24519839aa8ac1ea3aff88a956349ba72798a72a`](https://github.com/OpenxIntelligence/open-intelligence/commit/24519839aa8ac1ea3aff88a956349ba72798a72a); root byte-verified 162 files and ran **236 Python tests** successfully | Python stdlib/SQLite and vanilla web; no FastAPI/PostgreSQL/React migration established |
| Branch inventory | `feat/composer-evidence-slice` equaled that main at inspection; 84 queried PR records and 86 branch records are preserved in the [inventory](../research/REPOSITORY_INVENTORY_2026-11-02.json) | An inventory snapshot is not a current-state guarantee or an exhaustive code review |
| Local combined candidate | Reused the three drafts below; added captured-context investigation → review-draft mapping, provenance, strict IDs, transactional rollback/idempotency, explicit review and stale-report propagation | Unmerged candidate; current main and the fallback remain unchanged |
| Candidate execution | **341 application Python tests passed** in 46.741 s; **219 guarded research tests** with zero skips/effect attempts; **63 named JavaScript tests passed**. [Combined evidence](INTEGRATION_VERIFICATION_2026-11-02.md) | Current combined local results; the 8 CI-boundary tests are already included in the 341 count. No live LLM or patient data used |
| Browser gate | Local Chromium prerequisite was unavailable; published candidate `1bb4ff06` subsequently passed the hosted ledger, Patient Mission and complete Composer journeys in [run 41527551989](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41527551989), plus [UI glance 41527551944](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41527551944), both attempt 1 | Verified synthetic browser behavior at that head; not comprehensive accessibility, usability or clinical validation |
| Literature and safety | Default-disabled metadata route/UI, strict public-term attestations, safe logging and request isolation; one live generic query returned three metadata records. Safety #123 disables residual acquisition and replaces identified case-derived fixtures | Metadata is not clinical evidence. Historical artifact retention remains open in #122; draft changes are not in main |

At pinned main, [synthetic application CI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510591184) and [Crossref contract CI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41510591705) succeeded. The inventory also records [a failed single-cell workflow result](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41511604578) on that SHA. Therefore “all main CI is green” is unsupported; safety/workflow reconciliation remains separate. No historical patient-bearing artifact was opened for this audit.

### Preserved drafts and historical branches

| Locally reused draft | Observed head | Preserved purpose |
|---|---|---|
| [#68](https://github.com/OpenxIntelligence/open-intelligence/pull/68) | [`7ea06ed679902a7b6c506b10ee0a6beaa83b5efc`](https://github.com/OpenxIntelligence/open-intelligence/commit/7ea06ed679902a7b6c506b10ee0a6beaa83b5efc) | Case/question/source-bound Composer context and fingerprint |
| [#91](https://github.com/OpenxIntelligence/open-intelligence/pull/91) | [`f33a71241c6cb67ddd383594961db19d003bb72e`](https://github.com/OpenxIntelligence/open-intelligence/commit/f33a71241c6cb67ddd383594961db19d003bb72e) | Input changes stale saved model hypotheses |
| [#93](https://github.com/OpenxIntelligence/open-intelligence/pull/93) | [`aa6d3f21b8d36d9949b66ed13ed34f76dabbd875`](https://github.com/OpenxIntelligence/open-intelligence/commit/aa6d3f21b8d36d9949b66ed13ed34f76dabbd875) | Existing patient/source context and rights-qualified knowledge boundary |

These were open drafts and were locally reused, then extended; they were not merged by this work. The supplied historical clinical PRs [#70](https://github.com/OpenxIntelligence/open-intelligence/pull/70), [#74](https://github.com/OpenxIntelligence/open-intelligence/pull/74), [#56](https://github.com/OpenxIntelligence/open-intelligence/pull/56), [#85](https://github.com/OpenxIntelligence/open-intelligence/pull/85), [#89](https://github.com/OpenxIntelligence/open-intelligence/pull/89), and #93 also remained open drafts. Their outbox, patient, EHR and LIS work must be reconciled rather than recreated or described as main functionality. [#95](https://github.com/OpenxIntelligence/open-intelligence/pull/95) remains a separate continuity-integration draft. The full inventory contains closed PRs and an open non-draft #48; “every PR is an open draft” would be false.

### Newer parallel integration evidence

After the initial inventory, [#130](https://github.com/OpenxIntelligence/open-intelligence/pull/130) at `2acff9ee870c8751606dec39d431ab2d678f5bb9` added an authorized clinical-to-Composer read adapter on #95. [#132](https://github.com/OpenxIntelligence/open-intelligence/pull/132) at `1e992ea1a0608962fb6f36d06ebb093c092cccf2` adds the rights-aware knowledge composition. Root independently checked [run 41514975368](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41514975368): completed success at that exact #132 head. These remain separate open drafts; that hosted result is not an independent code review, a merged domain, a production authority system or part of this candidate's local test count. Preserve their source ownership and reconcile them at the first-party domain integration gate.

### Reusing the existing World Model source view

The combined increment reuses the read-only projection from [#147](https://github.com/OpenxIntelligence/open-intelligence/pull/147), `97f197c3472df785b68cfab8794c388e20c4b798`, and inspector from [#157](https://github.com/OpenxIntelligence/open-intelligence/pull/157), `0bad696797af2ff036710eaed8dbff0427c48a59`. Both read the same canonical case/source ledger. No new patient table, clinical authority or inferred biological model is introduced.

Code review and failing regressions found a missing static-script route and an inspector listener that read the attempted case before the existing unfinished-draft guard could veto the switch. The integration fixes both. The expanded lifecycle gate requires source observations to remain clinically unreviewed after a report acknowledgment and retains historical stale reports after a replacement is reviewed. A separately reproduced Mission projection mismatch is corrected by distinguishing active unresolved review from stale history; unknown/missing question or replacement review remains actionable.

The [World Model integration receipt](WORLD_MODEL_WORKFLOW_INTEGRATION_2026-11-02.md) records source ownership and focused checks. The candidate must obtain its own combined hosted browser receipt after these changes; earlier `1bb4ff06` results do not cover them.

Broader clinical convergence remains separate: #152 and this candidate share identical Composer code, but #152/#150/#158 store changes and #154's newer export-rights checks need deliberate composition. A deterministic source-quotation export and a persisted model-hypothesis report have different contracts; preserve one source/evidence/review ledger rather than replacing either behavior. Continue existing #81/#116/#120/#121.

## 2. Accepted choices versus recommendations

**Accepted bounded H1 baseline:** Decisions 03 records Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, React, Vite and TypeScript; the stdlib/SQLite prototype remains a runnable behavior oracle/fallback. **No Next.js.** H1 excludes vector search and acute clinical alerts. This does not settle production tenancy, canonical FHIR ownership, deployment, provider contracts or all domain write-back authority. The running candidate has not migrated to that stack. The atlas's PostgreSQL 18.6 license sample is an observation, not a change to the accepted PostgreSQL 16 baseline.

**Product recommendation for validation:** make the patient/caregiver the primary entry experience, with granular delegation and an authorized clinician reviewing clinical interpretation and proposed care actions. This is a recommendation to test against the earlier operator/partner hypotheses, not an already accepted persona or market decision. The [six public narratives](../research/PATIENT_JOURNEY_RESEARCH_2026-11-02.md) suggest questions, care transitions, access constraints and caregiver workload deserve first-class support; they establish neither prevalence nor software benefit. Preserve clinician/navigator workspaces and the full first-party platform destination.

## 3. Capability map and the MVP subset

The map applies the existing plan's registered → reviewable → analyzable → research-linked support tiers. “MVP” is required scope, not completion status.

| Capability family | Minimum connected MVP | Broader destination / present gap |
|---|---|---|
| Identity, consent and delegation | One patient/case binding; visible actor, scope and access status | Local case creation exists; verified identity, consent and clinician authority do not |
| Records and extraction | Original bytes/hash/version; identity quarantine; dates and exact anchors; reviewable extraction | Current importer accepts an artificial text contract; PDF/OCR and ordinary clinical documents remain unqualified |
| Patient World Model | Longitudinal source assertions, unknown/negative/conflicting states, specimen context, goals and questions | Existing projections cover a subset; complete oncology state, goals/function and historical reconstruction remain incomplete |
| Biomedical knowledge and rights | Versioned permitted evidence; support/counterevidence; applicability and explicit missing evidence | Metadata is discovery only; broad licensed guidelines/full text and source-update operations remain open |
| Investigation and scientific tools | Bounded typed task; captured inputs, model/tool identity, citations, uncertainty and abstention | Local Composer/run/report bridge exists; evaluated reasoning, robust durable workers and tool authorization remain incomplete |
| Report, review and reassessment | Durable report, review decision and change history; new inputs require renewed review | Current acknowledgment is demo-only; credentialed, scoped accept/reject/request-more-information semantics remain open |
| Care coordination, access and trials | Owned questions/tasks and practical constraints; reviewable handoff | Referral execution, verified contacts, feasibility, recruitment and criterion-level screening require separate qualification |
| First-party EHR and pharmacy | Preserve interfaces and common identity/source authority | Draft encounter/note/order work exists separately; operational medication/orders, administration and write-back are not qualified |
| LIS, pathology and imaging | Register assets and review source reports | Laboratory custody/QC, WSI viewers, PACS and DICOM analysis are separate domain integrations |
| Genomics and other biology | Preserve specimen/assay/reference provenance and reviewable reports | Genomics, transcriptomics, single-cell/spatial, proteomics, MRD and immunology need task-specific pipelines, rights and evaluation |
| Experimental/therapeutic research | Retain a governed extension boundary | Organoids, experimental models, vaccines and gene/cell-therapy investigations are separately qualified research, not MVP care outputs |
| Enterprise, evaluation and operations | Authorization, audit, rights, safe jobs, recovery and consequential-error evaluation | Multi-organization operations, production security/regulatory qualification and clinical-outcome evidence remain open |

Sources: [existing platform plan](../FIRST_PRINCIPLES_PLAN.md), [patient/knowledge foundation](../research/PATIENT_KNOWLEDGE_REASONING_FOUNDATION.md), [existing integration/access research](../research/INTEROPERABILITY_ACCESS_RESEARCH_2026-10-31.md). Specialist platforms must enrich the same patient/source contracts rather than create competing patient masters or belief stores.

## 4. Screens, data and interfaces

Use the existing [UX 09 task map](https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f) and [#58](https://github.com/OpenxIntelligence/open-intelligence/issues/58); no parallel menu architecture is proposed.

| Surface | User job and necessary information |
|---|---|
| Overview | Confirm selected patient, authority, source cutoff, current review state, unresolved questions and next owned task |
| Journey | Read event/issued/received dates, treatments or symptoms only when recorded, contradictions and material changes |
| Record | Add authorized documents; inspect originals, extraction proposals, versions, specimen/assay context and corrections |
| Investigations | Select a question; inspect included inputs and permitted evidence; compare support/opposition; prepare a cited report |
| Care & work | Review within authority; assign follow-up, record rationale and practical constraints, export or hand off a dated artifact |

**Shared data contract:** one identity/authority owner; immutable source artifact/version/receipt; typed assertions and biological context; questions; rights-qualified evidence and applicability; task/run input snapshots; report dependencies; scoped review events; accountable tasks. Keep source claims, machine proposals, research hypotheses and clinician decisions distinct. The current CaseStore ledger is the prototype's source of truth; reconcile canonical-patient/EHR/LIS draft contracts before migration. Avoid a second clinical model hidden in the UI or agent memory.

**Current interface evidence:** main exposes local case creation and source imports, state/source readers, questions, investigations, snapshots, review acknowledgment and export. The candidate adds captured Composer context and `POST /api/cases/{case}/investigations/{id}/review-draft`, returning 201 for creation, 200 for retry and 422 for invalid/stale input. It reuses the ordinary snapshot/review ledger. Future PDF, FHIR/HL7, DICOM and biological adapters must meet the same identity, rights, provenance, correction and loss-reporting contract. The candidate also exposes `GET /api/literature/status` and `POST /api/literature/search`, enabled only through the local operator flag. It neither reads CaseStore nor persists results, sends case context, or promotes metadata into appraised evidence. See the [adapter boundary and live receipt](../research/LITERATURE_ADAPTER_BOUNDARY.md).

**Security and data boundary:** independently authored fictional fixtures only; no Sid Sijbrandij records, images, molecular files, catalogs or patient-derived synthetic data. Public narratives remain method discovery, never training/evaluation records. Before real use, prove case/tenant access, delegation and revocation across sources/search/jobs/export; isolate document parsers; treat retrieved text as untrusted; gate model egress and retention; protect credentials/logs; test backup/restore and incidents. Current loopback/Host checks and demo labels do not establish production authorization or clinical safety. See [data policy](../METHOD_REFERENCE_NOT_CASE_DATA.md), [rights broker](../RIGHTS_BROKER.md) and backlog OI-012–014.

## 5. Acceptance and delivery order

1. **Reconcile and freeze one candidate.** Preserve reviewed upstream changes, record the exact combined commit and run root's final Python/JavaScript/browser/CI gates. Preserve the completed bounded metadata and safety reviews, then verify the published combined tree in hosted CI. A synthetic application pass does not clear every workflow, dependency or historical artifact.
2. **Close identity → documents → context.** Exercise actual case creation and upload, then a bounded extraction contract; confirm original bytes, identity conflicts, exact anchors, chronology and uncertainty. Introduce the accepted H1 stack through compatibility/migration tests while retaining the runnable oracle. A seeded interface is not an ingestion demonstration.
3. **Close permitted evidence → report → authorized review.** Use one rights-qualified frozen item if live content is not yet qualified. Show support, counterevidence, applicability and abstention. Persist the run/report/review relationship and actor scope. Legacy runs without captured context require rerun; preparation must never mark a question reviewed.
4. **Prove the second time point and usability.** Create Alpha, import three original fictional records, investigate, prepare/export/review, then amend a source or evidence item. Preserve the historical review; stale affected work; prepare a new run/report; switch to Beta without leakage. Include concurrent retries/rollback, source changes during model work, revoked permission, unknown versus negative, wrong specimen, unsupported citation, retrieval failure, keyboard operation and zoom. Measure correction and review burden.
5. **Qualify expansion separately.** Complete governed identity/security and independent workflow evaluation before real-data or clinical release. Extend first-party domains and specialist modalities only with a named use, rights closure, reproducibility and accountable review; preserve the broad ambition without declaring those stages complete.

The ordinary manual-draft path retains its existing minimum one source and maximum 50 source/50 evidence-assessment dependencies. The internal generated-report path preserves the complete canonical dependency set, including more than 50 items, and permits a source-free report only for a genuine abstention with no accepted claims. Generated text is bounded at 65,536 characters with no silent truncation. Real clinician credentials, prompt/weight attestations, production jobs, full ingestion and clinical adjudication remain gaps. These limits are implementation facts, not final product requirements.

## 6. Research questions and existing owners

Roles below are proposed responsibility assignments, not claims that named people accepted work. Keep decisions and acceptance evidence on existing issues/backlog rows; do not create a duplicate issue register.

| Question requiring evidence | Responsible role | Existing home |
|---|---|---|
| Does patient-first entry reduce explanation and coordination burden, and who owns follow-up? | Product research lead with patient, caregiver and clinical reviewers | [#128](https://github.com/OpenxIntelligence/open-intelligence/issues/128), [#58](https://github.com/OpenxIntelligence/open-intelligence/issues/58); OI-001–002 |
| Which patient/source/authority contract owns cross-domain identity and corrections? | Domain architect and privacy/security reviewer | [#81](https://github.com/OpenxIntelligence/open-intelligence/issues/81), [#87](https://github.com/OpenxIntelligence/open-intelligence/issues/87); OI-005–007, OI-013 |
| Which document type and extractor preserve exact spans with acceptable correction effort? | Ingestion owner and clinical adjudicator | [#92](https://github.com/OpenxIntelligence/open-intelligence/issues/92); OI-006, OI-011 |
| Which exact source content may be stored, embedded, processed and displayed commercially? | Evidence owner and rights/legal reviewer | [#59](https://github.com/OpenxIntelligence/open-intelligence/issues/59), [#92](https://github.com/OpenxIntelligence/open-intelligence/issues/92); OI-004, OI-008 and existing commercial-rights register |
| Does bounded model assistance improve the manual baseline without hiding omissions or counterevidence? | AI/evaluation owner and independent adjudicators | [#92](https://github.com/OpenxIntelligence/open-intelligence/issues/92); OI-003, OI-011, OI-014 |
| Can users inspect, correct and review without excessive navigation or alert burden? | UX/accessibility owner and intended users | [#58](https://github.com/OpenxIntelligence/open-intelligence/issues/58), [#81](https://github.com/OpenxIntelligence/open-intelligence/issues/81); OI-007, OI-009–010 |
| Are excluded acquisition paths retired and releases reproducibly inventoried? | Security/CI owner and release/rights reviewer | [#122](https://github.com/OpenxIntelligence/open-intelligence/issues/122), [#59](https://github.com/OpenxIntelligence/open-intelligence/issues/59); OI-004, OI-013, OI-018 |

The wider WS-00–15 roadmap already uses [#96](https://github.com/OpenxIntelligence/open-intelligence/issues/96) through [#111](https://github.com/OpenxIntelligence/open-intelligence/issues/111); [Roadmap 12](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3) and the existing backlog own dispatch. The 16 malformed workstream URLs and four stale stack/gate statements in OI-27 were corrected in place; read-back confirmed all 20 replacements. Preserve the canonical dispatch owners.

## 7. Preserved research and small documentation follow-ups

| Dated appendix | Evidence and scope |
|---|---|
| [Technology atlas](../research/TECHNOLOGY_ATLAS_VERIFICATION_2026-11-02.md) and [JSON receipts](../research/TECHNOLOGY_ATLAS_VERIFICATION_2026-11-02.json) | 25 source-license observations, exact commits/license blobs, candidate dispositions and material gaps; supplements [#125](https://github.com/OpenxIntelligence/open-intelligence/pull/125), [#127](https://github.com/OpenxIntelligence/open-intelligence/pull/127) and [#66](https://github.com/OpenxIntelligence/open-intelligence/pull/66) |
| [Biomedical access atlas](../research/BIOMEDICAL_ACCESS_ATLAS_2026-11-02.md) | Primary-source access/rights evidence, API versus content distinctions, explicit production-documentation gaps and held sources |
| [Patient journey research](../research/PATIENT_JOURNEY_RESEARCH_2026-11-02.md) | Six public accounts, source links, limitations and product hypotheses; no patient files or derived test cases |
| [Documentation audit](../research/DOCUMENTATION_AUDIT_2026-11-02.md) | Selected Notion/Drive authorities, observed dates, H1 decisions, stale claims and precise suggested edits |
| [Repository inventory](../research/REPOSITORY_INVENTORY_2026-11-02.json) | Main/branch/PR/CI metadata snapshot; raw JSON preserved unchanged |

All software and source-rights recommendations remain provisional legal/release review. A source-license file does not establish transitive code/native-library/asset/weight/dataset/service clearance. No resolved transitive SBOM or complete commercial clearance was established. NCCN/ASCO/ESMO and other restricted content remain held without applicable permission; no unverified API is assumed. Public metadata is not appraised clinical evidence. Follow the source-specific receipts rather than extrapolating a permissive label across a corpus.

**Suggested next edits, not made here:** update README's last-verified-main block and link this audit with exact final evidence; scope AGENTS' “stack undecided” sentence to production/open boundaries while recording the accepted H1/no-Next decision; label older IMPLEMENTATION_STATUS and first-principles implementation statements as historical checkpoints. Preserve their history, full vision, data policy and existing decision owners. This documentation pass changes no README, AGENTS, code, tests, web files, remote issues or external documents.
