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

Pending at initial test-first publication. Record observed failures, final exact
head, commands and hosted run links in the draft PR and canonical engineering
progress records; do not infer a complete patient investigation from this slice.
