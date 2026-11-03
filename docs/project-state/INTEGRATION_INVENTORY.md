# Integration inventory — current contracts and unfinished connections

## Image, question, follow-through and citation convergence — 3 November 2026

[Draft PR #313](https://github.com/OpenxIntelligence/open-intelligence/pull/313)
joins the verified #298 head
`89f98824610e23a26d2904a845ed1d930207bd76` (tree
`30e40fd60b4f42d65732bfcebe6233ad602ad955`) with #278 at
`b72560ac0f5e5005040b0fc660ce1650343611cf`. This section supersedes earlier
selected-baseline and image-separation statements only for this candidate;
the individual historical receipts below remain preserved.

The existing patient/source/question/packet/brief/review/task/citation owners now
coexist with original image custody under `0011_image_evidence_merge`. All 14
published migrations remain intact; the new revision joins
`0009_image_review_merge` and `0010_question_evidence` without DDL. No parallel
patient ledger, evidence store, new dependency or clinical authority is selected.
The [combined engineering contract](../engineering/H1_IMAGE_QUESTION_EVIDENCE_CONVERGENCE.md)
defines amendment, independent grants, immutable history and restored-API
acceptance. The draft PR and canonical engineering records carry the executed
submitted-head receipt; separate green parent runs do not establish this join.

The initial combined runtime `895561f6ca7e1271e8401604c77c95635c28274f`
passed [464 API/PostgreSQL tests, 282 reference tests and all five recovery probes](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051682),
plus [219 client tests and actual built-browser acceptance](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41659051340).
The current candidate also adopts [#311](https://github.com/OpenxIntelligence/open-intelligence/pull/311)'s
exact two-file citation timestamp correction after 20 locally reproduced failures
and 22 focused passing tests. Its valid timestamp strings remain unchanged; the
current PR records fresh combined-head acceptance after that adoption.

The next separate owners are [#307](https://github.com/OpenxIntelligence/open-intelligence/pull/307)
at `c35219dc5eb244874a7df6e9bf00cfbfda18251f` for metadata/authored-evidence/report/task
convergence (incorporating #300/#302/#303/#304), and
[#312](https://github.com/OpenxIntelligence/open-intelligence/pull/312) at
`9cd218210099c69d04b023ef77f9051a32206fc4` for archive retrieval joined to #278.
They and the clinical EHR/LIS ports remain separate from this candidate until
explicit semantic and persistence reconciliation. Governed citation metadata
remains distinct from claim support and authored evidence appraisal. The
patient-centered full-platform direction and existing backlog ownership are unchanged.

**Assessment:** 3 November 2026 (America/New_York).  
**Baselines:** reference main `24519839aa8ac1ea3aff88a956349ba72798a72a`; initial H1 assessment [#276](https://github.com/OpenxIntelligence/open-intelligence/pull/276) at `c154bfbc5f99f76801d37903959943659c0b6a71`; current verified draft integration [#298](https://github.com/OpenxIntelligence/open-intelligence/pull/298) at `f4750327537a5febf764d25f43873be50ac7265a`, based on #293. Other drafts are named separately.

**Status vocabulary:** the eight categories in [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) apply to bounded behavior, never to a whole clinical domain by implication.

## Current integration checkpoint — 3 November 2026

The selected runtime base is [draft #293](https://github.com/OpenxIntelligence/open-intelligence/pull/293) at commit 635f357048eb27e52e6ec5c3d7b6714215070127, tree 74c4a2ab65bf54a0908246199bb67c300ae2662b, preserving [#287](https://github.com/OpenxIntelligence/open-intelligence/pull/287) and its source base 247705700080052705817fee9e8f7b54afa8ffaa. The published tree matches the reconstructed local checkout. Its [e44f225e evidence-only follow-up](https://github.com/OpenxIntelligence/open-intelligence/commit/e44f225e3ce4953d754ad0e6e1409e22b696a29f) changes exactly five documentation files; those newer receipts are preserved here without changing the selected runtime. Main remains [24519839aa8ac1ea3aff88a956349ba72798a72a](https://github.com/OpenxIntelligence/open-intelligence/tree/24519839aa8ac1ea3aff88a956349ba72798a72a). The #276 assessment and separate-owner tables below remain historical checkpoints; this section supersedes only their selected-baseline and next-work statements.

The exact #293 head has successful [H1 API](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216511), [H1 React](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216590), and [synthetic UI](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216653) workflow conclusions. These establish the inherited bounded baseline only. The separate #298 results below establish its subsequent metadata/citation integration.

| Connection | Current owner and state | Remaining boundary |
| --- | --- | --- |
| Canonical source → authored saved question → exact quotation | H1 patient/case/source/question owners composed in #287 and retained in #293; fully implemented and tested within that synthetic contract | No arbitrary document extraction, external-record identity verification or scientific evidence appraisal follows. |
| Saved question → nonterminal return/history → source-only brief | Existing verification-return and brief owners retained in #293; fully implemented and tested for the bounded path | Source verification, source export and professional clinical judgment remain separate operations and authorities. |
| Saved question → durable follow-through → amendment recheck | #293 ports the existing reference follow-through lifecycle to PostgreSQL, retaining canonical questions and immutable source anchors | Operational owner labels do not grant access; completion does not verify external delivery or clinical action. No notification service is implied. |
| Saved question → biomedical evidence catalog/citation | **Implemented and tested together in draft #298** at `f4750327537a5febf764d25f43873be50ac7265a`, using KaijuCake's [#224 evidence catalog/citation contract](https://github.com/OpenxIntelligence/open-intelligence/pull/224). API/PostgreSQL, built-browser and recovery acceptance passed. | External maintainer review and merge remain open. Fictional metadata only; no live source activation, alternate patient chart or SQLite identifier coercion. |
| Evidence → governed Composer → evidence report/review | Existing clinical/evidence/report owners, including [#249](https://github.com/OpenxIntelligence/open-intelligence/pull/249), [#250](https://github.com/OpenxIntelligence/open-intelligence/pull/250), and [#272](https://github.com/OpenxIntelligence/open-intelligence/pull/272), remain separate from this selected H1 path | Explicit persistence and authority integration remains open. A catalog citation is not model execution, claim support, evidence appraisal or clinical approval. |

The catalog/citation slice preserves existing H1 ownership: versioned fictional metadata, separate rights history and question/citation links use the existing investigation schema. At runtime `f4750327`, [API CI 41639678827](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639678827) passed 354 API/PostgreSQL and 282 reference tests, both reference browser journeys and all four Compose probes. [React CI 41639678872](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41639678872) passed 219 tests, the production build and actual evidence browser acceptance. These include original question/source histories, independent authority, exact retry recovery, amendments, rights revocation and actual database dump/restore. The full oncology product is not thereby complete.

Historical negative evidence is preserved: [tests-first API 41636114987](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41636114987) at `9cdb8971` ran 336 tests with seven failures and eight missing-implementation errors; [tests-first React 41636115127](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41636115127) covered only the inherited 195 tests. Backend candidate `100512e7` subsequently passed 339 API/PostgreSQL and 282 reference tests before the final combined runtime was published. See [project state](PROJECT_STATE.md#evidence-metadata-slice--verified-draft-integration) and [the full acceptance record](../engineering/H1_QUESTION_EVIDENCE.md). Existing OI-004/007/008/009/010/013 retain backlog ownership.

The [current project-state audit](PROJECT_STATE.md#canonical-record-conflicts-requiring-in-place-reconciliation) records stale [Sprint Board](https://app.notion.com/p/9a3fbdbf73ea4b779b2fe2b29172561d) and [OI Task Board](https://app.notion.com/p/40b3866f77ef807eb47bc45698b90d44) ownership/status fields, and the mismatch between the [Notion rights register](https://app.notion.com/p/52e843c6b0574713b66a5fb5d7f67ea3) and [Drive catalog](https://drive.google.com/drive/folders/1BSt9Whovg9jM9U6_eGBrvGi3NoZKmSIw). Reconcile those existing records in place; do not infer a named assignee or commercial clearance from a branch, a catalog label or a successful workflow.

This is a draft synthetic development checkpoint. No merge, deployment, real-patient use, external notification, professional signoff or clinical validation has occurred. The four existing Notion architecture/engineering/rights records and two Drive current-truth/progress documents were updated and read back after acceptance; [the exact receipt](../engineering/H1_QUESTION_EVIDENCE.md#canonical-record-updates) records their scope. Task-board ownership and cross-catalog rights reconciliation remain separate unfinished work.

## Historical #276 connection inventory

The current #293/#298 checkpoint above supersedes the earlier pending-integration
statements in this retained assessment.

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

| Work / source | What the evidence describes | State in the original #276 assessment |
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

## Rechecked historical leads — 3 November 2026

The originally referenced PRs and issues were re-read from GitHub, including
immutable head revisions and returned pull-request workflow records. All six
PRs below remain open drafts and unmerged. Workflow success is scoped to that
head and job; it is not evidence of complete H1 integration, release or clinical
validation. In particular, the returned #89 workflow is UI-only and does not by
itself prove its patient/EHR/event acceptance claims.

| Lead | Repository state | Exact head | Observed selected workflow |
|---|---|---|---|
| [#56](https://github.com/OpenxIntelligence/open-intelligence/pull/56) | Open draft; unmerged | `08eafc5fc4d606c9c47913d0e8e45641338489aa` | [Reference ledger workflow 41482472060](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41482472060) success |
| [#70](https://github.com/OpenxIntelligence/open-intelligence/pull/70) | Open draft; unmerged | `b1b99b3095b33b8cd7352793c94990b852ea88f9` | [Reference ledger workflow 41493529854](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41493529854) success |
| [#74](https://github.com/OpenxIntelligence/open-intelligence/pull/74) | Open draft; unmerged | `a1ce73e4bfa0eabee15e378968c424229a96cb02` | [Reference ledger workflow 41489395344](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41489395344) success |
| [#85](https://github.com/OpenxIntelligence/open-intelligence/pull/85) | Open draft; unmerged | `3326774b99e819d07ed555a6e505c24dfc699320` | [Reference ledger workflow 41494256338](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41494256338) success |
| [#89](https://github.com/OpenxIntelligence/open-intelligence/pull/89) | Open draft; unmerged | `7125aca84ebf38820482e8640e7a1479bcc0f429` | [UI-only returned workflow 41499742399](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41499742399) success |
| [#93](https://github.com/OpenxIntelligence/open-intelligence/pull/93) | Open draft; unmerged | `aa6d3f21b8d36d9949b66ed13ed34f76dabbd875` | [Reference ledger workflow 41501875440](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41501875440) success |
| [#87](https://github.com/OpenxIntelligence/open-intelligence/issues/87) | Open engineering issue | — | Not a completion receipt |
| [#92](https://github.com/OpenxIntelligence/open-intelligence/issues/92) | Open engineering issue | — | Not a completion receipt |

Preserve #56's laboratory operations, #70's outbox/inbox, #74's encounter/note
owner, #85's canonical registry, #89's separate integration lane and #93's
knowledge-context/rights contract. #298 reuses the canonical registry through its
existing PostgreSQL port; it does not merge all of these domains or close #87/#92.

### Concurrent clinical work rechecked at 13:03 UTC

All three rows remain open drafts, unmerged and outside #298. Preserve their
owners and evaluate combined behavior before selecting an integration order.

| PR and exact feature head | Actual work and verification | Integration implication |
|---|---|---|
| [#289](https://github.com/OpenxIntelligence/open-intelligence/pull/289), `6c6f28c9cfe9a886ac8f3f774a441e7e8cbdbb63` | One new reconciliation test file, six acceptance methods and no route implementation. [API 41628915787](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41628915787) checked out that feature head and ran 252 tests with six failures caused by absent routes returning 404. [React 41628915820](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41628915820) passed. | Tests-first development; reconciliation behavior is not delivered by this head. |
| [#290](https://github.com/OpenxIntelligence/open-intelligence/pull/290), `950b2346559728b3f17e58102a1e3848e4c3c970` | Seven files for PostgreSQL encounters, storage hooks, migration, parity tests and supporting records; child of #148. [Matrix 41629516514](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41629516514) ran 42 tests with one error on each of PostgreSQL 17.11 and 18.6. Actual checkout was PR merge `b88dab3e263faa2d1443805e11b09af5c6afda9e`. [UI 41629516399](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41629516399) passed; two inherited single-cell push runs failed with zero jobs. | Current parity verification is blocked. The observed error is in the SQLite oracle fixture, not evidence of a PostgreSQL row-conversion defect. |
| [#291](https://github.com/OpenxIntelligence/open-intelligence/pull/291), `b6ad6e7d2e78d56db38eac0763333d4be790b7cf` | Two-file child of #152 adds late authorization checks and stored-note SHA-256 verification. [Suite 41633964920](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633964920) passed 386 tests and both Chromium journeys at PR merge `0b15a00477eb6e784a2a4fada4d6f6eb8f4efd8b`. [UI 41633965153](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633965153) and [Crossref 41633964941](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633964941) passed; [single-cell push 41633957595](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633957595) failed with zero jobs. | Preserve the verified reference hardening. No PostgreSQL verification of this head was found, and it does not fix #290's separate fixture. |

In #290, the parity test executes its SQLite oracle first. That fixture creates
`sqlite3.connect(":memory:")` without `row_factory`; the workflow then indexes
`row["revision"]` and raises `TypeError`. The PostgreSQL adapter explicitly
converts query rows to dictionaries. #291 edits neither the parity fixture nor
that PostgreSQL adapter; its passing reference suite cannot close this gate.

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

