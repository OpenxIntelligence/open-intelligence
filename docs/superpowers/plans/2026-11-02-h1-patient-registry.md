# H1 canonical patient registry integration

**Goal:** Exercise the existing first-party patient identity owner through the
accepted FastAPI/PostgreSQL 16 shell, with explicit migrations, trusted request
context, durable idempotency and fail-closed patient reads.

**Authority:** Founder master directive, 2 November 2026; accepted H1 decision
register; issues #96/#112 and source owners #85/#148/#162. Ordinary reversible
implementation and draft PR publication are authorized; merge and deployment
are separate. This plan is an implementation record, not a replacement mandate.

**Base:** PR #162 `62d2ad0dd2c2d581f9d13d7659f888265838a4f0`. Its owner published the
network repair and bounded startup-reset retry during this audit; our overlapping local draft was discarded.
**Upstream identity owner:** PR #148
`19b1c1319ba543fd0e93744ea3425bd861b0f233`, itself using #85's validation and API.
Copy its two Python modules unchanged and preserve their blob identities.

## Decisions and limits

- Retain the exact H1 dependency lock. No new third-party packages, models,
  patient records, content connectors, frontend stack or clinical authority.
- Reconcile only the canonical identity tables and immutable receipt/event
  triggers into Alembic `0002_patient_registry`. Do not promote the broad
  experimental EHR/auth/source schema from #145.
- Add `POST /v1/patients` (synthetic acknowledgement and idempotency key only)
  and `GET /v1/patients/{patient_id}`. The existing registry generates patient
  IDs and owns transactions/events. No competing patient ledger.
- Trust comes from an injected authentication boundary. The included adapter
  is explicitly a local synthetic fixture file containing token hashes and
  actor/organization/purpose/action/exact-patient grants. It is re-read on each
  request, fails closed if unavailable/invalid, and has expiry. It is not an
  account system, verified identity, caregiver consent, or a clinical policy
  service. Real providers must replace this adapter through the same boundary.
- A caller cannot supply actor, organization, purpose or authorization in JSON.
  Creation does not implicitly grant access. Reads require an exact patient grant
  and an independently checked matching organization. No list-all route.
- No source/EHR/LIS/Composer migration is claimed. Those existing owners are
  the next integration; clinical, real-patient and distribution gates remain.

## Implementation and acceptance

1. **Migration owner:** domain SQL, Alembic revision and real PG16 tests.
   Establish RED before implementation. Verify one patient table, no unrelated
   schemas, append-only receipts, atomic event rollback, restart/idempotency,
   bounded downgrade, re-upgrade and preservation of unrelated schema objects.
2. **API owner:** root. Introduce typed request/response/error boundaries,
   hash-token fixture adapter, scoped canonical registry operations and request
   limits. Verify missing/bad credentials, overposted authority, cross-tenant
   and ungranted-patient reads, expiry/revocation, lost DB, stale schema,
   concurrent duplicate requests and secret-safe errors through actual HTTP.
3. **Composition owner:** root. Package the existing domain code in the API
   image without copying the repository wholesale. Preserve local-only port,
   explicit migration, original synthetic regression and exact-head CI. Extend
   the container acceptance to perform actual scoped registry persistence
   across API and database restart plus actual backup/restore, using disposable synthetic fixture credentials.
4. **Independent review:** review source ownership, authorization, failure
   paths, migration isolation and test evidence. Correct material findings
   using regression-first verification.
5. **Publication/records:** create one draft integration PR stacked on #162,
   preserve #148/#85 ownership, record local and hosted evidence separately,
   and append bounded receipts to existing Notion/Drive engineering records.

## Review focus

Credential changes are rechecked per request; no cached authority. No request
field, forged proxy header or patient identifier grants access. Unknown and
inaccessible patients have the same outward error. New patient creation and
its event/receipt commit together. No credentials, database URLs, source text or
validation input are echoed in public errors. Only explicit migrations apply
DDL; old revisions cannot silently serve writes. Concurrent retries must leave
one canonical patient and one creation event. API restart must preserve state.

## Execution evidence

At start, the sandbox denied loopback sockets (9 errors, 3 database skips).
With the approved local-socket execution mode, the unchanged API suite ran:
26 discovered, 23 passed, 3 explicit database skips. A separate disposable
PostgreSQL 16.15 server is now available for zero-skip integrated verification.
Final commands and results will be recorded in the existing API README/PR.

