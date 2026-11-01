# Experimental-loop automation — complementary research extension

**Project:** Open Intelligence  
**Classification:** Supporting Research / Architecture Extension Proposal — **not adopted**  
**Date:** 2026-10-31  
**Scope:** Additive investigation and evaluation capability within the existing longitudinal oncology/case architecture. **Not a replacement architecture, product rename, new platform, clinical decision engine, or authorization to execute treatments.**

## Decision in one paragraph

Explore whether Open Intelligence can improve its existing **case → question/hypothesis → evidence → scoped review → update** workflow by making *digital, reversible, policy-bounded scientific evaluations* easier to propose, execute, compare, and reproduce. The experimental-loop concept is a possible **workflow extension** to the current investigation lifecycle and evidence ledger, not a reason to introduce another orchestration platform, graph database, independent patient model, or automatic medical-action path. Discovery Loop's proposed ML-first approach is an **external research analogy**, not a dependency, technology endorsement, implemented capability, or evidence of clinical outcomes.

## 1. What we are adding — and what is already owned

| Existing owner or contract | Additive opportunity (proposed, not implemented) | Boundary |
| --- | --- | --- |
| Versioned patient case, source ledger and three-clock temporal model | Freeze an as-known-at snapshot for an evaluation, then attribute results to exactly that version | Never overwrite originals or convert an evaluation output directly into patient fact |
| Durable questions, hypotheses and investigation state machine | Link multiple falsifiable, competing evaluation proposals to one scoped question | No parallel ungoverned “AI scientist” record system |
| Evidence source/claim/applicability model | Track predicted observations, independent counterevidence, null results and confounders | Multiple model votes are not independent biomedical studies |
| Agent tool contracts and human authority | Add typed, effect-classed run proposals and receipts to the existing task/authorization model | Only safe digital runs may be automatically executed within prior authorization |
| Amendment → stale review → human re-review | Invalidate relevant evaluations when input, evidence, software or permission changes | A refreshed computation cannot approve a new clinical conclusion |
| Engineering/independent validation | Evaluate whether the extension reduces human effort without increasing consequential errors | A synthetic benchmark cannot establish real-world clinical value |

**Architecture precedence:** [Repository first-principles plan](../FIRST_PRINCIPLES_PLAN.md), [contributor constraints](../../AGENTS.md), and [Notion identity/precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f). Historical “CEVax” documents are preserved as **historical source references only**.

## 2. Minimal loop inside the existing investigation

1. **Observe** a permitted, source-versioned case amendment or external evidence update.
2. **Scope** a human-owned question; record what decision/review the information might influence.
3. **Generate** candidate *investigations* or computational checks plus competing explanations; models output drafts only.
4. **Select** via deterministic permission/rights/budget gates and reviewable prioritization; record excluded candidates and reasons.
5. **Execute** only authorized reproducible digital tasks in an isolated environment. Record attempt, tool, code/model/data versions and resource usage.
6. **Evaluate** outcomes against predeclared criteria, baselines, negative controls and uncertainty; do not score solely on a model grading its own results.
7. **Review** the evidence and resulting claims in the existing review state machine; clinical implications remain clinician-owned.
8. **Update** case-linked evidence and investigation freshness without silently modifying authoritative patient facts; repeat only if an approved next question remains.

This is **not** “patient data → LLM → treatment → new patient data.” A simulation result, an in-vitro assay, a planned intervention, an executed intervention, and a clinical observation are different records with different owners.

## 3. Three explicit execution classes

