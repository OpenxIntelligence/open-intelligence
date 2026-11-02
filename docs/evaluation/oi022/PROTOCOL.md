# OI-022 preregistered protocol — option-preservation falsification (issue #14)

**FICTIONAL — SYNTHETIC ONLY. Protocol draft `OI022-DRAFT`. NOT ACTIVATED.
No reviewers recruited, no thresholds set, no runs executed, no results.**

## 1. Evaluation identity

| Field | Entry |
| --- | --- |
| Evaluation ID | `OI022` (TO CONFIRM at freeze) |
| E-track | E6 (optional option-preservation falsification), lane D of the [playbook](../../INDEPENDENT_EVALUATION_COLLABORATION.md) |
| Claim under test | That an option-preservation graph (options, dependencies, optionality threats, preparation tasks) adds clinically and economically meaningful value beyond an evidence-linked brief and beyond ordinary navigation/case preparation |
| Study posture | **Falsification**: the study is designed to give the claim every fair chance to fail. Null and negative findings are first-class outcomes. |
| Intended audience, decision and setting | Open Intelligence product/engineering owner deciding go / pivot / stop on the OI-021 option view; independent oncology reviewers adjudicating fictional staged journeys offline. No care setting, no live workflow. |
| Explicit non-claims | No clinical benefit, no treatment efficacy, no eligibility determination, no diagnostic accuracy, no regulatory clearance, no willingness-to-pay finding, no real-world error rate. A synthetic result is engineering feedback only. |
| Study stage / permitted data | Synthetic-only (Gate 0/1). No real patient data, no retrospective records, no clinical pilot. |
| Preregistration date and immutable location | **TO COMPLETE BEFORE RESULTS** |
| Study lead / accountable stop owner | **TO ASSIGN** |
| Review independence and declared conflicts | **TO DOCUMENT** per §3; none recruited |
| Approved sharing scope | **TO DOCUMENT**; default is public synthetic material only, no reviewer identities |

## 2. Scope and hard boundaries

1. **Synthetic-only.** All inputs are the fictional journeys in
   [JOURNEYS.md](JOURNEYS.md). If any element resembles a real identifier, a
   real record, or restricted text, stop scoring that element, log it as a
   packet defect, and escalate to the coordinator. Resemblance confers no
   meaning.
2. **No clinical inference by the packet.** Journeys use abstract fictional
   findings (e.g. `marker-q`, fictional lesion descriptions, fictional
   procedures). Reviewers score **traceability to packet sources at a declared
   cutoff** — never clinical truth, and never what a real patient or clinician
   should do.
3. **No recommendation or order language.** Any arm output containing
   directive clinical language (recommendation, eligibility assertion,
   prescription, order, instruction to act) is a severity S3 finding per
   [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md), even if its sources
   trace correctly.
4. **Potential discussion deadlines are not clinical deadlines.** The OI-021
   deterministic potential discussion deadline is scored only as an
   arithmetic projection over stated lead times and sourced anchors,
   labelled as discussion scheduling.
5. **No retrospective synthetic score masquerades as clinical validation.**
   Every report, memo, and summary produced under this protocol carries the
   header: *"Synthetic staged-journey result; not clinical validation."*
6. **No real patient acquisition or clinical pilot** is authorized, planned,
   or implied by this protocol.
7. **Thresholds are reviewer-set, prospective, and frozen.** §8 gives the
   procedure and a blank table. There are no default, suggested, or example
   numeric values anywhere in this packet — an example value would anchor the
   reviewers and is therefore forbidden.

## 3. Roles, independence, and conflict declarations

Four roles are kept separate. One person must not hold two of them for the
same evaluation:

| Role | Responsibility | Must not also be |
| --- | --- | --- |
| Product/engineering owner | Freezes the evaluated software revision; receives the decision memo | Coordinator, assessor, adjudicator |
| Evaluation coordinator | Owns journeys, cutoff inputs, arm allocation, masking, burden/cost ledgers; holds the coordinator checkpoint key | Assessor, adjudicator |
| Independent assessor (≥2) | Scores arm outputs against the worksheet; at least one assessor per journey must hold independent oncology review qualification for any applicability judgment | Feature builder, coordinator |
| Dispute adjudicator | Resolves disagreements or marks rows explicitly unresolved; signs the adjudication record | Assessor of the same rows |

