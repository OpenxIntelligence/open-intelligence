# IV-04 — activity and disclosure checklist

**Preparation only. All decisions below are unmade.** This is an operational checklist derived from issue #23 and the proposed collaboration playbook, not a statement of law, institutional permission, clinical approval or authorization to send a message. Applicable requirements must be determined for the actual activity by the responsible people and institution.

## Choose the smallest appropriate activity

| Proposed activity | Allowed purpose if separately authorized | Decision evidence needed | Does not authorize |
| --- | --- | --- | --- |
| Non-confidential scoping discussion | Ask whether one question is meaningful and whether the recipient is interested | Project-owner approval for that recipient, exact message and public artifact set; recipient identity/role verified; no private data | Scored research, recruitment of patients, institutional endorsement, data/sample transfer |
| G0 / developmental synthetic walkthrough | Explore limitations of public fictional practice material | Permitted frozen artifacts, purpose and limitations, voluntary scope, feedback handling, prior-exposure disclosure, accountable facilitator | Blinded or held-out performance claims; clinical conclusions |
| G1 / independent scored synthetic review | Test a prespecified claim with reference judgments and a comparator | Appropriate participation/governance determination; independent roles; fresh controlled cases where confirmatory claims require them; prospective metrics, denominators, thresholds and stopping rules; frozen versions | Retrospective real-record use, prospective care, clinical deployment |
| G2 / retrospective real-data research | Evaluate an independently justified question on permitted historical data | Activity-specific institutional/ethics determination where applicable; documented data basis and agreements; access, minimization, security, retention and incident controls | Automatic live-patient workflow use or an exemption declaration by the project |
| G3 / prospective workflow study | Evaluate a specified real-world workflow under accountable oversight | Separate institutional, clinical, participant and regulatory decisions appropriate to the activity; safety and stopping authority | Unrestricted clinical use, treatment advice or marketing efficacy claims |
| GX / experimental biological research | Investigate an independently specified hypothesis | Qualified partner, scientific protocol/controls, safety and ethics determinations, sample rights/custody, facilities and agreements | Any sample acquisition, shipment, wet-lab work or human intervention based on software review alone |

An ordinary non-confidential discussion should not be treated as a formal study by default. Conversely, calling an activity a demonstration does not resolve its actual governance requirements. Unknown scope is a reason to clarify and limit disclosure, not guess that everything is allowed.

## Before any message is sent

- [ ] Record recipient reference, proposed role, bounded question, contact owner and requested activity. Keep private identifiers out of public GitHub.
- [ ] Approve the exact invitation revision and complete attachment/link list. A public repository can contain designer keys; share only the intended materials and do not promise blinding.
- [ ] Check the rights, confidentiality and disclosure purpose of each artifact. Exclude real records, secrets, restricted article content, private negotiations and unpublished data unless separately authorized.
- [ ] Record project-owner authorization for this recipient, purpose, channel, artifact set and validity period. No default approval or inferred consent.
- [ ] Record that interest, a reply, or a public affiliation is not a partnership or institutional agreement.

## Before evaluation begins

- [ ] Classify the contribution with INDEPENDENCE_AND_ROLES.md; record relevant expertise, conflicts, prior key/future-result exposure and any recusal.
- [ ] Freeze the exact application, packet, protocol and source-rights versions; record hashes and the permitted input/output locations. Confirm which PRs are actually merged rather than describing draft material as released.
- [ ] For scored work, use the existing IV-01–03 packet, adjudication and baseline contracts. Freeze cases, arm order, denominators, acceptance/stop thresholds and handling of abstention, omission and failed runs before looking at results.
- [ ] Determine institutional participation, ethics, agreements/DUA, privacy/security and consent requirements for the actual activity. Record an authorized not-applicable determination where justified; do not silently assume one.
- [ ] Agree expected effort, compensation if applicable, confidentiality, publication/attribution, intellectual-property handling, feedback storage/access and retention. No outcome-conditioned positive endorsement.
- [ ] Name accountable coordination, clinical/experimental roles where relevant, and stop/incident owners. Define where urgent concerns or suspected disclosure go; do not put patient details into public issue trackers.
- [ ] Record each participant's acceptance of the specific activity. Approval to contact and agreement to participate are separate events.

## During and after the activity

Stop or pause under the agreed plan if permission is withdrawn, prohibited material appears, identities or artifacts are misbound, future-cutoff information is exposed, or a participant is asked for an unapproved clinical/experimental action. Preserve the permitted evidence of what happened; do not erase failures or rewrite a protocol after seeing results. Route sensitive incident details to the designated restricted channel.

Record actual activity dates, roles, exact artifacts, raw permitted observations, deviations, negative/null findings, dissent and decision. Distinguish `proceed_to_next_authorized_step`, `repair_and_retest`, `narrow_claim`, and `stop`; these outcomes do not confer clinical release clearance.

## Decision record semantics

Use decision_template.json in a restricted location once populated. Choose exactly one current disposition:

- `not_reviewed`: default; no outreach or evaluation authorization.
- `approved_for_nonconfidential_discussion`: limited to the recipient, purpose and artifacts expressly recorded; no scored review.
- `approved_for_synthetic_review`: limited to the separately specified practice or scored synthetic activity and its conditions.
- `needs_more_governance`: scope/authority, data, conflicts or required review unresolved; do not start the affected activity.
- `stop`: do not initiate or continue; preserve the recorded reason and escalation path.

A label by itself grants nothing. A disposition must reference an actual accountable decision, evidence, valid scope and participant acceptance where required. Blank fields remain unknown; the template does not supply identities, dates, signatures, reviewers, thresholds or approvals.

## Current state

No recipient selected, disclosure approved, invitation sent, participant recruited, score recorded, agreement signed, specimen transferred or study activated by this package. Issue #23 remains open for review. Existing application architecture, OI-001–018 priorities and clinical authority boundaries remain intact.
