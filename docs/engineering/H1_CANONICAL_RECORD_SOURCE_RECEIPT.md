# H1 PostgreSQL: canonical record request → exact received original-source receipt

**Status:** synthetic-only, reviewable integration candidate stacked on original source owner [PR #187](https://github.com/OpenxIntelligence/open-intelligence/pull/187). Do not adopt or deploy as clinical software without authorization, security, data-rights, and source-owner reviews.

## What is actually connected

Existing first-party owners remain authoritative:

- `identity.identity_patients`: opaque canonical patient and its append-only `identity.identity_domain_events` journal
- `coordination.patient_case_bindings`: reviewed-but-fictional qualified patient/case relationship and its revocation
- `coordination.record_requests`: original request/intention, category, cancellation guard, revision, and organization
- `clinical_source.source_versions`: original bytes, SHA, current/historical versions, source kind, and authored assertions

The new `POST /v1/patients/{patient_id}/record-requests/{request_id}/receive` links an **already imported, exact original** to an existing requested item. It does **not** reimport/copy the original or send a request to an institution. It requires independent `patient_read`, `record_request_receive`, and `source_read` scopes plus an active, correct canonical patient/case organization mapping. A mismatched case, different patient, different category, cancelled request, superseded/unrecognized source, or corrupt original hash fails closed.

A single append-only `record.request.received` event records `request_id`, `case_id`, `source_id`, SHA and version in the **existing patient identity event journal** within the existing row-locked transaction. There is **no second received-source table or mutable source pointer**. Reads project `received` from the event, and the request's `updated_at` is projected from that exact event's `occurred_at` rather than incorrectly retaining request creation time. Source disclosure requires its separate `source_read` grant. A received request cannot subsequently be cancelled. Identical retry returns a duplicate without another event; changed source references are rejected. The source may later be amended, but the previous receipt stays historically pinned and projections show `source_superseded_reconciliation_required` until a separate, explicitly reviewed reconciliation action exists.

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

## H1 workspace connection

A Records panel now connects the same existing patient-scoped request API to
missing-record tracking, cancellation and an exact received-original pointer.
The transient controller has no token, permission issuer or persistence layer:
`RegistrySession` supplies its scoped credential transport and resets on
patient/session changes. The UI preserves status and source disclosure separately,
shows amended historical receipts without retargeting, and never marks receipt
as clinical approval. Current compatible imported sources are selected explicitly.

Create requests retain a stable request key after uncertain responses; cancel
and receive retain their complete original command. Recovery does not replace
an earlier source version with the latest source. Denied recovery leaves the
original uncertain intent pending. Patient rechecks/creation cannot silently
discard that state. Explicit disconnect/reload clears local-only intents and
requires a durable history check. No automatic provider request or clinical
communication is introduced.

Only frontend source, focused client/browser tests, and these existing owner
records change. The API's current authorization/transaction contracts remain
unchanged: the final transaction-bound refresh described above applies to
source import and receive, not a new claim about every list/create/cancel path.
Production authority, independent review and deployment remain separate gates.

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
