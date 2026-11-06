# Preparing a question about a fictional laboratory result

A caller can prepare a human-authored question against one current, source-owned
FHIR Observation. This is a preview. It neither saves the question nor runs an
investigation. The API is for independently authored synthetic records.

Based on the accepted H1 application at `62e218e1e2bd6996bb126fcc1ea956fcf18199e6`
(#481), including the #471 migration join and #473/#475 laboratory workspace.
The earlier #473-based local patch (SHA-256
`337be71b6c34fffac73b348d3dafe425faf2d14e42bc95e9d86dea9f22adec4e`)
is the source of the preparation implementation; its historical, partial test
results are not evidence for this revision. Sibling #503 publishes the same source preparation on #480. The projection, API contracts
and route are byte-identical to its 73bfdb75; this main-based integration retains the
accepted request-size protections and uses the existing loopback route-test harness.
No schema, model, dependency or permission changes.

## Why this step

The existing Composer preflight selects an exact text assertion by source ID and
line. Laboratory results instead have immutable source ownership and local FHIR
Observation references. Inventing a text line or silently copying a laboratory
value into a different ledger would misstate provenance. This change adds typed
preparation alongside the original text contract, leaving saved-question
storage and downstream consumers unchanged.

## Contract

`POST /v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-preflight`

The caller supplies `synthetic: true`, `source_id`, a local
`observation_reference`, `expected_source_snapshot_sha256`, and a literal
human-authored `question`. It supplies neither laboratory values nor a source
line. The existing request guard caps the body at 16,384 bytes. Unknown fields,
unsupported references, mismatched patient/case context, and stale or absent
anchors are rejected.

The response is `oi.synthetic-laboratory-question-preflight/1`. It pins the
current source ID/version/hash and World Model fingerprint, plus the exact
Observation, Specimen and DiagnosticReport references. Literal value precision,
unit/code strings, separate dates and absent-result reasons are preserved. No
terminology validation, unit conversion or clinical interpretation is performed.
The content fingerprint excludes the changing access receipt identifier.

The response explicitly sets `durable_question_created`,
`durable_review_connected`, `biomedical_evidence_rights_verified`,
`model_execution_authorized`, and `clinical_approval` to false. This preparation
is not an executable authorization and cannot be reused as permission for a
later write. No public FHIR resource REST interaction is added or advertised.

## Authority and source ownership

The route uses existing patient, source-read and Composer-context-read grants.
It calls the existing source owner's transaction: active binding and original
custody validation, then a current laboratory-child read, typed projection, full
JSON serialization, fresh authority checks around the existing source access
event, and commit. The route returns the already-materialized response, bounded
to 65,536 bytes, with no-store and nosniff headers. It creates no source, clinical
assertion or question row. A successful read does append the existing authorized
source-read receipt; it is not a zero-write database operation.

Final denial, serialization failure or source audit failure must withhold the
response and roll back the transaction.

## Patient workflow

In Journey, open an authorized case and choose a result under **Prepare a
question about a result**. Selection and editing are local. On **Check question
against report**, the server rechecks access and the current source. The client
compares the returned patient, case, question, source snapshot, report version
and digest, full literal result, and limitations with the selected observation.
Editing, changing the selection or leaving the scope discards the earlier preview.
A stale report or denied response clears the projection. A preview is never a
saved question, a message to a clinician, or authority for a later write.

## Verification

The original patch put five PostgreSQL test methods below the module's
`unittest.main()` guard. Normal discovery would omit all five. They now belong
to `LaboratoryFHIRHTTPTests`; require individual execution in the full suite.
The nine route tests use the existing loopback server and Python standard HTTP
client; no optional TestClient dependency is required.

- Local: 36 projection, parser and source-integrity tests passed. These do not
  exercise the network, PostgreSQL or transaction commit.
- Hosted acceptance: check this revision's API run for all five laboratory
  preparation tests, all nine scoped route tests, migration and regression checks,
  and existing recovery jobs. The PR records actual results by commit.
- The connected Chromium gate exercises explicit selection, preparation before and
  after an amendment, absent results, unchanged saved-question history and denied
  Composer access. Existing recovery jobs exercise existing durable records;
  there is no new durable question or recovery claim. No question
  or report is created. A future save must revalidate authority and the exact
  source/Observation before committing to the existing question owner.

Tracked with OI-007 and issues #425/#428. No deployment or clinical approval.
