# Open Intelligence H1 API shell

This is the `apps/api` composition root for [issue #112](https://github.com/OpenxIntelligence/open-intelligence/issues/112).
It implements a local synthetic infrastructure boundary with typed HTTP
contracts, PostgreSQL 16 readiness and explicit Alembic migrations. The existing
Python/SQLite application in `src/open_intelligence` remains the patient-domain
implementation. This shell does not copy that ledger or implement clinical routes.

## Product and release boundary

The connected patient-information → evidence → investigation → human-review
workflow remains the priority. This shell enables its migration to the accepted
H1 stack; it does not complete MRT-01 or an end-to-end patient investigation.

The environment is **local, synthetic development only**. It has no authenticated
accounts, patient operations, licensed clinical content, model inference or
production authorization. The manifest reports those omissions explicitly.
Host-header validation is a local boundary, not authentication. Do not expose the
container listener directly, use real patient data, or put this behind a public
reverse proxy.

No Next.js, vectors, acute alerts, external model calls or patient-data acquisition
are added. The project distribution license remains undecided.

## Run with Compose

From the repository root, with Docker Engine and the Compose plugin already
available:

```bash
docker compose --file apps/api/compose.yaml config --quiet
docker compose --file apps/api/compose.yaml up --build --detach api
docker compose --file apps/api/compose.yaml ps --all
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/health/ready
curl --fail http://127.0.0.1:8000/v1
```

The database is not published on a host port. The API is published only on
`127.0.0.1:8000`. A separate one-shot migration must succeed before the API
starts. The API runs as an unprivileged user on a read-only filesystem, with an
internal database network and a separate frontend bridge for loopback publication.
The database and migration service remain internal-only. **The API frontend bridge
also permits outbound routing; this is not an egress firewall.** The shell has no
external content/model connector. Database state lives in the named synthetic volume.

```bash
docker compose --file apps/api/compose.yaml restart api
curl --fail http://127.0.0.1:8000/health/ready
docker compose --file apps/api/compose.yaml down
```

`down` preserves the named database volume. Use `down --volumes` only when you
intend to delete this disposable synthetic database. The documented password is
a public fixture credential, never an operator or production credential.

Current artifact target: **Linux x86_64 / CPython 3.12**. The lock pins the exact
reviewed wheels for that target. Other architectures, optional extras, and native
source builds need their own artifacts and review. Python 3.12.16 and PostgreSQL
16.15 container **patch tags** are used; tags are not immutable digest pins. CI
records the actual image identities. Container/OS/driver layers are not cleared
by the Python wheel inventory, and no production image is released by this work.

## Run the application without containers

Use Python 3.12 on the reviewed platform. Dependency download is an explicit
build operation; serving the shell performs no outbound content retrieval.

```bash
python3.12 -m venv /tmp/oi-h1-api-venv
/tmp/oi-h1-api-venv/bin/python -m pip download --require-hashes --only-binary=:all: --dest /tmp/oi-h1-wheels -r apps/api/requirements.lock
python3.12 apps/api/tools/check_dependencies.py --wheel-dir /tmp/oi-h1-wheels --sbom /tmp/oi-h1-sbom.json
/tmp/oi-h1-api-venv/bin/python -m pip install --no-index --find-links /tmp/oi-h1-wheels --require-hashes -r apps/api/requirements.lock
/tmp/oi-h1-api-venv/bin/python -m pip check
PYTHONPATH=apps/api/src /tmp/oi-h1-api-venv/bin/python -m oi_api
```

Without a database URL, liveness and the version contract work, but readiness
returns 503 with `unconfigured`. To use an independently prepared, empty local
synthetic PostgreSQL 16 database, set `OI_API_DATABASE_URL` to its
`postgresql+pg8000://` URL, then run:

```bash
PYTHONPATH=apps/api/src /tmp/oi-h1-api-venv/bin/python -m oi_api.migrate upgrade head
PYTHONPATH=apps/api/src /tmp/oi-h1-api-venv/bin/python -m oi_api.migrate current
```

Only `OI_API_ENVIRONMENT=synthetic` is accepted. Database connection timeout
defaults to two seconds and may be set through
`OI_API_CONNECT_TIMEOUT_SECONDS` from 0.1 to 10 seconds. Database URL query
options are not enabled in this shell. Credential-safe errors do not echo URLs,
SQL or raw database exceptions.

## HTTP and migration contracts

| Route | Contract |
|---|---|
| `GET /health` | Process liveness, 200 even while the database is unavailable. |
| `GET /health/ready` | 200 only for PostgreSQL major 16 at migration `0001_h1_shell`; otherwise 503 with a bounded state. |
| `GET /v1` | Versioned synthetic-shell manifest; capabilities empty, authentication not implemented, patient data disabled. |
| `GET /v1/openapi.json` | Local OpenAPI contract. Swagger/Redoc CDN interfaces are disabled. |

Readiness states are `unconfigured`, `unavailable`, `unsupported_version`,
`schema_mismatch` and `ready`. Every response has `Cache-Control: no-store`.
Non-loopback or ambiguous Host headers are rejected. No patient route exists.

Importing or starting the application never applies DDL. The baseline migration
creates only Alembic's revision bookkeeping, not patient/source/evidence tables.
The future canonical PostgreSQL patient port must be integrated through its
existing owner and contracts. Downgrades are restricted to
`OI_API_RUN_DATABASE_TESTS=1` and database names beginning `oi_api_test_`.

## Dependencies and rights gate

Direct pins are FastAPI 0.162.0, Pydantic 2.14.1, SQLAlchemy 2.0.55, Alembic
1.20.1, Uvicorn 0.54.0 and pg8000 1.31.6. The resolved lock contains 24 exact
wheels. **The pin list is not a whole-artifact license conclusion.** Consult
[the artifact inventory](dependency-license-inventory.json) and
[retained notices](THIRD_PARTY_NOTICES.md) for exact hashes, selected grants,
embedded/native components, obligations and unresolved deployment boundaries.

The default psycopg driver was not selected: its LGPL grant does not fit the
strict permissive baseline. pg8000 is the researched BSD-3-Clause driver
alternative. No HTTPX/TestClient or pytest dependency was needed: the tests use
`unittest`, Uvicorn and actual loopback HTTP. Existing research-environment pins
are not silently promoted into application dependencies.

The gate is a review-integrity check. It rejects incomplete review status,
expanded scope, blocking rights items, changed notices, unexpected wheels,
lock/inventory differences, changed hashes and unreviewed selected expressions.
It does not infer permission or replace legal review. Approval, when recorded,
is only for the exact artifacts in **local synthetic H1 development/evaluation**.
The Docker build checks the same wheel bytes it installs. SBOM output includes
supplier-declared all-target Rust components; that is not proof that every such
component is linked in the Linux binary. Embedded runtime and host-library
limitations remain explicit in the inventory.

No model weights, clinical dataset, guideline content, font/icon assets or new
frontend packages are included. The four rights registers must remain separate
as those capabilities are added. Product distribution and complete image
licensing remain later decisions and evidence requirements.

## Verify

```bash
PYTHONPATH=apps/api/src /tmp/oi-h1-api-venv/bin/python -m unittest discover -s apps/api/tests -v
PYTHONPATH=src /tmp/oi-h1-api-venv/bin/python -m unittest discover -s tests -v
python3 tools/audit_ci_data_boundaries.py
```

The PostgreSQL tests skip explicitly unless **both**
`OI_API_RUN_DATABASE_TESTS=1` and `OI_API_TEST_DATABASE_URL` identify an empty,
disposable `oi_api_test_*` database. They remove the revision table during their
tests. They verify actual migration/re-upgrade, missing/unknown/multiple
revisions, API restart and absence of domain tables. Do not point these checks at
another database. CI fails if the acceptance suite skips any test.

`.github/workflows/h1-api.yml` tests the exact proposed head, then runs the
existing prototype regressions/browser journeys and the actual Compose build,
migration and restart. CI data-boundary checks remain in force. Hosted results
and exact commit links belong in the draft PR; configuration alone is not proof
that they ran or passed.

### Local execution evidence — 2 November 2026

- **26/26 API tests passed**, with no skips, using Python 3.12.14 and an actual
  temporary PostgreSQL 16.15 server. This includes migration/restart, invalid
  revisions, rollback after injected DDL failure, HTTP contracts and negative
  dependency-gate controls.
- **245/245 existing prototype tests passed** on the safety-base checkout plus
  this separate shell. The suite includes synthetic loopback HTTP behavior.
- The real wheel gate passed for 24 wheels, 99 supplier native entries and 13
  embedded-runtime entries. The inherited CI data-boundary scanner passed.
- Initial failing tests exposed the missing shell/migration/gate implementations.
  Configuration-error sanitization and the downgrade boundary were corrected
  after observed failures; independent code review confirmed the downgrade fix.
- The temporary PostgreSQL source archive came from the official 16.15 release
  and matched SHA-256
  `c1575341fa7bd40f5274ea465b34390f4dc64cdd0770af327005caaeb9f6b7ed`.
  It was built under `/tmp` with ICU/readline/zlib disabled for this local probe.
  This is not the container build or a supported production server distribution.
- Docker and Chromium are absent in the session. The hosted workflow is the
  required separate evidence for actual Compose and browser execution; consult
  the exact-head run linked in the draft PR for its observed outcome.
- The first hosted [run #41528664902](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41528664902)
  passed the API/PG16 suite, original regressions and both browser journeys,
  then failed the host-to-container HTTP check. The API was running internally,
  but Docker does not publish ports for an internal-only container. The corrected
  composition gives only the API an additional frontend bridge and retains the
  loopback binding. CI now asserts actual port bindings and database/migrator
  isolation before testing HTTP. See the
  [Docker maintainer explanation](https://github.com/moby/moby/discussions/53256)
  for the gateway requirement; the final PR-head run must verify the correction.

## Traceability and handoff

| Source | Bounded relationship |
|---|---|
| [Issue #112](https://github.com/OpenxIntelligence/open-intelligence/issues/112), parent #96 | API/PG16 composition root, migrations, contracts, dependency gate and reproducible local startup. |
| [OI-27 roadmap](https://docs.google.com/document/d/1Wlg7k61mjVbj-_4x6dth8KM1N7N0U4qzZh-ywitwNA4/edit) | WS-00; supports M-H1-0. Does not complete all component-contract work or any clinical step of MRT-01. |
| [OI-25 components](https://docs.google.com/document/d/1BC5JPDXGf0hnsZwMuofGHQox7IZCKn30-kLSmzgj_D4/edit) | Primary CMP-17; bounded CMP-15 and CMP-19 support. |
| [OI-23 requirements](https://docs.google.com/document/d/1_aw9TKHQ_GRfT8i9FDiAA6MA7F971fX20YCw021noBc/edit) | Tests REQ-L-113 loopback/Host and REQ-L-120 contracts/invariants. That register labels broader requirements as proposals; this does not accept them wholesale. |
| REQ-L-102 / REQ-L-106 | UI performance and source-linked clinical statements remain downstream; no accomplishment claim from this shell. |
| REQ-A-001 / REQ-A-003 | Authentication and consent/purpose remain unimplemented; local shell behavior is not their substitute. |

This branch starts at PR #137's synthetic-only correction
`533afd3ca6dd0c011e2e47397d3d5cae04e62512`; it must not be merged independently
of that safety dependency without reconciliation. It preserves existing
patient-port, clinical-spine, composer, source-correction and review branches.

**Next useful integration:** review the existing PostgreSQL canonical patient
port, establish its domain-owned migrations, and mount one authenticated/scoped
patient-source contract through this shell. Then connect the existing
source/evidence/investigation/review contracts and the React/Vite workspace in
issue #119. Preserve one canonical patient/source/evidence history throughout.