| Class | Examples | Potential automation | Release boundary |
| --- | --- | --- | --- |
| A — synthetic / general computational engineering | Recompute a benchmark, test competing parsers, evaluate source-linking algorithms, compare retrieval/rerankers on fictional cases | Can be automatically run if budget, tool, environment and security controls permit | Do not treat benchmark gain as clinical evidence or deploy algorithm changes automatically |
| B — authorized case-specific computation | Rerun a qualified assay interpretation in an authorized environment; check versioned literature applicability; reproduce an approved analysis | Only within patient-specific consent/purpose, use rights and reviewer-defined scope; output is a candidate scientific artifact | No PHI to unqualified providers, no unreviewed diagnosis, no automatic publication |
| C — external physical/clinical work | Tissue assays, organoids, imaging, blood draws, treatment, expanded access, labs, collaborator requests | AI may draft a bounded handoff or prepare questions; actual orders, acceptance and execution are **human/institution-owned** | No autonomous order, intervention, sample release, consent, lab instruction or claim that coordination equates to performance |

A fourth category—**hypothetical simulation only**—must be explicitly labeled when an experiment did not actually execute. Planning thousands of experiments is not running thousands of experiments.

## 4. Minimal record extension (proposal; do not migrate schemas yet)

Extend existing case/question/task IDs and source/version references, rather than creating a second case or evidence store.

```text
ExperimentProposal:
  id, case_id (if case-bound), question_id, hypothesis_ids
  kind, stated prediction, falsifier / negative control
  input_refs_and_versions, as_known_at, intended decision relevance
  method/protocol_ref, run_environment, permission_scope, rights_status
  expected_signal, measurement_plan, uncertainty/limits
  estimated_compute/time/cost, effect_class, owner, proposal_state

EvaluationRunReceipt:
  proposal_id, attempt_id, actual_execution_state
  immutable input/content digests, source and model/code versions
  execution environment and isolated outputs, parameters/seeds
  started/ended timestamps, cost/resource record, errors
  observed metrics and uncertainty, negative/null results
  comparator, reproduction_status, independent_verification
  invalidation dependencies, reviewer and review decision
```

**State machine (illustrative mapping, not a competing orchestration engine):** draft → scoped → authorized → queued → running → result-ready → independently checked → human-review → accepted-as-evidence / rejected / inconclusive. Include quarantined, canceled, budget-exhausted and superseded. Reuse the repository's existing `Draft → Scoped → Authorized → Running → EvidenceReady → Verification → ClinicianReview → Closed` states and map experiment-specific status as metadata.

Persist causal claims separately from temporal associations: “new biomarker after treatment” is not evidence that treatment caused the biomarker. Retain reference standards, assay limitations, batch artifacts, and unknown outcomes.

## 5. Selection policy: optimize for useful learning, not run count

Suggested ranking dimensions, **not a validated single numeric score**:

- Likely reduction in *decision-relevant* uncertainty, conditional on adequate measurements.
- Falsifiability and discrimination among genuinely competing hypotheses.
- Evidence quality, applicability to current case state, and independence of sources.
- Technical feasibility, reproducibility, failure detectability, and rights/authorization.
- Expected cost, time, compute budget, clinical burden and risk.
- Opportunity cost, evaluation redundancy and time sensitivity.
- Independence of graders and held-out tests; avoid benchmark leakage and self-confirming models.

An optimization policy may propose an order, but hard constraints—permissions, source rights, no clinical effect, budgets, and human review—must be enforced outside the model. If prioritization cannot be justified, abstain and request a human decision. A computed “value of information” is a research heuristic, not a clinical order or a validated survival-utility score.

## 6. First falsifiable, low-risk evaluation

**Question:** Does adding a bounded evaluation-proposal/receipt mechanism help reviewers identify and investigate an evidence-changing uncertainty more reliably than the existing deterministic/manual workflow?

**Fixture:** independently authored fictional longitudinal case(s) with contradictory reports, specimen identity drift, an amended observation, an out-of-order document, and a fictional external evidence revision. Prespecify accepted facts, unknowns, valid scope, expected affected questions, forbidden actions and counterexamples before tool execution.

**Arms:** (A) existing deterministic/manual workflow; (B) model-assisted candidate proposals with a deterministic selector; optionally (C) deterministic candidate proposal rules. Use the same frozen input cutoff and access to evidence.

