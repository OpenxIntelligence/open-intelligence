# Laboratory question preparation: a typed, source-owned first step

## Goal and boundary
Continue #428 and #425 on the exact #473 source artifact at
`9ea4560fc03be567e8383f9b145fc8eaef0cd140`. Allow an authorized caller to prepare
one human-authored question against an exact current laboratory Observation.
This is a read-only preparation contract, NOT persistence of a typed question,
an evidence report, a model call, clinical review or completion of #428.

## Existing mismatch
`PostgresSourceComposerPreflight.preview_locked` selects only text assertions
by `(source_id, source_line)`. Laboratory observations live under the same source
owner but use resource references. An observation must not acquire an invented
text line or enter the existing text-only question table with false provenance.

## Approach
Extend the existing Composer preflight owner with a separate typed preparation
contract. Reuse `PostgresSourceVersions.list` for original integrity, the active
patient/case lock, response preparation, final authority, audit and commit.
Read current laboratory children only inside that callback and reuse the existing
World Model projection. Select by exact source version plus Observation reference.
Keep the text contract and saved questions unchanged. Broader polymorphic
question persistence is deferred until a reviewed forward migration and combined
PostgreSQL/recovery acceptance exist; no second question or source ledger.

## Acceptance
Exact patient/case, source ID/version/hash, Observation/Specimen/DiagnosticReport
references, literal numeric precision/units or absent reason, and separate dates
must survive preparation. A fresh source snapshot is required. Missing, foreign,
superseded or ambiguous anchors fail closed. Question text remains literal.
Receipt IDs do not affect the content fingerprint; question or source context does.
`source_read` and `composer_context_read` are both required, in addition to the
existing patient grant. Full JSON serialization happens before final authority
and source receipt commit; denial or serialization failure withholds output.
Request bytes are bounded by existing middleware. Unknown request fields are
rejected. No new permission, database, dependency, FHIR REST claim or clinical
interpretation is introduced. Only independently invented fixtures are used.

## Integration status
#471 migration convergence and #475 Journey navigation are siblings, not silently
included. The local workspace is reconstructed from a retained source archive;
local Git commit IDs are not remote ancestry. Full PostgreSQL/browser/recovery
qualification and publication remain separate gates.
