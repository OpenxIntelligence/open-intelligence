# H1 source read authority and receipts — 2 November 2026

## Existing owners and bounded decision

Continue the patient → source → investigation foundation under the accepted H1
FastAPI/PostgreSQL direction. Preserve the patient registry, qualified case
binding, original-source owner, source IDs, action vocabulary and event ledger.
No new database, source adapter, package, model, medical content or patient data.

Initial inspection started at #182 `fa41da5e7a17b3803b74d779592b0d25faaf41eb`.
A live recheck discovered concurrently published #187
`2f43c000dbe7b6d42b546eb8c726c8b8ca4db164`, which already ports original source
versions to PostgreSQL. This contribution therefore starts from #187 rather
than publishing a competing SQLite-backed API. #188
`fa67df4e83d278b4edb51407dac4893f1ac26e82` is an internal SQLite read contract,
not an HTTP or PostgreSQL implementation. Its permission-recheck principle
informs the tests; its adapter is not mounted over the newer source owner.

The abandoned local SQLite experiment exposed an A→B→A pathname-replacement
race despite before/after device/inode checks. It remains unpublished. Resolving
filesystem identity is unnecessary for this single-owner PostgreSQL slice.

## Reproduced behavior and intended change

The inspected #187 read paths authenticate only at entry, omit the persisted
case-binding purpose and append no read-access event. Tests first reproduce
content returned after changes to actions, patient grant, actor, organization,
purpose, expiry or provider availability. A purpose-mismatch test reproduces
an operations principal accessing a research binding. Matching-purpose
research remains supported; this is not a new research authorization policy.

1. Reuse one bearer parser for initial and refreshed authentication.
2. Retain patient+action authorization and require purpose equality with the
   persisted binding for imports and reads. No implicit patient/source grants.
3. Keep the existing patient `FOR SHARE` and binding `FOR UPDATE` locks during
   source materialization, final authority callback and event append.
4. Append reference-only `source.read_authorized` or
   `source.original_read_authorized` to the existing immutable identity events.
   Return an opaque `ACCESS-*` receipt only after commit. A failed callback,
   event insert or commit withholds the response.
5. Record the exact materialized index digest, or the original ID/hash/version/
   state, without source text, credentials or filesystem paths in events.
6. Revalidate original bytes against their stored hash, parsed patient/document/
   event/specimen context and amendment predecessor. Stored corruption is an
   unavailable-service condition, not a bad user request.
7. Apply the existing 16 KiB/five-second JSON ingress guard to case-binding
   revocation; its missing `/revoke` match was independently reproduced.

An access receipt records authorization for prepared disclosure, not successful
network delivery. External grants can change after the final check; PostgreSQL,
the fixture provider and HTTP are not one atomic system. Existing mutation
routes otherwise retain their entry-authentication behavior.

## Verification boundary

Use independently authored synthetic UTF-8 reports only. Run actual PG16/HTTP
negative controls for changed authority, purpose mismatch, active-patient state,
audit rollback and corrupt stored originals; preserve existing historical
version, amendment, isolation and immutable-history tests. Run the complete H1
suite and unchanged legacy suite once the integration is ready. Hosted CI must
check the exact proposed head and execute actual Compose source import/read,
API/database restart, dump/restore and revocation acceptance.

No new third-party artifacts are adopted. Existing lockfile and rights inventory
remain unchanged; inherited distribution/container/native-linkage holds remain.
No real accounts, clinical consent, source-to-investigation invalidation port,
React source workflow, real-data pilot, merge or production deployment is implied.

## Observed results

The initial six PG/HTTP authority tests produced nine assertion failures and one
missing-receipt error; the authorization-before-source-I/O control already passed.
After the bounded fix all six passed. A separate wrong-context original with a
matching SHA-256 reproduced HTTP 200 before read-integrity validation.
Final integration and hosted evidence will be attached to the published head.

Final local integration: **91 H1 tests passed, zero skips**, in 45.941 seconds
against actual PostgreSQL 16.15/Python 3.12.14. **245 unchanged legacy tests
passed** in 28.864 seconds. A focused HTTP check also confirmed the index receipt
digest matches the returned serialized payload. The exact-wheel gate passed
for the unchanged 24 wheels, 99 supplier native components and 13 embedded
runtime entries in its existing local-synthetic-development scope. The static
CI patient-data boundary guard passed. Independent authorization review found
no blocking defect in the final callback, purpose or receipt sequence.

Docker and Chromium are unavailable locally. The new dedicated Compose verifier
is syntax-checked and wired after the inherited registry acceptance; execution
and exact-head hosted status are pending at publication, not inferred from the
local tests. It checks actual HTTP source import/read, both service restarts,
historical originals, permission denial, access receipts and source-aware restore.

Remaining known gaps include source-index pagination, independent assertion
revalidation, downstream investigation invalidation, and the earlier nullable
terminal-reason CHECK expressions in acquisition/binding migrations (inspection
finding, not changed or claimed fixed here). The write source/receipt owner,
identity and source schema definitions remain with their existing PRs.
