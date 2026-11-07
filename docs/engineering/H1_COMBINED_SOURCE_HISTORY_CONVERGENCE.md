# Open Intelligence — historical source membership + World Model convergence

**Status:** integrated construction candidate, no deployment, merge or clinical approval.

## Canonical ownership and donor identity

Candidate base: #624 `631c3e0cea30d4b859a2e428d200d352c97c6567`, tree `fb4dd9cef6f6713f6390d4559c665ad75253f473`. Retains #620 / #618 persisted patient grants, historical as-received World Model, #615 Imaging report chronology, DICOM study/series, Labs, Composer snapshot binding, source/image original controls.

Donor: #617 `842c2cd70c78e454d0233d753806c2155bf78858` on #602 `2e37d7579f3d748dfe2918a1ec4d02872e0e625c`. It adds a receipt-time **source membership** endpoint and Records UI, separate from the already connected historical World Model projection.

## Reconciliation contract

Use Git three-way merge with #602 as common baseline; preserve **both** current and donor additions in patient/source/router contracts and frontend. All 18 donor-modified files were resolved locally without deleting current owners. Of these, 17 merge automatically; the only text conflict was `apps/web/tests/registry-client.test.mjs`, where the permission-management regression and the new historical-source regressions were both inserted at the same anchor. Preserve **both suites**.

All 18 resulting files were hashed with `git hash-object`. The candidate tree uses exactly those matched blob SHAs. No source changes outside those 18 and this record. Both parents retained in the merge commit.

The two historical services have different purposes and must **not** silently be conflated:
- `GET /world-model/history`: reconstructs original reported observations, laboratory findings and source chronology as of a receipt time, without reviving historical grants or modifying current context;
- `GET /source-history`: lists the last source version per original document available by the exact received timestamp, omitting current mutable state, and permits explicitly rechecking exact original bytes under present authorization.

Both services reuse the canonical PostgreSQL patient/source owner, current organization/case and purpose grants, response preparation inside a transaction, final authority recheck and immutable event receipts. Historical membership does not certify what an earlier clinician knew, what a patient consented to, or whether a treatment was appropriate.

## Verification gates and limits

Local checks: `node --check` on both frontend test files and `python -m py_compile` on changed API/browser files passed. Local unittest import was **blocked by missing pydicom**, not a passing test. All affected tests and actual PostgreSQL/Chromium/browser recovery must run on the exact published commit using hash-locked CI dependencies.

Required: source snapshot/permission denial and revocation tests; microsecond receipt cutoff, retroactively received old events, original integrity, cross-case/actor guards, timestamp validation, response/commit rollback, API restart + dump/restore, complete frontend/SSR suite, production build and persistent synthetic demonstration. Parent CI runs do not qualify the composition.

No new runtime dependencies or database migration. No real patient input, historical clinical conclusions, clinical identity/consent verification, model execution, publication, external integration or deployment.

## Remaining engineering work

#616 semantic classification overlaps source/API and World Model owners and needs separate conflict-aware convergence. #629 adds independent purpose enforcement; ensure it composes with the persisted grants from #611. #623 lab trends and #627 hypotheses have separate scientific evaluation gates. Full product scope remains human and veterinary oncology EHR, diagnostics, pathology/molecular/genomics, treatments, clinical trials/research, operations, permissions/consent and biomedical computation. Reconcile moving main only after final-head qualification and independent merge review.

## Integration defect found and repaired before hosted acceptance

Independent donor branches each used the Python name `SourceHistory`, the route handler name `source_history`, and OpenAPI operation ID `read_source_history_v1` for different historical contracts. A simple structural merge therefore shadowed the source-membership Pydantic response model with the World Model history model and duplicated the operation ID.

The repair preserves the established `/world-model/history` model/handler/operation ID unchanged. The `/source-history` membership endpoint now uses `SourceMembershipHistory`, `source_membership_history`, and `read_source_membership_history_v1`. The source-membership donor tests patch the correct model. A new dependency-free AST regression `apps/api/tests/test_history_route_collision.py` fails on the collision and passes on the corrected revision. Both historical API behaviors remain separate.

Local evidence: the new 1-test regression failed against the initial merge with two `SourceHistory` classes and passed after repair. `python -m py_compile` and `node --check` passed. Full runtime tests still require hash-locked CI because this local runtime lacks pydicom/pg8000.
