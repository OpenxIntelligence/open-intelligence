# Manual record context on canonical questions

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

The existing React evidence workspace will let a user inspect saved documents,
choose saved passages, save/clear a set and recover an exact uncertain submission.
Patient/case/question changes clear local disclosure and ignore late responses.
No new dependency, vector search, model execution, clinical approval, real-data
input or new canonical question/report owner is introduced. Starting a question
from a manual-only record and clinically comparing against manual annotations
remain separate extensions.