Before any scored output is opened, each assessor and adjudicator files a
declaration recording:

- involvement in feature construction, journey authorship, or prompt/model
  tuning for any evaluated system (including any vendor system);
- financial or institutional conflicts in the outcome;
- relevant qualification (oncology review qualification is required to judge
  whether an applicability inference is withheld correctly; methodological
  qualification suffices for pure traceability rows — record which applies).
  The dispute adjudicator must hold oncology review qualification for any
  row where an applicability judgment is in dispute; otherwise the row is
  resolved only on traceability grounds or marked explicitly unresolved;
- **prior exposure**: whether they have seen any checkpoint key, pilot score,
  full-journey material beyond their assigned cutoff, or vendor output, and
  when.

A reviewer with prior key/cutoff exposure is recused from primary scoring of
the affected journeys; they may serve only as a logged, non-voting observer.
Personal identities live in an authorized private register; public outputs
use anonymous reviewer IDs. An independence breach voids the affected scores
and triggers re-adjudication. **No reviewer or partner institution is implied
by this draft — names are filled in only when real people are recruited under
appropriate authorization.**

## 4. Study question and comparison

**Question:** does the option-preservation graph surface genuinely
time-sensitive discussion items earlier, with fewer consequential errors and
lower total human burden and operating cost, than (a) ordinary
navigation/case preparation and (b) an evidence-linked brief — when all three
work from identical fictional sources under identical cutoffs, and when
reviewers actively probe for false urgency, missed threats, source errors,
leakage, and hidden burden?

### Arm A — Ordinary navigation / case preparation

Manual reading of the cutoff sources plus the coordinator-documented
"current-workflow" preparation steps (see §4.4): source gathering, manual
notes, a manually written case brief in the fixed five-section structure of
[`validation/iv01/BASELINE.md`](../../../validation/iv01/BASELINE.md) §2. No
evidence-linked brief tooling, no option graph. This arm produces the frozen
baseline brief per journey-cutoff, prepared by a coordinator-designated
preparer who is **not** an assessor of that journey-cutoff (see §12).

### Arm B — Evidence-linked brief

The source-investigation workspace: source-linked assertions, one focused
question linked to permitted (here: fictional) evidence with applicability
limits, and a dated brief — **without** the OI-021 option/dependency/threat
projection. If the workspace under test cannot disable the option view, the
coordinator re-renders arm outputs with all option-view surfaces removed and
logs the re-render. The removal must leave **no marker** (no redaction label,
placeholder, or gap an assessor could use to identify the arm); if clean
removal is impossible, the coordinator logs a masking limitation and the
reviewers decide, before scoring, whether that journey-cutoff can proceed.
Any option-view content leaking into Arm B is a protocol deviation.

### Arm C — Option-preservation graph

Arm B's workspace **plus** the reviewed OI-021 option/dependency view:
Options, OptionDependencies, OptionalityThreats, and human-owned
PreparationTasks as a derived projection over snapshots/investigations, with
the deterministic potential discussion deadline and reviewer action audit.
Contradicted options must appear visibly held; no recommendation/order
language may appear.

### Equal information, equal task burden

- All arms receive identical cutoff sources, identical journey questions, and
  identical cutoff datetimes. The journey question set is fixed in
  [JOURNEYS.md](JOURNEYS.md) before the run; no arm gets extra hints, extra
  sources, or reworded questions.
- Burden and cost recording is identical across arms (see §7 and
  [METRICS_SPEC.md](METRICS_SPEC.md)). Learning control: counterbalance arm
  order across reviewers and journeys, or assign previously unseen journeys
  across arms so no reviewer sees the same journey in two arms. Record arm
  order and journey assignment in every run record.
- A reviewer who has seen a later cutoff early, or who reuses knowledge from
  prior full-journey exposure, is prior-exposed for that journey (see §3) and
  is recused from primary scoring of it.

