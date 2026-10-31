# Open Intelligence — Patient Mission Portal & A-to-Z Orchestration

**Complementary capability annex · 31 October 2026 · proposed, not implemented**

> **Architecture precedence:** Open Intelligence is the sole current project name. This document adds a patient-facing mission portal, continuous A-to-Z orchestration, and bounded multi-engine infrastructure to the established Open Intelligence architecture. It does not replace the first-principles plan, create a parallel architecture, select a stack, reorder the current roadmap, or authorize real patient data, diagnosis, treatment, manufacturing, or clinical execution. Existing case, source, assertion, evidence, question, investigation, review, task, authority, and temporal contracts remain canonical.

## 1. The friction Open Intelligence is trying to remove

A patient’s path from symptoms to the best achievable outcome is split across people, institutions, portals, records, laboratories, specialists, trials, insurers, manufacturers, and time. Each transition can lose information, delay action, repeat work, obscure responsibility, or make an otherwise relevant option impossible to realize.

Open Intelligence should reduce the friction between:

- the patient and their own records;
- symptoms and a coherent longitudinal case;
- diagnostic findings and unresolved diagnostic questions;
- raw observations and reviewed interpretations;
- scientific evidence and patient-specific applicability;
- potentially useful options and real eligibility;
- clinical decisions and completed follow-through;
- treatment, monitoring, outcomes, and reassessment;
- research hypotheses and governed experimental development.

The platform promise is not “AI gives the answer.” The complementary promise is:

> Maintain a continuously updated, source-grounded patient mission; determine what changed, what remains unknown, and what matters next; route each question to the appropriate bounded capability; and help authorized humans turn the best feasible path into completed care or research work.

## 2. The portal is the primary patient and team surface

The first visible product surface should be a secure patient mission portal. It is the place where a patient profile is created, authorized data is gathered, diagnostic and biological material is registered, questions and goals are preserved, and the patient and care team can see the evolving state of the case.

The portal is not the source of clinical truth by itself. It is an experience over the existing governed Open Intelligence state and evidence architecture.

### Patient profile and authority

The profile should represent:

- verified identity and patient matching;
- caregivers, proxies, guardians, and delegated authority;
- treating clinicians, specialists, institutions, and coordinators;
- consent, purpose of use, sharing, revocation, and emergency boundaries;
- patient goals, risk tolerance, quality-of-life priorities, and practical constraints;
- preferred language, accessibility needs, and communication preferences.

### Data and asset intake

The portal should gather or register, as permissions and integrations allow:

- clinical notes, diagnoses, medications, procedures, and hospitalizations;
- laboratory results and longitudinal trends;
- imaging reports and, when permitted, original DICOM assets;
- pathology reports, slides, blocks, specimens, and custody state;
- genomic, transcriptomic, proteomic, immunologic, and other molecular results;
- treatment administrations, dose changes, toxicity, response, and reason for discontinuation;
- patient-reported symptoms, function, quality of life, and relevant home measurements;
- referrals, appointments, authorizations, trial contacts, and pending requests;
- research evidence, trial versions, guidelines, case reports, and regulatory changes.

Every source remains linked to identity, version, dates, specimen or assay context, receipt state, permitted use, and original artifact. Registration does not imply successful interpretation, availability, ownership, or clinical validity.

## 3. The Patient Mission is the organizing object

Each case should have a persistent Patient Mission that answers:

- What outcome is the patient trying to achieve?
- What is happening now?
- What does the available record support?
- What is missing, contradictory, stale, or unreviewed?
- Which questions could materially change the next decision?
- Which options are scientifically relevant?
- Which options are realistically reachable?
- What action is due now, who owns it, and what evidence is expected?
- What result would change the plan?
- What happened after the last action?

A Patient Mission can project existing Open Intelligence objects without introducing a duplicate ledger:

```text
Patient Mission
  ├─ identity, authority, consent, goals
  ├─ case and disease state snapshots
  ├─ source artifacts, versions, assertions, and events
  ├─ open questions, hypotheses, and uncertainty
  ├─ evidence and applicability assessments
  ├─ diagnostic, therapeutic, trial, and research options
  ├─ tasks, dependencies, owners, deadlines, and receipts
  ├─ review decisions and authorization state
  └─ outcomes, resistance, learning, and next triggers
```

The mission is longitudinal and versioned. It must support “as known at the time” replay and preserve the difference between event time, specimen time, report time, receipt time, review time, and later correction.

