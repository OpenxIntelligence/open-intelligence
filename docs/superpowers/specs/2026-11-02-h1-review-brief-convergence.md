# Canonical H1 question, verification-return and brief convergence

## Intent
Continue the authorized authenticated-report integration by composing its existing
source foundation first. A single saved source question must support a nonterminal
verification return and a fresh authorized source-only download, without losing
history or weakening intake authority after amendment.

## Approach and ownership
Use #265 `6299eea666a1a014bc239ea7a7ce8f6971380021` as the base; merge the actual
#262 `f5f135a3b72e2c82ed479d83fb524e3cc958b9df` and #264
`e042f753eca85cca97e08fdbb3e07ea8263aae69` parents. All three share #244
`3b6c466950852c20f99d57a70dd196fd2862571a`. Retain canonical PostgreSQL source,
question, immutable return, and event owners; preserve the existing migrations.
This is an implementation choice within the requested continuation.

Directly copying #249's SQLite report stores into H1 would create competing
persistence and incompatible identifiers. Adapting only its rendering would omit
rights and annotation identity. Both are excluded. This prerequisite does not
claim to port #249's PDF annotations, evidence rights or governed reports.

## Acceptance
- Same source/question identities and content fingerprints across list, queue and brief.
- Return and brief access receipts do not alter source fingerprints or clinical authority.
- Export and operational review grants remain independent; preserve final same-bearer
  checks and rollback in #265 and the original consumer operations.
- Amendment refuses stale brief preparation, preserves exact old originals and
  immutable return history, and allows exact committed return retries after restart.
- Combined React state resets retain both brief invalidation and review retry rules.
- Run inherited actual PostgreSQL, migration, browser, restart and restore gates.

## Constraints
FastAPI/PostgreSQL 16, React/Vite/TypeScript. No dependency, original migration,
patient data policy, production identity, model, publisher grant or deployment change.
Only independently authored fictional data. Source-verification returns are not
professional clinical review; briefs are not biomedical evidence reports.
