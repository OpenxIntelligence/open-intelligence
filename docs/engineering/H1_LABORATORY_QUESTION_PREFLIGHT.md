# H1 typed laboratory question preparation

## Delivery state

**Locally implemented and self-reviewed; not published, not merge-ready, not deployed.**
This bounded increment continues #428 under #424/#425. It does not close those
issues or create a saved question, evidence report, review, task or model run.

The base is the retained source archive from draft #473, remote commit
`9ea4560fc03be567e8383f9b145fc8eaef0cd140`. Artifact `13368518149` has SHA-256
`d6fa1e0f161738c93955d886033fab0bccf2ea0cf4094265627a93a844d30af8`; its commit marker
matched. Local Git history was reconstructed from the archive, not fetched from
GitHub; local commit identities must not be described as remote ancestry.
Sibling #471 migration convergence and #475 Journey navigation are not included.
No parent test result is claimed as verification of this patch.

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
response and roll back that transaction. Offline routing tests simulate the
transaction boundary; the new real PostgreSQL cases below are still required
to qualify actual rollback and locking.

## Verification actually executed

- 13 new typed-preparation tests passed after a genuine missing-behavior red run
  (34 failing assertions/subtests, no test errors). An earlier fixture-authoring
  attempt also had two Decimal encoder errors; those were repaired before that
  genuine red run and are retained in the delivery logs.
- 9 new FastAPI ASGI/routing tests passed after 11 expected missing-route
  failures. These execute real routing and response serialization with simulated
  source-owner transactions and authority callbacks, not a PostgreSQL server.
- The final combined focused run passed all 45 test methods: the 22 new methods,
  8 inherited laboratory-parser methods and 15 inherited original-integrity
  methods, with zero failures or skips. These counts overlap earlier runs and
  must not be added as independent test coverage.
- Full API discovery before changes: 246 entries, 65 import errors and 27 skips.
  After changes: 268 entries, the same 65 named import errors and 27 skips. All
  import errors end in missing `pydicom`. This is not a full-suite pass.
- Full reference suite: 765 tests executed, with 9 failures and 8 errors, all in
  PDF-intake tests at the exact-version dependency guard. A separate rerun of the
  17 PDF-intake tests on the unchanged base reproduced the identical failure/error
  names. Installed pypdf is 5.9.0; the code requires exactly 6.21.4. No dependency
  pin or assertion was weakened. Existing SQLite ResourceWarnings are retained.
  An earlier 35-second reference attempt timed out and is not completion evidence.
- Syntax compilation and whitespace checks passed.

Five new PostgreSQL/HTTP test methods were authored inside the existing
laboratory fixture. They cover nonpersistent preparation and read receipts,
independent grants and scope, amendment/history, revocation after serialization,
and audit-tail denial/serialization rollback. **None was executed here.**
The local environment also lacks `pg8000`, PostgreSQL and Docker. Installed
Python/package versions are not the project's pinned hosted environment.
Full API/OpenAPI application tests, PostgreSQL locking/rollback, browser,
restart/backup/restore and exact combined-head CI remain unqualified.

## Follow-through required

1. Reconcile this patch with the selected integration head, including relevant
   #471/#473/#475 changes, without overwriting source, migration or UI owners.
2. Run the pinned dependency/rights gates, the full API suite and the five new
   real PostgreSQL/HTTP cases. Preserve negative authorization assertions.
3. Design and review one forward-compatible typed-anchor extension to the
   existing saved-question owner. Preserve every old text-line question and
   historical report; do not create a second question ledger.
4. Connect deliberate patient UI selection to that typed question, then prove
   question/evidence/report/review continuity, source amendment and reassessment,
   revoked access, retry, restart and restore on one exact commit.
5. Obtain independent source/security/rights review before an explicit merge or
   release decision. No real patient data or clinical validation is authorized.
