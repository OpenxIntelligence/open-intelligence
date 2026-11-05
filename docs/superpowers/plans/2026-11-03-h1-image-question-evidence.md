# H1 image, question, follow-through and evidence integration plan

> **For agentic workers:** Execute the independent migration and lifecycle tasks
> in parallel with explicit file ownership; root owns merge resolution, publication
> and exact-head verification. Obtain one fresh whole-change review before completion.

**Goal:** Preserve one patient's original images through the existing canonical
question, verification-return, follow-through and metadata-citation workflow.

**Architecture:** Join verified #298 and #278 at their existing common ancestor.
Keep their source/question/image/task/evidence/event owners and add one explicit
no-DDL migration merge. Extend existing acceptance and restored-API probes.

**Tech Stack:** Existing Python 3.12, FastAPI/Pydantic 2, Alembic/PostgreSQL 16.15,
React/Vite/TypeScript and locked code-only pydicom 3.0.2; no new dependency.

**Spec:** `docs/superpowers/specs/2026-11-03-h1-image-question-evidence-design.md`

## Global constraints

- Preserve exact remote #298 `89f98824610e23a26d2904a845ed1d930207bd76`
  and #278 `b72560ac0f5e5005040b0fc660ce1650343611cf` ownership/history.
- New head is `0011_image_evidence_merge`, parents `0009_image_review_merge`
  and `0010_question_evidence`; never edit published migration content.
- Independently authored fictional inputs only. Keep separate grants and immutable
  anchors/receipts; no clinical approval, external messages, merge or deployment.
- Real PostgreSQL acceptance must have zero skips. Keep all five recovery gates.

## Review focus

- A populated upgrade preserves both existing owner data and strict readiness.
- Image access events do not invalidate or revive question/task/citation content.
- A metadata-rights withdrawal cannot leak cached title/URL or become image access.
- Exact old-intent retries after amendment preserve historical IDs without new effects.
- Restored HTTP proves which database answered and preserves revoked-state behavior.

## Task 1: Preserve and join existing runtime owners (root)

Files: conflicts in `apps/api/src/oi_api/{patients,access,app,contracts}.py`,
dependency/container preparation, API workflow and inherited integration docs.
Retain #298 frontend, follow-through/evidence routes and source-import authority;
retain #278 image routes and complete image/review response preparation.

- [x] Verify #298 archive digest, commit and full 356-file source tree.
- [x] Create a branch in the existing isolated workspace and run 10 base contracts.
- [x] Merge exact #278 local equivalent into the #298 local import, preserving
      both remote parents for publication. Resolve only actual conflicts.
- [x] Retain all image routes/capabilities/independent grants and existing #298
      routes/models. Validate the combined contract and clean conflict markers.
- [x] Keep the code-only dependency build/gates and all five Compose steps.

## Task 2: Prove preserving schema convergence (migration worker)

Files: create `apps/api/migrations/versions/0011_image_evidence_merge.py` and
`apps/api/tests/test_image_evidence_migration.py`; own schema/capability contract
expectations and historical migration/current-head test alignment. Own exact-head
constants in registry/review/follow-through Compose helpers; image helper belongs
to Task 3. Coordinate shared fixture cleanup with root before changing it.

Consumes existing published migrations and populated fixtures from both parents.
Produces a single ready schema and actual PostgreSQL upgrade/rollback acceptance.

- [x] Add a graph test that expects the explicit merged head; observe failure on
      the two published heads before writing the merge migration.
- [x] Add the minimal no-DDL merge and observe graph GREEN.
- [x] Add populated upgrades from either parent and both applied parents; compare
      every existing owner row and immutable original byte/hash/provenance.
- [x] Add unknown image/task/evidence ownership rollback checks and preserve
      downgrade/immutability guards. Use real SQL owners, not mocked migrations.
- [x] Verify all distinct published migration files remain byte-identical.
- [x] Run focused local contracts/graph checks; actual populated acceptance runs
      on the frozen hosted candidate. Report database skips explicitly.

