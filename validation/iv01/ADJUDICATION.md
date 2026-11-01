# IV-02 — Independent adjudication contract

Status: **contract only, unadjudicated.** No independent reviewer has yet run
this contract against a packet, so nothing in this document is evidence that
an evaluation happened. A passing unit test is not clinical validation, and
a correct trace to a synthetic source is not clinical validity.

Scope: issue #22 (IV-01–03), backlog items OI-011 and OI-014, and the
evaluation protocol proposed in PR #18. This contract governs how outputs
produced from a synthetic challenge packet are scored. It does not create a
packet, a canonical state, a source ledger, or a competing roadmap, and it
does not change the architecture, the stack, or any priority.

## 1. Synthetic-only boundary

- All packet material is independently authored fiction. No real patient
  data, no restricted clinical content, no copied licensed text.
- Reviewers make **no clinical claims** and no treatment, diagnosis, or
  progression inference. Every judgment here concerns traceability to packet
  sources at a declared cutoff — not clinical truth.
- If any packet element resembles a real identifier, a real record, or
  restricted text, stop scoring that element, log it as a packet defect, and
  escalate it to the packet coordinator. Resemblance confers no meaning.

## 2. Roles, independence, and conflict declarations

Four roles are kept separate. One person must not hold two of them for the
same evaluation:

| Role | Must not also be |
| --- | --- |
| Feature builder | Packet coordinator, assessor, adjudicator |
| Packet coordinator / reference author | Assessor, adjudicator |
| Independent assessor (scores outputs) | Feature builder, packet coordinator |
| Dispute adjudicator (resolves disagreements) | Assessor of the same rows |

Before any scored output is opened, each assessor and adjudicator files a
declaration recording:

- involvement in feature construction, packet authorship, or prompt/model
  tuning for the evaluated system;
- financial or institutional conflicts in the outcome;
- relevant qualification for the review task (methodological; no clinical
  qualification is implied by this packet);
- **prior exposure**: whether they have seen any answer key, designer
  reference, pilot score, or full-case packet material, and when.

A reviewer with prior key exposure is recused from primary scoring of the
affected cases; they may serve only as a logged, non-voting observer.
Personal identities live in an authorized private register; public outputs
use anonymous reviewer IDs. An independence breach voids the affected scores
and triggers re-adjudication. No reviewer or partner institution is implied
by this template — names are filled in only when real people are recruited
under appropriate authorization.

## 3. Two rubrics, never merged

Rubric A and Rubric B are scored in **separate columns**, reported
separately, and must never be merged, averaged, or substituted for each
other. There is no combined score column.

### Rubric A — Claim-level source correctness

Question: does the output claim match a cited source version and anchor
**as it existed at the cutoff**?

Outcome vocabulary (one value per row):

- `correct` — faithful to the cited source version and anchor; the anchor
  is locatable in the cutoff input.
- `incorrect` — mismatch with the cited source, wrong version, or a claim
  about a source that does not support it.
- `unsupported` — no packet source at the cutoff supports the claim.
- `omitted` — a predeclared expected observation is absent from the output.
- `abstain` — the reviewer formally abstains (see §6).
- `not_applicable` — the opportunity does not apply to this case/cutoff/arm.
- `not_scored` — the row was excluded before scoring for a recorded reason.

Unknown is never forced into false: if the packet at the cutoff does not
settle a point, the correct Rubric A outcome is `unsupported` or `omitted`
as applicable — never `incorrect` by default, and never `correct` by
inference from a later source.

### Rubric B — Clinical applicability and uncertainty (separate)

Question: is the claim applicable, and is its uncertainty preserved?

Rubric B is scored on a separate scale:

- `uncertainty-preserved` — the output keeps the packet's distinctions
  (untested vs negative, pending vs indeterminate, order vs
  administration, old event newly received vs new event) and claims no
  more than the sources support.
- `overstated` — the output upgrades uncertainty into a firmer claim, or
  draws an efficacy, eligibility, urgency, or action inference the packet
  does not support.
- `not-assessable-from-synthetic-packet` — the default for any
  applicability question the synthetic packet cannot settle. This is the
  expected value for genuine clinical-applicability judgments: a synthetic
  practice packet cannot establish them.
- `abstain`, `not_scored` — as in Rubric A.

Rubric B is **never scored as clinical validity**. A `correct` on Rubric A
plus `uncertainty-preserved` on Rubric B means only that the output traced
faithfully and did not overstate the fiction. It is not endorsement,
regulatory approval, or permission for real patient use.

## 4. Severity categories

Severity is assigned per row, independently of the Rubric A/B outcomes:

- **S0** — no consequential discrepancy. Cosmetic or presentational only.
- **S1** — presentation or traceability inconvenience with meaning
  retained (for example, an awkward anchor format or a redundant citation).
