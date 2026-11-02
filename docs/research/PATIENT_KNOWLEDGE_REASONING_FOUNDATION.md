# Open Intelligence — patient + biomedical knowledge context

**Status:** First-party engineering foundation and research contract, 2 November 2026. Product objective: **complete longitudinal patient data + governed AI/scientific interpretation against evidence, including supporting and opposing publications and approved clinical guidelines.** This is the central product intelligence workflow, not a separate research application, EHR replacement or a closed clinical recommendation engine.

## What the current code implements

`src/open_intelligence/knowledge_context.py` builds a typed patient-question context from the actual `CaseStore.state(case_id)` snapshot, not another patient source store. It preserves current source IDs and versions, source SHA-256, original document and source line, issued/event dates, and explicit reported/negative/pending/indeterminate statuses. A source amendment changes the current assertion IDs; links against stale versions are rejected.

**Trusted-state boundary:** `compile_context` is an offline projection over a caller-supplied snapshot. Its case-label and source-reference checks do not independently establish row ownership or freshness against the database: a caller could relabel or combine snapshot rows, or retain an old snapshot after an amendment. Callers must provide a fresh, unchanged `CaseStore.state(case_id)` result from the canonical ledger. Before any external integration, bind that read to the separately enforced actor, case and purpose checks; never accept arbitrary request JSON as an authorized case snapshot. The helper is not an authentication, case-authorization or freshness authority, and its output does not authorize model transmission.

`knowledge_sources` captures a versioned source ID, family, public identifier, source date, rights state, rights receipt and existing `rights.py` permissions. It **does not fetch guideline/PDF/article content** or assert legal rights. Superseded/revoked sources return identifiers but redact content. Content lacking an explicit model/AI-use permission cannot be admitted to a proposed AI context. Metadata and full-text use are separate permissions. Without cleared evidence text, no clinical interpretation or matching is attempted; the output explicitly marks evidence missing.

Human-authored comparison proposals connect an exact current patient assertion ID to an exact rights-qualified knowledge source, separately label supports/contradicts/context/unknown and applicability, and remain **unreviewed proposals**. The function neither infers that a publication supports patient treatment nor authorizes model/PHI transmission.

`tests/test_knowledge_context.py` uses real synthetic CaseStore imports and verifies case isolation, correct source hashes, guideline holds, no default rights, revoked/superseded redaction, explicit fictional opposing evidence, amendment invalidation and denial of metadata-only inferred appraisal.

## Confirmed evidence and rights research

- **NCCN:** source content is proprietary and requires specific written permission for commercial and AI use. Official NCCN AI-content licensing has precedent (Nov 5, 2025 NCCN/OpenEvidence agreement; https://doi.org/10.6004/jnccn.2026.0005). No license held by Open Intelligence is established. Official NCCN Developer API, official NCCN MCP, public JSON/FHIR/XML endpoints or named `/api/Guideline/`, `/api/OrderTemplates/`, `/api/Biomarker/`, `/api/Radiation/` routes are NOT verified here. Treat these user-pasted claims as unverified; never build to assumed endpoints. Publisher permissions/contract needed.
- **ASCO:** public Terms of Use explicitly restrict AI ingestion of site/services/content without separate authorization (https://www.asco.org/about-asco/legal/terms-use). Official ASCO Guidelines Assistant is a member product, not redistribution rights or an integration API. Licensing contact via publisher.
- **ESMO:** guideline publications carry all-rights-reserved reproduction restrictions; exact product/AI/API use must be negotiated. Do not scrape.
- **CIViC:** openly documented CC0 data and API, including released evidence statements and variant interpretations (https://civicdb.org/releases/licensing); scientific and clinical use still needs qualification.
- **PubMed:** E-utilities provides citation records; full-text publisher rights are separate (https://pubmed.ncbi.nlm.nih.gov/help/).
- **PMC Open Access Subset:** approved automated acquisition services only; per-article CC license varies (https://pmc.ncbi.nlm.nih.gov/tools/openftlist/); *free to read* is not necessarily freely trainable/redistributable.
- **NCI PDQ:** medical evidence information summaries; not equivalent to NCCN/ASCO guideline decisions. Reuse text requires correct attribution and trademark/image rules (https://www.cancer.gov/policies/copyright-reuse).
- **ClinicalTrials.gov / FDA labels:** official data are candidate evidence sources under their current service/license policies. Study-level status cannot establish individual trial eligibility, and a drug label cannot establish a patient-specific treatment choice.

## Full product requirements (not implemented by this PR)

1. Patient creation with verified identity, consent/authority, and persistent complete history; structured FHIR/HL7/mCODE, DICOM, pathology WSI, laboratory, genomic FASTQ/BAM/VCF/quantification, medications, symptoms, goals, documents, source and specimen lineage.
2. Multimodal ingestion and normalization: original asset custody, hash, patient match, clinical terminology and units, extraction provenance, quality/uncertainty, temporal validity, review. No automatic data promotion from AI output to confirmed clinical fact.
3. Longitudinal Patient World Model separate from source owners, with as-known-at snapshots, contradictions, hypothesis graph, unanswered questions, evidence-to-claim dependencies and invalidation on amendments.
4. Biomedical World Model for literature, guidelines, variant annotations, clinical trials, regulatory labels, genes/pathways/targets, structured evidence strength, populations, interventions/outcomes and limitations.
5. Licensed adapter per source family (NCCN/ASCO/ESMO through contract, others under verified source-specific rights): versioning, permission receipt, content/ML use distinction, cache/redistribution rules, update/revocation, citation and correction.
6. Question-driven retrieval and **counterevidence search**: patient context filters by disease, stage, line of therapy, histology, specimen/assay, variant genome build/transcript, demographics/organ function/goals, jurisdiction and timing; separate missing/uncomparable input from disconfirming evidence.
7. Governed agent and scientific tool workflows produce citation-verified *proposals* with explicit support/opposition, effect sizes where justified, evidence maturity, applicability, uncertainty, disagreement and clinician review status. No fabricated applicability or inference from abstract/DOI alone.
8. UI: one patient overview with longitudinal timeline, record explorer, open questions, evidence map, research runs, guideline/literature comparison, read-only exact-source inspector, rights/source version labels, human review queue and outcome follow-up. High value, low noise.
9. Operational safety: isolated PHI processing, real user/organizational roles, audit and consent, regulatory intended-use review, medication/safety escalation; prohibited unauthorized medical action.
10. Engineering: persistent authorized knowledge/content store and search indexes, provider/contract monitoring, source-rights audit, runtime model tool gating, provenance APIs, full integration tests, security evaluation, deployment/backup/restore and scientific/clinical validation.

## Next engineering acceptance

A real permitted CIViC evidence item (metadata + approved content) must be acquired through its official API with rights and version receipts, mapped into the existing case question and evidence store, tested for source anchoring, contradictory evidence, revocation and independent clinician review. A publication item must verify actual content rights; an unlicensed NCCN/ASCO/ESMO item must remain citation/reference-only and must never enter prompts. Later, after licensed publisher access, compare source-guideline versions against patient facts and flag missing diagnostics or divergences for qualified review.

**No Next.js. OI-17 exact release/asset/model/terminology rights gates apply.** The current code is a deterministic source-context preflight, not the complete platform, medical reasoning, a production permissions authority or clinical validation.
