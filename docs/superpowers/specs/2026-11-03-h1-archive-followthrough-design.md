# Archive continuity within the combined H1 workflow

## Intent and accepted foundation

Continue the existing patient/source workflow by bringing PR #312's verified
archive read path into PR #313's image, question, verification-return, task and
citation integration. This implements the next bounded step already recorded
in the canonical Roadmap and Integration Contracts. It does not select a new
architecture or archive provider.

Base: #313 `f6132e894a21a326f72660c3399499ccbf251831`.
Archive donor: #312 `9cd218210099c69d04b023ef77f9051a32206fc4`.

## Approach

Selectively reuse the archive seam, authority tests and synthetic fixture, then
extend the richer #313 recovery scenario. Replacing that scenario with #312's
older copy would discard task/citation acceptance. Merging all report/reading
and transport branches at once would add separate schema and delivery concerns.
Those owners remain explicit future integration work.

## Required behavior

- Optional trusted application construction supplies an archive reader. Default
  operation remains local. Clients cannot select an archive or supply its URLs.
- Preflight uses canonical patient/case/source/image identity and current grants.
  Archive I/O occurs without database locks. A fresh transaction rechecks custody,
  prepares the complete response, rechecks authority, and commits the receipt.
- Missing, changed, malformed or unavailable archive bytes withhold disclosure;
  valid local originals never silently replace a failed configured archive read.
- Source amendment and explicit relinking preserve earlier questions, returns,
  tasks, citation versions and original image identity. Rights withdrawal redacts
  citation metadata independently of image-read authorization.
- Restart and PostgreSQL backup/restore preserve the combined history and exact
  retry identities. Fresh read receipts occur only in the restored database.
  Revoked binding prevents archive invocation and disclosure.

## Constraints and scope

Use independently authored synthetic records only. Preserve the existing owners,
14 published migrations and `0011_image_evidence_merge` head; add no dependencies,
schema, permissions or public API fields. Retain #313's citation timestamp fix.
No frontend rewrite is needed. A controlled file archive is a test fixture, not
live PACS qualification, network isolation, external-archive backup or clinical
validation. PR #320 transport and #307/#316/#322/#326 report/reading continuations
remain separate owners. This candidate stays draft, unmerged and undeployed.
