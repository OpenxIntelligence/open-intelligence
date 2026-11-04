---
# Journey archetypes, scoped slice for issue 128 (OI-28)

This is a draft research document only. It does not replace the
existing architecture, it does not make a clinical efficacy claim,
and it does not authorize any clinical action.

## Data boundary, stated plainly

No patient dataset was retrieved, downloaded, stored, ingested,
trained on, evaluated, or benchmarked for this document. No exact
treatment timeline is reproduced here, and no named person's medical
records are used. The three archetypes below are independently
invented fictional examples, not case downloads and not a retelling
of any named person's journey. Where a capability is described as
implemented, it means it exists on main at 2451983 in the synthetic
prototype; where it is proposed, it is labeled proposed, not verified.

## Archetype 1: no research staff, community clinic

- Who, invented: a patient whose clinic has no dedicated research
  coordinator, and whose records arrive from two fictional community
  sources.
- Platform abstraction: record acquisition with a receipt per
  source, then a task-first list, not a chat thread. The patient sees
  state and next tasks first.
- Workflow dependency: acquisition depends on source-version
  receipts; normalization depends on those receipts, not on a
  clinician retyping a record.
- User and clinician need: the patient needs to know what arrived,
  what is missing, and what to do next, in plain language. The
  clinician needs the same record with source, version, and line
  anchors, not a summary that hides its origin.
- Safety and rights gate: wrong-patient deliveries are quarantined,
  never asserted. Evidence is review-pending, never presented as a
  validated finding.
- Opportunity to improve: a missing-record task that names the
  source and the exact gap, instead of a generic "records incomplete"
  banner.
- OI mapping, implemented on main: source-version receipts and
  quarantine in the store; snapshot drafts over current sources.
- OI mapping, proposed: a plain-language missing-record task
  generator, not yet built.

## Archetype 2: no tertiary-center access, remote review

- Who, invented: a patient far from a tertiary center, whose care
  team reviews material remotely and asynchronously.
- Platform abstraction: temporal evidence with amendment history.
  When a source is amended, conclusions built on the old version go
  stale, visibly, instead of silently updating.
- Workflow dependency: review depends on a stable snapshot, not on
  a live document that can change under the reviewer.
- User and clinician need: the patient needs to know when a
  conclusion is stale and why. The reviewer needs the original
  version, the amended version, and the basis for the change.
- Safety and rights gate: a stale snapshot cannot be acknowledged
  as current. Rights revocation blocks redistribution, not just
  display.
- Opportunity to improve: a stale-conclusion notice that carries
  the exact source version that changed, so the reviewer does not
  have to re-read the whole record.
- OI mapping, implemented on main: amendment supersession and
  snapshot invalidation in the store; demo review acknowledgement.
- OI mapping, proposed: a remote-review packet that bundles
  snapshot, basis, and provenance in one auditable receipt.

## Archetype 3: limited digital literacy, caregiver-assisted

- Who, invented: a patient who prefers paper and phone calls, with
  a caregiver who helps with tasks, under explicit delegation.
- Platform abstraction: task-first screens with one task at a time,
  conversation optional, never the primary organizing principle.
  Delegation is a recorded permission, not a shared password.
- Workflow dependency: every task depends on a named owner and a
  named source. A task with no source anchor cannot be marked done.
- User and clinician need: the patient needs tasks that can be
  completed by phone or on paper and then recorded, without
  navigating a research interface. The caregiver needs a clear
  boundary: which tasks they may do, and which require the patient
  or clinician.
- Safety and rights gate: caregiver access is scoped, revocable,
  and logged. No treatment selection, ranking, dosing, eligibility,
  diagnosis, or prognosis is offered by the platform.
- Opportunity to improve: a printable task sheet that mirrors the
  on-screen task list exactly, with source anchors printed alongside
  each task.
- OI mapping, implemented on main: task-first screens in the
  existing plain-JS interface; review-pending state on all outputs.
- OI mapping, proposed: scoped caregiver delegation and printable
  task sheets, neither yet built.

## What this slice does not do

It does not update the full 40-activity OI-28 matrix, it does not
produce 10 to 15 complete journeys, it does not compare alternatives
on cost and workload in detail, and it does not build the fictional
end-to-end demo. Those remain open deliverables for issue 128, and
this document does not claim them.
---
