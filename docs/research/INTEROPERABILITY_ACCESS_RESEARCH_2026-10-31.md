# Open Intelligence — interoperability and patient-access research addendum

**Date:** 2026-10-31  
**Status:** Supporting research / architecture extension candidate; **not** an adopted architecture, vendor decision, implemented integration, legal determination, or clinical release.  
**Existing owners:** OI-005 (interoperability boundary), OI-006 (source fidelity), OI-012 (authorization), OI-013 (isolation), OI-014 (evaluation).  
**Project:** Open Intelligence. The former project name is historical only.

## Why this exists

Recent inquiry into InterSystems, national exchange, Epic, and patient-directed data access raises testable questions for the **existing** Open Intelligence source/evidence/investigation architecture. Do not create a second canonical state, source ledger, or authority plane. Follow [AGENTS.md](../../AGENTS.md), [the first-principles plan](../FIRST_PRINCIPLES_PLAN.md), and [the implementation status](../IMPLEMENTATION_STATUS.md).

## Distinguish five boundaries

| Boundary | Responsibility | Not implied |
| --- | --- | --- |
| Patient-authorized acquisition | Identity, authorization, permitted purpose, organization discovery, access contracts | Universal access to every EHR or artifact |
| Exchange transport | FHIR/SMART, C-CDA, HL7, network routing | Source fidelity or permission to use data for every purpose |
| Integration and transformation | Mapping, normalization, deduplication, monitoring | Lossless conversion or clinically authoritative interpretation |
| Open Intelligence evidence | Immutable original, subject/source/version anchors, conflicts, unknowns, amendments | That a normalized projection replaces the source |
| Clinical intelligence/action | Governed review, questions, evidence and authorized external workflows | Automatic clinical recommendation, EHR writeback or clinical approval |

An ordinary API gateway (routing/policy) is **not** the same thing as a health-information-network access product. InterSystems API Manager, IRIS for Health / Health Connect, Unified Care Record, and Health Gateway occupy different roles.

## Candidate paths; no vendor selected

