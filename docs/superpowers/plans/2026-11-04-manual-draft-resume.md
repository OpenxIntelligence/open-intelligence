# Make retained passage drafts discoverable

OI-007/008 continuation on the verified combined #445 head
641273d98bc9058ac78185f8d674a243f70446e9. Retained references currently survive
navigation, but Overview and the saved-question list do not identify unfinished
passage work. Add a scoped, quote-free reminder and an explicit resume action.

The existing session remains the only owner of unsent references. Its public
snapshot derives question IDs from current authorized question/case context;
no new persistence, source ledger, task or permission is introduced. Overview
opens the exact saved question through the existing evidence read; the passage
client then performs its existing fresh source checks. Reminders are not claims
that selections were saved, remain current, or received clinical review.

Acceptance: immediate subscriber updates on edit/discard; removals (empty
selected set) still count as unsent work; loading/error/foreign context withholds
reminders; denial and disconnect clear them; successful navigation makes no
write; Overview preview truncation cannot imply there are no other drafts.
Verify focused session/render tests, full client/build/rights checks, independent
review and the actual PostgreSQL/API/browser resume path. Synthetic only.
