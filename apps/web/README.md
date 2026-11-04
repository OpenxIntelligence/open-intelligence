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
- Overview, Records, Journey, Investigations and Review connect to the same
  canonical fictional patient/source context. Review records only nonterminal
  source-verification returns. The old reference application remains unchanged.

No real account management, identity proofing, identifiable clinical records,
caregiver delegation, consent, live model, biomedical retrieval or deployment is
introduced. Source inputs are independently authored fictional reports. The backend remains responsible for authorization. An authorized
request can complete after a later grant change; this UI is not a consent service.

## Saved-question follow-through

The Investigations workspace can turn an existing saved question into an
attributed follow-up task with an owner and revisit date or trigger. Tasks show
their original source anchor, amendment/recheck state and append-only history.
Assignment, acknowledgment, completion and deferral use the canonical API;
status changes survive application restart. An uncertain write preserves its
exact request for explicit recovery and blocks a different write until resolved
or abandoned. Changing patient, case or credentials clears task content and
rejects late responses.

This builds on the authored-question, source-inspection, verification-return and
source-only brief workflow from #287. [The task contract](../../docs/engineering/H1_QUESTION_FOLLOWTHROUGH.md)
records exact acceptance evidence and limits. An owner label does not grant
access, task completion is not clinical approval, and no notification is sent.

## One question, distinct evidence permissions

[Draft #307](../../docs/engineering/H1_EVIDENCE_CONTINUITY.md) composes the existing
fictional metadata discovery/citation controls with the independently authored
original/comparison/report panel on a canonical saved question. Citation and
comparison writes retain separate exact retry identities. Metadata permission
cannot reveal an authored quotation, and report permission cannot grant metadata
access. Patient/case/credential changes and common authority denial clear both
views; specific evidence grants retain their own boundaries.

The two original browser helpers remain separate, with distinct selectors and
observer state. The combined journey also checks one question through a citation,
report and independent permission changes. See the linked record for actual
combined-head verification; implemented controls alone do not prove that gate.

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

### World Model and original-read cancellation

Journey uses the same source owner and carries a per-read access receipt
separately from its stable content fingerprint. If opening or closing an
original invalidates a pending World Model request, the cancelled view leaves
the loading state and requires an explicit retry. Its late response cannot
restore the cancelled context. An already completed World Model remains
available across original open/close actions. This behavior does not add a
background retry, model call, approval or new clinical state.

### Connected source questions

The current source-derived World Model also supplies the existing **Investigations**
workspace. A user can prepare a source-only context for an exact current finding,
save its question through the independent question grant, and refresh persistent
question history. A source amendment flags the earlier question for reassessment
while retaining its original source/version/line. The current UI uses a standard,
visible provenance question; free-text browser drafting and clinical review are
separate future work.

Preflight and question-list `/2` decoders require explicit snapshot provenance
and source-access receipts. Only the stable canonical content fingerprint enters
preflight equality; fresh receipts do not invalidate an otherwise identical
packet. An uncertain save retains its same-session request key for a deliberate
retry. Case, source or permission changes invalidate pending consumer views.
Legacy fingerprint rows remain visibly in need of reassessment. Nothing in this
workspace executes a model, grants clinical approval or creates another patient
or source store.

### Connected verification-return inbox

Review derives its inbox from the same persisted source questions. Each item
shows its question, source context and verification state; a bounded reason
belongs to its selected question. Protocol versions, hashes and source-access
receipts remain available in disclosure details. A return records an operational
request for independent verification; it does not notify a person, approve a
finding or establish reviewer credentials.

Current and historical receipts retain their source/queue provenance. A source
amendment moves an old return into history and requires a new current question.
Legacy contracts cannot masquerade as current canonical work. Queue reads and
return writes use separate server-side grants.

After an uncertain write response, **Retry this exact return** preserves the
captured question, reason, fingerprint and request key. Navigation and a
successful same-case source refresh retain that minimal in-memory intent, so an
already committed historical return can be recovered after amendment. Editing
that uncertain intent is disabled; a stale/conflicting 409 response stops the operation
without creating a replacement key. Patient, case or credential changes and
authoritative permission denial clear it. Late requests cannot restore another
case's queue or unlock a newer in-flight return. No browser storage is used.

The new browser journey exercises the actual PostgreSQL/API/React source question
→ return → source amendment → preserved history → new question/return workflow,
independent grant denial and recovery, and captures a populated desktop view.
Its fake-response-free workflow is separate from client-module tests that inject
network errors to verify retry mechanics. See
[the review integration record](../../docs/engineering/H1_SOURCE_QUESTION_REVIEW_RETURN.md).

### Saved-question brief and fresh download

The existing question panel can prepare a readable brief for a current canonical
question. The question and exact source-reported statement remain distinct from
clinical interpretation. An independent `source_brief_export` grant is required
in addition to patient, question and source reads. The brief includes source
versions, dates, uncertainty and historical context; technical identifiers are
available in a disclosure.

Download repeats preparation on the server and verifies the new UTF-8 body hash
before creating a file. A cached preview cannot substitute for this check.
Patient, case, credential or source-context changes invalidate in-flight work,
including delayed digest calculation. An amended source preserves the old
question with reassessment status and prevents a new export of that stale intent.
See the [contract, acceptance and limits](../../docs/engineering/H1_SOURCE_LINKED_BRIEF.md).

### Verification (exact branch head required)

The existing reviewed H1 web workflow now targets this integration branch and
runs the original unit suite with added contract/isolation cases, TypeScript
compilation, locked dependency/rights checks, and actual Chromium over a
disposable PostgreSQL 16 server. Its browser journey also imports an independent
fictional case+pathology report, displays exact source IDs and a literal
HTML-like statement without execution, amends the original, checks old/new
version history, removes source_read and checks that the previous content
disappears.

The browser journey also temporarily holds delivery of a real completed World
Model HTTP response, opens and closes an original, releases the late response,
and verifies that only an explicit retry restores the view. It preserves the
actual response body, status, access receipt and content fingerprint; it does
not replace the server with a mocked successful response.

The extended question journey also prepares the brief, downloads actual bytes,
checks them against the freshly returned body, withdraws export permission,
preserves stale question history after amendment and prepares a new question.
The client suite covers exact contracts, source/body tampering and context
changes during both the request and asynchronous hash verification.

No result is claimed until the hosted job has passed on this branch's **final
commit**. Keep parent #193, original frontend #181, patient workspace #179 and
the separate UX source-owner branches in draft review; do not auto-merge.
