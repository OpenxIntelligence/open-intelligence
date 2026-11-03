# Open Intelligence H1 patient registry API

## Exact manual-passage references (dependent candidate)

`GET /v1/patients/{patient_id}/cases/{case_id}/documents/{source_id}/selections/{revision_id}/{selection_key}`
resolves one saved human-selected passage through the existing source owner.
The `oi.reviewed-document-selection/1` envelope contains an immutable `anchor`
and its SHA-256 (canonical sorted compact UTF-8 JSON). The anchor binds patient,
case, original source/version/hash, frozen extraction method/hash, annotation
revision/review hash, selecting actor/time, key, selected state, literal quotation,
line and physical PDF page. Text pages and non-PDF extraction hashes are null.

Source state, latest annotation revision and selection freshness stay outside the
anchor. A correction or source amendment marks an earlier reference
`selection_reassessment_required` without changing its quote or hash. A missing
revision/key never falls back to a newer selection. All selections remain
`user_selected` / `not_performed`; currentness is not clinical verification.

Each read independently requires patient, source-read and original-read authority;
serialization and source-owned access audit occur inside the locked binding
transaction. Original credentials are checked again after audit persistence.
Denied reads disclose no passage and roll back their access receipt. The hash is
not a capability token: a future question/report consumer must re-resolve the
reference under its own authority and freshness rules.

This is a read-only prerequisite for manual-passage → canonical-question/report
integration. It does not create questions, promote annotations into source-authored
facts, execute a model, grant clinical approval or complete that broader workflow.
No database migration or dependency is added. Exact-head acceptance and limitations
belong in the dependent draft PR and the existing convergence gate.

> **Pinned-main reconciliation:** #354 remains the document owner at `7b16a9a900737f07adb03e35362922c886424e9b`. This dependent source checkpoint preserves that concurrent update, includes accepted main `c4798ae` and records #374 ancestry. See the [convergence gate](../../docs/engineering/H1_EVIDENCE_CONVERGENCE_MERGE_GATE.md) for the exact composition and its separate verification requirements. The earlier checkpoint below retains its original scope.

