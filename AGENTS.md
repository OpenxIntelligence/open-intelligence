# Working on Open Intelligence

## Read first

Read `README.md`, `docs/FIRST_PRINCIPLES_PLAN.md`, and the relevant rows in `docs/EXECUTION_BACKLOG.csv`. Inspect the current repository before claiming that a capability, dependency, test, or decision already exists.

The initial repository is a planning foundation. Implement bounded work against explicit acceptance criteria. Ordinary development and reversible fixes within the authorized task should proceed without repeated approval requests.

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
