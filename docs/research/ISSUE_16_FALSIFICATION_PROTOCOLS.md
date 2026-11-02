# Issue #16 — bounded falsification protocols for wedge hypotheses

**Tracker:** [#16](https://github.com/OpenxIntelligence/open-intelligence/issues/16)
**Date:** 2026-11-02
**Status:** Draft validation-governance designs. **Not** authorized outreach,
engineering, procurement, clinical evaluation, or demand evidence.
**Precondition:** run before any wedge engineering or outreach; a protocol that
cannot be executed as written invalidates its hypothesis rather than lowering
its own bar.

## 0. Scope honesty: which hypotheses these protocols cover

Issue #16 wedge definitions A–E are **not readable in-repo** (matrix row F-06,
DEFERRED). These protocols therefore target the only wedge-like hypotheses
readable in-repo — the three entry points of
`docs/FIRST_PRINCIPLES_PLAN.md` §3 plus the first business hypothesis of §13:

| Protocol | In-repo hypothesis (source) | Issue-wedge mapping |
| --- | --- | --- |
| FP-1 | Clinician-supported consultation investigation reduces total preparation + review burden within consequential-error limits (plan §§3, 11; backlog OI-014) | DEFERRED — map to A–E when definitions are readable |
| FP-2 | The organization operating the review workflow values a reliably prepared, updated case enough to change workflow and pay (plan §13; backlog OI-015) | DEFERRED — map to A–E when definitions are readable |
| FP-3 | Patient-owned record coordination: patients can gather records, see gaps, and prepare questions at acceptable acquisition burden (plan §3 row 1) | DEFERRED — map to A–E when definitions are readable |
| FP-4 | Specialist molecular / tumor-board research as early design-partner path (plan §3 row 3) | DEFERRED — map to A–E when definitions are readable |

No protocol below treats synthetic capability tests (`docs/IMPLEMENTATION_STATUS.md`)
as demand, burden, or willingness-to-pay evidence.

**Shared conventions.** Each protocol states: hypothesis, population /
denominator, baselines, measurements, failure outcomes (hypothesis falsified),
invalid outcomes (test discarded, hypothesis stays UNKNOWN), reviewer
authority, bounded costs, and stop criteria. Thresholds are set with reviewers
*before* results are examined (plan §11). Missing proof keeps the hypothesis
UNKNOWN; it never upgrades it.

---

## FP-1 — Consultation-investigation burden reduction (workflow wedge)

**Hypothesis.** For a defined adult oncology review setting, a shared
case-investigation workspace (reviewable brief + one evidence-linked question +
amendment-driven re-review) reduces *total* human burden per reviewed case and
per update versus current practice, within prespecified consequential-error
limits.

**Population / denominator.** Consecutive referred cases in one accountable
review service over a fixed window (denominator = all cases entering the
service in-window, including ones with incomplete records). Matched /
counterbalanced assignment across arms; hold out cases by patient; respect the
evidence available at the historical cutoff (plan §11).

**Baselines (all measured, none assumed).**

1. The partner's current manual workflow (observed, not described).
2. A simple source-search / structured-timeline workflow without AI assistance.
3. The proposed AI-assisted investigation (only after OI-006–OI-009 behavior exists).

**Measurements.** End-to-end preparation time, correction time, reviewer
burden, marginal cost of updates; source fidelity, traceability, longitudinal
behavior, evidence quality per plan §11 dimensions. Acquisition, organization,
review, correction, documentation, and follow-through all counted; effort moved
between roles is not counted as saved.

**Failure outcomes (hypothesis FALSIFIED).** Records cannot practically be
acquired; important unsupported claims persist; review eliminates the time
saved; users cannot inspect corrections; the brief is not useful even when
manually prepared; or no one owns follow-up (plan §11 stop list). Any one
falsifies this wedge in this setting.

**Invalid outcomes (test DISCARDED, hypothesis stays UNKNOWN).** Reviewer
unblinded to arm before scoring; cutoff leakage (evidence dated after the
case cutoff used); denominator tampering (selective case exclusion); loss of
source-version recovery during the test window.

