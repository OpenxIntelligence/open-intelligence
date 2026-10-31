# Open Intelligence — additive HL7 / Nano / specialist-model evaluation

**Status:** RESEARCH / EVALUATE; not an adopted architecture decision, implementation, clinical validation, or vendor approval.  
**Date:** 2026-10-31  
**Tracker:** [#15](https://github.com/OpenxIntelligence/open-intelligence/issues/15)  
**Boundary:** supplements, does not supersede, [the first-principles plan](../FIRST_PRINCIPLES_PLAN.md), existing Notion decisions (including OI-ADR-002, -007, -008, -010, -011 and -012), the current synthetic-only implementation, or any in-flight PR.

## 1. Decision framing

Open Intelligence owns the consent-scoped clinical and biological case, immutable/versioned source material, reviewable assertions, longitudinal timeline, evidence, investigations, human decisions, and governance. It is model-neutral. **Nano is one optional, independently evaluated model** for chronology extraction, timeline reconciliation, contradiction/missingness detection, and context preparation. Other scientific models can be optional specialists (e.g., regulatory genomics, protein, pathology, imaging, pharmacology) selected per task, permissions, modalities, fitness, rights, and evidence. Neither Nano nor any provider owns clinical truth or is a platform dependency.

The proposed addition is an **integration and validation slice** in the existing workflow: authorized source -> existing versioned case and question -> authorized model/tool run -> source-linked candidate -> scoped human review -> existing dated brief. An amended source selectively marks dependent outputs stale while history remains inspectable. Avoid parallel ledgers, a new patient-world-model authority, a separate orchestration core, or a new mandatory FHIR store.

## 2. Verified scope of the HL7 reference

[HL7 Informative Document: AI/ML Data Lifecycle, Edition 1 — US Realm](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=658) (status date **2024-08-27**) is *informative guidance*, not a mandatory normative implementation specification for Nano or Open Intelligence. Its Phase I focus is **data used for predictive ML models**. The official product brief emphasizes consistent annotation and processing, interoperability, data quality, provenance, accountability/audit, transparency and appropriate use. It mentions 12 supplementary case studies. The product brief alone does **not** supply the full mapping, license grant, downloadable document contents, or an AI inference/run API. Confirm licensing and inspect the full specification and case studies under permitted access before claiming a clause-by-clause compliance crosswalk or copying text.

**Implication:** use the published principles as a checklist for existing data lifecycles and future dataset/model evaluation. Do not introduce another schema, claim HL7 compliance, or describe it as guidance for all generative AI output workflows.

## 3. Existing-object crosswalk (do not duplicate authority)

| HL7-relevant concern | Existing Open Intelligence owner | Candidate *addition only if needed* | Evidence/gate |
| --- | --- | --- | --- |
| Acquisition, permitted purpose, source origin | Identity/consent + SourceArtifact/version + import receipt | Record usage purpose, privacy class, rights status per input; do not store another original | Revocation and wrong-patient quarantine tests |
| Annotation/normalization and data quality | Original report bytes + ClinicalAssertion/Observation + source anchor | Record transformation/tool version, normalization map, field-level QC failure and abstention | Exact spans; units, polarity, absent/negative/pending tests |
| Temporal integrity | Clinical event/disease state + versioned timeline | Keep clinical effective, issued/report, ingestion and amendment times independently, with partial/uncertain dates | Out-of-order reports and multiple-specimen cases |
| Provenance/audit and AI involvement | Existing task/investigation/run receipt + assertion provenance | Extend run receipt with provider/model/version, input artifact versions, output hashes, rights/egress policy decision, reviewer state | Replay against frozen inputs; reject stale output |
| Lifecycle transparency | Existing evidence, review and dependency links | Derive display-ready timeline candidates; never grant independent clinical-decision authority | Amendment -> targeted invalidation -> re-review |
| Model quality and fitness | Existing evaluation and legal gate | Versioned benchmark, capability metadata and failure thresholds; avoid an unqualified global model score | Deterministic vs generic vs Nano (if actually available) |

**Important distinction:** source authenticity, source-byte integrity, clinical accuracy, extraction fidelity, scientific support, and clinician approval are separate properties. A cryptographic hash only proves byte equality; model agreement is not independent clinical corroboration.

## 4. Minimal interface proposals, not required new tables

Use existing schemas if they can express these contracts. Introduce new persistence only after a concrete missing capability is demonstrated.

### 4.1 Model execution receipt (extension of existing Run/Investigation)

- `run_id`, `case_scope`, `investigation_id`, task type and purpose; actor/authority and reviewed policy decision.
- `model_provider`, immutable model/version/build reference, task interface version, runtime location, model capability reference and deterministic configuration when possible.
- Authorized `input_artifact_id@version` references and field-level scope; exact preprocessing/normalization version and input fingerprint; never log PHI payloads by default.
- Egress mode (`local_only`, `authorized_remote`, `blocked`) and explicit privacy/contract/license decision; token/compute/latency/cost when measurable.
- Output artifact content hash, structured parsing result, errors/abstentions, validity/staleness, downstream dependencies and review status.

### 4.2 Timeline candidate (projection over existing assertion/event entities)

- Distinguish `reported_text`, `extracted_candidate`, `derived_interpretation`, `hypothesis` and `clinician_reviewed` rather than collapsing them into an event.
- Include exact source version + anchor, patient/cancer episode, lesion/specimen/assay identifiers, polarity, certainty, units/reference, and effective/report/ingestion/amendment timestamps.
- Carry competing interpretations and source conflicts. No silent promotion to `clinician_reviewed` from model output, confidence score or successful validation of JSON syntax.

### 4.3 Capability registry (configuration for the existing tool/agent boundary)

- Declare task + modality, allowed input/output schema, required specimen/assay metadata, QC/rejection conditions, local/remote execution and data classes.
- Declare deployment + data-use terms, retention/training restrictions, dependencies/model-weight/data license status, per-use rights provenance, cost/latency and evaluation date.
- Unknown permissions => `BLOCKED`; capability is optional, replaceable and may be disabled without losing the case.

## 5. Training and Nano-specific boundary

Nano is **not** the system of record and should not be trained on patient data by default. A future Nano training or fine-tuning program is a separate, reviewable decision requiring: lawful provenance and scope-specific data-use rights, governance approval, representative cohort and labeling policy, train/eval segregation by patient and time, leakage audits, privacy protection, baseline comparison, subgroup/error analysis, reproducibility, deployment approval and monitoring. Benchmarking Nano on synthetic cases does not imply clinical fitness, privacy clearance or any right to train on uploaded records.

The platform must retain the ability to use deterministic workflows and other approved models when Nano is unavailable or performs worse. Third-party models are not assumed callable merely because a publication, web demo or repository exists (including AlphaGenome). Provider availability, hosted API terms, model weights, training rights, personal-data policy and clinical-use restrictions require independent verification.

## 6. Test-first experiment for issue #15

**Independent synthetic fixture set:** cases covering multiple institutions, two primaries, distinct specimens, negative vs untested variant, uncertain/partial dates, reissued pathology finding, duplicated import, conflicting staging, withdrawn evidence, cross-case isolation and revocation.

**Candidates:** (A) deterministic parsing/rules already supported; (B) one permissible general model, if available; (C) Nano only when a runnable version and documented license exist. Use the same frozen source inputs and a blinded, independently authored adjudication set. Model runs must never have tool permission to approve their own results.

**Measurements:** exact source-anchor precision/recall; event extraction and pairwise chronological ordering; polarity and uncertainty preservation; specimen/episode attribution; contradictions retained; valid abstention rate; cross-tenant isolation; selective invalidation precision/recall; human correction time; latency and full cost, including setup and verification. Report raw counts and confidence intervals where sample size permits; no invented performance claims.

**Pass/fail scenarios:**

1. No output lacking a valid authorized source/version/anchor can enter the reviewed projection.
2. Negative, absent, untested and indeterminate remain distinct; wrong-specimen linkage is a hard failure.
3. T0 snapshot remains replayable after T1 report amendment; only dependent derived objects become stale.
4. Unrelated case and unaffected evidence remain unchanged; retries and duplicate imports are idempotent.
5. Egress without explicit authorization/terms fails closed and leaves an inspectable denial receipt.
6. A specialist-model JSON result is registered only as a derived candidate until a properly scoped human decision.
7. A generic model or Nano must outperform the deterministic baseline on predefined *total review burden or quality* to justify its added complexity.

**Sequence:** schema inventory -> fixture + gold labels -> deterministic baseline -> local mock specialist adapter -> amendment/invalidation test -> general/Nano comparative evaluation (only if available and cleared) -> rights and clinical validation decision. Do not reprioritize the existing first implementation milestone.

## 7. Open checks and decision state

- [ ] Inspect full HL7 document/case studies and any applicable terms; resolve whether a more detailed lifecycle-stage crosswalk is warranted.
- [ ] Map existing code/database fields and active PR implementations to the interfaces above; label each as implemented, partial, proposed or absent (this document is **not** a code audit).
- [ ] Complete purpose-limited per-provider rights/privacy/security clearance before real-data access, production model calls or training.
- [ ] Obtain independent clinician review for intended clinical-use questions; do not infer treatment actionability from mechanistic model outputs.
- [ ] File a separate adopt/hold/reject decision with evidence, author, date and reversibility; **current decision remains EVALUATE**.

## References

- [Open Intelligence implementation plan](../FIRST_PRINCIPLES_PLAN.md) and [contributor instructions](../../AGENTS.md)
- [Existing canonical timeline and provenance](https://app.notion.com/p/40a3866f77ef81d9a5adca4ee9adb2e0)
- [Existing integration decisions](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876) (particularly OI-ADR-011 model providers)
- [HL7 AI/ML Data Lifecycle official product brief](https://www.hl7.org/implement/standards/product_brief.cfm?product_id=658) and [HL7 publication record](https://hl7news.hl7.org/2025/01/13/hl7-standards-published-since-august-2024/)
- [Issue #15 tracking bounded evaluation](https://github.com/OpenxIntelligence/open-intelligence/issues/15)

**Verification note:** research/source reading and documentation only. No repository code changed, no tests or model benchmarks run, no PHI processed, and no clinical or vendor approval claimed.
