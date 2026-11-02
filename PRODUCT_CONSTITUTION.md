# Open Intelligence — Product Constitution
Status: proposed engineering governance, submitted for founder review on 2026-11-02. This does not itself amend accepted architecture, authorize clinical practice, or configure GitHub permissions.

## Mission and product identity
Open Intelligence is a distinct, full first-party AI-native healthcare ecosystem, beginning with oncology and spanning longitudinal patient/case records, EHR/EMR, laboratory/LIS, pathology, imaging, genomics, therapies, patient/professional experiences, scientific investigation and enterprise operations. The current Python/SQLite and browser demonstration is synthetic-only reference software, not the final platform or a clinically validated product. The founder-approved November 2 scope and exclusion of Next.js for new first-party work are recorded in the existing Notion architecture register; draft PR #49 is the related GitHub implementation proposal. Do not treat this document as a substitute for reviewing or reconciling PR #49.

Preserve existing case/source/assertion/evidence/investigation/authority contracts. Preserve original record versions, temporal history, provenance, patient goals, uncertainty and alternative hypotheses. New research supplements—not silently replaces—accepted decisions. Do not silently create another canonical patient store.

## Authority boundaries
- Human founder/product owner: final approval for product scope, core UX changes, architecture, platform licensing, major technology choices, releases and material commercial commitments.
- Engineering coordinator: assigns bounded engineering work, sequences dependencies, identifies collisions, reviews evidence and prepares decisions. Has no independent power to waive red gates or self-approve red changes.
- Specialist coding agents: execute tasks only within assigned scope and workspace, raise change requests, and deliver tests and reviewable PRs. Instructions are not permission enforcement.
- Qualified clinical and domain reviewers: own clinical interpretation/adjudication where a workflow legitimately requires it. Founder approval is NOT a substitute for clinician authorization, patient consent, regulatory obligations or independent validation.
- Privacy/security/rights reviewers: separate review of identity, PHI, security, data provenance/egress, code/data/model licenses and downstream rights before applicable adoption.
- Models and in-product clinical agents: generate inspectable candidate findings only; never mint identity, consent, clinical authorization or completed care events.

## Non-negotiable engineering invariants
1. No real patient data, identifiers, PHI, clinical records, credentials or private correspondence in repo, issues, PRs, model requests or demo. Use independently authored fictional cases only.
2. No clinical treatment selection, orders, verified clinician role, patient consent, trial eligibility or real external execution is inferred from a synthetic demo acknowledgment.
3. No silent technology replacement, architecture rewrite, product-feature removal, new Next.js implementation, or competing patient/evidence/permission ledger.
4. No evidence promotion without source identity, version, anchors, relevant dates, assay/specimen context, support, uncertainty and appropriate review.
5. Never collapse unknown, negative, not-tested, missing, conflicting, superseded, or withdrawn states.
6. No third-party code, data, assets, weights, terminology or service enters the build without exact version, rights, obligations and intended-use decision. Unknown rights = HOLD; follow the adopted commercial-independence procurement policy.
7. No authorization change, patient data egress, persistent model memory/training, safety escalation, medication/treatment logic, deployment, billing, or destructive data migration without separate explicit approvals.
8. No push to main by agents, no self-merge, no bypass of failing tests, no secret exposure, no rebase/reset that destroys another contributor's work.
9. Every consequential change is tied to one tracked task, an owned branch, accepted interface contracts, test receipts, documentation changes and a PR.
10. Architecture documents, Notion proposals and PRs must be marked as proposed, accepted, implemented, verified or released; these statuses are not interchangeable.

## Risk-based permission classes
| Class | Examples | Before implementation | Before merge |
| --- | --- | --- | --- |
| GREEN | Isolated test fixture, scoped documentation correction, UI change not changing accepted flows/contracts | Assigned task and ownership check | Relevant CI and independent review according to project policy |
| AMBER | Shared UI navigation, domain type/API contract, source parser, investigation data contract, additive migration, third-party adapter | Engineering coordinator and affected owners agree in recorded task; record compatibility plan | Contract/regression/security evidence and designated reviewer |
| RED | Patient identity/consent/PHI, clinical action/safety rules, rights/licensing, data egress, destructive migration, architectural replacement, major UX change, production access/deploy, feature removal | Explicit recorded human founder decision plus applicable clinical/security/rights authorization; do not execute while pending | Protected-branch reviews, demonstrated controls, release approvals by authorized humans |

If the category is disputed, treat as RED until settled. A code review cannot replace required regulatory, data, or clinical authority.

## Reconciliation / precedence
Use existing Notion identity/architecture precedence and founder decision records for accepted product intent; GitHub main + approved ADRs for actually merged implementation and tests. Notion Sprint Board is the current hackathon assignment register; GitHub Issues/PRs contain engineering execution references, not an independent competing assignment list. Resolve contradictions by recording a decision request, not by selecting a preferred document silently.

## No implied enforcement
This constitution becomes contributor guidance only when reviewed and merged. It is NOT a sandbox, permission boundary, branch protection, CODEOWNERS enforcement, clinical authorization system or production release gate. Repository administrators must configure rulesets and least-privilege credentials; verify them in a separate acceptance test.