## Task 3: Prove the connected patient lifecycle and restored API (lifecycle worker)

Files: create `apps/api/tests/test_image_evidence_integration.py`; extend only
`apps/api/tools/verify_images_compose.py`. Consume existing source/question/image/
review APIs, `GET /followthrough`, `POST /questions/{id}/followthrough`, task
transitions and `POST/GET /questions/{id}/evidence-links` plus evidence search.
Reuse the existing fictional metadata seed/rights owner.

- [x] Add real HTTP/PostgreSQL acceptance for report/image/question, source
      packet/brief, verification return, task and citation in one qualified case.
- [x] Assert image activity preserves content fingerprints and stored task/link
      history; amendment keeps old anchors and IDs, with explicit relink and fresh
      current question context. Exercise old exact retries and current new intent.
- [x] Assert independent image/task/evidence grants, rights redaction and rollback
      preserve unrelated existing history. Scope new tests to combined risks.
- [x] Extend active restored-API image probe with task/citation rows and retries,
      new receipt only in restored DB, original DB unchanged, then restored rights
      and binding revocation. Keep existing image/question/review assertions.
- [x] Keep helper stdlib-importable and bounded; run focused local checks and
      report real PostgreSQL/Compose execution as pending until hosted results.

## Task 4: Review, exact-head acceptance and durable receipts (root)

- [ ] Independently review the frozen whole candidate; reproduce and fix material
      findings before final publication/acceptance.
- [ ] Publish a stacked draft with both exact remote parents and matching tree.
- [ ] Execute full API/PostgreSQL, 282-reference baseline, frontend/build/browser,
      applicable inherited browser journeys and five Compose recovery gates at
      the submitted head.
- [ ] Inspect only concrete failures; do not waive skipped database checks or
      weaken owner contracts. Record RED-to-GREEN where a repair is required.
- [ ] Verify browser artifact digest, recorded commit/source blobs and relevant
      populated captures. Record evidence and precise limits in PR and existing
      Notion/Drive engineering records and the integration inventory.

## Execution notes

The user authorized continuation and routine reversible integration. Existing
decisions determine the platform and owners; no new design permission is needed.
The common executor has no usable local PostgreSQL/Docker acceptance path; use
the existing hosted disposable PostgreSQL workflow for real database evidence.
The first baseline command named nonexistent `test_settings`; its 10 contract
tests passed and a corrected `test_contracts` command passed all 10. The first
archive import assumed ZIP Unix mode attributes; this archive records zero
attributes. Reconstructing regular-file modes reproduced the exact pinned Git
tree, verifying both mode and byte choices. Neither setup correction is a product
failure. Final executed acceptance belongs to the exact PR/docs receipt.

## Executed checkpoint and bounded follow-up

Initial runtime `895561f6ca7e1271e8401604c77c95635c28274f` passed the complete
464-test API/PostgreSQL suite without skips, 282 reference tests, both original
browser journeys, all five Compose probes, 219 client tests, build and actual
React browser acceptance. Independent whole-change review found no material
finding. Artifact 13241720289 matched all 391 source files and its recorded
commit; relevant populated captures were inspected. The standalone legacy UI
workflow was excluded by its unchanged path filters; the inherited journeys ran
inside the API gate.

Fresh canonical-record reconciliation identified #311's directly applicable
citation-history timestamp correction. Adopt its exact two files and actual
remote ancestry: donor `8f7ad6a80dcb5312bc63480339d9142376883a4a`. The imported
regressions first produced 20 failures; exact implementation adoption then passed
22 focused contract/API tests with zero skips. This is a scoped outgoing-contract
correction, with added OpenAPI length bounds and unchanged valid timestamp bytes.
It adds no migration, permission, dependency or owner.

Task 4's final completion is tracked in PR #313 and the existing Notion/Drive
engineering records after the fresh delta review and combined-head gates. This
committed plan is the implementation checkpoint, not a substitute for that final
acceptance record. The newer #307 report/task join and #312 archive/image join
remain separate continuation owners; they do not expand this candidate by implication.
