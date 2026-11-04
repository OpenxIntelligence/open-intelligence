# H1 original images in the question, follow-through and citation workflow

## Intent and authority

Continue the founder's patient-centered longitudinal platform: one person's
original report and image must stay connected to their question, verification
request, next task and permitted evidence metadata through amendments and recovery.
This is a preserving integration under the user's continuation instruction and
existing OI-006/007/008/009/013 contracts, not a new architecture or clinical scope.

The current Notion Identity 00 makes the patient the organizing principle across
providers and settings. Decisions 03, Contracts 14 and Engineering 12 retain the
existing H1 stack and domain ownership. GitHub reconciliation on 3 November shows
that #298 has follow-through and citation metadata, while #278's image custody
remains separate. The reported benefits to patient effort/continuity are goals;
software integration checks do not establish those outcomes.

## Exact owners

- #298: `89f98824610e23a26d2904a845ed1d930207bd76`, tree
  `30e40fd60b4f42d65732bfcebe6233ad602ad955`. Includes #287 canonical
  source/question/packet/brief/review, #293 follow-through and governed metadata
  and citation links. Current API, React and inherited UI workflows passed.
- #278: `b72560ac0f5e5005040b0fc660ce1650343611cf`, tree
  `db488cbdd121a2052e8df95a5a724d32ca3d80e9`. Includes exact image custody,
  image/question/review convergence and active restored-API acceptance.
- Common ancestor: #262 `f5f135a3b72e2c82ed479d83fb524e3cc958b9df`.

The #298 artifact ZIP digest is
`692f54945e70b9bd47997e93387f8fccca400284ba992d1b5d706783e55ecd0b`.
All 356 source files reproduce its complete Git tree. Local import commit
`8c2cbdbe728f65965032f391e9bcea70dd5b93e9` is attached to the verified
common ancestor for three-way resolution. Publication must retain both actual
remote parent SHAs; local metadata is not claimed to be the remote commit.

## Approach considered

1. **Join these two verified owners (selected implementation choice).** Preserve
   their data contracts and published history, then exercise the combined path.
   The cost is resolving real merge boundaries and proving populated recovery.
2. Build another image/task/evidence owner. Rejected because it would duplicate
   authoritative patient state and discard the existing acceptance evidence.
3. Include authored evidence/reports (#300), active #302/#303/#304 continuations
   and optional archive #277 now. Deferred because they have distinct live owners
   and semantic contracts. Keep them visible in the integration inventory.

## Required behavior

- Preserve original imaging report UTF-8, exact DICOM bytes, qualified case scope,
  immutable source/image links, question anchors and all original receipts.
- One canonical question can have a source packet/brief, verification-return
  history, follow-through task/history and a permitted metadata citation.
- Image import/read/relink must not silently change source, question, review,
  follow-through or evidence-content freshness. Access receipts stay distinct
  from content fingerprints.
- Amendment makes the old question context historical. Image relink cannot make
  it current. Open tasks require the owner's recheck state; old citation and
  return identities remain recoverable under the owners' existing retry rules.
  A fresh current question can carry new task, return and citation intent.
- Metadata rights withdrawal redacts restricted title/URL fields while preserving
  citation identity; it neither grants image access nor rewrites task history.
  Image, task, review and evidence grants remain independently enforced.
- Binding revocation denies all relevant reads and retries without new effects.
- Existing bounded JSON/binary preparation, final authority and audit/commit
  ordering remain intact. Failed attempted image effects cannot damage committed
  task, citation or review history.

## Persistence and migration

Preserve every published migration byte. Add only the no-DDL merge revision
`0011_image_evidence_merge`, with exact parents `0009_image_review_merge` and
`0010_question_evidence`. Readiness requires that one complete head.

Prove upgrades from populated #278 and populated #298, and from both published
heads explicitly applied without the final merge. Existing values and provenance
must survive. Unknown competing image/task/evidence ownership must fail closed
without adopting data or advancing the schema. Preserve downgrade and immutable
history guards.

## Recovery and acceptance

Retain all four #298 Compose gates and add the #278 image probe, for five gates.
Extend the latter to cover the connected task/citation history alongside original
images/questions/returns. Restore a populated PostgreSQL backup, reconnect the
real API to that copy, read and explicitly retry preserved history, and prove new
HTTP receipts are written only there. The original database must stay unchanged.
Restore revoked binding and metadata-rights states and verify denial/redaction.

Use actual PostgreSQL 16.15 hosted acceptance with zero skipped database tests,
the reference suite, existing real React browser journey, production build and
dependency checks. Match the submitted source tree and browser artifact. Obtain
an independent whole-change review and repair concrete findings with regression
evidence. Local skipped database tests are not acceptance.

## Constraints and scope

Use only independently authored fictional records/images/metadata. Retain the
existing Python 3.12/FastAPI/Pydantic 2/Alembic/PostgreSQL 16.15 and React/Vite/
TypeScript owners. Retain #278's hash-locked code-only pydicom 3.0.2 build and
rights gates; no new dependency, provider, model, service or permission is chosen.
No new patient ledger, evidence store, report renderer or image viewer is needed.

Metadata identity does not establish claim support, applicability or quotation/
export rights. Task completion and verification returns do not establish clinical
approval or external notification. Broader authored-evidence/report, archive,
clinical EHR/LIS, identity/consent and production qualification remain with their
existing owners. Publish a draft; no merge, deployment or external message.
