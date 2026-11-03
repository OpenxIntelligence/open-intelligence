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

- [ ] Add `apps/api/tests/test_image_disclosure_authority.py` on pristine #242: prepare real metadata/binary responses then withdraw authority, remove provider or fail construction; assert denial, sanitized errors and no new read receipt.
- [ ] In the real constructor, inspect independent PostgreSQL sessions to prove patient/case locks remain held and the receipt is not committed.
- [ ] Run existing hosted H1 API suite on the exact test-first head. Retain failed assertions and distinguish harness/setup errors.

## Task 2 — converge source owner and image preparation

- [ ] Reuse #234 `source_integrity.py`, `test_source_index_integrity.py`, `test_projection_authority.py` unchanged. Extend `sources.py` with #234's snapshot/prepare contract while retaining #242 `_validated_original`.
- [ ] In `images.py`, add optional preparation callbacks to metadata/original reads. Reserve the access ID, prepare the complete result, final-authorize and append the same existing event, commit, then return.
- [ ] In `patients.py`, use source preparation callbacks for the existing source index/World Model; image metadata validates its existing DTO and renders JSON under the lock, and original bytes build the existing bounded non-streaming Response under the lock.
- [ ] No original bytes are disclosed on failed preparation, authority, event insertion or transaction commit. Preserve no-store and existing binary headers. Internal callers without callbacks retain their prior return types.

## Task 3 — verify and document the combined runtime

- [ ] Run local compilation, whitespace checks, retained reference tests and relevant client tests; disclose unavailable local PostgreSQL/parser/browser dependencies.
- [ ] Run hosted exact-head full API, source/image permission and integrity tests, real Compose HTTP/restart/dump-restore and existing React/Chromium acceptance.
- [ ] Inspect exact source/artifact identity and record failure history, passing counts, unresolved PACS network/service integration and production/clinical gates in the PR and existing engineering records.

The independent PACS findings remain HOLD. This increment secures the existing first-party custody path; it does not make an externally reachable PACS safe or claim raw-PACS bypass denial.
