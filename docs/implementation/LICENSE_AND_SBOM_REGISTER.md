# License and SBOM register

**Decision, 5 November 2026.** No dependency, dataset, model, hosted service or distribution license is added. The existing exact-artifact determination is limited to local H1 development and evaluation with independently authored fictional cases. The application is **not cleared for commercial distribution, institutional installation, processing real patient data or clinical use**. The rights dossier and tests are cumulative; this register is an index, not a second approval authority.

## Scope and fingerprints

Inspected the application manifest/locks at [#540](https://github.com/OpenxIntelligence/open-intelligence/tree/299cfb54df8259c6d72ddd88f3e0c08ca3dda3f4) and on the [#542 integration candidate](https://github.com/OpenxIntelligence/open-intelligence/tree/80660730df2b8a819aa37215e39bc7f9af55c0f7). The [#545 frontend SBOM donor](https://github.com/OpenxIntelligence/open-intelligence/tree/b91e7b9cd05cfa0d954745289b3ed737330d6e40), also included for integration review, changes the web rights gate, its tests and CI, but no lock. The locks, not an older planning count, identify the set below. The [architecture decisions](ARCHITECTURE_DECISIONS.md) distinguish the integration candidate from accepted main. This document reports inspection; do not infer an exact-revision CI result from its existence.

| Artifact (SHA-256 of checked-in bytes) | Use and evidence |
|---|---|
| [requirements.in](../../apps/api/requirements.in) · `59497051b5cdb3dcd159cd3ce04784c3079de946c09a6fbb5f1ce8420d177fa6` | Direct pins: FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn, pg8000 and pydicom. pypdf is retained in the resolved lock and used by the existing documents owner. Rebuilding from the input alone is not equivalent. |
| [requirements.lock](../../apps/api/requirements.lock) · `708dbcebd47c232b087cc7edc95d37def4e07195883c917418d6eb10f9738dc7` | 26 exact SHA-256 wheel identities; CPython 3.12/Linux x86_64, no extras. |
| [Python rights inventory](../../apps/api/dependency-license-inventory.json) · `a6e6b8c1854385677939d9446d85170f1e36cf6c54a47015ed5620144830aecc` | Per-wheel filenames and hashes, selected expressions, license-file paths/hashes, Requires-Dist and markers, native files, provenance, obligations, scope. Retain [third-party notices](../../apps/api/THIRD_PARTY_NOTICES.md). |
| [package.json](../../apps/web/package.json) · `b9b3d91c6853c798d468e05f9ca19093b37d065849b32177db2d3e73728790c7` | First-party package `open-intelligence-h1-web@0.1.0`, private, `UNLICENSED`. Two direct application dependencies, four development pins, two package aliases. |
| [package-lock.json](../../apps/web/package-lock.json) · `b8a6bbf057ec46eba267e921362484cec0d183f99a23217d63de1a29be5e8c3b` | v3; 20 third-party locations plus root; registry tarball URL and SHA-512 integrity for each. Two optional entries are not installed by the H1 workflow. |

## Python runtime: selected expressions for the exact wheels

| Package | Version | Recorded wheel evidence (cumulative where applicable) |
|---|---|---|
| alembic | 1.20.1 | `MIT` |
| annotated-doc | 0.0.5 | `MIT` |
| annotated-types | 0.8.0 | `MIT` |
| anyio | 4.16.0 | `MIT` |
| asn1crypto | 1.5.1 | `MIT` |
| click | 8.5.0 | `BSD-3-Clause AND PSF-2.0` |
| fastapi | 0.162.0 | `MIT` |
| greenlet | 3.5.6 | `MIT AND PSF-2.0` |
| h11 | 0.16.0 | `MIT` |
| idna | 3.20 | `BSD-3-Clause` |
| Mako | 1.4.3 | `MIT AND Python-2.0` |
| MarkupSafe | 3.0.4 | `BSD-3-Clause` |
| opentelemetry-api | 1.45.2 | `Apache-2.0` |
| pg8000 | 1.31.6 | `BSD-3-Clause` |
| pydantic | 2.14.1 | `MIT` |
| pydantic_core | 2.50.1 | `MIT AND BSD-3-Clause AND NCSA AND SunPro AND Unicode-3.0 AND Unicode-DFS-2016 AND Zlib AND (Apache-2.0 WITH LLVM-exception)` |
| pydicom | 3.0.2 (build 1oi1) | `MIT AND BSD-3-Clause` |
| pypdf | 6.21.4 | `BSD-3-Clause` |
| python-dateutil | 4.0.0 | `BSD-3-Clause` |
| scramp | 1.5.0 | `MIT-0` |
| SQLAlchemy | 2.0.55 | `MIT` |
| starlette | 1.10.0 | `BSD-3-Clause` |
| typing_extensions | 4.16.0 | `PSF-2.0` |
| typing-inspection | 0.4.4 | `MIT` |
| tzdata | 2026.6 | `Apache-2.0 AND LicenseRef-IANA-TZ-Public-Domain` |
| uvicorn | 0.54.0 | `BSD-3-Clause` |

FastAPI requires Starlette, Pydantic and the OpenTelemetry **API** among others; its telemetry SDK/exporter extras are **not** in the lock. Pydantic requires the matching pydantic-core wheel; Alembic requires SQLAlchemy and Mako; SQLAlchemy uses greenlet on this platform; pg8000 requires python-dateutil and scramp. Marker-specific branches and optional extras in supplier metadata are not runtime approvals. No ASGI standard extras, SQL vendor drivers, DICOM codecs or downstream SDKs are implied.

The [pydicom derivation manifest](../../apps/api/tools/pydicom-runtime.json) pins upstream wheel SHA-256 `abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b` as a preparation input. Only the code-only wheel `cbd2edf9051da7cce3f53184cc16dde1238b065845acfa0ceb241d0e8f06acc4` is installed. Preparation removes example/test assets and the eager examples import, retains the BSD GDCM-dictionary notice, and checks member/hash consistency. Pixel data, upstream example records, download helpers, optional GPL codecs, training and diagnostic interpretation are outside scope.

The supplier all-target native inventory lists 99 Rust crate entries, with 13 further embedded-runtime source evidence entries. This is not a count of independently proven linked objects. Mako's inherited, unversioned Python notice is conservatively retained and blocks general redistribution pending clarification. The pydantic-core notice chain cannot be reduced to MIT. ELF dependencies such as libc, libgcc_s and libstdc++ come from the host; their versions/terms are not resolved by a wheel hash.

## Web build and runtime: all non-root package-lock entries

| Lock location (alias → actual package where applicable) | Version | Manifest SPDX | Lock role |
|---|---|---|---|
| @napi-rs/lzma-linux-x64-gnu | 1.5.1 | MIT | Optional; omitted in CI |
| @types/estree | 1.0.10 | MIT | Development/build |
| @types/react | 19.3.0 | MIT | Development/build |
| @types/react-dom | 19.2.2 | MIT | Development/build |
| csstype | 3.2.3 | MIT | Development/build |
| esbuild → esbuild-wasm | 0.28.2 | MIT | Build alias |
| fdir | 6.5.0 | MIT | Development/build |
| fsevents | 2.3.3 | MIT | Optional; omitted in CI |
| nanoid | 3.3.20 | MIT | Development/build |
| picocolors | 1.1.1 | ISC | Development/build |
| picomatch | 4.0.7 | MIT | Development/build |
| postcss | 8.5.32 | MIT | Development/build |
| react | 19.3.1 | MIT | Application |
| react-dom | 19.3.1 | MIT | Application |
| rollup → @rollup/wasm-node | 4.67.4 | MIT | Build alias |
| scheduler | 0.28.0 | MIT | Application |
| source-map-js | 1.2.2 | BSD-3-Clause | Development/build |
| tinyglobby | 0.2.17 | MIT | Development/build |
| typescript | 5.9.3 | Apache-2.0 | Development/build |
| vite | 7.3.7 | MIT | Development/build |

The application uses React and React DOM; the latter uses scheduler and peers on React. Vite's build pulls the override aliases and modules such as PostCSS (nanoid, picocolors, source-map-js) and tinyglobby (fdir, picomatch). Optional peer toolchains from Vite are not automatically present. `MIT` in Vite's manifest is not the entire published notice file: the existing [artifact screen](../project-state/TECHNOLOGY_STRATEGY.md) recorded MIT, BSD-2-Clause, CC0-1.0 and ISC notices. Preserve the exact notice material of Vite and the WASM distributions. The Node engine lower bound is 22.12.0; it does not identify a tested Node binary or OS image.

## Reproduce the scoped evidence

From the repository root, within the specified disposable synthetic build/CI profile:

```sh
python apps/api/tools/prepare_dependencies.py --wheel-dir /tmp/oi-h1-wheels
python apps/api/tools/check_dependencies.py --wheel-dir /tmp/oi-h1-wheels --sbom /tmp/oi-h1-sbom.json
python -m pip install --no-index --no-deps --require-hashes --find-links /tmp/oi-h1-wheels -r apps/api/requirements.lock
python -m pip check
```

Within `apps/web`:

```sh
npm ci --omit=optional --ignore-scripts --no-audit --no-fund
npm run rights
npm audit --omit=optional --audit-level=high --json
```

[API verification](../../apps/api/tools/check_dependencies.py), [preparation](../../apps/api/tools/prepare_dependencies.py), [web evidence checks](../../apps/web/tools/license-gate.mjs), [API CI](../../.github/workflows/h1-api.yml) and [web CI](../../.github/workflows/h1-web.yml) are the executable owners. The npm gate checks identity, registry, integrity declaration, actual installed notice bytes, unsafe paths and absent optional packages; it writes `.licenses/inventory.json`. In the #545 implementation, `node tools/license-gate.mjs` also emits `.licenses/web.cdx.json` (CycloneDX 1.6) only after a successful inspection, first removing any stale BOM. Its components describe installed npm locations using the actual package name/purl, version, lock archive SHA-512, declared license and build/development flag; absent optional locations are counted in BOM metadata and retained only in the evidence inventory. This is the installed build environment, not a file-to-browser-bundle link map. The web CI checks the BOM is nonempty and preserves it beside `verification-web/api.cdx.json`. The Python gate emits CycloneDX 1.6 for 26 runtime wheels, 99 supplier all-target crates and 13 embedded-runtime evidence entries; these scopes must not be collapsed into 138 linked packages. Neither BOM describes the full OS image, and an audit threshold without its dated DB/result does not prove absence of vulnerabilities.

## Non-application components and operation rights

| Surface | Evidence and permitted scope | Held or excluded |
|---|---|---|
| Container/runtime stack | [Compose](../../apps/api/compose.yaml) selects linux/amd64; [Dockerfile](../../apps/api/Dockerfile) uses `python:3.12.16-slim-bookworm`; database is `postgres:16.15-bookworm`. Synthetic loopback composition only. | Tags are not digests. Inventory actual pulled platform manifests and layers, OS packages, runtimes, PostgreSQL binaries, native linkage, network policy, keys and backup artifacts before redistribution or institutional deployment. |
| Continuous integration | Both H1 workflows use ubuntu-24.04, [checkout@11d5960](https://github.com/actions/checkout/blob/11d5960a326750d5838078e36cf38b85af677262/LICENSE), [setup-python@a26af69](https://github.com/actions/setup-python/blob/a26af69be951a213d495a4c3e4e4022e16d87065/LICENSE) and [upload-artifact@ea165f8](https://github.com/actions/upload-artifact/blob/ea165f8d65b6e75b540449e92b4886f43607fa02/LICENSE). All three pinned action root files were read and are MIT. API uses Python 3.12.16; web requests 3.12 and records actual Node/npm. | Runner, Chromium/CDP, action bundles, npm/pip, engine/Compose plugins and base OS are not shipped client dependencies. Root action licenses do not clear bundled npm modules or a runner snapshot. |
| Candidate infrastructure and scanners | [Technology catalog](OPEN_SOURCE_TECHNOLOGY_CATALOG.md) records source references and dispositions. | No new cache, broker, IdP, secret manager, object service, collector/exporter, dashboard, orchestrator or scanner selected as runtime. Candidate build manifests screen dependencies; they are not distribution attestations. |
| Research/reference applications | [Research-only Python lock](../../tools/research/requirements.lock) is a historical separate environment (different Pydantic etc.); [reference SBOM](../safety-packet/SBOM.md) describes a different deliverable. | Do not merge research pins into H1 or imply that LangGraph, optional model paths, SQLite/vector tools or live literature services are connected H1 dependencies. |
| Clinical terminology, literature, models and scientific assets | [Data rights](../safety-packet/DATA_RIGHTS.md), [rights broker](../RIGHTS_BROKER.md) and the existing per-item/source owners govern the specified operation. | Software permission does not authorize lookup, caching, bulk extraction, display, embedding, external submission, model training, rehosting, export or redistribution of a resource. Separate version, license/DUA, field/territory, attribution, retention, revocation and intended-use evidence for each; unknown denies the operation. |
| First-party code and synthetic data | Independently authored fictional cases for bounded engineering; first-party web manifest states `UNLICENSED`. | No implicit project license from public visibility, third-party licenses or this register. No real person's medical records or pseudonymized replicas; no real-data, commercial, clinical, outreach or release authorization. |

**Release handoff.** The technical owner records the exact source commit, artifact digest, platform, package URLs, dependency edges, files/purls, license text hashes, patch/derivation notices and model/data exclusions. Generate SPDX or CycloneDX for the final image/browser bundle (Syft is a candidate), compare it against both application gates and investigate unmatched native objects, fonts, WASM, vendored code and OS entries. The security owner records scanner/database/date, exploitability, accepted exceptions and expiry; the rights reviewer decides each actual operation, distribution form and notice/source-offer obligation. Archive the reports and restore/revocation evidence with the build digest. A component, image, file, platform, license, optional group or intended-use change invalidates the affected decision. The [release acceptance record](RELEASE_ACCEPTANCE.md) owns the final disposition.
