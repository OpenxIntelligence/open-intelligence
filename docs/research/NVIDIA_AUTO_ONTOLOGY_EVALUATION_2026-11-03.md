# Open Intelligence — NVIDIA Auto Ontology and open-source evaluation

Date: 2026-11-03. Status: research candidate and offline contract test. No vendor deployed; no PHI, clinical validation, model execution, or new canonical owner.

## Decision
Evaluate NVIDIA Auto Ontology as an OPTIONAL metadata-discovery and semantic-vocabulary layer. Do not replace the Patient World Model, source/version registry, source-linked questions, review or evidence owners. Do not give the vendor service credentials to the patient database or permit clinical text-to-SQL. A produced graph edge is an unreviewed suggestion, not clinical proof or authorization.

The inspected code-level source of truth is the existing PostgreSQL/FastAPI owner on unmerged draft PR #381 at e52898fa5661334ef5c149f6f3f73da0ac1955df, particularly its source_world_model.py and composer_preflight.py. Main is an earlier prototype. This research PR is intentionally branched from main, independent of the unmerged stack, to avoid modifying its clinical/runtime contracts.

## What NVIDIA actually ships
NVIDIA Auto Ontology is Apache-2.0 source. The 1.1.0 distribution exposes a metadata/ontology catalog, natural-language-to-SQL, a PostgreSQL/pgvector-backed store, FastAPI, Next.js, MCP and configurable inference endpoints. Code licensing does not clear NVIDIA NIM hosted services, model weights, embeddings, datasets or bundled runtimes. Its README documents two security boundaries: UI-entered connection passwords are stored in plaintext without a COMPLETE optional Vault configuration; direct internal FastAPI identity headers are trusted and the service port must stay private. Hosted inference defaults are not suitable for unapproved PHI transmission.

## Implemented first slice in this PR
- tools/semantic_contract_probe.py emits a static, deterministic catalog of APPROVED FIELD NAMES from the observed read-only source projection. No patient values, SQL schema introspection, external dependencies, database connection or model call.
- The same module checks a strict intermediate mapping-proposal envelope. Unknown concepts or fields, untrusted extra keys, injected SQL, patient values, stale manifest digests, duplicate mappings and false approval states fail closed.
- tests/test_semantic_contract_probe.py has 11 independently executed local unittest methods. These are OFFLINE contract tests; not vendor-integration, hosted CI, PostgreSQL or clinical-performance evidence.
- The intermediate contract is NOT NVIDIA Auto Ontology's native import schema; a future explicitly reviewed adapter must transform its output into this contract. No application endpoint or database schema is changed.

## Technology shortlist — do not automatically install every candidate
| Candidate | Source-code terms | Evaluation decision / relevant boundary |
| --- | --- | --- |
| NVIDIA Auto Ontology | Apache-2.0 | P0 isolated metadata pilot; no PHI, credential, SQL or external inference access |
| LinkML | Apache-2.0 | P0/P1 typed clinical-vocabulary contracts; content ontologies licensed separately |
| pySHACL | Apache-2.0 | P0/P1 graph constraint checks; SHACL conformance does not prove clinical truth |
| NeMo Relay | Apache-2.0 | Agent stage only; lifecycle hooks supplement but do not create clinical permissions |
| NeMo Fabric | Apache-2.0 | Agent stage only; replaceable harness adapters, no delegated clinical authority |
| NeMo Helix | Apache-2.0 | Evaluate agent accuracy/latency/cost on synthetic tasks |
| NeMo Guardrails | Apache-2.0 | Already in OI registry; supplemental dialogue rails, not a final clinical safety gate |
| NVIDIA FLARE | Apache-2.0 | Already in OI registry; future partner-governed federated research |
| NVIDIA BioNeMo | Code generally Apache-2.0; weights separate NVIDIA Open Model License | Research only; no patient-level treatment conclusions |
| MONAI / MONAI Deploy | Apache-2.0 source, distinct runtime/model terms | Preserve current registry reject-for-product decision; reference for imaging research |
| OHIF | MIT | Existing registry adopt candidate; implement governed viewing without unvalidated image interpretation |
| HAPI FHIR | Apache-2.0 | Existing registry interoperability candidate, not another patient clinical owner |
| Microsoft GraphRAG | Research; upstream in maintenance mode | Reference only; high indexing costs and no clinical validity assurance |
| NeMo Agent Toolkit | Apache-2.0 | Do not newly adopt; deprecated October 2026; EOL planned by end of 2026 |

## Go/no-go gates before turning the pilot into product code
1. Only schema metadata from an explicit allowlist. Never expose row values, patient IDs, source quotations, case-level access receipts, DB secrets, embeddings, telemetry, or network traces to a vendor service in the evaluation.
2. Compare at least 30 independent synthetic questions with a plain field catalog and deterministic query plan. Record mapping correctness, false merges, contradictory specimen/time cases, version updates, manual-review effort and latency/cost.
3. Check terminology and data rights per artifact, including clinical vocabularies, ontology content, NVIDIA model weights, endpoints, container third-party notices and all installed dependencies. Existing distribution license remains undecided.
4. Prove no API/FastAPI trusted-header exposure, no direct source database grant, no generated SQL execution, no prompt-injection escalation, and no clinical-status promotion. Revalidate access at each eventual source read/write boundary.
5. Before integrating with any canonical owner, reconcile PR #381 and its dependent work, run exact-head PostgreSQL/API, source amendment/review, recovery, rights, React/Chromium and security regression gates.

Go only if the semantic approach materially outperforms a simpler schema-only mapping while satisfying all safety, reproducibility, rights and maintenance gates. Otherwise keep a first-party LinkML/SHACL-compatible metadata catalog.

## Verified upstream references
- https://github.com/NVIDIA/auto-ontology
- https://nvidia.github.io/auto-ontology/
- https://catalog.ngc.nvidia.com/orgs/nvidia/-/containers/auto-ontology/1.1.0
- https://github.com/linkml/linkml
- https://github.com/RDFLib/pySHACL
- https://github.com/NVIDIA/NeMo-Relay
- https://github.com/NVIDIA/NeMo-Fabric
- https://github.com/NVIDIA-NeMo/nemo-helix
- https://github.com/NVIDIA/NeMo-Agent-Toolkit
- https://github.com/NVIDIA-BioNeMo
- https://github.com/NVIDIA/NVFlare
- https://github.com/OHIF/Viewers
- https://github.com/hapifhir/hapi-fhir
- https://github.com/Project-MONAI/monai-deploy-app-sdk
- https://github.com/microsoft/graphrag
- Internal OI: AGENTS.md, docs/FIRST_PRINCIPLES_PLAN.md, draft #381 and current open-source licensing registry.
