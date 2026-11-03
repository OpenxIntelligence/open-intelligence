# Open Intelligence H1 patient registry API

This is the FastAPI/PostgreSQL 16 composition root for [issue #112](https://github.com/OpenxIntelligence/open-intelligence/issues/112).
It mounts the existing canonical patient registry and a small synthetic record-request operational domain, with migrations and durable event receipts.
The Python/SQLite prototype remains the evidence/investigation reference. This
branch now connects canonical PostgreSQL sources, source questions and
nonterminal verification-return receipts; the evidence/report persistence
boundary remains a separate integration.

## Current combined image, question and verification-return candidate

The H1 candidate joins verified #263 (the #260 image/question owner with complete
image JSON response preparation) and #262 (the canonical question verification-return
owner). Both published `0008` histories remain intact under the explicit
`0009_image_review_merge` head. Source, question, image and review grants remain
independent. An amendment preserves historical question anchors, image bytes and
return receipts while requiring reassessment and explicit image relinking.
Image response preparation, including actual JSON encoding for metadata and import
receipts, precedes final authority and commit. Review queue and return callbacks now
also validate their existing models and prepare the complete JSONResponse before
that boundary; new returns remain 201 and exact retries remain 200.

See [the combined design and acceptance scope](../../docs/superpowers/specs/2026-11-02-h1-image-question-review-design.md)
and [the combined engineering contract](../../docs/engineering/H1_IMAGE_QUESTION_REVIEW_CONVERGENCE.md).
The domain sections below retain their incremental history; statements that
source persistence, received records or image custody are still unavailable
describe earlier slices, not this combined candidate. The existing fictional
authorization and clinical-release limits still apply.

## PostgreSQL record-acquisition continuation (draft, synthetic only)

The H1 API includes a record-request operational domain, using the same patient
identifier in `identity.identity_patients` and the same append-only event owner.
A request starts independently of a source. The later source integration can
attach an existing exact fictional source through a received-record event;
it does not acquire records from an external provider or copy source bytes.
Actor, organization, purpose and exact-patient policy remain explicit.

The explicitly applied `0003_record_acquisition` migration creates only
`coordination.record_requests` with a foreign key to the existing canonical
patient and immutable identity-bound request fields. Its database trigger allows
only requested → cancelled with revision increment; deletion and id/subject
rewrites are denied. Both changes add events through the existing identity event
owner in the same transaction. A stable patient-scoped request key prevents
duplicate tasks and conflicting intent. No external provider is contacted.

Additional synthetic-only HTTP endpoints:
- `GET /v1/patients/{patient_id}/record-requests` — requires both `patient_read` and
  `record_request_read`, an exact patient grant and persisted organization match.
- `POST /v1/patients/{patient_id}/record-requests` — requires `patient_read` plus
  `record_request_create`; body includes `synthetic:true`, stable `request_key`,
  `kind`, `record_label` and `source_organization`. 201 new, 200 identical retry.
- `POST /v1/patients/{patient_id}/record-requests/{request_id}/cancel` — requires
  `patient_read` plus `record_request_cancel` and an explicit fictional reason.
- `POST /v1/patients/{patient_id}/record-requests/{request_id}/receive` —
  requires `record_request_receive`, `source_read` and `patient_read`, with an
  exact existing `case_id` and `source_id`. The current source category and case
  must match the request. Receipt is one immutable `record.request.received`
  event; identical retries recover it. Views report `source_receipts_enabled:true`
  and `external_request_sent:false`. A received pointer is not clinical acceptance.

All request commands use the existing 16 KiB/5-second bounded JSON ingress.
The local access fixture and `patient_ids` list are **test authorization only**,
not real consent, patient verification, clinician signoff, or PHI authorization.
A denied patient is returned as the same 404 for missing, unauthorized and
cross-organization requests. Source distribution rights, model access and
untrusted third-party content remain separate and unavailable.

