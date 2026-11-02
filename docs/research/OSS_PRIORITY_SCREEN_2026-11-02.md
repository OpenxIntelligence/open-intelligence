# Open Intelligence — priority OSS, licensing and architecture decision checkpoint

**Date:** 2 November 2026 · **Status:** upstream-source screening, not release clearance or accepted stack ADR  
**Authority:** OI-17 commercial/source-rights policy and existing [Notion 125-resource register](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3). This document is a **dated evidence appendix**, not a competing resource catalog. Open Intelligence remains a single patient-centered intelligence environment expanding into the complete first-party healthcare ecosystem. No Next.js. Do not treat a prototype milestone as a product boundary.

## The product and what should be built first

**Primary user journey:** Create a patient → collect and preserve authorized original medical/biological data → reconcile source identity, specimen, temporal history, and uncertainty into the Patient World Model → retrieve rights-qualified biomedical knowledge (including supporting and contradictory research) → run bounded computational and AI investigations → inspect exact sources/methods/applicability → obtain appropriate human review → persist outcomes and re-evaluate after new patient evidence, publication, guideline version or revocation. The first-party EHR, LIS, pathology, RIS/PACS, genomics and treatment products must feed this same governed patient state, rather than duplicate it.

Democratization is binding: support ordinary patients, caregivers, and the full spectrum of diagnosis, treatment, recurrence, survivorship and advanced care, not only exceptional high-resource cases. Use independently authored fictional fixtures. Patient narratives may motivate product research; personal cancer/genomic datasets are **not** an engineering/CI dependency. Current [PR #123](https://github.com/OpenxIntelligence/open-intelligence/pull/123) removes remaining named-person public-case downloads from CI; review its evidence and preserve source analysis only as historical research.

## Critical distinction: a source license is not product clearance

**T1 screening** = official upstream repository states MIT, Apache-2.0, BSD, ISC, PostgreSQL, etc. **No artifact in this appendix has passed the OI-17 exact-release source, fork, license, patent, dependencies, asset/weights, dataset/content, security, SBOM and authorized-commercial-use gates.** Distinguish legal/content rights from software code, and research-only runtime from product build. The [existing OI-17 register](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9) remains the single adoption decision register. Exact release tags, source SHAs and resolved dependency hashes remain to be populated during actual bake-offs.

### Candidate evaluation (upstream repository-level license assertions, not releases)

| Role / layer | Candidate and official evidence | Source-level license finding | OI engineering recommendation and decisive gate |
| --- | --- | --- | --- |
| FHIR foundation / typed SDK / UI widgets | [Medplum](https://github.com/medplum/medplum/blob/main/README.md) | Apache-2.0 | **EVALUATE** its FHIR types/React packages and server as separate roles. Does not supply the full oncology/EHR/LIS/PACS first-party product. Resolve exact package graphs and compare with existing first-party code. |
| Alternative FHIR server | [HAPI FHIR](https://github.com/hapifhir/hapi-fhir) | Apache-2.0 | **BAKE-OFF** as an independently operated FHIR R4 interchange server; Java operational footprint and clinical data ownership require explicit architecture. Do not install alongside another FHIR server without a demonstrated need. |
| Alternative FHIR/CQL platform | [Blaze](https://github.com/samply/blaze) | Apache-2.0 | **BAKE-OFF** for FHIR/CQL; determine whether its clinical querying semantics justify a distinct service. |
| Alternative FHIR server | [Microsoft FHIR Server](https://github.com/microsoft/fhir-server) | MIT | **RESEARCH** support/maintenance and actual deployment semantics, not a default stack choice. |
| Product UI build | [Vite](https://github.com/vitejs/vite/blob/main/packages/vite/LICENSE.md) | MIT | **EVALUATE** for first-party React/TypeScript front end. No Next.js. Verify all build plugins and exact lockfiles. |
| Accessible interaction primitives | [Radix UI](https://github.com/radix-ui/primitives/blob/main/LICENSE) | MIT | **EVALUATE** for accessible dialogs, popovers, controls; retain independent first-party design tokens and clinical UX acceptance tests. |
| Data-dense tables | [TanStack Table](https://github.com/TanStack/table) | MIT | **EVALUATE** for patient records, laboratory tables, variant and evidence matrices; it does not provide clinical meanings or authority controls. |
| Python API | [FastAPI](https://github.com/fastapi/fastapi) | MIT | **EVALUATE** alongside existing Python engine; optional `[standard]` installs additional packages/services, so pin extras and production image. |
| DICOM presentation | [OHIF Viewer](https://github.com/OHIF/Viewers) | MIT | **EVALUATE** task-specific image viewer. It is not a production PACS, diagnostic validation or DICOM custody backend. |
| Imaging primitives | [Cornerstone3D](https://github.com/cornerstonejs/cornerstone3D) | MIT | **EVALUATE** viewport/tools, codecs and WebAssembly assets; adopt with/without OHIF only after a single integrated UI test. |
| DICOM parsing | [pydicom](https://github.com/pydicom/pydicom/blob/main/pyproject.toml) | MIT main code | **EVALUATE** basic parsing; optional `gpl-license` codec group and native pixel decoders require a separate full dependency/asset gate. |
| Computational pathology | [TIAToolbox](https://github.com/TissueImageAnalytics/tiatoolbox/blob/develop/LICENSE) | BSD-3-Clause code | **EVALUATE** Python pathology/WSI capabilities; pretrained weights are explicitly under different terms; no automatic commercial model qualification. |
| Genomic variant calling | [DeepVariant](https://github.com/google/deepvariant) | BSD-3-Clause code | **EVALUATE** for its actual germline-calling tasks; not a substitute for oncology somatic pipelines or bioinformatics validation. |
| Reproducible scientific workflows | [Snakemake](https://github.com/snakemake/snakemake/blob/main/pyproject.toml) | MIT | **COMPARE** with Nextflow for one real synthetic genomics process; plugin/executor/container/reference data rights independently. |
| Alternative bioinformatics workflows | [Nextflow](https://github.com/nextflow-io/nextflow) | Apache-2.0 | **COMPARE**, select one primary scientific workflow engine on actual benchmark, not community popularity. |
| Scientific PDF parsing | [GROBID](https://github.com/grobidOrg/grobid) | Apache-2.0 code | **EVALUATE** only with authorized publications; code license never grants content/text-mining/ML rights to copyrighted articles. |
| Relationship/authorization graph | [OpenFGA](https://github.com/openfga/openfga) | Apache-2.0 | **EVALUATE** for granular relationship access; first-party consent/purpose/clinical authority, audit and recheck-on-export remain required. |
| Federated IAM / SSO | [Keycloak](https://github.com/keycloak/keycloak) | Apache-2.0 | **EVALUATE** as identity-provider candidate, not verified clinician credentials or patient matching by itself. |
| Optional search engine | [OpenSearch](https://github.com/opensearch-project/OpenSearch) | Apache-2.0 | **RESEARCH/DEFER** until the measured retrieval quality/volume exceeds PostgreSQL structured/lexical/terminology capabilities. |
| Optional focused search | [Meilisearch CE](https://github.com/meilisearch/meilisearch/blob/main/README.md) | MIT **Community Edition** | **EVALUATE CE ONLY**; Enterprise Edition includes BSL 1.1/commercial terms and is not automatically cleared. |
| Object storage backend | [SeaweedFS community](https://github.com/seaweedfs/seaweedfs) | Apache-2.0 | **EVALUATE** S3 storage role; enterprise recovery/erasure features are distinct, and clinical immutability/backup/retention must be proven independently. |
| Clinical imaging AI framework | [MONAI](https://github.com/Project-MONAI/MONAI) | Reported Apache-2.0 upstream | **RESEARCH** code vs individual checkpoint, dataset, GPU/runtime license; no inference of clinical diagnostic authorization. |
| Clinical reference information | [NCI information/PDQ](https://www.cancer.gov/policies/copyright-reuse) | NCI text generally free for reuse; figure/trademark exceptions | **SOURCE-REVIEW** NCI content with attribution and product distinction; it is not automatically a clinical guideline or patient treatment instruction. |
| Molecular evidence knowledge | [CIViC](https://docs.civicdb.org/en/latest/about/faq.html) | CC0 curated content; MIT application code | **PRIORITIZE** rights-qualified variant evidence via official API with specimen/histology/assay/applicability evaluation. |
| Scientific full text | [PMC Open Access Subset](https://pmc.ncbi.nlm.nih.gov/tools/openftlist/) | **Per-article** licenses vary | **HOLD PER ITEM** until full-text commercial/AI use verified. Only approved PMC machine retrieval services; not all free-to-read content is reusable. |

### Important restrictions and alternatives

| Candidate | Verified source-level restriction | OI decision |
| --- | --- | --- |
| [OpenELIS Global 2](https://github.com/DIGI-UW/OpenELIS-Global-2) | **MPL-2.0**, not a Tier-1 MIT/Apache library | **T2 HOLD** for embedding/forking; independently study LIS workflows; external interoperability can be researched with legal review. The old 1.x is end-of-life. |
| [OpenSlide](https://openslide.org/license/) | **LGPL-2.1-only** | **T2 HOLD** for commercial integration until dynamic/static linking and redistribution obligations are reviewed. |
| [Orthanc](https://orthanc-server.com/download.php) | Server **GPLv3+**; some plugins/viewers **AGPLv3+** | **T3 EXCLUDED for incorporated core** under the existing business policy. External protocol integration requires separate legal opinion, not a loophole. |
| [MinIO community repository](https://github.com/minio/minio) | **AGPLv3**, **archived Apr 25, 2026** | **T3 EXCLUDE** as preferred first-party incorporated storage. Evaluate licensed alternatives where appropriate. |
| [Meilisearch Enterprise Edition](https://github.com/meilisearch/meilisearch/blob/main/README.md) | **BSL 1.1/commercial restrictions** (Community Edition MIT is distinct) | **T3 EXCLUDE** enterprise build unless separately licensed. |
| [pydicom optional GPL pixel-codec extra](https://github.com/pydicom/pydicom/blob/main/pyproject.toml) | Explicit `gpl-license` extra in source manifest | **T3 HOLD/EXCLUDE** that install path; default pydicom code remains Tier-1 screening candidate. |
| NCCN / ASCO / ESMO oncology guidelines | Licensed/copyrighted clinical content distinct from SDKs, URLs or access accounts | **CONTENT HOLD** until written contracts specify exact ingestion, AI processing, versioning, retention, commercial reuse and distribution. Do not assume pasted NCCN API/MCP endpoints are official. |
| Clinical staging/classification (AJCC, WHO, SNOMED, LOINC, RxNorm) | Terms and jurisdictions vary by content/provider | **DATA/TERMINOLOGY REVIEW**, never infer rights from a parser or terminology-server license. |

## Architecture decision to test, NOT a final stack lock

- **First-party patient and evidence core:** extend the existing patient identity, source version/lineage, time/provenance, investigation and event contracts. The Patient World Model is a governed derived projection, never a duplicate operational EHR database.
- **Interoperability:** evaluate Medplum typed FHIR/React libraries and **one** interoperable FHIR backend (Medplum server vs HAPI vs Blaze) using the same versioned Patient/Encounter/Observation/Specimen/DiagnosticReport/DocumentReference/Provenance fixtures. Do not outsource ownership of clinical facts to a FHIR façade.
- **Presentation:** first-party React + Vite + TypeScript is a viable candidate, with Radix and TanStack where necessary. Keep the current working interface until navigation, patient evidence drilldown, keyboard access, 200% zoom and source-amendment testing show improvement. Separate patient overview from institution-wide clinical/LIS/imaging workflows.
- **Scientific knowledge:** first build permitted CIViC + PubMed metadata + rights-qualified PMC/NCI sources. NCCN/ASCO/ESMO connectors stay explicit licensed interfaces; absence of content must be visible rather than hallucinated or silently filled.
- **Search:** structured identifiers, terminology, temporal and lexical search first. Consider embeddings/vector search only after evidence of greater precision, explainability and tractable rights/cost for patient-specific queries. Search is not truth or source authority.
- **Imaging:** OHIF/Cornerstone task-specific viewer and pydicom processing are candidates. Build/archive/retrieve original DICOM Study/Series/Instance with first-party custody; choose its storage engine separately. Do not confuse a viewer with PACS.
- **Scientific pipelines:** choose Snakemake or Nextflow per reproducibility, container/assets license, execution latency and actual genomic task; specialized models require their own license and scientific validation.
- **Security:** trusted IdP and relationship authorization candidates still need first-party purpose/consent, audit, revocation and regulatory controls. No external PHI or real-patient deployment prior to authorization.
- **Software rights:** source license + exact release/digest + dependencies/extras + artifact/assets + patent + notices + security + OI-17 approval. No assertion of “zero legal risks.” Never install all these packages merely because they are listed.

## Executable supply-chain inventory contribution

`tools/oss_dependency_inventory.py` scans the **current checked-out repository** using the Python standard library; collects manifests, pinned research requirements, inline workflow `pip install` declarations, GitHub Actions code/pins and file hashes; emits JSON. It **does not download patient data, fetch packages, resolve dependencies, inspect model weights, discover hidden transitive dependencies, grant licenses, or generate an SBOM**. Research-only `tools/research/requirements.lock` and the single-cell workflow's pinned `numpy/h5py` installation must not be mislabeled as adopted production dependencies. A separate existing [PR #66](https://github.com/OpenxIntelligence/open-intelligence/pull/66) checks declared adopted-receipt presence; these are **complementary, not competing** controls.

Command: `python tools/oss_dependency_inventory.py --output verification-artifacts/oss-declarations.json` (no package installation).

## High-value engineering bake-offs and acceptance (next work after this audit)

| Priority | Reuse decision | Must pass |
| --- | --- | --- |
| P0 | First-party patient data + FHIR adapter comparison | Correct exact original source/version, case/episode/specimen identity, amendment and rollback, authorized import/export, no silent patient merge |
| P0 | CIViC + permitted publication knowledge adapter | Exact authoritative version/identifier, applicable biology, source rights for model use, opposing evidence, revoked-content withholding, no fabricated clinical guidance |
| P0 | Patient investigation UI | Open original report from supported statement in 1-2 interactions, keep context, version/applicability/contradictions visible, human review separable |
| P1 | Imaging viewer + DICOM archive | Open a *synthetic* DICOM study through task-specific viewer; verify source identity, access, pixel/codec rights, archive recovery and role boundaries |
| P1 | Genomics/omics workflow | One fictional reproducible assay → versioned reference, pipeline/model fingerprint, results with QC and explicit comparability limits |
| P1 | Security/operations | Real authority/consent and tenant isolation tests, verified bundle/SBOM/patents, backups, audit, rollback, monitored failure and cost |

**Additional domain coverage required:** first-party oncology, LIS, pathology, radiation planning, multi-omics, pharmacy/medication operations, care coordination, scheduling, enterprise administration, research collaboration, patient access/language/accessibility, model orchestration/evaluation and scientific validation. These remain the comprehensive product scope. Incomplete coverage is a tracked gap, not permission to narrow the platform.

**Evidence completeness:** this is an upstream-code-license screen and a proposed composition, not an exhaustive evaluation of every listed upstream release, the existing 125 catalog entries, transitive dependencies or all categories in the four founder-supplied source documents. No candidate was advanced to `Cleared`, no third-party runtime package was adopted, and no real patient data was used.
