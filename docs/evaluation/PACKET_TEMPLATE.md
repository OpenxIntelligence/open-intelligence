# Independent Evaluation Packet — Blank Template

**Open Intelligence · Complementary to existing architecture · Unexecuted template**

> Use one packet per bounded claim. Complete and freeze the protocol before opening held-out materials or collecting evaluation results. No real patient identifiers, restricted data, confidential collaborators or private agreements belong in this public template.

## 1. Evaluation identity

| Field | Entry |
| --- | --- |
| Evaluation ID | TO ASSIGN |
| E-track | E0 / E1 / E2 / E3 / E4 / E5 / E6 or separately governed experimental protocol |
| Claim / capability | TO SPECIFY |
| Intended audience, decision and setting | TO SPECIFY |
| Explicit non-claims | TO SPECIFY |
| Study stage / permitted data | Synthetic-only initially; controlled real-data research requires separate authorization |
| Preregistration date and immutable location | TO COMPLETE BEFORE RESULTS |
| Study lead / accountable stop owner | TO ASSIGN |
| Review independence and declared conflicts | TO DOCUMENT |
| Approved sharing scope | TO DOCUMENT |

## 2. Frozen implementation and input manifest

- Git commit: TO RECORD
- Product/module versions, provider/service configuration and disabled network paths: TO RECORD
- Exact evaluation mode and permitted clinical/experimental inference: TO RECORD
- Data rights, provenance and redistribution permissions: TO RECORD
- Original source hash + version for every input: TO RECORD
- Case/time cutoffs (no future information revealed to a historical decision): TO RECORD
- Reference authors and reviewers; independence disclosures: TO DOCUMENT
- Environment, commands, fixtures and output locations: TO RECORD
- Allowed outputs/visibility and retention: TO RECORD

**Stop before testing if** the data origin, permitted use, review independence, version or essential safety controls cannot be established.

## 3. Study question and comparison

**Question:** TO SPECIFY

**Intervention/workflow A:** TO SPECIFY (usually manual/current case preparation)

**Comparator B:** TO SPECIFY (minimal structured/source-linked brief or simple non-agent tool)

**Comparator C, if applicable:** TO SPECIFY (optional option preservation E6 only)

**Randomization, masking and order effects:** TO SPECIFY

**Eligibility, exclusions and negative/no-action controls:** TO SPECIFY

**Study population:** Independently authored fictional records to start. Future governed data only after institution-specific approvals.

## 4. Preregistered outcomes — complete denominators before any result

| Domain | Operational numerator | Operational denominator | Severity | Prespecified pass/fail threshold |
| --- | --- | --- | --- | --- |
| Source identity and version fidelity | TO DEFINE | TO DEFINE | TO DEFINE | TO DEFINE |
| Wrong-subject or wrong-specimen errors | TO DEFINE | TO DEFINE | Severe where consequential | TO DEFINE |
| Amendment and historical cutoff accuracy | TO DEFINE | TO DEFINE | TO DEFINE | TO DEFINE |
| Supported versus unsupported clinical claims | TO DEFINE | TO DEFINE | TO DEFINE | TO DEFINE |
| Unknown eligibility and justified abstention | TO DEFINE | TO DEFINE | TO DEFINE | TO DEFINE |
| Contradiction/negative evidence preservation | TO DEFINE | TO DEFINE | TO DEFINE | TO DEFINE |
| End-to-end work per case (minutes) | Per-case measure | Total attempted cases, including failures | TO DEFINE | TO DEFINE |
| Patient/care-team comprehension (if in scope) | TO DEFINE | TO DEFINE | TO DEFINE | TO DEFINE |
| Unauthorized disclosure / unreviewed action | Events observed | Relevant attempts/exposures | Severe | TO DEFINE |

Don't choose a threshold after observing results; a 0-event synthetic sample is not proof that a severe failure cannot occur. Report sample size and uncertainty.

## 5. Blind adjudication and disagreements

- Independent reviewer ID (use nonidentifying code in public artifacts): TO ASSIGN
- Expertise needed for each claim: TO SPECIFY
- Reference truth provenance: TO SPECIFY; mark unverifiable rather than invent certainty
- Masked case presentation format and cutoff: TO DEFINE
- Accept / incorrect / insufficient evidence / indeterminate / cannot assess: TO DEFINE IN RUBRIC
- Adjudication of conflicts: TO SPECIFY BEFORE UNMASKING
- Escalation and immediate stop owner: TO ASSIGN

Reference answers must not be injected into evaluation fixtures or prompts presented to the system being assessed.

## 6. Case execution and reproducibility

Capture in a restricted evaluation log where permitted: case ID, cutoff, source versions, observed claim, source anchor, baseline observation, reviewer judgment and reason, software result, disagreement, severity, corrections and time. The accompanying [blank result register](./RESULTS_REGISTER_TEMPLATE.csv) supplies a machine-readable header.

Commands/steps: TO DOCUMENT

Test execution date, environment and run links: TO RECORD

Deviations and failed runs (never silently discard): TO RECORD

## 7. Safety, rights and interpretation

- Governance/ethics/DUA/privacy status and accountable institution: TO DOCUMENT; not approved by this template.
- Confirm no real patient data, copyrighted guideline passages, private communication, model secret, or restricted scientific asset is committed publicly.
- Experimental/biological studies have additional protocol, sample custody, quality and appropriate approval gates. They are not implied by product evaluation.
- Clinical performance, regulatory clearance, treatment efficacy and patient benefit are not inferable from a software simulation or bibliographic metadata panel.

## 8. Report and irreversible record

**Actual evaluated sample and denominators:** NOT YET EVALUATED

**Primary and negative/null findings:** NOT YET EVALUATED

**Counterexamples, reviewer disagreements and limitations:** NOT YET EVALUATED

**Unexpected harms/incident report (if any):** NOT YET EVALUATED

**Decision:** NOT STARTED / GO / REPAIR AND RETEST / NARROW CLAIM / STOP

**Decision author, date and immutable evidence location:** TO COMPLETE

**Proposed effect on the architecture:** No automatic change; any amendment requires the established Open Intelligence decision, test and review process.

See [Independent Evaluation & Collaboration Playbook](../INDEPENDENT_EVALUATION_COLLABORATION.md), existing [OI-001–018 backlog](../EXECUTION_BACKLOG.csv), [validation plan](https://app.notion.com/p/40a3866f77ef816f9cd4df7a9efb9b9b), and optional [E6 issue #14](https://github.com/OpenxIntelligence/open-intelligence/issues/14).