### 4.4 Documenting the "ordinary" comparator (reviewer-dependent)

The coordinator must write down, **before freezing**, what "ordinary
navigation/case preparation" concretely consists of for this study (steps,
roles, tools allowed, e.g. plain file listing vs script-assisted sorting),
and the independent reviewers must confirm it is a fair representative of a
manual baseline rather than a straw man. If reviewers judge the Arm A
definition unfair, the protocol is repaired and re-frozen; it is not scored
as-is. Record the agreed Arm A definition in the freeze record.

### 4.5 E6 divergences from the IV-02/IV-03 contracts (explicit; amends nothing)

This packet follows the IV-02 adjudication contract
([`ADJUDICATION.md`](../../../validation/iv01/ADJUDICATION.md)), the IV-03
reproducibility procedure
([`BASELINE.md`](../../../validation/iv01/BASELINE.md)), and the supporting
rubric ([`SCORING.md`](../../../validation/iv01/SCORING.md)) except for the
following stated E6 divergences, which apply to OI-022 only:

1. **Arms.** OI-022 Arm B is the evidence-linked brief without the option
   view — not the IV-03 simple manifest/time-sort arm. OI-022 Arm C is Arm B
   plus the OI-021 option/dependency/threat projection — not the IV-03
   general application arm. Arm A keeps the IV-03 role (manual preparation
   producing the frozen baseline brief).
2. **Journeys replace cases.** Staged fictional journeys with three receipt
   cutoffs (T0/T1/T2) replace IV practice cases; run records and worksheets
   use `journey_id` / `cutoff` / `arm_blind_code` where IV-02/IV-03 use
   `case_id` / `cutoff` / `arm`.
3. **Worksheet columns.** Relative to IV-02 §7: `protocol_version` and
   `reviewer_qualification` are added; `source_anchors` replaces
   `source_lines`; `software_revision` replaces `application_commit`;
   `journey_id` replaces `case_id`; `arm_blind_code` replaces `arm`; three
   flags are added (`missed_threat`, `directive_language`,
   `deadline_labelling_error`); `prior_exposure` replaces
   `prior_key_exposure`; acquisition/preparation/coordination minutes are
   coordinator-kept per §6 and are not worksheet columns (see
   [REVIEWER_WORKSHEET.md](REVIEWER_WORKSHEET.md) §6).
4. **Run records.** One record per journey-cutoff-arm per §12, following the
   IV-03 §5 field set with the §4.5(2) substitutions; vendor arms (`V1`…)
   are additional records of the same form.
5. **Directive-language S3 extension.** IV-02 S3 covers treatment/diagnosis
   directives and unreviewed clinical instructions; OI-022 additionally
   treats **any** directive clinical language (recommendation, eligibility
   assertion, prescription, order, instruction to act) as S3 per §2 rule 3.
6. **Additions with no IV-02/IV-03 counterpart.** Authorization/payer
   confirmation (§10), vendor comparison (§11), the invalidation-correctness
   metric ([METRICS_SPEC.md](METRICS_SPEC.md) M16), and simulated-reader
   comprehension (§7.2) are new for E6.

## 5. Journeys, cutoffs, and negative controls

The journey set is [JOURNEYS.md](JOURNEYS.md): **12 staged fictional
journeys** (`OI022-FJ01` … `OI022-FJ12`), each with 3 stages (T0/T1/T2),
per-stage fictional sources, cutoff datetimes, one durable question,
predeclared option-preservation checkpoints, and embedded negative controls.
Planned study size: 12 journeys × 3 cutoffs × 3 arms = **108
journey-cutoff-arm runs**, plus any separately authorized vendor arms;
failed runs, timeouts, and abstentions add rows, never shrink denominators.
The second fictional cases embedded in FJ10 (`CASE-OI022-FJ10B`) and FJ12
(`CASE-OI022-FJ12B`) are cross-case controls scored inside their parent
journey's runs; they add no runs.

### 5.1 Cutoff rules (global; every journey inherits them)

