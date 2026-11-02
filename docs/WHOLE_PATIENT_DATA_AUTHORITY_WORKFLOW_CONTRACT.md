# Whole-patient integration contract — patient data, clinical authority, and Composer workflow

**Status:** implementation-ready *proposal for review*, 2 November 2026. **Scope:** a cross-domain interface/acceptance contract, not a replacement architecture, production EHR, authorization service, or approved clinical function. **Environment:** fictional/synthetic patient cases only. **No Next.js.**

## 0. Decision precedence and precise objective

The founder's **complete first-party healthcare ecosystem** scope (EHR/EMR, oncology, laboratory/LIS, pathology, imaging/RIS/PACS, genomics, treatment/pharmacy, patient/professional experiences, research, AI/ML, hospital operations) governs the destination. The current Python/SQLite `CaseStore` is a synthetic, source-preserving reference adapter, not the permanent canonical patient registry. Preserve the existing source/version, biological-asset, case, question, evidence, review, rights and event contracts. **Do not build a parallel patient/source/authority ledger.**

This contract answers three implementation questions:

1. **What must be durably linked across the clinical record and Patient World Model?**
2. **Who may read, propose, run, review, sign, or effect a consequential action, and on what evidence?**
3. **How does a clinician move from a patient finding to evidence and computation to a reviewable result, with correction and failure recovery?**

