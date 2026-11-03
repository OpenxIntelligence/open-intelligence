# H1 PostgreSQL: canonical record request → exact received original-source receipt

**Status:** synthetic-only, reviewable integration candidate stacked on original source owner [PR #187](https://github.com/OpenxIntelligence/open-intelligence/pull/187). Do not adopt or deploy as clinical software without authorization, security, data-rights, and source-owner reviews.

## What is actually connected

Existing first-party owners remain authoritative:

- `identity.identity_patients`: opaque canonical patient and its append-only `identity.identity_domain_events` journal
- `coordination.patient_case_bindings`: reviewed-but-fictional qualified patient/case relationship and its revocation
- `coordination.record_requests`: original request/intention, category, cancellation guard, revision, and organization
- `clinical_source.source_versions`: original bytes, SHA, current/historical versions, source kind, and authored assertions

The new `POST /v1/patients/{patient_id}/record-requests/{request_id}/receive` links an **already imported, exact original** to an existing requested item. It does **not** reimport/copy the original or send a request to an institution. It requires independent `patient_read`, `record_request_receive`, and `source_read` scopes plus an active, correct canonical patient/case organization mapping. A mismatched case, different patient, different category, cancelled request, superseded/unrecognized source, or corrupt original hash fails closed.

A single append-only `record.request.received` event records `request_id`, `case_id`, `source_id`, SHA and version in the **existing patient identity event journal** within the existing row-locked transaction. There is **no second received-source table or mutable source pointer**. Reads project `received` from the event, and the request's `updated_at` is projected from that exact event's `occurred_at` rather than incorrectly retaining request creation time. Source disclosure requires its separate `source_read` grant. A received request cannot subsequently be cancelled. Identical retry returns a duplicate without another event; changed source references are rejected. The source may later be amended, but the previous receipt stays historically pinned and projections show `source_superseded_reconciliation_required` until an explicitly authorized operational reconciliation is recorded (the draft continuation below supplies that command; it is not clinical review).

A revoked case relationship hides the exact source reference and blocks subsequent source use, without fabricating a deletion of history. `record_request_read` alone may show that a record has been received but must not reveal source identifiers or bytes. `source_original_read` is still required to view original source text.

## Final write authority — continuation on #244

[Draft #265](https://github.com/OpenxIntelligence/open-intelligence/pull/265)
extends this existing receive command and the existing original-source import
command. It is based on canonical source/question head
`3b6c466950852c20f99d57a70dd196fd2862571a`; it does not replace the active
question/review convergence in #262 or source-only brief in #264.

Both writers now prepare their existing receipt's validated JSON and HTTP status
while their patient/case/request locks are held, then refresh the original bearer
before their existing transaction commits. Source intake requires current
`patient_read` and `source_import`; receive requires current `patient_read`,
`record_request_receive` and `source_read`. Actor, organization, purpose and patient
scope must still match. The same boundary covers original/amended imports,
quarantine, duplicate originals/quarantine, first received pointers and historical
receipt retries. No new grant, table or event type is introduced.

A denial or response-preparation failure rolls back the tentative source,
assertions, predecessor supersession, quarantine or received event as applicable.
Already committed originals and historical receipt pointers remain unchanged. A
restored legitimate grant may retry. The JSON body is prepared before commit;
network delivery occurs afterward and can still be uncertain. External authority
may change after the last successful check.

The two domain methods require a `recheck_authority` callback and accept the same
application-owned `prepare_response` callback pattern already used by the source
and question owners. The HTTP adapters supply both. In-process callers must
provide their trusted current-authority check; client-supplied callbacks or rights
objects are not an API feature.

Twelve new real PostgreSQL/HTTP regressions cover late grants/identity changes,
quarantine/duplicates, historical retry, DTO and actual JSON preparation, and
independent-session locks. The first hosted red checkpoint exposed an incorrect
generic JSON-render test hook; the refined checkpoint reproduced committed writes
after denied authority/preparation and released locks. The final fixture covers
both FastAPI's typed serializer and explicit prepared JSON. See the
[implementation record](../superpowers/plans/2026-11-02-h1-intake-authority.md).
Final exact-head API, recovery and built React/Chromium results are recorded in
the draft PR's verification receipt; local PostgreSQL availability is not claimed.

## Explicit limitations

- The record request's institution/label is user-authored fictional input; it is **not independently authenticated as the source provider** or evidence that an external hospital was contacted.
- `source.current` means current **among imported versions in this synthetic system**, not clinically verified or the latest external document.
- The source is fictional structured `.txt` (`OI-SYNTHETIC-REPORT/1`); no PDF/OCR, DICOM, clinical EHR, real PHI or consent.
- Only a synthetic operator fixture provides actor tokens and rights; this is not clinician identity, professional authority, clinical data rights, a prescribed test or treatment action.
- No full Patient World Model/Composer reassessment or rights-aware research model is activated by the receipt event. It is an operational provenance bridge awaiting review and source-domain integration.
- The same PostgreSQL transaction protects request row and case binding; asynchronous distributed publication to external systems and cross-service atomicity are **not claimed**.

## Verification and source ownership

`apps/api/tests/test_received_record_requests.py` uses the real PG16 HTTP app, source owner, patient registry, original source bytes, case binding and event history. It checks first receipt/identical retry, restart, source amendment without retarget, cancelled request, wrong case/kind/patient, scoped read versus source read, binding revocation, and failed domain event rollback. Existing source-owner and record-request regression suites remain enabled.

**Review dependency order:** #162 H1 root → #172 patient → #178 record acquisition → #182 case binding → #187 original sources → this candidate. Existing record request, source and patient schemas belong to their original owners; no new migration, vendor dependency, model weights, or frontend framework was introduced. **No Next.js.** This is not a merged/released capability. The exact-head PostgreSQL/HTTP/Chromium CI must pass before describing the integration as verified.

## Explicit amendment reconciliation — PR #289 continuation, 3 November 2026

This continuation completes the previously tests-only #289 branch, based on
#276 at c154bfbc5f99f76801d37903959943659c0b6a71. It does not incorporate the
newer evidence/report/image or React Records branches.

- POST `/v1/patients/{patient_id}/record-requests/{request_id}/reconcile`
  requires the existing independent patient_read, record_request_receive and
  source_read grants. The caller supplies an exact expected source, current
  replacement, case, request key and the sole operational reason source_amendment.
- The existing request row, patient and case binding serialize changes. The
  source owner's parser verifies exact original bytes, hash, document identity,
  specimen/date context and every amendment edge. Unrelated documents, stale
  replacements, stale expectations and cancelled/unreceived requests fail closed.
- A record.request.reconciled event extends the existing immutable journal.
  Its original received event is unchanged. List projections use the latest
  explicit receipt; amendment alone continues to require reconciliation.
- Retry keys are scoped to one patient/request. Their digest binds actor,
  organization, purpose, case, expected source, replacement and reason. A retry
  of an older committed intent returns that receipt even after later amendments
  or reconciliations; it cannot retarget the latest projection. The existing
  receive endpoint continues to recover its initial original receipt.
- GET `.../receipt-history` independently requires patient_read,
  record_request_read and source_read. It returns ordered source references and
  operational attribution, never source text, and records a prepared-disclosure
  event. A revoked case binding denies history; request-only list access still
  hides source references.
- Complete typed JSON is prepared under locks before final fresh authorization
  and transaction commit. History and reconciliation recheck after audit append
  too. List preparation is now covered by its final authorization check.
  Encoding, audit and authorization failures withhold content and roll back
  tentative effects. A prepared receipt does not prove HTTP delivery.
- The existing 16,384-byte POST bound covers receive and reconcile. This bounded
  implementation supports at most 256 versions per document and 256 receipt
  events per request; exceeding a stored-history bound fails unavailable rather
  than truncating history. Reconciliation rejects a new event at the limit.
  No migration, dependency, clinical permission or second state store is added.

### Verification checkpoint

The existing tests-first run [41628915787](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41628915787)
at 6c6f28c9cfe9a886ac8f3f774a441e7e8cbdbb63 executed 252 PostgreSQL/API tests:
246 passed and all six new reconciliation tests failed because the routes were
absent. This negative evidence is retained.

Those six tests remain intact. Eight additional PostgreSQL/HTTP tests cover late
read/retry authorization, audit-tail revocation, competing keys/changed actor,
unreceived/cancelled/cross-patient requests, body bounds, a forked stored journal,
source/request/patient/binding locks through actual encoding, and request-only
metadata projection without loading original bytes.
Hosted API, regression, recovery and React/browser verification of the
implementation is pending at this checkpoint. No local runtime was available;
no local execution or independent review is claimed.

Synthetic operational provenance only. No clinical approval, institutional
outreach, real patient content, deployment or merge. UI integration and
reconciliation with newer combined branch owners remain separate follow-up work.
