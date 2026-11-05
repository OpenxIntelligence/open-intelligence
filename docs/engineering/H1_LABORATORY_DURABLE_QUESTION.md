# H1 durable typed laboratory questions

## Scope

This increment extends the existing `investigation.source_questions` owner with an explicit
FHIR Observation anchor. It does not create a second question ledger and does not invent a
text line for structured laboratory data.

## Storage contract

Migration `0018_typed_question_anchor` adds `anchor_kind` and `observation_reference`,
keeps legacy text questions as `text_line`, and allows `source_line` to be null only for
`fhir_observation`. A database CHECK enforces exactly one anchor representation. The typed
reference has an FK to the existing immutable `clinical_source.fhir_laboratory_observations`
row. The insert guard still requires the active patient/case and a current source version/hash.

## API boundary

`POST /v1/patients/{patient_id}/cases/{case_id}/questions/laboratory` persists one
human-authored question after re-running the current typed preflight under the source-owner
transaction. `GET` on the same path lists only typed questions and their current/reassessment
state. The legacy `/questions` path remains text-line-only so Review, evidence, manual-passage
and follow-through consumers cannot accidentally treat a resource reference as a text line.
Unsupported downstream entrypoints explicitly filter to `anchor_kind='text_line'`.

## Safety

The question remains unreviewed and non-clinical. The new list states that clinical Review,
evidence workflow and follow-through are not connected. Exact retry is idempotent. Source
amendment preserves the original question and marks it `source_reassessment_required`. Final
question-create authority is checked after response serialization and before commit.

## Next slice

Extend one downstream path at a time using a typed anchor union; do not fake `source_line`.
The first candidate should be Review/source packet, followed by evidence/report and then
follow-through, each with amendment/revocation/restart/restore acceptance.