## Reviewed implementation checkpoint — 2 November 2026

- Source owners and base remain the revisions above. No dependency lock changes.
  Source blob identities are recorded in apps/api/README.md and independently
  checked. No source owner branch was merged or rewritten.
- Original main observed at 24519839aa8ac1ea3aff88a956349ba72798a72a.
  Patient #85, EHR #74, LIS #56, events #70, integration #89/#95,
  evidence rights #93, PostgreSQL #148 and H1 #162 are distinct source owners.
  Implemented drafts are not a released combined platform.
- H1's accepted PostgreSQL major is 16. The #148 PG17/18 experimental test
  matrix does not change that decision; only the identity subset is composed.
- The current implementation adds identity-only migration, canonical create/read
  HTTP, synthetic fixture authentication, request bounds, Docker packaging and
  container recovery acceptance. It does not add account/consent, clinical
  source, EHR/LIS, knowledge connector, model or UI implementations.
- RED before correction: missing patient route returned 404 instead of the
  expected authentication denial; oversized body returned 422 instead of 413;
  weaker preexisting identity table was accepted; terminated backend skipped
  explicit pooled release while a retained proxy prevented GC from hiding it.
- Independent reviewer reproduced weakened-schema adoption on a separate
  disposable PostgreSQL 16 database. Preflight now refuses conflicting owned
  objects before domain DDL. Connection cleanup uses nested finally.
  Reviewer confirmed both fixes and the Dockerfile-specific context allowlist.
- Final local observed suites: 49 API/migration/gate tests, no skips;
  245 existing prototype tests. Exact 24-wheel/notice gate and static current-CI
  patient-data boundary check pass. These are software tests, not clinical
  validation or proof of all historic data handling.
- Docker and Chromium are unavailable locally. The stacked PR's exact-head
  hosted workflow is the required independent execution evidence for container
  build, both browser journeys, API/DB restart and actual pg_dump/pg_restore.
  Read its result; do not infer success from this script or the parent's CI.
- Default authority is deny-all. The fixture adapter rereads bounded hash-only
  grants each request; synchronous work already authorized may finish.
  No production identity proofing, consent, RLS, least-privilege service role
  or broad security qualification is established.
- Rights scope remains local synthetic H1 development/evaluation. Mako
  inherited-license labeling, native link-map and complete image/distribution
  review are open. No patient records or restricted content were acquired.

### Reproduction commands

Use Python 3.12 with the unchanged apps/api/requirements.lock. For real database
tests set OI_API_RUN_DATABASE_TESTS=1, OI_API_TEST_DATABASE_URL to a disposable
PostgreSQL 16 oi_api_test_* database and, optionally,
OI_API_REGISTRY_MIGRATION_TEST_DATABASE_URL to a second such database.

    PYTHONPATH=apps/api/src:src python -m unittest discover -s apps/api/tests -v
    PYTHONPATH=src python -m unittest discover -s tests -v
    python apps/api/tools/check_dependencies.py --wheel-dir /tmp/oi-h1-wheels --sbom /tmp/oi-h1-sbom.json
    python tools/audit_ci_data_boundaries.py
    python apps/api/tools/verify_registry_compose.py

The last command requires Docker/Compose, a free loopback port 8000 and permission
to build the pinned synthetic images. It creates and removes only a uniquely
named disposable project; it is not a deployment operation.

### Next executable work and record ownership

1. Read the new stacked draft's exact head and CI logs; resolve only observed
   failures. Keep #162/#137 and #148/#85 review dependencies explicit.
2. Reconcile canonical patient/source bindings with #89/#95/#148. Define one
   versioned source acquisition/read contract with exact patient/organization
   authority, original hashes/versions and amendment dependencies.
3. Test correct-patient import, wrong-patient quarantine, source correction,
   stale dependent investigation and persistence through real APIs, before
   extending #119's React/Vite interface. Reuse existing source and review owners.
4. Record the implementation/CI receipt in the existing Notion engineering
   progress page and Drive engineering progress document; retain GitHub as
   code/test truth. Research agents update existing rights and obsolete
   immediate task records only, preserving archival decisions.

There is no merge, deployment, outreach, clinical approval or scheduled
background work in this checkpoint. The founder retains license-exception,
real-patient and consequential deployment authority. Source owners/reviewers
retain their existing code ownership and merge requirements.
