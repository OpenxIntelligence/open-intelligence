# Open Intelligence — Patient World Model and Future Option Preservation
**Status: Proposed product thesis and design contract, 31 October 2026. Not implemented or clinically validated.**

## Decision context
Open Intelligence continues the comprehensive oncology intelligence ambition. The narrower commercial hypothesis to test is **future cancer-option preservation**, not another EHR, scribe, treatment recommender, clinical chatbot, generic molecular profiler, or trial-matching site.

**Long-term vision:** a patient-authorized, cross-institutional computational model of the patient's disease, biological assets, scientific knowledge, hypotheses, options, approved actions, and measured outcomes.

**Candidate first customer/job:** a complex/advanced cancer patient and accountable oncology review team encountering recurrence, progression, new biopsy, resection or an approaching next-line treatment decision. Continuously identify *options at risk of becoming unavailable* and prepare reviewable, time-sensitive evidence and coordination tasks. No claim that this improves outcomes has been established.

The product should be called Open Intelligence in this repository. CEVax research is its historical conceptual source; do not split into unrelated implementations without an explicit decision.

## Core user promise: two questions at once
1. What does the available, dated, rights-qualified patient record support now?
2. What must be learned, preserved, requested, discussed or arranged **now** to prevent loss of clinically relevant options later?

An option is not a therapy recommendation. “Buildable” is a research hypothesis until independently reviewed for biological feasibility, safety, lawful access, manufacturing quality, cost, time and authorization.

## Domain invariants
- Patient authority, verified identity, case isolation and scope-bound consent precede real-data acquisition. Reading mode is not professional credential verification.
- Distinguish source artifact, reported observation, extracted assertion, derived measurement, model inference, scientific hypothesis, clinical interpretation, recommendation, physician decision, authorization, operation and outcome.
- Preserve clinical effective time, source issued time, receipt time, knowledge/cutoff time, review time and amendment time. Do not overwrite history or silently rewrite a prior belief state.
- Every consequential claim resolves to an exact source/version/anchor or is explicitly labeled unsupported. A SHA proves byte equality, not patient authenticity.
- Distinguish *unknown*, *not requested*, *not assessed*, *pending*, *negative*, *not detected*, *contradictory*, *stale*, and *withdrawn*. Never assign arbitrary numeric clinical probabilities.
- Model outputs are proposals, not authorization to order tests, give clinical advice, choose combinations, prescribe, release tissue, access experimental therapies or manufacture treatments.
- No actual PHI or unapproved external service calls in repo, logs, issues, prototypes or demos. Retain existing license, source-rights, and release gates.

## First-class objects: extend rather than replace the existing source/investigation ledger
| Entity | Core contents | Required lineage/status |
| --- | --- | --- |
| PatientWorldModelSnapshot | case, scoped cutoff, reviewed knowledge state, hypotheses, unresolved questions | source versions, produced_at, reviewer, freshness |
| DiseaseState / Lesion | episode, anatomic region, treatment exposure, competing interpretations | method, comparison limitations, time |
| BiologicalAsset | specimen/block/slide/frozen aliquot/viable cells/raw omics/image, custody, availability | collection and derivative graph, verified/unverified counts |
| DataArtifact | DICOM, pathology slides, FASTQ/BAM/CRAM/VCF, RNA/scRNA/spatial/TCR/BCR/proteome etc. | format, access rights, checksums, analysis capability level |
| EvidenceClaim | permitted source, assertion, applicability, supporting/contradictory material | source, version, retrieval date, limitations |
| Uncertainty | question, missing discriminating information, affected decisions/options | explicit unknown status, owner, recheck trigger |
| Option | standard treatment / trial / access / off-label review / research or buildable hypothesis | source/evidence level, review state, legal/clinical caveat |
| OptionDependency | test, consent, tissue, eligibility, institution, physician, production or timeline constraint | required_by, lead-time distribution if evidenced, blocker |
| OptionalityThreat | irreversible/expiring dependency, projected loss condition, urgency basis | objective trigger, uncertainty, reviewer, action alternatives |
| PreparationTask | owner, authorization needed, external counterparty, cost/time, status | execution receipt, source links, rollback/abort |
| ClinicalDecision | qualified responsible clinician, options considered, signed rationale | dated approval and exact state snapshot |
| OutcomeObservation | test/response/toxicity/absence of outcome | method, actual event time, attribution limitations |

## Dual synchronized graphs
**Patient World Model:** continuously updated patient/cancer chronology, sample/assay lineage, disease states, interventions, decisions, raw-data pointers, and uncertainty. Historic beliefs must be replayable “as known at time T.”

**Biomedical World Model:** versioned sources for scientific evidence, trial protocols, guideline references (without unlicensed text), regulatory and access programs, expert/manufacturer capabilities, and permitted published datasets. Discovering metadata is not evidence appraisal; indexed URLs do not imply rights to content.

A **patient-conditioned change detector** produces a *review-required* event when any relevant patient record, evidence item, trial, eligibility criterion, publication correction, rights status, treatment or logistics dependency changes. It must not auto-promote a new clinical conclusion.