The real PostgreSQL 16 acceptance includes creation, idempotency, cancellation,
event atomicity, immutable-schema enforcement, patient/org/grant isolation,
credential revocation, patient suspension and restart. The received-record
continuation separately covers exact current source links, historical amendments,
independent grants, case revocation and atomic event failure. Use only
`oi_api_test_*` disposable databases with the documented explicit test flag.

### Record-receipt integration boundary

The existing `PostgresRecordRequests.receive` and
`test_received_record_requests.py` own the source-linked continuation. Received
state is derived from the immutable event and its exact original-source pointer;
the original request row's guarded requested/cancelled lifecycle is preserved.
The source/question/review integration below reuses those same identities.
External provider verification and professional clinical acceptance remain open.

## H1 canonical patient-to-case reference binding (draft extension)

The PostgreSQL patient registry now has a **qualified synthetic case-reference mapping**
port following the original `CanonicalLabBridge` and `ClinicalSourceProvenance`
contracts from existing first-party clinical integration #95/#152. This
increment makes the boundary durable, patient-scoped, revocable and auditable
without duplicating a patient registry, source document table, clinical note or
evidence ledger. It does **not** import source records or assert their validity.

Migration `0004_case_binding` adds `coordination.patient_case_bindings`
with one case reference per patient binding, a unique qualified external
`(source_organization, source_system, source_subject_ref)` tuple, an explicit
fictional review reference, an immutable mapping, guarded active → revoked
transition and denial of deletion. Subject reassignment and reactivation after
revocation are refused. Events use `identity.identity_domain_events`, inside
the same `PostgresPatientRegistry.transaction()`. Creation/revocation are
idempotent; conflicting reuse is rejected.

Additional versioned endpoints are:
- `POST /v1/patients/{patient_id}/case-bindings`: requires separate
  `case_binding_create` plus `patient_read`, exact patient grant,
  originating organization, actor/purpose and the independently authored
  synthetic-only input. A synthetic `review_ref` is only an operator-provided
  reference; it is **not** proof of actual professional identity verification.
- `GET /v1/patients/{patient_id}/case-bindings`: separately gated by
  `case_binding_read`; returns current/historical source reference mappings
  and explicit `source_identity_verified:false` and
  `clinical_sources_linked:false`.
- `POST /v1/patients/{patient_id}/case-bindings/{case_id}/revoke`:
  `case_binding_revoke`, exact patient grant and meaningful reason required.
  No production consent or external source authorization is created.
- This identity migration alone adds no source-import or received-request
  endpoint. The later canonical original-source integration below adds fictional
  original bytes and amendments under this binding. The later request-to-source
  receipt is an operational pointer; verified external subject identity remains open.

The tests exercise real disposable PostgreSQL 16, duplicate and conflicting
external identities, patient/org/action isolation, trigger immutability, event
rollback, explicit revocation and restart. These fictional fixtures are **not**
clinical records, human review attestations, verified patient identity, consent,
external hospital connections or a production security boundary. No clinical
data, open-model inference or guidelines may enter this synthetic environment.

## Canonical original-source persistence (synthetic H1 development)

Alembic revision `0005_source_versions` ports the **existing**
`CaseStore.source_versions` / `assertions` and wrong-case quarantine behavior
to one H1 PostgreSQL 16 source owner: `clinical_source.source_versions`,
`clinical_source.assertions` and `clinical_source.quarantine`. This is a
migration of the existing first-party source contract, **not** a separate patient,
clinical truth, pathology or evidence service. The case foreign key targets the
one `coordination.patient_case_bindings` mapping, itself linked to canonical
`identity.identity_patients`.

The source-owner parser remains unchanged: independently authored original
`OI-SYNTHETIC-REPORT/1` UTF-8 LF-only, at most 64 KiB, with exact case,
document, type, event/issued dates and finding-key/state/original quotation
lines. The H1 port preserves the input bytes byte-for-byte, SHA-256, original
line numbers, exact version/line citations and historical versions. Changed
document text requires `Amends: DOCUMENT@LATEST`; an amendment cannot silently
change event date, specimen or document type. The previous original is
`superseded` but never deleted or rewritten; new version and assertions commit
atomically with the existing patient-domain event. Invalid/cross-case document
headers are quarantined instead of creating source-backed assertions.

