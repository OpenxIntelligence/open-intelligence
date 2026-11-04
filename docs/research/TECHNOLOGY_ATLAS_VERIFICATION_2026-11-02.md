> **Dated research appendix — 2 November 2026.** Candidate dispositions are research recommendations, not adoption or legal clearance. The accepted bounded H1 baseline is PostgreSQL 16; the PostgreSQL 18.6 source-license observation below does not amend that decision. H1 excludes vector search. Code, transitive dependencies, native assets, model weights, datasets and hosted content remain separate review scopes. The dated machine-readable companion is [TECHNOLOGY_ATLAS_VERIFICATION_2026-11-02.json](TECHNOLOGY_ATLAS_VERIFICATION_2026-11-02.json). Original working-file names in the preserved text refer to this companion.
>
> The original research text follows unchanged. Original capture `technology-atlas.md` SHA-256: `c7a09e5e64096ba39f0883cb5701f94a9236eac22e813399cd4c4ea9ae0da639`. This appendix complements the [first-principles plan](../FIRST_PRINCIPLES_PLAN.md), [execution backlog](../EXECUTION_BACKLOG.csv), and [execution audit](../engineering/EXECUTION_AUDIT_2026-11-02.md).

---

# Open Intelligence — technology atlas verification appendix

**Observed:** 2 November 2026. **Purpose:** a focused, evidence-backed supplement to the existing technology and licensing work, not another adoption register.

## Outcome

The strongest minimum direction remains a first-party patient/evidence/review core, a phased Python FastAPI + PostgreSQL and React/Vite/TypeScript application baseline, one bounded document-extraction path, and existing rights-qualified biomedical adapters. Complete the working patient identity → original documents → Patient World Model → permitted evidence → investigation → sourced report → human review path before adding specialist servers, raw-omics pipelines, or self-hosted model fleets.

This pass inspected **25 candidate source-license files at full commits**, including **20 newly pinned tagged-source receipts**. It independently re-fetched five receipts already in PR #125; all five license blob SHAs matched. This is useful source evidence, not a resolved-package audit or permission to install.

The five reused receipts are FastAPI, Vite, HAPI FHIR, OHIF and Orthanc. The full machine-readable companion, `technology-atlas.json`, records each full source commit, observed tag where available, exact license-file blob SHA, source URL, code/dependency/weight/dataset/hosted-content distinctions, and remaining gates.

## Existing authority and preservation

The existing work is substantial and should remain authoritative:

