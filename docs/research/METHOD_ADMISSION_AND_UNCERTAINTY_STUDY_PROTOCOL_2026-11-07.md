# Method admission and uncertainty-study protocol — Open Intelligence

**7 November 2026 · Proposed research protocol, NOT an adopted implementation, statistical validation, or clinical authorization.**  
**Main reviewed:** `f8ff4f4cea8dbfa1ee81cf33308e10af8aff29c4`. **Companion research crosswalk:** [Uncertainty, conformal prediction and experimental evidence](UNCERTAINTY_CONFORMAL_PREDICTION_AND_RESEARCH_LINEAGE_2026-11-07.md).  
**Existing owners:** [AGENTS.md](../../AGENTS.md), [first principles](../FIRST_PRINCIPLES_PLAN.md), [independent evaluation packet](../evaluation/PACKET_TEMPLATE.md), [specialist model evaluation draft](ISSUE15_EVALUATION_DESIGN.md), [issue #604](https://github.com/OpenxIntelligence/open-intelligence/issues/604), [draft #596](https://github.com/OpenxIntelligence/open-intelligence/pull/596).

## 1. Why this protocol exists

A named technique, a published guarantee, a program passing synthetic tests, and a clinically useful intervention are **four different statements**. Open Intelligence needs a repeatable gate that links scientific methods to patient and laboratory questions without quietly converting any of those statements into the next.

**Adopt no new canonical data owner.** The H1 PostgreSQL patient/source/investigation/review/permission contracts remain authoritative for the connected fictional patient application; the offline SQLite research registry in draft #596 has a different role. This document extends the *existing* evidence and evaluation packet workflow, rather than creating another model catalog or experiment scheduler. An accepted, exact-head implementation review is required before introducing fields or code.

The platform remains one modular Patient Oncology ecosystem spanning human and veterinary oncology and later broader health/science, but species-specific evidence, assay ranges, instruments, sites, exposure and intended use may not be borrowed by default.

## 2. Admission record: one per task–method–version

Complete and freeze these fields *before* viewing the locked evaluation results. A missing entry is **not assessed**, never a silent default.

| Required field | Definition / acceptance question |
| --- | --- |
| `research_question_id` / owner | What exact unknown matters to the existing case, operation or scientific experiment? Which existing module is accountable? |
| `method_family` / version / source | Which algorithm, theorem, implementation and precise source version? Any rights or artifact restrictions? |
| `task` / output type | Is the output a source-derived fact, measurement, point prediction, probability, prediction set, causal estimate, simulation, hypothesis or proposed action? |
| `intended_user_effect` / harm | Who sees it and what may change? Distinguish research-only, internal quality gate, human-reviewed suggestion and separately authorized clinical action. |
| `unit_of_analysis` / applicability | Patient, episode, specimen, source family, site, experiment, animal, instrument, assay, species, time-zero and endpoint. Explain dependence. |
| `as_known_at` / source versions | Exact input versions, clinical/event time, issue time, receipt time, amendment and permitted cutoff. Later information cannot leak backwards. |
| `rights_and_authority` | Which access grant, purpose, consent, source rights, and environment allow this use? A study authorization does not imply patient-data egress or clinical use. |
| `baseline_and_alternatives` | Include no-model and deterministic methods. What improvement would justify complexity and review burden? |
| `assumptions_and_identifiability` | Exchangeability, measurement and label validity, censoring, confounding, priors, shift model, physical boundary conditions, etc., as appropriate. |
| `train_tune_calibrate_test` | Immutable manifests, split/group keys, model-selection exposure and exact locked-test access. Declare unavailable roles explicitly. |
| `metrics_denominators` | Raw successes, failures and exclusions; task accuracy, uncertainty calibration/coverage, harms, latency, compute, reviewer minutes and resource burdens. |
| `falsification_tests` | What counterexample would invalidate the method, data, guarantee or usefulness claim? |
| `claim_status_and_release` | Distinguish proposed, software-tested, statistically assessed, independently externally evaluated, clinically evaluated, authorized and deployed—do not use one "validated" boolean. |

**Typed uncertainty is not a single numerical confidence field.** Preserve the distinction among (a) missing/pending/unknown source states, (b) measurement error, (c) predictive probabilities, (d) conformal set/interval coverage, (e) posterior/model uncertainty, (f) between-model disagreement, (g) scientific evidence quality, and (h) human interpretation/review. Each needs different units, validation and explanatory text.

## 3. Research-to-product admission matrix

| Area / candidate family | Earliest useful *bounded* research question | Existing owner and initial gate | Do not imply |
| --- | --- | --- | --- |
| Provenance/ontology/bitemporal records | Can a historical exact-version report be replayed without importing a later amendment? | Patient/source semantic history; #604/#630; rights-aware source fingerprint | Review approval from a timestamp |
| Baselines, GLM, tree/boosting, kernels | Does a learned extraction or operational comparator beat deterministic code on a protected set? | OI-011/018, #596; same task, frozen labels and budget | Neural model superiority by default |
| Calibration, conformal prediction, risk control | Does a defined predictor return useful and correctly scoped sets on independent units? | Evaluation receipts, split integrity and documented coverage assumptions | Individual diagnostic certainty |
| Survival, longitudinal and causal analysis | Can time zero, censoring, event clocks, selection/confounding be justified? | Source chronology; predefined estimand/endpoint; research-only | Causal treatment effect from association |
| Imaging/pathology/measurement physics | Do derived coordinates, segmentation/volume and uncertainty survive device/site changes? | Original DICOM/pathology records, specimen and geometry provenance | Clinical measurement validity from Dice alone |
| Genomics, single-cell, multiomics and molecular design | Can specimen/assay/genome build and independent experimental unit be traced? | Molecular and biological-asset owners; rights, reference assembly and negative assays | Generated structure or cluster as clinical actionability |
| Decision theory, value of information, optimization | Does a proposed review/test ordering reduce burden under declared constraints? | Existing tasks and patient preferences; operational simulation or recorded human review | Automatically ranked treatment strategy |
| Retrieval and agents | Are every cited fact and counterclaim independently supported by permitted original content? | Evidence/investigation/human review; source-anchor, rights and freshness checks | Multiple agent agreement as independent scientific proof |
| Privacy/reliability | Does revocation, crash, retry or backup/restore preserve version and authority? | Existing worker, event and grant contracts; exact-head execution | Security/compliance from unit tests alone |
| AutoResearch and fine-tuning ontology | Can an authorized candidate run, fail, compare and be reproduced at equal budgets? | #596 offline dataset/recipe/trial/artifact lineage; no second canonical store | Neural training or deployment from a memorization control |
| Clinical human factors and external validity | Do reviewers and people actually make fewer consequential mistakes, with acceptable burden? | Existing [independent evaluation packet](../evaluation/PACKET_TEMPLATE.md), domain review and external study design | Clinical benefit from synthetic acceptance tests |

If no task, data or comparator can be specified, retain the idea as **research lead**, not an implementation backlog commitment.

## 4. First conformal study: a *feasibility design*, not an initiated trial

**Research question:** Does the addition of a formally scoped set-valued uncertainty wrapper to a frozen, score-producing *synthetic classification predictor* improve the information available to a nonclinical reviewer, without making misleading confidence claims or unacceptable deferrals?

### 4.1 Model and data prerequisites

- There is **no verified score-producing learned classification predictor or independent conformal calibration cohort** established by the inspected #596 exercise. Its two candidate arms are a deterministic parser and an exact-source memorization/leakage control, selected on **one** fictional validation case. This does not become an independent calibration set by renaming it.
- First define a lawful, independently authored synthetic target, label taxonomy and scoring model. Keep the comparison with a no-conformal deterministic alternative. If no meaningful, frozen score exists, STOP: a conformal layer would be theater.
- Define the **exchangeable sampling unit**. If multiple notes/assays come from one fictional patient or source family, do not count them as independent subjects. Patient-disjoint grouping is a leakage safeguard; it does not automatically establish exchangeability of dependent measurement-level scores.
- Freeze *disjoint* training, model-selection/tuning, conformal calibration, and locked-test information roles. Labels in calibration cannot choose model architecture, change score definitions or revise preprocessing after the fact. Include retrieval corpora, embedding fits, prompts and annotation heuristics in the dependency audit.
- Freeze species, population, time interval, site, assay and intended-use profile. A distinct site, shifted time distribution or canine/human transfer requires fresh assessment, not an inherited marginal-coverage claim.

### 4.2 Mathematical statement and conservative finite-sample rule

For standard split conformal with a **fixed** prediction rule and exchangeable calibration scores and future score at the declared unit, let `s_1,...,s_n` be conformity *error* scores (higher = less conforming) and `alpha` the target miscoverage. Set

```text
k = ceil((n + 1) * (1 - alpha))
if k > n:
    threshold = +infinity             # full/vacuous prediction set
else:
    threshold = kth_smallest(calibration_scores)
C_alpha(x) = { y : score(x, y) <= threshold }
```

Then a qualified **marginal**, not individual or arbitrary-subgroup, coverage statement applies. Ties, scores, exchangeability, randomness and group units must be specified; do not mechanically apply this recipe to survival censoring, time series, weighted-shift or risk-control tasks.

At `alpha = 0.10`: `n=1 -> k=2 > n` (vacuous), `n=8 -> k=9 > n`, `n=9 -> k=9` (finite threshold), and `n=19 -> k=18`. **Nine independent calibration units is only the smallest non-vacuous rank in this construction; it is NOT a statistically adequate or clinically useful sample-size recommendation.** Sample size for useful set size, precision, coverage subgroups and error consequences must be justified separately.

### 4.3 Preregistered comparison and honest readout

**Arms:** A = original frozen score-producing predictor with explicitly defined ordinary outputs; B = same predictor and calibration-frozen split-conformal wrapper. If no model fits, conduct only a pure mathematical/unit-fixture exercise and report it as such. Do not fabricate a training run.

**Primary feasibility outcomes (no clinical thresholds implied):** `covered / evaluable` with exact denominator and exclusions; median/p95 prediction-set size; proportion returning all labels; uninformative/empty sets; error among accepted singleton results; deferral/abstention fraction; simulated reviewer time; rejected/unknown states and reason; empirical uncertainty for the cohort design. Prespecify acceptability thresholds **before** opening locked test, or report as descriptive feasibility only. For clustered observations, use design-aware uncertainty estimates; a naive binomial interval over repeated slices is inappropriate.

**Secondary:** group-specific performance with sample sizes, species/site/assay applicability; calibration plot, log loss/Brier when probabilities are actually produced; latency, memory, compute and human workload. Record failures, null findings, inconsistent labels, drift and unassessable cohorts.

**Guarantee language:** "At a nominal 90% marginal coverage target, the specified method has the stated finite-sample guarantee *under its recorded assumptions*." Do not say "this patient has a 90% chance of diagnosis X", "90% diagnostic confidence" or "clinically safe".

**Artifacts:** frozen protocol, exact commit and dependency hashes, code and data manifests, assessed rights, calibration score manifest, result receipt, per-unit predictions, quality and burden report, technical reviewer sign-off and explicit non-claims. Use the existing evaluation packet and, once accepted, the existing run/artifact owner. Do not register model weights that were never trained.

## 5. Falsification/negative controls for a synthetic harness

| Test | Trigger | Required outcome |
| --- | --- | --- |
| CP-01 | `n=1, alpha=.10` with no predeclared alternative | Threshold is infinite/full set; no non-vacuous coverage UI |
| CP-02 | `n=8, alpha=.10` | Full/vacuous threshold; cannot promote a "90% confident" label |
| CP-03 | `n=9, alpha=.10` | Rank 9 computed correctly; feasibility NOT automatically approved |
| CP-04 | Same fictional patient/source family appears in calibration and test | Overlap detected; result ineligible until split corrected |
| CP-05 | Validation case used for candidate selection repurposed for calibration | Leakage/reuse blocked unless a new valid study is designed |
| CP-06 | Training/test leakage via preprocessing, embedding, prompt or lookup table | Result blocked, lineage/failure retained |
| CP-07 | Later report receipt is backdated to an earlier clinical event | Historical cutoff excludes later knowledge |
| CP-08 | Source amended after model output | Original immutable; dependent assessment stale; unrelated cases unchanged |
| CP-09 | Unknown, negative, below-detection and pending are conflated | Typed data-quality/label failure, not an invented negative observation |
| CP-10 | Species/site/assay shifts outside applicability profile | Qualified evaluation required; no inherited guarantee |
| CP-11 | Test includes dependent tissue tiles/cells as distinct patients | Correct independent unit enforced or statistical claim withheld |
| CP-12 | Revoked source right or insufficient actor/purpose authority | Deny dependent read/reuse; no bypass via stored assessment |
| CP-13 | Missing true label, unresolved adjudication or unassessable score | Excluded with counted reason; not silently scored as correct/incorrect |
| CP-14 | All-label set, mass abstention or wrong-polarity but nominal coverage | Show low usefulness and safety failure rather than celebrate coverage |
| CP-15 | Improper UI says "90% diagnostic confidence" | Wording gate rejects the claim even if mathematical coverage passes |
| CP-16 | Test labels used for tuning thresholds after review | Locked-test independence breached; invalidate promotion and register deviation |
| CP-17 | Misreported `n`, misordered quantile or mismatched artifact digest | Deterministic integrity failure; no passing receipt |
| CP-18 | Correct statistical output used to authorize a clinical order | Authorization boundary rejects effect; human review still required |

**Never turn these into passing-test claims until code actually runs at the exact candidate revision.** Synthetic tests establish only the correctness of the exercised software invariants; clinical performance requires separate lawful independent validation.

## 6. Handoff to engineering and review gates

1. **P0 — source/authority reconciliation:** confirm the accepted integration head and precise owner contracts; follow [#604](https://github.com/OpenxIntelligence/open-intelligence/issues/604), not a competing clinical ontology.
2. **P0 — AutoResearch reconciliation:** review/land suitable pieces of [draft #596](https://github.com/OpenxIntelligence/open-intelligence/pull/596) with exact-head tests and historical failure receipts. Do not import its offline registry as patient truth.
3. **P1 — method-admission schema:** propose an additive, pure typed protocol and negative synthetic checks **through existing evaluation/run receipts**, with exact split/group/time/assumption fields and no new patient mutation.
4. **P1 — nonclinical feasibility:** only if frozen scores and independent calibration groups exist, execute and report the finite-sample/risk hypothesis with negative controls, cost and reviewer burden. Preserve null and stopped runs.
5. **P2 — prospective external suitability:** independent species/population/site/assay/clinical workflow assessment and rights/regulatory gates before any new real-data or patient-facing effect.

**Status vocabulary:** `research_lead` → `protocol_frozen` → `software_tested` → `statistically_assessed` → `externally_assessed` → `human_factors_evaluated` → `use_authorized`. Treat these as proposed descriptive stages, *not* schema fields or transitions authorized by this document. Progress in one dimension does not imply another.

## 7. Source map and claims

- [Angelopoulos & Bates, *A Gentle Introduction to Conformal Prediction and Distribution-Free Uncertainty Quantification*](https://arxiv.org/abs/2107.07511) — marginal guarantees under exchangeability and extensions.
- [Angelopoulos, Barber & Bates, *Theoretical Foundations of Conformal Prediction*](https://arxiv.org/abs/2411.11824) — formal proofs and scope; additional research reading.
- [Romano, Patterson & Candès, *Conformalized Quantile Regression*](https://arxiv.org/abs/1905.03222) — heteroscedastic interval method.
- [Angelopoulos et al., *Conformal Risk Control*](https://arxiv.org/abs/2208.02814) — expectation of specified monotone loss, not universal safety.
- [Tibshirani et al., *Conformal Prediction Under Covariate Shift*](https://arxiv.org/abs/1904.06019) — qualified weighting under shifted covariates.
- [Candès, Lei & Ren, *Conformalized Survival Analysis*](https://arxiv.org/abs/2103.09763) — censoring-dependent results.
- [BMJ, *Evaluation of clinical prediction models* (2024)](https://www.bmj.com/content/384/bmj-2023-074819) — prediction design, splitting, and external validation considerations.
- [TRIPOD+AI (2024)](https://www.bmj.com/content/385/bmj-2023-078378) — reporting; [PROBAST+AI (2025)](https://www.bmj.com/content/388/bmj-2024-082505) — bias and applicability appraisal.
- [Existing protocol and results template](../evaluation/PACKET_TEMPLATE.md) — project-local evaluation governance; this document is not its replacement.

Research papers, protocols and software checks provide **different levels of evidence**. The intended-use, rights, patient-authority and clinical approval decisions remain separate and unchanged.