Typed synthetic-only H1 API:
- `POST /v1/patients/{patient_id}/cases/{case_id}/sources` with `synthetic:true`
  and `original_text`: requires patient_read plus independent source_import,
  case binding, active patient, exact originating organization/actor/purpose.
- `GET /v1/patients/{patient_id}/cases/{case_id}/sources`: requires patient_read
  plus source_read. Returns source/version receipts and **as-reported**
  assertions, not clinical interpretations.
- `GET /v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}`: separately
  requires patient_read plus source_original_read to retrieve the exact original
  fictional text and hash, including superseded historical originals.
- `GET /v1/patients/{patient_id}/cases/{case_id}/world-model`: requires
  patient_read plus source_read. Projects the same source index into the existing
  read-only `oi.pg-source-world-model/1` response; it grants no original-read or
  clinical authority.

Source-index and World Model reads revalidate every current and historical
original against its hash, headers and immediate amendment predecessor. The
complete current finding inventory must match the original key, state, quote
and literal line; missing or extra assertions fail closed. One additional
case-scoped source query performs this check without a query per finding.
Projection and response-schema validation run under the existing patient and
case-binding locks, before the final authority refresh and access-receipt
commit. A preparation, authority, integrity or audit failure returns no source
view or newly committed read receipt. A reserved receipt ID is not proof of
network delivery, clinical review or continued authorization after the final
check. Rehashing the complete source history adds work under these locks;
large-history performance and pagination remain unqualified.

No existing source, report or patient ledger has been copied into a second
application database. The unmerged Python/SQLite reference remains a separate
acceptance oracle while the PostgreSQL port is reviewed. All H1 routes explicitly
report **no clinical interpretation** and **no integrated research-review
invalidation**; original-source amendments do not yet automatically reissue
Composer or clinician review. Outside records requests are not sent to real
institutions. A synthetic case-binding review label is **not verified identity,
patient consent or rights to source content**. No PDF/DICOM ingestion or
real-patient medical record is supported.

The received-record continuation above now links an existing exact original to
its request through the same event owner. Source-derived questions and verification
returns below are additional bounded consumers of that source history; none
establishes external source identity or a clinical interpretation.

## Product and release boundary

### Source context and persistent questions

The existing Composer preflight and question owner are connected to the same
`oi.pg-source-world-model/1` snapshot used by React. They preserve the original
patient, source and event owners; question intake is not a clinical review queue.

- `POST .../cases/{case_id}/composer/source-preflight` requires independent
  `composer_context_read`, `source_read` and `patient_read` grants. Supply the
  current World Model `snapshot_fingerprint` as
  `expected_source_snapshot_sha256`, plus an exact current source ID/line and
  bounded question. The `/2` packet declares its snapshot contract and carries
  a separate access receipt; changing receipts do not change its content hash.
- `POST .../cases/{case_id}/questions` additionally requires `question_create`.
  It revalidates that source context and preflight inside the question transaction,
  refreshes authority and commits one immutable question plus one creation event.
  Same-intent retries keep the original question ID; a stale packet under a new
  key is rejected. It grants no clinical review or model execution.
- `GET .../cases/{case_id}/questions` requires `question_read`, `source_read`
  and `patient_read`. The `/2` list preserves original anchors and identifies
  context requiring reassessment. Its access receipt describes the authorized
  source context, not delivery or professional approval.

All three consumer operations require the existing operations purpose. A
follow-up migration preserves `0006_source_questions` and explicitly marks
pre-existing fingerprint rows as legacy. Such rows require reassessment even
when a hash happens to match a canonical hash; their immutable values are not
rehashed or relabeled. New rows record the canonical fingerprint contract.
See [question ownership and acceptance](../../docs/engineering/H1_CANONICAL_SOURCE_QUESTION_INTAKE.md)
and [preflight boundaries](../../docs/engineering/H1_SOURCE_COMPOSER_PREFLIGHT.md).

### Source-question verification returns