## 4. The A-to-Z patient loop

Open Intelligence should eventually support one continuous, inspectable loop:

```text
CONNECT AND GATHER
        ↓
VERIFY IDENTITY, RIGHTS, AND SOURCE
        ↓
NORMALIZE AND RECONCILE
        ↓
RECONSTRUCT PATIENT AND DISEASE STATE
        ↓
DETECT MISSINGNESS, CONTRADICTIONS, AND URGENT RISK
        ↓
MAINTAIN DIAGNOSTIC AND MECHANISTIC HYPOTHESES
        ↓
SEARCH AND APPRAISE RELEVANT EVIDENCE
        ↓
GENERATE POSSIBLE NEXT ACTIONS AND CARE PATHS
        ↓
COMPARE SCIENTIFIC VALUE, RISK, TIME, ACCESS, AND PATIENT GOALS
        ↓
PREPARE REVIEWABLE OPTIONS
        ↓
HUMAN REVIEW AND AUTHORIZATION
        ↓
COORDINATE CARE, TESTING, TRIALS, OR GOVERNED RESEARCH
        ↓
OBSERVE OUTCOMES AND FAILURES
        ↓
UPDATE THE PATIENT MISSION
        ↺
```

This is not a single automatic pipeline. It is a graph of bounded loops with different authority requirements. Some steps can be deterministic or highly automated; consequential medical actions remain under qualified human and institutional authority.

## 5. Complementary multi-engine capability map

The “AI goes through every component from A to Z” requirement should be implemented as orchestration across bounded engines, not as one unrestricted medical super-agent.

### Patient and record intelligence

- source intake, patient attachment, deduplication, and wrong-case quarantine;
- timeline reconstruction and amendment handling;
- terminology, unit, medication, and molecular normalization;
- patient state and disease trajectory projections;
- record completeness and data-quality assessment.

### Diagnostic and missingness intelligence

- confirmed, suspected, disputed, ruled-against, and unresolved states;
- contradictions across reports, specialists, dates, specimens, and assays;
- recommended follow-up that has no completion evidence;
- missing evidence that could change an active decision;
- urgent safety signals that require immediate escalation rather than research.

### Evidence and knowledge intelligence

- patient-conditioned literature, guideline, trial, and database retrieval;
- source rights, freshness, correction, retraction, and version tracking;
- evidence quality and patient-specific applicability;
- supporting, opposing, indirect, and insufficient evidence;
- material-change detection when new external evidence affects an open question.

### Hypothesis and experiment intelligence

- diagnostic, mechanistic, resistance, and therapeutic hypotheses;
- explicit predictions and possible falsifiers;
- computational analyses and reanalysis of existing data;
- proposed information-acquisition, in-vitro, ex-vivo, organoid, or preclinical work;
- experiment selection based on decision impact, information value, cost, risk, time, sample consumption, and reversibility.

### Therapeutic and development intelligence

- standard care, trials, approved therapies, combinations, and investigational possibilities;
- personalized vaccine, RNA, cell, gene, biologic, small-molecule, radiation, surgery, and other modality hypotheses;
- prerequisite evidence, safety questions, feasibility, and uncertainty;
- research-stage candidate design and validation planning;
- CMC, manufacturing, regulatory, and clinical-development coordination where separately governed.

### Trial, access, and care-realization intelligence

- eligibility evidence and missing criteria;
- recruiting status, site availability, timing, washout, geography, and patient burden;
- referral, authorization, scheduling, insurance, funding, travel, and caregiver dependencies;
- provider, institution, laboratory, CRO, and manufacturer capability;
- actual outreach, acceptance, rejection, completion, and execution receipts.

### Monitoring, outcome, and learning intelligence

- adaptive monitoring plans;
- symptoms, laboratory, imaging, molecular, immune, functional, and patient-reported outcomes;
- toxicity, adherence, exposure, disease progression, and resistance;
- structured failure analysis rather than a generic “did not work” label;
- patient-specific model updates before any cross-patient generalization;
- cautious knowledge promotion that preserves confounders and negative results.

### Verification, safety, and authority

- deterministic checks wherever possible;
- task-specific model evaluation and calibration;
- independent review, source inspection, and contradiction search;
- privacy, purpose, consent, egress, and role enforcement;
- explicit states for proposal, reviewed interpretation, clinician decision, authorization, execution, and observed outcome;
- emergency stop, correction propagation, and downstream invalidation.

## 6. The AI interface is a control surface, not the database