Design references: `AGENTS.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, `docs/BIOLOGICAL_ASSET_PROVENANCE.md`, `docs/EXECUTION_BACKLOG.csv`; adopted full-scope direction in draft PR #49; Composer C0–C7 design in #65 and executable bounded Composer context in #68; identity candidates #51/#53, clinical encounter domain #74, event outbox #70, clinical/LIS #56, UX/navigation #64, scientific/option investigations #71/#73/#75. **All referenced PRs are drafts or require status verification, and none is treated as merged solely by being referenced.** Reconcile overlapping contracts before wiring.

## 1. Patient-centered domain and provenance contract

### 1.1 Single ownership, multiple projections

| Contract/entity | Owning boundary / key | Must preserve | Never infer |
| --- | --- | --- | --- |
| Patient identity, institutional aliases, proxies | Future **single canonical identity owner**: opaque `patient_id`, optional `tenant_id`; alias mapping version | identity-match confidence, source, relationship, consent/delegation | matching names imply same patient; a synthetic case ID is clinical identity |
| Patient/case and cancer episode | patient owner plus case/oncology domain: `case_id`, `episode_id`, `primary_cancer_id` | multiple primaries, relapse, competing episode interpretations | one patient = one tumor or one episode |
| Encounter/note/order and administered events | first-party clinical domain, with opaque patient reference | authored/signed/corrected history; order/request vs performance vs receipt | an order proves treatment/test was performed; a demo acknowledgment is a signature |
| Source artifact/version/ingress receipt | **existing source/version owner** (`source_id`, `version`, byte fingerprint, source subject) | original bytes, external issuer, acquired/issued/clinical effective times, exact span/line, rights, supersession | same bytes prove clinical authenticity or right-patient binding |
| Observation and derived clinical assertion | clinical/biological projection, linked to one or more source version anchors | value/unit/reference/method, polarity, certainty, human verification, all original forms | missing = negative; model proposal = verified clinical conclusion |
| Cancer/lesion/specimen/assay/derived asset | oncology/pathology/molecular owners, stable typed references | anatomical origin, timepoint, sampling block, chain of custody, assay QC, reference genome/normal comparator | different blocks/lesions equivalent or new specimen = amendment |
| Treatment, symptom, patient goal and outcome | appropriate clinical and patient-contributed owners | intended regimen vs actual administrations, adverse events, response evidence, preference attribution and timing | efficacy or causation from chronological coincidence |
| Evidence, guideline/standard of care and applicability | evidence domain, versioned permitted source | bibliographic discovery vs full text, publisher rights, version/retrieval cutoff, patient-specific applicability assessment | a DOI = article appraisal; a trial listing = eligibility or availability |
| Question, investigation, computation and work item | **existing investigation/run/task owners**, with source-cutoff fingerprint | owner, intent, input versions, method/model/build, cost/budget, receipts, failures, evidence-backed findings | a planned or generated result was executed; completed job = clinician-approved conclusion |
| Review, consent, authority and audit | institutional authority/consent owners (not the model) | actor, verified identity/role, purpose, scoped grant, decision, time, policy version, revocation | interface role switch = authentication; approving extraction = approving treatment |

All read and write views must derive from these owners. Do not introduce a second editable "patient world record": the World Model is a review- and provenance-aware projection over these versioned entities and explicit interpretations.

### 1.2 Mandatory semantics

- **Source identity:** `tenant_id / patient_id / source_subject_ref / document_id / source_version` are distinguishable. Attach only after allowed match; on ambiguity quarantine, do not route to a different patient.
- **Time:** preserve `clinical_effective_time`, `specimen_collection_time`, `issued_time`, `ingested_time`, `reviewed_time`, `knowledge_cutoff` when relevant. Unknown/partial dates stay unknown/partial; no retroactive future evidence in historical replay.
- **Coverage:** distinguish present, explicitly negative, unknown, not assessed, pending, indeterminate, known missing, contradicted, and stale. Completeness is relative to a clinical question and available authorized sources.
- **Biological context:** finding → assay/method/version → exact specimen/derivative → lesion/site/episode → patient. Preserve incompatible assays/references and the source's caveats.
- **Correction:** new *version of the same source* invalidates only dependent work; a different specimen/timepoint adds a new observation. Both originals and historical review snapshots survive.
- **Interpretation ladder:** observation → extracted assertion → computed result → hypothesis → human-reviewed interpretation → clinical decision → authorized action → observed outcome. Each transition has evidence and a distinct status.
- **Permissions follow data:** original bytes, thumbnails, embeddings, semantic indexes, model prompts, caches, logs, background jobs, work items and exports carry purpose/scope/retention restrictions. Revocation blocks new access and affected queued work while retaining permitted audit history.

### 1.3 Minimal cross-domain reference envelope (proposed, not a new database schema)

```json
{
  "contract": "oi.reference-context/1",
  "tenant_id": "TENANT-SYNTH",
  "patient_id": "PATIENT-SYNTH-A",
  "case_id": "CASE-ALPHA",
  "episode_id": "EPISODE-1",
  "knowledge_cutoff": "2026-10-15T12:00:00Z",
  "subject_binding_status": "reviewed_synthetic",
  "source_refs": [
    {"source_id": "PATH-A", "version": 1, "anchor": "line:8",
     "specimen_id": "SPECIMEN-A", "clinical_effective_date": "2026-10-10",
     "issued_date": "2026-10-11"}
  ],
  "question_id": "QUESTION-1",
  "context_fingerprint": "sha256-of-canonical-authorized-reference-set"
}
```

The envelope **references** canonical owners and carries a fingerprint of selected authorized inputs; it stores no copied medical conclusions. Do not assume identifiers or `context_fingerprint` above match actual code—adapt them to implemented contracts only after review.

## 2. Clinical intent and effect/authority boundaries

The model may **suggest** a task but may never self-issue a privilege, sign a note, consent for a patient, or approve its own clinical output. All effectful operations are mediated by server-owned deterministic checks and independently authenticated actors.

### 2.1 Effect matrix (proposed policy requirements)

| Effect class | Typical example | Minimum gate | Result if gate absent |
| --- | --- | --- | --- |
| E0 read | patient source view; permitted literature metadata | authenticated actor, patient/tenant/purpose/field/rights check | deny without disclosing content |
| E1 draft | proposed interpretation, task, unsigned note, research question | E0 plus source fingerprint and "unreviewed" labeling | leave unpersisted or create a *restricted draft* under permitted scope |
| E2 compute | versioned laboratory trend or reproducible genomics tool | task-specific inputs, legal/consent scope, approved runtime, cost/budget, isolated execution, audit receipt | blocked with typed reason; never fake completion |
| E3 record-changing clinical action | sign/attest clinical note, accept/reject an interpretation, amend official record | professionally verified authorized actor, role/purpose/patient/record scope, current source versions, conflict and concurrency check | remain pending; no forged signature |
| E4 external/clinical effect | order, prescribe, send referral, transmit data, release specimen, enroll, administer | verified institutional workflow, intended-use-specific approval, applicable consent, named accountable human, explicit final confirmation, connected destination receipt | **deny/hold**, never convert a proposal to action |

This is a **specification for future authorization**, not a claim that currently injected test authorizers or demo acknowledgments authenticate clinicians.

### 2.2 Typed Composer intent preview

Before tool execution, render a preview containing: `actor_ref`, `tenant_id`, `patient_id`, `purpose`, `question_id`, `input_source_versions`, `knowledge_cutoff`, `task_type`, `effect_class`, `tool_version`, `expected_outputs`, `data_egress`, `rights/consent_decision`, `required_review`, `estimated_cost`, `idempotency_key` and `run_status`. Signatures/authority **must not** be accepted as an LLM-generated string.

States to keep distinct: `draft`, `preflight_blocked`, `awaiting_approval`, `authorized`, `running`, `failed`, `completed_unreviewed`, `stale`, `human_reviewed`, `cancelled`. A complete computation does not imply a clinically accepted result.

### 2.3 Mandatory adversarial tests

- Cross-patient/tenant read, impersonated clinician, consent expiration/revocation, unsupported external transfer, model-written "approval", forged tool receipt, retry with mutated idempotency payload → **deny**.
- Source amendment between preview and execution/save → reject stale context and offer refreshed preview; no silent substitution.
- Raw sequence absent, QC unacceptable, specimen alias conflict, reference build mismatch, or evidence rights unknown → honest blocked/unknown result, never invented analysis.
- A clinician switches from extraction review to therapy workflow → previous review grants **no** additional privilege.
- Patient-provided goals and symptoms may be reviewed and attributed; they cannot be silently turned into physician-signed conclusions.

## 3. One end-to-end synthetic workflow specification

**Scenario WP-01: chart → question → Composer → evidence → bounded compute → clinician review → amendment and targeted invalidation.**

| Step | User-visible behavior | Durable evidence / invariant | Current implementation / owner candidate |
| --- | --- | --- | --- |
| 1. Open chart | authenticated professional sees coherent identity, episode, source coverage and last-known cutoff | no cross-case contamination; absent data visible | main CaseStore/mission are synthetic; identity PRs #51/#53 |
| 2. Select finding | choose a sourced pathology or lab finding, inspect original and specimen/time | exact version/anchor and assay context; source not reduced to text summary | main source/version/biological asset; UI #64 |
| 3. Ask Composer | "What changed and which evidence is relevant to this question?" | typed task preview with current patient/question/version scope | Composer #65/#68, not a free-form clinical agent |
| 4. Retrieve evidence | show permitted metadata/full source only where licensed; classify type/applicability | citation and rights receipt; unavailable guidelines called unavailable | rights/evidence contracts; external guideline access **not implemented** |
| 5. Run optional computation | request an approved deterministic trend only if eligible input exists | input fingerprint, tool/method, output checksum, QC, failure receipt | bounded lab trend candidate #72; molecular compute outside current app |
| 6. Present draft | place findings and contradictory/missing inputs alongside chart/source | explicitly unreviewed, patient cutoff, source and algorithm reference | existing investigation and review contracts |
| 7. Human decision | verified authorized clinician records acceptance, rejection, or request for more information | separate attestation/authority, accountable actor and version | full professional authentication **not implemented**; encounter PR #74 |
| 8. Amend source | import corrected pathology; preserve previous source/version, invalidate only dependents | stale affected outputs, leave unrelated case/questions and prior snapshots unchanged | main synthetic ledger; amendment tests |
| 9. Resume | re-open work item, show exact change, collect fresh review where applicable | no automatic clinical decision or external order | investigation/review and event outbox #70 candidate |

**Acceptance** requires the full path to be demonstrated with actual application behavior and reproducible tests—not merely a written script, static UI mock, catalog row, or model-generated narrative. Mark unimplemented steps as **blocked**, not "partially completed" without evidence.

## 4. Cross-case and reference-case matrix

| Case | Why it matters | Required failure/coverage check |
| --- | --- | --- |
| WP-01 fictional routine oncology case | whole-chart comprehension, questions, evidence, review, correction | source fidelity; patient isolation; stale update |
| WP-02 fictional active treatment/toxicity | actual exposure vs prescription and clinical operations | order ≠ administration, clinically important alerts require validated rules and staffed escalation |
| WP-03 fictional survivorship/follow-up | longitudinal care and patient quality of life | no automatic missing-test alarm or over-testing |
| WP-04 fictional recurrence across institutions | identity, multiple lesions and specimen chain | no silent merging, no future-knowledge leakage |
| WP-05 fictional resource-constrained case | coverage, access, goals, no-additional-intervention option | no assumption of universal test access or aggressive experimental preference |
| WP-06 Sid-derived *synthetic* multimodal challenge | multi-block specimens, molecular/pathology/radiology evidence, competing hypotheses and therapy feasibility | no transfer of real patient data, no causality/benefit claims, no specimen or treatment conflation |

Sid Sijbrandij's public case is a **requirements stress-test input**, not clinical ground truth or a replay of therapeutic decisions. For an actual public catalog import, rights/scope and dated availability require separate gates. See existing issue #20 and research workflows.

## 5. Ownership, dependencies and review requests

**Proposed integration seam:** the first-party clinical owner publishes immutable, source-bound event and encounter references; the canonical source/version owner governs original material; the World Model and UI read/propose projections; Composer runs only authorized, version-frozen tasks; clinician review changes clinical status through its *own* authority service; outbox publishes receipts after the domain's committed transaction. Do not merge all domains into one `CaseStore` class or introduce a new parallel ledger.

| Dependency | Before integration | Evidence to request |
| --- | --- | --- |
| PF-01 identity / PF-02 authority | reconcile #51/#53 with first-party clinical host #74 | trusted account and patient binding contract, consent/delegation/revocation decisions |
| PF-03/04 source/world | retain `CaseStore` synthetic contract as adapter | exact source/version/anchor, specimen context, contradiction and amendment behavior |
| Clinical encounter/LIS | reconcile #74, #56 with #70 outbox | order/result vs performed; atomic events; note provenance and signing authority |
| Composer / tools | reconcile #65/#68 and #72 | tool registry, input cutoff, tool-version run receipt, stale-at-save tests |
| UX | reconcile #64 and Notion 09 without setting final navigation | task-first workflow, evidence inspector, accessibility and task timing |
| Clinical evidence | separate metadata discovery from validated rights to full text | versioned source receipt, applicability, professional review, licensed guidelines |
| Clinical safety/release | no live PHI or actual treatment | independent clinical/regulatory/security/rights review; intended-use decomposition |

### Immediate engineering assignments (proposals for coordinator)

1. **P0 / Contract reconciliation:** adopt or amend the opaque patient/case/episode/source reference envelope across the *existing* branches. No migration until owners agree.
2. **P0 / Authority review:** establish an executable, deny-by-default matrix for E0–E4 in a dedicated policy owner; integration tests for impersonation, revocation, stale context and unauthorized effects. Do not call synthetic test receipts real consent or credentials.
3. **P0 / Integrated fictional workflow:** wire or test only the actual supported WP-01 steps; explicitly present unavailable evidence/computation/clinical signing as unavailable. Release a passing integration receipt at a pinned merge candidate, not separately green isolated PRs.
4. **P1 / EHR continuity:** verify encounter correction → source version/provenance → Patient World Model/review projection, avoiding duplicate source ledgers.
5. **P1 / Evaluation:** freeze WP-01–06 fixtures and expected failures; compare manual and deterministic baselines before model-assisted claims.

## 6. Done means evidence, not appearance

A cross-domain slice is not done until a reproducible run proves: correct patient/episode/source/specimen binding; only authorized inputs used; work survives restart; source and external evidence rights respected; computational receipts distinguish proposed/executed; review is scoped and provenance-preserving; amendments invalidate only dependents; other patients remain isolated; denied E3/E4 requests have no effect; no Next.js or unapproved rights dependencies; and screen-reader/keyboard behavior is assessed separately from code-level correctness.

**At authoring:** this document is a contract proposal. It does **not** claim an integrated implementation exists or that the referenced unmerged PRs work together. Owner/clinical/security/rights review and actual integration are outstanding.