The same question history now supplies a derived review inbox. No second queue,
patient or source store is created. The queue is an operational source-verification
view; a returned receipt does not attest to a professional review or send a message.

- `GET .../cases/{case_id}/review-queue` requires `patient_read`, `source_read`,
  `question_read` and independent `review_queue_read`, under operations purpose.
  Contract `/2` separates a fresh source `access_receipt_id` from stable content
  fingerprints and includes current questions plus immutable return history.
- `POST .../questions/{question_id}/return-for-verification` requires the same
  patient/source/question grants plus independent `review_return`; it does not
  require queue-read or Composer grants. The bounded request contains
  `synthetic:true`, `request_key`, `expected_queue_fingerprint` and `reason`.
  A new receipt returns 201; an identical retry returns the original receipt/200.
- Amendment makes affected prior questions and returns historical. A fresh key
  cannot act on stale context; an original committed request can be recovered
  with its unchanged key and intent after fresh authorization.

`0008_review_convergence` joins both unchanged original 0007 migration histories.
Legacy rows retain their original hashes and explicit legacy provenance. New
receipts bind the canonical source and `/2` queue-fingerprint contracts. The
migration refuses a downgrade that would discard canonical receipt meaning.
Typed response preparation, final grant refresh, source-access receipt and the
return/event write share the existing transaction. A failure rolls them back.
See [ownership, provenance and verification](../../docs/engineering/H1_SOURCE_QUESTION_REVIEW_RETURN.md).

### Image/review migration convergence

