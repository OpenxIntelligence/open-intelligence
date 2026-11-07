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


## Institutional source identities — connected construction continuation

Base #624 `631c3e0cea30d4b859a2e428d200d352c97c6567` preserves the integrated
patient permissions, history, diagnostic workspaces and Composer. #560's separate
amendment reconciliation remains a convergence dependency; it has not been silently
included or declared merged. Existing #99/#115 and #121 retain intake/MRT-01 ownership.

Migration `0030_case_source_identities` extends the canonical case-binding owner
with immutable institution/system/subject associations and quarantined conflicting
association attempts. It backfills each original primary identity without changing
the parent case or source rows, seeds subsequent primary identities transactionally,
retains unique qualified identities, and refuses downgrade with additional history.
The same patient journal records actor, purpose and exact command identities.

GET/POST `/v1/patients/{patient_id}/cases/{case_id}/source-identities` require the
existing independent case-binding read/create grants, active patient/case and matching
purpose. Writes retain exact retries and quarantine a qualified identity already
owned by another case without disclosing that case. Held associations cannot import.
Current authority and actual response encoding precede commit. There is no automatic
identity matching, release from quarantine, separate patient registry or consent claim.

Laboratory preview/import accepts an optional `source_identity_id`. Omitted selection
retains the primary mapping and legacy retry digest. Explicit choices bind that identity
into the import command and source metadata. Same report IDs across institutions fail
closed, including byte-identical payloads; namespacing colliding report IDs is unfinished.
Records provides an explicit identity refresh/selection, then preview/import and exact
original reopening with the institution and source patient identifier. Establishing new
associations is currently an operator API action, not a patient self-authorization flow.
The existing uncertain import preserves the selected identity and request on exact retry.

Local checks at the initial implementation: 826 client tests, production build,
17 parser/graph/config checks, strict new wire test, architecture and synthetic-data
boundary pass. Ten new PostgreSQL tests are skipped locally because no PostgreSQL16
server or Docker executable is installed. Hosted acceptance remains pending until its
exact source, jobs and counts are recorded in the draft PR. The tests cover three
institutions, explicit amendments, original bytes, collision quarantine, wrong scope,
independent grants, concurrent retry, late revocation/encoding rollback, populated
migration/downgrade and actual pg_dump/pg_restore with restored HTTP and denial.

Remaining: first-party identity review/disposition UI, ambiguous-original quarantine
intake and release, namespaced institutional report identifiers, #560 convergence and
full MRT-01 scientific/clinical-review acceptance. This source identity foundation is
synthetic engineering work; no merge, deployment, real patient data or clinical effects.


Follow-up self-review retained concurrent legacy primary-create recovery after the
qualified-identity lock and updated explicit migration fixture cleanup for the owned
child table/functions. Local reference regression passed 1,036 tests on an exported
source tree, and the 31 architecture tests passed. The full initial local API run
attempted 1,055 tests with 75 AF_UNIX permission errors and 638 database skips, without
assertion failures; it is not database acceptance. The initial local npm install
included an optional binary lacking its LICENSE/NOTICE and failed the rights gate.
Reinstalling with the existing CI `--omit=optional --ignore-scripts` flags passed all
13 controls and the inventory (18 installed, two optional entries uninspected).
