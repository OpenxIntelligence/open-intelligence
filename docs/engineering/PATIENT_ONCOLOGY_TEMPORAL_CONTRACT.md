# Patient Oncology: unified patient context and traceable longitudinal history

**Founder direction: 7 November 2026, America/New_York.** The product naming,
unified patient architecture and chronological provenance requirements below
are adopted requirements. Detailed contract shapes and implementation sequencing
are engineering specifications to realize through existing owners, not claims
of an implemented or clinically qualified capability. This complements the
existing PF/PD program, Patient World Model and first-party clinical/scientific
scope; it does not create a replacement architecture or roadmap.

## 1. One oncology domain, context-specific clinical meaning

| Use in current product materials | Meaning |
|---|---|
| Patient Oncology | One oncology domain spanning supported species |
| Patient | The subject receiving care, with sourced species classification |
| Unified Patient Registry | One canonical identity owner; qualified external identity links |
| Patient-specific clinical workflows | Shared workflow infrastructure with applicable clinical and authority rules |
| Species-aware Clinical Intelligence | Rules and evidence constrained to qualified biological and clinical context |
| Patient Oncology Research | Research with explicit species, method and applicability boundaries |

This rule applies to navigation, architecture, new API/schema design and current
documentation. Retain accurate names of professions, institutions, source
standards and dated historical decisions. It does not mechanically rename
published API fields or migrations. Those require compatible changes and tests.

The Patient supports species code/system/version, breed where applicable,
biological characteristics, anatomy, clinical history, diagnoses, staging,
specimens, diagnostic results, treatments, outcomes and longitudinal episodes.
Unknown or disputed species remains explicit; never infer human from an absent
animal attribute. Species assertions and their corrections retain provenance.
A patient may have multiple cases/episodes. Caregiver, owner, guardian and
professional identities remain distinct actors with independently qualified
authority; a relationship label does not grant access or establish legal consent.

Clinical applicability is a versioned decision over species plus relevant age,
sex/reproductive state, anatomy, disease, specimen, assay/method, units, reference
system and intended use. Preserve the laboratory's reported interval separately
from any computed interpretation. A missing or unsupported profile blocks only
the affected interpretation/computation and explains why; authorized source
inspection remains possible. Comparative research declares source/target species,
transfer assumptions and evidence. It cannot silently supply clinical rules for
another species. No shared UI or database establishes biological equivalence.

## 2. Connect objects without collapsing their meaning

| Object | Identity and relationship requirements |
|---|---|
| Clinical event/activity | Existing owner ID; patient link; optional or multiple qualified case/episode links; lifecycle such as planned, performed, canceled or unknown |
| Original source/version | Existing source ID and exact version; qualified issuer/system/accession; original artifact or explicit unavailable-original state; receipt and integrity evidence |
| Reported finding | Exact source version and anchor; original wording/value/unit; subject, specimen and method context; result/missingness status |
| Derived result or interpretation | Typed output, input versions/anchors, producing actor or method/code/model version, parameters/QC, time and limitations |
| Relationship | Typed endpoints, source of the link, effective and recorded times, documented/computed/proposed/disputed status and correction lineage |
| Review/decision | Exact reviewed artifact and input snapshot, reviewer/role, scope, disposition, time and dissent; separate from execution of the resulting action |

An event is not a file. One biopsy can produce a collection record, pathology
report and molecular results; one report can describe multiple events. Several
organizations may transmit copies of one source. Preserve each custody receipt
without inventing repeated clinical procedures. Accession identifiers are qualified
by their issuer; similar names, dates or anatomy do not establish identity.

An unsigned upload or patient-reported recollection is still an identifiable,
attributed source. Label its provenance and uncertainty rather than fabricating
an original or hiding it. Unresolved patient matching remains in the existing
intake/reconciliation boundary; never attach material to a patient by guesswork.
Do not force an unrelated test into a cancer episode just to satisfy a case field.

“Source proof” has separate dimensions: retained bytes/integrity comparison;
origin asserted or authenticated; custody and receipt history; extraction
fidelity; clinical verification; and evidence applicability. A file hash does not
prove who authored it, when the test occurred, whether its statement is true, or
whether the chart is complete. Signatures and trusted time evidence, where
available and qualified, record what was actually verified and by which method.
Never compress these dimensions into one misleading verified badge.

## 3. Time has explicit meaning and uncertainty