- **S2** — wrong source, chronology, or missingness, or an unsupported
  interpretation with potential to mislead review (for example, a
  pre-cutoff fact cited as post-cutoff, an untested marker reported as
  negative, or a qualifier dropped so the scope changes).
- **S3** — wrong-subject attribution, hidden future-data leakage,
  unauthorized disclosure or action, or an unreviewed clinical
  instruction. Any treatment or diagnosis directive derived from synthetic
  data is S3.

Rules:

- S3 findings are **never averaged away**. Each confirmed S3 is listed
  individually with its row ID and requires explicit resolution. Summary
  rates are reported with and without S0/S1, but the S3 count stands alone.
- One confirmed S3 blocks a `go` decision (see §8).
- A deliberate wrong-patient or wrong-specimen test input is not itself an
  incident; **failure to handle it correctly** is the finding.
- A clinician or second reviewer may dispute a severity: record both
  assessments, the sources, and the reason; the adjudicator resolves or
  leaves the row explicitly unresolved (see §6). Disagreement never
  silently downgrades an S3.

## 5. Denominators and thresholds frozen BEFORE scoring

No scored output is opened until the following are frozen in writing,
signed, and timestamped:

1. Evaluation ID, packet commit, and application commit (see BASELINE.md).
2. Case list, cutoff dates, and arm definitions (Arms A/B/C).
3. The predeclared opportunity list per case: every expected observation,
   every missingness distinction (untested / negative / pending /
   indeterminate), every identity challenge, every amendment effect, and
   every no-action control.
4. The worksheet schema (§7) and the Rubric A/B rules and S0–S3 examples.
5. Primary and secondary denominators (below), the handling of
   abstentions and omissions, and the reviewer-agreement protocol.
6. Empirical thresholds: minimum source-fidelity rate, minimum
   missingness-fidelity rate, maximum omissions, maximum S2 count,
   acceptable burden change, and the abstention/unresolved limits.
7. Stopping authority, timeout and missing-data handling, source-rights
   review, and the authorization appropriate to the actual activity.
8. Attestation: no scored output was viewed before the freeze.

**Ban on retrofitting.** No threshold, denominator, opportunity, or
severity definition may be changed after results are seen in order to
alter an outcome. A post-freeze correction requires a new version, a
written rationale, retention of the original freeze, and a re-freeze before
any further scoring. Unknown thresholds stay null and the evaluation stays
`not_activated`.

### Predefined denominators

One row represents one predeclared opportunity or one output claim, for one
case, cutoff, arm, and reviewer. Denominator eligibility is fixed at freeze
time, before results are seen:

| Metric | Numerator / denominator |
| --- | --- |
| Source fidelity | Assessed claims with `correct` Rubric A / all assessable output claims. Expected-but-omitted assertions are also scored (as `omitted`); the denominator must not be shrunk to hide missing claims. |
| Missingness fidelity | Correct untested / negative / pending / indeterminate distinctions / predeclared missingness opportunities. Abstention and omission reported separately. |
| Identity boundary | Correctly handled wrong-case or wrong-specimen attempts / supplied identity challenges. A source hash is not patient authentication. |
| Amendment handling | Correct stale-version / preserved-history outcomes / predeclared affected outputs. Unaffected controls recorded separately. |
| Temporal leakage | Conclusions using post-cutoff material / all assessed conclusions. Also report the absolute leak count; never percentage-only. |
| Unsupported evidence | Patient-specific efficacy / eligibility conclusions without adequate support / all assessed conclusions. Invented evidence is not real efficacy evidence. |
| False urgency | Unjustified urgency / action claims / no-action opportunities. No-action correctness does not establish clinical safety. |
| Work burden | Total acquisition + preparation + correction + review + coordination minutes per case/arm (see BASELINE.md). Record failed runs, denominator, range, and assessor time; no fabricated timing. |

## 6. Disagreements and abstentions

### Disagreements

- Claims in the sampled set are scored independently by two assessors,
  blind to each other's scores.
- On any disagreement about a Rubric A outcome, a Rubric B outcome, or a
  severity level, **both assessments are recorded verbatim** in the
  worksheet, with sources and reasons.
- The dispute adjudicator either resolves the row with a cited
  source/version rationale or marks it **`explicitly unresolved`** with a
  reason. Dissent is preserved in the record and counts in the disagreement
  rate. Unresolved rows are excluded from the numerator but retained in
  the denominator note — never silently dropped.
- Disagreement rate, unresolved count, and every unresolved row ID are
  reported with the results.

### Abstentions

A reviewer abstains — rather than guessing — when any of these hold:

- a packet defect prevents judgment;
- a cutoff ambiguity is unresolved;
- a conflict is discovered mid-review;
- prior key exposure is discovered mid-review.

