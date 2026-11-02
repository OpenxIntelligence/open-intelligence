# Open Intelligence — OSS technology and licensing audit, Wave 1

**As of 2026-11-02. Status: audited upstream *root license files*, not release/stack clearance.** Supplemental to established [OI-17 and issue #59](https://github.com/OpenxIntelligence/open-intelligence/issues/59) and the existing technology register. No new third-party code is introduced by this research branch; no architecture is replaced. **None** of the candidates is yet legally or technically approved for adoption.

## Security and license decision rule

Use `BUILD`, `ADOPT`, `EXTEND`, `INTEGRATE`, `RESEARCH`, `HOLD`, `REJECT`. `ADOPT` and `EXTEND` are prohibited without an actual release/tag pin, exact package/submodule inventory, transitive runtime + dev SBOM, bundled native binary and asset inspection, trademark/patent review, vulnerability review, and separate dataset/model/terminology-content rights. A checked root `LICENSE` is **necessary but insufficient**. An OSS license permitting commercial use does not imply clinical, HIPAA, GDPR, regulatory or operational fitness. This is not a legal opinion.

`docs/research/OSS_LICENSE_DISCOVERY_WAVE1.json` is the machine-readable inspected-source record. The `source_commit` captures the upstream branch HEAD at the time of inspection (not an endorsed or pinned release); `license_blob_sha` identifies the LICENSE bytes. Re-inspect the actual chosen version and all dependencies before using anything.

## Inspectable primary-source license reconnaissance

| Candidate and role | Root source license observed | Upstream exact source commit and file | Decision | Unresolved |
|---|---|---|---|---|
| [Medplum](https://github.com/medplum/medplum) — FHIR/API/React libraries | Apache-2.0 | [`217e248` LICENSE.txt](https://github.com/medplum/medplum/blob/217e248256cd98e9f1e08b2564412cb00006f319/LICENSE.txt) | RESEARCH | Hosted features, package boundaries, transitive SBOM, first-party identity/evidence ownership |
| [HAPI FHIR](https://github.com/hapifhir/hapi-fhir) — FHIR client/server | Apache-2.0 | [`f3cbac3` LICENSE.txt](https://github.com/hapifhir/hapi-fhir/blob/f3cbac3b7788a2b71ca5614d8e18599d00fb0d4a/LICENSE.txt) | RESEARCH | Java deployment complexity, Maven modules, maintenance/operational fit, exact library graph |
| [OHIF Viewer](https://github.com/OHIF/Viewers) — image display | MIT | [`51e301d` LICENSE](https://github.com/OHIF/Viewers/blob/51e301d1460206c2cf946eeda08207bbe49d3993/LICENSE) | RESEARCH | Viewer does NOT constitute PACS archive/RIS; extensions, decoders/assets, build/runtime graph |
| [pydicom](https://github.com/pydicom/pydicom) — DICOM parsing | Primarily MIT; GDCM-derived private dictionaries have separately stated BSD-like terms | [`413945f` LICENSE](https://github.com/pydicom/pydicom/blob/413945fee751a4260c567e1bf8377adfc37ba6ba/LICENSE) | RESEARCH | Optional pixel codecs can change license profile; maintain asset/codec matrix, avoid GPL extra unless reviewed |
| [MONAI](https://github.com/Project-MONAI/MONAI) — medical imaging AI research | Apache-2.0 | [`5b7e314` LICENSE](https://github.com/Project-MONAI/MONAI/blob/5b7e3149332ff2ee2a686e236b9e62b1238dc413/LICENSE) | RESEARCH | Model weights, datasets, pretraining, PyTorch/native dependencies and clinical validation NOT cleared |
| [Orthanc](https://github.com/orthanc-mirrors/orthanc) — DICOM server/PACS candidate | GPLv3 core, LGPL/BSD subcomponent distinctions | [`3d3c441` COPYING](https://github.com/orthanc-mirrors/orthanc/blob/3d3c441847cc26e43125623602828a9ec6dd853f/COPYING), [upstream licensing explanation](https://orthanc.uclouvain.be/book/faq/licensing.html) | HOLD | Legal review of actual deployment/integration/distribution/plugin modes; do NOT simplistically claim GPL forbids all commercial use |
| [FastAPI](https://github.com/fastapi/fastapi) — Python APIs | MIT | [`5cb6272` LICENSE](https://github.com/fastapi/fastapi/blob/5cb6272ed7e3e07eaf6978e1e65b94aca76fa8e0/LICENSE) | RESEARCH | Exact FastAPI/Starlette/Pydantic stack, auth/security, API schema contract and packaging |
| [Vite](https://github.com/vitejs/vite) — TS/React build | MIT | [`b3cb057` LICENSE](https://github.com/vitejs/vite/blob/b3cb0575aff63004a71301a1ec798aeea2aa05d7/LICENSE) | RESEARCH | npm transitive SBOM, assets and deployment; Next.js excluded by founder |

**License facts, not adoption clearance:** These upstream files were inspected with exact commit and blob identifiers. Neither dependency installation nor a software composition scan was performed against them, and no vulnerabilities, submodule rights, clinical validations or model weights were cleared. Avoid advertising the candidates as commercially *approved* from this table.

## Twenty-domain technology inventory: investigate, do not prematurely install

This is a broad **coverage register**, not 20 architectural decisions. Only the eight above have direct root-license inspections this wave. Every remaining candidate is `DISCOVERED/UNVERIFIED` unless independently checked against its exact version.

| Domain | Candidates / discovery leads | Open Intelligence boundary |
|---|---|---|
| A. Application UI/API | React, Vite, FastAPI, Pydantic, Radix UI, TanStack | One task-first patient/clinician workspace; first-party domain contracts |
| B. EHR / FHIR | Medplum, HAPI FHIR, Blaze, Microsoft FHIR Server | FHIR exchange distinct from actual EHR/clinical signature |
| C. Oncology | OHDSI oncology tools, mCODE implementation guides, cancer registry tooling | Disease episodes, staging, treatment history owned by OI |
| D. LIS / LIMS | OpenELIS, OpenMRS laboratory extensions, first-party LIS PR #56 | Real accession/QC/release vs unordered lab data import |
| E. Computational pathology | OpenSlide, TIAToolbox, PathML | Whole-slide input and model conclusions require versioned provenance |
| F. Imaging / PACS | OHIF, Cornerstone3D, pydicom, DCMTK, ITK, Orthanc | Viewer, decoder, PACS archive and RIS are distinct products |
| G. Genomics / bioinformatics | Biopython, HTSlib, samtools, bcftools, VEP, GATK, DeepVariant, Nextflow, Scanpy | Source build/transcript/assay provenance and sample rights |
| H. Terminology / biomedical knowledge | FHIR terminology tooling, OMOP/OHDSI, MONDO, HPO, RxNorm, SNOMED tooling | Terminology contents separately licensed; normalize without false matches |
| I. Evidence / scientific retrieval | PubMed/Europe PMC APIs, OpenAlex, GROBID, citation managers | DOI metadata ≠ full-text rights; specific AI use rights |
| J. AI/agents/eval | MLflow, PydanticAI, LangGraph, vLLM, Transformers, OpenTelemetry | OI-owned durable investigation, versioned source receipts, human review |
| K. Databases / search | PostgreSQL, SQLite existing, pgvector, OpenSearch, DuckDB | Structured-first initial retrieval; exact operational state ownership |
| L. Durable orchestration | Temporal, Celery, Dagster, Airflow, Prefect | Durable commands and audit; avoid opaque agent-side clinical writes |
| M. Identity / consent / security | Keycloak, OpenFGA, OPA, Cedar, Vault-like systems | Patient identity, delegated rights and consent are first-party truth |
| N. Document ingest | Apache Tika, OCRmyPDF, PDF tooling, FHIR HL7 transforms | Retain original bytes, citations, source version and transformations |
| O. Visualization | OHIF, medical timeline libraries, Plotly, Vega-Lite, Cytoscape | Low-noise patient context; authoritative clinical provenance |
| P. Testing / validation | Playwright, pytest, Hypothesis, Schemathesis, synthetic FHIR generators | Synthetic only until actual privacy/security clearance |
| Q. DevOps | OpenTelemetry, Prometheus, container runtimes, Terraform, CI scanners | Self-hosted deployments, security, restore, exact release evidence |
| R. Patient accessibility | React Aria, i18n tooling, WCAG audit utilities | Accessibility and human navigator handoff are baseline, not premium |
| S. Enterprise operations | Scheduling, referrals, provider directories, billing integrations | Distinguish medical orders from logistics and payments |
| T. Emerging discoveries | Multimodal/omics provenance, biomedical graph, privacy-preserving computation | Qualify value without importing data/model/tenant risk |

## Recommended minimal research-to-integration sequence

1. **Keep current first-party source/patient authority.** Do not swap in a generic FHIR EHR or another patient registry to bypass existing #85/#89/#94/#95 ownership debates. Use synthetic FHIR transformations only as an interface comparison.
2. **One viewer/parser bake-off.** Evaluate OHIF and pydicom separately using wholly invented DICOM fixtures: identity/source binding, image metadata, amendment, source/version and no unauthorized cross-patient display. Viewer and server are separate roles.
3. **One FHIR exchange bake-off.** Compare HAPI vs Medplum adapter complexity, deployment and validation against the same fictional encounter/specimen/LIS receipt without creating a second identity ledger; complete tag, SBOM and licenses **before** importing dependency into production branch.
4. **One structured evidence/Composer bake-off.** Source access + citation evidence rights + relevance + opposing evidence + review state. No biomedical model or guideline content without independently documented rights and safety evaluation.
5. **Complete OI-17 gate.** Pin package and transitive versions, produce CycloneDX/SPDX actual SBOM with evidence path for all external runtime/build/test dependencies (including `numpy/h5py` already used in *research-only* CI), scan license notices and exceptions, check advisories and patents, confirm redistribution/hosted restrictions, issue founder ADR before adoption.

## Immediate risk register

| Risk | Severity | Evidence | Closure criterion |
|---|---|---|---|
| Public-person data accidentally used in automated research | Critical | Existing main workflows had manual live routes; see [issue #122](https://github.com/OpenxIntelligence/open-intelligence/issues/122) | Synthetic-only CI branch merged, historical artifacts/logs/caches separately audited |
| Root-license mistaken for full-stack clearance | Critical | Individual LICENSE files inspected, **no** transitive SBOM | Reproducible exact-release/commit SBOM, legal review, signed OI-17 adoption ADR |
| Clinical content/terminology/model rights conflation | Critical | Scope and user mandate | Independent rights clearance per software, terminology, guideline, model weights and datasets |
| FHIR/EHR/LIS identities collapse | High | Existing [issue #87](https://github.com/OpenxIntelligence/open-intelligence/issues/87) and draft #94/#95 | Issuer-qualified patient/source/specimen contract with negative tests |
| Orthanc GPL imposed on OI proprietary derivative | High/conditional | GPL root license and distinct framework/plugin licenses | Legal assessment of actual use and code composition; hold until sign-off |
| Replacing first-party operations with view-only OSS | High | OHIF/pydicom implement viewer/parser roles, not entire PACS workflow | Domain-specific build vs adopt ADR and functional acceptance |
| Overstating patient evidence outcomes | High | Case narratives not controlled outcome studies | Patient stories remain product research, not training/evaluation datasets or efficacy proof |

## Work products still required

- Exact *release* pins (the listed commits are inspected branch heads, not releases), transitive SBOMs, trademark/patent and security advisories, versioned build reproducibility.
- Complete longlist with maintenance, runtime and financial tradeoffs, then shortlist score across functional fit, maturity, rights, maintainability, integration, security, performance, hosting, community and independence.
- Real working FHIR and DICOM synthetic bake-offs with evidence packets; no implied clinical validation.
- Independent licensing counsel sign-off where required, and recorded OI-17 founder adoption decisions. Do not call this Wave 1 survey a completed comprehensive audit.
