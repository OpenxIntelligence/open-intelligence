# Upstream reconciliation — H1 frontend redesign

Inspected 2026-11-03 through the authorized GitHub connector; read-only remote access. No tracked files, index, HEAD or browser were changed by this analysis.

## Exact upstream change

- Repository: `OpenxIntelligence/open-intelligence`.
- Original UX baseline: `d8de9aaca352cc58b64e9e32440f4ea248b02cb8`.
- Inspected live parent head: `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`.
- [Compare](https://github.com/OpenxIntelligence/open-intelligence/compare/d8de9aaca352cc58b64e9e32440f4ea248b02cb8...68935c9fc60ef229aa9ff6cc4238153dc01a9b91): ahead by 1, behind by 0; merge base is the original UX baseline; exactly one changed file.
- [Commit](https://github.com/OpenxIntelligence/open-intelligence/commit/68935c9fc60ef229aa9ff6cc4238153dc01a9b91): `chore(h1): remove unused duplicate source parser from Records integration`, timestamp `2026-11-03T01:01:51Z`.
- Sole change: deletion of `apps/web/src/source-model.ts`, 133 deleted lines, zero additions. The removed module contained unused alternate case/source decoders and original-byte SHA verification helpers.

## Compatibility and preservation

No upstream file overlaps the frontend redesign's modified or added presentation/test files. No textual conflict is expected. Repository search found no production or test consumers of the deleted module or its exported decoder helpers; matches outside the module are only the new UX documentation. `RegistrySession` continues to import the unchanged active `source-contracts.ts` parser. The redesign's `RecordsPanel` also imports its types from `source-contracts.ts`.

The new parent introduces no user-facing capability, endpoint, grant, validation behavior, dependency, or test to preserve. Preserve its deletion; do not resurrect the unused decoder module when preparing the draft. Original-document retrieval remains absent from this UI.

## Required reconciliation steps

1. Build the draft branch/commit on the inspected parent head (or reconcile any further drift before publishing). Preserve `source-model.ts` as absent through parent ancestry; do not present that upstream cleanup as a UX-authored validation change.
2. Retain the original `d8de9a…` baseline in historical screenshots/test provenance. Add `68935c9…` as the final parent comparison point. Do not silently relabel earlier executions as tests against the newer parent.
3. Update `docs/ux/2026-11-02-h1-workspace-design.md:33,45` and `docs/ux/2026-11-02-product-research-ux-evolution.md:169,463`: the unused module existed at the original baseline and was subsequently removed upstream. Replace blanket byte-identity promises for that file with an explicit inherited-deletion exception or compare to the new parent where it is absent.
4. Final scope proof should show no UX diff in client/contracts/backend/auth/business/dependencies against `68935c9…`. If also comparing against `d8de9a…`, separately attribute the one deleted parser file to the upstream commit.
5. Run the planned final build/client checks against the reconciled tree and label evidence with its actual parent/head. No browser replay or new backend tests were performed for this read-only drift analysis.

Risk assessment: low integration risk; no expected functional conflict. The material risk is inaccurate scope/provenance reporting or accidentally restoring an upstream-deleted duplicate parser. No additional frontend functionality needs implementation because of this drift.

## Recorded worktree reconciliation

The working checkout advanced to parent `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`, preserving the upstream deletion, before the final product checkpoint. The boundary report compares the final UX worktree to this explicit parent. Earlier analysis wording is preserved as history and does not relabel baseline executions.
