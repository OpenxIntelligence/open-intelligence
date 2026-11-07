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
| GET `/source-citation-report/versioned` | Returns the version-2 inspection and a SHA-256 fingerprint over its content. The changing read receipt is excluded from this fingerprint. |
| POST `/source-citation-report/snapshots` | Requires the dedicated capture grant, a request key, and the fingerprint of the opened report. Stores the source anchor, ordered citation references and capture fingerprint. |
| GET `/source-citation-report/snapshots` | Lists captures under the question’s current report-read permissions. |
| GET `/source-citation-report/snapshots/{snapshot_id}` | Reopens the originally captured citation set. Current content rights and source freshness can change the visible report and its live fingerprint. |
| GET `/source-citation-report/snapshots/{snapshot_id}/review-returns` | Requires `review_queue_read` alongside report-read permissions. Returns the exact opened context and nonterminal request history. |
| POST `/source-citation-report/snapshots/{snapshot_id}/review-returns` | Requires `review_return` and the checked queue, captured-report and opened-report fingerprints. Records the reason and trusted actor in the existing review owner. |
| GET `/evidence-links` | Reopens the original question anchor and links. Rights restrictions withhold the record metadata. |

A capture stores references and a fingerprint. Each saved question supports up
to 100 inspections. Opening one projects its original ordered citation set
under current permissions. Metadata hidden at capture stays hidden after a
later grant. If visible content or freshness changes, the reopened report can
have a different fingerprint from the captured version. The write checks that
the current content matches the submitted fingerprint. Its audit event records
the access receipt from capture. A qualified reviewer’s disposition is still
an outstanding operation. A nonterminal human request for independent verification
is now connected to each reopened saved inspection through the existing
`question_review_receipts` owner. The additive `0026_laboratory_review_returns`
migration records a typed inspection origin; it preserves earlier text-question
contracts and refuses downgrade once laboratory returns exist.

The user reopens an inspection, checks its verification requests, enters a reason,
and returns that exact visible version for independent verification. Both the
captured hash and reopened hash remain traceable. A changed source or citation
permission moves earlier requests into prior history; it does not erase them.
A newly returned amended inspection still requires source reassessment. An
ambiguous reply can be retried with the exact original command after fresh
authorization. New altered commands fail without a return or event. No external
notification, professional identity verification or completed review is implied.

Verification: focused API/real-PostgreSQL tests, strict client state-machine tests,
the built React journey, and the existing FHIR restart/backup-restore probe cover
this increment. Exact source revision and actual hosted results belong to the
stacked pull request; a donor pass is not a combined pass.

When a source changes, the saved question and its links retain their original
identities. Historical reads show reassessment status. The scope of a citation
is bibliographic metadata. Content appraisal, clinical applicability and
professional approval each require their own evidence and review process.

The [fictional demo](../H1_DEMO.md) describes the patient workflow. The child
pull request records the exact tested revision, verification history and release
status. The development fixture uses independently authored catalog records.