| Time facet | Meaning and boundary |
|---|---|
| Occurred/effective | When an activity happened or a value concerns the patient; may be an interval or partial date |
| Collected/measured/processed | Domain-specific specimen, measurement or processing times, when supplied |
| Authored/issued | Source author's creation or issuer's release of that exact version; not proof of delivery to every clinician |
| Received and committed | Platform receipt/custody versus successful inclusion in canonical state; a failed upload is not available patient context |
| Reviewed/decided | Attributable human review or decision referencing its exact basis |
| Corrected/superseded | Issuer amendment time plus when the correction/link became known to the platform; previous versions remain addressable |

Only identifiers, platform-generated receipt/commit evidence and the appropriate
status fields are necessarily available at intake. Other dates may be unknown,
date-only, approximate, conflicting or not applicable. Preserve source wording,
precision, timezone/offset, authority and uncertainty; do not replace an unknown
clinical date with the upload date. Normalize comparable instants for sorting,
while retaining original representations. Use stable identity as a display tie
breaker without asserting causal order. Clock order alone does not prove causality.

The design needs both **clinical/effective time** and **system knowledge/version
time**, with the domain activity timestamps above. The chosen storage must also
version identity/specimen links, mappings and interpretations: filtering report
timestamps alone cannot reproduce a historical patient context.

## 4. Three explicit historical questions

| View | Required answer |
|---|---|
| Current reconstruction of past events | What the currently authorized, supported sources say about the selected clinical period, including later reports and corrections |
| Available in Open Intelligence then | Which canonical source versions and links were committed by the chosen platform cutoff; later arrivals must not leak backward |
| Basis of a documented review/decision | The exact evidence and rule/method versions attached to that recorded review, not everything theoretically available |

External issuer release can be shown as a separate sourced fact. A clinician's
knowledge, availability at another institution and receipt by this platform are
different questions. Do not label platform receipt history “everything the
clinician knew.” A later reprocessing of old originals is a new derivation, even
if its inputs were available earlier; show its run time and method version.

Illustrative fictional case: a specimen is collected January 10, a report issued
January 18, imported and committed January 20, amended January 25, and the
amendment committed January 26. Platform history on January 19 contains neither
report; January 22 includes version 1; January 26 after the commit includes
version 2. Current retrospective history can show both versions linked to the
January 10 specimen. No view invents evidence of clinician review.

Every snapshot records the selected temporal mode/cutoff, canonical revision or
watermark, included source/link revisions, projection/method version and omitted
or unresolved coverage where disclosure is permitted. Stable pagination uses the
same snapshot so concurrent imports cannot silently change page membership.
Repeatability is bounded by current authority and permitted retention: revocation
can prevent reopening historical content. It never restores an old grant.

## 5. One timeline across the workspace

Use one authorized patient context across Journey/Living Patient, Records, Labs,
Imaging, Pathology, Molecular, Treatment, Research and Copilot. Provide a patient
overview, episode/domain filters and focused comparison; do not require viewing
every event at once. One selection is shared as patient, optional case/episode,
clinical range, temporal mode, cutoff and snapshot identity. Existing session
and domain owners enforce it. A surface that cannot honor the chosen historical
mode must say so rather than silently presenting current data as historical.

The default clinical chronology groups encounters, tests, specimens, procedures,
actual treatments and observations. Orders, pending results, cancellations,
patient reports, research and AI outputs keep their distinct types and status.
High-volume monitoring may have declared summaries with links to exact source
ranges. Security access logs remain a separate permission-controlled audit view.
External publications enter a patient investigation through explicit evidence
links; publication date is not a clinical event for that patient.

Each event opens a source/evidence panel: original and anchor, author/issuer,
times and their uncertainty, current/previous versions, specimen/study links,
review status and any known limitations. Unavailable originals remain labelled;
original-file access may require authority beyond a derived summary. An imaging
report is distinct from its image series; a generic 3D atlas is not patient anatomy.
Spatial linkage requires qualified study/frame/registration evidence.

Amendments produce a visible difference and identify affected interpretations,
questions, runs and reviews through existing dependency/event owners. Invalidate
only affected derived work; preserve old reviewed outputs and dissent. A proposed
reassessment or next task does not become a new diagnosis, treatment or completed
action. Copilot receives the same authorized snapshot and must cite exact sources,
name unknowns and preserve the separation between observation and interpretation.

## 6. Build through existing owners

| Responsibility | Existing owner and workstream |
|---|---|
| Patient/species, qualified matching and representative authority | PF-01/PF-02; canonical patient registry and grants; GH-112, OI-013 |
| Originals, identifiers, source versions and custody | PF-03; existing source/document/image/laboratory owners; OI-005/OI-006 |
| Timeline and temporal snapshots | PF-04; Patient World Model projection and shared frontend session; OI-005/OI-006/OI-009 |
| Relationship evidence, clinical profiles and review | PF-05/PF-07 and existing question/evidence/review owners; OI-007/OI-008/OI-016 |
| Amendment delivery and reassessment | PF-06/PF-08; existing event, job and dependency owners; OI-009/OI-018 |
| Domain events and interoperable mappings | Existing PD owners and PF-09, with PF-10 controls; OI-005/OI-010/OI-013 |

