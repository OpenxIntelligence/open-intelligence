# H1 reviewed ordinary documents

Draft [#323](https://github.com/OpenxIntelligence/open-intelligence/pull/323) extends
#315's converged H1 workspace. This is fictional engineering, unmerged and undeployed.

Records now previews ordinary UTF-8 text and text-bearing PDFs without saving a
source. Explicit case, metadata, hash and manual-transcription confirmation saves
exact original bytes in the existing canonical source ledger. The frozen rendition
retains numbered lines and physical PDF pages. Selections are attributed manual
classifications, never source-authored assertions or clinical approval. A correction
appends an immutable revision with a reason; exact retries recover one receipt.
Amendments retain earlier originals and histories. The browser downloads fresh,
authorized bytes and checks their hash before creating the download.

Apply `0012_reviewed_documents` explicitly. The new immutable source-owned children
are `clinical_source.document_intakes` and `annotation_revisions`; no parallel
patient/source store is introduced. The bounded parser comes from reference #249
at `af72cd6ad5d4e934aa3168334b1592bfdce35e51`, using hash-locked pypdf 6.21.4 and its
recorded BSD-3-Clause notice. Extraction runs outside write locks in a constrained
worker after initial authorization. Response encoding and final authority checks
remain inside the authoritative transaction.

## API and limits

Prefix: `/v1/patients/{patient_id}/cases/{case_id}/documents`.

| Operation | Additional grants |
| --- | --- |
| POST `/preview` or collection import | `source_import` |
| GET collection | `source_read` |
| GET `/{source_id}` rendition/history | `source_read`, `source_original_read` |
| GET `/{source_id}/original` | `source_original_read` |
| POST `/{source_id}/annotations` | `source_import`, `source_original_read` |

All operations also require existing patient, organization, case and purpose
checks. Maximum original/extracted UTF-8 size is 64 KiB, with 20 PDF pages, 512
lines, 30 selections of at most 1,200 characters, and 64 revisions. Ingress is
262,144 bytes. Client reads stream within a 32 MiB history bound (including worst
case escaped Unicode), with a separate 64 KiB original bound. No OCR is provided.

## Verification and remaining work

The draft PR records final commit-specific hosted results. Local verification
covers strict wire contracts, isolated parser tests, client state and production
build. The independent whole-change review found a too-small history response
limit; regressions reproduce the Unicode history failure and verify bounded
stream cancellation after its correction.

Hosted acceptance runs real PostgreSQL migrations, immutable history and rollback
checks, the built React PDF journey (page-two correction, exact binary download,
restart, denied original access and 390px layout), and container recovery probes.
Parent #349 compared reviewed-document rows through dump/restore and checked
history/retry after API/database restart; it did not serve document HTTP from the
restored copy. The dependent recovery continuation extends the existing source
probe to recreate the API on an active restored database, confirm its configured
engine target, and read both UTF-8/CRLF text and a two-page fictional PDF. It checks
exact binary bytes/hashes, frozen page/line anchors, complete correction history,
collection identity, and exact intake/correction retries across API/database restarts.

Independent source-read, original-read, import and patient grants, changed patient
scope/purpose, absent credentials and a wrong case exercise fail-closed behavior.
A revoked binding is backed up from the restored copy and restored again with all
grants enabled; reads, preview, import and correction retries must remain denied.
Complete application rows and sequence states are compared. Returned access events
must match their exact patient/case/source/hash/actor scopes in the serving copy;
original and intermediate copies must remain unchanged. No runtime, schema,
migration, permission or dependency changes are part of this increment.

Local negative controls exercise the actual recovery assertion against changed
originals/history, wrong or missing receipts and sequence drift. Hosted execution
is pending until a commit-specific successful run and its retained
`source-document-recovery.json` are recorded in the dependent draft PR. The existing
five recovery gates and seven-day artifact retention remain in place.

Manual document selections are deliberately excluded from the existing structured
source World Model and question snapshots. Propagating their explicitly manual
provenance into investigation questions and reports is the next dependent stage;
this draft does not establish that integration, professional review, real patient
identity, live retrieval, model execution or clinical validity.
