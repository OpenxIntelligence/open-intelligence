# Working on Open Intelligence

## Read first

Read `README.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, and the relevant rows in `docs/EXECUTION_BACKLOG.csv`. Inspect the current repository before claiming that a capability, dependency, test, or decision already exists.

The repository contains a synthetic implementation and a planning foundation. Implement bounded work against explicit acceptance criteria. Ordinary development and reversible fixes within the authorized task should proceed without repeated approval requests.

## Project identity and complementary research

- The current project name is **Open Intelligence**. Use the former name CEVax only when identifying historical source material; preserve original archival titles and provenance.
- **Founder direction, 7 November 2026:** **Patient Oncology** is the unified oncology product domain. **Patient** is the clinical entity; species is a sourced patient attribute that helps determine applicable clinical context. Use **Unified Patient Registry**, **Species-aware Clinical Intelligence**, and **Patient Oncology Research** in current product architecture and navigation. Do not split human and veterinary oncology into separate patient masters or products. Preserve accurate professional, regulatory, source and historical terminology where it describes actual context.
- Apply the [Patient Oncology and temporal history contract](docs/engineering/PATIENT_ONCOLOGY_TEMPORAL_CONTRACT.md) across existing owners. Unknown species must not default to human. Shared infrastructure does not establish interchangeable reference ranges, anatomy, staging, therapies, evidence or representative authority; clinical rules require versioned applicability and qualification.
- Research dossiers, diagrams, vendor comparisons, Notion pages and Google Drive/Docs additions are **complementary inputs**, not a new architecture or replacement baseline merely because they are published.
- Map each useful finding to the existing case, source, evidence, investigation, review, authority or evaluation contract and its existing backlog item. Do not create a parallel canonical state, source ledger or competing roadmap.
- Keep research findings, extension proposals, accepted decisions, implemented behavior and validation evidence distinct. An architectural change requires an explicit scoped proposal and accepted review; a research document cannot approve a vendor, dependency, product pivot or clinical function.
- Preserve the full platform ambition. A proposed cohort, first customer, commercial model or initial workflow does not narrow the architecture without a separately recorded decision.

## Product principles

- Preserve the full multi-vertical platform ambition — starting with longitudinal cancer care and biological research, spanning domains on a shared core, with each vertical keeping its own rules, toolsets, and evidence.
- Organize work around a patient case, durable questions, source evidence, review, and updates.
- Distinguish reported observations, extraction proposals, calculations, clinical interpretations, and research hypotheses.
- Preserve missing, negative, pending, indeterminate, and conflicting states separately.
- Keep source versions, specimen/assay context, relevant dates, and exact source anchors.
- The patient timeline is an authorized projection across domain-owned events and records. Distinguish the event, source version, reported finding, derivation and review; do not create a competing universal source/event ledger. Preserve occurrence/collection, issuer release, platform receipt/commit, review and amendment times, including unknown or partial dates.
- Historical reconstruction states its availability boundary. Platform receipt is not proof of external availability or human review. A hash establishes a byte-integrity comparison, not the clinical truth, authenticity or completeness of a record. Current permissions apply to historical retrieval and derived views.
- Receipt of an amendment changes freshness and review status. A new reviewed conclusion requires the appropriate scoped review; previous versions remain recoverable.
- Patient explanations must preserve the uncertainty and status of the underlying information.

## Repository boundaries

- **Founder clarification, 2 November 2026:** public accounts of Sid Sijbrandij's journey may inform abstract workflow and capability requirements only. Do not acquire, download, ingest, index, embed, analyze, redistribute, train on, or evaluate on his personal medical data. No manual flag, ethics-note exception, or public-data license overrides this project decision. Use independently authored synthetic patient data for all current engineering, development, testing, demonstrations and evaluation; do not create pseudonymized replicas of a real person's records.
- Study multiple journeys and care settings. Map each activity's goal, required information, enabling service, technical function, AI contribution and improvement opportunity to the existing source, evidence, investigation, review, authority and operational contracts. Public accessibility does not make an individual medical file a development input.
- Do not commit real patient data, credentials, private correspondence, or restricted clinical content. Use independently authored synthetic cases with explicit provenance.
- Before integrating a third-party component, document its exact version, intended use, license/terms, dependency and asset obligations, and unresolved issues. Hold integrations with unresolved permissions.
- Public repository visibility does not select a distribution license or establish clinical approval. Do not silently choose a project license, relax documented rights requirements, or describe an unvalidated function as clinically validated.
- Do not copy earlier bundles or vendor demonstrations wholesale. Import specific artifacts only after inspecting their contents, rights, and relevance.
- Keep outreach, real-data acquisition, external service commitments, clinical deployment, and changes to project licensing within their separately authorized scope.

## Engineering workflow

1. Inspect current state and applicable instructions; identify a bounded backlog item.
2. State the behavior to establish and the evidence needed to assess it.
3. Make focused, reversible changes. Preserve unrelated work and inspect the branch head before updating it.
4. Verify material behavior and failure modes. Do not add tests that merely repeat implementation details or claim a test passed without running it.
5. Update documentation and backlog status with actual results and remaining limitations.

Prefer deterministic software for authorization, source identity, validation, versioning, job state, and publication state. Model outputs are inspectable proposals governed by typed task contracts and allowed tools.

The complete first-party healthcare ecosystem remains the destination: EHR, oncology, LIS/LIMS, pathology, RIS/PACS, genomics, pharmacy, research, care operations and enterprise services. The patient-centered intelligence experience is the first implementation priority. An initial adapter to an existing hospital does not reduce that scope.

The bounded H1 engineering decision selects Python/FastAPI/PostgreSQL and React/Vite/TypeScript. **Next.js is excluded.** The connected fictional application is in `apps/api` and `apps/web`; use `docs/H1_DEMO.md` and the exact-revision acceptance receipts in [consolidation #481](https://github.com/OpenxIntelligence/open-intelligence/pull/481). The Python/SQLite prototype remains a separate reference implementation. This does not establish migration of the complete planned platform, production suitability or clinical release. Exact dependencies and those release claims still require their own evidence. See the [H1 decision register](https://docs.google.com/document/d/1YrORrdNxzT6MN-WuKVdk2vWVtVXVw9OSo0z5ARvMypg/edit).

## Completion reports

Report what changed, why, what was verified, and what remains unproven. Separate software checks from clinical evidence. Never fabricate ingestion, model execution, citations, approvals, or deployment status.
