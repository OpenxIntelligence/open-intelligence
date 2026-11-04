# Manual record context on canonical questions

## Refresh draft guard — dependent continuation of #440

Attachment and evidence refresh require an explicit save or discard of unsaved
passage additions/removals. Both controls use the existing exact-question dirty
state; uncertain committed-save recovery remains independently available. The
actual browser regression retains before/after passages and request counters
for both controls, then checks a fresh authorized read after explicit discard.
See the [bounded plan](../superpowers/plans/2026-11-04-manual-passage-refresh-guard.md)
and draft #444 for tests-first failure and final verification. This is a UI
refresh safeguard, not general navigation draft persistence or clinical review.

Scope: OI-006–010 and OI-013, extending draft #392 at
`3eeeaac29ba60f490a6f0e1af1cb28a2baee29c7`. This is a bounded implementation
proposal and synthetic engineering candidate, not a merged architecture or
clinical acceptance decision.

An existing canonical question may carry up to 20 manually selected record
passages as additional context. Its primary structured-source anchor and
comparison semantics stay unchanged. Manual selections remain user-authored,
unreviewed annotations, never source-authored World Model observations.

The question owner stores immutable revisions of the selected reference set.
Each reference pins source ID, annotation revision, selection key and exact
anchor hash. Quotations are resolved by the existing document owner under the
case lock; no second original or annotation store is introduced. Replacing or
clearing a set appends a revision. The old set and report bytes remain recoverable.

Reads use patient/source/question grants and independently require original-read
authority before disclosing manual text. Changes also require question-create.
Full response encoding, fresh credential checks and access receipts happen in
the same transaction, including an authority check after audit callbacks.
Exact retries recover the same revision after correction; changed intent under
the same request key conflicts. Foreign case, source, revision and hash fail closed.

Existing evidence reports remain byte-for-byte valid. A new report that includes
manual context uses renderer v3 and freezes its exact question-context revision,
anchors, quotation, selected actor/time and physical PDF page. The human evidence
comparisons still describe the primary structured observation. The report labels
manual passages as additional context, not clinically validated evidence.

New reports require an inspected manual-context fingerprint when a set has ever
been saved. Stale selections block new reports until explicitly replaced or
removed. Correction, amendment or context-set replacement makes affected earlier
reports historical; it never retargets a frozen quotation. Removing an attachment
does not erase history or grant permission to disclose a historical report.

The existing React evidence workspace lets a user inspect saved documents,
choose saved passages, save/clear a set and recover an exact uncertain submission.
Patient/case/question changes clear local disclosure and ignore late responses.
No new dependency, vector search, model execution, clinical approval, real-data
input or new canonical question/report owner is introduced. Starting a question
from a manual-only record and clinically comparing against manual annotations
remain separate extensions.

## Verification and recovery behavior

Draft #398 verifies the combined increment on #392, incorporating #396. Its current pinned head and hosted
results are recorded in draft #398. Do not infer merged or clinical state
from this engineering candidate.

An uncertain save retains only its exact reference command in the scoped session,
including across an evidence refresh or denied retry. Restoring authority allows
recovery with the same request key; changing patients or questions cannot display
that command or its previous quotations. Disconnecting clears session memory.
Unsaved additions/removals and unresolved saves block report preparation until
saved, recovered or explicitly discarded.

The independent review identified four issues: historical manual reports coupling
unrelated reads to original-read authority, denied retry losing intent, evidence
refresh disposing pending intent, and unsaved selections diverging from report
context. The combined implementation addresses all four. Metadata freshness is
checked without disclosing manual text; only the requested quotation-bearing
report invokes original resolution and its final authority checks. Concurrent
commits through `595b2c421213a25752a1813334e73463fe9659e5` are preserved.
The combined continuation uses an isolated branch to keep its checks pinned
while the shared draft continues to advance.

Local verification: 434 client tests, production build and 13 dependency-rights
controls pass; the installed inventory is 18 packages with two uninstalled optional
packages explicitly uninspected. The local API suite runs 467 tests with 343
PostgreSQL tests skipped; this is not database acceptance. The inherited reference
suite passes 351 tests. The hosted API workflow must complete without skipped
PostgreSQL tests, and the React workflow must complete its actual browser journey.

The browser journey uses independently fictional text and a two-page PDF, loses
an actual committed save response, refreshes, denies recovery, restores authority,
and recovers the same command before downloading a preserved report. It also
checks unsaved removal, annotation correction and original-read revocation.
The database recovery journey separately preserves legacy and manual reports,
compares complete rows and sequences after restore, reads through the restored
HTTP service, verifies exact retries and independent grants, then checks that
annotation correction preserves historical quotations and report bytes.
