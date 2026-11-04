# Report freshness within the prepared patient workspace

Continue OI-009/010/013 by combining #402 at
`547039fb3ea3e2d520cbbc4e2318c5b97d99ceae` with #378 at
`ecc8f6d8066178573c950ab537faea8094a1e81c`. Preserve both source parents and
their existing session, question, evidence, task and report owners.

## Behavior

When a fresh report read discovers that previously current evidence is historical,
remove stale comparison actions and invalidate earlier original reads. Keep its
unfinished comparison hidden until fresh matching context is available. Exact
uncertain-write recovery remains separate. A historical download must reauthorize
and retain the original body. Denied or withheld report content clears dependent
evidence drafts. These evidence-only changes must not erase independently authorized
follow-up creation or transition drafts, rewrite task ownership, or add unsent
work to the preparation agenda. Common session termination still clears all drafts.

## Execution

1. Pin both upstream heads and inspect their deltas and repository boundaries.
2. Add the donor's seven freshness regressions, repeated-download check and two
   composed evidence/follow-up session cases; observe expected failures first.
3. Reuse the donor evidence runtime. Preserve both sides of shared browser/docs
   changes. Exercise an external evidence amendment while follow-up inputs exist
   in the real browser, checking retained forms and saved-only preparation work.
4. Run client, build, rights, syntax and boundary checks. Obtain independent review.
5. Publish an isolated draft integration onto #402 with both upstream parents.
   Verify exact-head PostgreSQL/API/Chromium acceptance and retained source artifacts.

No backend, schema, grants, dependencies, workflow or clinical authority change.
Synthetic-only engineering; no merge, deployment, external handoff or durable autosave.
At the local implementation checkpoint, the tests-first run had 442 passes and
seven expected failures across the 449-test suite (including the strengthened
download test and new composed historical-report case). With the exact donor
runtime, all 449 client tests pass without skips. The 13 rights controls,
installed-package gate, pinned TypeScript/Vite build, Python helper compilation,
whitespace and synthetic boundary checks pass. Independent review and combined
hosted acceptance remain pending; final exact-head results belong in the draft PR
receipt, separately from upstream success.
