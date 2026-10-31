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

Create independently authored fictional multi-institution oncology cases with conflicting pathology, distinct specimens, late amendments, a false patient match, missing molecular data, imaging reports without pixels, and a payer event without confirmation of administration. Define a per-source expected artifact inventory. Test each candidate adapter against **the same cases**, capturing:

- Source coverage by organization and artifact class; false-match and omission rate.
- Raw-byte preservation, original source link, timestamps, source version, authorization receipt.
- Duplicate handling and field-level transformation loss; preservation of conflict and unknown states.
- Amendment-driven invalidation only for affected derived work.
- Revocation/isolation/egress controls and absence of unauthorized external action.
- End-to-end reviewer effort, vendor costs, and exit/portability evidence.

No real records, live QHIN calls, commercial account creation, service agreements, patient outreach, or vendor commitment is authorized by this research document.

## Decision gate

Keep status **EVALUATE** until: exact vendor product and terms are confirmed; lawful data access and scope established; synthetic fidelity/isolation checks pass; clinical and privacy owners review intended use; and an ADR explicitly accepts a bounded adapter. Passing code tests is not clinical validation or release clearance.

## Source links / follow-up

- [Epic TEFCA IAS developer documentation](https://open.epic.com/Home/Interoperate/TEFCA/IAS)
- [TEFCA RCE](https://rce.sequoiaproject.org/)
- [InterSystems Health Gateway](https://www.intersystems.com/products/healthshare/health-gateway/)
- [InterSystems Health Connect](https://www.intersystems.com/products/healthshare/health-connect/)
- [HL7 FHIR ImagingStudy](https://hl7.org/fhir/R4/imagingstudy.html)
- [Open Intelligence Notion interoperability page](https://app.notion.com/p/40a3866f77ef8137a47cf95794e33ea7)
