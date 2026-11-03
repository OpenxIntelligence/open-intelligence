# Source-authorized remote original reads over canonical image custody

Status: proposed synthetic-only integration seam. No production deployment,
clinical authorization or successful live private-PACS acceptance is claimed.
Base: #242 at 0c57f9fe86ef3ef12d24e1fd2a883dd80ddd7a3d. No new schema,
migration, image identity, route, permission, runtime package or patient store.

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
binding revision, original custody and caller grants again. The existing read
receipt must commit before bytes are returned. Source amendments, revoked
permissions, changed actors, altered originals and audit-write failures withhold
content. Receipts attest prepared disclosure, not delivery or distributed
revocation atomicity.

Five new tests use actual PostgreSQL and HTTP with a controlled archive port:
allowed exact bytes and receipt; wrong-patient refusal before remote access;
remote errors/changed or non-byte results without fallback; amendment during
fetch without blocking the writer; late grant/actor changes; and audit failure.
Some test methods cover more than one negative condition. Existing local-only
custody and all parent security/ingress/migration tests are retained.

## Explicitly unfinished deployment boundary

A separate Linux network-namespace/private-socket PACS experiment was authored
locally, but publication was blocked. It is not part of this source change and
has not established a successful live private-PACS or network-isolation result.
An application-side source check alone does not prevent direct raw PACS access.
Before enabling an external archive, independently verify network reachability,
service credentials, direct-URL bypass denial, WADO/metadata/frame/rendered/bulk
routes, DIMSE, restart/recovery and audit behavior against actual deployed code.

The prior PACSNode OIDC findings remain: role/modality authentication does not
establish patient/tenant/purpose isolation. Exact source/asset/crate licensing,
full DICOMweb conformance, compressed-image fidelity, production identity and
consent, broad image profiles and clinical use remain HOLD. No real patient data,
model inference, merge or deployment is authorized.

## Reconciliation

The earlier competing image-custody candidate was stopped in favor of #242's
published owner. #234's newer source/response fidelity and #238's sibling
migration branch still require explicit owner-reviewed convergence; this change
does not represent those branches as integrated.
