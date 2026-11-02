# Open Intelligence — reusable technology audit addendum

**Research date:** 2 November 2026. **Status:** complementary evidence and recommendations, not an accepted architecture or adoption decision. This appendix supports the existing OI-17 decision register, the 125-resource register, and PR #125/#127 research; it does not replace them. No third-party software was installed, no patient data was retrieved, no model was run, and no remote write or outreach was performed in this pass. New development excludes Next.js.

## Outcome and next useful decision

The prior research is already broad enough to support implementation. The immediate priority is to complete a rights-qualified path from a source/evidence item into a durable investigation and its scoped human review using the existing contracts. That step needs no new dependency. Adding a broad stack now would not resolve the remaining product integration work.

For the next dependency decisions, prioritize **a bounded first-party React/Vite UI increment, Docling versus simpler extraction on synthetic reports, and a versioned CIViC adapter**. Compare Medplum only against the app-owned persistence/interchange path defined by OI-005; do not let a demo app select the domain architecture. Use OHIF/highdicom, VRS/VEP, and specialized pathology tools as later adapters when their actual input/output contracts are ready. IAM and orchestration infrastructure should address measured requirements. No candidate here is release-cleared.

The commercial ambition remains a complete first-party patient and healthcare platform. Reuse implementation underneath coherent first-party workflows while retaining one governed case/source/evidence/investigation/review model. A viewer, FHIR store, LIS, agent framework or knowledge API does not replace that model. The absence of a permissive comprehensive LIS choice is a tracked gap, not a reason to narrow the product or adopt an incompatible license by default.

## What this pass adds to existing evidence

1. **Reused prior source and artifact evidence explicitly.** The 29-Oct catalogs contain 58 clinical, 75 multimodal, 69 evidence and 57 platform entries (259 category entries, not necessarily 259 unique products). The Medplum source audit supplies ten immutable snapshots. Its conclusion was zero release-cleared components; the trimmed UI build was quarantined.
2. **Independently re-read exact installed license files.** React/React DOM 19.2.0, Vite 7.3.7, Mantine core 8.3.18 and Medplum core 5.2.11 package manifests and actual license files were checked again on 2-Nov, with full SHA-256 hashes below/in JSON. These are historical candidate artifacts, not assertions that those versions are current, supported or approved.
3. **Rechecked primary upstream source.** Actual official current-branch LICENSE text was read for Medplum, HAPI, OHIF, highdicom, DICOM Microscopy Viewer, VRS-Python, VEP, Docling, medSpaCy, PydanticAI, Temporal, OpenFGA, Keycloak, DuckDB, React, Vite and Mantine, plus PostgreSQL's actual official license. A branch check is weaker than an immutable source-to-artifact match.
4. **Resolved two additional version pointers without overclaiming.** Docling v2.145.0 resolves to `45d334e33f7aca345fc26880777288b8cd14262d`; highdicom v0.28.2 resolves to `847fea5946b4be9cf0c9939b8f9dcbf0bc60b24d`. Their exact pinned LICENSE fetches failed in this environment. Consequently the matrix does not claim that the current-branch license was independently matched to either immutable commit. Their release pages show active release work, not validation of these components for Open Intelligence.
5. **Preserved higher-quality existing receipts.** PR #127 says PR #125 already records eight exact upstream source commits and LICENSE blob SHAs. That JSON was not available to this subtask; its specific receipts take precedence for those inspected commits. This appendix does not manufacture a second clearance status.

## How to read the recommendations

**Adopt** means the preferred candidate direction once the existing decision process and exact artifact checks are satisfied; **extend** means add a small governed capability around the component; **integrate** means a bounded adapter rather than importing a complete product; **research** means a comparison or qualification is still needed; **hold** means the current rights/fit boundary prevents selection. These are proposed actions, not statements of accepted decisions or implemented behavior.

MIT/Apache/PostgreSQL grants generally permit commercial use, modification and self-hosting subject to their terms. A permissive source grant does not settle dependencies, patents outside the grant, trademarks, content, model weights, training data, hosted services or clinical deployment. Apache redistribution entails applicable LICENSE/NOTICE and modification notices; MIT and PostgreSQL require their notices. MPL permits commercial use but carries file-level conditions, so it remains outside the preferred permissive incorporated-core path here. Exact duties depend on the selected artifact and distribution mode.

## Shortlist

