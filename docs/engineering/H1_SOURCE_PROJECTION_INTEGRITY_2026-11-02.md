# H1 source-to-World-Model integrity and disclosure

## Bounded continuation

Base: PR #222, `911b0767c671ae6f40caf20f204aedf1e9df2ab0`. Its live API and
React CI already integrate #214's access receipts with #213's source-derived
World Model. Do not duplicate those decoders, endpoint or patient/source owners.
The local source branch is `fix/h1-source-projection-integrity-20261102`.

Reconcile the literal source-validation behavior inspected in #216
(`6ea7b3cdde680c971414f5b9ace8d513ec5dd7d8`, `world_model_read.py`) into the
existing #222 owner. Preserve #222's response contracts and React projection;
do not introduce #216's competing World Model representation or ordinal IDs.

## Reproduced gaps and intended behavior

1. The source index trusts persisted assertion tuples without rechecking their
   quote, key, certainty, line and completeness against the original bytes.
   Validate originals, metadata, amendment history and current assertion tuples
   before returning the index or producing its dependent World Model.
2. The World Model currently projects after the source owner commits. A
   credential revoked, expired or unavailable during projection still produces
   HTTP 200. Prepare the response under the existing patient/binding locks,
   then perform the mandatory authority recheck and receipt commit. A reserved
   receipt ID is only an internal candidate until that commit succeeds.
3. Opening or closing an original invalidates a concurrent World Model read,
   but leaves its UI phase loading. Clear the cancelled pending state, keep the
   late-response guard, preserve completed views and allow an explicit retry.

Keep the source-index digest and stable World Model content fingerprint
separate from the per-read receipt. The receipt describes authorized prepared
source disclosure, not clinical approval or confirmed delivery to the client.
External authority can still change after the final check.

## Verification plan and environment

Test first against the unchanged parent. Actual PG/HTTP negative cases cover
schema-legal inconsistent originals/assertions, missing or extra findings,
lineage corruption, projection-time authority changes, projection/audit failure,
and independent-session NOWAIT locks held through preparation. Client tests use
deferred responses to exercise cancellation and explicit recovery. Preserve the
parent's complete API, legacy, built React/browser, dependency and container
restart/restore gates on the exact final head.

The parent's hosted baseline passed 128 API/PG tests, 245 legacy tests and 51
client tests plus browser/container acceptance. A local attempt could not start
the disposable PostgreSQL server: user switching was denied and the automatic
approval policy rejected escalation. The resulting local run reported database
connection setup errors; it is not a passing baseline. Use the existing hosted
disposable PostgreSQL workflow for actual database red/green evidence.

All fixtures remain independently fictional. No new dependency, migration,
medical content, model, distribution license, real-data permission or deployment
is introduced. Full Composer/evidence/report/review integration remains separate.

## Execution evidence

Tests-first commit: `5d5a723e57861fa63a845bc55c65592a1928636c`.
[Hosted API run 41567217329](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41567217329)
collected 145 tests against PostgreSQL 16 and reproduced 35 failed assertions
(including subtests), with no test setup errors. The failures covered source
tuple/hash/history mismatches, projection-time authority changes, projection
failure and early receipt/lock release. The valid Unicode/amendment control
passed. This is red evidence, not a successful implementation run.

The local client regressions reproduced two loading-state failures before the
fix. After the implementation, all 53 client tests passed using the actual
TypeScript modules through Node 24.22.1's in-memory TypeScript stripping. This
does not establish TypeScript type checking or a built-browser result. The
local pure-source and HTTP contract command also passed 25 tests:

```sh
PYTHONPATH=apps/api/src:src:apps/api/tests /tmp/oi-h1-venv/bin/python -m unittest test_source_integrity test_contracts -v
```

Independent read-only implementation reviews found no blocking defect in the
source validation or projection/authority ordering. The new browser regression
holds only delivery of a real completed response; it uses the actual application,
API and database and restores its temporary interception afterward.

Final PostgreSQL, pinned frontend build and actual-browser verification remain
required on the published implementation head. Record that exact head, commands
and hosted run links in [draft PR #234](https://github.com/OpenxIntelligence/open-intelligence/pull/234)
and the canonical engineering progress records. This slice serves the existing
OI-006 source-provenance and OI-013 authorization/recovery backlog requirements;
it does not complete either requirement or the patient investigation milestone.

Operational limit: every read rehashes the complete case source history while
the existing locks are held. It uses one additional query rather than an N+1
query pattern, but large-history latency and pagination require separate
qualification. No performance or distributed authorization atomicity is claimed.