- [PR #125 exact-source license evidence](https://github.com/OpenxIntelligence/open-intelligence/blob/d93c07d4c2c4b44619aed44617139154b59a5f58/docs/research/OSS_LICENSE_DISCOVERY_WAVE1.json): eight inspected source receipts and explicit unresolved adoption status.
- [PR #127 priority screen](https://github.com/OpenxIntelligence/open-intelligence/blob/9c98e48cb026f8d8137445ebb445369039676b24/docs/research/OSS_PRIORITY_SCREEN_2026-11-02.md): wider candidate screening and declaration-inventory work.
- [PR #66 release manifest](https://github.com/OpenxIntelligence/open-intelligence/blob/f2a02fb26b3ae053a2b4c8395e51121c901eea8b/docs/OSS_RELEASE_MANIFEST.json): the inspected manifest contains an empty `adopted_components` array.

The existing OI-17 register remains the adoption decision authority. This appendix does not replace it, change any candidate to cleared, choose a production ADR, or edit the project. It narrows the next technical comparisons and adds evidence for their review.

**Decision labels below are proposed post-gate engineering dispositions.** “Adopt” and “Extend” indicate a preferred future composition after the required exact-artifact gates; they are not current approval states. Current work remains Research or Hold. “Hold” can reflect scope or operations as well as licensing. It does not assert that a copyleft component is inherently forbidden for commercial use.

“Initial workflow need” orders delivery for the requested path. Later priority does not remove imaging, pathology, genomics, first-party clinical operations, or other domains from the product's broader scope.

## Candidate evidence and disposition

The linked file is the actual inspected source-license/COPYRIGHT file. A release sample is an observation, not an instruction to install the newest version. The five inherited source snapshots remain explicitly unqualified as release pins.

| Candidate and role | Observed version/ref and license evidence | Source finding | Proposed disposition | Initial workflow need |
| --- | --- | --- | --- | --- |
| **FastAPI** — Application API | [source 5cb6272e; no release pin](https://github.com/fastapi/fastapi/blob/5cb6272ed7e3e07eaf6978e1e65b94aca76fa8e0/LICENSE) | MIT | **Adopt** | Foundation, phased |
| **PostgreSQL** — Operational database | [REL_18_6 · 724edf9b](https://github.com/postgres/postgres/blob/724edf9bde9d356724ad384a2e196edc3c9f80f7/COPYRIGHT) | PostgreSQL | **Adopt** | Foundation, phased |
| **React** — Application UI | [v19.3.1 · 61aa00df](https://github.com/react/react/blob/61aa00df822d0eb76d0362eb8b6fdd3527693efe/LICENSE) | MIT | **Adopt** | Foundation, phased |
| **Vite** — Frontend build | [source b3cb0575; no release pin](https://github.com/vitejs/vite/blob/b3cb0575aff63004a71301a1ec798aeea2aa05d7/LICENSE) | MIT | **Adopt** | Foundation, phased |
| **HAPI FHIR** — Clinical interoperability | [source f3cbac3b; no release pin](https://github.com/hapifhir/hapi-fhir/blob/f3cbac3b7788a2b71ca5614d8e18599d00fb0d4a/LICENSE.txt) | Apache-2.0 | **Integrate** | P1 exchange; optional for first path |
| **OHIF Viewer** — Imaging UI | [source 51e301d1; no release pin](https://github.com/OHIF/Viewers/blob/51e301d1460206c2cf946eeda08207bbe49d3993/LICENSE) | MIT | **Integrate** | P1 imaging |
| **Cornerstone3D** — Imaging primitives | [v5.14.0 · 37d135dd](https://github.com/cornerstonejs/cornerstone3D/blob/37d135ddf81dbea6ee1348024d1beddb872b4f9c/LICENSE) | MIT | **Extend** | P2 custom viewport |
| **DCMTK** — DICOM toolkit | [DCMTK-3.7.1 · 108acdae](https://github.com/DCMTK/dcmtk/blob/108acdae424d6999b2e398243938d8c563315ecf/COPYRIGHT) | BSD-3-Clause-like OFFIS core plus bundled notices; optional-library obligations | **Integrate** | P1/P2 DICOM utilities |
| **Orthanc** — DICOM server | [source 3d3c4418; no release pin](https://github.com/orthanc-mirrors/orthanc/blob/3d3c441847cc26e43125623602828a9ec6dd853f/COPYING) | GPL-3.0-or-later core; plugin-specific licenses include AGPL-3.0-or-later | **Hold** | P2 archive integration review |
| **OpenSlide** — Pathology WSI I/O | [v4.0.1 · fe79a971](https://github.com/openslide/openslide/blob/fe79a9713bef2bfd64bbfefd15704060764b1274/COPYING.LESSER) | LGPL-2.1-only | **Hold** | P2 pathology |
| **TIAToolbox** — Computational pathology | [v2.1.3 · 0d1495f7](https://github.com/TissueImageAnalytics/tiatoolbox/blob/0d1495f726aa73118da3e2b61d70ea50784505f7/LICENSE) | BSD-3-Clause code; pretrained weights expressly separate | **Research** | P2 pathology experiments |
| **Nextflow** — Scientific workflows | [v26.10.5 · de707574](https://github.com/nextflow-io/nextflow/blob/de707574a458f4f762310e9563b8c245f9be054f/COPYING) | Apache-2.0 | **Integrate** | P2 raw-omics workflow |
| **nf-core/sarek** — Somatic/germline sequencing | [3.11.0 · 6e9b164d](https://github.com/nf-core/sarek/blob/6e9b164daa2a54c98f7dda538645d340c561ac24/LICENSE) | MIT workflow code | **Research** | P2 raw sequencing |
| **Docling** — Document parsing/layout | [v2.145.0 · 45d334e3](https://github.com/docling-project/docling/blob/45d334e33f7aca345fc26880777288b8cd14262d/LICENSE) | MIT | **Integrate** | P0 extraction bake-off |
| **OCRmyPDF** — Searchable-PDF OCR | [v17.13.0 · 1a1cfb59](https://github.com/ocrmypdf/OCRmyPDF/blob/1a1cfb595b9a504a4689b23193a76bae7c3a156d/LICENSE) | MPL-2.0 code; per-file notices; docs include CC-BY-SA-4.0 | **Hold** | P1 searchable-PDF alternative |
| **Tesseract OCR** — OCR engine | [5.5.4 · 7e548e6e](https://github.com/tesseract-ocr/tesseract/blob/7e548e6eff172f38f97664afe7f7ce40db36c8d6/LICENSE) | Apache-2.0 engine | **Integrate** | P0 scanned-document fallback |
| **vLLM** — Model serving | [v0.33.0rc3 · 4ba787ec](https://github.com/vllm-project/vllm/blob/4ba787ec9959e566d3b587a796dff07673324da5/LICENSE) | Apache-2.0 | **Research** | P2 high-throughput self-hosting |
| **llama.cpp** — Local/compact model serving | [v0.8.0 · 8642541b](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/LICENSE) | MIT | **Research** | P2 compact self-hosting |
| **Temporal server** — Background workflow durability | [v1.32.2 · 6d085822](https://github.com/temporalio/temporal/blob/6d085822273f4336796e6959c73ab1d14a23eb77/LICENSE) | MIT server | **Integrate** | P1 when durable waits/retries require it |
| **LangGraph** — Agent graph orchestration | [1.2.19 · 5bd231cb](https://github.com/langchain-ai/langgraph/blob/5bd231cbfd913e05ebc662f519eb9a655bc766df/LICENSE) | MIT repository code | **Research** | P2 optional graph complexity |
| **pgvector** — Optional semantic retrieval | [v0.8.7 · f37c13f6](https://github.com/pgvector/pgvector/blob/f37c13f68b57d2c3472b2214fbcff699d6d34876/LICENSE) | PostgreSQL | **Integrate** | P1 after lexical baseline |
| **OpenSearch** — Standalone search cluster | [3.9.0 · 4ee42a94](https://github.com/opensearch-project/OpenSearch/blob/4ee42a94e87f66fbf1e62a9871b1b87f91e02472/LICENSE.txt) | Apache-2.0 server | **Hold** | P2 scale/retrieval trigger |
| **Keycloak** — Authentication and federation | [26.8.1 · 24ed1dad](https://github.com/keycloak/keycloak/blob/24ed1dadf3f246a555adb6d3d4a99e9b3003fb3b/LICENSE.txt) | Apache-2.0 | **Integrate** | P0 before authorized real deployment |
| **Syft** — Software bill of materials | [v1.56.0 · 173055c3](https://github.com/anchore/syft/blob/173055c39e9752f7b450ea404cd1801695277426/LICENSE) | Apache-2.0 code | **Adopt** | P0 release tooling |
| **Trivy** — Vulnerability and configuration scanning | [v0.76.1 · e713f67f](https://github.com/aquasecurity/trivy/blob/e713f67f7d54decdcd9b3132c9751833dcced698/LICENSE) | Apache-2.0 code | **Adopt** | P0 release tooling |

### What these choices buy

**FastAPI, PostgreSQL, React and Vite** are the smallest coherent target application baseline among these candidates. They do not replace first-party domain logic. Patient matching, source versioning, specimen identity, time, uncertain claims, evidence applicability, rights, investigations, report approval and amendment history stay in Open Intelligence's contracts. Introduce framework/storage/UI changes through compatibility boundaries; the existing integrated proof path should not wait for a rewrite. The PostgreSQL 18.6 receipt is an inspected source sample; choose a supported and compatible major/minor during the actual ADR and migration review. PostgreSQL explicitly recommends the current minor release of the selected supported major. [Version policy](https://www.postgresql.org/support/versioning/).

**Docling and Tesseract** are useful first document bake-off candidates. Docling offers layout-aware conversion and granular optional formats/models; Tesseract offers a direct scanned-text path. A small fictional corpus should cover tables, units, page breaks, amended reports, uncertain dates, malformed PDFs and OCR corrections. The criterion is preservation of source-page/span identity and correct uncertainty handling. No medical claim becomes verified merely because an extractor produced structured JSON. Docling's exact release manifest and README make model and feature selection consequential. [Manifest](https://github.com/docling-project/docling/blob/45d334e33f7aca345fc26880777288b8cd14262d/pyproject.toml), [model-license distinction](https://github.com/docling-project/docling/blob/45d334e33f7aca345fc26880777288b8cd14262d/README.md).

**HAPI FHIR** belongs at an interchange/validation boundary when FHIR exchange is needed. Compare it with Medplum and Blaze already in the catalog using the same independently fictional Patient, Encounter, Observation, Specimen, DiagnosticReport, DocumentReference and Provenance fixtures. Operating a second patient authority or a second clinical database is not justified by a FHIR server's presence. HAPI's Java/Maven footprint is a separate operational decision. [Existing exact receipt and scope](https://github.com/OpenxIntelligence/open-intelligence/blob/d93c07d4c2c4b44619aed44617139154b59a5f58/docs/research/OSS_TECHNOLOGY_AUDIT_WAVE1_2026-11-02.md).

**OHIF, Cornerstone3D and DCMTK solve different imaging jobs.** OHIF is the stronger first viewer integration candidate; Cornerstone is appropriate when a demonstrated custom viewport need warrants extending lower-level primitives; DCMTK supplies DICOM utilities/protocol functions. None of those alone establishes PACS custody, patient identity, operational imaging workflows or clinical validation. Do not maintain two viewer stacks merely because both are permissively licensed. [Existing OHIF boundary](https://github.com/OpenxIntelligence/open-intelligence/blob/9c98e48cb026f8d8137445ebb445369039676b24/docs/research/OSS_PRIORITY_SCREEN_2026-11-02.md), [Cornerstone license](https://github.com/cornerstonejs/cornerstone3D/blob/37d135ddf81dbea6ee1348024d1beddb872b4f9c/LICENSE), [DCMTK COPYRIGHT](https://github.com/DCMTK/dcmtk/blob/108acdae424d6999b2e398243938d8c563315ecf/COPYRIGHT).

**Syft and Trivy** are complementary release-tooling candidates. The existing declaration inventory says what the repository declares; Syft can inventory a built image/filesystem and emit SPDX/CycloneDX; Trivy can supply vulnerability, configuration and license signals. Preserve tool versions, scanned artifact digests and advisory database timestamps. A clean result is not complete security, patent, content or model clearance. No scanner or dependency resolver was run in this research task. [Syft README](https://github.com/anchore/syft/blob/173055c39e9752f7b450ea404cd1801695277426/README.md), [Trivy README](https://github.com/aquasecurity/trivy/blob/e713f67f7d54decdcd9b3132c9751833dcced698/README.md).

## Highest-value corrections and gaps

### 1. TIAToolbox has two concrete restrictions beyond its BSD root

The exact v2.1.3 requirements directly include `openslide-bin` and `openslide-python`. Consequently, a proposed default TIAToolbox install inherits the unresolved OpenSlide integration/distribution review even though TIA's own code is BSD-3-Clause. The official OpenSlide license states **LGPL-2.1-only** for its code and official bindings. [TIA requirements](https://github.com/TissueImageAnalytics/tiatoolbox/blob/0d1495f726aa73118da3e2b61d70ea50784505f7/requirements/requirements.txt), [OpenSlide license](https://openslide.org/license/).

TIA's exact pretrained documentation identifies `fcn-tissue_mask`, `hovernet_fast-pannuke` and other checkpoints as **CC BY-NC-SA 4.0**. **Reject those specific weights as a commercial product default absent a separate grant.** This does not reject TIA's BSD code or grant clearance to its other checkpoints. Other documented model families use different licenses; each chosen weight file, hash, model card and dataset provenance still needs its own review. No weights or datasets were downloaded. [Exact pretrained documentation](https://github.com/TissueImageAnalytics/tiatoolbox/blob/0d1495f726aa73118da3e2b61d70ea50784505f7/docs/pretrained.rst).

### 2. DCMTK needs an actual build inventory

The inspected DCMTK 3.7.1 COPYRIGHT starts with a permissive OFFIS license, but also includes IJG/legacy/component notices, mentions separately licensed modules outside the free toolkit, and describes optional libraries with additional obligations. Optional libiconv and libsndfile entries are LGPL. A label such as “BSD DICOM toolkit” is insufficient to clear a compiled artifact. Record enabled modules, static/dynamic linkage, native dependencies and their notices. The source file itself cautions that module-specific COPYRIGHT files can apply. [Exact COPYRIGHT](https://github.com/DCMTK/dcmtk/blob/108acdae424d6999b2e398243938d8c563315ecf/COPYRIGHT).

### 3. Orthanc core, plugins and protocol use are separate decisions

The official FAQ identifies GPLv3+ core and AGPLv3+ plugin cases. Its table distinguishes external REST/DICOM calls from linked plugins, scripts and derived code. Preserve the incorporation hold while assessing any concrete protocol integration on its own facts. Do not say that GPL prohibits all commercial uses. The official DICOMweb plugin page specifically identifies that plugin as AGPL. [Official FAQ](https://orthanc.uclouvain.be/book/faq/licensing.html), [DICOMweb licensing](https://orthanc-server.com/static.php?page=dicomweb).

The same FAQ says dual licensing is no longer available for Orthanc versions containing UCLouvain code; 1.9.7 was the last potentially eligible server release. Therefore “buy a commercial license later” is not a valid generic mitigation for a current Orthanc composition. This is upstream's stated position and must be assessed against the intended deployment. [Restricted-use explanation](https://orthanc.uclouvain.be/book/faq/licensing.html).

### 4. OCRmyPDF's current dependency picture is more nuanced than older guidance

The inspected OCRmyPDF v17.13.0 source is MPL-2.0; some documentation files carry CC-BY-SA-4.0 notices. MPL is file-level copyleft, not an automatic prohibition on proprietary combinations. OI's policy review still applies. [Code license](https://github.com/ocrmypdf/OCRmyPDF/blob/1a1cfb595b9a504a4689b23193a76bae7c3a156d/LICENSE), [Mozilla FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).

The exact release's installation/introduction documentation says v17 supports pypdfium2 rasterization and internal PDF/A handling without Ghostscript. Some PDF/A conversions still require a Ghostscript path, and a stale paragraph in that same introduction continues to say Ghostscript is required. Qualify the selected build and disable unreviewed fallback executables; do not infer that an ordinary system installation excludes Ghostscript or other optional tools. [Installation documentation](https://github.com/ocrmypdf/OCRmyPDF/blob/1a1cfb595b9a504a4689b23193a76bae7c3a156d/docs/installation.md), [introduction](https://github.com/ocrmypdf/OCRmyPDF/blob/1a1cfb595b9a504a4689b23193a76bae7c3a156d/docs/introduction.md).

That introduction also identifies its sample HTTP service as a demonstration without security and states OCRmyPDF is not designed against malware-bearing PDFs. Use an isolated, resource-bounded ingestion worker, retain immutable originals, and treat extracted text as untrusted input. The example service should not become the product ingestion endpoint.

### 5. A permissive genomic workflow does not license all tools or tests

Sarek 3.11.0's MIT license covers its workflow code. Its README/configuration lists multiple caller/aligner choices, including Sentieon and Parabricks paths, and each process container/tool/model/reference requires separate review. Sarek also documents real human benchmark datasets in built-in full test profiles. Those profiles must not be executed or copied into OI fixtures under the current synthetic-only mandate. Create independently fictional sequence/report fixtures instead; do not derive them from a real patient or donor. [Exact README](https://github.com/nf-core/sarek/blob/6e9b164daa2a54c98f7dda538645d340c561ac24/README.md), [configuration](https://github.com/nf-core/sarek/blob/6e9b164daa2a54c98f7dda538645d340c561ac24/nextflow.config).

### 6. Serving and orchestration licenses do not clear models or services

vLLM's Apache-2.0 and llama.cpp's MIT code do not license any LLM, tokenizer, GGUF conversion, quantized checkpoint, embedding model or clinical corpus. No model or weight artifact was selected. Compare them only after a permitted model, hardware budget and measurable task exist. vLLM is a candidate for higher-throughput service requirements; llama.cpp is a candidate for compact or lower-concurrency CPU/hybrid deployments. These are design hypotheses to benchmark, not measured performance conclusions. [vLLM README](https://github.com/vllm-project/vllm/blob/4ba787ec9959e566d3b587a796dff07673324da5/README.md), [llama.cpp README](https://github.com/ggml-org/llama.cpp/blob/8642541b255bfb5dc39cd351a178be09013a55d6/README.md).

The observed GitHub `releases/latest` endpoint returned **v0.33.0rc3** for vLLM with `prerelease=false`. Record the actual tag and qualify stability independently; the “latest” API marker is not a release-quality gate.

Temporal's inspected MIT receipt covers the **server**, while SDKs, UI, worker dependencies and Temporal Cloud must be reviewed separately. LangGraph's MIT repository is distinct from LangSmith and deployment services. Neither framework owns patient authority, clinical writes, rights decisions or final review. Patient-containing workflow history and telemetry need controlled payloads/retention. [Temporal scope](https://github.com/temporalio/temporal/blob/6d085822273f4336796e6959c73ab1d14a23eb77/README.md), [LangGraph service links](https://github.com/langchain-ai/langgraph/blob/5bd231cbfd913e05ebc662f519eb9a655bc766df/README.md).

## Minimum comparisons that can change a decision

These are proposed engineering acceptance tasks, not tests executed in this research pass.

| Decision | Minimum useful comparison | Decision criterion |
| --- | --- | --- |
| Core stack migration | Existing first-party workflow vs one compatibility-preserving FastAPI/PostgreSQL and React/Vite boundary | No lost source lineage, identity ambiguity, amendment history, rights behavior or review state; migration/rollback practical |
| Document extraction | Current extraction vs minimal Docling features; direct Tesseract for scans | Exact original bytes preserved; correct page/span/cell mapping; visible uncertainty and correction; bounded resource use |
| FHIR | HAPI vs already cataloged Medplum/Blaze on the same fictional exchange cases | Correct issuer/identity/specimen/version semantics and acceptable operational footprint; one server only if justified |
| Imaging | OHIF configured first; Cornerstone custom view only for an unmet task | Authorized source image linked to the correct patient/study with provenance and a reviewed codec bundle |
| Retrieval | PostgreSQL structured/lexical baseline vs exact pgvector search before approximate indexing | Better retrieval on a permitted synthetic/evidence benchmark without rights-filter leakage or lost recall; embedding rights explicit |
| Background work | Existing persisted job state vs Temporal for retry, cancellation and human wait | Survives worker restart, prevents duplicate effects, preserves source/right versions, supports review and revocation |
| Model serving | vLLM vs llama.cpp using the same separately approved model and task | Measured latency, concurrency, memory, cost and data-location requirements; no efficacy claims from infrastructure alone |
| Genomics | One independently fictional pipeline task in Nextflow vs cataloged Snakemake | Reproducible input/output, tool/container/reference fingerprints and QC; no uncontrolled upstream test downloads |
| Release evidence | Existing declaration inventory plus actual artifact SBOM/scanner output | Pinned target digest, package/native/asset coverage, notices, advisory timestamp and reviewed findings |

The **PostgreSQL-first retrieval choice** avoids a second operational cluster while the corpus is small and rights-qualified joins remain central. pgvector is a reasonable next step if a benchmark justifies semantic retrieval; OpenSearch should wait for a demonstrated need. Exact search and approximate HNSW/IVFFlat tradeoffs are documented by pgvector; numerical recall/latency has not been measured for OI. [Exact pgvector README](https://github.com/pgvector/pgvector/blob/f37c13f68b57d2c3472b2214fbcff699d6d34876/README.md).

**Keycloak** is a self-hosted IdP candidate if an approved identity provider is not already present. Its Apache-2.0 source does not establish clinician credentials, patient matching, consent, purpose-of-use or case-level authorization. Those remain first-party responsibilities. [Exact source](https://github.com/keycloak/keycloak/blob/24ed1dadf3f246a555adb6d3d4a99e9b3003fb3b/README.md).

## Explicit limits and handoff

1. Source licenses were inspected; no installation, dependency resolution, code adoption, SBOM generation, scanner run, model download or clinical test was performed.
2. The twenty new tagged-source receipts improve on branch-head-only evidence, but tags are not deployment artifact digests. Store a reproducible lockfile/container/native-asset inventory when an actual release is chosen.
3. The five reused source snapshots have no endorsed release pin. Their independently verified license blobs do not close their package graph, assets or security review.
4. No transitive legal clearance, patent freedom, trademark clearance, clinical safety, regulatory readiness or production authorization is asserted.
5. Code, dependency/native binary, model weights, datasets, terminology/guidelines, hosted services and document/article content remain distinct rights surfaces. A software license does not authorize the clinical corpus.
6. Public examples, benchmark images, upstream test profiles and real patient narratives are not OI fixtures. No real patient data or patient-derived synthetic data was used.
7. Tool availability and version observations are dated. Re-verify the actual chosen release and security status at adoption; do not automatically chase sampled newest releases.
8. Next work should update the existing evidence register and execute the few comparisons necessary for the integrated workflow. Further catalog expansion should not delay that workflow.

## Machine-readable receipt integrity

All 25 entries contain a 40-character source commit, a 40-character license blob SHA and the corresponding immutable source-file URL. The JSON deliberately records `adoption_clearance: NOT_GRANTED` for every entry. It includes the observed release tags/timestamps for new inspections, the five inherited audit origins, source-file receipts for material dependency/model findings, and unresolved scope for every candidate.

No project code, GitHub state, external document or adoption manifest was changed by this appendix.
