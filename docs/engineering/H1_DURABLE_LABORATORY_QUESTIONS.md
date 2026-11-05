# Saving a question about a laboratory result

After a patient checks a question against a current laboratory result in Journey,
they can save it and reopen its original source reference. Preparation and save
are separate actions. Question text, the local FHIR Observation reference, source
version and original file digest retain the identity of the result the patient saw.

A case supports up to 250 laboratory questions in this bounded workflow. Once full,
its existing questions and exact save receipts remain available.

The existing question registry owns the question ID and request key. The new
typed anchor refers to the existing source-owned laboratory child. A retry
uses the same request key and complete original intent. A new save rechecks
the source and preparation fingerprints in the source transaction. Active
patient, organisation, case, purpose and operation grants apply to both paths.
The API encodes its response before final grant checks, audit and commit.

| Operation | Existing grants in addition to patient access | Outcome |
| --- | --- | --- |
| POST to `/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-questions` | Source read, Composer context read, question create | First save returns 201. An exact retry returns 200 and the existing question ID. |
| GET on the same path | Source read, question read | Reads saved laboratory questions with a fresh access receipt. Each carries its original reference and current reassessment status. |

Text-line question history and laboratory question history have separate read
contracts over the same question registry. Briefs, evidence reports, clinical
review and follow-up for a laboratory question require a future typed consumer.
The current workflow supports independently authored fictional laboratory records.

## Acceptance

Use [the fictional demo](../H1_DEMO.md) to try Journey. Acceptance covers a
mixed case with text and laboratory questions, independent grants, immutable
source anchors, lost-response retry, an amendment that preserves the earlier
identity, and active and revoked PostgreSQL restore. The pull request records
the revision tested, observed results, failure history and release status.