**Reviewer authority.** Independent oncology adjudicators plus the evaluation
lead (backlog OI-014) set critical-error definitions and acceptance thresholds
before results; the accountable treating/reviewing clinician owns follow-up.
Model-generated self-review cannot substitute.

**Bounded costs.** Reviewer/adjudicator hours, coordinator hours, case-brief
preparation labor, compute/licensed-content spend, incident-handling overhead —
tracked per reviewed initial case and per update. Token price alone is not the
unit economics (plan §13).

**Stop criteria.** Stop the wedge if any failure outcome triggers, or if two
consecutive invalidation-free runs show no burden reduction within error
limits. Changing the workflow in response is progress; adding agents is not a
substitute.

---

## FP-2 — Organizational buyer and paid workflow change (business wedge)

**Hypothesis.** A clinical organization operating the review workflow will
change that workflow and pay for reliably prepared, updated case briefs on a
repeat basis (plan §13 first business hypothesis). Patient subscription is a
*different* hypothesis and is not tested by this protocol.

**Population / denominator.** Denominator = every organization approached that
operates a qualifying review workflow in the defined setting, tracked from
first contact through decision (adopt / decline / no-decision with reason).
Numerator events: signed paid pilot with named budget owner, repeat usage in
the intended workflow with an accountable owner, identified budget/approval
path (plan §11 adoption row).

**Baselines (best existing/manual alternatives at equal depth).**

1. Status quo: current manual preparation inside the organization's staffing.
2. Cheapest adequate substitute the buyer names (e.g., template + coordinator
   hours, existing EHR/portal workflow) costed honestly.
3. The proposed service at full cost per reviewed case/update (§13 cost list).

**Measurements.** Observed preparation work actually performed for the buyer;
procurement conversations with recorded objections and decision authority;
repeat-use counts; cost per reviewed initial case and per update including
acquisition, review minutes, licensed content, storage/egress, compute,
support, and failed jobs.

**Failure outcomes (hypothesis FALSIFIED).** No budget owner identified after
the bounded outreach list is exhausted; repeat usage does not occur absent
free labor; full-cost brief exceeds the buyer's named adequate substitute with
no valued differentiator the buyer will pay for; procurement requires
deployments the project cannot lawfully operate.

**Invalid outcomes (test DISCARDED, hypothesis stays UNKNOWN).** Contacts lack
decision authority and none is reached; pilot scope changes mid-test so cost
comparisons break; buyer receives undisclosed subsidy (free labor, waived
costs) that is not recorded and re-costed.

**Reviewer authority.** Product/evaluation leads record every contact outcome;
the buyer's own budget owner confirms authority and price sensitivity. No
internal vote substitutes for a signed paid commitment.

**Bounded costs.** Bounded outreach list size, staff hours for preparation
work and procurement conversations, pilot delivery cost — all pre-registered
with a cap. Outreach itself needs separate authorization (backlog OI-002
boundary); this protocol does not authorize it.

**Stop criteria.** Stop this wedge if the bounded list is exhausted with zero
paid pilots, or if the only conversions require economics the cost model
cannot sustain. Do not re-score failures as partial wins.

---

## FP-3 — Patient-owned record coordination (patient wedge)

**Hypothesis.** Patients/caregivers can gather their records, see gaps, and
prepare reviewable questions through the workspace at an acquisition burden
ordinary patients can sustain — making this a possible earlier market (plan §3
row 1) — without implying the research promise is delivered.

**Population / denominator.** Denominator = all consenting patients/caregivers
enrolled in the bounded cohort attempt, including dropouts (dropout reasons
recorded as primary data). Stratify by records-access situation (portal access,
multi-institution, paper-only) and support needs (language, accessibility,
connectivity).

**Baselines.**

1. Current patient experience: unaided record gathering for the same referral.
2. Navigator/coordinator-assisted gathering without the workspace.
3. Workspace-assisted gathering with defined helper roles.

