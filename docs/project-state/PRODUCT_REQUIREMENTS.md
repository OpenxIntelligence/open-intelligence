# Product requirements — patient-centered execution crosswalk

> **Current reconciliation checkpoint:** #354 remains the document candidate at `7b16a9a900737f07adb03e35362922c886424e9b`. The [existing convergence gate](../engineering/H1_EVIDENCE_CONVERGENCE_MERGE_GATE.md) records this dependent composition with accepted main `c4798ae` and #374 ancestry. Earlier checkpoints below retain their original scope and do not establish this combination's hosted acceptance.

**Assessment date:** 3 November 2026 (America/New_York).  
**Purpose:** interpret current requirements against the existing [execution backlog](../EXECUTION_BACKLOG.csv), without creating a competing backlog or replacing the architecture.  
**Current candidate:** existing #354, based on `d9b81f08a97998e8f95d2a1cc7c43b4165e99862`, composes frozen #368/#369/#362/#367 corrections. **Local composition verified; exact combined hosted acceptance pending.** The [candidate record](../engineering/H1_CONNECTED_RIGHTS_CONVERGENCE.md#current-candidate--reviewed-document-convergence-in-354) identifies actual local checks and remaining review/API/browser/recovery gates. Main `c4798ae85004713593f83458abd2102be6729095` remains the reference; the H1 candidate is unmerged and undeployed.