How to abstain: set the row outcome to `abstain`, cite a reason code plus
free text, and notify the lead without revealing a provisional score.
Abstentions are **reported separately from omissions** (an omission is a
missing score without a declared reason) and are **never scored as correct
or incorrect**. An abstention rate above the frozen limit triggers
`repair`; omissions trigger an audit of the review process itself.

## 7. Claim-level worksheet

One row per predeclared opportunity or output claim, per case / cutoff /
arm / reviewer. Required columns (no hidden columns; no merged A/B column):

```text
evaluation_id, packet_commit, application_commit, run_id, reviewer_id,
case_id, cutoff, arm, opportunity_id, claim_id, denominator_eligible,
source_ids, source_versions, source_lines, rubric_a_outcome,
rubric_b_outcome, severity, missingness_error, identity_error,
post_cutoff_leak, unsupported_claim, false_urgency,
acquisition_minutes, preparation_minutes, correction_minutes,
review_minutes, coordination_minutes, prior_key_exposure,
disagreement, adjudicator_outcome, reason, evidence_location
```

Column rules:

- `denominator_eligible` is set at freeze time, not after seeing results.
- `post_cutoff_leak` names the post-cutoff source (if any); a leak is a
  finding, not a scoring footnote.
- `missingness_error`, `identity_error`, `unsupported_claim`, and
  `false_urgency` are boolean flags recorded even when the row's Rubric A
  outcome is otherwise `correct` — a claim can trace to a source and still
  overstate it.
- Negative and null findings are rows, not absences: a correct null ("no
  packet support at this cutoff"), a correct negative, and a false
  positive (an output claim with no source) are all preserved in the
  worksheet. Dropping nulls to inflate precision is a protocol violation.
- False positives are preserved and counted; they are not deleted as
  "noise".

A blank worksheet template with exactly these columns accompanies the
packet for each evaluation. The coordinator's reference key, if one exists,
is **never** distributed with the worksheet or the participant inputs.

## 8. Leakage ban

- Any conclusion that requires material dated after the case cutoff is a
  leakage finding, recorded with case ID, claim ID, post-cutoff source ID
  and date, and reviewer.
- Leakage is reported as an **absolute count** (n leaks / N claims
  reviewed), never percentage-only.
- Confirmed leakage is at minimum S3 and blocks a `go` decision.
- The cutoff input given to a participant or arm must contain no future
  sources, future receipt IDs, future hashes, or reference answers. If a
  future item is found in a cutoff input, scoring stops until the input is
  regenerated and re-frozen.

## 9. Go / repair / stop decision template

Record, for the frozen denominators: N opportunities, N claims, Rubric A
correct rate, Rubric B uncertainty-preserved rate, S0/S1/S2/S3 absolute
counts, leakage n/N, abstain n, omission n, unresolved n, disagreement
rate, and burden per case/arm.

- **Go** (proceed to the next authorized evaluation step) requires all of:
  Rubric A rate at or above the frozen threshold; S3 count zero; leakage
  zero; omissions zero; abstentions and unresolved rows within frozen
  limits; negatives and nulls retained in the record.
- **Repair** (fix and retest) on: any S2 count above the frozen limit, a
  threshold miss on either rubric, excess abstentions or unresolved rows,
  packet defects, or a disputed S3 that the adjudicator resolves as
  non-S3 with a documented rationale and preserved dissent. State the
  repair actions and re-freeze before re-scoring.
- **Stop** on: any confirmed S3 (wrong-subject, leakage, disclosure, or
  clinical instruction), systematic chronology failure, a retrofitting
  attempt, or an independence breach. List the S3 / leakage row IDs.

The decision is signed by the adjudicator, with dissent attached, and
names the accountable approver. Passing engineering checks permits further
review only; it is not clinical endorsement, regulatory approval, or
permission for real patient use.

## 10. How this pairs with the runnable packet (PR #24)

PR #24 ("eval: runnable synthetic challenge packet for IV-01–03") supplies
the packet machinery this contract scores: fictional cases, hashed sources,
receipts, cutoffs, a cutoff-specific participant-input generator, a
designer reference key, and a short scoring note. Where that packet is
present, its severity labels (S0–S3), outcome vocabulary, and denominator
table are the same ones used here, and this contract is the fuller
adjudication procedure behind its short note: the declaration form (§2),
the separate Rubric B scale (§3), the freeze checklist (§5), the dual
scoring and abstention procedure (§6), and the worksheet column rules
(§7). Where the packet is absent, this contract still applies to any
packet satisfying issue #22; nothing in it depends on fixture IDs, source
texts, or reference answers, and none appear in this document.

## Attestation (copy into the evaluation record)

> We certify: synthetic-only scope; denominators and thresholds frozen
> before any scored output was opened; Rubrics A and B scored and reported
> separately, never merged; nulls, negatives, false positives,
> abstentions, disagreements, and leakage counts fully preserved; and no
> claim of independent evaluation beyond what the filed reviewer evidence
> actually shows.