**Representative candidate tasks:** compare source versions, check specimen/assay identity, test whether a hypothesis's supporting evidence is stale, generate a reviewer-ready evidence-gap brief; a simulated attempt to issue a medical order must be denied and audited.

**Prespecified measures:** correct source lineage, actionable-vs-noisy review proposals, missed critical contradictions, false authority promotions, replay reproducibility, reviewer correction burden, end-to-end elapsed effort, compute/API cost, invalidated-result propagation, and rate of clinically consequential hallucinations. Track denominators and confidence intervals; report failures and abstentions rather than only success anecdotes.

**Acceptance to advance:** (1) zero allowed authority/PHI/rights bypasses across the adversarial suite; (2) full replay from immutable inputs; (3) negative and unknown states retained; (4) improvement against a simpler baseline with no unacceptable increase in serious error or reviewer burden. Thresholds and study size require approval **before** running. If the extension fails, keep the base workflow and archive the evidence; do not force an experimental runtime into the product.

## 7. Sequencing and dependencies

- **Research only now:** map contracts; freeze evaluation questions and schema proposal. Do **not** import Discovery Loop code, adopt its stack, or claim ML self-improvement.
- **After OI-006/007/008/009 are stable:** evaluate an isolated synthetic experiment proposal + run receipt *attached to existing questions and evidence*, without a new patient graph.
- **After OI-011/014 protocol and rights gates:** compare qualified model assistance with a simple deterministic baseline and human workflow.
- **Future optional work:** domain-specific computational biology, specialty imaging/genomics, lab coordination, and multi-institution partners require individual permission, assay, quality, safety and clinical evaluation. No default roadmap commitment.
- **Never inferred:** clinical outcome benefit, commercial viability, autonomous treatment, or measurable success merely from throughput/many parallel attempts.

## 8. Open decisions / failure modes

1. Is the “experiment” a distinct typed object or a subtype of existing `Investigation/Task`? Default to the *smallest* compatible extension.
2. Which data inputs may be reused for a digital evaluation, and where may each computation execute?
3. Who adjudicates an assay, analysis validity, patient relevance, and final reviewed claim?
4. How do we prevent correlated model proposals, overfitting, publication bias, benchmark leakage and false certainty?
5. What events invalidate outputs (source amendment, source retraction, tool/model revision, consent revocation, specimen reassignment)?
6. What automated steps have **demonstrated** net improvement in complete reviewer workflow cost and quality?
7. What are the actual effective source-code, dataset, model-weight, service, article and patient-data rights?

**Do not create a separate graph platform or a parallel orchestration system just to embody these ideas.** A conceptual “hypothesis graph” or “experiment graph” is initially a view over versioned assertions, tasks, runs and provenance already owned by Open Intelligence.

## 9. Source attribution and status

- [Discovery Loop — official website](https://www.discoveryloop.com/): public mission statement proposing automation of the ML experiment cycle and self-use. **External research inspiration only; not independent validation of promised scale/quality or a dependency.** Do not copy its prose, code, branding or protected content.
- [National Academies — automated research workflows and discovery loop](https://www.nationalacademies.org/read/26532/chapter/4): background research on model-directed experimental design, not oncology product validation.
- [Open Intelligence first-principles plan](../FIRST_PRINCIPLES_PLAN.md); [case/agent authority page](https://app.notion.com/p/40a3866f77ef81fc929eca89e41a3f4a); [rights governance page](https://app.notion.com/p/40a3866f77ef815a97d5e016ededf5b9).
- [Historical Sid Sijbrandij publicly shared case material](https://osteosarc.com/): case-study *workflow inspiration*, not proof of efficacy, causality, or authorization to use individual-level data in software.

**Status:** proposed/unevaluated research, with no added dependency, clinical functionality, deployed job runner or implied change to the accepted architecture. Advance only through a separate scoped ADR or accepted engineering issue after baseline testing and source/rights review.
