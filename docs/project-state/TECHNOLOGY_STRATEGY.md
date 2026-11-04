# Technology strategy — retained H1 and evaluated alternatives

**Assessment:** 3 November 2026. This is a supplementary decision rationale, not an adoption record, dependency change, replacement roadmap, or production qualification. Work remains tracked in [EXECUTION_BACKLOG.csv](../EXECUTION_BACKLOG.csv), principally OI-004, OI-005, OI-010, OI-013 and GH-112.

## Governing outcome

Retain **React + Vite + TypeScript, Python + FastAPI, and PostgreSQL** for H1. The accepted decision excludes Next.js and vector retrieval from H1. Build a modular platform whose canonical patient, source, evidence, question and review owners support both interoperability and eventual standalone clinical workflows. Introduce infrastructure when a measured patient-facing or operational need justifies it. [Accepted precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f), [H1 decision](https://app.notion.com/p/40a3866f77ef81e08a12fd4921e19629), [architecture crosswalk](ARCHITECTURE_DECISIONS.md).

The 3 November founder clarification makes patient autonomy, continuity, understandable information and coordination the product criteria. A new framework does not establish those benefits. Assess changes against complete patient journeys, clinical provenance, accessibility, recovery and authority boundaries. Synthetic development is the current qualification stage; it is not the permanent product scope.

## Evidence and exact current artifacts

Live `main` at initial discovery was `24519839aa8ac1ea3aff88a956349ba72798a72a`. H1 evidence below comes from the selected draft [#276](https://github.com/OpenxIntelligence/open-intelligence/pull/276) lineage and the inspected integration working tree; it must not be reported as merged main or deployed functionality. See [PROJECT_STATE.md](PROJECT_STATE.md) for the integrated revision and verification results.

| Component | Inspected pins / evidence | Scope of the conclusion |
|---|---|---|
| React application | `react` and `react-dom` **19.3.1**; TypeScript **5.9.3**; Vite **7.3.7**; React type packages **19.3.0 / 19.2.2**. [Manifest](../../apps/web/package.json), [lock](../../apps/web/package-lock.json). | Current H1 direct dependencies; no additional component, form, chart or state library in that manifest. |
| Web build artifacts | Overrides use `esbuild-wasm` **0.28.2** and `@rollup/wasm-node` **4.67.4**; Node engine minimum **22.12.0**. | Preserve exact artifact/notice checks; changing an alias or platform changes the reviewed set. |
| API | FastAPI **0.162.0**, Pydantic **2.14.1**, SQLAlchemy **2.0.55**, Alembic **1.20.1**, Uvicorn **0.54.0**, pg8000 **1.31.6**. [Lock](../../apps/api/requirements.lock). | Existing H1 implementation; no framework replacement warranted by discovery. |
| Runtime/database | Accepted Python **3.12** and PostgreSQL **16**; API CI pins Python **3.12.16** and `postgres:16.15-bookworm`. [Workflow](../../.github/workflows/h1-api.yml). | A CI tag is not whole-image, host, deployment or recovery qualification. |
| Python dependency rights | **24** pinned wheels, **99** supplier all-target Rust crates, **13** embedded-runtime source-evidence entries. [Inventory](../../apps/api/dependency-license-inventory.json), [notices](../../apps/api/THIRD_PARTY_NOTICES.md). | Approved scope is local synthetic H1 development/evaluation on the recorded CPython 3.12 Linux x86_64 artifacts, without extras. |
| Web dependency rights | Lock integrity plus installed license/notice inspection; noninstalled optional packages remain uninspected. [Gate](../../apps/web/tools/license-gate.mjs). | Gate records local fictional development, not commercial release clearance or independently verified native linkage. |
| Existing verification | TypeScript plus Node's test runner; actual built React → FastAPI → PostgreSQL journey driven by Chromium/CDP. [Scripts](../../apps/web/package.json), [browser journey](../../apps/web/tools/browser_journey.py). | Playwright, Vitest and Cypress are not the current H1 harness merely because catalogs name them. |

The web package is private and marked `UNLICENSED`; no first-party distribution license is selected. The Python inventory retains cumulative native/historical terms, including the Mako inherited-notice issue and pydantic-core's broader native notice set. OS images, Python distribution, PostgreSQL server, developer tools, clinical content and model weights are outside that dependency clearance.

## Immediate metadata slice and source-screening checkpoint — 3 November 2026

The selected #293 baseline and current [#298 metadata/citation integration](https://github.com/OpenxIntelligence/open-intelligence/pull/298) use the same H1 dependency pins. Manifest and lockfile inspection found no dependency change for this increment. The source screen below is supporting research for existing OI-004/008/013 and the canonical technology/rights registers; it is not a new master catalog or an adoption decision. [Implementation state](PROJECT_STATE.md#evidence-metadata-slice--implementation-present-acceptance-pending) and [operation-specific data rights](../safety-packet/DATA_RIGHTS.md#h1-metadata-and-citation-boundary--3-november-2026) remain separate evidence.

| Existing component | Exact retained version and rights evidence | Immediate metadata-slice use and limit |
| --- | --- | --- |
| React / React DOM | 19.3.1 in the existing manifest/lock. The installed React LICENSE is MIT, SHA-256 da6d3703ed11cbe42bd212c725957c98da23cbff1998c05fa4b3d976d1a58e93. | Extend the current saved-question workspace and session owner. No new component library, patient state store or framework. |
| Vite | 7.3.7. Installed LICENSE.md identifies MIT core plus BSD-2-Clause, CC0-1.0, ISC and MIT bundled terms; file SHA-256 a77a1c089806b39ad339535bdf3677f636c91d96693e8ad7b11fe733f650ea64. | Existing TypeScript/Vite build. Preserve all bundled notices; a top-level MIT label does not replace the package's full notice set. |
| FastAPI | 0.162.0; existing locked wheel SHA-256 3785963de305dd09912426cb81f2d230fce98ab3521cdfe97265c8d14983128c. MIT in the [publisher metadata](https://pypi.org/project/fastapi/0.162.0/) and existing exact-wheel inventory. | Add routes to the current patient/question API. Existing development-scope determination does not clear extras, images, hosting or commercial distribution. |
| PostgreSQL | 16.15, as pinned by the existing CI image; [official release](https://www.postgresql.org/docs/16/release-16-15.html) and [PostgreSQL License](https://www.postgresql.org/about/licence/). | Store metadata, rights history and citation links under the existing investigation schema and source/authority transaction. This does not qualify the complete server/container/OS artifact or establish production readiness. |

| Capability / candidate | Disposition for this increment | Specific next evidence; no implied adoption |
| --- | --- | --- |
| #224 catalog/citation semantics on canonical H1 saved questions | Original project code selectively reused; implementation present, final review/acceptance pending | Inspect stored scope, exact version/hash, rights revocation and immutable citation history using existing owners. No new patient chart or external scientific claims. |
| Live biomedical metadata adapters | RESEARCH; not activated in #298 | Versioned source terms, bounded acquisition, permitted storage/display, update/retraction handling and no patient-identifying public query payloads. Current fixtures remain original fictional metadata. |
| Full-text retrieval, scientific/model investigation and evidence-rich reports | HOLD for this increment; existing separate owners retained | Item/operation-specific content rights, permitted model input, claim support/applicability and explicit H1 persistence/review adapters. A valid citation cannot establish these. |
| pypdf 6.21.2 | RESEARCH; no new H1 dependency | [Publisher metadata](https://pypi.org/project/pypdf/6.21.2/) declares BSD-3-Clause. Review the exact artifact, optional extras and source-fidelity/extraction contract before use; this is a screened version, not a latest-version claim. |
| PDF.js; prior source screen nominated 6.5.438 | RESEARCH; no new viewer or parser | [Official project page](https://mozilla.github.io/pdf.js/) distinguishes Apache-2.0 code from CC BY-SA 2.5 documentation. Exact release, bundled fonts/assets, workers and dependency closure remain unqualified. |
| pydicom 3.0.2 | RESEARCH for this slice; preserve separately reviewed imaging owners | [Publisher metadata](https://pypi.org/project/pydicom/3.0.2/) identifies MIT core and distinct extras including gpl-license. Do not activate optional codecs, bundled data or a medical-image workflow by inheriting the core license. |
| OHIF; prior source screen nominated 3.12.15 | RESEARCH / artifact HOLD | [Current upstream license](https://github.com/OHIF/Viewers/blob/master/LICENSE) is MIT. The exact v3.12.15 license URL was unavailable in this follow-up read; release/extension/asset/transitive review remains open. No PACS or viewer integration is selected here. |
| Biopython 1.88 | HOLD pending use/file/artifact review | [Publisher metadata](https://pypi.org/project/biopython/1.88/) reports LicenseRef-Biopython-License-Agreement. Do not relabel the whole distribution BSD; qualify selected files, native/NumPy dependencies, data and operation separately. |

The upstream policy and package pages above were read on 3 November 2026. None of these source-level findings grants project commercial clearance, selects a dependency, permits a patient dataset or authorizes model training. Retain exact-version artifact review and the existing OI-17 decision process.

## How to read the comparison

**Retain** means accepted/current within the stated H1 scope. **Consider later** means a plausible option with no established present need. **Qualify separately** means a bounded evaluation must resolve rights, authority, operations or deployment constraints. **Excluded from H1** records an accepted boundary, not a claim that the technology is universally unsuitable.

These are technology dispositions, not the eight implementation-status categories in [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md). A named candidate is not an installed, tested or approved feature. Unless an exact artifact appears in the inventories above, its direct/transitive licenses, vulnerabilities and deployment versions are **not qualified by this document**.

## Frontend, interaction and verification

| Candidate family | Disposition | Rationale / evidence needed to change the disposition |
|---|---|---|
| **React; Vite** | Retain | Preserve working H1 routes, shared session handling and browser tests. Compare a change against the same complete patient workflow before accepting migration cost. |
| **Next.js** | Excluded from H1 | Accepted founder/H1 decision overrides older scaffolding proposals and mixed React/Next catalog entries. Evaluation request does not reverse that decision. |
| **Vue; Nuxt** | Consider later | Alternative frontend family; no demonstrated patient or engineering benefit currently justifies replacing the accepted implementation. |
| **Svelte; SvelteKit** | Consider later | Same migration test: accessibility, authority behavior, workflow reliability and operational cost must improve enough to justify a rewrite. |
| **TypeScript; modern JavaScript; component architecture** | Retain | TypeScript is the H1 application language; existing JavaScript/reference behavior remains useful migration evidence. Consolidate reusable semantic components around actual repeated workflows. |
| **Progressive Web App; server-side rendering** | Qualify separately | Establish a concrete installation, connectivity or rendering need. Patient-data offline caching requires deliberate device, revocation, retention and recovery behavior; SSR adds a server-side access boundary. Neither is required for current H1 completion. |
| **Tailwind CSS** | Consider later | Compare against existing CSS and tokens; adopt only if it simplifies consistent styling without an unnecessary screen rewrite. |
| **shadcn/ui; Radix UI; Headless UI** | Qualify separately | Candidate accessible-component approaches. Evaluate one coherent approach using keyboard, focus, dialogs, screen readers, error states and the existing source-review journey; copied component source also needs notices and update ownership. |
| **Mantine; MUI; Ant Design; Chakra UI** | Consider later | Candidate complete UI systems. Select at most one if its actual components reduce maintenance and meet the design/accessibility requirements. Review exact package, premium modules, icons, fonts and assets separately. |
| **Storybook** | Consider later | Useful evaluation target when component reuse and review volume warrant a dedicated workbench; not a substitute for actual patient-flow verification. |
| **React Hook Form; TanStack Form** | Consider later | Compare on a genuinely complex form, including correction, validation, draft loss and accessible error recovery. Current bounded forms do not justify a new form abstraction by themselves. |
| **Zod** | Qualify separately | Use only with a clear client/server schema relationship. Client validation improves feedback but cannot replace canonical server validation or clinical authority. Avoid a drifting second clinical schema. |
| **TanStack Query** | Qualify separately | Evaluate request lifecycle benefits against patient/case changes, revocation, amendment, stale responses and nonpersistent sensitive caches. Preserve existing authority invalidation and retry behavior. |
| **TanStack Table** | Consider later | Introduce for a real complex table with sorting, navigation and accessibility needs; table machinery must not obscure longitudinal context or provenance. |
| **Zustand; Redux Toolkit; Jotai** | Consider later | No demonstrated need for an additional state store. Existing RegistrySession owns transient application state; none may become a second patient, question, queue or authority ledger. |
| **Apache ECharts; Recharts; D3.js; Visx** | Consider later | Compare on one needed longitudinal clinical view. Require correct units/time axes, missingness, uncertainty, provenance, accessible alternatives and responsive interaction before selecting a chart stack. |
| **Playwright; Cypress** | Qualify separately | Candidates for a maintained browser harness if they improve reliability/diagnostics over existing Chromium/CDP journeys. Preserve real API/database execution and security races; avoid two overlapping end-to-end systems without a specific benefit. |
| **Vitest; Testing Library** | Consider later | Candidate unit/component tools where current Node tests leave a real interaction gap. Prefer user-observable behavior; do not replace meaningful integration evidence with mocked success. |

WCAG 2.2 AA is the product target, not a claim that any framework or current screen is conformant. [Patient journey requirements](https://app.notion.com/p/40b3866f77ef816ea25fd3e8dbda6ca7), [experience specification](https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f).

## Backend and API architecture

| Candidate family | Disposition | Rationale / evaluation boundary |
|---|---|---|
| **Python; FastAPI** | Retain | Accepted H1 with existing domain owners, PostgreSQL integration and verification. Continue modular boundaries before service proliferation. |
| **Django; Django REST Framework** | Consider later | Compare only for a concrete capability the existing stack cannot economically provide. An administrative interface alone does not justify moving canonical clinical ownership. |
| **Node.js; NestJS; Express** | Consider later | Node remains current web tooling; a Node backend is a separate proposal. Older NestJS-core research does not supersede accepted Python H1. Qualify a separately justified adapter without duplicating domain state. |
| **Go; Java with Spring Boot** | Consider later | Consider isolated workloads with measured performance, integration or deployment needs. Preserve language-neutral contracts; avoid multi-language services based on hypothetical scale. |
| **REST; OpenAPI** | Retain | Continue explicit command/query contracts and typed validation. API schema availability does not prove authorization, persistence or workflow correctness. Runtime public docs are disabled in the synthetic API. |
| **GraphQL** | Consider later | Require a demonstrated composition benefit and tests of field/resolver authorization, bounded queries and patient isolation before adding another query surface. |
| **WebSockets** | Qualify separately | Add for a needed live progress/communication flow, with reconnect, expiry, revocation and patient-context tests. Request/response transport currently suffices for the bounded workflow. |
| **Event-driven architecture; asynchronous processing** | Retain boundary; extend incrementally | Preserve transactionally committed canonical events and idempotent commands. Use a durable outbox before introducing a broker; asynchronous work cannot publish success before commit or bypass final access checks. |

Interoperability adapters and future standalone encounter, order, medication, appointment and communication modules must share the same patient/provenance/consent boundaries. FHIR does not become an independent parallel patient master. [Canonical data](https://app.notion.com/p/40a3866f77ef81d9a5adca4ee9adb2e0), [integration inventory](INTEGRATION_INVENTORY.md).

## Background work, messaging and gateways

| Candidate family | Disposition | Rationale / evaluation boundary |
|---|---|---|
| **Celery; Dramatiq** | Qualify separately | Candidate Python job systems. Compare exact license/artifact sets, crash recovery, duplicate delivery, idempotency, cancellation and visibility on an actual ingestion job. Do not assume both meet the permissive-core preference. |
| **BullMQ** | Consider later | Requires justification for another worker/runtime dependency and its Redis-family deployment. Preserve OI-owned tasks, source lineage and authority checks. |
| **Temporal** | Qualify separately | Candidate for durable multi-step workflows when replay/recovery value exceeds operational cost. Compare the existing runtime against cancellation, version changes, retries and long-lived patient-context revocation. |
| **Redis-based queues** | Qualify separately | Queue choice includes exact server version/license, client, persistence and failure semantics. A permissive client license does not qualify the server. |
| **RabbitMQ; Apache Kafka; NATS** | Consider later | Evaluate independently against required ordering, replay, delivery, retention and operational capacity. A broker is not necessary merely because the design has events; exact server/plugin licenses also differ. |
| **Kong Gateway; Apache APISIX; Traefik** | Qualify separately | Compare only once deployment needs routing, TLS, quotas or ingress policy. Pin edition/plugins/images and test direct-backend bypass. A gateway does not replace application-level patient, purpose or consent authorization. |

No queue, broker, durable engine or gateway is adopted by this comparison. Retain one modular deployable where practical; split services only for demonstrated independent deployment, isolation or scaling requirements. [Technology specification](https://app.notion.com/p/40a3866f77ef811c969fc38e95027ec2), [agent/runtime design](https://app.notion.com/p/40a3866f77ef81fc929eca89e41a3f4a).

## Database, search and object storage

| Candidate family | Disposition | Rationale / evaluation boundary |
|---|---|---|
| **PostgreSQL** | Retain | Accepted transactional store for canonical identity, immutable source lineage, questions, review receipts and events. Require populated migration, recovery and isolation evidence as deployment scope grows. |
| **SQLite** | Retain reference/local scope | Existing reference implementation and comparison oracle. It does not create an alternate multiuser production patient store; preserve explicit migration adapters and distinct identifier types. |
| **Redis** | Qualify separately | No current dependency need established. Versioned terms below and operational/security review are necessary; old permissive releases must not be selected merely to avoid licensing work. |
| **OpenSearch** | Consider later | Candidate dedicated search service if measured retrieval needs exceed the accepted structured/lexical approach. Prove source freshness, deletion/revocation and patient isolation; qualify distribution/plugins/images. |
| **Elasticsearch** | Qualify separately; outside permissive H1 core | Source options and default distribution have different terms. No current need justifies adding it or changing the accepted retrieval boundary. |
| **MinIO** | Not selected | Current community server licensing and maintenance status require a separate decision; historical Apache-era information or SDK licensing does not qualify a current server deployment. |
| **S3-compatible object storage** | Qualify separately | Treat S3 compatibility as an interface, not a product/license decision. Prove exact-byte/version retention, private access, encryption/key control, deletion policy, restore and export portability. |
| **pgvector** | Excluded from H1 | Accepted retrieval is structured, terminology and lexical. Any later vector experiment needs measured clinical retrieval benefit, traceable evidence, freshness and zero cross-patient leakage. |
| **TimescaleDB** | Consider later | Require a measured longitudinal/time-series workload that ordinary PostgreSQL cannot meet economically. Extension feature/edition licensing and backup/upgrade portability need separate qualification. |

Clinical records require provenance, amendment history, reconciliation and authority semantics beyond generic CRUD. Search indexes, caches and projections remain replaceable derivatives of canonical records. [Canonical data source](https://app.notion.com/p/40a3866f77ef81d9a5adca4ee9adb2e0).

## Authentication, identity, consent and authorization

The current H1 authentication port defaults to denial and supports operator-controlled synthetic credentials. It does not establish verified people, caregiver authority, workforce identity, real consent or production access management. Preserve that explicit boundary until OI-013 qualification. [Access implementation](../../apps/api/src/oi_api/access.py), [security assessment](SECURITY_AND_PRIVACY.md).

| Candidate | Disposition | Rationale / evaluation boundary |
|---|---|---|
| **Keycloak** | Qualify separately | Existing proposed identity comparison candidate; upstream core license is Apache-2.0. Test exact deployment, account recovery, MFA, federation, lifecycle and adapter behavior; the IdP must not assign patient grants by inference. |
| **Ory** | Qualify separately | Evaluate the specific self-hosted components/editions required, not the brand as a single dependency. Compare identity, login, authorization and operations against Keycloak using the same patient/caregiver/workforce journeys. |
| **Zitadel** | Outside current permissive-core selection | Current core and pre-v3 code have different terms. Retain the catalog's exclusion pending an explicitly accepted licensing/deployment arrangement and technical qualification. |
| **Authentik** | Qualify separately | Potential identity candidate; current repository separates MIT-covered code from website, enterprise and third-party terms. Qualify actual components/features and patient-facing recovery/identity behavior. |
| **Open Policy Agent; Casbin** | Qualify separately | Candidate policy evaluation mechanisms. Compare deterministic denial, purpose/patient/action scoping, revocation, explainability, policy versioning and outage behavior. Neither supplies identity proofing or a complete consent lifecycle. |

Identity-provider authentication, patient matching, caregiver delegation, clinical role, legal consent and request authorization remain separate decisions. Avoid making a token's existence sufficient authority. [Security source](https://app.notion.com/p/40a3866f77ef81e9848ec0a14a97b53d), [decision proposals](https://app.notion.com/p/40c3866f77ef80f891e5e446289c0484).

## License distinctions verified against primary sources

Checked on 3 November 2026. These are upstream license facts, not legal clearance for this project. Source branches can change; any adoption requires immutable release/commit and artifact hashes, applicable files and complete transitive terms.

| Project | Verified distinction | Consequence for evaluation |
|---|---|---|
| **Redis** | Upstream states **7.2.x and earlier: BSD-3-Clause; 7.4.x–7.8.x: RSALv2 or SSPLv1; 8+: RSALv2, SSPLv1 or AGPLv3**. [Official licenses](https://redis.io/legal/licenses/). | Redis 8's AGPL option does not make it permissively licensed. Review maintenance/security and exact deployed modules as well as the chosen terms. |
| **Elasticsearch** | The 7.11 change replaced Apache-2.0 for affected source with SSPL/ELv2; the 2024 change added AGPLv3 for free source portions. Default distribution remains ELv2; current source exceptions need file-level inspection. [Official FAQ](https://www.elastic.co/pricing/faq/licensing), [source license](https://github.com/elastic/elasticsearch/blob/main/LICENSE.txt). | Do not label every release, source file, client and distribution Apache-2.0 or AGPL. Select a precise artifact before comparison or adoption. |
| **MinIO** | Current community source is **AGPLv3** and its README states the repository is no longer maintained. Maintainers documented the server's license change in April 2021. [Current source](https://github.com/minio/minio), [historical maintainer discussion](https://github.com/minio/minio/discussions/12157). | Historical Apache-era release/SDK information is not current-server clearance. An old release or separately licensed successor needs its own security, support and rights decision. |
| **TimescaleDB** | Repository license identifies Apache-2.0, Apache-compatible and Timescale License portions; file headers determine applicability. [License](https://github.com/timescale/timescaledb/blob/main/LICENSE). | Do not assume every extension feature/edition is Apache-2.0; qualify the precise feature set and image. |
| **Zitadel** | Vendor identifies the v3 transition from Apache-2.0 to AGPL; current repository states AGPL-3.0-only with identified Apache/MIT exceptions. [Vendor FAQ](https://help.zitadel.com/zitadel-licensing-faqs), [current licensing](https://github.com/zitadel/zitadel/blob/main/LICENSING.md). | A legacy license or MIT client does not qualify current core. This is a permissive-core policy distinction, not a claim that AGPL prohibits commercial use. |
| **Authentik; Keycloak** | Authentik's MIT grant has explicit website, enterprise and third-party exclusions; Keycloak's upstream core license is Apache-2.0. [Authentik license](https://github.com/goauthentik/authentik/blob/main/LICENSE), [Keycloak license](https://github.com/keycloak/keycloak/blob/main/LICENSE.txt). | Upstream labels support a shortlist, not image/plugin/transitive or deployment clearance. |

## Adoption gate and current next step

The Notion [Tier 1 catalog](https://app.notion.com/p/40c3866f77ef80a6846bdb98161b34cb) and [technology proposal register](https://app.notion.com/p/40c3866f77ef80f891e5e446289c0484) are research inputs. Their `Adopt`/license labels do not override accepted H1 or clear an artifact. Discovery found **0 Cleared** entries in the **125-row** [resource/rights registry](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3); repository-local exact-artifact development determinations have their own narrower scope.

Before adding a candidate, record in the existing architecture/rights owners:

1. The concrete patient or operational problem and a comparison against the existing implementation.
2. Exact version, source commit, package/image hashes, direct/transitive code, assets, data, notices and elected license terms; maintain the [OI-17 rights policy](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9).
3. Current security advisories, supported upgrade path, community/maintainer health, documentation and ability to operate/recover with the available team.
4. Representative correctness, authority/isolation, accessibility, reliability and performance evidence, including failure/abstention behavior where relevant.
5. Full operational cost, deployment complexity, export/exit path and boundaries that preserve independent patient/clinical ownership.

**Verified continuation:** the bounded patient-authored question/exact-source packet integration into the existing review/brief/intake owners passed its hosted gates without a new library or infrastructure; see [implementation evidence](IMPLEMENTATION_EVIDENCE.md). The next integration should connect the existing evidence/report owners through explicit canonical H1 persistence and clinical-store adapters. Broader stack selection follows demonstrated need through the existing backlog, while real-data, identity/consent, clinical safety and deployment qualification remain explicit stages.
