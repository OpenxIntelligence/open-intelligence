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
- Overview is connected; Records can read authorized canonical case bindings,
  immutable source versions and current unreviewed source-reported statements.
- An explicitly selected original is fetched only with independent
  `source_original_read` permission and its UTF-8 bytes are checked against
  the SHA-256 and version/state in the last authorized source index. Historical
  originals remain inspectable, while a concurrent amendment requires an
  explicit index refresh before the original can be shown again.
- Journey, Investigations and Review remain visibly unconnected. The original
  reference application and evidence/report/review owners are not replaced.

No real account management, identity proofing, real clinical records, frontend
source imports, caregiver delegation, consent, live model, biomedical retrieval,
clinician review or deployment is introduced. The backend remains responsible for authorization. An authorized
request can complete after a later grant change; this UI is not a consent service.

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
source-case binding, actual fictional source ingestion by the existing API,
source amendment/history, original-read permission withdrawal, exact original
SHA-256 verification and stale-index rejection, reload clearing, landmarks and
responsive width. The test changes synthetic grants
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

## Read-only case and source integration (new stacked branch)

This branch composes the **original reviewed React patient entry** from #181 (all
17 files imported verbatim at its verified source head) above the **original
PostgreSQL canonical patient/case/source/record-request owners** in #193.
The additional frontend does not create a case store, source ledger, evidence
authority, clinical assertion or new runtime dependency.

After explicitly opening an authorized fictional patient, choose **Records**:
- **Check authorized cases** fetches the existing canonical case-binding projection.
  The operator's fixture must separately grant case_binding_read and patient_read.
- **Inspect source versions** requests the exact active, scoped case's source index.
  That requires an independent source_read grant; raw original bytes are not exposed.
- See every immutable version/hash, provenance, supersession link, and current
  version's source-reported statements. React renders untrusted statements as text.
  Every statement is marked as **unreviewed**, not an interpreted clinical finding.
- Re-reading the patient, starting another identity, disconnecting, changing the
  synthetic grant, receiving a denied response or invalid contract clears the
  affected records. Late responses from a prior patient or case cannot repaint
  the new selection.

The canonical PostgreSQL API remains authoritative for all records. The
source-index API explicitly reports clinical_interpretation=false and
research_review_invalidation_integrated=false. This view does **not** connect the
earlier SQLite PWM/Composer/report-review flow (#179); it provides one real
PostgreSQL/React integration seam for later reconciliation. Actual real-patient
identity, consent, source rights, clinical review and deployment remain blocked.

### Verification (exact branch head required)
The existing reviewed H1 web workflow now targets this integration branch and
runs the original unit suite with added contract/isolation cases, TypeScript
compilation, locked dependency/rights checks, and actual Chromium over a
disposable PostgreSQL 16 server. Its browser journey also imports an independent
fictional case+pathology report, displays exact source IDs and a literal
HTML-like statement without execution, amends the original, checks old/new
version history, removes source_read and checks that the previous content
disappears.

No result is claimed until the hosted job has passed on this branch's **final
commit**. Keep parent #193, original frontend #181, patient workspace #179 and
the separate UX source-owner branches in draft review; do not auto-merge.

## Exact-original inspection boundary (draft)

The Records screen never infers a diagnosis or promotes a source-reported
statement to clinician-approved assessment. The operator must grant distinct
`patient_read`, `case_binding_read`, `source_read`, and `source_original_read`
actions as appropriate. Every source GET is scoped to the selected canonical
patient and bound fictional case, with the token kept only in tab memory.
The original reader limits JSON to 128 KiB and decoded original bytes to
64 KiB, checks the exact document/source/version/state, recomputes SHA-256, and
renders the bytes as escaped text (not HTML). A denied, malformed, stale,
tampered or late reply clears the original. These checks provide software
integrity in the synthetic environment; they do not establish real-world
identity, consent, medical validity, clinical safety or PHI authorization.