## The option portfolio
The portfolio is NOT a ranked list of recommended treatments. Each candidate should track:
- **Type**: currently approved, guideline alternative, trial candidate, off-label research, expanded-access feasibility, frontier research, personalized/buildable *hypothesis*.
- **Epistemic status**: discovered → unassessed → evidence gathering → expert-reviewed (with scope) → operational feasibility assessed → clinician-considered → clinician-authorized → action active → observed/closed/retired.
- **Operational status**: available now, blocked by evidence, candidate eligibility, available site uncertain, tissue required, manufacturing feasibility unverified, expired, rejected or discontinued.
- **Dependencies**: resources, people, approvals, sample quality/quantity, lead time, cost, competing scheduling constraints and anticipated expiry conditions.
- **Reasons**: source-backed support, contradiction, clinical risk, unknowns and action owner.

The system must **never** map “expert reviewed” to “clinically approved” or “potential trial match” to “eligible/enrolled.”

## Optionality threat contract
An OptionalityThreat is an auditable hypothesis that a future option could be lost without an action by a stated decision point. Examples for synthetic evaluation:
1. Upcoming planned surgery without confirmed viable/frozen tumor preservation discussion.
2. Trial candidate whose **specific protocol criterion** may be affected by planned therapy; site must confirm.
3. Archived tissue inventory unknown before sending remaining slides for another assay.
4. Candidate mechanism lacking protein/localization evidence; proposal is to ask relevant experts whether more discriminating evidence would change choices.
5. Long lead-time experimental access requiring early feasibility conversation; no assertion of guaranteed supply.

Each threat must include **the source of the deadline, reliability of lead-time estimate, reversible alternatives, possible harms of preparation, owner, permissions, and explicit stop condition**. No automatic tissue reservation, ordering, diagnosis, dosing or clinical action.

## Execution and oversight
```text
New source / biomedical knowledge
  -> versioned state and evidence diff
  -> uncertainty or threatened option proposal
  -> deterministic identity/rights/authority checks
  -> qualified human review
  -> authorized coordination task
  -> receipt and failure/exception
  -> follow-up measurement or outcome
  -> revised state; history retained
```
Agents may *draft* requests, compare approved documentation, monitor publicly accessible permitted metadata, and prepare evidence packets. They do not bypass physician decisions, informed consent, board requirements, IRB/regulatory requirements, lab tissue release rules, supplier contracts or licensed practice.

## Experience: one truth, multiple projections
- **Overview / Timeline**: as-known-at date, source completeness, newly stale claims.
- **Disease & Biology**: lesion/tumor, specimen, assay, molecular evidence at suitable resolution.
- **Assets**: specimen inventory including *unverified* custody/quantity and future requirements.
- **Uncertainty**: missing/contradictory evidence and decision affected.
- **Option Portfolio**: candidate status, dependency chain, readiness, review owner, source age.
- **Time-to-Option**: Gantt-like evidence/operational critical path; ranges not false precision.
- **Threats / Review Inbox**: time-sensitive, proof-linked tasks with conservative safety messaging.
- **World Watch**: change event, why possibly relevant, independent appraisal and review state.
- **Collaboration / Board**: specialists and patient see shared facts at role-appropriate detail; clinician decisions remain distinct.
- **Audit / Export**: historical cutoffs, revised sources, decisions, task receipts, outcome and limitations.

## First implementation contract (fictional only)
Integrate with existing case/question/source/evidence lineage; avoid a second isolated data model.
- Represent 2 synthetic patient cases, 3 historical snapshots, 4+ versioned sources, and at least one amendment.
- Persist 3–5 option candidates and dependency relationships, including a false-positive candidate, one disappearing *hypothetical* trial window, and a tissue-preservation *discussion*, all explicitly fictional.
- Render option history as of T0/T1 without retrospective leakage; make source and evidence cutoff inspectable.
- On amended or out-of-order input, mark only dependent options/threats stale, reopen review, preserve earlier snapshots and require distinct authority to accept any clinical assertion.
- Provide a synthetic reviewer/owner action queue (no real-world orders or calls). Failure on wrong-case, missing source, revoked rights or unreviewed candidate must be safe.
- Show *why action matters* versus *why action is not yet justified* equally prominently.

## Validation and commercial status
No real clinical utility, prospective benefit, willing buyer, consumer willingness to pay, legal clearance or achievable marginal-cost reduction is proven by simulation. First run blinded historical/synthetic case replay with independent experts and comparator workflows; pre-register errors, time saved, actionable early opportunities, false alarms, harms, and total acquisition/review labor. See [validation protocol](OPTION_PRESERVATION_VALIDATION.md) and [competitive register](COMPETITIVE_THESIS_REGISTER.md).

## Cross-references
- [First-principles plan](FIRST_PRINCIPLES_PLAN.md)
- [Execution backlog](EXECUTION_BACKLOG.csv)
- [Implementation status](IMPLEMENTATION_STATUS.md)
- [Evidence contract](SYNTHETIC_EVIDENCE_CONTRACT.md)
- Notion project: https://app.notion.com/p/40a3866f77ef81c7a73af37e4ca73654
- Working Google Docs: https://drive.google.com/drive/folders/1O037nOW8L15vnsjGEWwETVKejyB71779
