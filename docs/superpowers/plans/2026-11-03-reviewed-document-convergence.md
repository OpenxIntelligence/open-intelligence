# Reviewed-document candidate convergence implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement and verify this bounded integration. The founder's instruction to start follows the product assessment; ordinary reversible development is authorized by AGENTS.md.

**Goal:** Bring the already implemented ordinary-document, evidence chronology, review-draft, task-date and restored-document workflows into the existing #354 candidate and verify their interaction on one exact head.

**Architecture:** Preserve the existing canonical source, question, evidence, review and task owners. Compose existing reviewed contributions with three-way source reconciliation. Update #354 with a lease after local review; keep merge/deployment as separate decisions.

**Tech stack:** Adopted H1 FastAPI/PostgreSQL16 and React/Vite/TypeScript; exact dependencies remain unchanged.

**Spec:** `docs/FIRST_PRINCIPLES_PLAN.md`, `docs/engineering/H1_REVIEWED_DOCUMENTS.md`, `docs/engineering/H1_EVIDENCE_CONTINUITY.md`, `docs/engineering/H1_CONNECTED_RIGHTS_CONVERGENCE.md`; existing backlog OI-006/007/008/009/010/013 and GH-323. This executes the assessment's integrated-candidate milestone, not full platform completion.

## Global constraints

- Independently authored synthetic patients only; no actual personal medical data or derivatives.
- Preserve patient/case authority, exact sources and versions, uncertainty, current content rights, human clinical authority and fail-closed access.
- No new owner, dependency, migration, model, clinical function or outbound notification.
- Preserve manual-document provenance as separate from structured question/report snapshots.
- Preserve #354's document-aware RegistrySession, migration 0012 and existing rights/PDF checks.
- No unrelated branch replacement, force-push, merge to main or deployment.

## Inputs

| Role | PR | Frozen head |
|---|---|---|
| Existing candidate | #354 | d9b81f08a97998e8f95d2a1cc7c43b4165e99862 |
| Chronology, recovery status and Review drafts | #368 | 2d62b05357ad64524d561c2e05c903674cd4e54c |
| Strict follow-up dates | #369 | 3c028ddfb4b408571b36140a5e5b52115c7bd790 |
| Restored-document HTTP acceptance | #362 | c7fd1bd865f4a8f42da1e515a2599431d14f0a8d |
| Shared acceptance triggers and bounded state reconciliation | #367 | bbf56762e73f50fbe6432768deb605ed03edf09b |

The #354/#368 common ancestor is #359 `e2c888cf5b9065c8b6a60284666e6f35fe2c1e63`. The verified archive supplies #354's exact tree; fetched donor blobs are checked against Git hashes. Local snapshot commits support comparison only; the published integration must retain actual remote parents.

## Review focus

- A current document denial clears an app-owned unsent Review reason and does not resurrect it after fresh access.
- Temporary or stale document failures preserve independently authorized newer work.
- Keep both document and review-draft browser journeys; run the two-case Review helper before the document helper creates its third case.
- Malformed evidence/task chronology withholds affected controls without broadening its API-specific timestamp contract.
- Restored documents are exercised through actual HTTP with independent grants and revoked-binding controls; inherited parent success is not combined success.

### Task 1: Compose existing owners and prove shared boundaries

**Files:** existing client/component/test/browser paths supplied by #368/#369; `apps/api/tools/verify_sources_compose.py`, its new assertion tests and existing workflow environment from #362; five-line H1 web trigger/audit change from #367; focused current-state documentation.

**Interfaces:** consume the existing RegistrySession/ViewState, Review draft hook, source/document adapter and browser CDP helpers. Produce the same APIs and schema with combined acceptance; no new persistent contract.

- [x] Confirm byte-exact #354 baseline and run existing client suite. Expected: all existing tests pass.
- [x] Run donor chronology/task regressions against the old implementation before composing their fixes. Expected: failure on accepted impossible timestamps or missing strict validator.
- [x] Merge the frozen contributions using their real common-base blobs. Keep both document and Review application paths, current rights implementation and complete histories.
- [x] Add actual browser coverage for Review draft → document denial → fresh recovery; retain existing document and evidence denial controls.
- [x] Run full client suite, typecheck/build, rights gate, data-boundary audit, recovery assertion tests and Python syntax checks. Expected: all scoped local gates pass; explicitly record any unavailable external/runtime gate.
- [x] Obtain independent code review of the final diff and fix material findings with a reproducing check.

### Task 2: Publish and verify the same candidate

**Files:** existing engineering continuity/current-state records; no further product changes except required verification fixes.

**Interfaces:** exact local tree plus frozen remote parent heads → Git tree/commit → leased existing #354 branch update → hosted Actions receipts.

- [ ] Recheck #354 head before publication; if moved, inspect and preserve its new work before any update.
- [ ] Create a commit with #354 first parent and the included donor heads as additional parents; verify the remote tree equals the locally tested tree.
- [ ] Update the existing draft using the expected old SHA. Record scope and pending hosted acceptance truthfully.
- [ ] Inspect actual full API/recovery and React/browser runs on the published head, including checkout identity, final status and restored-document receipt. Fix failures without weakening acceptance.
- [ ] Record exact verified source, run URLs, included/excluded work and remaining product boundaries in #354's description and the existing evidence record.

## Completion boundary

Success is one reviewed, locally and hosted-verified draft candidate containing these existing capabilities. It does not establish manual-document findings in structured investigations, ordinary real accounts/consent, clinical review operations, live biomedical/model reasoning, independent usability, production readiness or main integration.
