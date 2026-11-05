# H1 source, image and question convergence

**Goal:** Run the existing canonical source/World Model, persistent question and original-image owners together on the accepted H1 stack.

**Authority:** The accepted H1 decisions in Notion 03 and the latest Notion 12/14 and Drive Engineering continuation call for owner reconciliation. This implements that recorded direction; it does not select another architecture.

**Architecture:** Extend #244 (`3b6c466950852c20f99d57a70dd196fd2862571a`), which already incorporates #234 source fidelity and the canonical question/preflight contract, with #242 (`0c57f9fe86ef3ef12d24e1fd2a883dd80ddd7a3d`). Keep the same patient registry, qualified case binding, source versions, access events and immutable questions. Preserve both published migration branches and converge them with a deliberate merge revision.

**Tech stack:** Existing Python 3.12/FastAPI/Pydantic/SQLAlchemy/Alembic/PostgreSQL 16 and React/Vite/TypeScript. Reuse #242's pinned code-only pydicom artifact and existing dependency-rights gate.

**Specification:** `docs/engineering/H1_CANONICAL_SOURCE_QUESTION_INTAKE.md`, `docs/engineering/H1_SOURCE_PROJECTION_INTEGRITY_2026-11-02.md`, and `docs/superpowers/plans/2026-11-03-h1-image-custody.md`.

## Constraints

- Independently authored fictional records and DICOM bytes only.
- Preserve the original source and question fingerprint contracts; access receipts are not part of content identity.
- Preserve independent image and question grants. Layout, an image attachment or a question never confers clinical authority.
- Prepare responses before the final authority check and immutable event commit; failures return no prepared body or new committed receipt.
- Keep every published migration ID and parent unchanged; readiness requires exactly the new merge head.
- No new viewer, model, dependency selection, evidence ledger, clinical review state, source-brief owner, production identity, merge or deployment.

## Review focus

1. A database already at either published branch head upgrades without losing images, questions, links, originals or events.
2. Image response construction fails or revokes a credential: no new read receipt or import persists and no body escapes.
3. Source amendment preserves original bytes and question anchors, requires explicit image relinking and marks the old question for reassessment.
4. Image-only activity leaves canonical source/World Model fingerprints stable; access receipts remain distinct.
5. Unknown/multiple Alembic heads and unexpected migration dependencies fail closed.

## Tasks

### 1. Reconcile existing owners

- [ ] Resolve only overlapping action lists, capabilities, response models, readiness references and test cleanup.
- [ ] Preserve #242's shared `_validated_original` helper with #234's literal source/snapshot verification.
- [ ] Add failing image-preparation regressions, then adapt image import/list/original response preparation to the final-authority/receipt owner.
- [ ] Run source integrity, response contracts, image parser/ingress and preparation checks.

### 2. Converge migration history

- [ ] Add failing single-head/branch-upgrade acceptance before introducing `0008_merge_image_questions` with parents `0007_question_snapshot_contract` and `0006_image_custody`.
- [ ] Retain both owner migrations byte-for-byte; update exact readiness revision and applicable fixture expectations.
- [ ] Test upgrades from each populated owner head and reject unknown/multiple heads. Run actual PostgreSQL migration and owner tests in hosted CI if PostgreSQL remains unavailable locally.

### 3. Prove the connected behavior

- [ ] Add a real PostgreSQL/HTTP integration journey: imaging source → World Model → question → image import/read → amendment → old question reassessment → explicit image relink, with distinct grants and stable fingerprints.
- [ ] Retain the existing image restart/dump-restore acceptance, canonical-question browser journey, source fidelity tests and supplier-rights gates.
- [ ] Independently review the combined diff and fix material findings with regression evidence.
- [ ] Publish a draft PR; inspect exact-head hosted results and document actual outcomes and limitations in the existing records.

## Execution notes

- The initial baseline attempt overlapped the mechanical merge and encountered conflict markers; it is not a product regression result. Re-run the untouched parent baseline independently.
- Local runtime has no PostgreSQL or Docker binary. Actual database, migration, container/restart and built-React browser verification must be distinguished from local unit checks.
