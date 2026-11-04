# Implementation roadmap — view of the existing execution backlog

Assessment checkpoint: **3 November 2026, America/New_York**. The canonical work-package IDs, dependencies and acceptance definitions remain in [EXECUTION_BACKLOG.csv](../EXECUTION_BACKLOG.csv). This file explains their current patient value and execution order; it creates no competing roadmap, owner assignments or delivery promises.

## Product direction and implementation basis

The patient is the organizing principle. Build continuity across records, people, care settings and time; interoperability is the first delivery stage and a complete independent clinical platform is the long-term destination. Clinical operations must be useful without AI, and models remain replaceable bounded assistants.

Preserve the selected H1 FastAPI/PostgreSQL and React/Vite/TypeScript direction in [AGENTS.md](../../AGENTS.md) and the [H1 decisions](https://docs.google.com/document/d/1YrORrdNxzT6MN-WuKVdk2vWVtVXVw9OSo0z5ARvMypg/edit). Preserve working Python/SQLite behavior as a reference rather than silently treating every parallel prototype extension as migrated product functionality. The [proposed Cosmo SQLite ADR](https://drive.google.com/file/d/1tW1010qbmGtDhiAdTSKhrv5tH6EhlN6n/view) does not override that accepted direction. Exact dependency and release qualification remain separate.

Status labels are the eight categories in [INCOMPLETE_FEATURES.md](INCOMPLETE_FEATURES.md). At this initial assessment, the selected integration below is **Designed but not implemented**; its implementation and final verification must be recorded separately before a completion claim.

## Next bounded implementation: source-linked questions through verification and export

**Patient value:** a person or authorized operator can ask about an exact statement in the record, inspect its provenance, request source verification, prepare a source-only brief, and understand why an amended report requires fresh consideration without losing the earlier history.

**Backlog mapping:** OI-006 source custody; OI-007 durable questions/scoped review; OI-009 second time point; OI-010 connected workflow; OI-013 authorization/isolation/recovery.

**Frozen owners:** integrate [#280](https://github.com/OpenxIntelligence/open-intelligence/pull/280) at `e8d851e5c7769c31f429a3d1649c26402aa9de12` into [#276](https://github.com/OpenxIntelligence/open-intelligence/pull/276) at `c154bfbc5f99f76801d37903959943659c0b6a71`. #276 owns the selected intake final-authority, canonical verification-return and source-brief convergence; #280 owns authored questions and exact quotation packet work. This is an isolated reviewable integration. The quoted-source packet contains source evidence, not biomedical evidence synthesis or a clinical conclusion.

Selectively reuse [#278](https://github.com/OpenxIntelligence/open-intelligence/pull/278) at `b72560ac0f5e5005040b0fc660ce1650343611cf` for its review-queue/return complete-JSON preparation fixes and same-case uncertain-return preservation during import or transient metadata failure. Importing those corrections does not import its image or migration scope. Other source/question/preflight final-encoding boundaries remain separately tracked; this slice must not claim a global disclosure repair.

### Required acceptance

1. Preserve canonical patient/case/organization/action checks and the exact original source/version/hash/line. No second patient, question, source or queue ledger.
2. Prepare and encode the entire packet, review-queue and verification-return responses while the existing source transaction and lock boundary still apply; then refresh the same credential, check actor/purpose/current grants, append the corresponding receipt/event and commit.
3. Late grant/identity withdrawal, failed preparation/serialization, failed audit append or failed commit withholds the prepared response and rolls back new success effects. Exercise actual response encoding, not only mocked DTO construction.
4. Run a connected independently fictional patient/source → authored question → exact quotation → verification return → source brief scenario through the existing API, PostgreSQL and built React application. Test a second patient and a denied action.
5. Amend the source; preserve original history, previous question and return receipt; expose reassessment state; refuse an obsolete new packet/brief; permit explicit fresh preflight/question. Exact permitted retries recover the same receipt without duplicate events.
6. Preserve source/queue content fingerprints, independent action grants, existing stable request keys and sensitive-state clearing. Source, patient, case or credential changes cannot let delayed responses restore prior content.
7. Run relevant owner regressions, build/type checks and recovery coverage required by the selected branch. Attribute results to the combined exact commit, including skips/failures and local versus hosted execution. The current runtime can run non-database API and client/build checks, but PostgreSQL is unavailable under its current privilege boundary; hosted PostgreSQL, migration, recovery and real browser/API gates are required. Parent test counts are baseline evidence only.

The separate [#286 patient overview](https://github.com/OpenxIntelligence/open-intelligence/pull/286), reading-convergence work, image/archive owners and PDF owner are preserved for coordinated follow-up. Their presence is not a reason to duplicate the same surfaces here.

## Sequenced work using existing backlog IDs

| Sequence | Patient outcome | Current state and next work | Dependencies and acceptance gate |
|---|---|---|---|
| Current | One trustworthy source/question/verification/brief path | Planned #276/#280 convergence described above. | OI-006/007/009/013; actual combined execution before calling OI-010 progressed. |
| Next connected step | Investigate a question using permitted scientific evidence | **Partially implemented:** reuse existing evidence/report/rights owners; add explicit H1 persistence and clinical-store adapters. | OI-004 + OI-007 → OI-008. Exact evidence version/quotation, support versus contradiction, applicability, rights withdrawal and source amendment; no duplicate SQLite patient chart. |
| In parallel, owned integration | Make the workflow understandable to patients | **Partially implemented:** integrate the existing overview/reading owners, source history and deliberate next steps. | OI-002/007/010. Test patient/case continuity, unfinished inputs, keyboard/mobile/assistive-tech behavior and comprehension without inventing urgency or clinical certainty. |
| Following canonical-source reconciliation | Accept ordinary patient documents | **Partially implemented:** port bounded original PDF/text intake and passage correction history into the authenticated canonical source owner. | OI-006/009/013. Original byte fidelity, exact page/span provenance, resource limits, correction-driven reassessment, restart, independent read/export permission. |
| Before real users/data | Verified identity, caregiver delegation, consent and operational security | **Partially implemented; externally blocked:** fixture grants prove checks, not real identity or clinical permission. | OI-012 → OI-013. Established access basis, account lifecycle, data/egress/retention rules, revocation across files/jobs/search/export, populated restore and independent review. |
| After source and identity contracts are stable | Obtain/exchange records across systems | **Designed/partial:** qualify one real provider/FHIR/SMART/HL7 channel at a time. | OI-005/006/012/013. Patient matching, source/provenance fidelity, explicit errors/retries and permission checks; first-party record independence preserved. |
| After intended use and evidence rights | Evaluate extraction and AI assistance | **Partially implemented:** preserve existing bounded tool/model contracts; compare with manual and deterministic baselines. | OI-003/004/006/007 → OI-011. Held-out consequential errors, grounded citations, abstention, correction burden, versioned model/input and cost. |
| Before clinical claims | Independent workflow evaluation | **Blocked by external dependencies:** qualified evaluators, permitted data/protocol and responsible operational context. | OI-002/011/012/013 → OI-014/015. Prespecified burden/error measures and stop criteria; synthetic CI cannot substitute. |
| After demonstrated need | One specialist modality and trial workflow at a time | **Partial research/proposals:** preserve existing imaging/genomic/trial owners. | OI-016/017. Named task, specimen/context, source and tool/model versions, exact rights, independent intended-use qualification. |
| Continuous | Reassess when records, evidence or permissions change | **Partially implemented:** expand targeted invalidation and responsible follow-through across connected owners. | OI-009 → OI-018. Preserve history, identify affected work, separate new review, measure notification/review burden and support rollback. |

## Expansion toward the standalone clinical platform

The platform must eventually support the operational domains below using the same patient identity, original-source provenance, authority and event contracts. These are capability families, not a requirement to split into microservices or replace existing modules.

| Capability family | Work to establish | Existing mapping |
|---|---|---|
| Patient/longitudinal record | Reliable demographics and matching, encounter context, conditions/allergies, history, goals and preferences; safe original-record access. | OI-005/006/012/013; proposed OI-23 domain requirements. |
| Clinical documentation | Encounter lifecycle, attributable authoring, signing/amendments, reusable source-linked review and historical reconstruction. | OI-006/007/009; existing EHR/source owners. |
| Orders, results and laboratory | Authorized order/specimen/accession/QC/result/acknowledgement workflow; actual routing, exceptions and recovery. | Existing bounded clinical/LIS owners; OI-006/013/016 plus qualification. |
| Medication and treatment management | Reconciliation, order versus administration semantics, versioned plans, licensed safety/terminology data and human authority. | OI-001/004/012/013 and proposed clinical-domain specifications. |
| Care coordination and communication | Accountable tasks, referrals, appointments, patient/caregiver communication, delivery failures and completed-action/outcome receipts. | OI-007/009/018/021; existing coordination owners. |
| Administrative and analytical services | Scheduling, operational reporting, appropriate financial workflows, auditability, support and service monitoring. | OI-005/012/013 and full-platform requirements; missing in the selected patient-source workflow. |
| Interoperability infrastructure | Standards-compatible adapters and exports that preserve clinical meaning while OI retains its own authoritative domains. | OI-005/006/012/013/016/017. |

The [OI-24 workflow proposal](https://docs.google.com/document/d/1LFOZGne5wVW0Hi5lU_uRwU7YMJGWz7fs2HeaJGlww0g/edit) supplies W-01–W-13 and authority distinctions; the [OI-25 architecture](https://docs.google.com/document/d/1BC5JPDXGf0hnsZwMuofGHQox7IZCKn30-kLSmzgj_D4/edit) connects interoperable and system-of-record modes. The [OI-29 gap report](https://docs.google.com/document/d/1LoRst3aZvAc8kNvWXvwv2oNQQOMgPjwjNIS0vo1AJQg/edit) is useful domain coverage but its old code-baseline status is not current H1 evidence.

## Progress and decision discipline

Record each increment in its existing source-owner engineering specification, exact PR and current assessment. Preserve `main`, draft and roadmap distinctions. A source-only brief does not complete OI-008, a verification return is not clinical sign-off, and a fictional workflow does not qualify real-patient use. Existing November 4 milestones in Drive are historical scheduling constraints to reconcile; they do not reduce the complete product scope or justify unsupported completion claims.

Before new third-party adoption, use the existing [rights register](https://docs.google.com/spreadsheets/d/1QnrvNBasHSzQa7goGfolIR-kt1gzMrmpO7__CYIzxT4/edit) and [policy overlay](https://docs.google.com/document/d/19YWwkhHzL3-A6oBjffkA0Zow2RV-0awXtodB9RjST9k/edit). Evaluate an exact artifact for a named problem; a catalog candidate is not an instruction to install it. Continue reversible engineering under existing authorization, retaining separate review for merges, production release and external clinical effects.
