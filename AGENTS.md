# Working on Open Intelligence

## Read first

Read `README.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, and the relevant rows in `docs/EXECUTION_BACKLOG.csv`. Inspect the current repository before claiming that a capability, dependency, test, or decision already exists.

The initial repository is a planning foundation. Implement bounded work against explicit acceptance criteria. Ordinary development and reversible fixes within the authorized task should proceed without repeated approval requests.

## Project identity and complementary research

- The current project name is **Open Intelligence**. Use the former name CEVax only when identifying historical source material; preserve original archival titles and provenance.
- Research dossiers, diagrams, vendor comparisons, Notion pages and Google Drive/Docs additions are **complementary inputs**, not a new architecture or replacement baseline merely because they are published.
- Map each useful finding to the existing case, source, evidence, investigation, review, authority or evaluation contract and its existing backlog item. Do not create a parallel canonical state, source ledger or competing roadmap.
- Keep research findings, extension proposals, accepted decisions, implemented behavior and validation evidence distinct. An architectural change requires an explicit scoped proposal and accepted review; a research document cannot approve a vendor, dependency, product pivot or clinical function.
- Preserve the full platform ambition. A proposed cohort, first customer, commercial model or initial workflow does not narrow the architecture without a separately recorded decision.

## Founder directive — full first-party healthcare ecosystem (accepted 2 November 2026)

- The product scope is the **complete first-party healthcare ecosystem**: EHR/EMR, oncology, LIS/LIMS, pathology, RIS/PACS, genomics, medication and treatment, patient/professional, research, AI/ML/agents, enterprise operations and shared clinical/data/security infrastructure. Implementing a bounded vertical slice never narrows that scope.
- **NO NEXT.JS.** Next.js has been explicitly rejected for new Open Intelligence frontend, backend and first-party product code. Old hackathon Next.js ADRs/BOMs are historical evidence and have no implementation authority. Do not add its packages, scaffolders or project files. This does not preselect an alternative stack.
- Evaluate every technology against the commercial freedom policy: actual corresponding source, independently forkable/modifiable/self-hostable commercial use, redistribution, patents/trademarks, transitive dependencies, data, fonts, weights, terminology and NOTICE. Unknown rights = HOLD; no AI-issued procurement clearance.
- Domain components must be first-party owned in scope, with named operational data owners, versioned API and event contracts, patient/specimen/study identity, consent, source provenance, temporal and uncertainty semantics, idempotent recovery and human clinical authority. Existing code can be reused or replaced only through a verified, reversible decision.
- Read the superseding decision and reference journey in docs/FIRST_PRINCIPLES_PLAN.md; follow relevant existing backlog/PR ownership. Do not create a parallel canonical patient ledger or architecture, and do not claim clinical validation from synthetic demonstrations.

## Product principles

- Preserve the full longitudinal oncology and biological research ambition.
- Organize work around a patient case, durable questions, source evidence, review, and updates.
- Distinguish reported observations, extraction proposals, calculations, clinical interpretations, and research hypotheses.
- Preserve missing, negative, pending, indeterminate, and conflicting states separately.
- Keep source versions, specimen/assay context, relevant dates, and exact source anchors.
- Receipt of an amendment changes freshness and review status. A new reviewed conclusion requires the appropriate scoped review; previous versions remain recoverable.
- Patient explanations must preserve the uncertainty and status of the underlying information.

## Repository boundaries

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

The backend, model provider, and detailed application stack remain undecided. Select them using the workflow requirements and a bounded comparison, rather than treating an earlier candidate as an approved dependency.

## Completion reports

Report what changed, why, what was verified, and what remains unproven. Separate software checks from clinical evidence. Never fabricate ingestion, model execution, citations, approvals, or deployment status.
