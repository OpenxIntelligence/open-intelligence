# Synthetic release acceptance

Record results against an exact commit and keep run identifiers with the engineering decision. A pull request's body may acquire newer receipts after this document is committed.
A branch's green tests do not qualify a different tree.

| Gate | Reproduction or evidence | Required outcome |
|---|---|---|
| Baseline identity | November 4 candidate `02f920c4`; [H1 API](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41933798460) and [H1 web](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41933798303). Selected main `f188aecc`; [ledger](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42085075497) and [Crossref](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/42085075416). | All four named runs succeeded on their respective revisions. This records history rather than qualifying the new change. |
| Browser client / code | From `apps/web` install the lockfile with `npm ci --omit=optional --ignore-scripts`; run `npm run rights`, `npm test` and `npm run build`. | Four previously accepted malformed responses are rejected. Complete typed and legacy disagreement groups render regardless of ordering. Denial or invalid refresh withholds the projection. |
| API and migration | Install hash-checked wheels from `apps/api/requirements.lock` following `.github/workflows/h1-api.yml`. Inspect `alembic -c apps/api/alembic.ini heads`. Run its populated upgrade checks and complete test discovery against disposable PostgreSQL 16. | Single head `0018_laboratory_questions`. No failed or skipped acceptance tests. The three-line disagreement includes the pending source until an amendment changes scope. |
| Integrated patient journey | Run `apps/web/tools/browser_journey.py` via the H1 web workflow. Run `apps/web/tools/demo_journey.py` for persistent demo. | Two primary labels remain distinct. Compare opens the amended and independent current statements with the correct document versions and lines. Historical original and declined source access behave correctly. |
| Recovery | The H1 API workflow runs seven Compose verification scripts covering registry, original documents, laboratory, imaging, reviews, follow-through and evidence. | Restart and restore preserve accepted bytes, versions and receipts. Revoked reads remain denied and historical reads observe fresh authority. Keep GitHub run/artifact references. |
| Release decision | Explicit maintainer integration decision following exact-head evidence and source/authorization review. | Synthetic use only. Clinical release, independent validation and production deployment require separate decisions. |

If CI fails, identify the failing step and head, reproduce the smallest representative case, repair it and rerun affected gates. Do not skip blocked suites, relax authorization or delete populated history to pass.
