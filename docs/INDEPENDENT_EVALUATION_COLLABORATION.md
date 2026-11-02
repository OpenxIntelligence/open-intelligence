# Open Intelligence — Independent Evaluation & Collaboration Playbook

**Status:** Proposed complementary operating protocol · 31 October 2026  
**Scope:** Existing Open Intelligence product and architecture only. This is not a new architecture, software stack decision, clinical validation claim, partnership announcement, or authorization to obtain real patient data.

## Purpose and authority

Open Intelligence should invite outside researchers, clinicians, patient representatives, and experimental scientists to *attempt to falsify specific claims* as features mature. External review occurs alongside engineering, but it does not outrank the existing source/versioned case model, provenance, patient authority, human review, rights registry, or architecture-decision process.

This document adds a reproducible collaboration workflow to the existing [first-principles plan](FIRST_PRINCIPLES_PLAN.md), [execution backlog](EXECUTION_BACKLOG.csv), [Notion validation program](https://app.notion.com/p/40a3866f77ef816f9cd4df7a9efb9b9b), and [Notion identity/precedence rule](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f). Engineering truth is determined by code, versioned fixtures, tests and CI; clinical utility, biological validity and efficacy require distinct forms of evidence.

The historical name CEVax may be referenced for archival source attribution only. **Open Intelligence is the present project.**

## What independent assessment can and cannot establish

| Evaluation lane | Who should challenge it | Question | Evidence produced | Does not establish |
| --- | --- | --- | --- | --- |
| A. Data, chronology and provenance (E0–E1) | Clinical informatics researchers, pathologists, radiologists, biomedical data experts | Are source statements, identity/specimen/time and amendments preserved without unsupported synthesis? | Annotated source-to-assertion matrix; misses, mismatches and correction log | Diagnostic accuracy or clinical readiness |
| B. Evidence and investigation (E2–E3) | Evidence-synthesis researchers, oncologists, molecular tumor boards, trial operations | Are factual claims properly sourced, applicability/negative evidence shown, and unknown eligibility kept unknown? | Blinded claim-level adjudication; unsupported claims and abstention statistics | Treatment benefit or confirmed trial eligibility |
| C. Human workflow and safety (E4–E5) | Physicians, navigators, coordinators, patients/caregivers, accessibility specialists, privacy/security reviewers | Does it improve comprehension or preparation without concealing uncertainty, increasing consequential errors or creating unjustified work? | Baseline-comparison task times, comprehension, correction burden and incident observations | Regulated clinical authorization or proven patient outcome |
| D. Option-preservation falsification (E6, optional) | Independent oncology reviewers and clinical operations experts | Does a prospective dependency view add value beyond the standard case brief, without false urgency? | Pre-registered three-arm historical-cutoff assessment | A replacement initial workflow or clinical benefit |
| E. Biological/experimental hypothesis studies (future optional) | Qualified translational laboratories and relevant specialists | Is an independently specified mechanistic hypothesis reproducible in a justified experimental system? | Protocol, controls, assay provenance, raw data/quality review and reproducible negative and positive results | Human therapeutic efficacy, patient-specific clinical validity or permission to intervene |

Experimental collaborations are *separate research protocols*. A software-generated hypothesis cannot be treated as an assay result, and an in-vitro or animal result cannot be promoted to a clinical conclusion automatically.

## Evidence maturity and activation gates

1. **Gate 0 — Public/synthetic evaluation readiness.** Freeze the capability and exact source revision, prepare independently authored synthetic records, prove no real identifiers or restricted materials are in the package, document source/license/terms for every artifact, publish runnable instructions and a complete limitations statement.
2. **Gate 1 — Independent synthetic challenge.** Recruit evaluators who did not write the fixtures or tune the target feature. Agree on intended use, failure taxonomy, adjudication approach and prospective thresholds. Include contradictory, wrong-person, wrong-specimen, no-evidence and no-action controls. Evaluators can report negatives.
3. **Gate 2 — Governed retrospective investigation, if warranted.** Obtain institutional feasibility review, appropriate research/ethics determination, permitted data basis, DUA/contracts, role-based access and security validation **before** any real data transfer. Define temporal cutoffs so future facts cannot leak into an earlier decision.
4. **Gate 3 — Prospective workflow evaluation, if independently justified.** Agree on accountable clinicians, patient involvement, safety-monitoring and stopping authority; evaluate workflow impact and real operating burden under suitable institutional/regulatory oversight. No clinical deployment follows automatically from Gate 2.
5. **Gate X — Experimental research, independently gated.** Require scientific rationale, named qualified laboratory, assay safety/ethics approvals, sample rights/custody, preregistered controls and independent replication plans. Nothing in a synthetic product demo authorizes wet-lab work.

Fail closed: lack of permission, independent review or an identifiable accountable owner means **hold**. Never imply HIPAA readiness, IRB exemption, clinical performance certification, access authorization or partnership merely because a review request was sent.

## Minimum independent evaluation packet (one packet per claim)

Maintain a versioned directory or immutable archive identified by **evaluation_id** and date. Each packet contains:

- **Claim card:** exact capability, intended setting and intended decision, what is *not* claimed, measurable endpoint and its denominator, version/commit and owning researcher.
- **Frozen input manifest:** source hashes, creation/revision timestamps, cohort/case selection, rights and consent/DUA basis; no live PHI in public repositories.
- **Reference standard:** independent authorship, blinded adjudication method, disagreements/escalation, how "cannot determine" is handled, relevant domain qualifications.
- **Comparison:** manual/current workflow and a simpler non-agent baseline; for E6, the three defined arms. Include total acquisition, preparation, correction, review and coordination time.
- **Protocol:** prespecified primary and secondary metrics, thresholds, safeguards, sampling/exclusions, cutoff-leakage checks, known risks, stopping criteria and protocol version.
- **Execution:** frozen code/model/tool/service versions, prompt/task contracts where lawful, allowed network access, run IDs, operator roles, reproducible setup, and raw per-case outcomes where permitted.
- **Adjudication:** source-linked pass/fail and severity, conflicting expert opinions, negative/null findings, residual unknowns, optional patient comprehension observations.
- **Decision record:** proceed / repair and retest / narrow claim / stop; sign-off owner, date, evidence locations and unresolved work.

Never publish an evaluator's personally identifying information, confidential feedback, private partner negotiations, unpublished data or patient records without appropriate permission.

## Metrics, denominators and stop rules

Use distinct outcome groups and show both a numerator and a denominator:

- **Source fidelity:** claims with resolvable correct source and version / claims assessed; wrong-patient or wrong-specimen attachments / deliberate challenge opportunities.
- **Temporal validity:** correct amended-versus-new findings and correct known-at-cutoff state / staged timeline events; post-cutoff leakage count.
- **Evidence fidelity:** unsupported patient-specific conclusions / adjudicated conclusions; unknown eligibility incorrectly asserted as eligible / unknown-eligibility challenges.
- **Reviewer burden:** elapsed end-to-end acquisition + preparation + correction + review minutes per case (median and range), not just model latency.
- **Patient-centered outcomes:** comprehension/uncertainty calibration for reviewed information and observed confusion or undue alarm; respect participation and accessibility.
- **Safety:** prespecified severe errors, misleading certainty, inappropriate actions, privacy violations, and any clinical escalation observations.

The study lead and independent reviewers must choose numerical success, safety and stop/pivot thresholds **before** viewing test outcomes. A severe wrong-subject disclosure, unauthorized clinical action or actual patient data leakage is an immediate incident requiring cessation and governance escalation; operational response depends on an approved incident plan. Do not invent thresholds retroactively.

## Collaboration governance: actual independence, no ceremonial endorsement

**Separate four roles:** product/engineering owner; evaluation coordinator; domain adjudicator; independent auditor/statistician (as justified). Declare financial and development conflicts. A collaborator who created a feature may contribute to study design but cannot be characterized as independent confirmation of the same feature.

Plan blinded or masked assessment where feasible. Allow reviewers to find failure cases and keep dissenting opinions. Define publication/confidentiality and IP conditions before work begins; do not guarantee publication or force positive conclusions. Independent validation is not established by multiple AI agents agreeing or by several employees reviewing the same fixtures.

**No external contact, pilot enrollment, sample transfer, patient data request, institution-facing commitment or formal scientific experiment is authorized by this planning document alone.** Identify the intended institution/person, proposed disclosure, scope and terms, then obtain appropriate authorization.

## Partner selection and outreach readiness (not a claim of active partners)

Maintain a restricted partner register with: candidate organization and role; scientific/domain fit; intended independent contribution; conflict-of-interest disclosure; evaluation dataset and facilities required; stage/gate; contact owner; lawful disclosure approval; invitation/response status; agreement and protocol status; outcome; next decision. **Keep personal contact details and private correspondence out of public GitHub.** No candidate is labeled "partner" until an actual agreement is established.

Selection preference: reviewers who can challenge one consequential failure mode and return evidence, rather than prestige or general endorsement. Prioritize small bounded synthetic review exercises before broader clinical, wet-lab or institutional work.

### Public, non-confidential invitation template — draft only

> Open Intelligence is developing a source-linked, longitudinal oncology investigation environment for patients and qualified clinical reviewers. We are inviting independent evaluation of a narrowly specified capability on fictional or otherwise lawfully approved data. We will provide the input set, a frozen software/version manifest, a defined comparison, and a method for documenting errors and negative findings. Participation does not imply a clinical partnership, regulatory clearance, patient benefit or endorsement. We would welcome a discussion about whether the evaluation question is meaningful and the appropriate governance for a scoped study.

The invitation is a drafting asset, **not sent**.

## First bounded implementation package

| Work item | Acceptance evidence | Prerequisite |
| --- | --- | --- |
| IV-01: versioned challenge packet | Two or more independent fictional cases; deliberate amendments, mismatched specimen, negative/unknown findings, no-action control; byte hashes; rights manifest | OI-003, OI-004 |
| IV-02: independent review rubric | Source-level scoring definitions, safety severity, missingness, reviewer disagreements, adjudication worksheet, mask/cutoff rules | OI-001, IV-01 |
| IV-03: baseline and reproducibility contract | Manual/simple comparison, executable local setup, frozen revision, measured total effort, failed-run accounting | OI-010, IV-02 |
| IV-04: partner-readiness package | Non-confidential study brief, role/conflict rubric, disclosure checklist, incident and stop-owner mapping | OI-012, IV-02 |
| IV-05: synthetic external dry run | Documented independent reviewers, valid permissions, protocol registered before evaluation, unedited raw outcome summary, decision memo | IV-01–IV-04; authorized outreach |
| IV-06: progression decision | Clear go / repair / stop and, if applicable, institutional review path; E6 remains separate under issue #14 | IV-05 and OI-012 |

A study with no recruited evaluators remains **planned**, not "in progress" or "externally validated." For actual changes to application schemas or workflows, use existing ADR/review procedures rather than treating this playbook as architecture authority.

## Related records

- [Notion: Independent Validation, Clinical Collaboration & Scientific Research](https://app.notion.com/p/40a3866f77ef816f9cd4df7a9efb9b9b)
- [Notion: Identity and architecture precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f)
- [GitHub: supplemental option-preservation falsification #14](https://github.com/OpenxIntelligence/open-intelligence/issues/14)
- [First-principles baseline](FIRST_PRINCIPLES_PLAN.md) and [OI-001–018 backlog](EXECUTION_BACKLOG.csv)
