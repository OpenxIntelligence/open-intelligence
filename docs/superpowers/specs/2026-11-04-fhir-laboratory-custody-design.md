# FHIR R4 Laboratory Custody and Typed Projection Design

## Intent
Persist the already-validated synthetic FHIR R4 laboratory bundle as a first-class modality in the existing H1 source owner, preserve exact original bytes, and expose typed source-reported laboratory observations in the Patient World Model/longitudinal projection.

## Constraints
- `clinical_source.source_versions` remains the one canonical source/version owner.
- FHIR rows are dependent children keyed to a canonical `source_id`; they are not a second patient/source ledger.
- Exact incoming JSON bytes and SHA-256 are preserved without normalization.
- Persisted intake requires one final DiagnosticReport so it has a stable external document identity.
- Changed bytes for the same DiagnosticReport require explicit `expected_previous_source_id`; no silent amendment.
- Request-key replay is exact: same key/same intent recovers; same key/changed intent conflicts.
- Typed observations remain `source_reported`, `clinical_review=not_performed`, with no normal/abnormal interpretation, unit conversion, diagnosis, recommendation, or model execution.
- Final patient + source-import authority is rechecked after response serialization and before commit.
- Generic source listing/original reading and World Model reuse the existing source-read/original-read permissions.
- Synthetic fixtures only.

## Approach
Add forward migration `0016_fhir_laboratory_sources` with immutable dependent intake, observation and command tables. Implement `PostgresLaboratoryFHIR` as a modality adapter that writes the canonical source row and dependent typed rows atomically. Extend source integrity validation to dispatch FHIR rows through the existing strict parser, and extend the existing World Model with additive typed laboratory observations and a time-ordered laboratory timeline.

## Non-goals
No external FHIR server, terminology expansion, clinical reference ranges, interpretation flags, unit conversion, LIS connection, real PHI, or production interoperability certification.