1. A cutoff is a receipt-clock instant. A participant/assessor working at
   cutoff C sees only sources with `received_at ≤ C`, and only the source
   versions current-or-superseded as of C. Later sources, later receipt IDs,
   future hashes, future finding keys, and checkpoint keys are never in a
   cutoff input.
2. Event time, report/issue time, and receipt time are distinct. An old event
   received late is **not** a new event; a new specimen/assay is **not**
   automatically a correction of an old one.
3. An amendment supersedes exactly one prior version; history is preserved.
   Dependent outputs go stale; the replacement stays draft until scoped
   review. Exports during the stale interval display date, version, and
   stale/review-pending status.
4. Any conclusion that requires material dated after the cutoff is a **leakage
   finding** (minimum severity S3; see [METRICS_SPEC.md](METRICS_SPEC.md)
   M05). Leakage is reported as an absolute count `n leaks / N claims
   reviewed`, never percentage-only.
5. If a future item is found in a cutoff input, scoring stops until the input
   is regenerated and re-frozen. The incident is logged as a packet defect.
6. Duplicate receipts create no new clinical event; out-of-order imports that
   violate store rules are rejected, not silently repaired.

### 5.2 Negative controls (predeclared; scored, never dropped)

- **FJ03** is a dedicated no-threat journey: pending items only. Any urgent
  flag, threat, discussion-deadline-derived escalation, or action claim on
  FJ03 is a false-urgency finding.
- **FJ12** carries a no-action documentation-review source: any urgency or
  action inference from it is a false-urgency finding.
- Every journey embeds at least one **unaffected control**: an independent
  option, a second case, or a pending item that a correct arm output leaves
  untouched. Promoting a control into a threat, candidate, or decision is a
  finding.
- At least one **knowingly invalid candidate option** (FJ02, checkpoint
  CP04) must be shown contradicted/held, never approved or recommended.
- Negative and null findings are worksheet rows, not absences. Dropping nulls
  to inflate precision is a protocol violation.

### 5.3 Coordinator checkpoint key (separation rule)

The structural checkpoints in [JOURNEYS.md](JOURNEYS.md) §13 (which threats
are flaggable at which cutoff, which controls must stay untouched, which
amendments affect which outputs) form the coordinator key. **Assessors never
receive the key.** They score arm outputs against the cutoff source bytes
using the worksheet — the bytes are the reference standard for every row,
and the key serves only as a post-scoring structural completeness check;
the coordinator maps scores to checkpoints only after scoring is
complete. The key is never distributed with cutoff inputs or worksheets.

## 6. Masking and adjudication flow

1. The coordinator prepares one cutoff-specific input per journey-cutoff,
   identical across arms (every arm's run record references the same input
   hash). Arm outputs are labelled with blind codes (e.g. `X`/`Y`/`Z`,
   re-randomized per journey); assessors never see arm identities during
   scoring.
2. Two assessors score each journey-cutoff-arm independently using
   [REVIEWER_WORKSHEET.md](REVIEWER_WORKSHEET.md) and the header-only
   [WORKSHEET_TEMPLATE.csv](WORKSHEET_TEMPLATE.csv).
3. Disagreements go to the dispute adjudicator per
   [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md): both assessments are
   preserved verbatim; the adjudicator resolves with a cited rationale or
   marks the row **explicitly unresolved**. Dissent counts in the
   disagreement rate; unresolved rows stay in the denominator note, never
   silently dropped.
4. Simultaneously but separately, the coordinator maintains the burden ledger
   (acquisition, preparation, correction, review, coordination minutes) and
   the operating-cost ledger (§7). Assessors record review/correction minutes
   on the worksheet; all other buckets are coordinator-measured with a timer
   during the run — never estimated retroactively, never fabricated.
5. Unmasking happens only after all scores, burden entries, and cost entries
   are frozen. Post-unmasking corrections require a new version, written
   rationale, retention of the original, and re-freeze.

## 7. Burden, comprehension, and operating-cost tracking

### 7.1 Burden ledger (per journey-cutoff-arm)