The supplied “Universal Patient Event Registry” and “Patient Evidence Source
Registry” requirements describe shared contracts and discovery across these owners.
They do not authorize another canonical database, generic event blob store,
mandatory broker, graph database or new patient master. Clinical event history,
technical job events and security audit records remain distinct types.

Inspected baseline: main `f8ff4f4cea8dbfa1ee81cf33308e10af8aff29c4` contains the
reference timeline and existing H1 owners. Draft #618 at
`5ed973594f3957335d6ace298e5591336cdc04b5` adds bounded Journey receipt-time
reconstruction; #617 at `842c2cd70c78e454d0233d753806c2155bf78858` adds overlapping
Records membership/original access. #620 at
`8d1b4b48400e8708ff4552c1b58c46f3821caa2c` includes the earlier #618 head and Imaging
chronology. These are reusable inputs with separate acceptance, not evidence
that this full contract already exists. Preserve #618's later timestamp-ordering
fix when reconciling them. Refresh heads before changing any candidate.

Next construction: reconcile those history paths on one candidate and establish
one read-only patient timeline projection over canonical source, laboratory,
imaging and encounter owners. Prove the shared temporal selector and exact source
drill-through, then extend the same contract to specimen/pathology, molecular,
treatment and review owners. Add species/context through the existing patient
and terminology owners with explicit unknown handling, migration and recovery
tests. Do not relabel a partially connected screen as the complete timeline.

## 7. Acceptance and patient value

The next implementation must demonstrate these scenarios with independently
authored fictional data; this document does not claim they have been executed.

1. One patient across multiple cases and organizations; ambiguous matching is
   withheld, and corrected identity links preserve prior provenance.
2. Lab, imaging and encounter entries appear together and open their exact owner
   evidence; multiple imports of a report do not invent repeated tests.
3. Delayed and amended reports yield the expected three temporal views above;
   partial dates, offsets, equal instants and microsecond cutoffs remain exact.
4. A link or interpretation learned after the cutoff cannot leak into the earlier
   snapshot; a later extraction is visibly a later derivation.
5. Unrelated samples/methods remain separate; uncertain specimen/lesion links and
   conflicting sources remain visible rather than merged by similarity.
6. Unknown/disputed species or an inapplicable clinical profile prevents the
   affected computation, while permitted originals remain viewable. A correction
   marks dependent work for reassessment rather than silently reinterpreting it.
7. An order, cancellation, performed procedure, pending result and missing report
   retain different states. No record found never means no care occurred.
8. Current denial/revocation applies to history, originals, relationships, counts,
   search, exports and queued AI work; inaccessible existence is not leaked.
9. Concurrent imports, pagination, retries, process interruption and populated
   backup/restore preserve the selected snapshot and canonical version lineage.
10. Review and Copilot outputs retain their exact input/time/profile basis;
    selecting a historical date does not silently change current care actions.

Measure time to reconstruct a case, time/clicks to verify a finding against its
original, unsupported/misattributed links, wrong-time leakage, unresolved gaps,
amendment reassessment latency, reviewer correction burden and patient
comprehension. Define denominators, error severity, permissions and modality
coverage before evaluation. A source count is not completeness; missing coverage
is not proof that a test is required. These are intended benefits to test, not
claimed patient outcomes or clinical validation.

## Standards grounding

These are exchange concepts to map, not replacements for domain contracts or
claims of implemented interoperability. Use the repository's supported FHIR R4
boundary; adopting another release requires an explicit compatibility decision.

- [FHIR R4 Patient](https://hl7.org/fhir/R4/patient.html) covers an individual or animal receiving care.
- [R4 animal extension](https://hl7.org/fhir/R4/extension-patient-animal.html) describes species/breed; its absence does not assert human identity. Its mapping is not the entire internal species model.
- [R4 Observation definitions](https://hl7.org/fhir/R4/observation-definitions.html) distinguish clinically relevant effective time from release of a result version.
- [R4 Provenance](https://hl7.org/fhir/R4/provenance.html) describes entities, actors and activities producing or revising resource versions.
- [R4 AuditEvent](https://hl7.org/fhir/R4/auditevent.html) records security/audit activity; it is not the patient clinical timeline.

Standards checked 7 November 2026. No new third-party package, model, data asset,
runtime behavior, schema migration, clinical permission or release is introduced
by this requirements amendment.
