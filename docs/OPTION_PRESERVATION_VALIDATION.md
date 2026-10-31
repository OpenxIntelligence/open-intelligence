# Open Intelligence — Option Preservation Falsification Protocol
**31 October 2026 · Proposed protocol, not completed validation**

## Objective
Determine whether source-linked, forward-looking **option-preservation threats** can be identified reliably *earlier* than a comparator workflow, without unacceptable false clinical implications, excessive human effort or costs.

## Hypotheses (to be falsified)
H1: At least some complex oncology cases contain verifiable, time-sensitive preparation decisions whose delay could remove a plausible future option.
H2: An evidence-backed portfolio plus dependency tracking can surface such events *before* deadline using only information available at the historical cutoff.
H3: Qualified reviewers find the output useful enough to act on, without taking unsupported clinical recommendations as facts.
H4: Acquisition, review, corrections and coordination have plausible sustainable unit economics.
H5: This produces value beyond a high-quality case brief, a conventional navigation service, and a simple rule-based task tracker.

## Simulation already discussed: interpretation only
Illustrative fictional P-001: adult with advanced rare/metastatic solid tumor, multiple institutions, pathology/sequencing/ctDNA, prior treatments and an upcoming biopsy or surgery. Walked through acquisition, case reconstruction, asset registry, uncertainty, options, dependencies, authorized coordination, subsequent outcome and economics. This was a **thought experiment**; it did not measure actual source coverage, accuracy, costs, medical benefit, legal classification or buyer demand. Figures previously used (e.g. 85% record coverage after 72 hours, 15–30 initial labor hours, 5–10 optimized hours, $5,000 onboarding + $500 monthly) were **illustrative assumptions**, not observed operating results. They must not be reused as forecast evidence.

## Study design
Phase A — 10–20 independently authored synthetic or lawfully de-identified historical cases with staged release of documents. Clinical experts construct an adjudicated reference set; no prior-case future knowledge may leak into earlier cutoffs. Cases should include *negative* cases with **no justified threat**. Exclude proprietary/restricted clinical materials without rights.

Phase B — comparative review by independent oncology reviewers and navigators using (i) current workflow, (ii) source-linked case brief, (iii) source-linked option/dependency/threat view. Order randomization where feasible. Reviewers blinded to “future” outcome when judging a past snapshot.

Phase C — permitted operational pilot only after identity/consent, rights, clinical authority, privacy/security, regulatory intended-use, and clinician responsibility review. Real-patient materials remain out of public GitHub.

## Gold-standard candidate event fields
case_id, cancer episode, decision_time, exact patient sources available before cutoff, candidate option, dependency, reversible/irreversible status, deadline provenance, evidence level, whether clinical team already considered it, possible downside, availability/eligibility caveats, required reviewer, outcome observed after cutoff (for evaluation only), adjudication confidence.

## Error taxonomy and metrics
- **Safety-critical**: wrong patient; fabricated source/citation; fabricated treatment availability; false claim of trial eligibility; unsafe clinical instruction; wrong/expired authority; unlicensed content exposure; history overwritten; future-information leakage.
- **Consequence-bearing**: missed source-supported option-preservation threat; unjustified urgent threat; unacknowledged contradictory evidence; conflated tumor/sample/time; unreviewed action presented as approved.
- **Utility**: time to reviewable case, reviewer correction minutes, completeness by source type, verified early threats per case, false-alert rate, reviewer usefulness, time to resolution, preserved tissue / eligibility discussion when documented.
- **Economics**: acquisition and processing labor, specialist review minutes, model/tool costs, external fees, month-over-month maintenance, price sensitivity, buyer budget owner, engagement, user burden.

Measure at cutoff, by patient and by action type. Use confidence intervals and actual denominators; do not optimize a synthetic score at expense of clinical safety.

## Fail-closed acceptance gates
1. No wrong-case linkage or unsupported “approved/eligible/available” assertion in the evaluation artifacts.
2. Human can reconstruct every claimed threat using accessible, rights-qualified source references.
3. A corrected/retracted source or changed protocol invalidates dependent outputs without destroying historical snapshots.
4. Flagging never executes an order, tissue release, medication change, trial enrollment or patient contact automatically.
5. Clinicians can abstain, reject and explain tradeoffs; patient wording never implies more certainty than clinician wording.
6. No production or clinical claim from a synthetic benchmark alone.

## Precommitted stop/pivot decisions (thresholds to be set *before* expert cases)
- Stop clinical deployment if source/identity/provenance integrity cannot be shown or governing authority is unclear.
- Pivot away from option preservation if reviewers find few actionable threats or current manual/navigation workflows catch nearly all of them at lower total cost.
- Narrow scope to specimen logistics, eligibility readiness or longitudinal investigation if one subworkflow demonstrates better incremental value.
- Delay commercial expansion if a realistic cohort cannot be acquired with consent and repeatably reviewed within viable margins.

## First engineering test matrix
- T0/T1/T2 replay with no look-ahead
- surgery tomorrow; specimen “possible” not confirmed; ask for discussion, not automatic banking
- treatment planned; trial criterion uncertain; site confirmation required
- conflicting specimen availability; no double-count
- external source corrected/retracted; staleness and review queue
- wrong-case and duplicate ingestion; isolation and idempotence
- option withdrawn/expired; historical availability preserved
- no-option case; system abstains
- cost and lead-time unknown; no fabricated deadlines
- cross-user role and revoked authority; action denied
- expired rights to a literature source; retain metadata and disable unauthorized full text

## Commercial falsification
No evidence of pricing or demand yet. Interview accountable oncologists, navigators, advanced-cancer patients, health-system leaders, payers and specialty centers. Obtain confirmed *workflow owner*, *budget owner*, *decision-to-pay* and *responsibility/liability allocation*. Do not confuse enthusiasm with a contract. Track true cost from raw record access through correction and follow-up.

## Relationship to existing repo
Extends OI-001/002 (job and comparator), OI-003 (challenge set), OI-006/007/009 (source/question/amendment), OI-008 (evidence) and OI-014/015 (controlled evaluation/economics). Introduce OI-019+ only after reviewing integration conflicts and agreeing the case-object contract. No stack migration is implied.