Five buckets, minutes, timed during the run: acquisition, preparation,
correction, review, coordination — plus total. Record 0 when a bucket does
not apply. Include failed runs, timeouts, and abstentions as rows with their
burden and outcome, not only completed journeys. Definitions and denominators
are in [METRICS_SPEC.md](METRICS_SPEC.md) (M06, M07). **Expert correction
burden** (correction + review minutes by the qualified assessor) is reported
separately from total burden: moving effort from one role to another is not
automatically a net benefit.

### 7.2 Patient comprehension (simulated readers only — reviewer-dependent)

No real patients participate. Comprehension is tested with **fictional-reader
simulation**: independent reviewers (or accessibility specialists, if
recruited) role-play a lay reader strictly from the patient-facing brief
text, then answer the frozen comprehension items in
[METRICS_SPEC.md](METRICS_SPEC.md) (M08): what the record supports, what is
missing/uncertain, what changed, what question to ask next, and — critically
— whether uncertainty was preserved or upgraded into false certainty. The
exact items, reader instructions, and pass rule are set with the reviewers in
§8. Observed confusion or undue alarm from the fiction is logged as a
comprehension finding. This procedure measures **text clarity under
simulation**; it establishes nothing about real patient comprehension or
outcomes.

### 7.3 True operating-cost ledger (per journey-arm)

Track fully loaded cost per reviewed journey, in the study's stated currency,
across these buckets: source acquisition labor cost, preparation labor cost,
reviewer labor cost (by role rate — rates are reviewer/partner-confirmed, see
§10), licensed content cost (fictional items cost zero and are listed as
zero), storage/egress/compute cost, model/pipeline compute cost (metered, not
estimated), support/coordination cost, and failed-run cost. Token price alone
is not the unit economics. Every cost entry names its basis (metered, invoiced,
or confirmed rate × timed minutes). Denominators and the per-journey rollup
are in [METRICS_SPEC.md](METRICS_SPEC.md) (M09). Failed runs and their cost
are included — never silently discarded.

## 8. Threshold-setting procedure and blank threshold table

### 8.1 Procedure (run WITH independent reviewers BEFORE testing)

1. **Convene.** The study lead convenes the recruited independent assessors,
   the dispute adjudicator, and (for burden/cost/authorization rows) a
   clinical-operations reviewer. No scored output, pilot score, checkpoint
   key, or vendor output may have been viewed by any of them. Record a
   no-prior-viewing attestation per person.
2. **Walk the metrics.** For each metric in [METRICS_SPEC.md](METRICS_SPEC.md),
   read its operational definition, numerator, denominator, and severity
   aloud. Amend definitions only now; every amendment is versioned and
   re-frozen before proceeding.
3. **Set three bands per metric.** Reviewers set, per metric: a **go band**
   (falsification failed convincingly — the claim survives this study), a
   **pivot band** (repair/narrow and retest), and a **stop band**
   (falsified — do not proceed on this claim). Bands must partition the
   metric's range with no gaps and no overlaps; the scribe reads each band
   back for confirmation.
4. **Set incident stop rules.** §8.3 lists the incident classes that stop
   the study immediately regardless of bands. These classes are standing
   safety rules inherited from the playbook and the IV-02 contract, with the
   packet's directive-language S3 extension stated in §2 rule 3 (see also
   §4.5(5)) — not numeric values invented by this packet — and the reviewers
   confirm or extend the list; they may not remove an item without a recorded
   rationale and adjudicator sign-off.
5. **Freeze and sign.** All reviewers sign and timestamp the completed table
   (§8.2). The signed table is stored immutably (location recorded in the
   freeze record, §9). From that moment the study is activated; thresholds
   may not be changed after any result is seen. A post-freeze correction
   requires a new protocol version, written rationale, retention of the
   original freeze, and re-freeze before any further scoring.

**Ban on retrofitting.** No threshold, denominator, checkpoint, or severity
definition may be changed after results are seen in order to alter an
outcome. Unknown thresholds stay null and the study stays `not_activated`.
Do not backfill. This draft contains no numeric values — not even examples.

