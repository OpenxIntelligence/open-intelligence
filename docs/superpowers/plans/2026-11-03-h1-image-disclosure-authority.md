# Source-bound image disclosure authority implementation plan

> Execute inline with the existing canonical source/image owners and test-first evidence.

**Goal:** Preserve patient, case, purpose, source fidelity and final authority through preparation of image metadata and exact original binary responses.

**Architecture:** Extend #242 at `0c57f9fe86ef3ef12d24e1fd2a883dd80ddd7a3d`. Reuse #234's source snapshot validation and prepared-response/receipt interface at `65eafebd9fda221dc79789619133c78c6d01dc60`, retaining #242's shared original-validation helper. No second patient/image store or external PACS integration.

**Tech stack:** Existing FastAPI/Pydantic, first-party PostgreSQL16 registry, same locked image parser and migration.

**Spec:** Existing `docs/superpowers/plans/2026-11-03-h1-image-custody.md`, #234 source projection integrity contract, and the accepted backend-continuation direction.

## Constraints and review focus

Independently authored fictional originals only. Preserve current route and response contracts, independent image grants, immutable image/link identity, duplicate/conflict and amendment/relink semantics. No new dependency, schema, UI, clinical authority, production identity, network PACS, main merge or deployment. A read receipt means authorized prepared disclosure, not delivered content or atomic distributed revocation.

Check late token/grant/actor/purpose changes, preparation or event failure, shared patient/case lock lifetime, reserved receipt identity and full source-history fidelity. Metadata and binary bodies must both be prepared before final authority and commit. Existing parser/context validation must not be lost during owner reconciliation.

## Task 1 — establish actual PostgreSQL/HTTP red evidence

- [x] Add `apps/api/tests/test_image_disclosure_authority.py` on pristine #242: prepare real metadata/binary responses then withdraw authority, remove provider or fail construction; assert denial, sanitized errors and no new read receipt.
- [x] In the real constructor, inspect independent PostgreSQL sessions to prove patient/case locks remain held and the receipt is not committed.
- [x] Run existing hosted H1 API suite on the exact test-first head. Retain failed assertions and distinguish harness/setup errors.

## Task 2 — converge source owner and image preparation

- [x] Reuse #234 `source_integrity.py`, `test_source_index_integrity.py`, `test_projection_authority.py` unchanged. Extend `sources.py` with #234's snapshot/prepare contract while retaining #242 `_validated_original`.
- [x] In `images.py`, add optional preparation callbacks to metadata/original reads. Reserve the access ID, prepare the complete result, final-authorize and append the same existing event, commit, then return.
- [x] In `patients.py`, use source preparation callbacks for the existing source index/World Model; image metadata validates its existing DTO and renders JSON under the lock, and original bytes build the existing bounded non-streaming Response under the lock.
- [x] No original bytes are disclosed on failed preparation, authority, event insertion or transaction commit. Preserve no-store and existing binary headers. Internal callers without callbacks retain their prior return types.

## Task 3 — verify and document the combined runtime

- [ ] Run local compilation, whitespace checks, retained reference tests and relevant client tests; disclose unavailable local PostgreSQL/parser/browser dependencies.
- [ ] Run hosted exact-head full API, source/image permission and integrity tests, real Compose HTTP/restart/dump-restore and existing React/Chromium acceptance.
- [ ] Inspect exact source/artifact identity and record failure history, passing counts, unresolved PACS network/service integration and production/clinical gates in the PR and existing engineering records.

The independent PACS findings remain HOLD. This increment secures the existing first-party custody path; it does not make an externally reachable PACS safe or claim raw-PACS bypass denial.

## Execution evidence and rulings

- Test-first head `e80477681f941d77055e518aa818de259376099f`; hosted API run [41571143018](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41571143018) ran 198 tests against actual PostgreSQL 16.15. The 194 inherited methods passed. Four new methods produced 20 failed subcases: 14 late authority/identity/expiry reads returned 200, two missing-provider reads returned 200, two reads had already committed access receipts during response preparation, and two construction-failure cases retained a receipt or returned an unsanitized 500. No setup/import errors explain those failures.
- Reused the three named #234 files byte-for-byte; kept #242's shared original validation helper, image schema, independent permissions, parser, import limits and immutable event owner. The checked implementation tree was `881d3bb76786051d05406070c3e10b64865e4b2d` before the CI/documentation additions.
- Ruling: the image index must render its actual JSON bytes before final authorization, not merely construct its DTO. Explicit DTO validation remains before JSONResponse. Original image responses remain bounded/non-streaming. Added a regression withdrawing permission after real JSON encoding.
- Ruling: test actual deferred commit failure, not just a failing append call. A PostgreSQL deferred constraint trigger rejects both image read commits after response preparation; success requires no response body or committed receipt escape.
- The new receipt test initially assumed JSONB was a string; live pg8000 returns a decoded mapping. Corrected only the receipt-ID lookup to that actual type, without changing the authority, lock, status or rollback expectations.
- Local final checks passed: Python compilation, diff whitespace, 245 unchanged reference tests, 15 original-source integrity tests, and the existing CI patient-data path guard. PostgreSQL/full API, pinned parser and container/browser acceptance require hosted evidence; they are not claimed from local runs.
- The inherited web workflow excluded backend paths. Its pull-request filter now includes `apps/api/**` and `src/**` so this and future API contract changes run the existing React build/browser acceptance without touching UI code.
- Hosted combined-head results and review state are maintained in [draft PR #253](https://github.com/OpenxIntelligence/open-intelligence/pull/253). Until observed there, full combined acceptance remains pending.
