# Reviewer rubric and preregistration contract

This is supporting evaluation methodology, not a validated clinical instrument. Public practice-fixture answers were prepared by the same AI-assisted author as the fixtures; they require independent clinical and methodological review.

## Roles

Separate the feature builder, packet coordinator/reference author, independent assessor and dispute adjudicator. Record each person's involvement in feature/fixture design, access to keys/future facts, financial conflicts and relevant qualification. Store personal identities in an authorized private register; use anonymous IDs in public outputs. No recruited reviewers or partner institutions are implied.

## Unit of assessment and denominators

One row represents one predeclared opportunity or one output claim, for one case, cutoff, arm and reviewer. Use outcome `correct`, `incorrect`, `unsupported`, `omitted`, `abstain`, `not_applicable` or `not_scored`; never force unknown into false. Preserve denominator eligibility before looking at results.

| Metric | Numerator / denominator | Required caveat |
|---|---|---|
| Source fidelity | Assessed claims with correct resolvable source/version/anchor / all assessable output claims | Also score expected-but-omitted assertions; do not hide missing claims by shrinking this denominator |
| Missingness fidelity | Correct negative/untested/pending/indeterminate distinctions / predeclared missingness opportunities | Abstention and omission reported separately |
| Identity boundary | Correctly handled wrong-case or wrong-specimen attempts / supplied identity challenges | A source hash is not patient authentication |
| Amendment handling | Correct stale/preserved-history outcomes / predeclared affected outputs | Record unaffected controls separately |
| Temporal leakage | Number of conclusions using post-cutoff material / all assessed conclusions | Also report absolute leak count; no percentage-only reporting |
| Unsupported evidence | Patient-specific efficacy/eligibility conclusions without adequate support / all assessed conclusions | Invented evidence is not real efficacy evidence |
| False urgency | Unjustified urgency/action claims / no-action opportunities | No-action correctness does not establish clinical safety |
| Work burden | Total acquisition + preparation + correction + review + coordination minutes per case/arm | Record failed runs, denominator, range and assessor time; no fabricated timing |

## Severity and disagreements

S0: no consequential discrepancy. S1: presentation or traceability inconvenience with retained meaning. S2: wrong source/chronology/missingness or unsupported interpretation with potential to mislead review. S3: wrong subject attribution, hidden future-data leakage, unauthorized disclosure/action, or unreviewed clinical instruction. These are proposed review labels, not validated clinical-harm ratings. A clinician may disagree: record both assessments, sources and reason; an adjudicator resolves or leaves unresolved. Do not average away an S3 finding. A deliberate wrong-patient test input is not itself an incident; failure to handle it correctly is a finding.

## Before opening scored outputs

Complete evaluation ID; packet/application commit; assessor roles/conflicts; whether exposed to the public key; inputs and exclusions; arm allocation/order; metrics and eligible denominator; acceptable error/omission limits; burden-improvement target; stopping authority; reviewer agreement protocol; handling of timeouts and missing data; source rights; study/disclosure authorization appropriate to the actual activity. Unknown thresholds stay null and evaluation stays `not_activated`. Do not retrofit a passing threshold after inspecting results.

## Decision template

Outcome: proceed to next authorized evaluation / repair and retest / narrow the claim / stop. Record supporting run IDs, severe errors, omissions, dissent, missing evidence, thresholds chosen prospectively and named accountable approver. Passing engineering checks permits further review only; it is not clinical endorsement, regulatory approval or permission for real patient use.