Natural-language interaction should let patients and professionals ask:

- What changed since the last review?
- What information is still missing?
- Why are two reports inconsistent?
- What questions are most important for the next appointment?
- Which trials appear relevant, and what prevents confirmation?
- What options are being considered, and what evidence supports or opposes each one?
- What action is due now, who owns it, and what are we waiting for?
- Did a new publication materially affect this case?

Every answer should be generated from a specific mission snapshot and return source links, dates, status, uncertainty, and review state. Useful conversation should create durable work: a question, correction request, investigation, task, or review proposal. It should not disappear as chat history.

The system should also be proactive. A new report, correction, scan, genomic result, trial change, or publication should trigger a bounded impact analysis:

```text
new event
  → identify affected assertions, questions, hypotheses, options, and tasks
  → run only the permitted relevant checks
  → prepare a material-change report
  → request the appropriate review
  → update accepted state only after the required authority
```

## 7. Graph projections that complement the canonical model

The current source-ledger and investigation contracts remain authoritative. The following are complementary projections or extensions, not competing stores:

1. Patient State Graph
2. Disease Evolution Graph
3. Evidence and Provenance Graph
4. Question, Hypothesis, and Uncertainty Graph
5. Experiment Graph
6. Therapeutic Option and Development Graph
7. Trial, Provider, and Care-Reachability Graph
8. Task, Dependency, and Execution Graph
9. Decision, Authority, and Consent Graph
10. Outcome, Resistance, and Learning Graph

Each edge must retain provenance and status. For example:

```text
Observation SUPPORTS Claim
Claim INFORMS Hypothesis
Experiment TESTS Hypothesis
Result SUPPORTS / WEAKENS / REFUTES Hypothesis
Hypothesis MOTIVATES Option
Option REQUIRES Evidence
Task ATTEMPTS Requirement
Human AUTHORIZES Action
Action PRODUCES Outcome
Outcome UPDATES Patient State
Correction INVALIDATES Dependent Work
```

A vector index, graph database, or model memory may provide derived retrieval or traversal. None should replace the canonical transactional state, original artifacts, event history, or review decisions.

## 8. Complementary orchestration infrastructure

The generic-system ideas are useful only when translated into Open Intelligence’s existing safety and evidence model.

### Mission compiler

Convert patient input, files, clinician questions, and new events into typed objectives, constraints, assumptions, unknowns, required evidence, allowed tools, risk, authority, and completion criteria.

### Domain and capability resolver

A case may require oncology, pathology, genomics, imaging, immunology, pharmacology, trials, logistics, insurance, manufacturing, and regulatory capabilities simultaneously. Resolve the necessary bounded capability set rather than assigning one broad domain label.

### Tool and model registry

Prefer approved deterministic tools and qualified adapters. A missing capability may justify a candidate tool, but dynamically generated tools must be quarantined, tested, permission-scoped, reviewed, versioned, monitored, and revocable before trusted use.

### Dynamic work graph

Create temporary specialist workers with typed tasks, limited context, permitted tools, budgets, expected artifacts, and completion rules. Agents coordinate through shared typed state, evidence, claims, blockers, and handoffs—not through unbounded conversation.

### Execution fabric

Support isolated computational work, database queries, simulations, external APIs, and eventually authorized laboratory or operational adapters. Every side effect requires explicit intent, permissions, receipts, failure handling, and reconciliation.

### Evaluation and assurance

Verification is task-specific. Possible states include verified, supported within scope, conditional, inconclusive, conflicted, contradicted, failed, unsafe, blocked, or awaiting authority. Agreement between models is not independent clinical corroboration.

### Event and memory substrate

Preserve every source version, run, artifact, decision, failure, correction, and outcome. Failed hypotheses and unsafe or invalid approaches remain anti-knowledge so future work does not repeat them without new evidence.

These capabilities are infrastructure proposals. They must reuse Open Intelligence’s existing source, case, evidence, review, task, and authority boundaries rather than creating a second “universal” control system.

## 9. Human authority and autonomy boundaries

Autonomy should be based on consequence and reversibility.

| Activity | Default platform role |
| --- | --- |
| Organize, retrieve, normalize, and compare permitted data | May automate with audit and validation |
| Run approved computational analysis | May automate within task and resource policy |
| Generate hypotheses or candidate options | Proposal only; preserve uncertainty and counterevidence |
| Prepare research, referral, trial, or access packets | May draft and coordinate after explicit authorization |
| Initiate external communication or spend resources | Named authorization and durable receipt required |
| Order tests, change treatment, enroll a patient, release a product, or administer therapy | Qualified human and institutional authority only |
| Manufacture or clinically deploy an individualized therapy | Separate scientific, quality, regulatory, contractual, and clinical governance |

