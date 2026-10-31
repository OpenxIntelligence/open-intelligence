# Open Intelligence — Full Precision-Oncology World Model Vision
**Research architecture / future capability map · 31 October 2026 · proposed, not built**

This document **preserves the entire long-term CEVax-inspired vision** while the first commercial wedge, *Future Option Preservation*, is experimentally falsified. The near-term product spec is [OPTION_PRESERVATION_PRODUCT_SPEC.md](OPTION_PRESERVATION_PRODUCT_SPEC.md). This is not a commitment to build every module or medically actionable claims.

## 1. Full mission
A cancer patient needs a durable, independent, governed computational account of what is known, suspected, unknown, contradicted, planned, attempted, measured and learned across their life and the changing scientific world. Source and knowledge history must survive amendments, vendor changes and clinician transitions. The same substrate may later serve other conditions, but oncology is the first deep domain.

A useful analogy is **version control for patient-specific medical beliefs**, combined with a decision/experimental/operations ledger. Do not confuse this with an EHR replacement or an autonomous oncologist.

## 2. Two coupled world models
**Patient World Model (PWM)**:
- Longitudinal biography, clinical episodes, primary tumors and recurrences, all lesions and sampling sites, therapies, clinical and molecular findings, toxicity, outcomes, patient goals, proxies and permissions.
- Raw-and-derived data custody: EHR/claims/medications, DICOM/RT, pathology slides, WGS/WES FASTQ/BAM/CRAM/VCF, bulk RNA, scRNA/scATAC, spatial, TCR/BCR, proteomics, metabolomics, ctDNA/MRD, viable cells/organoids/functional assays; registered presence does **not** imply analytical ability or data-use rights.
- Timestamped source receipt, interpretation, hypothesis, clinical decision, operations, response, contradictory claims and missingness.
- Replay any historical knowledge snapshot with publication cutoff and patient evidence cutoff separately; record what was believed at the time without retroactive edits.
- Model assertions as typed attributed evidence claims, never authoritative narrative by default.

**Biomedical World Model (BWM)**:
- Permitted clinical information/guidelines, scientific literature, preprints, trial registry and protocol versions, molecular and target biology, known modality risks, investigator/capability directory, manufacturer/assay capacity, access programs and relevant regulatory pathways.
- Each source has identity, retrieval, permission and provenance, publication and correction dates, intended use, applicability, limitations and review status.
- Patient-conditioned deltas ask “which changes may alter this patient's option, evidence gap or deadline?”; no unsolicited clinical conclusion is promoted automatically.

**Interaction:** PWM state + BWM candidate evidence → versioned question/hypothesis/option → independent reviewer decision → authorized task → external outcome → updated PWM.

## 3. Chronological proof and layered epistemics
Canonical chain:
```text
source artifact and identity
  -> original observation
  -> extracted candidate / measurement (pipeline/version)
  -> interpretation and alternative explanations
  -> scientific hypothesis
  -> reviewed evidence/applicability
  -> options and uncertainties
  -> clinician/patient decision (actual authorization)
  -> real-world task and execution receipt
  -> biological/clinical observation
  -> revised belief state
```
Evidence must distinguish RNA expression from protein accessibility, imaging signal from validated target selectivity, association from causality, multiple concurrent treatments from attributed treatment effects, and a registry match from an actually available trial place. No synthetic numeric confidence without a calibrated task-specific model.

## 4. Specimen optionality and raw-substrate stewardship
Manage the chain from lesion to collection to block/aliquot to assay to derivative result. Show quantity/custody uncertainty as *unknown*. Record potential destructive assay costs, rights to request/release, specimen stability, chain-of-custody, consent and open tasks. Before planned resection or biopsy, enable a clinician-approved **conversation** about whether banked/frozen/viable material would preserve research choices; no automated orders, collection or shipment.

## 5. Adaptive diagnostics and uncertainty
“Test everything” is not a principle. Preserve information when it may become useful, but propose evidence acquisition based on clinical relevance, potential management impact, sample scarcity, time, risk, redundancy, possible future utility, costs, evidence quality and user preferences. Such optimization is a proposal requiring relevant expert review; any “information gain” scoring must be calibrated/validated.

Example unsupported hypothesis: high B7-H3 transcript in a tumor → *does not* imply safe accessible surface protein. Resolve discordance with suitable additional molecular, pathology or localization evidence where a qualified team deems appropriate. Fail-closed on source gaps.

## 6. Therapeutic portfolio (not a treatment ranker)
Scope: standard-of-care, guideline-reviewed alternatives, clinical trials, approved medicines used off-label under clinician care, compassionate/expanded access, investigational programs, radiation/surgery/interventional approaches, modality research (ADC, radiopharmaceutical, vaccine, cell/gene/RNA and other treatments) and **buildable research hypotheses**. Treat combinations and sequences as evidence questions with interaction and toxicity constraints; no system declaration of safety.

Option life cycle separates:
- Scientific: discovered, mechanistic hypothesis, evidence gathering, negative/contradictory, qualified review, retired.
- Clinical: under discussion, clinician-approved for a defined plan, not selected, contraindicated, unknown.
- Operational: prerequisite unmet, potential supplier, access request, site confirmation, feasibility reviewed, reserved (only if actually contracted), delivered, expired.
- Outcomes: administered, measured, mixed/no clear attribution, subsequent options changed.

**Time-to-option:** reason about prerequisite chains (assay → clinician interpretation → site or manufacturer → regulatory review → procurement → logistics → treatment), including lead-time uncertainty and patient safety constraints. Parallel preparation may be useful, but priority is a clinical/ethical decision, not automatic portfolio maximization.