This is the FastAPI/PostgreSQL 16 composition root for [issue #112](https://github.com/OpenxIntelligence/open-intelligence/issues/112).
It mounts the existing canonical patient registry and a small synthetic record-request operational domain, with migrations and durable event receipts.
The Python/SQLite prototype remains the evidence/investigation reference. This
branch now connects canonical PostgreSQL sources, source questions and
nonterminal verification-return receipts, bounded fictional evidence metadata
links, case-owned fictional evidence originals, human-authored comparisons,
immutable evidence reports and question-linked follow-through. The latter
owners are composed in the #307 → #322 → #328 lineage; see the
[current checkpoint](../../docs/project-state/PROJECT_STATE.md) and
[continuity evidence](../../docs/engineering/H1_EVIDENCE_CONTINUITY.md).
Qualified biomedical retrieval, scientific/model appraisal and professional
clinical approval remain separate work. Current source/evidence/report software
does not establish those capabilities or a merged/clinical release.

## Reviewed ordinary documents

Records uses source-owned ordinary text/PDF intake and immutable selection history.
See [routes, grants, bounds and verification](../../docs/engineering/H1_REVIEWED_DOCUMENTS.md).
Manual classifications remain separate from structured source assertions.

### Current reviewed-document convergence checkpoint

On 3 November 2026, the local continuation of existing draft #354 composes
`d9b81f08a97998e8f95d2a1cc7c43b4165e99862` with the frozen #368/#369/#362/#367
inputs in the [current candidate record](../../docs/engineering/H1_CONNECTED_RIGHTS_CONVERGENCE.md#current-candidate--reviewed-document-convergence-in-354).
**Local composition verified; exact combined hosted acceptance pending.**
Main `c4798ae85004713593f83458abd2102be6729095` remains the Python/SQLite
reference; the H1 candidate is unmerged and undeployed.

The existing source recovery probe now includes #362's restored-database
reviewed-document HTTP assertions: exact text/PDF bytes, immutable selections,
retry identities, independent grants and restored revoked-binding denial.
Those checks must execute on the new combined head before acceptance is claimed.
The production API, published migration history and exact dependency set remain
unchanged. Manual selections do not enter structured investigation provenance;
real identity/consent, professional review and clinical validation remain open.

## Question-scoped fictional evidence metadata

Apply the current migration head (`0012_reviewed_documents`) explicitly:

```bash
PYTHONPATH=apps/api/src:src python -m oi_api.migrate upgrade head
PYTHONPATH=apps/api/src:src python -m oi_api.evidence_catalog
```

The second command is an operator-only, opt-in seed of two independently authored,
nonclinical metadata records. It performs no external retrieval. Repeating it
does not overwrite an existing version or restore revoked rights. The application
does not seed records or grant access on startup.

After the existing patient, case, source, World Model and question workflow,
these routes operate on the same canonical question:

| Method and question suffix | Behavior | Additional synthetic grants |
|---|---|---|
| `POST /evidence-search` | Bounded lexical search of authorized fictional metadata; exact versions, metadata hash and access receipt | `evidence_read` |
| `GET /evidence-links` | Immutable citation history with freshly checked metadata rights | `evidence_read` |
| `POST /evidence-links` | Save an exact citation and metadata hash against the question's current source snapshot | `evidence_read`, `evidence_link` |

The full prefix is `/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}`.
Patient, question and source access plus the `operations` purpose remain required.
Use the versioned local OpenAPI contract for exact request/response fields. The
existing React saved-question panel exposes these operations, recovery of an
uncertain save, and source-reassessment status.

Unknown, withdrawn or superseded metadata rights withhold the title, license and
URL on a fresh read. The link's identity and hash remain historical references
under patient access. An exact retry can recover an earlier receipt without
creating a new effect or releasing revoked metadata. An amended patient source
blocks new links from the stale question while preserving its prior history.

An internal fixture declaration is not legal clearance of third-party content.
A matching citation identifies a catalog version; it does not establish claim
support, trial eligibility or clinical validity. No publisher connector, model
call, scientific computation or clinical approval is enabled by this slice.
See [the implementation and verification record](../../docs/engineering/H1_QUESTION_EVIDENCE.md).
The existing `verify_followthrough_compose.py` recovery probe now also preserves
the evidence catalog, rights decisions and citation through actual dump/restore,
and verifies redacted metadata and restored patient-binding denial over HTTP.

## Canonical saved-question follow-through

The synthetic task increment extends the existing saved-question/source owner
with immutable task origins and append-only operational status history. See
[the follow-through contract and verification ledger](../../docs/engineering/H1_QUESTION_FOLLOWTHROUGH.md).
Apply migration `0009_question_followthrough` explicitly. The three versioned
routes list tasks, create a task from an exact saved question and append a legal
transition. Independent `followthrough_read`, `followthrough_create` and
`followthrough_update` grants supplement patient, question and source access.

A stable request key recovers the original receipt; concurrent updates require
the current revision. Original source anchors survive amendment, while open
work is marked for rechecking. Completion records attributed work and neither
approves a clinical finding nor contacts an external service. Real JSON bytes
are prepared before final authorization and audit commit. The actual container
recovery probe is `python apps/api/tools/verify_followthrough_compose.py`.
Hosted results and remaining limits are recorded in the linked ledger.

## Historical pending-record milestone

The following record-request milestone predates canonical source persistence.
Its former no-receipt limitation is superseded in this candidate by the
[canonical received-source contract](../../docs/engineering/H1_CANONICAL_RECORD_SOURCE_RECEIPT.md).
The original milestone is retained to explain schema and owner provenance.

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

## Historical patient-to-case binding milestone

This initial mapping milestone predates the original-source port described in
the next section. Its no-import limitation is historical, not the current API.

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
- `POST .../cases/{case_id}/questions/{question_id}/brief` additionally requires
  `source_brief_export`. It reconstructs the current saved question, exact
  original anchor and preflight under the existing source locks, prepares a
  bounded typed response, refreshes all authority, and commits a source-read
  receipt. Its literal text declares no clinical approval, model execution or
  biomedical evidence. A stale or legacy question requires reassessment.

All four consumer operations require the existing operations purpose. A
follow-up migration preserves `0006_source_questions` and explicitly marks
pre-existing fingerprint rows as legacy. Such rows require reassessment even
when a hash happens to match a canonical hash; their immutable values are not
rehashed or relabeled. New rows record the canonical fingerprint contract.
See [question ownership and acceptance](../../docs/engineering/H1_CANONICAL_SOURCE_QUESTION_INTAKE.md)
and [preflight boundaries](../../docs/engineering/H1_SOURCE_COMPOSER_PREFLIGHT.md).
The [saved-question brief contract](../../docs/engineering/H1_SOURCE_LINKED_BRIEF.md)
specifies the independent export grant, complete response bound and fresh
authorization for every download. It adds no table, dependency or review state.

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

### Concurrent image-owner boundary

The separate [image/question convergence #260](https://github.com/OpenxIntelligence/open-intelligence/pull/260)
is draft at `90dfe49fab082f3698fc82b3e8224cf7d30e5c4f`, with
`0008_merge_image_questions`. Its image functionality and validation are not
included in this review-return branch. A later combined owner must preserve
both original 0008 histories, add an explicit merge of `0008_merge_image_questions`
and `0008_review_convergence`, and require that new single head in readiness.
Populated upgrades from both sides must retain image bytes/links, questions,
receipts, source contracts and events. Image activity must leave review content
fingerprints unchanged; report amendment must invalidate dependent work without
relinking images silently reviving an old question.

### Authored evidence and comparison reports

The bounded `0009_question_evidence` continuation adds case-owned original
fictional evidence, human-authored comparisons and immutable report preparations
inside the existing source-owner transaction. It reuses the original synthetic
evidence parser and content-specific rights functions; it does not mount the
reference SQLite clinical stores or create a shared cross-patient catalog.

All seven routes under `.../questions/{question_id}` require `patient_read`,
`source_read`, `question_read`, `authored_evidence_read` and operations purpose:

| Route | Additional independent action |
|---|---|
| GET `/evidence` | None |
| POST `/evidence` | `authored_evidence_import` |
| POST `/evidence/{evidence_id}/withdraw` | `authored_evidence_withdraw` |
| GET `/evidence/{evidence_id}/original` | `authored_evidence_original_read` |
| POST `/evidence-assessments` | `authored_evidence_assess` |
| POST `/evidence-reports` | `evidence_report_export` |
| GET `/evidence-reports/{report_id}` | `evidence_report_export` |

Original bytes, declared content item and normalized permissions are immutable.
Display and export intersect the referenced version's permissions with the current
family declaration using the original item class. Metadata, full text, abstract and
API output rights remain separate. Unknown and denied permissions fail closed;
this human-only reader never implies model-use permission. Amendments require the
existing explicit grammar, make old comparisons historical and require authored
reassessment. Withdrawal withholds that family's original/report content while
preserving its records and report digests.

Every write has an exact idempotency key/intent, including duplicate-byte imports.
Receipt recovery checks the actual stored object, and returns no report body.
Stored reports are checked against actual canonical question/source and immutable
comparison/evidence records, not merely self-consistent supplied hashes. Every
fresh download rechecks current grants and rights; historical and withheld states
are explicit. The complete bounded JSON body is prepared before final bearer
refresh, source-access audit and the same transaction commit.

The five append-only tables are `case_evidence_versions`,
`case_evidence_withdrawals`, `question_evidence_assessments`,
`question_evidence_reports`, and the exact-command receipt ledger
`evidence_commands`, all in `investigation`. A nonempty evidence history prevents
routine downgrade. The distinct parallel `0009_question_followthrough` owner must
be reconciled through an explicit merge preserving both histories.

Follow-up `0010_authored_evidence_origin` preserves the published 0009 migration
and all existing rows. Its append-only `evidence_command_origins` table binds each
assessment/report to the exact creating request key and intent. Upgrade requires
exactly one matching scoped command per old object; missing or ambiguous mappings
stop for explicit reconciliation. Old reports retain their original body/hash and
`oi.h1-evidence-text/1` renderer. Their inspected packet is bound by the original
complete command-intent digest and is explicitly labelled `intent_digest_only`;
no packet hash is invented from that one-way digest. New reports retain an explicit
expected packet digest and `/2` rendering, which prints frozen metadata and declared
content-item store/display/redistribute/ml_use permissions. Exact retry verifies
these independent origins so a corrupted receipt cannot redirect to another valid
same-content object. No earlier report body, snapshot, command or audit event is
rewritten by this migration. Populated origin history prevents routine downgrade.

The separate metadata search/citation-link owner remains independent: this slice
adds no acquisition connector, publisher verification, clinical appraisal, model,
professional review or delivery. Source-only briefs retain their original meaning.
See the [contract and verification receipt](../../docs/engineering/H1_AUTHORED_EVIDENCE_REPORTS.md).

### Broader product boundary

The first integrated product remains patient information → source-linked World
Model → permitted evidence → investigation → human review → follow-up →
reassessment. This branch connects identity, original sources, canonical source
context, questions, nonterminal verification returns and authored fictional evidence
comparisons/reports. It does not complete live permitted evidence retrieval, model
investigation, professional review or MRT-01.

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
Purpose is operations or research; the operation-specific grants are listed
above and validated by `oi_api.access`. Question and review operations require
operations purpose; creating an identity never grants those additional actions. Expiry must include a timezone. Unknown fields, duplicate token
hashes, oversized/invalid files and unavailable files fail closed. Bearer tokens
must be 32–256 ASCII letters, digits, dots, underscores, tildes or hyphens.

For a generated fixture and a complete automated demonstration, run:

    python3 apps/api/tools/verify_registry_compose.py
    python3 apps/api/tools/verify_sources_compose.py
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

## Run without containers

Use Python 3.12 on the reviewed platform. Download is an explicit build step:

    python3.12 -m venv /tmp/oi-h1-api-venv
    /tmp/oi-h1-api-venv/bin/python -m pip download --require-hashes --only-binary=:all: --dest /tmp/oi-h1-wheels -r apps/api/requirements.lock
    python3.12 apps/api/tools/check_dependencies.py --wheel-dir /tmp/oi-h1-wheels --sbom /tmp/oi-h1-sbom.json
    /tmp/oi-h1-api-venv/bin/python -m pip install --no-index --find-links /tmp/oi-h1-wheels --require-hashes -r apps/api/requirements.lock
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
| GET /health/ready | 200 only for PostgreSQL major 16 at revision 0011_evidence_convergence; bounded 503 otherwise. |
| GET /v1 | Reports synthetic_patient_registry stage, implemented synthetic capabilities and the configured authentication mode. |
| GET /v1/openapi.json | Local typed contract, including bearer security; no CDN documentation UI. |
| POST /v1/patients | Authenticated synthetic creation; trusted actor/org/purpose; 201 for new identity or 200 for identical retry. |
| GET /v1/patients/{patient_id} | Requires read action, exact-patient grant and persisted organization match. Missing and inaccessible identities both return 404. |

The manifest's patient_data_enabled: false means identifiable/clinical patient
data is excluded; synthetic_registry_enabled: true reports the bounded identity
capability. Authentication is deny_all, synthetic_fixture or trusted_provider.
All responses use Cache-Control: no-store. External or ambiguous Host headers
are rejected. Ordinary POST bodies are bounded to 16 KiB; original source imports to 72,000
bytes and authored evidence imports to 210,000 JSON bytes (decoded originals stay
limited to 32 KiB). Chunked bodies have the same bounds and a five-second deadline. Malformed/duplicate credentials are rejected.
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

**Historical evidence-convergence checkpoint:** [draft #307](../../docs/engineering/H1_EVIDENCE_CONTINUITY.md)
converges the existing metadata/citation, authored-content/report and follow-through
owners without copying PostgreSQL state into a competing SQLite chart. Its
DDL-free `0011_evidence_convergence` joins the two published `0010` lineages;
serving at that checkpoint required that exact single head. The current document
candidate explicitly upgrades to `0012_reviewed_documents`; original migration files and receipt
meanings remain unchanged. Citation identity grants no content/assessment rights.
Actual combined acceptance, populated upgrades and restored HTTP are recorded
with the exact candidate head in that bounded receipt. Live permitted biomedical
retrieval, full clinical/annotation parity, accounts, consent, EHR/LIS,
professional review and complete MRT-01 remain incomplete.

The current #354 continuation retains ordinary text/PDF custody and manual
selection history, adds the existing restored-document verification, and awaits
its own combined API/recovery and browser result. See the current checkpoint
above; historical local or parent-hosted counts are not substituted.

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
