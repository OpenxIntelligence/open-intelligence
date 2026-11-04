# Canonical questions, original images and verification returns

## Existing owners in one candidate

[Draft PR #278](https://github.com/OpenxIntelligence/open-intelligence/pull/278)
joins two independently maintained H1 owners:

- #263 at `213913fbc19d55076c54780af21b189b3622828c`: #260's canonical
  source/questions and original-image custody, complete image JSON preparation,
  and active restored-API recovery.
- #262 at `f5f135a3b72e2c82ed479d83fb524e3cc958b9df`: the canonical question
  projection, derived Review inbox and immutable operational return receipts.

The patient registry, qualified case binding, source ledger, question/image owners
and domain-event journal retain their identities. Review queue state is derived;
`investigation.question_review_receipts` remains the one published receipt owner.
No new clinical state, table, route, permission, dependency or service is selected.

## Connected lifecycle

An authorized case can hold an original imaging report, its exact DICOM bytes,
a question pinned to the report's source/version/line and a deliberate reason for
independent source verification. Image imports, reads and access receipts do not
change source, preflight, question or review content fingerprints.

A report amendment preserves original image bytes, question anchors and return
receipts. The old question becomes `source_reassessment_required`; its prior
return remains historical and its obsolete source-bound image route is withheld.
An explicit same-byte image relink reuses the immutable image ID without reviving
the old question or return. A fresh preflight and question can receive a distinct
return against the new current context.

An exact retry of an already committed return recovers its original receipt,
including after amendment. A new key cannot act on the stale question. A changed
intent cannot reuse the prior key. The existing React Review workspace preserves
the exact uncertain return intent across same-case source imports as well as reads;
late replies cannot overwrite that recovery state. It never automatically retries.
Patient/case switches, disconnect and denied authority clear the retained intent.
If a confirmed import's metadata refresh temporarily fails, the intent remains
recoverable while the client requires an explicit case-permission recheck. That
recheck preserves the key only while the same case remains active; a missing or
revoked mapping clears it. A metadata refresh cannot submit a return.

## Completed response preparation

The existing `PostgresSourceVersions.list_locked` transaction holds the patient
and qualified case locks while the review owner derives its queue or records the
return. Its callback now validates the original Pydantic model and constructs the
complete buffered JSONResponse. Only then does the source owner refresh the same
bearer's authority, append the existing access event and commit. New-return status
is 201; exact retry status is 200. OpenAPI request/response models remain unchanged.

Preparation or encoding failure, changed grants/identity, event failure or failed
commit withholds the prepared body and rolls back newly attempted effects. The
image owner's existing complete JSON and binary response preparation is preserved.
Receipts attest authorized preparation; they do not prove delivery or make an
external credential file transactionally atomic with PostgreSQL.

Independent review actions remain `review_queue_read` and `review_return`, each
alongside the existing patient/source/question read grants and operations purpose.
Image import, metadata and original-byte grants remain separate. A review grant
cannot confer image access or clinical authority.

## Migration and recovery

`0009_image_review_merge` performs no DDL and joins the two published heads:
`0008_merge_image_questions` and `0008_review_convergence`. All 11 distinct prior
migration files remain byte-identical. Readiness requires exactly the one new head.
Published canonical-versus-legacy provenance and immutable guards remain enforced.

Populated upgrade acceptance covers either parent and both simultaneously applied
parents, preserving complete existing owner rows. Conflicting image/review table
ownership refuses migration without advancing the head or adopting unknown data.
Downgrade cannot discard the canonical review provenance.

The combined Compose probe restores populated v1/v2 questions, image originals
and immutable returns, then recreates the API against that restored database. New
question/review HTTP receipts must appear only in the restored copy. Both old and
new return intents recover the same IDs; the original database remains unchanged.
Restoring revoked bindings cannot authorize image, question or review disclosure.
The separate original review recovery gate is also retained.

## Verification record and scope

The first hosted checkpoint, `05c6ef38dc8beddee064f97959035498751dad3e`,
ran 314 API tests with no skips. The 32 expected failures across four new methods
demonstrated late encoding disclosure, unsanitized encoder errors, already committed
effects and commit-before-encoding order. New populated migration and combined
lifecycle tests passed. See [the tests-first run](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41576685948).

Independent review also reproduced same-case import erasing a pending return
intent. Two new client tests first failed with idle rather than unknown state;
the focused reset repair plus denial coverage passed all 98 client tests locally.
Follow-up review reproduced a confirmed import followed by a temporary source
refresh failure blocking recovery. The added regression first failed with error
rather than unknown state. Seven additional recovery, denial, removed/revoked-case
and late-response tests pass after the narrow case-refresh repair; the final local
suite passes all 105 client tests and the production TypeScript/Vite build.
Those transport tests are separate from the actual built-browser workflow.

Final submitted-head PostgreSQL, browser and recovery evidence is recorded in
PR #278 and the existing Notion/Drive engineering records after execution. Local
database skips are not acceptance. Counts include inherited software executions,
not independent clinical cases.

Only independently authored fictional records/images are used. The image profile
and pinned code-only pydicom from #242/#263 are unchanged. A verification return
records an operator's request; professional identity, clinical review/approval,
external notification, biomedical appraisal, model execution and deployment remain
separate. Other source/question serialization and #265 intake authority, archive,
source-packet, brief and clinical evidence/report/PDF owners are not included.

Backlog OI-006, OI-007, OI-009 and OI-013 remain partially covered. The full
patient-centered healthcare and biomedical platform remains the product scope.
