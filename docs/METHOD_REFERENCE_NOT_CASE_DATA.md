# Open Intelligence — Method reference, not case dataset

**Founder direction, 2026-11-02.** This note supplements, and does not replace, the established Open Intelligence architecture.

Open Intelligence studies *how* an exceptionally resourceful patient and their clinicians, scientists, and collaborators organized a longitudinal cancer investigation, coordinated experts, researched evidence and possibilities, and acted on reviewable findings. We aim to make comparable work available in one intelligent, patient-centered product, while improving accessibility, reliability, cost, speed, and continuity.

**No personal-case data reuse:** Do not download, ingest, analyze, benchmark, train on, or build demonstrations or fixtures using Sid Sijbrandij's records, imaging, molecular files or dataset catalogs. Previous conditional evaluation/ethics approval language is withdrawn. No manual opt-in exception. Publicly written accounts and interviews may inform a *workflow and capability study*; those accounts are not imported as medical records.

Use independently invented synthetic patient journeys for tests. Authorized future users may supply their own information subject to separate privacy, consent, security and clinical release requirements.

The product loop: gather records -> reconcile patient state and provenance -> identify gaps -> investigate permitted research -> develop hypotheses and options -> invite expert review -> coordinate authorized next actions -> observe new evidence -> reassess. The platform must capture the artifacts and decisions, not merely present conversations.

Research multiple other journeys and ordinary-resource constraints before treating any one patient's experience as universal. Do not promise to reproduce one patient's treatment decisions or outcomes.

Historical exploratory data-acquisition code is being retired; the synthetic-only CI workflows are maintained for regression. Audit past workflows and artifacts separately.

## Workflow-to-product traceability — 3 November 2026 increment

This is a bounded extension of the existing method study, not a completed
patient-journey atlas. The [President's Cancer Panel navigation report](https://prescancerpanel.cancer.gov/reports-meetings/enhancing-patient-navigation-2024/action-to-improve-equity/technology-support-equitable-outcomes)
describes repeated handoffs, fragmented information, financial and practical
barriers, and the need for care coordination. The [Blood Cancer United Clinical
Trial Support Center](https://bloodcancerunited.org/resources/patients/clinical-trial-support-center-ctsc)
provides a complementary hematologic-cancer navigation reference. These are
workflow/service sources, not patient datasets or causal evidence that a
particular treatment succeeds. The public osteosarc.com landing page remains a
method reference only; its record/data links were not acquired for this work.

The following product mappings are engineering inferences from those workflows
and the founder's requirements. Current permissions are synthetic operator
grants, not qualified real-patient consent or professional authority.

| Activity | Information required | Domain entities | Platform functionality | User experience | AI/tool capability | Permissions | Verification method | Actual implementation status |
|---|---|---|---|---|---|---|---|---|
| Assemble records for a handoff | Correct patient; origin; exact record version; dates | Patient; case binding; source version; assertion | Preserve and inspect original bytes and normalized source assertions | Records and source-linked Journey | Deterministic authored-format parser; no OCR/model claim | Patient, case and source grants | Hash/byte preservation; wrong-patient rejection; actual API/PG/browser and restore tests | Existing selected H1 baseline; draft/unmerged; ordinary medical uploads remain unsupported |
| Turn a missing or disputed fact into a question | Source line and version; current snapshot; question author | Source question; preflight; access receipt | Save an exact question; inspect quotation; return for source verification | Existing Investigations and Review | Deterministic source context and nonterminal review return | Separate question/source/review grants | Current source hash; independent final authority; amendment and retry tests | Existing #287/#293 integration; no clinical approval |
| Identify candidate research material | Explicit query; source identifier/version; metadata rights | Evidence record; rights decision; question citation | Search permitted metadata and save a source-linked citation | Progressive panel beside the saved question | Bounded lexical search and citation identity check; no evidence appraisal/model | `evidence_read`; independent `evidence_link`; patient/question/source grants | Exact version/hash; revoked metadata redaction; scoped access and duplicate-key tests | #298 integration candidate; independently fictional catalog only; live biomedical connector remains open |
| Keep a practical next step owned | Question/source anchor; owner; revisit basis; operational status | Follow-through task; immutable origin; status events | Assign, acknowledge, complete or defer bounded non-treatment work | Existing question tasks and work history | Domain state machine; no external contact | Independent create/read/update grants | Real lifecycle and exact retry; source amendment retains history; actual restore | Existing #293; draft/unmerged; no referral, prescription or external scheduling effect |
| Reassess after a correction or changed access | Original and amended versions; dependency; current permission | Source history; question freshness; evidence link; rights history | Keep originals; flag stale questions; withhold revoked metadata on fresh access | Source-change notice and inspectable historical citation | Deterministic dependency/freshness and authorization checks | Current source and evidence access | Amendment, revocation, delayed-response and backup/restore scenarios | Source/task behavior in baseline; evidence behavior in #298 acceptance candidate |
| Navigate trials and practical access barriers | Clinician input; protocol/site state; patient goals; travel, financial and support constraints | Future trial applicability; referral; navigation request; goal | Coordinate informed inquiry and practical support without asserting eligibility | To be designed with existing patient/task context | Permitted registry retrieval plus human verification; no autonomous enrollment | Future purpose-bound sharing and separately authorized outreach | Recruitment/site and criterion verification; usability with limited-resource scenarios | Research only; the metadata or task slice does not implement this service |

Coverage still needed: representative common solid cancers, pediatric and rare
cancers, refractory disease, unsuccessful investigations, survivorship,
palliative care, language/disability access, and resource-limited settings.
Independent authored oncology fixtures and qualified professional review are
required before claiming that these engineering examples cover those journeys.
