# Bounded private-socket original-image reader

## Goal and ownership
Continue draft #277 at `2ad1271535accd73352a04672a03820a8cf05a6b`
(tree `4ef5e93e783fd102f110098adeca182e7c6d30f7`). Add a concrete,
operator-injected transport for its existing `read(study_uid, series_uid,
sop_uid) -> bytes` port. The PostgreSQL patient/source/image owner still validates
exact original bytes, current source and authority before disclosure. This
transport does not grant patient access. OI-006/OI-013, fictional development only.

## Approach (engineering choice under the standing execution mandate)
A fixed Linux AF_UNIX pathname socket keeps DNS, arbitrary URLs, redirects,
network credentials and TCP dialing out of this first transport. Require an
explicit expected peer UID and verify SO_PEERCRED before sending identifiers.
A general HTTPS client and a deployed PACS/gateway would require additional
service identity, endpoint policy and deployment decisions; they are not added.
No source ledger, schema, permission, runtime dependency or automatic activation.
The upstream service/gateway itself is not implemented in this slice.

## Wire contract
GET `/studies/{study}/series/{series}/instances/{sop}`, with canonical numeric
DICOM UIDs (3-64 ASCII characters, no leading zero components). Fixed Host
`oi-archive`, no caller headers, cookies or bearer forwarded. Accept only 200,
Content-Length, and either application/dicom or exactly one multipart/related
application/dicom part. Parameters/headers outside the documented strict profile
fail closed; no transfer/content encodings, redirects, retries or fallback.
The header limit is 16,384 bytes; at most 64 headers; each header line at most
4,096 bytes. The decoded instance limit is 2,097,152 bytes, with at most 16,384
additional multipart envelope bytes. Reject empty/truncated/oversized bodies,
ambiguous lengths/duplicate headers, extra parts, malformed delimiters, preambles,
epilogues, nested multipart and trailing wire bytes. Original bytes are never
normalized. Require EOF after the declared body within the same deadline.

A monotonic total deadline (default 5 seconds; configurable 0.05-30 seconds)
covers connect, request send, every response read and parsing. Recompute remaining
time before each blocking operation so trickling bytes cannot reset the budget.
Each call opens/closes its own socket; no shared connection/cache/background job.
Public errors/repr contain no socket path, UID, upstream reason/header/body or
underlying exception. Configuration errors are similarly generic. Per-call bounds
are not a global concurrency limit or hard real-time scheduling guarantee.

## Verification
Real temporary Unix-socket responders, independently authored payloads and
existing fictional DICOM fixture. Test exact bytes/request construction, kernel
peer UID refusal before identifiers, malformed transport, full size limits,
slow headers/body and connection closure, interrupted peers, repeated/concurrent
reads and resource cleanup. Inject this same adapter into the existing real
HTTP/PostgreSQL test fixture to test custody/authorization integration when the
exact runtime is available. Never count an unexecuted PG test as acceptance.
Retain inherited reference/source checks and unchanged owner/migration hashes.

## Remaining gates
No live PACS, gateway, private-network isolation or raw-backend bypass claim.
Local peer UID is service identity only; protect the socket directory and use a
dedicated service UID in deployment. Same-UID compromise/root and another exposed
backend route are not blocked by this reader. Default application stays local.
No broad DICOMweb conformance, compressed-image expansion, production identity,
consent, clinical validity, merge or deployment. Independent review remains due.

## Primary references consulted 2026-11-03
- DICOM PS3.18 2026d Retrieve Instance example:
  https://dicom.nema.org/MEDICAL/DICOM/current/output/chtml/part18/sect_B.8.html
- Python 3.12 socket API and per-operation timeout semantics:
  https://docs.python.org/3.12/library/socket.html
- Linux AF_UNIX pathname sockets and SO_PEERCRED:
  https://man7.org/linux/man-pages/man7/unix.7.html

These document protocol/API behavior; they are not copied implementation code
or product compliance evidence. The deliberately smaller profile above is an
engineering constraint, not a claim that unsupported responses violate DICOM.