- **TEFCA Individual Access Services (IAS):** evaluate an eligible patient-facing app's relationship with a QHIN/IAS provider; patient matching, identity proofing, SMART authorization, participation, scope, and completeness must be measured. See [RCE](https://rce.sequoiaproject.org/) and [Epic IAS](https://open.epic.com/Home/Interoperate/TEFCA/IAS).
- **InterSystems Health Gateway:** network-access aggregation advertised for participating healthcare-network workflows; independently verify applicability and commercial terms for a patient-facing IAS application. See [Health Gateway](https://www.intersystems.com/products/healthshare/health-gateway/).
- **InterSystems Health Connect / IRIS for Health / UCR:** evaluate separately for integration, FHIR exchange, normalization, identity, and provenance. See [Health Connect](https://www.intersystems.com/products/healthshare/health-connect/).
- **Health Gorilla / b.well:** candidate patient-access paths, subject to demonstrations and rights review. See [Health Gorilla IAS](https://www.healthgorilla.com/home/use-cases/ias).
- **Direct SMART/FHIR and patient-directed records requests:** useful comparison/fallback; institution-specific registration, supported scopes, and specialty artifacts vary.
- **Payer access and specialized laboratories:** separate planes; do not assume national EHR exchange includes native DICOM, whole-slide images, raw sequencing, research assays, or every claims event.

## Key adversarial questions

1. Does the vendor support **patient-directed IAS**, provider Treatment purpose, or both? What contractual role would Open Intelligence have?
2. Which organizations are discoverable and which data actually return, for a properly consented patient?
3. What are the raw artifacts, source identifiers, specimen/assay links, effective/recorded/retrieved times, and amendment semantics?
4. Which mapping steps are lossy? Preserve input/output and field-level transformation receipts; test cardinality, negative/unknown, conflicts, duplicate data, and source corrections.
5. What is the complete authorization and revocation path? What PHI leaves each boundary and under which agreements?
6. Are retrieval and EHR writeback separate commercial, technical and clinical pathways?
7. Can we switch network/integration vendors without changing the source/evidence/investigation contracts?
8. What are the pricing, rate, latency, operational, liability, and audit obligations? Do not infer them from marketing claims.

## Proposed synthetic evaluation (no external patient access authorized)

Create independently authored fictional multi-institution oncology cases with conflicting pathology, distinct specimens, late amendments, a false patient match, missing molecular data, imaging reports without pixels, and a payer event without confirmation of administration. Define a per-source expected artifact inventory. Test local adapters or recorded synthetic responses against **the same cases**, capturing:

- Fixture-level artifact completeness, false attachment, omission and duplicate behavior against the authored expected inventory.
- Raw-byte preservation, original source link, timestamps, source version, authorization receipt.
- Field-level transformation loss; preservation of conflict and unknown states.
- Amendment-driven invalidation only for affected derived work.
- Simulated revocation/isolation/egress controls and absence of unauthorized external action.
- Reproducible local processing effort and export/reimport fidelity; identify which costs and review burdens remain estimates.

**Synthetic fixtures cannot establish actual network discovery, patient matching performance, population record completeness, vendor pricing, or clinical usefulness.** A fictional patient must not be submitted to a live clinical exchange as though it were a real authorized individual.

| Evaluation tier | Permitted evidence claim | Not established |
| --- | --- | --- |
| Local synthetic fixtures | Behavior of the adapter and existing source/evidence/authority contracts for specified test cases | Real institutional coverage, live identity proofing or representative clinical error rates |
| Separately authorized vendor sandbox | Compatibility with the named sandbox version, documented payloads and supported test identities | Production access rights, nationwide availability or real-patient completeness |
| Separately authorized real-data evaluation | Observed results for the specified population, sites, dates, artifact classes and permitted protocol | Universal coverage, efficacy or clinical release approval |

For any later real-data evaluation, define the reference inventory, retrieval window, denominator, adjudication method and source-specific missingness before comparison. Report unknown source availability separately from retrieval failure and data not exposed by the source. Compare identical evaluation scopes rather than unqualified vendor totals.

No real records, live QHIN calls, commercial account creation, service agreements, patient outreach, or vendor commitment is authorized by this research document.

## Route the broader research into existing work

The earlier clinical, scientific, regulatory and commercial dossier is complementary research, **not a successor architecture or a newly accepted roadmap**. The following crosswalk routes questions to existing work packages; it neither creates new package identifiers nor changes their order, owners, dependencies or completion status.

| Complementary research | Existing work | Bounded evidence to add |
| --- | --- | --- |
| Intended use, patient/clinician authority and privacy roles | OI-001, OI-012, OI-013 | Function-level intended-use and authority matrix; dated specialist review; consumer/provider access distinction |
| National access, payer data and direct laboratory interfaces | OI-002, OI-005, OI-006; issue #17 | Artifact/access matrix, exact product and purpose, original-source fidelity, unknowns and exit path |
| Provenance, chronology, specimen context and projections | OI-003, OI-006, OI-009 | Loss receipts, wrong-patient/specimen controls, as-known-at replay, conflict retention and amendment tests within the current model |
| Knowledge, terminology, model and service rights | OI-004, OI-008, OI-018 | Use-specific permissions for access, storage, display, redistribution, retrieval, embeddings, training and evaluation; unresolved rights remain blocked |
| Imaging, pathology, molecular and other biological assets | OI-016 | Separate registration, report review, native-artifact access and qualified analysis; rights, custody, QC and exact versions |
| Trials, investigational possibilities and authorized follow-through | OI-007, OI-008, OI-012, OI-017 | Criterion-level evidence/unknowns, site confirmation requirements and scoped human-owned tasks; no implied eligibility, availability or clinical order |
| Model assistance and independent clinical evaluation | OI-011, OI-014, OI-018 | Held-out task comparisons, source-faithful citations, abstention, consequential errors, reviewer correction burden and version-change controls |
| Competitors, customers, partners and economics | OI-002, OI-015 | Compare measured workflows, coverage and fully loaded effort; treat positioning, cohort, buyer, pricing and partnerships as hypotheses |

Research concerning individualized or hypothetically buildable therapies remains a separately qualified research question under the existing specialist-modality and authority boundaries. This crosswalk does not approve a therapy-development program or remove that long-term ambition.

For each addition record: research question; existing module/backlog link; source and version; date actually checked; claim status (source-stated, independently checked, hypothesis or unresolved); rights status; falsification test; evidence still needed; and any scoped ADR required. Do not label an older source as newly verified just because it was copied into a document dated today.

## Decision gate

Keep status **EVALUATE** until: exact vendor product and terms are confirmed; lawful data access and scope established; synthetic fidelity/isolation checks pass; clinical and privacy owners review intended use; and an ADR explicitly accepts a bounded adapter. Passing code tests is not clinical validation or release clearance. Selection and deployment decisions must state which evaluation tier supplied their evidence and which real-world claims remain untested.

## Source links / follow-up

These are carried-forward source pointers, not a claim that every external document or commercial term was freshly reverified in this editorial update. Check the applicable published version and effective date before relying on a legal, regulatory, vendor-access or licensing claim.

- [Epic TEFCA IAS developer documentation](https://open.epic.com/Home/Interoperate/TEFCA/IAS)
- [TEFCA RCE](https://rce.sequoiaproject.org/)
- [InterSystems Health Gateway](https://www.intersystems.com/products/healthshare/health-gateway/)
- [InterSystems Health Connect](https://www.intersystems.com/products/healthshare/health-connect/)
- [HL7 FHIR ImagingStudy](https://hl7.org/fhir/R4/imagingstudy.html)
- [Open Intelligence Notion interoperability page](https://app.notion.com/p/40a3866f77ef8137a47cf95794e33ea7)
- [Complementary historical research and source crosswalk](https://app.notion.com/p/40a3866f77ef81e0a9e9c1a96773f8b9)
- [Existing execution backlog](../EXECUTION_BACKLOG.csv)
- [Existing bounded validation issue #17](https://github.com/OpenxIntelligence/open-intelligence/issues/17)
