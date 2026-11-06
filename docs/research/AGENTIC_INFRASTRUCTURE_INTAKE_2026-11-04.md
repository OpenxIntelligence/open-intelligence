# Agentic infrastructure intake for Open Intelligence

**4 November 2026 · Research proposal · No adoption or runtime changes**

## Decision

Use the supplied infrastructure landscape to strengthen the existing patient-source → investigation → verification → human-review workflow. Preserve first-party control of patient identity, consent, source custody, Patient World Model, investigation state, review and consequential actions. Keep providers and execution frameworks replaceable behind those contracts.

The immediate priorities are a source-preserving document extraction comparison, minimal privacy-safe operational telemetry, and recovery tests for bounded work in the existing task owner. Evaluate sandbox and durable-workflow products only against a named gap. A requirement to run thousands of agents is an unvalidated scale assumption, not the current product acceptance criterion.

This is an additive selection overlay. It neither replaces the full healthcare architecture nor narrows the platform to an agent portal. Open Intelligence remains independent of DevX and Meridian. Independently authored fictional patients and synthetic sources remain the engineering boundary.

## Evidence and current baseline

| Evidence | Observed state on 4 November 2026 | Consequence |
|---|---|---|
| [Repository main](https://github.com/OpenxIntelligence/open-intelligence/tree/f3f8a97fed90c9b23c8e6daa0f5865485a5a9a37) | Head `f3f8a97fed90c9b23c8e6daa0f5865485a5a9a37`; tree `e786c46302989e93223ca60d9042376b35483762`. README describes the Python/SQLite synthetic prototype. | Do not describe all H1 branch work as merged capability. This review did not rerun application tests. |
| [Main investigation module](https://github.com/OpenxIntelligence/open-intelligence/blob/f3f8a97fed90c9b23c8e6daa0f5865485a5a9a37/src/open_intelligence/investigation.py) | Fixed templates, source/citation validation, hypothesis/pending-review output, server-side Meta transport and recorded replay are visible in source. | Preserve this owner; source inspection does not establish live execution, security completeness or clinical performance. |
| [H1 composition PR #162](https://github.com/OpenxIntelligence/open-intelligence/pull/162) | Open draft, unmerged; observed head `62d2ad0dd2c2d581f9d13d7659f888265838a4f0`. | FastAPI/PostgreSQL is a recorded H1 target and branch implementation, not a new migration selected by this document. |
| [Provider-neutral PR #141](https://github.com/OpenxIntelligence/open-intelligence/pull/141) | Open draft, unmerged; observed head `429faf8982dc3737482d4166d19adb7ec0ba06e0`. | Extend the proposed native adapter boundary; no second model or agent control plane. Historical Notion verification SHAs differ from this live head and were not revalidated here. |
| [License evidence PR #134](https://github.com/OpenxIntelligence/open-intelligence/pull/134) / [backend evaluation PR #135](https://github.com/OpenxIntelligence/open-intelligence/pull/135) | Both open drafts; heads `ca18f2d3fe94573aa234c6ee01868b1e94b81b19` / `1490dd27332c7dba481174097dffad08d522988d`. | Reuse the existing rights and component owners; this intake does not supersede their stronger source-commit evidence. |
| [Notion technology architecture](https://app.notion.com/p/40a3866f77ef811c969fc38e95027ec2) / [agent lifecycle](https://app.notion.com/p/40a3866f77ef81fc929eca89e41a3f4a) | H1 Python/FastAPI/PostgreSQL and React/Vite/TypeScript direction; no vector search in H1; first-party task/authority boundary; conditional later orchestration. | Preserve recorded direction while distinguishing it from main and deployment. |
| [Drive component/rights document](https://docs.google.com/document/d/19YWwkhHzL3-A6oBjffkA0Zow2RV-0awXtodB9RjST9k/edit) / [existing registry](https://docs.google.com/spreadsheets/d/1QnrvNBasHSzQa7goGfolIR-kt1gzMrmpO7__CYIzxT4/edit) | Existing component, rights and release review process. Registry was discovered, not exhaustively reread or reconciled row by row. | The CSV below is a dated attachment inventory, not another canonical adoption registry. |

The main branch's planning documents retain earlier undecided-stack language. Later Notion and H1 work record a more specific engineering direction. This intake preserves that distinction rather than silently rewriting the older baseline or treating a draft as an accepted merge.

## Scope of the attached landscape

The 18 layer tables contain **149 rows and 144 distinct project labels**. These are input counts, not audited dependencies; aliases such as “OPA” and “Open Policy Agent (OPA)” remain visible. The attached source's recommendation table and organization summaries are contextual prose, not additional table rows in that count.

- [Complete input-row inventory](agentic_infrastructure_intake_2026-11-04.csv): every layer-table row, its original license claim, observed correction where screened, and its proposed layer disposition.
- [License-file evidence](agentic_infrastructure_license_evidence_2026-11-04.json): 16 upstream snapshots with repository, path, returned Git blob SHA, immutable blob API URL, and explicit unestablished release/dependency/asset clearance. The dated 5 November follow-up preserves those snapshots, extends Docling and adds five page-observation entries using the same record fields; unresolved pins remain null. See the [six-candidate follow-up](../project-state/TECHNOLOGY_STRATEGY.md#six-candidate-evidence-follow-up--5-november-2026) for the research/HOLD boundaries.
- Unscreened rows are marked **NOT_VERIFIED_IN_THIS_REVIEW**. Names in the attachment are discovery leads, including generic labels such as “MCP Gateway.” No capabilities, licenses, maturity scores or production suitability are inferred for those rows.

## Corrections before using the shortlist

| Source statement or framing | Correction | Selection impact |
|---|---|---|
| Dramatiq: Apache-2.0 | [Project documentation](https://dramatiq.io/license.html) declares LGPLv3 or later; the fetched COPYING.LESSER contains LGPLv3. | Outside this strict permissive shortlist. Existing OI-17 conditional-review policy is not changed. |
| Airbyte: MIT core | [Current license documentation](https://github.com/airbytehq/airbyte/blob/master/docs/community/licenses/README.md) distinguishes ELv2 platform/connectors from the separately MIT protocol; root LICENSE fetched as ELv2. | No blanket permissive Airbyte adoption. Examine exact component and release. |
| OpenBao appears in the recommended architecture while later excluded | The source contradicts its own strict filter. | Remove it from that strict recommendation; no decision about existing OI-17 exception paths is made here. |
| A2A versus MCP as alternatives | [A2A documentation](https://a2a-protocol.org/latest/topics/what-is-a2a/) distinguishes agent delegation from MCP tool/resource connectivity. | Choose by integration role; neither protocol grants patient-data or clinical authority. |
| SPIFFE/SPIRE versus Keycloak | [SPIFFE](https://spiffe.io/docs/latest/spiffe-about/overview/) addresses workload identity; [Keycloak](https://www.keycloak.org/) addresses user/application authentication and federation. | Different identities need different controls. Neither replaces first-party consent and purpose checks. |
| OPA versus OpenFGA | [OPA](https://www.openpolicyagent.org/docs) evaluates policy; [OpenFGA](https://openfga.dev/docs/fga) models fine-grained relationship authorization. | Compare against a specific authority query. Do not install both by default. |
| age + an unspecified backend as a secrets architecture | [age](https://github.com/FiloSottile/age) is file encryption, not a complete credential issuance, lease, rotation and audit service. | Secrets backend and recovery remain an explicit open decision. |
| OpenTelemetry versus Jaeger; NeMo Guardrails versus Presidio; Tekton versus Argo CD | These pair instrumentation with a tracing backend, behavioral controls with sensitive-data detection, and pipelines with deployment reconciliation. | The source's “alternative” column is not a drop-in replacement map. |
| PostgreSQL versus etcd; KEDA versus Knative | Transactional domain data differs from coordination state; autoscaling differs from a serving platform. | Keep the patient/run ledger authoritative; qualify additional services independently. |
| Permissive project name implies cleared product | LiteLLM excludes enterprise/; Langfuse names multiple enterprise directories and preserves third-party terms. | Exact packages, images and required features need review. Root licensing alone is insufficient. |
| OpenSandbox foundation contribution | The [AAIF announcement dated 22 October 2026](https://aaif.io/news/agentic-ai-foundation-announces-four-new-projects) confirms OpenSandbox, Agent Skills, Open Responses and OpenEnv additions. | Governance news is confirmed; it does not prove security or maturity for Open Intelligence. |

Current NVIDIA security documentation resolves to **v0.1.7** and describes configurable enforcement. An older search excerpt still called OpenShell alpha; that stale excerpt is not used as the current maturity conclusion. Production suitability remains unestablished in this review. See [current enforcement documentation](https://docs.nvidia.com/openshell/latest/security/best-practices).

## Map all 18 layers to existing work

| Layer | Existing responsibility | Backlog mapping | Proposed disposition | Candidate boundary | Evidence required |
|---|---|---|---|---|---|
| 1. Sandboxing and execution | Existing tool/run and authority owners | OI-011; OI-013; OI-016 | Evaluate later | OpenShell / OpenSandbox; configured isolation backend | A task actually needs untrusted execution; cross-case, host, network, budget and cleanup probes pass. |
| 2. Harnesses and agent orchestration | Investigation templates, validation and review | OI-008; OI-011 | Keep native coordinator | Optional LangGraph adapter; other harnesses remain leads | An adapter reduces measured complexity without replacing task IDs, permission checks or review semantics. |
| 3. Durable workflows | Existing task receipts, work ledger and outbox | OI-009; OI-013; OI-018 | Test current owner first | Temporal candidate | Crash/retry and multi-day wait requirements exceed current implementation; no duplicate domain effects. |
| 4. Interoperability protocols | Versioned model/tool boundary | OI-005; OI-011; OI-013 | One bounded adapter when needed | MCP for tools; A2A only for delegated external agent tasks | A concrete endpoint needs it; authority rechecked on dispatch, retry, resume and result acceptance. |
| 5. Tool gateways | Host-owned tool registry and effects | OI-011; OI-013 | Retain host authority | MCP adapter; proxy product unselected | Registry version, auth audience, credential custody and per-tool effect checks are demonstrated. |
| 6. Identity and authorization | Patient grants, actor, organization, purpose and consent | OI-012; OI-013 | Qualify before real identities/data | Keycloak; OPA/OpenFGA if justified; SPIFFE/SPIRE for workloads later | Revocation and wrong-patient tests pass; human identity, workload identity and domain authority remain distinct. |
| 7. Secrets | Server-owned credential custody | OI-004; OI-013 | Complete operational design | Backend unselected; age alone is insufficient | Short-lived or rotated credentials, recovery, audit, scoped injection and no secret-bearing model/trace payloads. |
| 8. Memory and data | Canonical source, case and investigation records | OI-005; OI-006; OI-013 | Preserve H1 relational direction | PostgreSQL target; no H1 vector store | Any extra index proves retrieval benefit and authorization/freshness parity; rebuildable from canonical owners. |
| 9. Events and messaging | Transactional domain event/outbox owner | OI-009; OI-013; OI-018 | Defer broker | NATS candidate if distribution becomes necessary | Measured fan-out/throughput need; duplicate, order, replay, revocation and dead-letter handling verified. |
| 10. Inference serving | Provider-neutral model-task boundary | OI-011; OI-013 | Task-qualified model comparison | vLLM candidate | Exact model/weights rights, source fidelity, privacy, memory, latency and cost outperform the relevant baseline. |
| 11. Model gateways | Same provider-neutral model-task boundary | OI-011; OI-013 | Avoid a second authority layer | LiteLLM core only if routing gap proven | Failover cannot broaden data region, provider retention, task effect, budget or permitted model list. |
| 12. Observability | Protected operational telemetry; existing durable audit | OI-010; OI-013; OI-018 | Next bounded comparison | OpenTelemetry-compatible instrumentation | Allowlisted fields, leakage tests, access/retention and exporter-failure behavior verified. |
| 13. Validation and guardrails | Deterministic validators and clinical review | OI-007; OI-011; OI-013 | Preserve enforcement first | OPA if policy gap; optional detector candidates | Injection resistance tested at tool/runtime boundary; detector score never grants access or clinical authority. |
| 14. Infrastructure orchestration | Existing deployment/composition boundary | OI-005; OI-013 | Defer cluster expansion | Kubernetes/K3s only after need | Availability, tenancy, capacity or operational requirement justifies measured extra cost and recovery burden. |
| 15. Object storage and analytics | Source custody, versions and derived projections | OI-006; OI-009; OI-013; OI-016 | Qualify one storage adapter on need | SeaweedFS candidate; analytics later | Exact bytes and subject bindings survive restart/restore; no public/raw bypass; retention and deletion tested. |
| 16. Ingestion and retrieval | Original-source owner and reviewable extraction | OI-006; OI-007; OI-009; OI-011 | Next bounded comparison | Docling vs current/manual parser baseline | Original bytes retained; page/span anchors, uncertainty and amendments preserved; no unapproved model downloads. |
| 17. Evaluation | Existing synthetic challenge cases and acceptance suite | OI-003; OI-010; OI-011; OI-014 | Extend task-specific evaluation | Framework unselected | Held-out scenarios, consequential-error and review-burden measures; tool scores do not replace adjudication. |
| 18. Developer portal and delivery | Existing repo, CI, Notion and Drive records | OI-004; OI-010; OI-013; OI-018 | Defer separate portal | Backstage and other tools remain leads | Multiple services/teams create a proven catalog need; CI and deployment controllers assessed separately. |

Candidates named above are proposed comparisons, not accepted dependencies. The existing [execution backlog](../EXECUTION_BACKLOG.csv) supplies the work-package IDs. OI-004 is the repository rights work package; it is distinct from the Notion OI-17 licensing-policy identifier and from repository OI-017 trial screening.

## What to build and verify next

### 1. Establish one joined patient-workflow baseline

Within the current convergence work, replay independently authored synthetic sources through patient attachment, source review, one investigation, amended-source invalidation and a revised review draft. Record exact branch/commit, scope, dependency state and tested versus untested paths. Use the already selected integration owner; do not combine unrelated draft PRs merely because this report links them.

Required evidence: original-byte hashes; durable source/question/run IDs; wrong-patient quarantine; revoked access; an amended report withholding stale output; restart/restore; no promotion of model output to clinical authority. This is the prerequisite for judging infrastructure improvements.

### 2. Compare one document extraction adapter

Extend OI-006/OI-007/OI-011 through the existing source owner. Compare a qualified Docling configuration with current/manual extraction on the same independently authored reports. Preserve the original bytes and exact version; return proposed assertions with page/span coordinates, literal text, units, dates, extraction method and uncertainty. A correction must invalidate only affected derived work.

Report extraction errors and total review/correction effort, not only throughput. Reject guessed patient attachment, missing anchors, wrong units and unsupported transformation. Pin parser, OCR/model artifacts and any downloads before running the candidate; Docling's MIT code license does not clear model weights or native parsers.

### 3. Add minimal operational visibility

Extend OI-010/OI-013/OI-018 with an allowlist of task type, opaque run correlation, duration, attempt, outcome code, adapter version and measured resource use. Treat even opaque identifiers as access-controlled metadata. Do not export patient/source text, prompts, response bodies, credentials, full URLs or source hashes as general telemetry. Token/cost fields must distinguish measured, estimated and unavailable.

[OpenTelemetry guidance](https://opentelemetry.io/docs/security/handling-sensitive-data/) makes sensitive-data handling the implementer's responsibility. Test errors and automatic instrumentation as well as successful spans. Operational telemetry may degrade without breaking safe processing, but a required durable authorization/audit receipt must still fail closed; those are separate channels.

### 4. Prove recovery before selecting an orchestrator

Extend existing task/work receipts under OI-009/OI-013/OI-018. Test a crash before claim, after side-effect attempt, before commit and after commit; duplicate delivery; lease expiry; stale worker completion; approval waiting; cancel/pause; source amendment; permission revocation during resume and persistence.

Use idempotency at the domain boundary and fencing against stale workers. A retried external side effect needs a downstream idempotency mechanism or explicit reconciliation state; do not claim universal exactly-once execution. [Temporal activities](https://docs.temporal.io/activities) also require application idempotency for duplicate effects. Evaluate Temporal only if it reduces measured recovery and operational burden without becoming a second clinical ledger.

### 5. Evaluate one isolated research task when execution requires it

Compare configured OpenShell and OpenSandbox environments using the same synthetic task, data, limits and attack probes. [OpenSandbox](https://open-sandbox.ai/) supplies lifecycle APIs across local/container and cluster environments. NVIDIA documents kernel, network and credential enforcement for [OpenShell](https://docs.nvidia.com/openshell/latest/security/best-practices). These are upstream capabilities, not tested results here.

Specify the actual backend, kernel, image digest, privilege, filesystem mounts, egress, credential injection, GPU access and cleanup policy. Do not stack Firecracker, gVisor, Kata and multiple sandbox managers automatically. Verify compatibility with the chosen runtime; GPU paths need their own isolation and resource tests.

## Required acceptance cases for any execution adapter

| Failure or boundary | Required observable result |
|---|---|
| Wrong patient/tenant/purpose | Refuse before content retrieval or dispatch; no content leak through logs, errors or artifacts. |
| Revocation while queued, running, retrying or persisting | Reauthenticate at each relevant boundary; withhold stale/unauthorized results and prevent prohibited new effects. Define the limit for already-issued external effects. |
| Source amendment | Preserve history; mark dependent output stale; resumed work uses an explicitly accepted source snapshot or stops. |
| Duplicate delivery and worker crash | One authorized domain effect or an explicit uncertain-effect reconciliation state; no silent duplicate event. |
| Expired lease or delayed child | Stale worker cannot overwrite current state; pause/cancel prevents new delegation and accounts for active children. |
| Prompt injection in source or tool output | Content cannot change policy, disclose another case, choose a forbidden tool, or approve itself. |
| Filesystem/network escape attempt | Deny host mounts, unauthorized destinations, metadata endpoints and credential reads under the tested configuration. |
| Budget and resource exhaustion | Bounded time, CPU/RAM/GPU, disk, output, tokens and concurrency; cleanup evidence retained. |
| MCP wrong audience or token forwarding | Reject the audience mismatch; upstream calls use their own authorized credentials. [MCP security guidance](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/tutorials/security/security_best_practices.mdx). |
| Result and evidence integrity | Persist result digest, source versions, model/tool versions, outcome and review state in the existing owner. Citations must resolve. |
| Sensitive telemetry | Seeded fictional markers and test secrets do not appear in exported logs/traces, exception payloads or retained worker files. |
| Clinical effect request | No prescription, diagnosis, treatment selection or clinical approval from infrastructure or a model. Return a blocked effect or scoped human-review task. |

These are proposed acceptance requirements, not tests executed by this documentation change.

## Measurement and promotion

Use the same tasks and hardware/runtime configurations for each comparison. Report quality (consequential errors, source fidelity, abstentions), autonomy (completion within authorized scope and recovery), speed (median/tail latency and cold start), human effort (review/correction minutes), and cost (compute, model, storage and operator effort per accepted task). Separate failed and cancelled tasks; keep raw denominators and sample sizes. No synthetic score establishes clinical benefit.

Promotion requires a named workflow gain, preserved ownership/contracts, exact release and artifact pins, dependency/asset/model/data/service rights, vulnerability and configuration review, failure/recovery evidence, a rollback/export path, and accepted scoped review. “Supports Kubernetes,” “self-hosted,” “Apache licensed” or “multi-agent” does not establish patient isolation or enterprise readiness.

No numeric maturity score, throughput target or unsupported GPU/protocol compatibility is assigned. The attachment's wider comparison fields remain **UNVERIFIED** until candidate-specific engineering evidence exists.

## Source-level license evidence

| Candidate | Observed license-file scope | Proposed disposition |
|---|---|---|
| [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell/blob/main/LICENSE) | Apache-2.0 | evaluate later |
| [OpenSandbox](https://github.com/opensandbox-group/OpenSandbox/blob/main/LICENSE) | Apache-2.0 | evaluate later |
| [Temporal](https://github.com/temporalio/temporal/blob/main/LICENSE) | MIT | evaluate on durability gap |
| [LangGraph](https://github.com/langchain-ai/langgraph/blob/main/LICENSE) | MIT | optional adapter |
| [OpenTelemetry](https://github.com/open-telemetry/opentelemetry-collector/blob/main/LICENSE) | Apache-2.0 | evaluate next |
| [Docling](https://github.com/docling-project/docling/blob/main/LICENSE) | MIT | evaluate next |
| [Open Policy Agent (OPA)](https://github.com/open-policy-agent/opa/blob/main/LICENSE) | Apache-2.0 | evaluate on policy gap |
| [OpenFGA](https://github.com/openfga/openfga/blob/main/LICENSE) | Apache-2.0 | evaluate on relationship gap |
| [Keycloak](https://github.com/keycloak/keycloak/blob/main/LICENSE.txt) | Apache-2.0 | evaluate before real identity |
| [SeaweedFS](https://github.com/seaweedfs/seaweedfs/blob/master/LICENSE) | Apache-2.0 | evaluate on object storage gap |
| [NATS](https://github.com/nats-io/nats-server/blob/main/LICENSE) | Apache-2.0 | defer scale trigger |
| [vLLM](https://github.com/vllm-project/vllm/blob/main/LICENSE) | Apache-2.0 | evaluate on model serving need |
| [Dramatiq](https://github.com/Bogdanp/dramatiq/blob/master/COPYING.LESSER) | LGPL-3.0-or-later (project declaration) | exclude strict permissive shortlist |
| [Airbyte](https://github.com/airbytehq/airbyte/blob/master/LICENSE) | Elastic-2.0 | exclude strict permissive shortlist |
| [LiteLLM](https://github.com/BerriAI/litellm/blob/main/LICENSE) | MIT outside enterprise/; separate enterprise terms | conditional core only |
| [Langfuse](https://github.com/langfuse/langfuse/blob/main/LICENSE) | MIT outside designated enterprise paths; third-party terms retained | conditional core only |

The JSON records pin returned license **blob** identities only. They do not pin a complete source commit, binary, container or deployable dependency closure. All candidates retain release_version/source_commit/artifact_digest as null and clearance as NOT_ESTABLISHED. No full license text or third-party source code is vendored.

Existing OI-17 tiered review remains authoritative. The attachment's stricter filter is used for this shortlist, not as an instruction to revoke previous scoped approvals or portray copyleft as universally noncommercial. Protocol, specification, SDK, server, enterprise module, hosted service, model and dataset licenses must be treated separately.

## Verification and limits of this change

- Read current main, repository instructions, first-principles plan, backlog, investigation source and four relevant live PR records.
- Read the existing Notion architecture/agent pages and Drive component/rights document.
- Extracted all 149 rows across 18 layer tables; checked the 16 scoped license-file receipts and verified corrections against upstream sources.
- Validated inventory/evidence structure, row counts, layer coverage, unique repository keys, blob SHA shape, absence of adoption/clearance claims and cross-file references.
- No package installed, model invoked, sandbox started, application behavior changed, benchmark executed, full dependency SBOM resolved, PR merged or deployment performed by this review.

Unverified attachment entries remain explicitly unverified. This work supplies a traceable intake and implementation sequence; it does not establish the complete global infrastructure landscape or finish the Open Intelligence platform.
