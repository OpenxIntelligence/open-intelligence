# Open Intelligence — current project state

Assessment date: 3 November 2026. Initial assessment recorded before this branch's product changes.

## Decision

Continue the existing patient-centered platform. Preserve the canonical patient, source, question, review and event owners. Use the accepted H1 FastAPI/PostgreSQL and React/Vite/TypeScript implementation for further convergence. The Python/SQLite application and its richer scientific/PDF workflows remain behavioral references and explicit migration inputs. This assessment is a source-linked index into the existing project, not a replacement roadmap.

The next bounded implementation joins [#280](https://github.com/OpenxIntelligence/open-intelligence/pull/280)'s user-authored questions and exact-source inspection to [#276](https://github.com/OpenxIntelligence/open-intelligence/pull/276)'s canonical verification-return history, source-linked brief and final intake-authority checks. It also brings actual packet JSON encoding inside the existing source transaction. At assessment time this work is **planned, not implemented**.

## What was actually inspected

| Source | Evidence and limits |
| --- | --- |
| GitHub main | `24519839aa8ac1ea3aff88a956349ba72798a72a`, read from the live branch API. Main is the original Python/SQLite application with a documentation clarification; it does not contain all later H1 capabilities. [Exact tree](https://github.com/OpenxIntelligence/open-intelligence/tree/24519839aa8ac1ea3aff88a956349ba72798a72a). |
| Working baseline | Clean isolated checkout of #276, `c154bfbc5f99f76801d37903959943659c0b6a71`. Read contributor instructions, README, first-principles plan, execution backlog, API/web source, schemas, migrations, dependency gates and CI. [Exact tree](https://github.com/OpenxIntelligence/open-intelligence/tree/c154bfbc5f99f76801d37903959943659c0b6a71). |
| Proposed donor | #280 at `e8d851e5c7769c31f429a3d1649c26402aa9de12`; inspected against the baseline. It lacks the review-return and intake-authority fixes already in #276, so replacing the baseline with this donor would regress behavior. [Exact tree](https://github.com/OpenxIntelligence/open-intelligence/tree/e8d851e5c7769c31f429a3d1649c26402aa9de12). |
| Other branches | Live inventory contained 205 open PRs, 204 draft, when #286 appeared during discovery. This is a time-bounded inventory, not a completion metric. Relevant owner branches and CI were sampled in depth; every line of all 205 PRs was not audited. |
| Notion | Founder/product/architecture, technology and rights, integration, clinical safety, UX, engineering roadmap and linked task/resource registries. [Core project](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f). Search results and document claims are not substitutes for code or CI. |
| Google Drive | Content searches and canonical product, engineering, decisions, research, licensing and overlap records, including linked H1 and historical CEVax material. [Engineering progress](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit), [H1 decision register](https://docs.google.com/document/d/1YrORrdNxzT6MN-WuKVdk2vWVtVXVw9OSo0z5ARvMypg/edit). Claims are scoped by approval and implementation evidence. |

Unrelated repositories and unrelated personal files were outside scope. Inaccessible content, unpublished local work and uninspected branch behavior are not certified by this assessment.

## Status vocabulary

Each status needs a named scope and evidence date. A draft can be fully implemented and tested for a bounded fictional-data contract while the overall clinical capability remains partial.

| Status | Meaning |
| --- | --- |
| Fully implemented and tested | Named behavior exists and the stated software gate passed at the named commit. Does not mean merged, deployed or clinically validated. |
| Implemented but not adequately tested | Code exists; the required behavior, failure mode or environment has no passing acceptance evidence. |
| Partially implemented | Some of the required workflow works; named steps or connections remain absent. |
| Designed but not implemented | A sufficiently concrete design exists, with no corresponding working implementation in the stated scope. |
| Proposed but not approved | A candidate, hypothesis or draft decision without adoption evidence. |
| Missing | No supporting implementation was found within the inspected scope. |
| Broken | A reproducible failure or directly observed invariant violation exists; do not infer this from absent evidence alone. |
| Blocked by external dependencies | Execution requires a named unavailable external grant, service, agreement, credential, environment or approval. |

## Initial verification of the selected baseline

Executed on #276's exact source in this turn before product changes:

- 106 client tests passed, zero failures or skips; TypeScript and Vite production build passed.
- API test discovery ran 246 executions: 51 passed, 195 skipped because no usable PostgreSQL service was available in this executor. **This is not local PostgreSQL acceptance.**
- Existing backend hash/notice gate passed: 24 wheel packages, 99 supplier-native entries and 13 embedded runtime entries. These counts describe an inventory, not independent guarantees or clinical tests.
- Existing frontend rights gate passed for 18 installed packages; two omitted optional packages remained uninspected. No runtime dependencies were added.
- PostgreSQL 16.15 binaries are present, but this executor maps only root. PostgreSQL refuses root execution; the permitted-user setup failed. No runtime restriction was bypassed. Full database/recovery acceptance must run in the existing hosted gates.

The live GitHub audit separately confirmed successful API/web workflow conclusions for #276 and #280. Those parent results establish baseline evidence only, never acceptance of this branch's future combined tree. [#280 API](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41577517975), [#280 web](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41577518214).

## Material findings

1. The product's central gap is convergence: tested capabilities are distributed across unmerged owners. Counting their test totals or rendering their screens together does not establish one integrated platform.
2. The patient is the organizing identity. A provider, organization or case binding supplies authority and provenance; it does not replace the person's longitudinal record or narrow the product to a care setting.
3. The accepted H1 direction supersedes older Next.js task rows. A later proposal to retain the SQLite/vanilla stack as the foundation has no adoption evidence and does not reverse H1.
4. The current authentication fixture is explicitly synthetic. Production patient identity, consent, delegated caregiver rights and professional verification remain open.
5. PDF/report/evidence and imaging owners contain substantial work, but each must cross its actual persistence, versioning, authorization and review boundaries before being claimed integrated.
6. Main's historical clinical-data acquisition workflows and their retirement branch remain a separate unresolved repository-wide issue. An offline gate on a draft does not disable them on main.

## Assessment index

- [Product requirements](PRODUCT_REQUIREMENTS.md)
- [System architecture](SYSTEM_ARCHITECTURE.md)
- [Existing features](EXISTING_FEATURES.md)
- [Incomplete features](INCOMPLETE_FEATURES.md)
- [Technical debt](TECHNICAL_DEBT.md)
- [Integration inventory](INTEGRATION_INVENTORY.md)
- [Security and privacy](SECURITY_AND_PRIVACY.md)
- [Implementation roadmap](IMPLEMENTATION_ROADMAP.md)
- [Architecture decisions](ARCHITECTURE_DECISIONS.md)

The supplementary [technology strategy](TECHNOLOGY_STRATEGY.md) compares every requested candidate family with the accepted H1 stack and records version-sensitive licensing distinctions without adopting new dependencies.

Existing authoritative engineering traceability remains [EXECUTION_BACKLOG.csv](../EXECUTION_BACKLOG.csv), [FIRST_PRINCIPLES_PLAN.md](../FIRST_PRINCIPLES_PLAN.md) and each named source owner's contract. Final candidate verification will be recorded separately so the initial baseline is not silently rewritten as a completion claim.

## Subsequent implementation

The [connected-workflow evidence record](IMPLEMENTATION_EVIDENCE.md) records the subsequent #287 integration, source-reuse manifest and observed failure/repair history. Its linked exact-head verification receipt distinguishes the implemented draft from this initial assessment and from `main`.