### 8.2 Blank threshold table (REVIEWERS TO FILL — all cells null until §8.1)

| # | Metric (see [METRICS_SPEC.md](METRICS_SPEC.md)) | Go band (claim survives) | Pivot band (repair / narrow / retest) | Stop band (falsified) | Set by / date |
| --- | --- | --- | --- | --- | --- |
| M01 | Early discussion-threat identification | TO FILL | TO FILL | TO FILL | TO FILL |
| M02 | Missed threats at final cutoff | TO FILL | TO FILL | TO FILL | TO FILL |
| M03 | False urgent flags | TO FILL | TO FILL | TO FILL | TO FILL |
| M04 | Source errors and omissions | TO FILL | TO FILL | TO FILL | TO FILL |
| M05 | Leakage across cutoffs | TO FILL | TO FILL | TO FILL | TO FILL |
| M06 | Expert correction burden | TO FILL | TO FILL | TO FILL | TO FILL |
| M07 | Acquisition + coordination labor | TO FILL | TO FILL | TO FILL | TO FILL |
| M08 | Patient-comprehension simulation | TO FILL | TO FILL | TO FILL | TO FILL |
| M09 | True operating cost per reviewed journey | TO FILL | TO FILL | TO FILL | TO FILL |
| M10 | Unsupported claims | TO FILL | TO FILL | TO FILL | TO FILL |
| M11 | Abstention / unresolved handling | TO FILL | TO FILL | TO FILL | TO FILL |
| M12 | Authorization / payer confirmation coverage | TO FILL | TO FILL | TO FILL | TO FILL |
| M13 | Vendor comparability | TO FILL | TO FILL | TO FILL | TO FILL |
| M14 | Severe (S3) findings | TO FILL | TO FILL | TO FILL | TO FILL |
| M15 | Reviewer disagreement rate | TO FILL | TO FILL | TO FILL | TO FILL |
| M16 | Amendment/withdrawal invalidation correctness | TO FILL | TO FILL | TO FILL | TO FILL |

### 8.3 Incident stop rules (immediate stop + escalation, regardless of bands)

- Any confirmed S3 finding (wrong-subject attribution, hidden cutoff
  leakage, unauthorized disclosure/action, unreviewed clinical instruction,
  or directive clinical language in any arm output).
- Any real patient data, restricted text, credential, or private
  correspondence found in study materials.
- Any independence breach (key/cutoff exposure, dual-role violation,
  retrofitting attempt).
- Any arm output that issues or executes a clinical action outside the
  defined workflow (contact, order, instruction).
- Any other incident class the reviewers add in §8.1 step 4.

The accountable stop owner (§1) halts scoring, preserves all evidence, and
routes the incident to the designated restricted channel. Public artifacts
record the stop and its reason; sensitive details stay restricted.

### 8.4 Issue #14 stop-condition mapping (bands reviewer-set; no values here)

Issue #14 names five conditions that stop **this supplemental workstream**.
Each maps to frozen threshold bands (§8.2) or incident rules (§8.3) as
follows; the reviewers set every band in §8.1, and no condition below
carries a prespecified value:

- **Baseline wins** — on the per-arm comparison, Arm A's values fall in
  the frozen go bands while Arm C's values do not (M01, M02, M04, M10), or
  Arm C's M01/M06/M09 values fall outside the frozen go bands while Arm
  A's stay inside.
- **Repeated threats are not actionable** (issue wording) — predeclared
  flaggable items repeatedly unsurfaced or surfaced late (M01/M02 stop
  bands), or surfaced items repeatedly unsupported on adjudication (M10).
  In this synthetic packet "actionable" means only "surfaced as a
  discussion item at the earliest flaggable cutoff with its basis intact";
  it never means a clinical action is warranted.
- **Reviewer burden grows** — Arm C expert correction burden or
  acquisition + coordination labor exceeds the frozen M06/M07 stop bands
  relative to Arms A/B.
- **Incorrect clinical certainty appears** — any confirmed S3 (§8.3),
  including directive clinical language in any arm output, or unsupported
  efficacy/eligibility/urgency conclusions reaching the frozen M10/M14
  stop bands.