**Historical assessment scope:** reference baseline `24519839aa8ac1ea3aff88a956349ba72798a72a`; connected H1 [#328](https://github.com/OpenxIntelligence/open-intelligence/pull/328) at `5a188d4e18e4d80bc2ba1d662c966abc3096301f`; the #330/#335/#339 composition and #355/#367 publication checkpoints remain in [PROJECT_STATE.md](PROJECT_STATE.md). Named historical passes below apply to those heads; they do not qualify the new combination. Older #276 acceptance text is preserved as historical evidence.

## Governing product direction

Open Intelligence organizes healthcare around the patient: the person's history, needs, goals, questions, care plan and next steps persist across professionals, organizations and delivery settings. Hospitals, laboratories, pharmacies and clinicians participate in that journey. They do not determine the product's organizing principle.

The explicit founder clarification on 3 November supersedes earlier institution-first positioning. The initial platform interoperates with existing systems; its long-term destination is a complete first-party standalone clinical platform. These stages must share identity, source custody, provenance, authority and operational contracts. Preserving the existing oncology and biomedical work is part of the mandate. [Founder precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f), [platform mandate](https://app.notion.com/p/cca3866f77ef822195188170742085af).

The primary product evaluation is whether a capability makes healthcare easier to access, understand, coordinate and continue while reducing avoidable patient effort and preserving clinical meaning. These are intended outcomes to measure; current software tests have not demonstrated patient benefit.

## Status vocabulary

Every status is scoped to the named behavior, branch and test environment.

| Required status | Interpretation |
|---|---|
| Fully implemented and tested | The bounded behavior exists and identified tests executed successfully at a specific commit; does not imply production or clinical qualification. |
| Implemented but not adequately tested | Code exists, but a material runtime, failure, migration or usability check is missing. |
| Partially implemented | Only part of the end-to-end requirement exists, or working pieces remain on separate branches. |
| Designed but not implemented | A concrete contract/design exists without corresponding working implementation in the assessed baseline. |
| Proposed but not approved | Research, alternatives or recommendations awaiting a scoped decision. |
| Missing | No implementation or adequate design was found in the inspected scope. |
| Broken | A reproducible failure exists on the relevant branch; identify its evidence rather than inferring failure from absence. |
| Blocked by external dependencies | The next step requires external access, rights, services, human authority or environment capability. |

## Requirements mapped to existing owners

| Patient need / requirement | Existing backlog | Current state and evidence boundary |
|---|---|---|
| Maintain one attributable patient identity across care settings | OI-005, OI-006, OI-013; GH-112 | **Partially implemented.** H1 has canonical PostgreSQL identity and qualified revocable case bindings. Production identity proofing and matching remain missing. [API contract](../../apps/api/README.md). |
| Obtain and organize records without repeatedly entering the same information | OI-006, OI-010; GH-323 | **Partially implemented.** #354 retains H1 record requests, structured-source import and bounded ordinary text/PDF originals with immutable manual selections. Requests do not contact an external institution. Manual selections remain separate from structured investigation provenance; the current combined acceptance is pending. |
| Preserve exact originals, versions, dates, specimen context and uncertainty | OI-006, OI-009 | **Fully implemented and tested for the bounded synthetic source contract** on established branch receipts; broader real-world formats remain partial. Source bytes/line anchors, amendments, wrong-case quarantine and source integrity are in the H1 owner. [Source integrity](../engineering/H1_SOURCE_PROJECTION_INTEGRITY_2026-11-02.md). |
| Ask a question about the patient's actual record | OI-007 | **Implemented and tested for the bounded #328 synthetic contract.** Authored questions persist against exact current source versions and quotations, with explicit save and retry recovery. Question text records user intent, not an invented clinical conclusion. |
| Understand what the record says and what is uncertain | OI-007, OI-010 | **Partially implemented.** Current source statements, uncertainty and patient/clinical reading layouts are connected in #328. Independent patient comprehension has not been measured; reading layout does not grant authority. |
| Prepare a faithful question/source brief or packet for the next discussion | OI-007, OI-010, OI-013 | **Implemented and tested for the bounded #328 synthetic contract.** Exact source/question packets and source-only briefs retain separate fresh export authority. Download is not transmission to a care team. [Brief contract](../engineering/H1_SOURCE_LINKED_BRIEF.md). |
| Keep questions, returns and source changes connected over time | OI-007, OI-009, OI-018 | **Implemented and tested for bounded behavior at the named historical heads.** Amendment retains anchors/history and requires reassessment. Current #354 composition adds #368's memory-only unsent Review reasons; shared document-denial clearing still needs combined browser acceptance. Clinical interpretation invalidation remains partial. [Return contract](../engineering/H1_SOURCE_QUESTION_REVIEW_RETURN.md). |
| Investigate a question against permitted scientific evidence | OI-008, OI-011 | **Partially implemented.** #328 composes canonical PostgreSQL fictional metadata, evidence originals, human-authored literal comparisons and immutable reports. Qualified biomedical retrieval, scientific/model appraisal and professional review remain unfinished. Bibliographic metadata alone is not claim support. [Evidence contract](../engineering/H1_AUTHORED_EVIDENCE_REPORTS.md). |
| Keep professional review distinct from a request to verify source information | OI-007, OI-012, OI-013 | **Partially implemented.** H1 supports nonterminal returned-for-verification receipts, not clinician signoff, verified professional identity or notification. |
| Coordinate tasks, owners, due dates and unresolved handoffs | OI-009, OI-010, OI-018 | **Partially implemented overall; bounded H1 task lifecycle is implemented.** The retained #328 lineage connects question-owned history, attention filters, amendment recheck and transition drafts. #369's strict timestamp checks are locally composed; malformed history must withhold actionable controls in combined acceptance. Recorded owner/completion is not external acceptance, notification or clinical action. |
| Carry images and modality-native context with the patient | OI-006, OI-013, OI-016 | **Partially implemented in separate drafts.** Original-image custody and archive-port owners are not included in this #354 document/evidence composition. No complete imaging viewer, private PACS isolation or clinical image analysis is established by these branches. |
| Access existing provider systems without replacement | OI-005, OI-006, OI-012 | **Blocked by external dependencies** for live providers. FHIR/HL7/document/DICOM adapters are designed or researched; production endpoints, permissions, identity and coverage are not proven. |
| Operate independently of another EHR | OI-005, OI-006, OI-013; full platform mandate | **Partially implemented foundation; most clinical operations designed but not implemented in H1.** Existing reference clinical/LIS modules must be preserved; encounters, orders, medications and full operational workflows require qualified integration. |
| Delegate to caregivers and professionals with revocable permissions | OI-012, OI-013 | **Designed but not implemented for production.** Fixture grants test action/patient separation; caregiver eligibility and actual consent are missing. |
| Use the interface with assistive technology and varied screen sizes | OI-007, OI-010 | **Partially implemented.** Bounded keyboard/responsive tests and accessibility CI exist in separate UI branches. WCAG 2.2 AA is the target; full conformance is not established. |
| Receive scheduling, messaging, medication, administrative and longitudinal support services | Full platform mandate; OI-001/OI-005 crosswalk before bounded execution | **Designed but not implemented in assessed H1.** No live appointment booking, pharmacy transaction, clinical messaging delivery or reimbursement integration is claimed. |

Do not use the number of tests, screens, PRs or catalog entries as a percentage of product completion.

## Complete founding MVP acceptance — distinct from the bounded H1 milestone

The [founding mandate](https://chatgpt.com/library?file_id=libfile_9c425a252d3081918f3c62c3e5e91d35&account_id=personal)
requires this 15-step independently authored synthetic scenario. The current
engineering checkpoint implements only the bounded behavior described here;
it does not silently redefine the full MVP or the later clinical release.

| Step | Required outcome | #354 local convergence; combined execution pending | Existing next gate |
|---|---|---|---|
| 1 | Create synthetic patient | Implemented canonical creation and case binding | OI-005/013: combined API/browser/recovery evidence |
| 2 | Upload representative medical records | Partial: structured reports plus bounded ordinary text/PDF originals and immutable manual selections in #354; general extraction is not established | OI-006/GH-323: combined document/recovery acceptance and explicit manual-provenance integration |
| 3 | Extract clinical information | General extraction not established by the annotated-text parser | OI-006/011: reuse existing parser/annotation owners, source-grounded proposals, abstention and correction |
| 4 | Create structured record | Partial source assertions; full typed clinical record/profile incomplete | OI-006: raw/normalized values, units, specimen/assay/episode context |
| 5 | Construct longitudinal timeline | Bounded chronology implemented | OI-009: partial dates, multiple episodes, as-known-at replay |
| 6 | Identify documented molecular/pathology findings | Source-authored findings represented; qualified extraction incomplete | OI-006/016: exact context and no inferred clinical meaning |
| 7 | Retrieve permitted biomedical evidence | Fictional catalog/upload path implemented; real source qualification pending | OI-004/008: one permitted live or frozen source and operation-specific rights |
| 8 | Investigate a scientific question | Saved question/manual comparison implemented; H1 scientific/model execution incomplete | OI-008/011: reuse bounded Composer, reproducible inputs and abstention |
| 9 | Compare support and contradiction | Human-authored literal comparisons implemented | OI-008/014: independent appraisal of source quality and applicability |
| 10 | Identify missing information | Bounded state/conflict projection | OI-006/009: clinical completeness and no-data controls |
| 11 | Generate source-linked report | Immutable fictional comparison reports and fresh status covers implemented | OI-008/010: final combined acceptance; biomedical synthesis remains separate |
| 12 | Present for human review | Inspection/nonterminal verification return implemented; professional sign-off incomplete | OI-007/012/013: qualified actor, exact artifact and scoped authority |
| 13 | Add new synthetic information | Bounded original/amendment flow implemented | OI-006/009: new specimen versus amendment and other-patient isolation |
| 14 | Reassess investigation | Stale/recheck and explicit new preparation implemented in bounded owners | OI-009/018: wider scientific/model/clinical dependency invalidation |
| 15 | Preserve prior report and explain change | Bounded immutable source/report history implemented | OI-009/010: combined browser/recovery and clinical change interpretation |

The [30-domain crosswalk](../research/PATIENT_JOURNEY_CAPABILITY_CROSSWALK_2026-11-03.md)
retains patient, caregiver, clinician and researcher workspaces, the clinical
spine and practical care/support domains. Extend existing OI-002/003/014
acceptance packets for guardian transitions, multimorbidity, hematologic disease,
limited access, disability/language needs, survivorship and palliative care.
Do not replace these journeys with new navigation placeholders or treat an
operator task transition as external completion.

## Historical #276 acceptance contract

Connect the existing patient question, source brief, exact-source packet and verification-return owners in one H1 candidate. The patient should be able to write a bounded question in ordinary language, attach it to an exact current statement, save it deliberately, inspect/download its faithful source context, and preserve that history when the source changes.

The required connected path is:

1. Open an authorized fictional patient and case, import original source bytes, and inspect the current statement.
2. Enter a question and prepare an exact source/version/line context without running a model or inventing clinical findings.
3. Save one durable question with stable retry semantics.
4. Prepare a source-only brief and exact-source packet under their existing independent authority.
5. Record a reasoned nonterminal verification return and recover an uncertain outcome with its original intent/key.
6. Amend the source, retain all old question/source/return history, refuse stale export and explicitly prepare a newly current question.

Preserve wrong-patient/case/organization denial; revocation and expiry; no successful receipt on serialization/audit/commit failure; cancellation and late-response discard; source-intake authority repairs; unchanged published migrations; and independently authorized read/export/return operations. A combined fresh test run is required. Parent-branch passes do not validate the new candidate.

The initial code audit also found that #276's review queue/return routes prepare typed DTOs without preparing the final JSON bytes before their last authority check. The #280 packet donor has the equivalent boundary gap. Selectively reuse the existing #278 response-preparation and same-case uncertain-return recovery repairs; its image implementation and migrations are outside this increment. Other source/question/preflight encoding boundaries remain tracked separately; this work does not claim to repair every API route.

This advances OI-006/007/009/010/013. OI-008's rights-qualified biomedical investigation and professional clinical review remain separate unfinished integrations.

## Architectural and product constraints

- Continue the accepted Python/FastAPI/PostgreSQL and React/Vite/TypeScript H1 baseline. Next.js is excluded from first-party implementation.
- Preserve the Python/SQLite reference as a behavior oracle, including meaningful source/evidence/review contracts.
- Use independently authored fictional patients for current engineering. Do not copy or pseudonymize real public case records.
- Keep raw observations, extraction proposals, calculations, interpretations and clinical decisions distinct.
- Preserve missing, unknown, negative, pending, indeterminate and conflicting states; never silently convert one into another.
- Reading preference is not authorization. Export, evidence rights, model processing, professional review and caregiver access have separate boundaries.
- Existing source and question ledgers remain authoritative; new projections and exports do not become competing stores.
- No new dependency is required for the selected integration. The technology catalog is not an installation list.
- Current workflow receipts establish authorized preparation or recorded operator intent, not external delivery, source authenticity or medical approval.

## Conflicts requiring durable reconciliation

[OI Task Board](https://app.notion.com/p/40b3866f77ef807eb47bc45698b90d44) still contains historical Next.js and “no patient-facing route” tasks. [TDR-025](https://app.notion.com/40c3866f77ef80b8a207ff87af0d03dd) proposes not building a LIS, contrary to the adopted standalone scope. Retain these as historical/proposed records and apply current founder/H1 decisions. Do not rebuild the product to make stale task text true.

First launch cohort, jurisdiction, professional review organization, commercial model, actual care-network access and clinical intended use remain open. They should be resolved through product and qualified review work, not inferred from synthetic fixtures or from a prospective institutional buyer.

## Evidence and related assessment

Primary project sources: [founder precedence](https://app.notion.com/p/40a3866f77ef8154bf15c7bb53138c9f), [decisions](https://app.notion.com/p/40a3866f77ef81e08a12fd4921e19629), [patient journey research](https://app.notion.com/p/40b3866f77ef816ea25fd3e8dbda6ca7), [engineering roadmap](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3), [UX evidence](https://app.notion.com/p/40a3866f77ef816881beea1863f14f4f). These are project evidence; linked CI claims need exact-head verification.

See [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md), [INTEGRATION_INVENTORY.md](INTEGRATION_INVENTORY.md) and [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md) for decisions, integration boundaries and remaining qualification.

