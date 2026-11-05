# Open Intelligence — oncology and research platform audit

Assessment: **4 November 2026**. Repository: **OpenxIntelligence/open-intelligence**.

## Decision and scope

**The repository provides a substantial synthetic record, provenance, investigation and follow-through foundation. It is not yet a complete oncology EHR, clinically qualified AI assistant, or integrated bioinformatics execution platform.** Preserve the working owners and converge existing domain work before creating additional modules.

This is an initial source-grounded audit and one implemented P0 repair under the supplied 22-phase mandate. It is **not completion of all 22 phases**, an exhaustive semantic review of every historical draft, or a production-readiness certification. No broad category below is labelled FULLY IMPLEMENTED. Narrow workflows can work while the requested domain remains partial.

The audit captured **501 tracked files on main**, **453 remote refs**, and **126 distinct runtime Python paths across those refs**. The [inventory](source-inventory.json) records immutable main blobs, branch heads, runtime paths, top-level symbols, route decorators and SQL declarations. The entire main tree and branch path inventories were enumerated; detailed inspection concentrated on canonical identity, source custody, World Model, authority, clinical/LIS donors, FHIR laboratory, imaging, scientific probes and active convergence. Inventory is not equivalent to executing every branch. SQL/route extraction is heuristic, not a live database schema dump.

The connected account listed the product repository and three other repositories: Coding-Agent-Library, Coding-Agent-Skills and legal-agent. They were excluded from product implementation claims; their names do not establish additional oncology services. Other accounts or unlisted repositories have not been exhaustively searched.

