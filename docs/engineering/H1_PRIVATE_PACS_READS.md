# Source-authorized remote original reads over canonical image custody

Status: proposed synthetic-only integration seam. No production deployment,
clinical authorization or successful live private-PACS acceptance is claimed.
Owners: #242 at `0c57f9fe86ef3ef12d24e1fd2a883dd80ddd7a3d`, #261 at
`a433a36287b453f226437614a67079b53f7c3956` and #253 at
`4c197559f1858642ce44417e40b292cee6e2b156`; convergence is draft #277.
No new schema, migration, image identity, route, permission, runtime package or
patient store. Main and both parent branches remain unchanged.

## Implemented application boundary

The existing PostgresSourceImages original-read owner accepts an optional
operator-injected archive port. Only server-stored Study/Series/SOP identifiers
reach that port; end users cannot supply an upstream URL, token or expected hash.
The canonical PostgreSQL original remains authoritative. A configured remote
archive must return those exact bytes; errors never silently fall back to local
storage and are sanitized by the existing route.

Preflight validates current source, qualified patient/case binding and original
custody under the existing transaction, then refreshes caller authority. Remote
I/O occurs outside database locks. A fresh transaction checks source currentness,
binding revision and original custody again, then prepares the complete bounded,
non-streaming response. Only after preparation does it refresh the same caller's
identity, independent grants and purpose, append the immutable read receipt and
commit. Preparation, authority, audit or commit failure withholds the response.
Default local custody and image-metadata preparation retain #253's behavior.
Receipts attest authorization for prepared disclosure, not delivery or distributed
revocation atomicity. The provider can still change after its final check.

## Test-first convergence evidence

The six new `test_archive_disclosure_authority.py` methods ran on otherwise
unchanged #261 at test-only head `1b34de32809890d7bab62f2c8ab87b1090ba7800`.
[API run 41576570150](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41576570150)
ran 205 tests against PostgreSQL 16.15. Five new methods produced 11 assertion
failures, with no setup/import errors: seven late grant/identity/expiry changes
still returned 200; a removed authority provider still returned 200; preparation
failure returned 500 instead of the sanitized 503; independent sessions acquired
both owner locks during response preparation; and the deferred-commit test
showed response preparation had not yet occurred. The suspension-during-fetch
case and all inherited methods passed. These are controlled regression
reproductions, not evidence of a real-patient incident.

The unchanged five #261 archive tests cover exact originals, denial before
archive access, no fallback on errors/changed/non-byte results, source amendment
during fetch without blocking the writer, changed grants/actor, and audit failure.
The new suite additionally observes both lock phases and uncommitted receipts,
uses a real DEFERRABLE constraint trigger to fail commit after preparation, and
checks that suspension prevents the next archive call. #253's source/index
fidelity, projection and metadata/local-image response tests are retained.
Hosted green acceptance must be established on the combined commit; the red
run alone does not establish the fix. Final run IDs and results belong in #277.

## Explicitly unfinished deployment boundary

The earlier separate Linux network-namespace/private-socket PACS experiment was
not published and has not established successful live private-PACS or network
isolation. An application-side source check alone does not prevent direct raw
PACS access. Before enabling an external archive, independently verify network
reachability, service credentials, direct-URL bypass denial, WADO/metadata/frame/
rendered/bulk routes, DIMSE, restart/recovery and audit behavior against actual
deployed code. The injected port also remains responsible for bounded transport,
timeouts and resource use; this composition is not a concrete network adapter.

The prior PACSNode OIDC findings remain: role/modality authentication does not
establish patient/tenant/purpose isolation. Exact source/asset/crate licensing,
full DICOMweb conformance, compressed-image fidelity, production identity and
consent, broad image profiles and clinical use remain HOLD. No real patient data,
model inference, merge into main or deployment is authorized.

## Reconciliation

This draft composes #261 with #253, including #234's source fidelity through
#253. #238's sibling migration branch and other source/question writers remain
separate. Independent review and final combined-main acceptance are pending.
See `docs/superpowers/plans/2026-11-03-h1-archive-disclosure-convergence.md`.