## 7. Continuously operating case board
Physicians, pathologists, radiologists, bioinformaticians, care coordinators, clinical trial specialists, laboratory partners, manufacturers (where authorized) and patient/proxy collaborate on one governed snapshot. A new amendment or research signal triggers an *assigned review task*, not a silent new recommendation. Preserve historical expert dissent and exact version used for each decision.

## 8. Specialized computational capability map
These modules are **future research interfaces**, not 18 required model deployments:
1. Medical record and chronology reconstruction
2. Pathology and IHC/spatial evidence
3. Imaging and lesion dynamics
4. Germline/somatic genomic variation
5. Bulk transcription and functional pathways
6. Single-cell and spatial ecosystem
7. Immunology/TCR/BCR/immune-state inference
8. Clonal disease evolution and resistance hypotheses
9. Target discovery and tumor-vs-normal expression evidence
10. Treatment/trial/program search and evidence appraisal
11. Combination risk and sequencing **research only**
12. Precision modality design (investigational pipeline, not clinical output)
13. Organoid/ex-vivo/functional assay appraisal
14. Longitudinal outcome/trajectory analysis
15. Rights-qualified biomedical publication/knowledge retrieval
16. Trial, expanded access and regulatory *workflow preparation*
17. Manufacturing feasibility/capability coordination, not production
18. Clinical safety, consent, effect class, identity and audit

Every module produces typed claims with source version, method, inputs, calibration/limitations, counterevidence, retrieval/compute version and review status. Provider-neutral interfaces avoid claiming control of every assay or model.

## 9. Authorized real-world orchestration
Potential tasks: retrieving and reconciling records, lab/pathology consultation requests, tissue inventory confirmation, trial-site enquiry, second opinions, scheduling, travel/navigation and insurer document preparation, expanded access evidence packets, and specialist partner feasibility discussions. Each needs a specific actor, legal authority, source scope, action state, audit receipt and clear failure policy. Clinical orders, medication changes, tissue release, investigational access or manufacturing remain in hands of appropriately authorized parties.

## 10. Multiple human experiences, same underlying truth
**Patient:** plain-language changes, options to discuss, missing records, requests, goals, uncertainty and protection from false promises.
**Oncologist:** time-aligned disease state, evidence and contradictions, review board, clinical responsibility, source inspection, action queue.
**Researcher/molecular team:** raw permitted artifact pointers, assay lineage, versioned analysis and reproducible comparison.
**Navigator/operations:** status, readiness/critical-path dependencies, permissions, contact/work receipts, escalation.
Accessible design (WCAG 2.2 AA target) and mobile pathways should be validated, not inferred from a responsive screenshot.

## 11. The three connected future loops
- **Patient loop:** measure → understand → authorize intervention → measure response → update person-specific state.
- **Science loop:** hypothesis → permitted experiment/assay → evaluate negative and positive outcomes → revise biology model.
- **Product loop:** validated finding → clinician/regulatory pathway → execution partner → real-world evidence → next useful capability.

Neither experiments nor therapies are autonomous by default. Safeguards, consent, trial oversight and expert responsibility cannot be compressed into LLM reasoning.

## 12. Commercial, competitive and regulatory caution
Tempus/Caris/Flatiron/xCures already cover substantial longitudinal molecular/evidence territory. Cancer Commons, CureMatch, Massive Bio, myTomorrows and other entrants cover decision preparation, options and access. An EHR can add many user-interface capabilities. Pharma can operate laboratories, drug research and manufacture. Therefore *breadth alone is not a moat*. Patient-side cross-vendor state, biological assets and time-critical preparation may be a differentiated workflow **only if a comparative study shows earlier useful action and an actual payer**.

The hypothetical end-to-end case simulation demonstrated plausible feasibility of partial record aggregation, reviewable chronology, inventory, option dependencies and human-run coordination; it was **not** measured feasibility, clinical evidence, legal advice, validated market size or profitability. Prior illustrative percentages, time-to-source, labor and pricing must be treated as scenario assumptions.

Scope clinical intended use function-by-function; clinician involvement alone does not guarantee non-device status. Rights to records, research datasets, samples, third-party code, model weights, clinical terminologies and external publication content are separately governed.

## 13. Engineering sequence preserving full vision
**Already in the repository:** source-ledger and research-evidence experimental slices on PR branches; check current GitHub main, PRs and CI before asserting implementation.
**Next falsification experiment:** 2 synthetic cases with staged T0/T1/T2 source snapshots, tissue discussions, hypothetical expiring trial dependencies, bad candidates and no-threat controls. Reuse existing case, provenance and investigation machinery.
**Next product proof:** independent reviewers compare option-preservation output with simpler case brief and standard navigation; measure errors, early actionable threats, real total labor and cost.
**Then:** one lawful data-access path and design partner; independent clinical/operational pilot only after all gates.
**Later:** selected BWM adapters, raw biological pointer custody, expert execution network and specialized models, based on demonstrated need.

## Cross-reference
- [Product spec](OPTION_PRESERVATION_PRODUCT_SPEC.md)
- [Falsification protocol](OPTION_PRESERVATION_VALIDATION.md)
- [Adversarial competitor register](COMPETITIVE_THESIS_REGISTER.md)
- [First-principles baseline](FIRST_PRINCIPLES_PLAN.md)
- Notion https://app.notion.com/p/40a3866f77ef81c7a73af37e4ca73654
