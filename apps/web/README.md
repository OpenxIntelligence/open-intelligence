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
