# Working on Open Intelligence

## Read first

Read `README.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, and the relevant rows in `docs/EXECUTION_BACKLOG.csv`. Inspect the current repository before claiming that a capability, dependency, test, or decision already exists.

The repository contains planning artifacts and working synthetic application slices; inspect the relevant branch before claiming integrated or deployed capability. Implement bounded work against explicit acceptance criteria. Ordinary development and reversible fixes within the authorized task should proceed without repeated approval requests.

## Founding mandate: platform first, useful MVP first

- Build a new, integrated cancer-care platform for many patients, caregivers and authorized professionals. The long-term scope includes first-party EHR, oncology, laboratory, pathology, imaging, genomics, scientific investigation, care coordination and patient support. A small initial workflow does not reduce that ambition.
- First deliver a functioning end-to-end MVP: independently synthetic patient information → structured longitudinal record → permitted biomedical evidence → source-supported investigation → report → human review → updated understanding. Preserve one canonical patient/case identity, source ledger, evidence contract and review history.
- Advanced models, image analysis, predictive algorithms and custom scientific pipelines are later capabilities, justified by a measured problem, baseline, validation method and expected benefit. They are not prerequisites for a useful integrated MVP. Existing suitable models and deterministic software are acceptable starting tools.
- Sid Sijbrandij and other public patient narratives may inform research into methods, access barriers and workflows. Never acquire or use Sid's medical records, genomic data, pathology, imaging or other patient data for development, training, evaluation, testing, synthetic derivation, biological reconstruction or reproduction of treatment decisions. Public availability does not override this boundary. Use independently authored synthetic patients and specimens.
- Research diverse journeys, including limited access, unsuccessful treatment, caregiver burden, pediatric care, survivorship and end-of-life needs. A published narrative is product-discovery evidence, not clinical efficacy evidence or a test fixture.
- Extend the canonical Notion/Drive artifacts and existing GitHub work. Separate established decisions, recommendations, experiments, unresolved questions, founder approvals and clinical/legal/institutional approvals. Do not restart architecture selection or create duplicate implementations without a scoped justification.
- Next.js is excluded from new product development.

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

The existing Python/SQLite/vanilla-JavaScript synthetic application remains the behavioral reference and fallback. The canonical decision register accepts Python 3.12/FastAPI/Pydantic 2/SQLAlchemy 2/Alembic/PostgreSQL 16 and React/Vite/TypeScript as the H1 working target; migration is not complete. This bounded engineering direction does not approve production tenancy, hosting, clinical use or every dependency. Preserve source contracts and tested behavior during migration, and document scoped adoption decisions rather than restarting stack selection. See the existing [decision register](https://www.notion.so/40a3866f77ef81e08a12fd4921e19629).

## Completion reports

Report what changed, why, what was verified, and what remains unproven. Separate software checks from clinical evidence. Never fabricate ingestion, model execution, citations, approvals, or deployment status.
