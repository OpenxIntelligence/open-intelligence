# Image custody, canonical questions and verification returns

## Intent and authority

Continue the existing H1 patient workflow so an original report, its exact image
bytes, a source-linked question and an operational verification return remain
connected through amendment and recovery. The user authorized continued
development; the existing Notion engineering and Drive engineering records
explicitly require this convergence while preserving both published 0008 heads.

Sources: [engineering roadmap](https://app.notion.com/p/40a3866f77ef8197ae65e727c8907eb3),
[integration contracts](https://app.notion.com/p/40a3866f77ef8122b08bcdc16de89876),
[Drive engineering](https://docs.google.com/document/d/1Zbn-8Z5fABdGrJa5W0kSh4ojSVFvd1ddXdvW6pHr9gA/edit).

## Existing owners and approach

- Base: #263 at `213913fbc19d55076c54780af21b189b3622828c`, tree
  `e8ef9d6d49ea309b39961381648323617836a46e`. This includes #260 and the
  complete image JSON response preparation plus combined image/question recovery.
- Review owner: #262 at `f5f135a3b72e2c82ed479d83fb524e3cc958b9df`.
  Preserve its canonical question projection, immutable return receipts,
  independent permissions, exact-intent retry and connected React Review panel.
- Use one explicit integration branch and no-DDL merge revision
  `0009_image_review_merge`, joining `0008_merge_image_questions` and
  `0008_review_convergence`. Keep every published migration byte-identical.

Alternatives considered: leaving these as separate verified branches would not
establish a connected runtime; recreating the alternate #275 image/question merge
would duplicate an existing owner. Reusing #263 and #262 is the selected engineering
approach under the recorded continuation. The archive adapter, source packet,
source brief, custom question authoring and clinical report/PDF owners remain
separate integrations; their implementations are not recreated here.

## Required behavior

1. One patient, qualified case binding, source ledger, question owner, image owner
   and domain-event journal remain authoritative. Review queue state is derived.
2. Image operations and access receipts do not change canonical source, question
   or review fingerprints. Image and review permissions remain independent.
3. Amendment preserves old bytes, question anchors and return receipts, marks old
   context for reassessment, and requires explicit image relinking. Retrying a
   recorded return recovers its original receipt without making old context current.
   A new current question can receive its own deliberate verification return.
4. Review queue and return responses must be fully JSON-encoded under their existing
   source transaction and patient/case locks. Final same-bearer authority and a
   successful commit precede returning the buffered response. Encoding, authority,
   event or commit failure withholds the body and rolls back new effects. Existing
   image response preparation and 200 duplicate / 201 new semantics stay intact.
5. Populated upgrades from either published 0008 head preserve all original source,
   question, image, return and event history. Both partial heads remain unready until
   the explicit new merge; unknown/conflicting schema ownership fails closed.
6. Real PostgreSQL/HTTP, actual React/Chromium and active restored-database HTTP
   evidence must cover the combined branch. No local PostgreSQL or Docker is
   available; skipped local tests cannot substitute for hosted acceptance.

## Constraints and limits

Use the existing Python 3.12/FastAPI/Pydantic/PostgreSQL 16 and React/Vite stack,
locked dependencies and independently authored fictional records/images. No new
package, API route, permission, table, queue owner or clinical state is selected.
The return records an operator's request for independent verification; it does not
establish clinician review, notification, approval, interpretation or deployment.
Receipts attest authorized prepared disclosure, not network delivery or a distributed
lock on external grants. Other source/question response encoding and #265 intake
authorization changes remain outside this bounded review/image convergence.

## Acceptance

- Exact published migration bytes; one required head; populated upgrades from
  both parents and refusal of conflicting ownership without partial advancement.
- Source -> question -> image -> return -> amendment -> explicit relink -> new
  question/return lifecycle, with preserved history, hashes and independent grants.
- Real serializer withdrawal/failure for queue, new return, duplicate return and
  post-amendment retry; patient/case locks and atomic receipts through preparation.
- Existing image serializer/deferred-commit tests and both owner recovery probes.
- All hosted API/PG and React/browser gates green on one published commit; draft
  PR and existing engineering records updated with actual evidence.