The [image/question owner #260](https://github.com/OpenxIntelligence/open-intelligence/pull/260)
and [complete image-response follow-up #263](https://github.com/OpenxIntelligence/open-intelligence/pull/263)
retain `0008_merge_image_questions`; [canonical review #262](https://github.com/OpenxIntelligence/open-intelligence/pull/262)
retains `0008_review_convergence`. This candidate combines their existing code and
adds only the no-DDL `0009_image_review_merge` graph join. Readiness requires that
single new head. Published owner migration bytes and legacy provenance semantics
are retained. Populated upgrade, lifecycle and actual restored-HTTP checks cover
image bytes/links, question anchors, return receipts and the existing event journal.
Image activity must leave review content fingerprints unchanged; explicit relinking
after amendment cannot revive an old question or its historical return.

### Broader product boundary

The first integrated product remains patient information → source-linked World
Model → permitted evidence → investigation → human review → follow-up →
reassessment. This branch connects identity, original sources, canonical source
context, questions and nonterminal verification returns. It does not complete
permitted evidence retrieval, model investigation, professional review or MRT-01.

**Local, independently synthetic development only.** The API accepts opaque
fictional identities and independently authored synthetic source text. Real
names, demographics and identifiable clinical records remain excluded.
The included credential adapter is an operator-authored test fixture. Account
creation, identity proofing, caregiver delegation, clinical consent, production
authorization, clinical sign-off and treatment actions remain unimplemented.
There is no real-patient, deployment or clinical-validation approval.

The default configuration denies all patient operations. Host-header validation
and loopback publication do not replace authentication. No new third-party
packages, model weights, medical content or frontend assets are introduced.
Next.js remains excluded; the project's distribution license is unchanged.

## Run with Compose

From the repository root, with Docker Engine and the Compose plugin available:

    docker compose --file apps/api/compose.yaml config --quiet
    docker compose --file apps/api/compose.yaml up --build --detach api
    curl --fail http://127.0.0.1:8000/health/ready
    curl --fail http://127.0.0.1:8000/v1

This default is usable for health/contracts and denies patient operations.
The database has no published host port. The API publishes only
127.0.0.1:8000. An explicit one-shot migration must succeed before serving.
The API is unprivileged with a read-only filesystem. Database and migrator use
an internal-only network; the API also uses a frontend bridge for loopback
publication. **The frontend bridge permits outbound routing; it is not an
egress firewall.** No external content/model connector is implemented here.

    docker compose --file apps/api/compose.yaml restart api
    docker compose --file apps/api/compose.yaml down

The named synthetic volume survives restart and ordinary down. Use
down --volumes only to delete this disposable project database. The documented
database password is a public fixture credential.

The image target is Linux x86_64 / CPython 3.12, with Python 3.12.16 and
PostgreSQL 16.15 patch tags. Tags are not immutable digest pins; CI records
resolved image identities. Container/OS/driver distribution rights remain a
separate review. The Dockerfile-specific ignore file bounds the root build
context, and explicit COPY instructions package only required app/domain files.

### Opt in to local synthetic access

Use the explicit apps/api/compose.synthetic-access.yaml overlay. Set
OI_API_ACCESS_DIRECTORY to an operator-controlled directory containing
access.json. The container user (UID 10001) must be able to traverse the
directory and read the file. Mounting the directory permits atomic replacement;
only token hashes and synthetic grants belong there.

The fixture schema is version oi.synthetic-access/1, with credentials containing
token_sha256, actor, organization, purpose, actions, patient_ids and expires_at.
Purpose is operations or research. Actions are explicitly enumerated by
Principal in access.py; patient, source, acquisition, binding, image, question and
review actions are independently granted. Question and review operations require
operations purpose; older source or identity grants do not imply these actions.
Expiry must include a timezone. Unknown fields, duplicate token
hashes, oversized/invalid files and unavailable files fail closed. Bearer tokens
must be 32–256 ASCII letters, digits, dots, underscores, tildes or hyphens.

For a generated fixture and a complete automated demonstration, run:

    python3 apps/api/tools/verify_registry_compose.py
    python3 apps/api/tools/verify_sources_compose.py
    python3 apps/api/tools/verify_images_compose.py
    python3 apps/api/tools/verify_reviews_compose.py

Run these commands sequentially. Each starts its own uniquely named disposable
Compose project and creates
synthetic credentials without printing raw tokens, tests create/retry/read,
changes exact-patient grants, rejects another organization, restarts the API
and database, performs pg_dump/pg_restore, verifies identity/receipt/event
continuity, revokes grants and credentials, then removes only its own project
and volumes. Port 8000 must be free. This is a container acceptance command,
not a deployment command. The review proof also verifies exact question/return
provenance, same-key recovery after amendment, independent review grants and
complete source/question/receipt/event equality after dump/restore.

For an operator-authored fixture, start the overlay with:

    docker compose --file apps/api/compose.yaml --file apps/api/compose.synthetic-access.yaml up --build --detach api

A create request accepts only a JSON object containing synthetic: true and a
bounded request_key. A successful create does not grant read access. Add the
returned patient_id to the authorized credential's exact patient_ids list to
enable reading; matching organization and patient_read action are also required.
Replace access.json atomically to change grants. Changes apply on the next
request; an already authorized synchronous request may finish. This is not a
distributed consent/revocation service.

## Source-bound original images (0006_image_custody)

This increment is based on PR #222 at `911b0767c671ae6f40caf20f204aedf1e9df2ab0`.
The original source, canonical identity and event journal keep their existing
owners. Images add immutable `clinical_source.dicom_objects` and
`clinical_source.source_image_links` children. The source report is still the
existing original text format; binary bytes do not enter that parser.

All routes below use the prefix
`/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images`.

| Method / suffix | Additional action | Result |
|---|---|---|
| POST collection, exact `Content-Type: application/dicom` | image_import | 201 for new original or explicit new source link; 200 for identical retry; server-derived image ID, digest and identifiers. |
| GET collection | image_read | Source-bound metadata index and committed access receipt. |
| GET /{image_id} | image_original_read | Exact original bytes, application/dicom, no-store, generic download filename and X-OI-Access-Receipt. |

Each also requires patient_read, the exact patient grant, the persisted
organization, active case binding and matching purpose. They refresh the same
credential before committing. Existing source_read/source_original_read grants
do not disclose image metadata or bytes. Query parameters and content encoding
are rejected; callers cannot override image UIDs, expected digest or backend URL.

The parent must be a current imaging report whose original bytes, hash, case,
type, dates and amendment edge pass the existing validator. `PatientID` must
exactly equal its locked source binding's `source_subject_ref`,
`IssuerOfPatientID` must equal `source_organization + "/" + source_system`,
and StudyDate must equal the report event date. Both source keys forbid `/`,
so equal subject/system strings from different source organizations remain
distinct. A qualified issuer longer than 64 bytes is outside this profile. This development convention does not verify the authenticity of an
external institution or a clinical patient; source_identity_verified stays false.

Same case/SOP with changed bytes returns conflict. Report amendment immediately
makes the old link unavailable to current-image routes. An explicit import of
the same bytes against the amendment creates a new immutable link to the same
image ID; original bytes are not duplicated or moved. Historical source text
remains readable through its original endpoint. Stored original-image reads
recompute the digest, reparse metadata and compare both to custody and binding.

The bounded profile is one uncompressed Explicit VR Little Endian CT object,
single frame, 16-bit MONOCHROME2. The parser validates file framing, lengths,
unique ordered tags, file-meta identity, identifiers, date and pixel geometry
before using the typed parser; it performs no pixel decoding or clinical
interpretation. Unsupported syntax, sequences and malformed input fail closed.
Maximum input is 2 MiB, with 256 originals/64 MiB per case and no archives.
These are development limits, not a claim of general CT-study ingestion.

Read receipts contain opaque IDs, hashes and counts, not raw image identifiers,
originals or tokens. The whole buffered response is withheld until final access
checks and event commit succeed. The case lock serializes local reads and
amendment/revocation; a receipt records a grant for prepared disclosure, not
client delivery or distributed revocation atomicity. No separate PACS endpoint
is deployed or protected by this change.

Run the combined question/image restart/restore acceptance with Docker available:

    python apps/api/tools/verify_images_compose.py

It creates two independently authored originals and canonical source-linked
questions, checks exact bytes and independent grants, restarts API/PostgreSQL,
amends the report and explicitly relinks the same images. The v1 question keeps
its original anchor and requires reassessment; a fresh v2 question remains
separate. Active and revoked snapshots undergo actual pg_dump/pg_restore. The
same API image is pointed at each restored database to check reopened question
history, same-key retries, exact image bytes and denied revoked access. A fresh
receipt in the restored database, absent from the original database, confirms
which database served the restored HTTP response.
The API/database cases also cover final credential changes during real image
response preparation and JSON encoding, encoder failure, and deferred database
commit failure in test_image_disclosure_authority.py. JSON responses validate the
existing model and encode inside the source transaction, keeping duplicate
imports at 200 and new objects/links at 201. The existing image
custody, migration, bounded parser and HTTP ingress tests remain separate.
See the [implementation record](../../docs/superpowers/plans/2026-11-03-h1-image-custody.md)
for scope, alternatives and remaining boundaries.

## Run without containers

Use Python 3.12 on the reviewed platform. Download is an explicit build step:

    python3.12 -m venv /tmp/oi-h1-api-venv
    /tmp/oi-h1-api-venv/bin/python apps/api/tools/prepare_dependencies.py --wheel-dir /tmp/oi-h1-wheels
    python3.12 apps/api/tools/check_dependencies.py --wheel-dir /tmp/oi-h1-wheels --sbom /tmp/oi-h1-sbom.json
    /tmp/oi-h1-api-venv/bin/python -m pip install --force-reinstall --no-deps --no-index --find-links /tmp/oi-h1-wheels --require-hashes -r apps/api/requirements.lock
    /tmp/oi-h1-api-venv/bin/python -m pip check
    PYTHONPATH=apps/api/src:src /tmp/oi-h1-api-venv/bin/python -m oi_api

Without OI_API_DATABASE_URL, liveness and version work; readiness reports
unconfigured. For an independently prepared empty synthetic PostgreSQL 16
database, set that variable to its postgresql+pg8000:// URL and run:

    PYTHONPATH=apps/api/src:src /tmp/oi-h1-api-venv/bin/python -m oi_api.migrate upgrade head
    PYTHONPATH=apps/api/src:src /tmp/oi-h1-api-venv/bin/python -m oi_api.migrate current

Set OI_API_ACCESS_FILE only to a local synthetic fixture file when exercising
patient operations. An application may inject a trusted Authentication provider
through create_app; that interface does not itself establish a production
provider. Only OI_API_ENVIRONMENT=synthetic is accepted. Connection timeout
defaults to two seconds; OI_API_CONNECT_TIMEOUT_SECONDS accepts 0.1–10 seconds.
Database URL query options are not enabled. Public errors omit credentials,
URLs, SQL, source text and rejected validation inputs.

## HTTP and migration contracts

| Route | Behavior |
|---|---|
| GET /health | Process liveness; 200 even if the database is unavailable. |
| GET /health/ready | 200 only for PostgreSQL major 16 at the single revision 0009_image_review_merge; bounded 503 otherwise. |
| GET /v1 | Reports synthetic_patient_registry stage, implemented synthetic capabilities and the configured authentication mode. |
| GET /v1/openapi.json | Local typed contract, including bearer security; no CDN documentation UI. |
| POST /v1/patients | Authenticated synthetic creation; trusted actor/org/purpose; 201 for new identity or 200 for identical retry. |
| GET /v1/patients/{patient_id} | Requires read action, exact-patient grant and persisted organization match. Missing and inaccessible identities both return 404. |

The manifest's patient_data_enabled: false means identifiable/clinical patient
data is excluded; synthetic_registry_enabled: true reports the bounded identity
capability. Authentication is deny_all, synthetic_fixture or trusted_provider.
All responses use Cache-Control: no-store. External or ambiguous Host headers
are rejected. Identity command bodies are bounded to 16 KiB; source JSON envelopes to
72,000 bytes; image originals to 2 MiB. These limits include chunked bodies,
with a five-second read deadline. Malformed/duplicate credentials are rejected.
Conflict is 409, invalid input 422, oversized body 413, read timeout 408, and
unavailable authority/database 503.

Creation delegates to the unchanged source-owned PostgresPatientRegistry:
patient, idempotency receipt and event commit together. It does not create an
alternative ledger. The current fixture grants contain no clinical authority.
There is no patient-list endpoint or implicit access from a created ID.

Import/startup never applies DDL. Migration 0001 remains the empty shell
baseline; 0002 owns only the identity patient, creation receipt and event tables,
their indexes, immutable guards and sequence. Its preflight rejects conflicting
owned table/index/sequence/function names, including weaker same-name schemas,
for explicit reconciliation. It does not silently import experimental EHR,
source, auth or RLS schemas from the PostgreSQL research branch.

Downgrade drops only owned objects without CASCADE and preserves unrelated
objects. The CLI permits downgrade only with OI_API_RUN_DATABASE_TESTS=1 and
an oi_api_test_* database. Runtime checks validate server/revision, not arbitrary
post-migration administrative schema changes. Production least-privilege roles,
RLS and independent security qualification remain open.

## Source ownership and rights

This integration is stacked on [#162](https://github.com/OpenxIntelligence/open-intelligence/pull/162)
at 62d2ad0dd2c2d581f9d13d7659f888265838a4f0, including its owner's network and
startup retry fixes. #162 depends on synthetic-only safety [#137](https://github.com/OpenxIntelligence/open-intelligence/pull/137).
The canonical patient port comes from [#148](https://github.com/OpenxIntelligence/open-intelligence/pull/148)
at 19b1c1319ba543fd0e93744ea3425bd861b0f233, preserving [#85](https://github.com/OpenxIntelligence/open-intelligence/pull/85)'s contract.

| Preserved source | Git blob |
|---|---|
| src/open_intelligence/patient_registry.py | 7edade0e13d81eebc4ffeac1a19beeb6c241cb3e |
| src/open_intelligence/postgres_registry.py | f0f59af9792c7ba8f36911c5768bae5bd7483cfd |
| tools/research/postgres_bakeoff/002_registry_port.sql | ff4d5ad6f0c9870b955711eee87c0df9d3a121e0 |

The domain SQL retains the identity-only portion of #148's contract and its
complete creation-receipt/event SQL. No source owner's branch is rewritten.

The unchanged lock has 24 wheels: direct pins FastAPI 0.162.0, Pydantic 2.14.1,
SQLAlchemy 2.0.55, Alembic 1.20.1, Uvicorn 0.54.0 and pg8000 1.31.6.
Consult [the exact artifact inventory](dependency-license-inventory.json) and
[notices](THIRD_PARTY_NOTICES.md). Their recorded scope is local synthetic H1
development/evaluation, not whole-product commercial clearance. pg8000 is the
researched BSD-3-Clause alternative to an unapproved LGPL driver.

The fail-closed artifact gate checks lock/inventory/hash/notice consistency and
review scope. Its 99 supplier native entries and 13 embedded-runtime entries
are distinct evidence scopes, not 112 verified linked components. Mako's
inherited-label review, native link-map evidence and complete container/host
distribution review remain explicit holds. No new dependency review is claimed
from this integration. Software, models, data and content retain separate
registers.

## Verification and continuation

    PYTHONPATH=apps/api/src:src /tmp/oi-h1-api-venv/bin/python -m unittest discover -s apps/api/tests -v
    PYTHONPATH=src /tmp/oi-h1-api-venv/bin/python -m unittest discover -s tests -v
    python3 tools/audit_ci_data_boundaries.py
    python3 apps/api/tools/verify_registry_compose.py
    python3 apps/api/tools/verify_sources_compose.py
    python3 apps/api/tools/verify_reviews_compose.py

Database tests require OI_API_RUN_DATABASE_TESTS=1 and
OI_API_TEST_DATABASE_URL pointing to a disposable oi_api_test_* database.
OI_API_REGISTRY_MIGRATION_TEST_DATABASE_URL can isolate migration tests in a
second disposable database. The tests remove owned identity objects and revision
tables; never point them at other data. Without these variables database checks
skip explicitly. CI rejects any skip in this acceptance suite.

Local integration evidence on 2 November 2026: **49 API/migration/gate tests
passed with zero skips** against actual PostgreSQL 16.15 and Python 3.12.14;
**245 prototype tests passed**. The exact-wheel gate and static CI data-boundary
guard passed. Failing tests first reproduced missing patient routes, unbounded
request bodies, weakened-schema adoption and lost-connection cleanup. Independent
review confirmed the latter two corrections and the Docker context boundary.

The H1 workflow checks out the exact proposed head, retains original prototype
and both browser journeys, then runs the actual container acceptance including
API restart, database restart and backup/restore. Docker and Chromium are absent
in this local session. Hosted results must be attached to the exact PR head;
this description or passing local tests alone does not prove those operations.

**Current continuation:** the source, question and review-return seams described
above supersede the original identity-only next-task note. The next evidence
integration must reconcile the existing clinical-store, assessment and report
owners through an explicit persistence/adapter contract, preserving canonical
IDs and rights. Do not copy PostgreSQL state into a competing SQLite chart or
coerce IDs to satisfy another owner's interface. Accounts, consent, EHR/LIS,
clinical review, production authorization and complete MRT-01 remain incomplete.

See the [bounded implementation/continuation record](../../docs/superpowers/plans/2026-11-02-h1-patient-registry.md)
for audit scope and regressions. No merge, deployment or clinical validation is
performed by this contribution.

### Preserved shell-only evidence — 2 November 2026

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
- The next hosted [run #41529433207](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41529433207)
  passed the actual network-isolation and loopback-binding assertions, then
  exposed a startup connection reset before the API was ready. Readiness polling
  now retries `ConnectionError` within its existing 45-second limit, alongside
  URL errors and timeouts. Response/schema assertions remain fail-fast; the
  published-port and restart checks must still pass on the final head.


The source owner's final shell-only [run #41530234376](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41530234376)
at 62d2ad0dd2c2d581f9d13d7659f888265838a4f0 passed 26 API tests, 245 prototype
tests, both Chromium journeys and the health-only Compose/API-restart probe.
That proves the base shell, not this new patient/backup/restore extension.
