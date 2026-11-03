# Integration inventory — current contracts and unfinished connections

**Assessment:** 3 November 2026 (America/New_York).  
**Baseline:** reference main `24519839aa8ac1ea3aff88a956349ba72798a72a`; selected H1 draft [#276](https://github.com/OpenxIntelligence/open-intelligence/pull/276) at `c154bfbc5f99f76801d37903959943659c0b6a71`. All other drafts are named separately.  
**Status vocabulary:** the eight categories in [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) apply to bounded behavior, never to a whole clinical domain by implication.

## Current integration checkpoint — 3 November 2026

The selected runtime base is [draft #293](https://github.com/OpenxIntelligence/open-intelligence/pull/293) at commit 635f357048eb27e52e6ec5c3d7b6714215070127, tree 74c4a2ab65bf54a0908246199bb67c300ae2662b, preserving [#287](https://github.com/OpenxIntelligence/open-intelligence/pull/287) and its source base 247705700080052705817fee9e8f7b54afa8ffaa. The published tree matches the reconstructed local checkout. Its [e44f225e evidence-only follow-up](https://github.com/OpenxIntelligence/open-intelligence/commit/e44f225e3ce4953d754ad0e6e1409e22b696a29f) changes exactly five documentation files; those newer receipts are preserved here without changing the selected runtime. Main remains [24519839aa8ac1ea3aff88a956349ba72798a72a](https://github.com/OpenxIntelligence/open-intelligence/tree/24519839aa8ac1ea3aff88a956349ba72798a72a). The #276 assessment and separate-owner tables below remain historical checkpoints; this section supersedes only their selected-baseline and next-work statements.

The exact #293 head has successful [H1 API](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216511), [H1 React](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216590), and [synthetic UI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216653) workflow conclusions. These establish the inherited bounded baseline only; no new evidence-integration test result is claimed.

| Connection | Current owner and state | Remaining boundary |
| --- | --- | --- |
| Canonical source → authored saved question → exact quotation | H1 patient/case/source/question owners composed in #287 and retained in #293; fully implemented and tested within that synthetic contract | No arbitrary document extraction, external-record identity verification or scientific evidence appraisal follows. |
| Saved question → nonterminal return/history → source-only brief | Existing verification-return and brief owners retained in #293; fully implemented and tested for the bounded path | Source verification, source export and professional clinical judgment remain separate operations and authorities. |
| Saved question → durable follow-through → amendment recheck | #293 ports the existing reference follow-through lifecycle to PostgreSQL, retaining canonical questions and immutable source anchors | Operational owner labels do not grant access; completion does not verify external delivery or clinical action. No notification service is implied. |
| Saved question → biomedical evidence catalog/citation | **Implemented but not adequately tested at this checkpoint:** [#298](https://github.com/OpenxIntelligence/open-intelligence/pull/298) has published backend candidate 100512e734361153d70bd4cd3da272b8bb49cf01 and separate local UI work using KaijuCake's [#224 evidence catalog/citation contract](https://github.com/OpenxIntelligence/open-intelligence/pull/224) | Independent review and final combined hosted acceptance remain pending. Fictional metadata only; no live source activation, alternate patient chart or SQLite identifier coercion. |
| Evidence → governed Composer → evidence report/review | Existing clinical/evidence/report owners, including [#249](https://github.com/OpenxIntelligence/open-intelligence/pull/249), [#250](https://github.com/OpenxIntelligence/open-intelligence/pull/250), and [#272](https://github.com/OpenxIntelligence/open-intelligence/pull/272), remain separate from this selected H1 path | Explicit persistence and authority integration remains open. A catalog citation is not model execution, claim support, evidence appraisal or clinical approval. |

The catalog/citation slice preserves the existing H1 ownership boundary in its current implementation: versioned fictional metadata, separate rights history and question/citation links are stored in the existing investigation schema. Its release evidence must prove that #293's source/question/task histories, independent authority, scoped retry recovery and amendment behavior remain intact. The [tests-first API run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41636114987) at 9cdb89711228bcffde6476f9001626d645b6128c reproduced seven failures and eight missing-implementation errors across 336 executions. The successful [tests-first React run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41636115127) covered the inherited 195-test suite only. The later backend candidate's 13 passing local HTTP/OpenAPI/migration-graph checks and pending hosted PostgreSQL verification are scoped in [project state](PROJECT_STATE.md#evidence-metadata-slice--implementation-present-acceptance-pending). Final integration acceptance is pending; these receipts are not combined product success. Existing OI-004/007/008/009/010/013 retain backlog ownership, with the bounded behavior specified in [H1_QUESTION_EVIDENCE.md](../engineering/H1_QUESTION_EVIDENCE.md).

The [current project-state audit](PROJECT_STATE.md#canonical-record-conflicts-requiring-in-place-reconciliation) records stale [Sprint Board](https://app.notion.com/p/9a3fbdbf73ea4b779b2fe2b29172561d) and [OI Task Board](https://app.notion.com/p/40b3866f77ef807eb47bc45698b90d44) ownership/status fields, and the mismatch between the [Notion rights register](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3) and [Drive catalog](https://drive.google.com/drive/folders/1BSt9Whovg9jM9U6_eGBrvGi3NoZKmSIw). Reconcile those existing records in place; do not infer a named assignee or commercial clearance from a branch, a catalog label or a successful workflow.

This is a draft synthetic development checkpoint. No merge, deployment, real-patient use, external notification, professional signoff or clinical validation has occurred. Remote Notion/Drive records have not been updated by this local audit.

## Connected H1 owners in the selected base

| Connection | Existing owner / contract | State | Remaining boundary |
|---|---|---|---|
| React → FastAPI → PostgreSQL | `apps/web`, `apps/api`, canonical registry | Fully implemented and tested for selected synthetic draft scope; see exact-head receipt in #276 | No merged/deployed H1 release or production identity. |
| Credential → actor/organization/purpose/action/patient grant | `oi_api/access.py` Authentication port and SyntheticFileAuthentication | Fully implemented and tested for local fixture policy | Account management, identity proofing and patient consent missing. |
| Patient → qualified case binding | `case_bindings.py`, migration 0004 | Fully implemented and tested for synthetic binding/revocation | Synthetic review label does not authenticate an external patient record. |
| Case → immutable originals/assertions | `sources.py`, `source_integrity.py`, migration 0005 | Fully implemented and tested for declared source format | Arbitrary medical PDFs/images/HL7/FHIR ingestion not implied. |
| Record request → received existing source | `record_requests.py`; existing source/event transaction | Fully implemented and tested for source pointer and independent grants | No external record request sent; receipt is not clinical acceptance. |
| Original sources → World Model | `source_world_model.py` and existing source-index owner | Fully implemented and tested for source-derived view | No clinical inference, full medical model or scientific investigation. |
| World Model/source → Composer preflight | `composer_preflight.py`; canonical snapshot and separate receipt | Fully implemented and tested for non-executing context | Does not call a model or acquire scientific evidence. |
| Preflight → durable source question | `source_questions.py`; source snapshot/line/hash | Fully implemented and tested for selected source-question flow | Authored question donor #280 needs current combined verification. |
| Question → verification queue/return | `question_review_returns.py` / existing review owner | Fully implemented and tested for nonterminal return/history | No professional signoff, notification or clinical judgment. |
| Question → source-only brief | `source_brief.py` and `source-brief.ts` | Fully implemented and tested for selected bounded brief | Each download needs current export authority; source-only brief is not scientific appraisal. |
| Brief → exact-source packet and authored entry | Separate #280 donor into current candidate | Partially implemented | Preserve selected base fixes; prove combined browser, client, API and PostgreSQL behavior. |
| Commands → append-only events | Existing identity event owner | Fully implemented and tested for supported transaction boundaries | Cross-domain production delivery, external inbox and deployment recovery remain broader work. |

Authoritative local documentation: [API README](../../apps/api/README.md), [web README](../../apps/web/README.md), [canonical source receipt](../engineering/H1_CANONICAL_RECORD_SOURCE_RECEIPT.md), [source-question intake](../engineering/H1_CANONICAL_SOURCE_QUESTION_INTAKE.md), [source brief](../engineering/H1_SOURCE_LINKED_BRIEF.md), [verification return](../engineering/H1_SOURCE_QUESTION_REVIEW_RETURN.md).

## Other existing work that must be preserved and explicitly integrated

| Work / source | What the evidence describes | Status relative to selected H1 base |
|---|---|---|
| Merged reference app | Python/SQLite source ledger, versions, timeline, questions, synthetic evidence/review and DOI bibliography | Fully implemented and tested within its own bounded reference contracts; not a production clinical platform. |
| Clinical/EHR/LIS continuity #95/#152 and related owners | Canonical clinical patient/source/LIS mapping, event/source provenance and review adapters | Partially implemented in separate drafts; do not duplicate or claim migrated into current H1. |
| PDF/annotation/report #235/#249/#250 | Reviewed source passages, permitted quotations, report/review continuity and amendment behavior | Partially implemented across separate reference owners; PostgreSQL persistence adapter open. |
| Follow-through #174 | Question/source-linked tasks, owner/history, dates, report/export, source amendment | Partially implemented relative to H1; preserve task owner and anchored history when integrating. |
| Image custody #242 | Exact original DICOM under current source and patient/case authority | Fully implemented and tested for bounded separate draft; absent from #276 base. |
| Image/question/return convergence #278 | Preserved original image plus canonical question/return history and populated restore replay | Fully implemented and tested per documented exact-head receipt, separate from this candidate. |
| Archive/disclosure #277 | Optional archive port, unlocked remote read, fresh transaction and final authorization | Implemented but not adequately tested for live private PACS; controlled test archive only. |
| Reading convergence #274 | Patient/clinical layouts, provenance disclosure, response-scoped filters, responsive/keyboard checks | Fully implemented and tested for separate UI draft scope; no full accessibility qualification. |
| Accessibility CI #285 | Includes existing reference UI accessibility checks in its workflow | Fully implemented and tested per documented branch receipt; not H1 UI migration. |

[Engineering roadmap](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3) and [integration contracts](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876) link the exact branch histories. Documentation claims are not substituted for current combined tests.

## External systems and standards

| External connection | Role for the patient journey | Current state | Needed before live use |
|---|---|---|---|
| Existing EHRs / FHIR R4 / mCODE | Bring longitudinal records across organizations while preserving local source ownership | Designed but not implemented as comprehensive live connectivity in assessed H1 | Provider endpoint/access, identity, consent, scope, conformance, mapping/loss report, amendments and coverage. |
| HL7 v2 / CDA / C-CDA | Receive older system messages and documents | Proposed but not approved for specific new dependencies; parsing research exists | Exact component/version rights and transactional/retry/identity/fidelity acceptance. |
| Laboratory systems | Orders/specimens/results with original assay and uncertainty | Partially implemented first-party reference contracts; no live laboratory connection established | Laboratory authorization, mapping/QC, correction/release semantics and clinical validation. |
| Pharmacy / e-prescribing / medication feeds | Preserve requested, dispensed, administered and reported exposure separately | Designed but not implemented in assessed H1 | Legal/operational authority, provider access, content rights and medication safety qualification. |
| DICOMweb archive / PACS | Preserve originals and modality-native identifiers behind patient/source authority | Partially implemented bounded experiments; external adoption on hold | Private access, direct-bypass denial, lifecycle/restore, broad DICOM profiles and image/data rights. |
| PACSNode candidate | Tested external DICOM roundtrip and storage behavior | Broken for required patient-scoped isolation in tested native OIDC configuration; adoption HOLD | Valid wrong-patient token must be denied on every exposed surface; H1 read port alone is insufficient. |
| Crossref DOI metadata | Bibliographic discovery | Fully implemented and tested metadata-only reference adapter | Does not establish full-text access, clinical evidence appraisal or patient-query permission. |
| CIViC / ClinVar / trials registries | Permitted molecular/trial evidence with provenance and update dates | Proposed or partially implemented research/reference integrations | Exact permitted content, freshness, category/context fidelity, qualified applicability and source terms. |
| NCCN and other licensed guidelines | Guideline version awareness and permitted links | Blocked by external dependencies for full content | Exact content/AI/display/derivative rights; metadata-only H1 remains the allowed scope. |
| Model providers / local models | Bounded extraction/reasoning assistance | Partially implemented reference execution boundary; not H1 clinical investigation | Task evaluation, permitted input class, provider terms/retention, model/assets rights, deterministic validation. |
| Production identity provider | Verify people and sessions across patient/caregiver/workforce roles | Proposed but not approved | Specific Keycloak/Ory/other selection, exact rights/security review, proofing/recovery/delegation tests. |
| Scheduling / messaging / external care-team actions | Coordinate appointments, questions and tasks | Designed but not implemented for live operations | Real recipient/participant identity, access, delivery receipts, operational ownership and authorized action. |

These rows report project state rather than current general legal/license advice about upstream products. New adoption requires checking the exact upstream artifact and relevant transitive dependencies.

## Data ownership and loss boundaries

Interoperability objects do not replace OI's clinical meaning. A FHIR resource, external identifier or archive UID is exchanged within a qualified patient/source contract. The original external representation, acquisition time, version and transformation losses must remain inspectable.

Every integration must identify:

1. Canonical patient and qualified source identity.
2. Original artifact, digest, dates, version and exact location of the supporting statement.
3. Allowed operations and purpose; independent processing/export/model rights.
4. What is absent, uncertain, transformed or unsupported.
5. Retry/idempotency and amendment/revocation behavior.
6. Durable event/receipt owner and failure recovery.
7. Exact component/data/model/service versions, rights and limits.

For evidence/report migration, PostgreSQL `QUESTION-*` / `SRC-*` identifiers must not be coerced into reference SQLite integer identifiers. Build the explicit adapter at the existing owner boundary and test semantics, not just serialization.

## Immediate integration acceptance

The selected question/packet integration must preserve #276's source-import and received-pointer final authority checks, existing verification-return recovery and source-only brief. Test all consumers against the same source history; retain no-disclosure/rollback on authorization, response preparation, audit and commit failures. Preserve published migrations and canonical session behavior.

Initial inspection found DTO-only final response preparation in #276 review queue/return and the #280 packet donor. Selective repairs from #278 (`b72560ac0f5e5005040b0fc660ce1650343611cf`) will bring actual JSON preparation and same-case uncertain-return recovery into the combined candidate without images or migration changes. This is a bounded repair; other source/question/preflight encoding boundaries are still tracked, not declared solved.

Later #278 imaging and #277 archive work must enter via their existing owners with explicit history reconciliation. The wider evidence/report, PDF and follow-through work remains visible unfinished work rather than being silently omitted or reported complete.

## Inventory gaps

The repository/Notion evidence does not establish a full live provider inventory, deployment network map, production identity directory, commercial content entitlements, complete software/asset bill of materials for a released artifact, or end-to-end first-party orders/medications/scheduling operations. These remain missing or blocked items under OI-004/005/008/012/013/016/017, not reasons to start duplicate domain implementations.

Source references: [ingestion/interoperability](https://app.notion.com/p/40a3866f77ef8137a47cf95794e33ea7), [technology stack](https://app.notion.com/p/40a3866f77ef811c969fc38e95027ec2), [source-rights register](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3), [current H1 base #276](https://github.com/OpenxIntelligence/open-intelligence/pull/276).

