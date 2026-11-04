# Architecture decisions — reconciled current register

**Assessment:** 3 November 2026 (America/New_York). This is an evidence crosswalk, not a new architecture or replacement ADR system. Existing accepted contracts, [AGENTS.md](../../AGENTS.md), [FIRST_PRINCIPLES_PLAN.md](../FIRST_PRINCIPLES_PLAN.md) and [EXECUTION_BACKLOG.csv](../EXECUTION_BACKLOG.csv) remain the implementation owners.

## Precedence and status

Apply explicit founder decisions first, then accepted versioned domain/architecture contracts, then verified implementation at named commits. Notion/Drive studies and component catalogs support those decisions; publication date does not promote a proposal to an accepted architecture. [Precedence source](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f).

Decision state and implementation state are different. A decision may be accepted while implementation is partial. Use the eight assessment categories in [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md): fully implemented and tested; implemented but not adequately tested; partially implemented; designed but not implemented; proposed but not approved; missing; broken; blocked by external dependencies.

## Accepted decisions to preserve

| Decision | Accepted direction | Present scope / evidence |
|---|---|---|
| Product organizing principle | The patient and longitudinal healthcare journey govern product structure; care settings and buyers are downstream choices. | Founder clarification, 3 Nov; [source](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f). Benefits are evaluation targets, not measured outcomes. |
| Product identity | Open Intelligence is the current project; CEVax denotes historical provenance only. | Repository instructions and same precedence source. |
| Two complementary stages | Interoperate first; build complete standalone first-party clinical capabilities over time. | Adopted long-term scope; not current system completeness. [OI-16](https://app.notion.com/p/cca3866f77ef822195188170742085af). |
| Preserve existing work | Extend canonical identity/source/evidence/investigation/review/authority owners. No parallel ledger or blanket rewrite. | Existing reference implementation and accepted domain contracts. |
| H1 runtime and database | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16. | Accepted bounded engineering target, separate from production qualification. [H1 decision](https://app.notion.com/p/40a3866f77ef81e08a12fd4921e19629). |
| H1 frontend | React, Vite and TypeScript; no Next.js in new first-party development. | Accepted H1 decision and repository instructions. Current user request to evaluate technologies does not itself adopt an alternative. |
| Reference application | Keep Python/SQLite/browser-JavaScript behavior available during H1 migration. | Merged reference main remains separate from draft H1. |
| H1 retrieval | Structured, terminology and lexical retrieval; no vector search in H1. | Accepted bounded scope. Hybrid/vector experiments remain proposals requiring measured benefit and isolation evidence. |
| Restricted guideline content | NCCN metadata, version and links only in H1 until content rights are documented. | No implied right to ingest, display or derive from full guideline content. |
| Test/data boundary | Independently authored fictional data; public narratives inform abstract workflows only. | Sid's medical data and derived/pseudonymized fixtures are excluded; prior opt-ins superseded. |
| Source and authority semantics | Originals/version/anchors persist; amendments trigger reassessment; AI hypotheses and source returns are not clinical approval. | Existing source, question and review-return owners. |
| Commercial independence | Exact-artifact source availability and rights review; preferred permissive core; no catalog-only clearance. | Adopted [OI-17 policy](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9); scope-specific development evidence differs from distribution approval. |
| Review and release | Reversible development and draft integration proceed; merge/deployment/clinical operation need their existing separate authority. | No new approval is implied by a successful branch test. |

## Current selected implementation decision

**Selected base:** [#276](https://github.com/OpenxIntelligence/open-intelligence/pull/276), `c154bfbc5f99f76801d37903959943659c0b6a71`. It combines canonical source questions, verification returns, source briefs and intake-authority repairs.

**Donor capability:** [#280](https://github.com/OpenxIntelligence/open-intelligence/pull/280), authored questions and exact-source packet. It is a separate draft; inheriting it wholesale would risk losing fixes or conflicting with existing review behavior. The current candidate reconciles the useful behavior into the selected owners and must be tested as one combined tree.

**Selective repair donor:** [#278](https://github.com/OpenxIntelligence/open-intelligence/pull/278), `b72560ac0f5e5005040b0fc660ce1650343611cf`, contains existing final-JSON preparation fixes and same-case uncertain-return preservation across source import or transient case-list failure. The initial audit found DTO-only preparation in #276 review queue/return and the #280 packet donor. Reuse the bounded repairs without importing images or migrations. Donor source blobs were matched to the hosted commit during repository inspection; the newly composed behavior still needs independent verification. Other source/question/preflight DTO boundaries remain separate open work.

**Reason:** patients need to express their own question and carry its exact source context into a care discussion. This improves the existing connected workflow without selecting a new stack, adding a service, changing clinical authority or duplicating state.

**Existing backlog:** OI-006, OI-007, OI-009, OI-010 and OI-013. Final changed paths, exact commit, checks and unresolved defects belong in [PROJECT_STATE.md](PROJECT_STATE.md). Until verified, this increment is **partially implemented**, not a passing combined release.

## Ownership and migration rules

| Domain or concern | Owner to preserve | Integration rule |
|---|---|---|
| Patient identity | `identity.identity_patients`, existing PostgreSQL registry | No new patient master or display-ID-based identity mapping. |
| Qualified patient/case link | `coordination.patient_case_bindings` | Preserve organization/system/subject qualification, immutable identity and explicit revocation. |
| Original sources/assertions | `clinical_source.source_versions`, assertions and quarantine | Preserve original bytes, hashes, lines, dates and immediate amendment edges. |
| Questions | `investigation.source_questions` | Stable exact intent, current canonical snapshot/preflight and immutable source anchors. |
| Verification returns | `investigation.question_review_receipts` | Append-only nonterminal return; derived queue, no duplicated queue ledger. |
| Events | Existing `identity.identity_domain_events` owner | Command and event in one transaction; failed commit must not publish success. |
| World Model | Read-only projection of canonical source state | Projection fingerprint is distinct from access receipt identity. |
| Brief/packet | Authorized prepared representation of saved question and source | Independent export grant, bounded complete response, final authority, no second source/report store. |
| Clinical evidence/report | Existing reference evidence/rights/review owners | Explicit persistence adapter needed; never coerce PostgreSQL string IDs into SQLite integer IDs. |
| Frontend session | Existing shared RegistrySession | In-memory views, drafts and retries never become authority; context changes invalidate stale work. |

Published migrations are immutable. Reconcile multiple heads through an explicit follow-up merge revision with populated-upgrade tests where needed. Do not rename or rewrite already-published histories. API readiness must identify the exact expected migration head.

## Research proposals that remain open

The [OI-16 program](https://app.notion.com/p/cca3866f77ef822195188170742085af) and [OI-18 blueprint](https://app.notion.com/p/19f3866f77ef824eb164015c9c8d735c) propose domain boundaries and infrastructure. They do not mandate one service per logical box.

| Area | Decision state | Evidence needed before adoption |
|---|---|---|
| FHIR infrastructure (Medplum/HAPI or first-party facade) | Proposed / comparative evaluation | Same canonical workflow, loss/fidelity report, identity/authority separation, operations and exact rights. |
| Durable execution (existing runtime vs Temporal/other) | Proposed | Recovery, idempotency, retries and execution ownership tests that justify added infrastructure. |
| Event broker | Proposed | Transactional outbox first; measured deployment/throughput need before broker choice. |
| Search/vector/graph | Proposed beyond H1 | Workload and retrieval benefit, source/rights/freshness fidelity and zero cross-patient leakage. |
| External object/archive storage | Proposed / bounded experiments | Exact original fidelity, private access, bypass denial, lifecycle/recovery and rights. |
| Production identity and authorization service | Proposed / bake-off | Verified people, caregiver relationship, workforce identity, patient-scoped grants, consent and revocation. |
| Agent topology and providers | Proposed task-specific qualification | Deterministic authority plus OI-owned task/verification boundary; task accuracy, useful abstention, reliability and cost. |
| Hosting, tenancy and domain separation | Open | Actual data flow, operational ownership, security boundary and deployment requirements. |

## Material conflicts found during discovery

| Source conflict | Resolution for current execution |
|---|---|
| OI Task Board still includes Next.js scaffolding and next-specific packages. | Treat as superseded historical task instructions; H1 uses React/Vite. |
| TDR-045 includes Next.js and TDR-093 proposes TypeScript/NestJS core. | They are proposed technology-register rows; they do not override accepted H1. |
| TDR-025 says “Do not build a LIS.” | Incompatible with adopted full first-party scope; external LIS integration remains an initial route, not permanent product limit. |
| TDR-067 proposes pgvector by default. | Does not override no-vector H1. |
| Tier 1 catalog marks some unverified/incomplete entries “Adopt.” | “Adopt” is a study recommendation, not exact-artifact or production clearance. |
| Older product plans nominate clinician/buyer/institution as starting point. | Preserve workflow research; patient-centered founder clarification governs strategy. |
| Historical public-case experimentation is still documented. | Preserve history; no authority to acquire/use medical data now. |
| Separate drafts each have green checks. | Fresh combined candidate is required; no inference of integrated-platform correctness. |
| Old “latest” headings conflict with newer receipts. | Pin claims to SHA/time/scope; current repository evidence decides present implementation. |

Source registers: [OI Task Board](https://app.notion.com/p/40b3866f77ef807eb47bc45698b90d44), [Technology Decision Register](https://app.notion.com/p/40c3866f77ef80f891e5e446289c0484), [Tier 1 catalog](https://app.notion.com/p/40c3866f77ef80a6846bdb98161b34cb), [engineering evidence](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3).

This assessment records conflicts without altering historical source documents or assuming a new vendor, project license, clinical purpose, deployment or distribution approval.

