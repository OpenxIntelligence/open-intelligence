# Preserve unsaved passage edits across refresh attempts

Objective: prevent attachment/evidence refresh from silently clearing unsaved
manual-passage additions or removals. Continue GH-323 and OI-007/009/010 on
pinned #440 `4893b81e51ac60fefd2fb6b714edc25a2f721a56`.

Root cause: refresh clears the client's packet; the panel effect then replaces
the locally chosen set with an empty/saved set. Existing dirty-state report
blocking does not protect either refresh control.

Use existing `manualReportBinding().dirty` to disable attachment refresh and
communicate this exact-question-scoped state to the evidence panel. Restore
refresh after explicit save/discard. Keep uncertain-save receipt recovery and
its evidence refresh enabled: dirty and uncertain are different states. Update
the explanation. No new persistence, authorization, owner, migration or package.

Verification:
- Tests-first commit `92c628aeac153545c1bec05d51887822c2c19fb1`, tree
  `ad8d957786e8de59f3ae3524581f076be18c3954`, failed the actual PG/FastAPI/React/
  Chromium journey in run 41827426212: attachment refresh discarded unsaved
  additions. All 483 client tests/build passed before that intended assertion.
- Cover additions/removals through both refresh controls; retain before/after
  text and request counts; require zero requests or writes. Explicit discard
  must permit a fresh receipt-bearing GET.
- Preserve lost-response refresh/retry, report/download, correction, Review,
  follow-through, original-read denial and patient-isolation journeys.
- Complete client/rights/build checks and final published-commit browser CI.
  Parent backend receipts remain separately attributed.

This fix does not claim draft persistence across navigation or every mutation
that can replace evidence context. Independently fictional inputs only. Draft,
unmerged, undeployed. Local final checks: 483 client tests, 13 rights controls and
TypeScript/Vite build pass. Existing large-chunk build warning remains.
