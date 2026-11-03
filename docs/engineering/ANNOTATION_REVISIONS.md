# Correcting selected passages after record intake

Status: implemented locally; hosted browser verification pending. Extends OI-006, OI-007, OI-009 and OI-010
on verified ordinary-text intake PR #173, head
`243bfec0fb36121868714dd36c6dd591243114da`. No clinical release is implied.

## Patient outcome and scope

A person can save an original text record first, then add or correct the exact
passages they want to track. Each confirmed change retains the previous
selections, its reason and its source. The original document, document dates
and document version stay unchanged. An annotation correction is a separate
event from receiving an amended medical record.

This is a reversible extension of the existing source owner. It adds no
dependency, patient registry, source ledger, model, clinical review authority or
alternative stack. The accepted H1 migration remains separately owned.

## Contract and acceptance

1. Read-only review exposes the exact original, current selections and prior
   annotation revisions. Current manual-intake sources can be edited;
   structured fixtures and superseded originals cannot be edited here.
2. A save confirms the case, original hash, expected annotation revision,
   exact source-line passages, manual transcription and reason. Invalid or
   stale saves leave all records unchanged. Concurrent editors cannot silently
   replace one another's work. Identical retries do not duplicate history.
3. Original bytes and initial intake confirmation remain immutable. Append-only
   revisions own selection history; the existing assertions table is the
   current projection. A revision can add, replace or remove selections,
   including returning to an earlier selection without reusing its identity.
4. A correction invalidates dependent drafts and model work in the same
   transaction and reopens affected questions. Earlier review actions remain
   inspectable. It does not approve a clinical conclusion.
5. Reports bind the annotation revision used at creation. A later export never
   substitutes newer selections for the earlier report's selections. Snapshot
   saves include expected annotation revisions to reject stale browser drafts.
6. Newly captured model investigations retain their input annotation revision
   references. Historical inputs that were not recorded are labelled as such;
   migration must not invent them.
7. Existing source browsing, timeline, Composer, question/report and original
   download paths remain connected. A pending edit survives errors and cannot
   cross a patient-case switch. The actual browser journey includes narrow
   viewport checks and original-byte comparison.

## Current work ownership

The fresh repository audit found no competing post-save annotation correction
implementation. PR #179 integrates the separate structured-file patient entry
from #166 with the clinical/report core. Its `web/intake.js` exports `OIIntake`,
whereas #173's ordinary-text component exports `OpenIntelligenceIntake` under
the same filename. Later integration must reconcile asset names, mounting and
case-switch guards explicitly; neither file should overwrite the other.
PR #182 owns PostgreSQL patient/source-case bindings, not annotation history.

## Persistence and API

The existing source owner stores append-only `document_annotation_revisions`
and immutable snapshot bindings. Original bytes and `document_intake_metadata`
stay intact; `assertions` projects the latest selection set. Revision identity
is monotonic and participates in Composer freshness, even when selections
return to an earlier value. SQLite triggers protect the immutable history.

| Route | Behavior |
| --- | --- |
| `GET /api/cases/{case}/sources/{id}/annotations` | Original lines, current selections and ordered history; no writes |
| `POST /api/cases/{case}/sources/{id}/annotations` | Exact fields: `findings`, `expected_revision`, `expected_sha256`, `confirmed_case_id`, `manual_transcription_confirmed`, `reason` |
| Existing snapshot POST | Adds `expected_annotation_revisions`, mapping string source IDs to revision numbers |

A revision accepts up to 30 exact single-line selections and a 3–500 character
reason. The 128 KiB request limit and original 64 KiB/512-line limits remain.
An exact immediate retry returns `duplicate`; identical current selections
return `unchanged`; neither adds an event. Stale revisions reject all writes.

Missing snapshot mappings mean revision 1 for compatibility with the earlier
API, so any corrected source requires an explicit current revision. The UI
always supplies manual source revisions and retains their earlier values while
an unfinished narrative is present. Explicit source reselection captures the
current revision after the author reviews the change.

Pre-revision databases migrate their known initial selections and snapshot
bindings to revision 1. Legacy model inputs remain `not_recorded`. New model
receipts capture revision references and the bounded manual assertions supplied
to prompt construction. These receipts do not prove a live model executed.
Revision provenance changes prior manual Composer fingerprints conservatively;
legacy structured-source fingerprints and prompt golden checks stay unchanged.
The existing durable computation owner reconciles freshness on read/execute.

## Verification

Executed locally: 12 new domain tests, 16 real HTTP boundary tests, one projection
test and seven new JavaScript session tests pass. Existing intake tests and
selected source/Composer/model/timeline/review regressions pass. Independent
review found no blocking defect and independently reran the domain and session
tests. The full local suite passed 378 Python/domain/HTTP tests in 94.462 seconds;
all 54 JavaScript cases passed across six existing and extended suites.
Compile/syntax, the no-patient-data CI guard and whitespace checks passed.
Hosted Chromium results are pending. All inputs are independently authored
fictional examples; this local application has no production patient access
control or clinical validation.
