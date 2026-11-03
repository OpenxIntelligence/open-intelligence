# H1 archive/disclosure convergence

Continue the accepted backend owner convergence: #261 at
`a433a36287b453f226437614a67079b53f7c3956` and #253 at
`4c197559f1858642ce44417e40b292cee6e2b156`, both above #242.
Serve the existing source-bound original-image route without losing either
archive I/O lock release or final prepared-response authority.

## Approach and boundaries

Compose existing owners, rather than create a new archive gateway, patient
ledger, image store or permission. Reusing #261 alone leaves response preparation
outside final authority; holding #253's transaction across remote I/O blocks
source writers. Instead: preflight and authorize; release the transaction;
retrieve the exact original via the operator-injected port; open a fresh
transaction; revalidate source, binding and bytes; prepare the full response;
recheck the same bearer and independent grants; append and commit the receipt;
only then return. Default local custody follows the existing #253 path.

Preserve #253 source snapshot/integrity validation, response headers, all parent
tests and #261's no-fallback rule. No schema, dependency, model, UI, identity or
clinical-status change. Independent fictional fixtures only. Tests use a
controlled archive double, not a live private PACS. No network-bypass, distributed
atomic revocation, delivery confirmation, deployment or adoption claim.

## Acceptance

Actual PostgreSQL16/HTTP must withhold bytes and successful-read receipts after
late grant/actor/organization/purpose/patient-scope/expiry/provider changes,
response construction failure and deferred commit failure. Independent sessions
must acquire patient/case locks during archive I/O and fail NOWAIT during
response preparation. Suspension or source amendment during fetch must invalidate
the read. Retain the exact-byte, no-fallback and canonical receipt contracts and
run both existing H1 API/recovery and React/browser workflows on one final head.
