# H1 PostgreSQL: canonical record request → exact received original-source receipt

**Status:** synthetic-only, reviewable integration candidate stacked on original source owner [PR #187](https://github.com/OpenxIntelligence/open-intelligence/pull/187). Do not adopt or deploy as clinical software without authorization, security, data-rights, and source-owner reviews.

## What is actually connected

Existing first-party owners remain authoritative:

- `identity.identity_patients`: opaque canonical patient and its append-only `identity.identity_domain_events` journal
- `coordination.patient_case_bindings`: reviewed-but-fictional qualified patient/case relationship and its revocation
- `coordination.record_requests`: original request/intention, category, cancellation guard, revision, and organization
- `clinical_source.source_versions`: original bytes, SHA, current/historical versions, source kind, and authored assertions

The new `POST /v1/patients/{patient_id}/record-requests/{request_id}/receive` links an **already imported, exact original** to an existing requested item. It does **not** reimport/copy the original or send a request to an institution. It requires independent `patient_read`, `record_request_receive`, and `source_read` scopes plus an active, correct canonical patient/case organization mapping. A mismatched case, different patient, different category, cancelled request, superseded/unrecognized source, or corrupt original hash fails closed.

A single append-only `record.request.received` event records `request_id`, `case_id`, `source_id`, SHA and version in the **existing patient identity event journal** within the existing row-locked transaction. There is **no second received-source table or mutable source pointer**. Reads project `received` from the event; source disclosure requires its separate `source_read` grant. A received request cannot subsequently be cancelled. Identical retry returns a duplicate without another event; changed source references are rejected. The source may later be amended, but the previous receipt stays historically pinned and projections show `source_superseded_reconciliation_required` until a separate, explicitly reviewed reconciliation action exists.

A revoked case relationship hides the exact source reference and blocks subsequent source use, without fabricating a deletion of history. `record_request_read` alone may show that a record has been received but must not reveal source identifiers or bytes. `source_original_read` is still required to view original source text.

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