| Candidate | Role | Source license | Recommendation | Fit |
|---|---|---|---|---|
| [Medplum core / selected SDKs](https://github.com/medplum/medplum) | Clinical / FHIR | Apache-2.0 | **research** | High for bounded OI-005 comparison; optional selected SDK reuse; no default backend replacement. |
| [HAPI FHIR](https://github.com/hapifhir/hapi-fhir) | Clinical / FHIR | Apache-2.0 | **research** | Conditional alternative if partner FHIR capabilities justify a separately operated server. |
| [OpenELIS Global 2](https://github.com/DIGI-UW/OpenELIS-Global-2) | Laboratory operations | MPL-2.0 | **hold** | Useful operational reference and potential separately reviewed integration; not a permissive incorporated-core default. |
| [OHIF Viewer](https://github.com/OHIF/Viewers) | Imaging review | MIT | **integrate** | High for later image-review slice; not necessary for report-only first milestone. |
| [highdicom](https://github.com/ImagingDataCommons/highdicom) | Imaging / pathology result objects | MIT | **integrate** | High for preserving quantitative image/pathology outputs once imaging analysis is scoped. |
| [DICOM Microscopy Viewer](https://github.com/ImagingDataCommons/dicom-microscopy-viewer) | Pathology viewing | MIT | **research** | Useful embedded pathology viewer alternative; compare with OHIF whole-slide capability before selecting another viewer. |
| [GA4GH VRS-Python](https://github.com/ga4gh/vrs-python) | Genomic representation | Apache-2.0 | **integrate** | High for normalizing imported variant representations after molecular ingestion exists. |
| [Ensembl VEP](https://github.com/Ensembl/ensembl-vep) | Genomic annotation | Apache-2.0 | **research** | Strong later annotation candidate after a concrete assay/reference requirement; not an initial clinical interpretation engine. |
| [CIViC](https://github.com/griffithlab/civic-v2) | Molecular evidence | MIT code; CC0-1.0 curated content | **integrate** | Highest-priority knowledge adapter after existing rights-qualified evidence-to-investigation path is proved. |
| [Docling](https://github.com/docling-project/docling) | Document extraction | MIT | **research** | Highest-priority extraction bake-off, using synthetic reports and exact source anchors. |
| [medSpaCy](https://github.com/medspacy/medspacy) | Clinical NLP | MIT | **extend** | Useful small, inspectable rule pipeline for negation/uncertainty alongside document extraction. |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | AI task orchestration | MIT | **research** | Good fit with the existing Python contract layer if it measurably reduces adapter effort; no need to replace deterministic coordinator. |
| [PostgreSQL](https://github.com/postgres/postgres) | Transactional persistence | PostgreSQL License | **adopt** | Preferred production persistence direction when concurrency/operations require graduating the existing SQLite prototype; recommendation is not an accepted migration. |
| [Temporal](https://github.com/temporalio/temporal) | Durable application workflows | MIT | **research** | Defer until existing worker/job design has a demonstrated durability or orchestration gap. |
| [DuckDB](https://github.com/duckdb/duckdb) | Research analytics | MIT | **research** | Useful later analytical projection; not another operational source of truth. |
| [Keycloak](https://github.com/keycloak/keycloak) | Identity | Apache-2.0 | **integrate** | Strong IdP candidate when the chosen backend does not already meet required identity flows. |
| [OpenFGA](https://github.com/openfga/openfga) | Relationship authorization | Apache-2.0 | **research** | Promising when delegated/care-team relationships exceed simple policy; retain deterministic first-party checks. |
| [React / React DOM](https://github.com/react/react) | First-party UI | MIT | **adopt** | Preferred candidate for bounded first-party UI increments after exact dependency approval; retain working domain/API and proven journeys. |
| [Vite](https://github.com/vitejs/vite) | UI build tooling | MIT core; bundled notices include BSD-2-Clause, CC0-1.0, ISC, MIT | **adopt** | Preferred build candidate for React UI when the UI increment is accepted; no Next.js dependency. |
| [Mantine](https://github.com/mantinedev/mantine) | React UI components | MIT | **research** | Practical if reusing qualified Medplum React widgets; compare with the existing #127 Radix/TanStack direction before selecting one UI system. |

## Candidate evidence and integration boundaries

### 1. Medplum core / selected SDKs

**Purpose and useful capabilities:** FHIR server, TypeScript client/types, React clinical components, authentication and automation primitives. **Technology:** TypeScript / Node.js / React; backend deployment is a separate role from SDK reuse.

**Version / source evidence:** Historical evaluation pin v5.2.11, source 42bc8d0ae9e6d3c81b852cf90de7128c851a12d2; installed @medplum/core 5.2.11 re-read. 29-Oct exact source/NOTICE audit reused. 2-Nov independently re-read installed 5.2.11 LICENSE.txt SHA-256 0477dcb7f150cb9de1a9f4f6cfa0e1eb7f6ba3d3920cf6636b7876abdfc6486c and current official LICENSE. Exact source URL fetch failed this pass; no fresh source-byte claim.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — FHIR resources and import/export adapters map to the existing case/source/assertion/review contracts. Compare app-owned domain plus adapters with a Medplum-backed implementation using identical correction, isolation and export cases. Existing scope: OI-004, OI-005; source/version and clinical exchange contracts.

**Maturity and limitations:** Established client/server project; an earlier trimmed UI probe built and typechecked locally on 29-Oct. No current product deployment or tenancy qualification. The external probe does not validate the current repository. Server operations, authorization, source-to-resource reconciliation and exit/export behavior require measurement.

**Separate rights and dependency boundary:** Preserve Apache LICENSE/NOTICE and modification attribution. Core builds can prebundle third-party code. Examples include clinical terminology, logos, photos, service adapters and hosted auth; do not import whole demos. Code license does not license hosted CPT, SNOMED, provider services or patient data. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/medplum/medplum/blob/main/LICENSE.txt); [2](https://github.com/medplum/medplum/blob/42bc8d0ae9e6d3c81b852cf90de7128c851a12d2/NOTICE); [3](https://github.com/medplum/medplum/blob/main/README.md).

### 2. HAPI FHIR

**Purpose and useful capabilities:** Java FHIR client/server libraries, persistence modules and validation infrastructure. **Technology:** Java / Maven; FHIR server or client modules.

**Version / source evidence:** No new release selected. Current master LICENSE rechecked; defer to PR #125 exact-source receipt for its specific inspected commit. Official actual LICENSE.txt inspected 2-Nov; root LICENSE is not an audit of a chosen Maven distribution.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Use one server candidate in the same OI-005 bake-off. Keep questions, rights, publication state and provenance in existing first-party contracts. Existing scope: OI-004, OI-005; FHIR interchange.

**Maturity and limitations:** Established FHIR ecosystem; no project-specific deployment, throughput or operational test. A FHIR server does not supply oncology reconciliation, case UX, record completeness or production authorization configuration.

**Separate rights and dependency boundary:** Pin Maven modules and all transitives; vocabulary packs, implementation guides, extensions and terminology services have distinct rights. Preserve Apache notices. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/hapifhir/hapi-fhir/blob/master/LICENSE.txt); [2](https://github.com/hapifhir/hapi-fhir); [3](https://hapifhir.io/).

### 3. OpenELIS Global 2

**Purpose and useful capabilities:** Laboratory accessioning, orders, analyzer interfaces and result workflows; useful LIS/pathology workflow reference. **Technology:** Java / Spring; React Carbon UI; Docker deployment.

**Version / source evidence:** No version selected. Current develop repository and release metadata inspected; exact release LICENSE still unresolved here. Official repository identifies MPL-2.0 and release notes record canonical LICENSE correction. Actual LICENSE retrieval failed; no new exact-file verification claimed.

**Commercial / modification / self-hosting:** Commercial use can be permitted; MPL obligations require separate review. Permitted; distributed modified covered files remain subject to MPL source obligations. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **hold** — Model first-party sample/accession/result workflows on owned contracts. Explore a defined result exchange when a laboratory partner requires it; external integration is not a license exemption. Existing scope: OI-17 rights policy; specimen/assay/result contracts; first-party LIS scope.

**Maturity and limitations:** Active project with laboratory workflow scope, based on owner repository; deployment and compliance claims not independently validated. Do not assume a LIS also supplies biobanking, omics assets or every instrument. No equally broad permissive substitute was established in this pass.

**Separate rights and dependency boundary:** MPL is file-level copyleft, not MIT/Apache. Pin covered files, modifications, notices, deployment/distribution mode and all dependencies. Samples, clinical terms and analyzer-specific interfaces need separate rights. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/DIGI-UW/OpenELIS-Global-2); [2](https://github.com/DIGI-UW/OpenELIS-Global-2/releases); [3](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).

### 4. OHIF Viewer

**Purpose and useful capabilities:** DICOMweb image review, 2D/3D views, measurements, segmentations and extension modes. **Technology:** TypeScript / React; browser viewer with DICOMweb integration.

**Version / source evidence:** No production release selected. v3.14.0-beta.68 appeared in release list; explicitly a prerelease, not a recommended stable pin. Use PR #125 exact-source receipt for its inspected commit. Actual master LICENSE text independently rechecked 2-Nov. Release list inspected; selected stable release and final codecs not verified.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **integrate** — First-party study navigation opens a scoped viewer with case, study, series, instance and version context. Persist approved annotations and source references through existing asset/review contracts. Existing scope: Biological asset provenance; source identity; image-review adapter.

**Maturity and limitations:** Established extensible viewer with ongoing releases; no use-specific diagnostic validation performed. Viewer is not PACS storage/custody or a regulatory clearance for the combined product. Measurements, hanging protocols and authentication integration need tests.

**Separate rights and dependency boundary:** MIT covers inspected source. Inspect Cornerstone packages, native/WASM codecs, extensions, sample DICOM, fonts and images in exact final bundle. Medical images and clinical use rights remain separate. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/OHIF/Viewers/blob/master/LICENSE); [2](https://github.com/OHIF/Viewers); [3](https://github.com/OHIF/Viewers/releases).

### 5. highdicom

**Purpose and useful capabilities:** Read spatial DICOM objects and write derived segmentations, parametric maps, annotations and structured reports. **Technology:** Python library built on pydicom / NumPy.

**Version / source evidence:** v0.28.2 resolves to 847fea5946b4be9cf0c9939b8f9dcbf0bc60b24d from official release/commit page; candidate only. Current master LICENSE actual text rechecked; release commit independently resolved 2-Nov. Pinned LICENSE fetch failed, so license-to-pin equality is NOT established.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **integrate** — Create source-linked DICOM SEG/SR results as derived assets; never overwrite original study. Preserve coordinate frame, algorithm/run version, units and reviewer decision. Existing scope: Biological asset provenance; derived-output/source lineage.

**Maturity and limitations:** Specialist DICOM library with release stream; no project-specific spatial/codec test. Syntactically valid DICOM can still carry wrong coordinates, units, source references or biological context.

**Separate rights and dependency boundary:** Source MIT does not clear pydicom dictionaries, optional pixel decoders or packaged test images. The existing #125 pydicom audit must be consulted for GDCM-derived dictionary and codec obligations. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/ImagingDataCommons/highdicom/blob/master/LICENSE); [2](https://github.com/ImagingDataCommons/highdicom); [3](https://github.com/ImagingDataCommons/highdicom/commit/847fea5946b4be9cf0c9939b8f9dcbf0bc60b24d).

### 6. DICOM Microscopy Viewer

**Purpose and useful capabilities:** Whole-slide DICOM browser viewing, ROI annotations, overlays and multichannel visualization. **Technology:** JavaScript / OpenLayers library; DICOMweb client; not itself a complete viewer app.

**Version / source evidence:** No tag selected; master LICENSE and README inspected 2-Nov. Actual LICENSE independently read 2-Nov; no pinned npm/WASM release audit.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Wrap in the same case/specimen/slide context and authorization boundary; record annotations as derived assets. A separate first-party pathology workflow must still handle accession and review. Existing scope: Specimen/slide assets; image-review adapter; first-party pathology scope.

**Maturity and limitations:** Specialized viewer library with documented DICOM WSI and annotation support; integration untested. Requires DICOMweb-ready slides. Vendor-native WSI conversion, large-file serving, color fidelity and performance remain engineering work.

**Separate rights and dependency boundary:** MIT source does not clear compiled JPEG/JPEG-LS/JPEG2000/HTJ2K/JPEG XL codecs, ICC profiles or test slides. Inspect exact bundle and content provenance. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/ImagingDataCommons/dicom-microscopy-viewer/blob/master/LICENSE); [2](https://github.com/ImagingDataCommons/dicom-microscopy-viewer).

### 7. GA4GH VRS-Python

**Purpose and useful capabilities:** Typed variation representations, normalization, deterministic identifiers and translation to/from variant formats. **Technology:** Python / Pydantic; reference-sequence resolution dependencies.

**Version / source evidence:** No release selected. Main LICENSE and README inspected 2-Nov; pin VRS schema, implementation and reference resolver together. Actual official LICENSE independently rechecked; no chosen wheel or reference-data artifact inspected.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **integrate** — Link normalized identifier to the original reported variant, reference assembly/sequence, transcript, specimen, assay and source version. Retain original representation. Existing scope: Biological asset provenance; variant identity and source assertions.

**Maturity and limitations:** Standards reference implementation; evolving schema and sequence dependencies need explicit pins. Identifier equivalence is not pathogenicity, somatic/germline status, clonality, actionability or evidence of a correctly bound patient sample.

**Separate rights and dependency boundary:** Source Apache license is separate from sequences, annotation databases, caches and external services. Review selected dependency graph and preserve notices. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/ga4gh/vrs-python/blob/main/LICENSE); [2](https://github.com/ga4gh/vrs-python).

### 8. Ensembl VEP

**Purpose and useful capabilities:** Transcript-aware variant consequence annotation and extensible annotation pipeline. **Technology:** Perl / Ensembl APIs; local caches and optional plugins.

**Version / source evidence:** release/116 branch inspected; this is mutable, not an immutable release pin. Exact commit/cache selection deferred. Actual release/116 LICENSE and relevant INSTALL.pl source inspected 2-Nov.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Worker consumes authorized normalized variants and emits versioned consequence proposals with reference/annotation/plugin versions, QC and retained source variants. Existing scope: Assay/reference/run provenance; bounded genomic analysis.

**Maturity and limitations:** Established bioinformatics tool; no assay-specific benchmark or analytical validation performed. Consequence predictions are not a clinical pathogenicity or treatment decision. Transcript and assembly choice can change output.

**Separate rights and dependency boundary:** Installer downloads additional libraries, caches and optional plugins. Software Apache rights do not settle dbNSFP, commercial annotations, transcript/reference data or every plugin. Review actual downloaded artifacts. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/Ensembl/ensembl-vep/blob/release/116/LICENSE); [2](https://github.com/Ensembl/ensembl-vep/blob/release/116/INSTALL.pl); [3](https://github.com/Ensembl/ensembl-vep).

### 9. CIViC

**Purpose and useful capabilities:** Curated variant/molecular-profile evidence and assertions linked to disease, therapy and published sources. **Technology:** Versioned data/API integration; full application code is optional.

**Version / source evidence:** No snapshot or application commit selected. Pin each imported release/export with retrieval date and checksum. Official documentation independently rechecked 2-Nov for separate code and data grants. Application LICENSE retrieval failed; do not claim fresh exact code-file verification.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **integrate** — Import curated evidence as source-specific evidence items; preserve assertion IDs, review state, evidence direction/type, cancer context and supporting citations. Apply the existing rights broker and applicability/review contracts. Existing scope: Rights broker; evidence/applicability; investigation Composer.

**Maturity and limitations:** Established community curation source; evidence strength remains assertion-specific. No project-specific clinical evaluation. Database entries do not grant full-text article access and do not establish patient eligibility or a treatment recommendation. Contradictory evidence must remain visible.

**Separate rights and dependency boundary:** CC0 applies to curated CIViC content, not every linked publication or all branding. Official graphics documentation distinguishes branding from other figures. Full application dependencies/fixtures are out of scope. **Full dependency clearance: not established.**

**Official evidence:** [1](https://docs.civicdb.org/en/latest/about/faq.html); [2](https://docs.civicdb.org/en/latest/about/participating.html); [3](https://docs.civicdb.org/en/latest/about/figures.html).

### 10. Docling

**Purpose and useful capabilities:** Document parsing, layout/table extraction and structured output suitable for anchored extraction proposals. **Technology:** Python; configurable parsers, OCR and model pipelines.

**Version / source evidence:** v2.145.0 resolves to 45d334e33f7aca345fc26880777288b8cd14262d; candidate only, not selected production version. Actual current LICENSE rechecked 2-Nov and official release commit resolved. Pinned LICENSE fetch failed; equality with current LICENSE is NOT established.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Worker preserves original bytes and emits candidate text/table spans, coordinates, confidence/abstention and run metadata into existing source/extraction review contracts. Existing scope: OI-006/OI-007 source/extraction; source anchors; evaluation.

**Maturity and limitations:** Active parser project with frequent releases; no oncology document test executed here. Must measure decimals, inequality signs, units, negation, table-cell associations, OCR omissions and amendment handling. Parser output is a proposal, not a clinical fact.

**Separate rights and dependency boundary:** MIT code does not license every OCR/VLM/table model, model weight, tokenizer, backend, CUDA runtime or input document. Select exact local pipeline and rights-qualified models; remote-provider services remain separate. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/docling-project/docling/blob/main/LICENSE); [2](https://github.com/docling-project/docling/blob/main/README.md); [3](https://github.com/docling-project/docling/commit/45d334e33f7aca345fc26880777288b8cd14262d).

### 11. medSpaCy

**Purpose and useful capabilities:** Section detection, clinical concept rules, negation and contextual attributes. **Technology:** Python / spaCy; rules and optional NLP/terminology resources.

**Version / source evidence:** 1.3.1 appears as latest release in inspected repository (21-Nov-2024); tag/license equality and supported dependency matrix need confirmation. Actual master LICENSE rechecked 2-Nov; official README/release page identifies 1.3.1. Pinned LICENSE fetch failed.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **extend** — Apply reviewed task-specific rules to extracted text; propose contextual labels with exact spans. Keep unknown, negative, pending and conflicting separate and reviewable. Existing scope: Source assertions; missingness/negation; extraction evaluation.

**Maturity and limitations:** Specialized library with published release; latest listed release is older than other candidates. No maintenance support guarantee inferred. Rules are language/institution/domain dependent; context scope errors can invert clinical meaning. Compare with simple rules and an LLM on identical cases.

**Separate rights and dependency boundary:** MIT library does not automatically license spaCy model weights, UMLS/QuickUMLS dictionaries, external language rules, training corpora or terms. Pin optional modules and model cards. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/medspacy/medspacy/blob/master/LICENSE); [2](https://github.com/medspacy/medspacy); [3](https://github.com/medspacy/medspacy/releases).

### 12. PydanticAI

**Purpose and useful capabilities:** Typed model/tool interfaces, structured results and provider adapters for bounded AI tasks. **Technology:** Python / Pydantic.

**Version / source evidence:** No release selected; current main LICENSE/README inspected 2-Nov. Actual official LICENSE independently checked; extras/provider SDKs and model terms not audited.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — A replaceable model adapter receives typed permitted inputs and returns proposals through existing investigation/review contracts. First-party software retains authorization, citations and publication control. Existing scope: Model task contracts; allowed tools; investigation proposals.

**Maturity and limitations:** Active agent library; no task-specific reliability or integration test performed. Schema conformity is not truth. Tool retries, prompt injection, source leakage, cancellation and wrong-case isolation require explicit tests.

**Separate rights and dependency boundary:** MIT source is separate from model/API terms, weights, training rights, observability hosting and each provider SDK. Keep telemetry/input routing governed by the existing rights boundary. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/pydantic/pydantic-ai/blob/main/LICENSE); [2](https://github.com/pydantic/pydantic-ai/blob/main/README.md).

### 13. PostgreSQL

**Purpose and useful capabilities:** Relational transactions, indexes, structured/lexical search and durable case/review history. **Technology:** C database server; SQL; multiple application drivers.

**Version / source evidence:** No production major/minor selected. Current official license inspected; version choice requires supported deployment constraints and migration test. Actual official license grant independently read 2-Nov; no binary/container/extension SBOM inspected.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **adopt** — Implement storage adapter preserving current identifiers, source versions, as-known-at queries, review decisions and transaction boundaries. Reuse existing contract tests. Existing scope: OI-005 persistence; existing SQLite/domain contracts.

**Maturity and limitations:** Established database project; this application has not been migrated or recovery-tested. Database choice alone does not implement tenant isolation, temporal semantics, backups, encryption, audit integrity or revocation.

**Separate rights and dependency boundary:** Core permissive license does not clear drivers, extensions, packaged OS/container content or managed-service agreements. Preserve notices in redistributed copies. **Full dependency clearance: not established.**

**Official evidence:** [1](https://www.postgresql.org/about/licence/); [2](https://github.com/postgres/postgres).

### 14. Temporal

**Purpose and useful capabilities:** Durable workflow history, retries, timers and recovery for long-running processing. **Technology:** Go server; separate language SDKs and persistence services.

**Version / source evidence:** No release selected; main server LICENSE/README independently inspected 2-Nov. Actual server LICENSE rechecked; SDKs, UI, container image and hosted service not audited.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Drive bounded processing runs keyed by immutable input versions; persist canonical sources/reviews in existing domain. Recheck authority before effects and after resume. Existing scope: Run/task/dependency contract; durable processing.

**Maturity and limitations:** Established workflow server project; no deployment/operational benchmark for Open Intelligence. Adds operational footprint; workflow replay/determinism, duplicate effects, cancellation and version migration remain application duties. Not a scientific pipeline substitute by default.

**Separate rights and dependency boundary:** MIT server code is not blanket clearance for SDKs, bundled UI, monitoring, dependencies or Temporal Cloud terms. Job histories may contain sensitive payloads requiring controlled retention. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/temporalio/temporal/blob/main/LICENSE); [2](https://github.com/temporalio/temporal/blob/main/README.md).

### 15. DuckDB

**Purpose and useful capabilities:** Embedded analytical SQL over columnar/local research extracts. **Technology:** C++ engine; Python and other bindings.

**Version / source evidence:** No version selected; main LICENSE/README inspected 2-Nov. Actual permission text inspected 2-Nov (file does not need an MIT title to contain the MIT grant); no release artifact or extensions audited.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Read permission-scoped, versioned extracts from the existing governed data model; retain lineage and expiry/revocation rules for generated files. Existing scope: Derived analytics; rights and export lineage.

**Maturity and limitations:** Established analytics engine; no Open Intelligence workload benchmark. Copying records into local files can bypass access/revocation semantics unless explicitly controlled. Avoid duplicating operational state.

**Separate rights and dependency boundary:** MIT core is separate from extensions, connectors, downloaded artifacts and dataset rights. Disable unnecessary network/extension paths for sensitive analysis. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/duckdb/duckdb/blob/main/LICENSE); [2](https://github.com/duckdb/duckdb).

### 16. Keycloak

**Purpose and useful capabilities:** OIDC/OAuth authentication, federation, users and session administration. **Technology:** Java server; web admin/account UI.

**Version / source evidence:** No version selected; main LICENSE actual text rechecked 2-Nov. Official source LICENSE checked; no container, extension or production configuration audit.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **integrate** — Authenticate humans/services into first-party authority contracts. Keep patient matching, caregiver delegation, consent and clinician-role verification separately governed. Existing scope: Authority grants; patient/proxy identity; authentication.

**Maturity and limitations:** Established IAM project; no project-specific failover, tenant or account-lifecycle test. Authentication does not verify clinical credentials, patient identity or purpose authorization. Avoid operating redundant identity systems without a need.

**Separate rights and dependency boundary:** Core Apache license is separate from providers/themes, imported branding, Java/container dependencies and external identity contracts. Preserve notices. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/keycloak/keycloak/blob/main/LICENSE.txt); [2](https://github.com/keycloak/keycloak).

### 17. OpenFGA

**Purpose and useful capabilities:** Relationship-based authorization evaluation for granular access decisions. **Technology:** Go service; relationship model/tuples and client SDKs.

**Version / source evidence:** No version selected; main LICENSE independently inspected 2-Nov. Actual official LICENSE rechecked; no release, SDK or deployment artifact closure.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Derive relationship tuples from authoritative grants. Enforce purpose, expiry, consent, source-specific rights and reviewer authority at tools/jobs/exports; handle stale tuples and revocation. Existing scope: Authority/consent; rights broker; export/job enforcement.

**Maturity and limitations:** Established authorization project; healthcare delegation semantics untested here. A graph relation does not by itself encode consent validity, clinician competence, emergency access policy or licensed content rights.

**Separate rights and dependency boundary:** Apache server license does not clear every client SDK, datastore or deployment package. Audit full selected graph and preserve notices. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/openfga/openfga/blob/main/LICENSE); [2](https://github.com/openfga/openfga).

### 18. React / React DOM

**Purpose and useful capabilities:** Component UI and browser rendering for patient, caregiver and professional workflows. **Technology:** JavaScript / TypeScript application components.

**Version / source evidence:** Historical evaluated npm react and react-dom 19.2.0; exact installed package files re-read 2-Nov. Not a current-version recommendation. Actual installed 19.2.0 LICENSE SHA-256 da6d3703ed11cbe42bd212c725957c98da23cbff1998c05fa4b3d976d1a58e93 independently rechecked; official current LICENSE also retrieved.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **adopt** — Introduce components over existing case, source, investigation and review APIs. Keep canonical state on the same contracts. No Next.js for new development. Existing scope: Patient/clinician presentation; current UI journeys.

**Maturity and limitations:** Established UI library; prior quarantined probe built/typechecked, not a validated production UI. Component choice does not ensure accessibility, patient comprehension, source traceability or safe clinical interaction. Preserve keyboard, zoom, mobile and amendment journeys.

**Separate rights and dependency boundary:** Inspect chosen React DOM/scheduler and build graph. Sample apps, icons, images and fonts need their own grants. Preserve MIT notices; no automatic rights to vendor branding. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/react/react/blob/main/LICENSE); [2](https://github.com/react/react).

### 19. Vite

**Purpose and useful capabilities:** Frontend development/build tool for a React/TypeScript first-party app. **Technology:** TypeScript / Node.js; bundler/plugins.

**Version / source evidence:** Historical evaluated npm vite 7.3.7; installed LICENSE.md re-read 2-Nov. Defer to PR #125 for its separate exact source commit. Actual installed 7.3.7 LICENSE.md SHA-256 a77a1c089806b39ad339535bdf3677f636c91d96693e8ad7b11fe733f650ea64 rechecked including bundled-license preamble; current official package LICENSE retrieved.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **adopt** — Build static first-party UI assets against existing APIs; distinguish build-tool distribution from shipped browser dependencies. Existing scope: UI tooling; OI-004 exact artifact inventory.

**Maturity and limitations:** Established build tool; historical probe build succeeded, not a current-stack or security certification. Pin Node, plugins and lockfile. A successful build does not establish production source-map handling, dev-server safety or complete bundle provenance.

**Separate rights and dependency boundary:** The package contains third-party bundled notices beyond root MIT. Preserve applicable combined license artifact; inspect plugins/native binaries separately. A source map is evidence, not complete proof of dependency closure. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/vitejs/vite/blob/main/packages/vite/LICENSE.md); [2](https://github.com/vitejs/vite).

### 20. Mantine

**Purpose and useful capabilities:** UI controls, forms/layout primitives, hooks and optional notifications/search components. **Technology:** TypeScript / React / CSS.

**Version / source evidence:** Historical evaluated @mantine/core and related packages 8.3.18; exact core LICENSE re-read 2-Nov. Installed @mantine/core 8.3.18 LICENSE SHA-256 61c765e625bc25d55143f14de7554685c52f21d9e671d3d204304691a163d06a independently checked; current upstream LICENSE also retrieved.

**Commercial / modification / self-hosting:** Permitted by inspected source license, subject to obligations and separate rights. Permitted by source license; retain required notices. Source permits self-hosting; operations and service/data rights remain separate.

**Integration and recommendation:** **research** — Use selected components within first-party design tokens and task flows. A component kit must not define clinical authority or patient-state semantics. Existing scope: First-party presentation; source drilldown and review UX.

**Maturity and limitations:** Established component project; historical probe demonstrated compilation only. Avoid simultaneously adopting multiple overlapping component libraries. Task-specific accessibility, data density and disclosure rules need user-journey verification.

**Separate rights and dependency boundary:** MIT core does not clear all hooks/component dependencies, separately supplied icons, templates or fonts. Historical 118-package probe remains quarantined and aggregate notices were incomplete. **Full dependency clearance: not established.**

**Official evidence:** [1](https://github.com/mantinedev/mantine/blob/master/LICENSE); [2](https://github.com/mantinedev/mantine).

## Gaps, corrections and exclusions to preserve

- **First-party LIS and comprehensive EHR functions:** no whole-product permissive replacement was established. Reuse FHIR primitives and build the owned operational workflows incrementally. OpenELIS is held for incorporated reuse under the existing commercial policy; its useful workflow ideas do not erase its license.
- **PACS archive/custody:** OHIF and microscopy viewers solve presentation. Archive ownership, retrieval, retention, authorization, data migration and recovery require separate qualification. The existing #127 screen's SeaweedFS investigation remains a candidate, not a completed selection.
- **Scientific workflow engine:** Temporal addresses durable application jobs. Retain the existing Snakemake/Nextflow comparison for assay pipelines; do not pick Temporal as a substitute without an actual task comparison.
- **Models and scientific datasets:** no model/checkpoint is adopted by this appendix. Docling, medSpaCy, MONAI, pathology and genomics code licenses do not propagate to weights, datasets, reference panels, terminology or annotation sources. No autonomous diagnosis/treatment recommendation follows from a structured result.
- **Licensed clinical knowledge:** CIViC's CC0 content does not clear linked article full text. NCCN, ASCO, ESMO, AJCC, CAP, SNOMED/UMLS, LOINC, RxNorm subsets and instruments remain exact content/use reviews in the existing register. Do not label all terminology as the same type of restricted or permissive content.
- **Synthea and demo fixtures:** the 29-Oct source audit found terminology and other notices, plus examples carrying service/branding content. Synthetic clinical data can still embed licensed terminology. Authoring original fictional fixtures avoids importing those payloads by default.
- **Source-license metadata:** a missing license field is unresolved evidence, not proof of unlicensed code. A root MIT/Apache file or passing scan is not a full product clearance. Conversely, a copyleft dependency somewhere in a monorepo does not prove it ships in the selected browser bundle; assess the actual artifact.
- **No Next.js:** excluded for new development by direction, independent of its source license. Existing React/Vite, Radix/TanStack and Mantine alternatives should be evaluated against the same UI journeys rather than accumulating overlapping kits.

## Concrete acceptance for the next reuse increments

| Increment | Smallest demonstrable outcome | Evidence needed before advancing |
|---|---|---|
| Evidence to investigation | A permitted versioned evidence item can be attached to a durable question, inspected and reviewed; missing/revoked rights visibly block inappropriate use | Contract tests for version binding, case isolation, changed/revoked rights, exact evidence anchors and no automatic clinical promotion |
| Document extraction | One synthetic original and amendment produce inspectable span/table proposals with retained originals | Correct units/inequalities/negation/table context; extraction error taxonomy; measured abstention/review burden; exact pipeline and model manifest |
| React UI increment | Patient and reviewer can follow a supported statement to the original version and create/resolve a scoped review task | Existing workflow parity, keyboard and 200% zoom, narrow-screen usability, patient wording and stale/amended source behavior; exact build artifact notices |
| CIViC adapter | A pinned export/API item is stored with identifier, molecular context, evidence direction and citation/applicability | Data/code rights recorded separately, update/deduplication and contradiction handling, source version replay, no unsupported patient actionability claim |
| FHIR comparison | The same fictional case and amendment pass import, isolation, review and export through each candidate | Operational/extension effort measured; preserved originals and identifiers; exact-release obligations; reversible data export and no silent patient merge |

## Evidence limitations

This pass is an audit of existing research plus primary-source spot checks, not a full supply-chain or security audit. Public web retrieval succeeded for current official license text but several pinned file URLs failed; no result has been silently upgraded from branch evidence to immutable evidence. Ordinary network access was unavailable in this subtask, and the GitHub fetch connector reported an unavailable tool. The fresh #127 screen was read from the root-supplied local copy; its assertions about #125 are attributed to that document rather than independently revalidated here.

The companion `technology-atlas.json` carries each candidate's version, technology, rights boundaries, recommendation and evidence state. It is an interim research matrix for merging into the existing register, not a new canonical adoption ledger. Use exact-source receipts, lockfiles, tarball/image checksums, shipped assets/models/data, notices and selected deployment modes when a concrete dependency trial is opened. No complete dependency graph or final bundle is cleared by this document.
