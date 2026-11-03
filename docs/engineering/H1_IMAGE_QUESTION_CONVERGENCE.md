# H1 image custody and canonical source questions

## Purpose and existing owners

This candidate connects the existing image-custody owner to the canonical H1
source, World Model, Composer preflight and persistent-question implementation.
It follows the accepted H1 continuation recorded in the
[Notion integration contracts](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876)
and [Drive engineering record](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit).

Source parents:

- [#244](https://github.com/OpenxIntelligence/open-intelligence/pull/244),
  `3b6c466950852c20f99d57a70dd196fd2862571a`: canonical source fidelity,
  World Model fingerprints, bounded source preflight and immutable questions.
- [#242](https://github.com/OpenxIntelligence/open-intelligence/pull/242),
  `0c57f9fe86ef3ef12d24e1fd2a883dd80ddd7a3d`: exact original DICOM custody,
  explicit source-version links, independent image grants and byte retrieval.
- [#253](https://github.com/OpenxIntelligence/open-intelligence/pull/253),
  `4c197559f1858642ce44417e40b292cee6e2b156`: complete JSON encoding before
  final image-read authority and deferred-commit failure coverage. The #263
  follow-up carries that response boundary into this combined owner and extends
  it to new-image, duplicate-import and explicit-relink receipts.

The one patient registry, qualified case binding, source ledger and domain-event
journal remain authoritative. Images do not create another patient record,
source assertion, review queue or clinical interpretation. The existing
source-brief and governed-evidence/report owners remain separate integrations.

## Connected behavior

An authorized fictional case can contain an imaging report, a source-linked
question and an exact original image. Image imports, duplicate retries and image
access receipts do not change the canonical report/World Model fingerprint or
silently stale a question. The image content is not silently added to a model
input or represented as an interpreted clinical finding.

When the report is amended, old question anchors remain pinned to their original
source and require reassessment. The former current-image routes are withheld.
Explicitly attaching identical image bytes to the new source version reuses the
same immutable image object and creates a new version link. It does not revive
an old question. A new question requires a fresh preflight against the amended
canonical source snapshot.

Image metadata and original-byte access keep their independent grants. A
question grant does not authorize an image download; an image grant does not
authorize source/question disclosure. The existing qualified patient, case,
organization and purpose checks still apply.

## Prepared responses and access receipts

Image import, list and original retrieval now accept an application-owned
`prepare_response` callback, following the existing canonical source owner.
The image owner holds the patient and case-binding locks while it validates
source/image integrity and constructs the bounded response. It then refreshes
authority, appends the existing event and commits before returning the result.

Read operations reserve a fresh `ACCESS-...` ID in memory and pass it explicitly
to `PostgresSourceVersions._read_receipt(receipt_id=...)`. Image index fingerprints
exclude this ID. A preparation, permission, audit or commit failure withholds
the prepared response; a new image/link is rolled back with its transaction.
Constructing a binary `Response` object does not send its bytes.

For image metadata and import receipts, constructing a validated DTO alone is
insufficient: FastAPI can encode it after the route's transaction has ended.
The application-owned callback therefore validates the existing response model,
converts its fields to JSON values and constructs the actual `JSONResponse`
before the final authority check. The buffered JSON response is returned only
after successful commit. Import status remains 200 for an identical retry and
201 for a new object or link; the public schema and original-byte route remain
unchanged. An encoder exception or a deferred database failure must withhold
the already-prepared body and roll back that operation's effects.

These receipts describe authorization for prepared disclosure. They do not prove
client delivery, continuing permission after the final check or clinical review.
The credential file and network are not transactionally locked with PostgreSQL.

## Migration convergence

The published owner revisions retain their identities and contents:

| Published branch | Final existing revision |
| --- | --- |
| Source-linked questions | `0007_question_snapshot_contract`, following `0006_source_questions` |
| Original-image custody | `0006_image_custody` |

`0008_merge_image_questions` depends on both final revisions and performs no DDL.
An upgrade from either owner head applies the missing owner history, then records
the single merge head. Application readiness still requires exactly that one
revision; no arbitrary set of sibling heads is accepted. Historical question
fingerprints and the legacy contract labels from revision 0007 are preserved.

## Verification scope

New acceptance checks cover:

- Real PostgreSQL/HTTP report → question → image → amendment → explicit relink
  → new question, preserving original bytes, history, distinct grants and hashes.
- Authority withdrawal and failure after actual DTO/binary response construction,
  plus lock ownership and receipt ordering.
- Populated upgrades from the published image and question heads, exact readiness,
  retained owner data and migration graph identity.
- Local response-ordering regressions using the real source receipt helper. The
  transaction double in those unit tests is not PostgreSQL durability evidence.

The inherited full API/PG, reference application, React/Chromium, source-fidelity,
image restart/dump-restore and package-rights gates remain in the workflows.
Exact hosted results are recorded on the draft PR and in the existing engineering
record after execution. Local checks alone do not establish those hosted results.

### Combined recovery and encoded-disclosure acceptance

The focused acceptance follow-up preserves the implementation above and extends
the existing `apps/api/tools/verify_images_compose.py` gate. It creates real
canonical source-linked questions alongside the independently authored images,
then checks both domains across API restart, database restart and PostgreSQL
dump/restore. The restore snapshot includes every persisted question field
(text as a UTF-8 hash and byte count) and the original event journal, as well as
image bytes, links, sources and identity. Reopened HTTP responses check the
exact question text.
The same API image is explicitly pointed at the restored database before any
restored HTTP behavior is claimed.

The flow preserves the v1 question's source/line/hash after amendment, requires
reassessment, explicitly relinks the same images to v2 and saves a fresh v2
question. Restored same-key retries must preserve question IDs without creating
another question or creation event. Source-access receipts are separate and may
advance on a successful authorized retry. Independent source/question/image
grants and a restored revoked binding must continue to deny access without
committing an unauthorized receipt.

`test_image_disclosure_authority.py` preserves six directly owned regression
methods from the #253 response-boundary work, with extended import coverage
and decoded PostgreSQL JSONB metadata. It changes the operation
grant, patient-read grant, patient scope, actor, organization, purpose and expiry
after actual metadata or binary response preparation. It also removes the
authority provider, forces preparation failure and observes real patient/case
locks before the matching receipt commits. These checks complement the existing
new-object, duplicate and relink preparation tests; they do not introduce another
authorization implementation.

The encoding regression observes the real framework JSON encoder, then either
withdraws the operation grant or raises an encoder error for an index, new
object, duplicate or explicit relink. A separate regression fails an actual
PostgreSQL deferred constraint at commit, after JSON or binary preparation.
It verifies no committed receipt or changed custody, a sanitized error, and
successful later retrieval of the unchanged original bytes.

The follow-up changes the two image JSON response callbacks, tests, the existing
recovery helper and documentation. Public API contracts, published migrations,
dependencies and original source owners remain unchanged. The first #263 head
passed the earlier recovery and DTO-preparation checks; the later encoding
regressions and fix require their own exact-head result. Inspect the PR's
evidence sequence rather than treating the earlier success as final verification.

## Boundaries

The complete-JSON response boundary in this follow-up covers image metadata and
image import receipts. Canonical source, World Model, Composer, question and
review-return responses require their own equivalent encoding checks. Inspection
of the source/question owners and #262 at
`f5f135a3b72e2c82ed479d83fb524e3cc958b9df` found typed DTO returns with later
framework encoding; the exact original-source response also needs review.
Source-import and record-receive repairs are already owned by #265 at
`6299eea666a1a014bc239ea7a7ce8f6971380021`; review and reconcile that work rather
than introduce a competing fix. This is an observed ordering limitation, not a
claim that authority-race
tests have run against those routes. Preserve their owners and add targeted
real-serializer regressions before extending the prepared-response pattern.

The existing image profile is unchanged: independently authored fictional
uncompressed Explicit VR Little Endian single-frame 16-bit MONOCHROME2 CT;
2 MiB per object, 256 objects/64 MiB per case. Reuses #242's pinned code-only
pydicom runtime and unchanged supplier/license/notice checks.

There is no new DICOM viewer, PACS service, diagnostic interpretation, AI model,
biomedical evidence integration, professional approval, real identity/consent,
clinical authorization or deployment. Source questions remain unsubmitted for
clinical review. This is a combined development increment on the accepted H1
stack, not completion of the platform or migration of the PDF/report reference.

Backlog: OI-006 source provenance, OI-007 persistent questions, OI-009 amendment
reassessment and OI-013 scoped authorization/recovery remain partially covered.
