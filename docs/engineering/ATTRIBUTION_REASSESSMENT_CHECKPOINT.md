# Attribution reassessment construction checkpoint

## Scope and actual state

This work implements OI-009 within the full Open Intelligence construction mandate.
It does not establish completion of the shared foundation or clinical domains.

- Draft #548 supplies unresolved paired source-attribution returns.
- Draft #566 supplies recorded/current passage comparison. Its head
  `98d4baa6b153cba811297f05a2e6ddc3d18ba388` passed hosted API, PostgreSQL,
  browser and restored-database qualification. Those results apply only to that head.
- The dependent comparison-fingerprint branch adds a deterministic digest of both
  passage pairs and patient/case/question/review scope to the existing atomic audit.
  The journal stores primitive references and the digest. Immutable source versions
  retain the text. No passage narrative is copied into the journal.
- Local commit `44a428c` attempted nested journal content and was defective.
  `736423f` corrects this and adds an actual journal-validator regression.
  Five focused tests passed. Broader verification must be rerun after restoring
  dependencies and through hosted PostgreSQL. Do not inherit #566 results.

## Next dependency sequence

1. Publish the fingerprint increment as a draft and verify its exact head with
   PostgreSQL, revocation rollback, restart and backup restore.
2. Add authorized retrieval of the comparison identity for a decision request.
   Reconstruct from immutable references, verify the digest, and refuse stale or
   cross-scope comparisons before writing.
3. Implement an explicit synthetic reviewer disposition through the existing
   review owner. Preserve prior history, bind the exact inspected content, enforce
   current authority, and provide idempotent recovery after uncertain writes.
4. Connect the Review interface, amendment invalidation and historical display.
   Verify positive, negative, concurrent, retry and recovery paths together.

No clinical attribution, reviewer identity verification, signed approval, production
use, merge or deployment is established. Full platform construction continues
through the existing execution backlog and domain owners.