**Subsequent integration.** [PR #481](https://github.com/OpenxIntelligence/open-intelligence/pull/481) has since merged into main at [62e218e](https://github.com/OpenxIntelligence/open-intelligence/commit/62e218e1e2bd6996bb126fcc1ea956fcf18199e6). The inventory and scores below describe the original audit snapshot. [PR #492](https://github.com/OpenxIntelligence/open-intelligence/pull/492) records verification of the access-policy repair against the consolidated application.

### Frozen implementation states

| State | Exact reference | Interpretation |
|---|---|---|
| Main tested here | `a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709` | Includes the SQLite reference and FastAPI/PostgreSQL/React H1 code. Older prose saying H1 is wholly absent from main is stale. |
| Consolidation candidate | [#481](https://github.com/OpenxIntelligence/open-intelligence/pull/481), `02f920c40959d26937df0f737e17e5392d041d26` | Active unmerged patient/demo convergence when inspected; not silently adopted into this repair. |
| FHIR laboratory custody | [#469](https://github.com/OpenxIntelligence/open-intelligence/pull/469), `8ff6e9e5a0389a1142ca479a6705c599cbda88e7` | Existing bounded native FHIR laboratory owner; do not duplicate. |
| Laboratory/manual migration convergence | [#471](https://github.com/OpenxIntelligence/open-intelligence/pull/471), `95bf73d23172c15bcf326183494030e6597ed449` | Existing join of published migrations; must preserve populated histories. |
| Laboratory UI convergence | [#482](https://github.com/OpenxIntelligence/open-intelligence/pull/482), `3217b90f86007f0f13a95850cfefa65128265ec3` | Existing laboratory workspace/reading continuation. |
| Clinical encounter PostgreSQL parity | [#301](https://github.com/OpenxIntelligence/open-intelligence/pull/301), `611b86e3f0fefd61d0937216141e05262d2b55a9` | Separate clinical owner and adapter; not proof of an integrated EHR. |
| Local semantic proposal harness | [#476](https://github.com/OpenxIntelligence/open-intelligence/pull/476), `4f1c613abe1f90c185e1f2f9edb816e3bf81fa3c` | Research-only metadata mapping and scoring; not clinical reasoning or bioinformatics execution. |

At inspection, #481's React, reference, Crossref and UI workflows reported success; its API workflow was still running. Those external run statuses are not locally reproduced evidence or artifact verification for this audit. Head movement after this snapshot does not retroactively update these findings. The repair was subsequently reconciled with main `840b41c31f6902fe89b7e714dff038f42ca84a74` (agentic-infrastructure documentation only). The merge was clean; no additional runtime, test, dependency or migration changes were introduced.

## Evidence index: owners, storage, API, UI and tests

Unless a donor is named, paths refer to frozen main above. Use `https://github.com/OpenxIntelligence/open-intelligence/blob/a5a5482f815ceb3c322cdfb32ab8b18c1c0e8709/` plus the path for immutable main evidence.

| ID | Source and storage | API / frontend | Tests and limitations |
|---|---|---|---|
| E01 | `src/open_intelligence/patient_registry.py`, `postgres_registry.py`; `identity.identity_patients`, creation receipts/events; `apps/api/migrations/versions/0002_patient_registry.py` | `oi_api/patients.py`: POST `/v1/patients`, GET `/v1/patients/{patient_id}`; `apps/web/src/registry-client.ts` | `apps/api/tests/test_patients.py`; fictional identity, not MPI/proofing/consent. |
| E02 | `oi_api/case_bindings.py`, `sources.py`, `source_integrity.py`; `coordination.patient_case_bindings`, `clinical_source.source_versions`, assertions/quarantine; migrations 0004/0005 | Patient/case `/sources`, originals, case bindings; `source-intake-view.tsx`, `world-model-view.tsx` | Source, intake and original-response authority suites; original bytes, scope, hashes, versions, retries. |
| E03 | `oi_api/source_world_model.py`; read-only projection of E02, no new ledger | GET patient/case `/world-model`; `world-model-view.tsx` | `test_source_world_model.py`, `test_projection_authority.py`; reported states are not clinical diagnoses. |
| E04 | `source_questions.py`, `question_review_returns.py`, `question_source_review_packet.py`, `source_brief.py`; `investigation.source_questions`, review receipts | Questions, source-review-packet, return-for-verification and brief routes; `source-question-panel.tsx` | Question/packet/review/brief suites and browser scripts; operational verification is not clinician signoff. |
| E05 | `question_followthrough.py`, `followthrough_routes.py`; coordination task/event tables | Question `/followthrough`, transitions; `followthrough-panel.tsx` | Follow-through API/client/recovery tests; records ownership and state, does not send referrals or book care. |
| E06 | `authored_evidence.py`, `evidence_catalog.py`, `question_evidence.py`, `evidence_report.py`; evidence versions, links, assessments, reports, rights/command tables | Evidence search/import/assessment/report routes; `authored-evidence-panel.tsx` | Evidence authority, original, report and restore tests; most material is fictional or metadata-only. |
| E07 | `src/open_intelligence/store.py`, `timeline.py`, `provenance.py`, `care_records.py`, `patient_access.py`, `scoped_review.py` | Reference `__main__.py`, `web/app.js`; patient notes/goals, visits, second opinions, survivorship, options | 737 reference tests passed here; reference contracts are not automatically migrated into H1. |
| E08 | `src/open_intelligence/investigation.py`, `citation_verifier.py`, `synthesis.py`, `rights.py`; model run/snapshot and rights state | Reference investigation/synthesis paths; H1 Composer is source preflight | Test fixtures and mock specialist adapter; no representative clinical AI evaluation or H1 clinical model execution shown. |
| E09 | Clinical donors: `clinical_encounters.py`, `postgres_encounters.py`, `clinical_lab.py`, `clinical_lab_bridge.py`, `platform_events.py` | Host-authorized domain APIs; encounter/note, LIS and event donors | SQLite and PostgreSQL parity work exists; no unified prescribing/administration/EHR workflow established here. |
| E10 | #469: `oi_api/laboratory_fhir_r4.py`, `laboratory_fhir_store.py`, `laboratory_fhir_routes.py`; FHIR laboratory source/observation/command tables | Bounded laboratory preview/import and originals; #472/#482 laboratory UI | Parser, real-PG and HTTP tests in donor. One Patient, one Specimen, 1–16 supported observations; not generic FHIR/mCODE conformance. |
| E11 | #481 and image donors: `oi_api/images.py`, `dicom_integrity.py`, `archive_socket.py` | Source-owned original-image custody and private archive transport | Bounded DICOM/source/permission/recovery tests exist; no qualified CT/MRI/PET interpretation, lesion tracking or RECIST demonstrated. |
| E12 | `tools/research/rna_expression_probe.py`, `single_cell_probe.py`, `gdc_projection_probe.py`, `trial_screening_probe.py`, `public_evidence_probe.py` | Offline/probe entry points, not connected research workspace | 191 research tests passed, 13 skipped locally. GCT parsing/descriptive comparison and bounded AnnData helpers do not establish RNA-seq/scRNA-seq pipelines. |
| E13 | #476: `tools/semantic_local_model_runner.py`, `semantic_model_scorer.py`, challenge fixtures | Loopback local model adapter, no clinical database/tools | Separate mapping challenge/scorer; no SQL execution or clinical truth promotion. Not rerun here. |
| E14 | `oi_api/access.py`, `request_limits.py`, `config.py`, `database.py`; append-only owner receipts/events | Deny-by-default API, fixture grants, loopback host, bounded requests | Authority/encoding/revocation tests; production identity, encryption infrastructure and clinical consent qualification remain open. |
| E15 | `apps/api/requirements.lock`, dependency inventory/notices, `apps/web/package-lock.json`, Compose, `.github/workflows` | FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL 16 and React/Vite/TypeScript | Hashed dependencies and test/recovery jobs; no production deployment/HA/SLO qualification shown. |

The H1 frontend contains real API-backed controls for its bounded implemented workflows. Disabled controls awaiting permissions or current data are **not by themselves UI PLACEHOLDERS**. H1 Composer preflight prepares source context but does not execute the promised clinical assistant. No substantiated imaging AI, chemotherapy administration, registry submission or omics-job UI was found to classify as functional.

## Requested capability crosswalk

Statuses use the requested vocabulary. PARTIALLY IMPLEMENTED includes working pieces without the complete requested workflow. BACKEND ONLY describes isolated backend/domain utilities. MISSING means no meaningful dedicated implementation was located in the inspected runtime/path inventory; this is not a proof about every unexamined file version. DOCUMENTATION ONLY records plans without executable support. UNVERIFIED is used where code exists but execution was not demonstrated here. There are **no FULLY IMPLEMENTED domain claims**.

| Phase / requested capabilities | Classification | Evidence | Specific remaining work |
|---|---|---|---|
| 2 — Longitudinal patient record, cancer history and patient-specific timeline | PARTIALLY IMPLEMENTED | E01–03, E07 | Consolidated typed oncology episodes and complete H1 chart; original assertions alone are insufficient. |
| 2 — Multiple independent primaries, secondary malignancies, recurrence, metastases, progression | MISSING dedicated domain | E03 holds literal source findings only | Stable tumor/episode/lesion identities, explicit relationships, dates, revisions and clinician attribution. Never infer metastasis from two diagnosis labels. |
| 2 — Family/genetic history, comorbidities, allergies, current/prior medications, surgeries and previous cancer treatments | PARTIALLY IMPLEMENTED as source/notes; typed workflows MISSING | E02/E07/E09 | Dedicated structured history, reconciled status and provenance; medication state must distinguish prescribed/dispensed/administered/reported. |
| 2 — Survivorship and follow-up | PARTIALLY IMPLEMENTED | E05/E07; survivorship tables and tests | H1 convergence, clinically authored plan elements, real care handoffs and outcome tracking. |
| 2 — Historical versions, timestamps, source references and authorship | PARTIALLY IMPLEMENTED | E02/E04/E07 | Strong bounded source history; not universal across future clinical objects or verified clinician identity. |
| 3 — Pathology PDFs, ordinary documents, source passages and clinician verification | PARTIALLY IMPLEMENTED | Main text/manual intake; E10/E11 document donors | Adopt reviewed PDF/text owner; exact page/span and specimen/tumor linkage; transcription review must stay separate from clinical signout. |
| 3 — Scanned documents/OCR and AI extraction | MISSING qualified workflow | E08; extraction research #466 | OCR/source coordinate contract, model provenance/confidence, negation/temporality, abstention and independently adjudicated extraction evidence. |
| 3 — Histology, tumor classification/grade; ER/PR/HER2/Ki-67/PD-L1; EGFR/ALK/ROS1/BRAF/KRAS; MSI/MMR/BRCA1/BRCA2 and other alterations | PARTIALLY IMPLEMENTED only as literal findings | E02/E03/E10 | Typed assay/specimen/method units, genomic notation/build, relevant dates, source-specific interpretation and reviewed normalization. A generic finding key is not a biomarker engine. |
| 3 — Confirmed/suspected/pending/negative/indeterminate; missing markers; contradictions | PARTIALLY IMPLEMENTED | E03 explicit source states and narrow disagreement grouping | Confirmed and suspected clinical assertions; tumor-specific completeness policy; same-assay comparability and cross-report adjudication. Missing is never negative. |
| 4 — DICOM/DICOMweb, original image and radiology report links | PARTIALLY IMPLEMENTED in donors | E11/E02 | Current combined acceptance, supported transfer syntaxes, study/series/index lifecycle and production archive authorization. |
| 4 — Orthanc/OHIF and CT/MRI/PET clinical viewer workflows | DOCUMENTATION ONLY / UNVERIFIED integration | E11 archive experiments, E15 | Specific approved versions/rights; actual viewer and archive access/identity tests. No installed integration claimed. |
| 4 — Tumor measurements, primary/metastatic lesion tracking, serial comparisons, progression and RECIST 1.1 | MISSING | E11 is original custody | Lesion identities and measurement series; modality-specific QA, algorithm evidence, reviewer workflow and licensed/reference rules as applicable. |
| 5 — AJCC TNM, clinical/pathological/histology-specific stage, grouping, restaging and edition history | MISSING | Sources may contain stage text | Governed versioned rule corpus; evidence for T/N/M; unresolved states; attributable clinician confirmation. No stage inferred from a report string. |
| 6 — Chemotherapy, immunotherapy, targeted/hormonal/radiation therapies, regimens/cycles/scheduling/infusions/administration | MISSING operational treatment engine | E07 history/options; E09 generic encounters/LIS | Prescription/order/plan/administration owners, cycle state, facilities, reconciliation, inventory and authorized clinical execution. |
| 6 — Dose changes, interruptions, discontinuation/reasons, adverse events/toxicity and response | PARTIALLY IMPLEMENTED as history only | E02/E07 | Structured treatment exposure, dose basis, toxicity grading, response provenance and reviewed longitudinal relations. |
| 6 — Allergy/interactions/dose/protocol checks and clinician authorization | MISSING qualified medication safety | E14 generic authorization | Approved knowledge/rules, dose-unit validation, interaction coverage and clinician identity; no autonomous treatment authorization. |
| 7 — Patient-contextual summaries, encounter summaries, timeline construction and source Q&A | PARTIALLY IMPLEMENTED | E03/E04/E08 | H1 authorized retrieval-to-model-to-reviewed-answer path; current/historical and uncertainty preservation; source/date citations; measured accuracy. |
| 7 — Access-controlled RAG, contradictions, missing information, hallucination controls | PARTIALLY IMPLEMENTED | E08/E14; deterministic source projections | Retrieval isolation and revocation during execution, evidence support checks, source-grounded abstention and prospective evaluation. No vector database is required merely to meet the label. |
| 8 — Tumor-board presentation, multidisciplinary discussion, recommendations, clinician ownership and follow-up | PARTIALLY IMPLEMENTED preparation primitives | E04–07/E09 | Meeting/case ownership, role-qualified discussion/decisions/dissent and real responsibility/closure workflow. A brief is not a tumor board. |
| 9 — ClinicalTrials.gov discovery and criteria analysis | BACKEND ONLY research; product matching MISSING | E12, fictional discovery E07 | Live versioned discovery adapter, criterion-level known/unknown/contradicted evidence, site freshness and research coordinator review. |
| 9 — Cancer/biomarker/stage/treatment filtering, locations/recruitment and match explanations | PARTIALLY IMPLEMENTED research profiles only | `trial_screening_probe.py` | Full patient-context matching remains absent; minimum-age helper is not eligibility. No enrollment action. |
| 10 — NAACCR cancer registry abstraction, validation and exports | MISSING | No dedicated runtime found | Versioned site/histology/stage/treatment/outcomes mapping, reporting jurisdiction, validation edits, export receipts and reporting authority. |
| 11 — FHIR and mCODE | PARTIALLY IMPLEMENTED FHIR subset; mCODE conformance MISSING | E10; `fhir_kernel.py` donor | Profiles/value sets and pinned packages, round-trip/loss reports, conformance suite; a JSON admission kernel is not a FHIR server. |
| 11 — SMART on FHIR, HL7 v2 and HAPI/equivalent | DOCUMENTATION ONLY for integrated deployment | Existing planning and E15 | Actual OAuth launch/scopes, endpoints, replay/ACK/idempotency, terminology and qualified patient matching. |
| 11 — SNOMED CT/LOINC/RxNorm/ICD-10-CM/NCIt/HGVS | PARTIALLY IMPLEMENTED literal codes/research only | E10/E12 | Versioned terminology service/mapping, original preservation, licensing jurisdiction and ambiguous/unmapped states. |
| 12A — FASTQ/BAM/CRAM/VCF/gVCF/BED/GFF/GTF/FASTA/annotation ingest | MISSING operational pipelines | E07 biological asset metadata | Original storage, sample consent/identity, build/reference checks, format validators, large-object and resumable ingest. |
| 12A — Laboratory harmonization, normalization/build conversion, QC/batch effects and transformation provenance | PARTIALLY IMPLEMENTED metadata/probes | E07/E12 | Reproducible jobs and validated transformations; retain original coordinates/build; explicit incompatibility and transformation losses. |
| 12A — AI Python generation, test and execution environment | MISSING governed executor | E13 only maps metadata | Isolated runner, resource/network/file limits, versioned code/input/output manifests, tests and human release gates. Never execute a model's arbitrary code in the clinical API. |
| 12B — Variant calling/annotation, somatic/germline, tumor-normal analysis | MISSING | No integrated DNA pipeline found | Qualified tools, reference bundles, sample pairing, QC, truth sets, reproducibility and result provenance. |
| 12C — Bulk RNA QC/quantification/normalization/differential expression/pathways/signatures/visualization | BACKEND ONLY limited helpers | E12 GCT parser and descriptive comparisons | FASTQ-to-expression, replication/design/batch model, DE pipeline, enrichment reference version and reproducible reports. Correlation is not differential expression or causality. |
| 12D — Single-cell ingest/QC/normalization/dimensional reduction/clustering/annotation/DE/TME/immune/cell-state comparison | BACKEND ONLY limited helpers; execution partly UNVERIFIED locally | E12 bounded AnnData/CSR helpers | End-to-end Scanpy/Seurat/scVI or justified alternative, QC decisions, annotation uncertainty, batch models, interactive workspace and reproducible report. |
| 12E/F — Multi-omics, CNV/epigenomics/proteomics, tumor-normal and public-reference comparisons | PARTIALLY IMPLEMENTED metadata only | E07/E12 | Shared sample/time/build ontology; modality-specific normalization; paired-vs-population controls; no automatic cross-platform biological equivalence. |
| 13A — Therapeutic target ranking by alterations/expression/pathways/specificity/evidence/druggability | DOCUMENTATION ONLY beyond manual hypotheses | E07 options/biological explanation | Validated scoring inputs, uncertainty/sensitivity, normal-tissue counterevidence and experimental validation plan. |
| 13B — PubMed/Europe PMC/OpenAlex/Semantic Scholar/Crossref retrieval and claim synthesis | PARTIALLY IMPLEMENTED | E06/E08/E12; DOI metadata adapter | Rights-qualified full evidence, retractions/corrections, claim-level support, relevance and evidence grading. Metadata is not evidence of efficacy. |
| 13C — Drug-target knowledge, mechanism research, combinations | DOCUMENTATION ONLY / isolated research leads | E07/E12 | Qualified knowledge adapters, source/version/rights, contextual evidence and computational-vs-clinical separation. |
| 13D — Somatic neoantigens, HLA, peptide-MHC binding, candidate prioritization/expression/immune evidence, mRNA vaccine research | MISSING computational workflow | Architecture only | Research-scoped sample/job/results, approved tools/assets, reproducibility and experimental review. No vaccine efficacy/design/manufacture capability established. |
| 14 — External research resources | PARTIALLY IMPLEMENTED research metadata; most product adapters MISSING | E12 and resource register below | Per-resource permissions, provenance, format/loss validation, patient/research separation and exact data access. |
| 15 — Clinical NLP across progress/consult/pathology/radiology/discharge/operative/molecular/chemotherapy/tumor-board documents | PARTIALLY IMPLEMENTED intake; NLP MISSING qualified workflow | E02/E08/document donors | Classification/extraction, negation/assertion/time/uncertainty models, exact anchors and clinician-reviewed gold sets. MedCAT/scispaCy are candidates, not installed facts. |
| 16 — Synthetic generation, gold standards, extraction/staging/timeline/assertion/negation/contradiction/hallucination evaluation | PARTIALLY IMPLEMENTED | E07/E08/E12/E13, `validation/`, `docs/evaluation/` | Independent oncology adjudication, representative held-out sets, prespecified thresholds, error severity and model promotion policy. Tests do not equal clinical benchmarks. |
| 16 — MLflow/DeepEval/Ragas, model monitoring/versioning | PARTIALLY IMPLEMENTED manifests; named services DOCUMENTATION ONLY | E08/E13/E15 | Compare tooling only against actual measurement/workflow needs; no deployment or integration claimed. |
| 17 — Auth, authorization, scope, audit, AI permissions and human authority | PARTIALLY IMPLEMENTED synthetic boundary | E14 and repair below | Production IdP/session security, verified roles, consent/delegation/revocation, immutable audit retention and validated clinical approvals. |
| 17 — Encryption at rest/in transit, secure deployment, HIPAA safeguards, retention/deletion | UNVERIFIED deployment controls / missing qualification | E15 local-only Compose | Threat model, actual host/object/database keys/TLS, recovery/SLO/incident evidence, legal/data-role review and verifiable deletion. Local loopback development is not production transport encryption. |
| 17 — Clinical/research separation and genomic privacy | PARTIALLY IMPLEMENTED purpose/rights boundaries | E06/E08/E12/E14 | Independent research projections, access agreements, re-identification controls, lineage and governed clinical promotion. |
| 18 — Radiation and infusion operations | MISSING | E07 literal history only | Specialized planning/order/administration, safety validation and clinical authority. |
| 18 — PROs/ECOG/pain/symptoms/QOL/toxicity | PARTIALLY IMPLEMENTED source/notes; dedicated instruments MISSING | E02/E07/E10 | Versioned validated instruments, longitudinal measures, review and escalation ownership. |
| 18 — Prior authorization/scheduling/communications/population health | MISSING integrated operations | E05/E07 internal tasks | External services, recipients/delivery receipts, benefits/status rules, institutional agreements and privacy-aware analytics. |
| 18 — Patient portal and survivorship | PARTIALLY IMPLEMENTED synthetic workspace | E05/E07 | Real accounts, accessibility qualification, clinical plan/signoff, consent and authorized communications. |
| 19 — Modularity, persistence, migration, APIs, tests and local deployment | PARTIALLY IMPLEMENTED | E15 | Converge owners; measured service extraction; production workload/recovery/security verification. |

## Architecture assessment and integration choices

Retain the accepted Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript direction. Main already contains both H1 and the Python/SQLite reference. They have overlapping capabilities with different maturity; do not create another frontend or patient database. Next.js is excluded by the accepted project decision.

Keep clinical records, AI proposals, research samples/jobs and therapeutic hypotheses as separate functional domains sharing canonical identity, provenance, permission, terminology and event contracts. This does not require a separately deployed service for every engine. Isolate scientific execution when workload, credentials or untrusted code require it; split other services only for a demonstrated operational reason.

| Candidate set requested | Current disposition | Acceptance needed before adoption |
|---|---|---|
| PostgreSQL/FastAPI/Python/React/Vite/Docker | Retain existing implementation and locks | Combined migration, recovery, isolation and actual UI/API acceptance at the chosen head. |
| pgvector/vector DB | Not added | Demonstrate retrieval gain over existing structured/lexical source access and enforce identical authorization/deletion. |
| HAPI FHIR/equivalent, FHIR/mCODE/SMART/HL7 | Extend the existing interoperability owner; no replacement approved | Exact supported profiles, terminology rights, authorization, round-trip losses and conformance. |
| Orthanc/OHIF/DICOMweb | Evaluate behind existing image/source contracts; not installed here | Qualified IDs, direct archive isolation, viewer access, formats, performance, versions/rights and restore. |
| MinIO/compatible object storage | Candidate for large original artifacts | Checksums/version retention, scoped credentials, access revocation, backup/restore and exact licensing review. |
| Nextflow/Snakemake | Compare one bounded research pipeline | Reproducible container/reference/input/output manifests, retries, cancellation and isolation. No competing scheduler yet. |
| Kubernetes/GPU infrastructure | Defer until workload evidence | Measured utilization, scheduling/isolation, operational capacity and security. |
| GATK/BCFtools/SAMtools/VEP/SnpEff/ANNOVAR | Not integrated as production analysis | Versioned build/annotation assets, licenses per component, synthetic/reference truth tests and sample identity. |
| STAR/Salmon/HISAT2/DESeq2/edgeR/limma/GSEA | Not integrated as complete RNA workflow | Experimental-design and normalization contracts; reference/geneset rights; truth/reference comparisons and reproducibility. |
| Scanpy/Seurat/AnnData/Cell Ranger/scVI-tools/SingleR | Limited AnnData helpers only | Full pipeline, resource bounds, model/reference licenses, uncertainty and independent scientific QA. |
| MedCAT/scispaCy/OCR/LLM extraction | Evaluate against manual extraction and existing baseline #466 | Exact model/data rights, source anchors, assertion/time/negation errors and correction burden. |
| MLflow/DeepEval/Ragas | Measurement tooling candidates | Prespecified outcomes and fit with existing result receipts; avoid treating a framework metric as clinical validation. |
| Open Targets/ChEMBL/DrugBank/PubChem/BindingDB/DGIdb/CIViC | Knowledge adapter candidates; isolated probes are not platform integration | Source/version/rights, contradictory evidence, disease/context fidelity, current-vs-historical and withdrawal. |
| OptiType/arcasHLA/NetMHCpan/IEDB/pVACtools | Research-only candidates; not integrated | Tool/weights/reference rights, HLA/sample identity, independently validated predictions and strict clinical separation. |

No third-party dependency, model, guideline corpus or dataset was added by this increment. None of the candidate names above constitutes a completed license/security evaluation. ANNOVAR, DrugBank, NetMHCpan, proprietary guidelines, code sets and restricted datasets remain specifically subject to exact use/asset review; public visibility is not permission.

### External-resource inventory

This is an integration status register. Unless marked checked, current API/format/access terms were not independently revalidated in this increment and remain UNVERIFIED. It does not authorize downloading patient data.

| Resource | Observed implementation / import-export status | Access, format and next gate |
|---|---|---|
| Synthea | No generator-to-H1 adapter verified; independently authored fixtures already exist | Evaluate generated FHIR against current source contracts; synthetic origin is not an accuracy benchmark. Current release/license not revalidated. |
| PhysioNet | No governed dataset import/export established | Official FAQ distinguishes open and credentialed datasets; inspect each dataset's license, training/DUA and model-use rules. [R4] |
| MIMIC-IV | No authorized ingestion established | Official dataset page requires credentialing, training and DUA for the inspected release; no entitlement inferred. No download performed. [R5] |
| MIMIC-IV-Note | No authorized note integration established | Separate release/DUA/rights and NLP corpus governance remain unverified; do not assume MIMIC-IV access automatically settles all uses. |
| ClinicalTrials.gov | Registry profiling research and fictional trial records; no integrated patient matcher/export | REST API v2 is documented by NLM; require retained version/date, criterion-level evidence and current site status. [R2] |
| CIViC | Research/knowledge leads; no complete patient-linked import/export qualified | Recheck exact API/schema/data license, clinical significance/context and update handling. |
| ClinVar | No qualified clinical variant interpretation adapter found | Recheck API/file release, assembly, allele identity, condition, review/conflict and submission dates. |
| GDC | Bounded projection probe; no end-to-end patient research workflow | Official portal/API/transfer tooling; open and controlled data differ. Controlled access requires authorization/authentication described by NCI. [R3] |
| TCGA | Public-reference research lead, not a unified import pipeline | Preserve project/sample/aliquot/reference provenance; check access by artifact through GDC. [R3] |
| GTEx | No qualified production import/export | Tissue/reference comparability, consent/access and exact artifact license unverified. |
| SEER | No registry analytics/import/export integration | Dataset agreement, release, allowed analysis and reporting relationship unverified; not synonymous with NAACCR export. |
| cBioPortal | No qualified API integration | Instance-specific schema/terms and underlying dataset rights unverified. |
| Human Cell Atlas | No connected single-cell reference workflow | Dataset-level consent/access, matrices/metadata, batch/context compatibility and attribution unverified. |

## Evidence scorecard (0–100)

These are **coarse engineering evidence bands, not percentages complete, clinical safety scores or release approval**. 0 = no implementation evidence; 10 = requirements/metadata only; 20 = executable isolated helper or source representation; 40 = persistent bounded domain primitives; 60 = demonstrated complete synthetic domain journey; 80 = broad requested domain integration plus independent evaluation; 100 = all declared domain acceptance and intended-use/release gates satisfied. Each score describes the strongest verified bounded foundation and is deliberately capped below full-domain acceptance. Draft-only additions do not raise the main baseline score.

| Requested category | Score | Reason / dominant blocker |
|---|---:|---|
| Oncology EHR | 40 | Durable source/question/care primitives; complete clinical chart and workflows absent. |
| Oncology data model | 40 | Versioned assertions/context; independent tumor/episode/lesion and reconciled history model missing. |
| Clinical AI | 20 | Reference task/citation machinery; no qualified H1 clinical assistant. |
| Pathology and biomarkers | 20 | Literal source states and anchors; typed/validated extraction engine missing. |
| Radiology | 20 | Source/asset representation; image donors do not establish interpretation or RECIST. |
| Cancer staging | 10 | Stage can be recorded in text; no versioned staging engine. |
| Treatment management | 20 | Historical source/task representation; ordering/safety/administration absent. |
| FHIR/mCODE | 10 | Main lacks qualified exchange; bounded FHIR drafts are separate and mCODE conformance absent. |
| Clinical trials | 20 | Research profiling/fictional discovery; no patient eligibility workflow. |
| Cancer registry | 0 | No dedicated NAACCR abstraction/export runtime found. |
| Security | 40 | Scoped synthetic authorization, audit and recovery primitives; production controls unqualified. |
| AI evaluation | 20 | Fixtures/harnesses/citation tests; independent clinical gold sets and promotion gates absent. |
| Bioinformatics | 20 | Asset metadata and offline helpers; governed job workspace missing. |
| Genomic analysis | 10 | Asset/context plans; no variant pipeline established. |
| Bulk RNA-seq | 20 | GCT/descriptive utilities; no complete sequencing/DE pipeline. |
| Single-cell RNA-seq | 20 | Bounded matrix helper code; 13 local research checks skipped, no integrated pipeline demonstrated. |
| Multi-omics | 10 | Metadata/provenance ideas; no integrated analytical workflow. |
| Therapeutic target discovery | 10 | Manual biological hypotheses/options; no validated ranking pipeline. |
| Drug discovery research | 10 | Knowledge/research leads; no reproducible discovery workflow. |
| mRNA vaccine research | 10 | Architectural requirement; no qualified computational pipeline. |

## Prioritized implementation under existing owners

Complexity is relative engineering scope, not a schedule estimate. The existing execution backlog and domain issues remain authoritative; this table is a dependency view of the requested mandate, not a second roadmap.

| Priority / slice | Existing owner and affected files | Data/API change | Acceptance, dependency and security implications |
|---|---|---|---|
| P0 — Ambiguous access policy rejection (small; implemented here) | OI-013, `oi_api/access.py`, `test_patients.py` | No schema/API changes | Duplicate fields rejected before DB access; private 503; fresh grant/revocation reads retained. |
| P0 — Converge current patient application (large integration) | GH-112/OI-006/009/010; #481, #471/#482; existing API/web/migrations | Preserve published migration ancestry; compose existing endpoints | Test populated upgrades from each parent, originals/typed labs/manual context/questions/reports/tasks, lost replies and revocation; current exact head only. |
| P0 — Typed oncology master record (large domain slice) | Existing patient/source/clinical owners; E01/E02/E09 | Additive tumor/episode/lesion/history contracts after ownership review | Two independent primaries, metastatic link distinct from primary, revisions, source anchors, uncertainty, clinician attribution, cross-patient denial and restore. |
| P0 — Production identity/consent/security (large; externally dependent) | OI-012/013, authentication port/patient grants | Qualified identity provider/session and purpose/consent adapters | Verify people/roles/delegation/revocation, encryption deployment, incident/recovery and intended-use governance before real records. |
| P0 — FHIR source foundation (medium–large) | #425/#428/#115, E10 and source owner | Existing FHIR adapters, versioned terminology/profile metadata | Qualified patient mapping, byte preservation, unsupported-field refusal, amended observations, round-trip losses and profile conformance. |
| P1 — Pathology/biomarker extraction (large) | OI-011, #466, source/manual-review owners | Proposal records with model/version/confidence and exact anchor | Manual baseline plus held-out adjudication; wrong patient/specimen, negation, pending, contradiction, unavailable evidence and source amendment. |
| P1 — Staging and radiology reports (large; content dependent) | Clinical/source owners | Versioned stage proposals and measurement records | Rights-cleared rules, missing evidence remains unresolved, human finalization, source/version change triggers review. |
| P1 — Clinical Copilot (large) | OI-008/011, Composer/question/evidence owners | Bounded execution receipts over authorized context | Independent access per input; exact citations, historical states, abstention; no unreviewed clinical write or action. |
| P2 — Treatment/infusion/radiation (very large) | Clinical encounter/order owners | Additive plans/orders/administrations/exposure/toxicity | Reconciled allergy/medication/protocol knowledge, dose units, verified clinician approval, full error/recovery simulations. |
| P2 — Tumor board, trials and registry (large per domain) | Review/question/task owners; OI-017 | Meeting decisions, criterion-level trial state, versioned registry exports | Professional accountability, dissent, no inferred eligibility/enrollment, current status and reproducible exports. |
| P3 — Research workspace and first sequencing pipeline (large) | OI-016, biological asset/evidence/job owners | Research sample/job/run/result manifests, governed original storage | Synthetic/publicly permitted reference only; isolated compute, pinned tools/builds, truth sets, retry/cancel, checksummed inputs/outputs and clinical separation. |
| P3 — Bulk/single-cell/multi-omics (large per pipeline) | E12 and same research owner | Extend qualified jobs instead of parallel sample ledgers | Batch/design/QC/normalization decisions, paired/reference distinctions, versioned visualization and reproducible scientific reports. |
| P4 — Targets/drugs/neoantigens (very large; scientific dependencies) | Evidence/options/research owners | Research hypotheses/evidence and validation status | Source-backed ranking and counterevidence; predicted/experimental/clinical states distinct; relevant licenses and experimental oversight. |
| P5 — Population/outcomes/prediction (large) | Authorized research projection/evaluation owners | Cohort/query/prediction contracts | Consent, representativeness, leakage/bias/calibration evaluation, outcome attribution and independent intended-use qualification. |

## Implemented change and verification

The existing synthetic credential adapter parsed configuration with `AccessDocument.model_validate_json`. Duplicate object members were silently collapsed. A reproduced configuration containing both `"actions": []` and a later `"actions": ["patient_read"]` authenticated with the latter scope. This is an operator-configuration ambiguity and fail-closed defect; **it is not evidence that an unauthenticated network user can edit the policy file or escalate access**.

The repair rejects duplicate decoded member names at every object level before Pydantic validation, including escaped aliases and identical repeated values. It rejects nonfinite JSON constants, preserves UTF-8 and the existing byte bound, and maps parse/model/depth failures to the existing private access-service error. It retains current credential rereads, expiry checks, token digest comparison, patient/action scope and default denial. No policy values or secrets are logged.

| Change type | Exact scope |
|---|---|
| Modified runtime | `apps/api/src/oi_api/access.py` only |
| Modified tests | `apps/api/tests/test_patients.py`; six new test methods covering nested/top-level duplicates, both value orders, escaped/equal keys, nonfinite expiry, recovery/revocation and actual loopback HTTP denial before DB access |
| New audit artifacts | This report and `source-inventory.json` |
| Database migrations/tables | None |
| API endpoints or frontend components | None |
| Dependencies/integrations/models | None |
| Clinical/research data | Independently authored synthetic fixtures only; no real records accessed or changed |

| Check run in this session | Actual result |
|---|---|
| Pre-fix new/adjacent authorization tests | 7 methods executed; 21 failing assertions/subtests reproduced ambiguity and DB-entry behavior. Not 21 independent test methods. |
| Same focused tests after repair | 7 passed. Includes one inherited denial test and six added methods. |
| Main reference suite | 737 passed, no skips. Runtime in this suite was unchanged by the repair. |
| Main API baseline | 417 discovered: 96 passed, 321 database tests skipped. |
| Repaired API suite | 423 discovered: 102 passed, 321 database tests skipped. No failed executed tests. |
| Research helper suite | 204 discovered: 191 passed, 13 skipped. Do not count skips as validation. |
| React client baseline | 339 passed; zero failures/skips. |
| Frontend build | TypeScript and Vite build passed. No frontend changes. |
| Synthetic-data boundary | Passed: no known excluded patient-case download entrypoints in current workflows. |
| Patch whitespace | `git -c core.whitespace=cr-at-eol diff --check` passed; preserve existing CSV CRLF convention. |
| PostgreSQL/Compose, browser journey and backup/restore for this repair | Not executed locally; no local PostgreSQL or Docker. Hosted result must be attached to the exact published head. |
| Clinical validation, full security audit, standards conformance and biological pipeline validation | Not performed; not implied by passing software tests. |

Counts are not additive unique clinical scenarios. API and reference suites overlap conceptually; hosted donor results are not substituted for local or combined acceptance.

## Remaining blockers and audit limitations

1. A single accepted, verified application head has to replace the fragmented integration picture. Do not merge old drafts merely because each once passed its own tests. Published migration IDs, ancestry, owner semantics and populated data require explicit convergence.
2. Dedicated multi-tumor, medication safety, staging, lesion/RECIST, registry and comprehensive treatment capabilities remain substantial development work.
3. Production identity, valid clinical roles/consent, institutional endpoints, authorized data agreements, encryption/operations and intended-use qualification remain external and technical gates. Fixture authentication is not account proofing.
4. The research engine needs governed samples/jobs/storage/compute before advanced DNA/RNA/single-cell/therapeutic workflows. No arbitrary generated-code runner was added.
5. Exact third-party versions, data/model/reference rights and complete transitive inventories must be checked per adopted capability. No legal clearance is inferred from this report.
6. Clinical gold sets, independent expert adjudication, representative scientific truth sets, patient usability and accessibility testing remain incomplete.
7. Static inspection cannot prove missing behavior across all historical ref versions. Detailed domain audit and full acceptance should continue on the selected convergence head; the source inventory makes that scope reviewable.

No production deployment, destructive migration, merge, clinical approval, real-patient processing or completed-platform claim is made.

## Primary references and current project context

- [R1 — HL7 mCODE published guide](https://hl7.org/fhir/us/mcode/): inspected page identifies 4.0.0/STU4 on FHIR R4. mCODE supplies exchange profiles, not a requirement that every datum be collected or a complete operational EHR. Pin the exact package in any implementation.
- [R2 — NLM ClinicalTrials.gov API v2 notice](https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html): documents REST/OpenAPI v2 access; no OI integration or eligibility assurance follows from API availability.
- [R3 — NCI GDC access processes](https://gdc.cancer.gov/access-data/data-access-processes-and-tools): documents portal/API/transfer tools and separate open/controlled access.
- [R4 — PhysioNet FAQ](https://physionet.org/about/faqs/): dataset-specific credentialing/training/DUA and model-use constraints.
- [R5 — MIMIC-IV inspected release access page](https://www.physionet.org/content/mimiciv/2.0/): historical release page used for access requirements, not a claim that 2.0 is the current release.
- [Canonical identity/architecture precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f) and [product architecture](https://app.notion.com/p/40a3866f77ef81199312f0887a7d8f3b): read for accepted boundaries; not used as proof of implementation.
- [Engineering progress record](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit): read for active owners and prior evidence; reported donor tests remain historical until independently checked.
- Existing [execution backlog](../../EXECUTION_BACKLOG.csv), [implementation evidence](../IMPLEMENTATION_EVIDENCE.md) and [mandate reconciliation #459](https://github.com/OpenxIntelligence/open-intelligence/pull/459) retain their ownership. This audit adds evidence rather than replacing them.
