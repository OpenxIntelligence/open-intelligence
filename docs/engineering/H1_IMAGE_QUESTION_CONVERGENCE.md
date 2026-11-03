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

## Boundaries

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
