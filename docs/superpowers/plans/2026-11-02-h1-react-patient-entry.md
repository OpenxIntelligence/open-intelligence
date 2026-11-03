# H1 React patient workspace implementation plan

Goal: connect the accepted React/Vite/TypeScript frontend to the already implemented FastAPI/PostgreSQL 16 patient registry without introducing another patient store.
Spec: existing issue #119 / parent #106, backend #172/#162, accepted H1 direction; OI-004, OI-007, OI-010, OI-013. Existing #166 remains runnable migration reference.
Baseline: #172 head 4a14fbe385781eab064e6526813938ae7a3f8a26; downloaded UI artifact 13190067625 digest 75f7c38c92c5dafbe592feeba5a7e0cec05e23b10ea6ee02047476ffec1a6c80, checked integration checkout 96edf012e7c5c0d0682af13ba00a252272ec5f31.

## Design
Only apps/web plus a dedicated CI job and this plan. No API, schema, domain, authorization, actor fixture or prototype rewrite. State contains a transient credential and visible patient selection only; no browser patient database or persistent token storage. Fetch only same-origin explicit /health and /v1 operations through a loopback-only development proxy. Creation does not imply permission to read. Unsupported patient-source/research/review capabilities remain labeled unavailable. First-party CSS and system fonts; no remote artwork, scripts or medical content.

React and ReactDOM are proposed exact 19.3.1; Vite 7.3.7 (Vite 8 rejected by transitive-license gate); TypeScript 5.9.3; types exact pinned. Primary upstream terms plus resolved lock and actual installed LICENSE/NOTICE hashes required before build. npm scripts disabled during package acquisition. Transitive terms and known vulnerabilities gate validation; unknown or restrictive terms block. Development qualification is not commercial/clinical distribution clearance; host/browser/native toolchains remain separately scoped.

## Implementation and tests
- [ ] Add failing dependency-free state/client tests for no authority escalation, exact response validation, credential clearing, delayed responses, no credential egress, idempotent retry and sanitized errors.
- [ ] Implement typed controller with memory-only credentials, cancellation/generation guards, no automatic retry or auto-read grant.
- [ ] Implement accessible task-first React interface: registry status, credential session, explicit synthetic create, authorized patient read and clear unavailable-module states.
- [ ] Add locked build, per-installed-package license evidence and a refusal on unknown terms.
- [ ] Run real PostgreSQL/FastAPI + Vite Chromium journey: default denial, create/retry, separate grant, read, revoke then deny/clear, expired credentials, reload forgets token, no browser storage, keyboard/mobile checks.
- [ ] Preserve original code byte-for-byte; publish one isolated draft on #172, source/test evidence and existing docs updates. No merge/deployment.

## Remaining limitations
The source-owned local access fixture is not accounts, human identity, caregiver delegation or consent. A request authorized before revocation may complete. This client guards display races but is not a general security boundary. Backend checks own permissions. Raw document ingestion, sourced investigations and durable professional review await their accepted source owners and routes. The rest of the product remains visible as scope, not implemented functionality.

## Observed qualification trail

Vite 8.3.5 acquired with scripts disabled but blocked before build for MPL-2.0
Lightning CSS and absent native-package notices. Vite 7.3.7 removed the required
MPL component but still exposed native-package notice gaps. Publisher-provided
WASM variants for Rollup 4.67.4 and esbuild 0.28.2 were selected for this bounded
build; optional native helpers remain omitted/uninspected. No gate allowlist was
broadened. Exact WASM lock from CI artifact 13192028408 is now frozen and bootstrap
removed. Transitive source declarations and root notices do not prove compiled
object, host, container or commercial-distribution rights.

Initial absent-module test failure preceded typed client implementation. Sixteen
client checks then passed. A seventeenth regression reproduced old pending-read
content reappearing after new identity creation; invalidating that selection before
creation fixes it. All 17 client checks pass locally with available TS 5.8.3;
full pinned TSX and real PostgreSQL/browser verification remain hosted gates.