The portal must visually distinguish AI-found evidence, unreviewed hypothesis, clinician-reviewed interpretation, authorized plan, completed action, and observed result.

## 10. First bounded implementation increment

The next portal-oriented increment should remain synthetic and reuse the existing implementation rather than start a parallel application.

A complete first mission should demonstrate:

1. Create a fictional patient profile and authority context.
2. Import multiple independently authored synthetic records with source/version identity.
3. Build a source-linked longitudinal case view.
4. Register diagnostic findings, missing states, contradictions, and open questions.
5. Provide AI-assisted interaction over a fixed case snapshot with citation and abstention.
6. Turn an important question into a bounded investigation.
7. Maintain a small option set with explicit evidence, prerequisites, and non-actionability.
8. Create owned tasks and dependency states without placing clinical orders.
9. Receive an amended or new result and recompute only affected work.
10. Show what changed, request review, preserve history, and update the mission after review.
11. Track a simulated outreach or coordination step with an execution receipt.
12. Record a simulated outcome without claiming causality.

The first portal home should answer five questions:

- Where am I now?
- What do we know and from which sources?
- What remains unknown, contradictory, or overdue?
- What paths are being investigated or prepared?
- What happens next, who owns it, and what would change the plan?

## 11. Validation and falsification

This capability should proceed only if it beats simpler workflows on defined outcomes.

Synthetic and later governed evaluations should measure:

- wrong-patient and wrong-specimen errors;
- source, date, unit, negation, and amendment fidelity;
- clinically meaningful missingness and contradiction detection;
- citation correctness and unsupported inference;
- total patient, coordinator, and clinician preparation/review burden;
- completeness and timeliness of task follow-through;
- false option or trial matches;
- preservation of uncertainty and expert disagreement;
- time to identify a material change;
- correction propagation and historical replay;
- accessibility and patient comprehension;
- incremental value over a document portal, timeline, simple search, and ordinary care navigation.

Stop or narrow the capability if it creates alert fatigue, adds review burden without better decisions, produces unsafe false confidence, cannot preserve provenance, or fails to improve practical follow-through.

## 12. Non-goals of this annex

This annex does not authorize:

- a replacement EHR;
- autonomous diagnosis or treatment selection;
- direct-to-consumer experimental therapy design;
- one model with unrestricted access to every tool;
- automatic promotion of model output into accepted clinical state;
- use of real patient records before identity, consent, security, privacy, and governance are established;
- claims of treatment benefit, cure, clinical validation, HIPAA readiness, regulatory clearance, or commercial rights;
- adoption of any particular FHIR server, graph database, orchestration framework, model provider, or cloud stack.

## 13. Integration with the existing Open Intelligence architecture

This proposal should enter through the established path:

1. Preserve the canonical project identity and current first-principles baseline.
2. Map each proposed capability to existing case/source/assertion/evidence/question/investigation/review/task/authority contracts.
3. Add only the smallest missing types or interfaces.
4. Keep original artifacts and transactional state authoritative.
5. Test with fictional data and adversarial amendments.
6. Record a bounded architecture decision for any material contract change.
7. Implement through reviewed GitHub changes with explicit acceptance evidence.
8. Keep Notion as the human-readable research and decision map, Google Drive as supporting source material, and GitHub as reviewed implementation and engineering evidence.

## Decision state

**Classification:** Architecture Extension Proposal / Supporting Research.

**Current recommendation:** preserve this as a complementary capability annex, link it to the existing patient-world/option-preservation work, and validate one synthetic Patient Mission Portal loop before accepting broader orchestration or therapeutic-development claims.

**Not implemented or clinically validated.**


## Cross-system references

- Notion architecture precedence: https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f
- Notion historical crosswalk and complementary inputs: https://app.notion.com/p/40a3866f77ef81e0a9e9c1a96773f8b9
- Google Docs companion annex: https://docs.google.com/document/d/18E3bCkguDnJ27UvOfh4ib1Fwc_RSaTaOhSUZIGFJ44k/edit
- First-principles baseline: FIRST_PRINCIPLES_PLAN.md
- Complementary precision-oncology capability map: FULL_VISION_PRECISION_ONCOLOGY.md