**Measurements.** Records requested vs. received vs. usable; patient/helper
minutes; gap-closure rate; questions prepared that the reviewer rates usable;
comprehension checks (uncertainty interpretation, research-vs-care
distinction); support minutes per patient.

**Failure outcomes (hypothesis FALSIFIED).** Acquisition burden dominates
(plan §3 named difficulty) — most enrolled patients cannot complete gathering
with available help; prepared questions are unusable for review; comprehension
checks fail (patients over-read certainty or confuse research with established
care); or the cohort that succeeds requires per-patient helper time the
operating model cannot fund.

**Invalid outcomes (test DISCARDED, hypothesis stays UNKNOWN).** Cohort
skewed to unusually resourced patients without recording the skew; helper
does the patient's work off-protocol and minutes go unrecorded;
records-access pathway changes mid-test for reasons unrelated to the wedge.

**Reviewer authority.** Clinical reviewer rates question usability and brief
readiness; patient/caregiver participants co-assess burden and comprehension;
evaluation lead owns the protocol. Builder-team optimism about "simple UI"
carries no weight against measured minutes.

**Bounded costs.** Helper/support minutes, accessibility provision, record
retrieval fees if any, participant compensation if any — per enrolled patient
and per completed case. Records alone do not deliver the research promise, so
no research-outcome value may be booked against these costs.

**Stop criteria.** Stop this wedge if completion rate below the prespecified
floor, or if required helper time per completed case exceeds the funded
operating model. A simpler interface is not evidence until the minutes say so.

---

## FP-4 — Specialist molecular / tumor-board design partnership (specialist wedge)

**Hypothesis.** Deep biological context and evidence appraisal create enough
value for complex cases that a specialist setting (molecular program /
tumor board) will sustain design partnership: supply reviewer time, required
data access, and assay context for bounded evaluations (plan §3 row 3; backlog
OI-016/OI-017 territory, but this protocol tests partnership viability, not
modality science).

**Population / denominator.** Denominator = all specialist reviewers/programs
approached in the bounded list. Numerator events: delivered reviewer hours,
delivered assay-context/data access under lawful terms, completed bounded
evaluation with independent review.

**Baselines.**

1. Current specialist preparation (manual literature/context review per case).
2. Existing institutional resources the specialists already use (named).
3. Workspace-assisted preparation for the same case complexity.

**Measurements.** Reviewer hours delivered vs. promised; data/assay-context
completeness; QC rejection rates; per-case preparation burden at matched
complexity; specialist-rated usefulness of the reviewable output; rights
clearance status per input.

**Failure outcomes (hypothesis FALSIFIED).** Specialist time unavailable at
the required cadence; assay context or data access unobtainable under lawful
terms; interpretation-validation bar exceeds what bounded evaluations can meet
(plan §3 named difficulties); or specialists will not route real questions
through the workflow after seeing reviewable output.

**Invalid outcomes (test DISCARDED, hypothesis stays UNKNOWN).** Single
enthusiast substituted for program commitment without recording it;
evaluation cases cherry-picked below the complexity the wedge claims;
rights/permission status of inputs left unassessed.

**Reviewer authority.** Modality experts plus the evaluation lead; rights
reviewer gates every input (backlog OI-004/OI-012). No research output
becomes a clinical fact through this protocol.

**Bounded costs.** Specialist reviewer hours (scarce — capped explicitly),
data-access and compute costs, rights-review effort, per-case evaluation
labor. Raw research outputs carry no clinical value in the costing.

**Stop criteria.** Stop this wedge if reviewer delivery or data access fails
twice consecutively for structural (not scheduling) reasons, or if the
interpretation-validation bar requires evidence the project cannot produce in
this setting. Enablement waits on the foundation proving itself (plan §3).

---

## Execution gate

None of FP-1–FP-4 is authorized to start by this document. Each requires its
own scoped approval covering: setting/partner, reviewer authority, real-data
governance (OI-012/OI-013 where applicable), outreach authorization (OI-002
boundary), budget cap, and preregistered thresholds. Until then, every wedge
hypothesis remains UNKNOWN with K = NONE.
