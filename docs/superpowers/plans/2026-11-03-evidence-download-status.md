# Preserve current status when downloading an evidence report

Base: #307 at `477f24826a8a102c7437c993d69877c1f250b951`.
Backlog: OI-009 (second time point), OI-010 (connected export), OI-013
(fresh permission and cross-context denial).

## Observed gap and bounded contract

The report API returns `historical_reassessment_required` after amendment while
preserving the original report body and hashes. The download helper exports only
that original body. Its general historical disclaimer does not communicate that
the latest authorized read already requires reassessment.

Add a plain-text download cover containing the fresh returned state, exact
patient/case/question/report references, original preparation date, access receipt,
original body and snapshot digests, and body byte length. Mark current reports
unreviewed and amended reports historical/reassessment required. Append the exact
original body after a fixed separator. Preserve stored report bytes, response
contracts, independent grants and the fresh-read/context-identity guard. Do not
claim a server timestamp, signed receipt, scientific review or delivery audit.
Already downloaded files remain historical; they cannot be recalled or updated.

## Work and acceptance

1. Reproduce the missing status with actual download-helper tests using the
   RegistrySession, plus denied/withheld/context-switch non-download checks.
2. Add the cover without changing the API, schema, report renderer or dependencies.
3. Extend the existing real Chromium journey to download the same report before
   and after an amendment. Check fresh receipt, historical warning, exact preserved
   Unicode body and hash, independent export denial, withdrawal and unchanged
   earlier files. Distinguish downloaded-file and preserved-body digests.
4. Run client/build checks, inspect the exact hosted browser artifact, request an
   independent read-only review, and record actual results in existing engineering
   and backlog records. Keep the candidate draft, unmerged and undeployed.
