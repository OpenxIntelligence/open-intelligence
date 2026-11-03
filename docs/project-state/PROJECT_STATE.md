# Open Intelligence — current project state

Assessment date: 3 November 2026. Initial assessment recorded before this branch's product changes.

## Current-truth reconciliation — 3 November 2026

This later audit updates the selected implementation baseline and next work. The initial assessment, former plans and verification receipts below remain historical evidence; their earlier use of "planned" or "selected baseline" does not describe the newer #293 checkpoint.

| Scope | Observed state and evidence |
| --- | --- |
| Merged main | The live repository audit observed main at [24519839aa8ac1ea3aff88a956349ba72798a72a](https://github.com/OpenxIntelligence/open-intelligence/tree/24519839aa8ac1ea3aff88a956349ba72798a72a). Main remains the reference Python/SQLite application; the H1 drafts below are not merged main capabilities. |
| Selected H1 runtime base | [Draft #293](https://github.com/OpenxIntelligence/open-intelligence/pull/293), runtime commit 635f357048eb27e52e6ec5c3d7b6714215070127, tree 74c4a2ab65bf54a0908246199bb67c300ae2662b. The local checkout was reconstructed from the published source and its tree verified. It preserves [#287](https://github.com/OpenxIntelligence/open-intelligence/pull/287), including source base 247705700080052705817fee9e8f7b54afa8ffaa, and adds canonical PostgreSQL question-linked follow-through. |
| Preserved upstream evidence follow-up | [e44f225e3ce4953d754ad0e6e1409e22b696a29f](https://github.com/OpenxIntelligence/open-intelligence/commit/e44f225e3ce4953d754ad0e6e1409e22b696a29f), tree 7c8d022a6158c3edcb0210dba85a18367e4145bb, is exactly one commit ahead of that runtime base. The [exact comparison](https://github.com/OpenxIntelligence/open-intelligence/compare/635f357048eb27e52e6ec5c3d7b6714215070127...e44f225e3ce4953d754ad0e6e1409e22b696a29f) changes only five documentation files. All five evidence additions/corrections have been reconciled into this continuation, preserving the newer predecessor receipts without changing the selected runtime, tests, migrations, dependencies or workflows. This is source-document reconciliation, not a PR merge. |
| Existing hosted verification | At that exact #293 head, the [H1 API workflow](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216511), [H1 React workflow](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216590), and [synthetic UI workflow](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216653) each completed with success. These are inherited baseline receipts, not tests of the subsequent metadata/citation slice; no execution counts are inferred or summed here. |
| Connected bounded behavior | Saved canonical question → exact source quotation → nonterminal verification return/history and source-only brief → persistent follow-through. Existing task/source anchors, attributed operational history, source-amendment recheck and independent read/update/export authority remain part of the selected contract. Recorded ownership or task completion is not verified professional identity, clinical approval or an externally completed action. |
| Remaining integration gap at #293 | Biomedical evidence catalog/citations, scientific Composer execution, evidence appraisal and evidence-report owners are not integrated into that baseline H1 path. The source-only brief and verification return do not establish those capabilities. The separate #298 progress checkpoint below scopes the subsequent metadata/citation work. |
| Release state | Draft, unmerged and undeployed; independently authored synthetic data only. No production identity/consent, real-patient authorization, commercial clearance or clinical validation is established by this checkpoint. |

### Evidence metadata slice — implementation present; acceptance pending

[Draft #298](https://github.com/OpenxIntelligence/open-intelligence/pull/298) selectively reuses KaijuCake's existing [#224 evidence catalog and citation contract](https://github.com/OpenxIntelligence/open-intelligence/pull/224) at H1's canonical PostgreSQL saved-question boundary. The current working tree contains the metadata persistence adapter, immutable question/citation links, independently authorized API routes and saved-question UI. The bounded input is independently authored fictional metadata. Canonical patient, case, source, question, review and follow-through owners remain unchanged; there is no alternate patient chart, implicit SQLite identifier coercion, new model execution or dependency adoption. Work remains under OI-004/007/008/009/010/013 and [the existing integration contract](../engineering/H1_QUESTION_EVIDENCE.md).

**Status: implemented but not adequately tested at this checkpoint.** Independent review and final combined hosted acceptance remain pending. The published tests-first head was 9cdb89711228bcffde6476f9001626d645b6128c. Its [API run 41636114987](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41636114987) executed 336 tests and reproduced seven failures for absent routes/request limits plus eight errors for the absent evidence_catalog implementation. Preserve that observed failure receipt. The [React run 41636115127](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41636115127) succeeded on the inherited 195-test suite; it does not establish acceptance of the new evidence UI.

The subsequent published backend candidate is [100512e734361153d70bd4cd3da272b8bb49cf01](https://github.com/OpenxIntelligence/open-intelligence/commit/100512e734361153d70bd4cd3da272b8bb49cf01), tree d3bf2f09ec4b5ce9b866fc0559c8b2a828771e73, verified against the local prospective tree. That commit contains the API, migration, reused donor code, contracts and tests only. The implementation runner reports 13 local HTTP/OpenAPI/migration-graph checks passing; hosted PostgreSQL verification remains pending at this recorded checkpoint. The new frontend and browser acceptance work remain separate local work until a combined head is published and tested. No final combined green result is asserted here.

Citation identity verification is metadata integrity, not evidence that a publication supports a claim. Scientific Composer execution, evidence appraisal, evidence-rich reports and professional clinical review remain separate integrations. Preserve the distinctions between source observation, citation, generated interpretation, operator verification return and clinician decision. The full patient-centered first-party destination, accepted H1 stack, no-Next.js rule and OI-17 rights policy continue to govern. Source-specific research and candidate holds are recorded in the existing [technology strategy](TECHNOLOGY_STRATEGY.md) and [data-rights note](../safety-packet/DATA_RIGHTS.md); this checkpoint creates no remote completion claim.

### Canonical-record conflicts requiring in-place reconciliation

| Existing record | Audit finding and treatment |
| --- | --- |
| [Notion Sprint Board](https://app.notion.com/p/9a3fbdbf73ea4b779b2fe2b29172561d) | Its twelve returned task rows have no named Owner; links still point to early PRs #1/#4/#7/#8. These rows cannot establish present implementation ownership or completion. Reconcile against the actual source owners and exact-head receipts rather than inventing assignees. |
| [Notion OI Task Board](https://app.notion.com/p/40b3866f77ef807eb47bc45698b90d44) | Sampled evidence/source tasks retain superseded Next.js-style paths and largely unassigned, Not started states. Preserve task identities and history; update only after comparing the relevant current owners. |
| [Notion resource register](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3) | The query returned 125 records: 124 Not cleared and one Review in progress, with no commercial-rights reviewer or commercial-freedom tier values. The sole review-in-progress row is [Crossref bibliographic metadata](https://app.notion.com/40a3866f77ef8154a0d2cf3195faf1fd). A preferred or implemented package is not automatically cleared for distribution. |
| [Drive technology catalog](https://drive.google.com/drive/folders/1BSt9Whovg9jM9U6_eGBrvGi3NoZKmSIw) | The [README](https://drive.google.com/file/d/1oR_P29HBhMndes7CR1pRZUXOAvSwlmi4/view), modified 2 November at 07:58 UTC, still calls master/license CSV generation pending, while the files exist and later [Technology 04](https://app.notion.com/p/40a3866f77ef811c969fc38e95027ec2) records a 556-row catalog. The Drive catalog and 125-row Notion register are distinct records, not a proven synchronized inventory or approval register. |
| [Contracts 14](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876), [Engineering 12](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3), and [Drive Engineering Progress](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit) | Older sections use "current tested candidate" for earlier heads. Retain each receipt with its original scope, then add the verified current checkpoint to the existing records. Chronology alone does not settle architecture or grant merge/deployment authority. |

H is the recorded product/mandate and catalog owner in [OI-16](https://app.notion.com/p/cca3866f77ef822195188170742085af) and the catalog README. No missing task assignee or rights reviewer is inferred from that ownership. Notion/Drive reads succeeded; the Team Dashboard response was truncated with three unknown blocks, so complete child records supplied the decision evidence. This local audit does not claim that any remote record has already been reconciled.

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

The complete runtime at `f7b0f683ab64ba2de7363744b65b8e26528f3138` subsequently passed both hosted workflows: 301 API/PostgreSQL executions, 245 historical reference executions, 170 client tests, production build, real browser journeys and patient/source/review recovery probes. Independent review's three Important client findings and one Minor decoder gap were repaired and re-reviewed. The authored-question/source-inspection/nonterminal-return/fresh-brief path is **fully implemented and tested within its bounded fictional-data contract**. The full patient-centered clinical platform remains partial; this draft has not been merged or deployed. See the separate evidence record for exact runs, preservation checks and remaining recovery/disclosure limits.


The subsequent [#293 follow-through continuation](../engineering/H1_QUESTION_FOLLOWTHROUGH.md)
is verified at `635f357048eb27e52e6ec5c3d7b6714215070127`: 326 API/PostgreSQL
executions, 245 reference executions, 195 client tests, actual browser journeys,
restart and restored-database HTTP acceptance. It adds durable recorded task
ownership, revisit basis and attributed history to the same saved questions.
Clinical accountability, scientific evidence appraisal and real external
coordination remain separate unfinished capabilities. The draft is unmerged.
