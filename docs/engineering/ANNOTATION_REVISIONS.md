# Correcting selected passages after record intake

Status: convergence of ordinary-text annotation revisions from [PR #190](https://github.com/OpenxIntelligence/open-intelligence/pull/190)
with PDF intake and the Patient World Model from [PR #215](https://github.com/OpenxIntelligence/open-intelligence/pull/215).
The exact integration base is `3be1106b5cd34523c4746e2df6f123048beb5659`;
its tree is `b03dc8a5d14f2bf7ca4c99a4c8b72491812015ee`.
This increment extends OI-006, OI-007, OI-009 and OI-010. Implementation and
verification are in progress; no merge, deployment or clinical release is implied.

## Patient outcome and scope

A person can save an original text or supported PDF record first, then add or correct the exact
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
   exact source-line passages, manual transcription and reason. A PDF save also
   confirms the immutable extraction hash. Invalid or
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

The source owner remains `CaseStore`, with a single original source ledger and
one immutable PDF rendition per original. This increment combines the shared
#173 descendants #190 and #215; it does not replace either with a separate
intake store. The accepted FastAPI/PostgreSQL/React H1 migration is separate.
H1 #213 and #216 currently propose different World Model response contracts
at the same route; convergence requires explicit contract review before porting
this behavior. Do not copy their competing implementations into this branch.

## Persistence and API

The existing source owner stores append-only `document_annotation_revisions`
and immutable snapshot bindings. Original bytes and `document_intake_metadata`
stay intact; `assertions` projects the latest selection set. Revision identity
is monotonic and participates in Composer freshness, even when selections
return to an earlier value. SQLite triggers protect the immutable history.

| Route | Behavior |
| --- | --- |
| `GET /api/cases/{case}/sources/{id}/annotations` | Original text or frozen PDF extraction, current selections and ordered history; no writes |
| `POST /api/cases/{case}/sources/{id}/annotations` | Exact fields: `findings`, `expected_revision`, `expected_sha256`, `confirmed_case_id`, `manual_transcription_confirmed`, `reason`; PDF additionally requires `expected_extraction_sha256`, which text requests must omit |
| Existing snapshot POST | Adds `expected_annotation_revisions`, mapping string source IDs to revision numbers |

A revision accepts up to 30 exact single-line selections and a 3–500 character
reason. The 128 KiB request limit and original 64 KiB/512-line limits remain.
An exact immediate retry returns `duplicate`; identical current selections
return `unchanged`; neither adds an event. Stale revisions reject all writes.

### Saved PDF corrections

Reading or revising saved selections never invokes the PDF parser. Validation
uses the original bytes and the immutable `source_text_renditions` record. It
rebuilds line/page anchors from stored page strings and verifies the original,
page and extraction hashes using the stored extractor descriptor. A later
extractor upgrade cannot silently change the old source's extraction identity.

The request supplies global extraction-line numbers and exact quotations.
Physical page, page-local line and page hash are derived by the server; callers
cannot supply alternative anchors. Original and extraction hashes must both
match. Historical reports keep their captured revision and PDF page anchors,
even after the current selection changes. Original downloads remain byte-identical.
No OCR or extraction-completeness claim is added.

Current source cards, Patient World Model observations/history/disagreements,
Composer, timeline and changes preserve the manual revision number and identity
alongside the original review and extraction provenance. Returning A → B → A
creates a new revision and cannot revive an old context fingerprint. User
classification stays separate from source wording and clinical approval.
Unreviewed model attempts leave questions open; manual numeric measurements
remain ineligible for the existing qualified laboratory-trend tool.

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

## Current convergence verification

Local validation used Python 3.12.14 and the exact pypdf 6.21.4 runtime.
The complete run executed 467 Python/domain/HTTP tests in 243.868 seconds:
466 passed; the inherited image-only-page rejection test failed because the
worker reached its time limit instead of returning its expected extractable-text
rejection. The unchanged test passed alone in 0.728 seconds. The rejection
remained fail-closed, and no parser/resource limit was relaxed. Hosted regression
results remain pending; the local run is not reported as fully passing.

All 146 JavaScript checks passed across eight suites. The offline data-boundary
suite passed 80 checks with 18 optional dependency skips. Compile, JavaScript
syntax, whitespace and the patient-data CI guard passed. A separate reviewer
found no blocking backend/HTTP/prompt issue and reran 54 relevant checks; those
checks overlap the full suite and are not additive.

The new PDF domain, HTTP and projection tests prove corrections and reads after
restart without re-extraction, exact dual-hash/quote/anchor validation, append-only
revision/revert identity, rollback, migration, snapshot-bound historical export,
question reopening and current patient-view provenance. Hosted Chromium must
still verify the implemented text/PDF correction journeys. Local Chrome launch
is blocked by `socket() failed: Operation not permitted`; no browser pass is
claimed from that attempt. The prior results below establish the inherited
ordinary-text baseline only.

## Prior ordinary-text verification

Executed locally: 12 new domain tests, 16 real HTTP boundary tests, one projection
test and seven new JavaScript session tests pass. Existing intake tests and
selected source/Composer/model/timeline/review regressions pass. Independent
review found no blocking defect and independently reran the domain and session
tests. The full local suite passed 378 Python/domain/HTTP tests in 94.462 seconds;
all 54 JavaScript cases passed across six existing and extended suites.
Compile/syntax, the no-patient-data CI guard and whitespace checks passed.
The implementation at `3ae915c037fc4389ad3b3a188675208834ba8a8d` passed
[exact-head CI 41553818718](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41553818718):
378 Python/domain/HTTP tests (33.841 seconds), 54 JavaScript cases, 80 offline
checks plus 18 optional dependency skips, and all six Chromium journeys. The
new journey proves original-only intake → later selections → report/demo review
→ correction → historical revision export, unchanged original download,
stale narrative rejection, explicit source reselection, 390 px layout and
delayed-response case isolation. It retains one original source version, three
annotation revisions and two report snapshots. No live model was invoked.

[Existing UI CI 41553818723](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41553818723)
also passed 378 tests and the existing integrated/source-dialog/keyboard/layout
journeys on generated merge `e789cbadf24151915c45862451966b092c6323c5`.
These overlapping regression counts are not additive. Runtime: Python 3.13.17,
Node v24.22.1 and Chrome 156.0.8078.47. The hosted logs retain inherited unclosed
SQLite resource warnings; they are not presented as a warning-free run.

Artifact `13193238470` is 878,649 bytes; its downloaded SHA-256 matched
`daf0b34fade4c715e82da19c95c91d5432860f01e608273450fc9f7ba945d728`.
The exact-head receipt and desktop/mobile screenshots were inspected. All
inputs are independently authored fictional examples; this local application
has no production patient access control or clinical validation.