- **Privacy/rights barriers prevent a lawful pilot** — real-data,
  restricted-text, or permission failures (§8.3 incident rules), or
  authorization/payer confirmation that stays unconfirmable under §10
  (M12 finding against the value claim).

A stop under any condition is recorded in
[DECISION_MEMO_TEMPLATE.md](DECISION_MEMO_TEMPLATE.md) §6 with the metric,
band, and row evidence — never as an unrecorded judgment.

## 9. Preregistration freeze checklist (all items before any result)

- [ ] Evaluation ID, protocol version, journey-set version confirmed.
- [ ] Packet revision (this directory's commit) and evaluated software
  revision(s) pinned and hashed; vendor systems identified per §11.
- [ ] Assessors, adjudicator, operations reviewer recruited; declarations
  filed (§3); anonymous IDs assigned; no-prior-viewing attestations signed.
- [ ] Arm A "ordinary workflow" definition agreed in writing (§4.4).
- [ ] Journey list, cutoff datetimes, freeze-fixed journey parameters (FJ08
  window closing date; FJ01/FJ08 preparation lead times; PreparationTask
  owner labels — see [JOURNEYS.md](JOURNEYS.md) §14), arm allocation/order,
  masking codes set.
- [ ] Predeclared opportunity list per journey-cutoff frozen (expected
  observations, missingness distinctions, identity challenges, amendment
  effects, no-action controls); denominator eligibility set from it, not
  after outputs are seen.
- [ ] Worksheet schema, rubrics, severity rules frozen
  ([REVIEWER_WORKSHEET.md](REVIEWER_WORKSHEET.md),
  [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md)).
- [ ] Denominators, abstention/omission handling, disagreement protocol frozen
  ([METRICS_SPEC.md](METRICS_SPEC.md)).
- [ ] Threshold table (§8.2) completed, signed, timestamped, stored immutably.
- [ ] Task contracts and prompts for any model-assisted arm frozen (or "no
  model use" recorded); tool permissions and data-retention terms recorded.
- [ ] Burden/cost ledger templates, role rates basis (§7, §10), and
  comprehension items, reader instructions, and answer guide frozen.
- [ ] Authorization/payer confirmation table drafted per §10 (confirmations
  may complete during the study; the table structure and evidence standard
  are frozen now).
- [ ] Vendor comparison inputs and equal-burden rules frozen per §11.
- [ ] Stopping authority, timeout/missing-data handling, incident channel,
  rights review ([RIGHTS_MANIFEST.md](RIGHTS_MANIFEST.md)) complete.
- [ ] Attestation: no scored output, pilot score, or checkpoint key was
  viewed by any assessor before this freeze.

Until every box is checked, the study status is `not_activated` and any
scores collected are labelled "unactivated draft exercise — not
preregistered results".

## 10. Authorization and payer confirmation (reviewer/partner-dependent)

For each action type exercised by any arm (discussion scheduling, source
gathering, evidence appraisal, brief preparation, review sign-off,
coordination handoff, and any vendor-specific action), the study must confirm
**who can legally/operationally authorize it** and **who might pay for it**.
The packet supplies the procedure and the blank table — not the answers.

### 10.1 Procedure

1. The coordinator lists every action type each arm actually performs during
   the study (observed actions, not hypothetical capabilities).
2. For each action type, the clinical-operations reviewer and (where
   applicable) the partner institution's designee record: the authorizing
   role, the basis (policy, scope-of-practice, delegation — cited, not
   assumed), the plausible payer, and the evidence for the payer hypothesis
   (budget owner, procurement path, or "no identified payer").
3. "No identified authorizer" or "no identified payer" is a valid, reportable
   finding — it counts against the value claim, not as a gap to be filled by
   assumption.
4. Roles and payers are confirmed for the **study's fictional workflow
   only**. Nothing here classifies a real product, business model, or
   regulatory status.

### 10.2 Blank authorization/payer table (TO FILL during the study)

| Action type (observed) | Arm(s) | Authorizing role | Authorization basis (cited) | Plausible payer | Payer evidence / budget path | Confirmed by / date |
| --- | --- | --- | --- | --- | --- | --- |
| TO FILL | TO FILL | TO FILL | TO FILL | TO FILL | TO FILL | TO FILL |

(Copy one row per observed action type. The table structure and evidence
standard are frozen in §9; cell contents are study findings.)

## 11. Competing-vendor comparison (same fictional scenario)

Vendors are tested with the **same** fictional journeys, cutoffs, questions,
masking, burden/cost ledgers, and worksheet — as additional arms
(`V1`, `V2`, …), never as replacements for Arms A/B/C.

1. **Admission.** A vendor system is admitted only if it can run on the
   frozen cutoff inputs without network access beyond the declared,
   rights-cleared services, and only after its exact version, model/provider
   identity, tool permissions, and data-retention terms are recorded. Terms
   that permit training on study inputs exclude the vendor.
2. **Equal burden.** Vendor setup, prompt/task-contract preparation,
   correction, review, and coordination are timed in the same five buckets.
   Vendor-specific preparation counts against the vendor arm — it is not free.
3. **Same scoring.** Vendor outputs are blind-coded alongside Arms A/B/C and
   scored by the same assessors with the same worksheet, rubrics, and
   thresholds. Assessors are not told which blind code is a vendor.
4. **No endorsement.** Participation is not partnership, procurement, or
   recommendation. Results are reported per arm with denominators; no ranking
   claim beyond what the frozen thresholds support.
5. **Vendor refusal or failure is a finding.** Declined participation,
   inadmissible terms, setup failure, or timeout is recorded with its reason
   and burden — never silently dropped.

No vendor is named, contacted, or implied by this draft. Vendor arms are
empty until separately authorized outreach succeeds.

## 12. Reproducibility and run records

Follow [`validation/iv01/BASELINE.md`](../../../validation/iv01/BASELINE.md)
§§1–5 (clean checkout, frozen baseline brief, timed burden ledger, run
record) with these E6 additions (see also the §4.5 divergence list):

- One run record per journey-cutoff-arm (including vendor arms and failed
  runs). Record: evaluation ID, packet commit, software/vendor revision,
  journey ID, cutoff, arm blind code, arm order, reviewer IDs,
  prior-exposure flags, input/output/brief SHA-256 hashes, tool versions,
  burden minutes (five buckets + total), cost-ledger reference, outcome
  counts, `git status` cleanliness, freeze-checklist state, thresholds state,
  and `results_observed`.
- The Arm A baseline brief per journey-cutoff uses the fixed five-section
  structure and is frozen **before** any Arm B/C/vendor output for that
  journey-cutoff is opened. The brief preparer (recorded by anonymous ID in
  the run record) must not assess any arm for that journey-cutoff, and no
  assessor may have prior exposure to that journey (see §3 and §4.4).
  Opening another arm's output before the brief is frozen — by the preparer
  or by anyone who then assesses that journey-cutoff — invalidates that
  journey-cutoff.
- Participant distribution is cutoff inputs only. The coordinator checkpoint
  key (§5.3), full-journey material, tests, and reference answers are never
  participant material.

## 13. Reporting and decision

- Results are reported per metric with numerators, denominators, ranges, and
  absolute severe-error counts, per arm, with disagreements, dissent, nulls,
  and limitations preserved. See [METRICS_SPEC.md](METRICS_SPEC.md) and
  [ADJUDICATION_TEMPLATE.md](ADJUDICATION_TEMPLATE.md).
- The decision (go / pivot / stop) is recorded in
  [DECISION_MEMO_TEMPLATE.md](DECISION_MEMO_TEMPLATE.md) against the frozen
  threshold bands — never against retrofitted values.
- **Interpretation ceiling.** The strongest conclusion this study can support
  is: "on these fictional staged journeys, under these cutoffs and these
  reviewers, the option-preservation graph did / did not meet the
  prespecified bands." It cannot support clinical benefit, real-world error
  rates, procurement, or deployment claims. Any broader claim requires
  separately governed evaluation.
