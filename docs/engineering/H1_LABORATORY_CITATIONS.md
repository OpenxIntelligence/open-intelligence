# Citations for a saved laboratory question

Journey lets an authorized patient search the fictional catalog and attach a
versioned metadata citation to one saved laboratory question. The linkage
preserves the question ID and its exact source ID, version, digest, local FHIR
Observation, source snapshot and preparation fingerprint.

The existing catalog and citation-link registry retain ownership. Migration
`0019_laboratory_citations` associates the link with its original Observation
and the rights decision that permitted storing and displaying the metadata.
New links require a current question and source, the selected metadata version
and digest, and fresh patient, case, question, source, evidence and link grants.
Search has an explicit submit action. Query terms stay in the synthetic system.

| Operation under `/composer/laboratory-questions/{question_id}` | Behavior |
| --- | --- |
| POST `/evidence-search` | Searches metadata with current rights for a current question. |
| POST `/evidence-links` | Stores an explicitly selected citation. An authorized identical retry recovers its link ID. |
| GET `/source-citation-report` | Prepares a source-reported result and currently permitted citation metadata for authorized inspection. |
| GET `/evidence-links` | Reopens the original question anchor and links. Rights restrictions withhold the record metadata. |

When a source changes, the saved question and its links retain their original
identities. Historical reads show reassessment status. The scope of a citation
is bibliographic metadata. Content appraisal, clinical applicability and
professional approval each require their own evidence and review process.

The [fictional demo](../H1_DEMO.md) describes the patient workflow. The child
pull request records the exact tested revision, verification history and release
status. The development fixture uses independently authored catalog records.
