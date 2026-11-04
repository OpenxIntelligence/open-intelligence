# Working on Open Intelligence

## Read first

Read `README.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, and the relevant rows in `docs/EXECUTION_BACKLOG.csv`. Inspect the current repository before claiming that a capability, dependency, test, or decision already exists.

The repository contains a synthetic reference implementation and separately reviewed clinical/integration drafts. Implement bounded work against explicit acceptance criteria. Ordinary development and reversible fixes within the authorized task should proceed without repeated approval requests.

## Project identity and complementary research

- The current project name is **Open Intelligence**. Use the former name CEVax only when identifying historical source material; preserve original archival titles and provenance.
- Research dossiers, diagrams, vendor comparisons, Notion pages and Google Drive/Docs additions are **complementary inputs**, not a new architecture or replacement baseline merely because they are published.
- Map each useful finding to the existing case, source, evidence, investigation, review, authority or evaluation contract and its existing backlog item. Do not create a parallel canonical state, source ledger or competing roadmap.
- Keep research findings, extension proposals, accepted decisions, implemented behavior and validation evidence distinct. An architectural change requires an explicit scoped proposal and accepted review; a research document cannot approve a vendor, dependency, product pivot or clinical function.
- Preserve the full platform ambition. A proposed cohort, first customer, commercial model or initial workflow does not narrow the architecture without a separately recorded decision.

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
- The definitive founder mandate excludes Sid Sijbrandij's medical, genomic, laboratory, pathology and imaging data from acquisition, development, testing, evaluation, training and synthetic-fixture derivation. Public patient narratives may inform workflow discovery only. A public dataset or an archived script is not authorization to fetch or reuse patient data.
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

The bounded H1 implementation stack is accepted in canonical Notion Decisions 03: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, React, Vite and TypeScript. Next.js is excluded from new applications and modules. Preserve the existing stdlib/SQLite implementation as a runnable behavior oracle and the labelled fallback; do not create a competing patient, source or evidence authority during migration. New candidate work does not change the preserved main fallback until reviewed and approved for merge.

H1 has no vector-search requirement. Production deployment, tenancy, authority, source licensing and clinical qualification remain separate decisions. The current prototype's provider contract is documented in `docs/META_MODEL_API.md`; this does not authorize real-patient egress or establish a new live-provider verification. Research candidates do not become adopted dependencies merely by appearing in an atlas. See `docs/engineering/EXECUTION_AUDIT_2026-11-02.md` for the current evidence and remaining gates.

## Completion reports

Report what changed, why, what was verified, and what remains unproven. Separate software checks from clinical evidence. Never fabricate ingestion, model execution, citations, approvals, or deployment status.
