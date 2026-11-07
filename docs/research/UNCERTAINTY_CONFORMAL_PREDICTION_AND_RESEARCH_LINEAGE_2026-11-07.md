# Uncertainty, conformal prediction, and experimental evidence — research-to-code crosswalk

**Date:** 7 November 2026  
**Classification:** supporting research / architecture extension proposal; no clinical claims or runtime approval  
**Baseline reviewed:** `main` at `f8ff4f4cea8dbfa1ee81cf33308e10af8aff29c4` (read on 7 November 2026)  
**Scope:** unified Patient Oncology and related research, with explicit human/veterinary applicability boundaries  
**Research home:** [Notion uncertainty chapter](https://app.notion.com/p/4113866f77ef81b1bbb0f049ec877d68)  
**Atlas:** [Open Intelligence Master Research Atlas](https://docs.google.com/document/d/1rDcbE4BWOYFws-TAm1oGGQFb9gJVle1WxUHFn_2SnqM/edit)

> This document introduces no additional canonical patient/source/observation store, graph database, experiment owner, model runtime, treatment recommender, clinical authorization, patient-data input or deployable predictor. Nothing here authorizes collection/use of real patient data. Any future feature must reuse existing ownership and undergo its own review and qualification.

## 1. Decision value

The scientific method catalog should not be a flat shopping list. Each candidate method needs (a) a defined task and sampling unit, (b) a frozen information set and lawful data, (c) a baseline, (d) an inspectable mathematical guarantee or empirical assertion, (e) a reference and failure-mode evaluation, and (f) a decision about permitted use.

**Recommended architectural increment:** a versioned `UncertaintyAssessment` projection associated with an existing saved prediction, calculation, investigation or experiment result, not a new patient fact or authoritative clinical record. The assessment may describe calibrated probabilities, prediction sets, distributions, model disagreement, measurement error, missingness or a *lack* of usable uncertainty. Distinguish each mathematically. Do not give every type the label “confidence.”

**Conformal prediction is a research candidate, not something verified in the current Open Intelligence product.** It is potentially useful as a wrapper around an already defined prediction task when calibration is feasible. It is not the first thing to implement for a deterministic clinical document parser or a data-quality/missingness state machine.

## 2. Repository reconciliation

| Existing owner / artifact | Observed facts | Consequence for research |
| --- | --- | --- |
| [AGENTS.md](../../AGENTS.md), [first-principles plan](../FIRST_PRINCIPLES_PLAN.md), [H1 demo](../H1_DEMO.md) | The main repository has a synthetic React/Vite/TypeScript + FastAPI/PostgreSQL patient workspace and a distinct Python/SQLite reference implementation. Its first-party healthcare ambition remains broader than H1. | Reuse patient/case/source/evidence/investigation/review/authority and avoid new ownership tables. No full-platform/clinical readiness claim. |
| [Laboratory experiment draft #596](https://github.com/OpenxIntelligence/open-intelligence/pull/596), [exact-head README](https://github.com/OpenxIntelligence/open-intelligence/blob/f43df38fe230f7dcd05042baf6d7f7b549dd24f7/validation/laboratory-evaluation/README.md) | As of the inspected draft head `f43df38`, the offline registry supports frozen plans/recipes, local deterministic parser and exact-source memorization control, worker limits, checkpoints, lineage, failures, cancellation, and validation-selected results. No trainable neural model is claimed. | This is a bounded **real experiment executor**, not merely registry/scoring groundwork. Extend after review; never create a parallel AutoResearch service. |
| [Semantic history draft #630](https://github.com/OpenxIntelligence/open-intelligence/pull/630), [#604](https://github.com/OpenxIntelligence/open-intelligence/issues/604) | An unmerged candidate binds historical source semantics to the existing patient owner and current permissions; completed semantic calculation/invalidation remains future work. | Bind experimental inputs and predictions to the same exact source versions and receipt cutoffs. |
| [Source-exact review preparation #645](https://github.com/OpenxIntelligence/open-intelligence/pull/645) | Source-backed, rights-checked review packet candidate; human content appraisal is explicitly *not performed*. | Uncertainty outputs must retain reviewed vs unreviewed and source-appraised vs metadata-only distinctions. |
| [Unified Patient Oncology design #649](https://github.com/OpenxIntelligence/open-intelligence/pull/649) | One Patient identity and species/context-sensitive requirements are proposed in a documentation PR. | The calibration population must distinguish species, assay, site and intended use; shared schema does not imply transferable calibration. |
| [Existing research method/experimental loop note](EXPERIMENTAL_LOOP_EXTENSION_2026-10-31.md), [proposed model run receipt](ISSUE15_MODEL_RUN_RECEIPT.md), [proposed capability registry](ISSUE15_MODEL_CAPABILITY_REGISTRY.md) | Prior papers specify complementary models and receipts; statuses vary by artifact. | Crosswalk and reuse; do not mark paper proposals as implemented. |

GitHub default-branch code search for `conformal` returned no indexed file at review time. This is a bounded search observation, **not proof** that no unpublished branch experiment exists. No conformal calibration or clinical-grade uncertainty is established by the inspected artifacts.

## 3. Method families, by actual product job

| Research family | Relevant OI job | Primary gate / priority |
| --- | --- | --- |
| Provenance, bitemporal chronology, semantics | Source/version/knowledge cutoff, amended facts, history replay | Existing ownership and typed time/missingness contracts; foundation |
| Statistical and ML comparators | Lab extraction, structured predictions, workflow metrics | Deterministic/GLM/tree baseline, leakage-safe split; foundation/pilot |
| Calibration and conformal prediction | Honest prediction intervals/sets, abstention | Independent calibration and qualified guarantee scope; research, then pilot |
| Longitudinal, survival, causal methods | Time-to-event research, visit bias, counterfactual hypotheses | Time zero, censoring, confounders and independent cohorts; research |
| Imaging, pathology, physics, metrology | Specimen/series identity, measurement error, geometry, repeatability | Raw source and acquisition context; modality pilot |
| Genomics, omics, network/structure models | Assay/context-linked research hypotheses | Species/build/assay, replication and mechanism validation; research |
| Decision theory, information value and operations | Test/review prioritization, throughput and delay | Explicit value tradeoffs, capacity and authority; operational pilot |
| Retrieval and agents | Evidence-linked questions, independent checking | Rights, claim-level citation tests and human review; existing owner |
| Reliable systems and privacy | Durable jobs, retries, revocations and recovery | Fail-closed access and backup/restore gates; foundation |
| AutoResearch/fine-tuning ontology | Experiment/data/recipe/artifact lineage and budget controls | Expand #596 from actual assessed use cases; engineering pilot |
| Clinical validation and human factors | Intended use, safe explanations, actual utility | Independent evidence, reporting, bias appraisal; mandatory gate |

Do not deploy an algorithm because a family appears in this table. For each method record: *task, output meaning, reference/assumption, information-time boundary, valid population, independent unit, evidence, limitations, permitted effects, ownership*.

## 4. Conformal prediction: statement and failure modes

For a score that is frozen before calibration, exchangeable calibration examples and a new example, a standard split-conformal construction can produce a prediction set `C_alpha(X)` satisfying **marginal** finite-sample coverage:

`P(Y_new in C_alpha(X_new)) >= 1-alpha`.

The probability is over calibration data and the future observation. It is **not** a patient-specific probability, guaranteed coverage for every subgroup, independence from model/data assumptions, or permission to perform diagnosis or treatment. When evaluating repeated observations, the independent unit can be a **patient/source family**, not every note, slice, assay or cell.

For calibration scores `s_1,...,s_n`, the conventional upper order statistic uses rank `ceil((n+1)(1-alpha))` with conservative infinity/whole-set handling when rank is `n+1`. The #596 fictional validation exercise reports one validation case. At `alpha=0.10`, `ceil((1+1)*0.90)=2` exceeds the single available calibration score. A non-vacuous 90%-coverage bound cannot be substantiated with this case. **No nominal “90% confidence” UI copy is justified.**

Distinguish methods:

| Method | What is potentially supported | What is *not* automatically supported |
| --- | --- | --- |
| Probability calibration (Platt / isotonic / temperature) | Better group-level calibration of estimated event probabilities | Finite-sample conformal coverage or clinical benefit |
| Split conformal / class-conditional conformal | Marginal / specified class-group coverage under the method's assumptions | Uniform individual or arbitrary subgroup coverage |
| Conformalized quantile regression (CQR) | Adaptive-width regression intervals with marginal coverage | Exact conditional coverage |
| Conformal risk control | Expected control of specified bounded monotone loss under assumptions | Per-person safety, arbitrary non-monotone losses, blanket “risk-free” use |
| Weighted CP under covariate shift | Qualified transport when valid likelihood-ratio/stability assumptions hold | Validity under changing conditional outcome mechanisms or arbitrary shift |
| Conformalized survival analysis | Carefully stated lower bounds with censoring assumptions | Naively treating censored observations as fully observed events |

Calibration and test labels, protected test scores, original corrections, prompts, rerankers and feature transformations must not silently cross information roles. Repeated tuning against a locked set erodes its independence.

### Examples of inappropriate claims

- A 90% conformal set does **not** mean “90% chance this patient has diagnosis A.”
- Multiple observations from one patient do **not** create independent calibration cases.
- An external site's data distribution does **not** necessarily preserve exchangeability.
- An interval that contains every label is not operationally useful just because its coverage is high.
- Abstaining on almost every case is not an intrinsic safety win: report retained-case error, deferral workload, delay and subgroup differences.
- A synthetic-only test can validate code paths; it does not validate patient-facing medical performance.

## 5. Proposed data contract (NOT implemented)

A single uncertainty assessment should be derived from and point back to existing source, event and experiment owners:

| Field group | Example fields | Integrity rule |
| --- | --- | --- |
| Assessment identity | `assessment_id`, `parent_run_or_output_ref`, `method_id/version`, `assessment_status` | No orphaned output; idempotent retries and amendment supersession |
| Intended-use & population | `target`, `time_horizon`, `patient_unit`, `species`, `site`, `assay`, `purpose` | Unsupported population and species transfer fail closed |
| Evidence and chronology | `source_version_refs`, `source_hashes`, `knowledge_cutoff`, `event_cutoff`, `mapping_version` | Historical as-of replay excludes future amendments |
| Frozen calibration | `train_manifest`, `tune_manifest`, `calibration_manifest`, `locked_test_manifest`, `n_independent` | Split boundaries and label access checks are audited |
| Mathematical validity | `assumption_basis`, `score_or_loss`, `alpha`, `quantile_rule`, `guarantee_scope` | No guarantee text without an applicable method and sample condition |
| Empirical evaluation | `covered`, `evaluated`, `coverage_ci`, `set_size`, `accepted_error`, `abstention`, `subgroups` | Numerators, denominators and excluded samples always shown |
| Oversight | `rights_decision`, `review_state`, `claim_status`, `freshness`, `prohibited_actions`, `dependency_refs` | Access cannot be inferred from ontology relationships; no auto clinical approval |

This is a projection contract proposal only. Before schema or code, inspect the exact accepted main/merge candidate: #596 offline SQLite research registry is **not** the authoritative H1 PostgreSQL case record. If it remains separate, its references are external research receipts, not silently imported patient facts.

## 6. Minimal research acceptance protocol

1. **Freeze target and comparator.** Declare exact observable outcome, prediction time, consequence of error, target population/species and a task-appropriate deterministic baseline.
2. **Freeze lawful synthetic sources.** Version and hash source files, labels, reviewer status and rights; split by patient/source-family and time; stratify sites only when the scientific question warrants it.
3. **Set protected information roles.** Fit on train, optimize on tune, conformalize on calibration, evaluate once on independently protected test. Protect preprocessing, prompt development, retrieval and expert labeling dependencies too.
4. **Precommit method and claim.** Specify score, alpha, coverage type or risk loss, finite-sample or asymptotic assumptions, minimum independent samples and fallback to "not assessable."
5. **Evaluate usefulness and failure modes.** Report covered/evaluated, coverage CI, set sizes, abstention and downstream reviewer workload; negative tests for duplicate patients, late amendments, drift, broken hashes, revoked authority and leakage.
6. **Independent adjudication.** Review uncertainty presentation, subgroup transport and applicable reporting/evidence. Mark software verified, statistically evaluated, clinically validated, and deployed as independent statuses.
7. **Amendment/revocation path.** Preserve prior assessment and source history, mark only affected outputs stale and require explicit reviewer disposition; never silently revise an approved clinical conclusion.

**Fail closed if:** insufficient calibration n, wrong sampling unit, mixed species/assays without adequate justification, stale source version, unknown reference rights, overlap across splits, missing reviewers, unbounded set sizes or unauthorized disclosure. An inconclusive result is a valid recorded research outcome.

### Initial engineering slice

Without introducing a model service, a documentation and test-only `UncertaintyAssessment` schema draft can be reviewed against the current H1 source/investigation and #596 run receipts. A pure synthetic fixture may test split independence, temporal leakage and coverage computation. Only after #596's integration is reconciled should a predeclared conformal experiment be attempted on a dataset with enough independent calibration examples. Do **not** refactor the lab parser or claim a new learned model merely to display a conformal set.

## 7. Proposed sequencing and acceptance

| Phase | Dependency | Acceptance |
| --- | --- | --- |
| P0 — reality and ownership | Resolve accepted integration head; #596/#630/#649 review | No duplicate canonical store; explicit statuses and exact heads |
| P0 — provenance and evaluation lineage | Existing case/source/experiment owners | Source version and as-known-at cutoff reconstructed; correction staleness and authority survive restore |
| P1 — uncertainty assessment proposal | H1 + offline run crosswalk | Reviewable schema and negative synthetic tests; no patient clinical UI |
| P1 — research-only conformal study | Protected calibration and appropriate sample count | Precommitted metrics, independent holdout, non-vacuous sets, reviewer workload report |
| P2 — modality and site pilots | Qualified lawful datasets and scientific partners | Separate validation for intended use, species, assay, equipment, institution and subgroup |
| P3 — any clinical-facing feature | Independent review and release gates | Human factors, clinical evidence, rights/privacy, regulatory assessment and explicit authorization |

This annex does not mark any gate complete. **Do not merge implementation PRs on the strength of this literature review.**

## 8. Traceable references

Primary papers and standards (consulted for this research snapshot):

- Angelopoulos & Bates, *A Gentle Introduction to Conformal Prediction* (2021/2022), https://arxiv.org/abs/2107.07511
- Romano, Patterson & Candès, *Conformalized Quantile Regression* (2019), https://arxiv.org/abs/1905.03222
- Angelopoulos et al., *Conformal Risk Control* (2022), https://arxiv.org/abs/2208.02814
- Tibshirani, Barber, Candès & Ramdas, *Conformal Prediction Under Covariate Shift* (2019), https://arxiv.org/abs/1904.06019
- Candès, Lei & Ren, *Conformalized Survival Analysis*, https://arxiv.org/abs/2103.09763
- TRIPOD+AI statement (BMJ 2024), https://www.bmj.com/content/385/bmj-2023-078378
- PROBAST+AI (BMJ 2025), https://www.bmj.com/content/388/bmj-2024-082505
- HL7 FHIR Observation, https://hl7.org/fhir/observation.html ; FHIR Provenance, https://hl7.org/fhir/provenance.html
- W3C PROV overview, https://www.w3.org/TR/prov-overview/

External literature supports **methods and limitations**, not an Open Intelligence implementation or clinical validation claim. Preserve citation URLs, source/revision access context and license/terms checks before copying any dataset, weights, guideline text or code.

## 9. Documentation-only validation boundaries

For this pull request, passing GitHub's Markdown preview and link review would demonstrate documentation integrity only. No backend, frontend, model, clinical, patient-data, calibration or experiment execution tests were run as part of this research document. This PR is safe to review independently of the stacked application feature branches and must remain draft until the documentation owner accepts its placement and statements.
