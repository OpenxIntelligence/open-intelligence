# Open Intelligence H1 patient workspace

This is the first **React + Vite + TypeScript** entry connected to the existing
**FastAPI/PostgreSQL 16** patient registry (#172, #162). It does not replace the
canonical identity owner, existing source-ledger application (#166), or accepted
whole-platform architecture. It advances #119, not its full ingestion-to-review
acceptance criteria.

## What works in this increment

- Real API readiness, no fake online status.
- An explicitly supplied local **synthetic fixture** credential, held only in
  JavaScript memory; never in localStorage, sessionStorage, URLs or cookies.
- Create an opaque fictional identity using the existing transactional registry
  and idempotency key. A retry keeps the same key; creation is NOT a read grant.
- Read only an explicitly granted identity under its persisted organization.
- Clear the displayed patient on a new request, refusal, credential change,
  logout or expiry; discard late responses from older selections/sessions.
- Overview connected; Journey, Records, Investigations and Review clearly marked
  not connected. The old reference application remains available unchanged.

No real account management, identity proofing, clinical records, source imports,
caregiver delegation, consent, live model, biomedical retrieval or deployment is
introduced. The backend remains responsible for authorization. An authorized
request can complete after a later grant change; this UI is not a consent service.

## Integrated read-only Records view (draft on #193)

This integration **reuses all 17 unchanged source-owned React files from #181**
and mounts the authorized received-record contract from #193. No second
patient, request, source or access store is introduced.

- The **Records** navigation works only with a selected, separately readable
  canonical patient. "Refresh authorized requests" calls the source-owned
  `GET /v1/patients/{id}/record-requests` under `patient_read` and
  `record_request_read`. It does not fabricate documents or send requests.
- Received state, historical amendment reconciliation and revoked-binding
  warnings come from the exact PostgreSQL receipt projection. A caller without
  independent `source_read` can see the operational received status but not
  source identifiers or hashes.
- Original text is **never loaded automatically**. Each read is an explicit
  action against `GET .../cases/{case_id}/sources/{source_id}`, additionally
  requiring `source_original_read`. The response's selected case, version
  and SHA-256 must match the authorized receipt reference; the UI recomputes
  the original UTF-8 SHA-256 before showing the text.
- Patient selection/create, credential replacement, disconnect, refused
  record refresh, and in-flight response supersession clear old source text
  and sensitive record references. No credential, patient or original is stored
  in localStorage/sessionStorage/cookies; the server remains authoritative.
- An amended source remains explicitly **historical**; "received" is an
  operational document receipt, not clinical review or validated provider
  identity. The UI cannot approve, reassign, reconcile or alter evidence.

The hosted web runner tests typed-client denials and real Chromium over the
existing PostgreSQL 16 API. Its fictional fixture creates a canonical patient,
qualified case binding, request, original report and immutable receipt; it
checks authorized viewing, independent source and original grants, revocation,
no stale text, and 390px containment. Screenshots are retained only as
synthetic verification artifacts. No added npm packages or Next.js.

This is **not** the original-file upload UI, general case-document browser,
signed review workflow, Patient World Model or clinical deployment.
Consent, professional identity, rights, external institution verification,
production access/auditing/RLS, original-file processing beyond the strict
fictional text contract and full React↔clinical-Composer integration remain
independent release gates. Continue to keep every parent PR draft/unmerged.

## Source-derived Patient World Model (H1 integration candidate)

An **Investigations → source-only** view is now connected to the same
PostgreSQL 16 clinical source owner as Records, without adding a second
patient/source database, model, evidence store or backend dependency.

The backend imports the original source-owned
`src/open_intelligence/world_model.py` **byte-for-byte** (Git blob
`cbdc18ff2e41fa2e18a4e96297380541e99e2c3b` from the already verified
clinical World Model stack). An in-memory PostgreSQL adapter reuses that pure
source assertion/conflict projector; temporary ordinal IDs never leave the
adapter. API responses retain canonical `SRC-*` original-version identifiers,
SHA-256, source line, asserted label, document date and specimen metadata.

The user must hold independent `patient_read` and `source_read` grants and
supply the exact case ID. `GET /v1/patients/{patient_id}/cases/{case_id}/world-model`
takes the existing source owner's case-binding lock so its view is consistent
with document import, amendment and case-binding revocation. It rechecks each
original's raw hash and that stored source assertion/line exactly matches the
author-supplied literal original. No source bytes are delivered by this route.

In React, the **Investigations** tab displays current observations, unresolved
reported labels, constrained same-specimen/date disagreements, history and a
source-set fingerprint. The tab is read-only and clears cached observations
on patient/session changes, permission failure, and navigation. Reloading
observations after a source amendment changes the fingerprint and shows the
new current original with the superseded version retained separately. This is
not continuous subscription or distributed invalidation.

**Not yet connected:** investigation question persistence, clinical Composer,
licensed medical literature, evidence interpretation, model execution,
clinical review decisions, provider identity, consent, PHI or a deployable
healthcare product. The older SQLite clinical review stack has not been mounted
into this PostgreSQL service. Absence of question/review records from this
read model **must not be interpreted as no work requiring clinical review**.
No inference of molecular status, diagnosis or treatment occurs.

The H1 workflow runs real PostgreSQL tests for source custody, exact quote/line
verification, conflicting source labels, amendment, wrong patient/organization,
revocation and access rights before the real Chromium journey. A successful
synthetic software gate is not production authorization or clinical validation.

## Durable source-linked questions (draft)

The source-only Composer preflight can now be deliberately **saved** as a
first-party `investigation.source_questions` item in PostgreSQL 16
(revision `0006_source_questions`). Its original source ID, version, exact
line, source fingerprint and preflight SHA remain pinned. Source corrections
make the *historical question* report
`source_reassessment_required` when its authorized case is re-read.
The React Investigations tab can refresh the saved question history after
restart. A saved question has **no assigned or approved clinician**; the
original durable review owner is still separate.

Question creation demands its own `question_create` scope plus patient,
source and Composer permissions. Reading saved history separately requires
`question_read` and source rights. The UI keeps a stable request key for
an uncertain same-preflight retry while the session remains open and never
stores credentials or source content in browser storage. For now the UI saves
the explicit standard provenance question only; the API can accept a
validated custom question, but editable free-text drafting must have an
unsaved-work guard before becoming a browser control.

Full integration boundaries and negative tests:
`docs/engineering/H1_CANONICAL_SOURCE_QUESTION_INTAKE.md`.
No clinical sign-off or user-facing AI answer is inferred.

## Development setup

The backend instructions and exact Python dependency gate remain in
`apps/api/README.md`. Use a disposable synthetic PostgreSQL 16 database and run
its migrations explicitly. Serving never creates schema automatically.

Node >=22.12 is required. From this directory, after reviewing the exact lock:

```sh
npm ci --omit=optional --ignore-scripts --no-audit --no-fund
npm run rights
npm audit --omit=optional --audit-level=high
npm test
npm run build
npm run dev
```

Open `http://127.0.0.1:5173`. The Vite proxy points only to the local API at
`http://127.0.0.1:8000`. An alternative explicit loopback HTTP origin can be set
with `OI_WEB_API_TARGET`; arbitrary remote URLs are rejected. No API CORS policy
or identity grant is broadened. For a built-screen check use `npm run preview`
and `http://127.0.0.1:4173`.

The backend defaults to denying all patient operations. An operator must use its
existing synthetic `OI_API_ACCESS_FILE` fixture contract. Supply a fixture token
in the password field. After creation, separately grant the returned patient ID
in the operator-owned file. Reloading or disconnecting intentionally forgets
credentials and displayed patient information. Do not paste real credentials.

## Reproducible integration

The dedicated `h1-web.yml` job uses the existing reviewed Python wheels and a
real temporary PostgreSQL 16 service. `tools/browser_journey.py` starts the actual
FastAPI process and built Vite UI, then uses Chromium for creation, retry,
independent read grant, permission withdrawal, credential expiry, cross-org denial,
reload clearing, landmarks and responsive width. The test changes synthetic grants
outside the browser; the frontend cannot issue its own permission.

This browser method uses the repo's existing standard-library CDP harness, not
Playwright. Full #119 user study/accessibility/ingestion-to-review acceptance stays
open. Tests and screenshots use only newly created opaque fictional identities.

## Dependencies and permissions

Exact candidates: React/react-dom 19.3.1 (MIT), Vite 7.3.7 (MIT), TypeScript 5.9.3
(Apache-2.0), DefinitelyTyped React types (MIT). These versions were checked against
primary npm/official project records on 2026-11-02. No create-vite template,
remote fonts, copied UI, images, model weights or patient dataset are used.

`tools/license-gate.mjs` evaluates the resolved lock, installed versions, approved
registry origins, SHA512 tarball integrity, manifest terms and actual supplier
LICENSE/NOTICE files before build. Unknown/restrictive declarations and missing
notices fail. It emits exact notice text and SHA256 receipts in `.licenses`.
Optional noninstalled platform packages and native build-tool linkage remain
uninspected; transitive declaration scanning is not a legal opinion or full
compiled-object rights review. The distribution/production release remains on
hold. The root package is private and UNLICENSED to prevent accidental publishing;
this does not change the project's unresolved distribution license.

Upstream records:
- https://registry.npmjs.org/react/19.3.1
- https://www.npmjs.com/package/react-dom?activeTab=versions
- https://www.npmjs.com/package/vite?activeTab=versions
- https://github.com/vitejs/vite/blob/v7.3.7/packages/vite/LICENSE.md
- https://github.com/microsoft/TypeScript/blob/v5.9.3/LICENSE.txt
- https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/LICENSE

## Qualification changes

The initial Vite 8.3.5 gate failed before any build: Lightning CSS carries MPL-2.0
and some native bindings omit actual notice files. The gate was not relaxed.
The supported Vite 7.3.7 line is used with the publishers' `esbuild-wasm@0.28.2`
and `@rollup/wasm-node@4.67.4` variants, locked through npm overrides. These are
build tools only, not an additional frontend runtime or clinical service. Optional
native packages are omitted from installation and remain explicitly uninspected.
This trades build speed for a smaller inspectable dependency surface; actual
benchmark/performance qualification is still needed. WASM compiled contents and
the complete host/toolchain still require deployment-specific rights review.

## State

Initial client tests have been executed locally. Dependency acquisition/full TSX
build and actual API browser validation require their own exact-head CI evidence.
The candidate lock was acquired through hosted CI, hash-checked and inspected. It
is now committed; bootstrap resolution is removed. Subsequent runs use only
`npm ci` against that exact lock, without lifecycle scripts or optional binaries. Do not equate a draft screenshot or previous-parent CI with this build.
