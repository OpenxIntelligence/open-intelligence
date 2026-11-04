# H1 question evidence and patient follow-through convergence

**Status:** #307 acceptance and subsequent source-reading/export receipts are preserved below.
The source-bound image continuation in draft #327 is published; its exact-source
verification and remaining gates are recorded in the final section.
**Scope:** independently authored fictional engineering inputs only.
**Product job:** keep one saved patient question, its citation discovery, separately
authored comparisons/reports and follow-up work in the same governed application.
This is an integration of existing owners, not a new patient or evidence ledger.

## Source ownership and current truth

The live audit on 3 November 2026 found `main` at
`24519839aa8ac1ea3aff88a956349ba72798a72a`. The owners below remained draft and
unmerged. At initial inspection, the existing Notion/Drive progress records stopped at
#298, so their proposed next passage/report implementation was already overtaken
by #300. A fresh read before publication found the later #302 restored-HTTP
receipt; this integration retains that contribution and extends its same-question
metadata/task coverage. Accepted product,
rights, source, identity and clinical-authority constraints remain applicable.

| Input | Pinned commit | Responsibility retained |
|---|---|---|
| #298 (base, including #293) | `89f98824610e23a26d2904a845ed1d930207bd76` | Canonical questions, metadata discovery/citation links and durable follow-through |
| #300 (including #288) | `818c67fcb742941fe1588c4ee130ce07e15a814d` | Patient Overview, authored original evidence, literal human comparisons and preserved reports |
| #302 | `1041b5db00f231a5ede6373a398ea3b9c765d1d7` | Actual HTTP against restored authored-evidence databases; preserves the evidence-only follow-up to tested runtime `c89b22df38a0ede3fff12ee65adb9c9ef1e347cc` |
| #303 | `5400be11f07c5efc4b4b2f60422a279bcb5faeb6` | Evidence/report date and timestamp wire-format correction |
| #304 | `6532e394411f66272c88bce63002dcd40ffbcd37` | Validate and encode original-source disclosure inside the final authority/receipt transaction |

The common patient/source/question owner is #287 at
`247705700080052705817fee9e8f7b54afa8ffaa`. The source, saved-question and source
preflight implementations are identical between the two main input branches.
The newer #304 correction deliberately extends the original-source read boundary
without replacing its owner, schema, grant or receipt semantics.
No original PR is merged, closed or rewritten by this integration.

## Integration contract

- Preserve both published `0009`/`0010` migration lineages byte for byte. Add one
  DDL-free `0011_evidence_convergence` with parents `0010_question_evidence` and
  `0010_authored_evidence_origin`. The application must require that exact single
  head. Test populated upgrades from each old head rather than stamping them.
- Register both metadata and authored-content routes with distinct names. Keep
  follow-through, metadata read/link, authored content read/import/assessment and
  report export grants independent. Preserve their original request-size limits.
- Keep metadata citation identifiers distinct from authored evidence/assessment/
  report identifiers. A citation link neither imports content nor changes content
  rights, report provenance, claim support or human review state.
- Compose both interfaces on the existing canonical question. Distinguish their
  labels, selectors and browser helpers. Preserve each uncertain write's original
  request bytes/key and independent recovery across permitted same-case refreshes.
- Keep source amendment, evidence amendment/withdrawal and access revocation
  distinct. Old report bytes remain historical; current rights still govern
  disclosure. Metadata cannot restore a withheld original or report.
- Retain both actual browser journeys and both evidence recovery probes. The
  metadata/task restore proof and authored-report restore proof cover different
  tables and permissions; neither alone proves complete combined recovery.

## Rights, safety and environment boundary

No dependency, model, content source, asset or hosted service is introduced.
The original locked API/web dependency inventories and notices remain the
selection boundary; their automated checks are not whole-product legal approval.
No project distribution license is changed. The complete platform ambition,
no-Next.js/no-vector H1 constraints and fictional-data restriction remain intact.

The inherited current-workflow patient-data entrypoint scan and its nine offline
regressions passed at the #298 base. This is a bounded static check, not an
exhaustive egress, credential or privacy audit. No identifiable patient records
were acquired or used. Local PostgreSQL and browser capability are not assumed;
actual database and rendered-application acceptance runs on the existing hosted
disposable PostgreSQL/Chromium workflow.

## Tests-first evidence

Tests-only commit `bd3f25846951b6614e5694d8ccdc27826675a6db` adds a combined API/
migration contract and same-question client/composition regressions.

- The two local API contract methods fail for the expected missing authored
  routes and absence of the merged migration head; no import/setup error is
  counted as behavioral evidence.
- [React run 41655157461](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41655157461)
  compiled the existing client and executed 223 tests: 219 inherited passes,
  four intended integration failures, zero skips. Its browser step did not run
  after the expected client-test failure.
- [API/PostgreSQL run 41655157685](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41655157685)
  ran 357 methods: all 354 inherited methods passed, while the three new methods
  produced seven expected failure assertions for missing routes/migration
  convergence. There were no errors/skips. Later browser/recovery steps were
  skipped after this intentional suite failure.
- Independent review also reproduced noncanonical timezone offset minutes accepted
  by Python's parser after the #303 fix. One new renderer regression failed in 32
  subcases before bounding offset hours/minutes. All 16 pure contract methods then
  passed, including unchanged legacy report hashes and valid timestamp bytes.
  This is a focused extension of #303, not normalization of stored timestamps.
- The final combined candidate is independently verified below. Donor success is
  not substituted for a combined-head result. #303's first API attempt passed its
  database/reference suites but failed inherited Chrome startup; its unchanged
  rerun subsequently passed. That failure remains part of the donor record.

Independent client review reproduced protected uncertain-write payload retention
after common authority denial. Four case/source/question/binding-removal
regressions and two same-patient 403/404 regressions failed before the bounded
reset corrections. The transient 503 case still retains exact recovery intent
without authorizing a retry before renewed access. No unauthorized server write
was demonstrated. The corrected local Node runtime suite passes 258 non-render
tests; it uses Node's type stripping and is not a TypeScript/React build claim.
All 287 reference tests also pass locally. The subsequent hosted acceptance below
provides the actual combined database/browser result.

## Published code and browser verification

The combined runtime is `477f24826a8a102c7437c993d69877c1f250b951`, tree
`cd8d909ad2844e7fbd37ae30a9a10b9123374666`, in
[draft PR #307](https://github.com/OpenxIntelligence/open-intelligence/pull/307).

[React/browser run 41658525265](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525265)
checks out that exact feature commit. It passed **266 client tests, zero skips**,
TypeScript checking, the production Vite build and the actual React/FastAPI/
PostgreSQL 16 journey. Both original evidence journeys, source custody, questions,
review returns, Overview, follow-through and cross-case clearing remain present.

The new browser receipt records the same canonical patient, case, question,
original source snapshot and preflight for a saved fictional citation and an
immutable authored comparison report. Independent metadata-read and report-export
denials returned 404; denied export created no Blob and did not change an earlier
download. Metadata does not authorize content, and a report does not appraise a
catalog entry. This browser callback does **not** establish a task on that same
question; that belongs to the combined API/recovery acceptance.

Downloaded browser artifact **13241475582** was verified against archive SHA-256
`abe9604cb4adabfd542d3c9a7590adffb95ed5076fc4f24d83636a79264f0053`.
All **398 tracked source files** in its source archive match the published commit
byte for byte. Its actual original evidence download is 301 bytes, and its two
report downloads are 3,859 and 3,860 bytes. The files' SHA-256 values match their
respective stored receipts, including unchanged historical report bytes and
literal Unicode quotation anchors. The archived receipt explicitly records
`synthetic: true`, `model_executed: false` and `clinical_approval: false`.

Desktop and 390 px screenshots were visually inspected. No blocking overlap or
horizontal overflow was observed in the inspected captures. The narrow report
uses nested vertical scrolling; those captures do not establish a complete
accessibility or user study. Narrow-browser verification introduces no mobile-app
commitment. Artifacts expire on **10 November 2026**; this receipt and the pinned
source/tests retain the durable engineering evidence.

[Inherited UI run 41658525058](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525058)
passed **287 reference Python/HTTP tests**, **16 Node tests** and the original
browser/layout/race journeys. Its actual checkout is temporary PR merge
`5510bb874c323cb7177db7f14620c2725ef2b361`, whose Git tree was independently verified
to equal `cd8d909ad2844e7fbd37ae30a9a10b9123374666`. It is not misreported as a direct
feature-head checkout.

The retained frontend dependency inventory has no scanner errors and records
exact installed package notices. Its scope remains local fictional development;
`commercial_release_cleared` and `native_object_linkage_reviewed` are false. The
two uninstalled optional platform packages remain explicitly uninspected. This
is a bounded inherited dependency gate, not a newly cleared production stack.

## Actual PostgreSQL and complete recovery acceptance

[API/PostgreSQL run 41658525044](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41658525044),
job **125995235121**, attempt 1, completed successfully on the exact published
runtime `477f24826a8a102c7437c993d69877c1f250b951`:

- **414 API/PostgreSQL tests passed, zero skips**, in 466.419 seconds. Both
  populated old evidence heads upgrade through the actual migrations while
  preserving complete prior rows, sequences, report bytes and exact retries.
  A genuine two-head state remains unready until the explicit merge.
- **287 reference tests passed** in 12.186 seconds; inherited browser journeys
  also passed. These are repeated regression checks, not independent clinical
  cases or additional patient outcomes.
- **All five recovery probes passed:** patient registry, original sources,
  canonical review returns, follow-through with metadata, and authored evidence
  with the combined same-question citation/report/task extension.
- No timeout or deadlock occurred. A longer-than-base unit step was inspected;
  no code, timeout or assertion was weakened in response.

Downloaded recovery artifact **13240724729** matches ZIP SHA-256
`8fc0c6b6e5baff42e2a821c40ac82e39efcc39909fe01170ac352d04ff1cd51c`.
Its `oi.h1-evidence-recovery-acceptance/3` receipt records the exact merged schema,
**18 tables and four sequence states**, with one patient, one canonical question,
two source versions, four evidence versions, three assessments, two immutable
reports, one metadata citation and one follow-through task. The record also
retains their exact identifiers and report hashes.

Actual HTTP is served against four independently restored checkpoints: readable
originals/report; content-class restriction before withdrawal; withdrawn evidence
plus amended patient source; and a revoked binding backed up from a recovered
copy and restored again. `current_database()` verifies the serving target. The
same citation, report and task survive restart/restore on their canonical
question. Original report/retry identities remain intact; open work requires
recheck after source amendment. Content withholding neither grants nor revokes
independent metadata access.

The receipt records **11 / 8 / 15** fresh access events in the readable,
rights-restricted and withheld restored copies. The added citation read requires
exactly one correctly scoped metadata-read event alongside source-read receipts;
new business writes, changed business sequences, unexpected audit events and
mutations to the original database remain rejected. A subsequently restored
revoked binding denies originals, reports, citation/task reads and exact retries
without durable effects. Both `clinical_approval` and `model_executed` are false.

## Current-truth and next integration

The final live branch recheck still found main at
`24519839aa8ac1ea3aff88a956349ba72798a72a`; #307 is an open draft based on #298 and
has not changed main. This cycle deeply inspected the selected API/web owners,
published migrations, affected authorization boundaries, tests, workflows and
artifact source. It is not a complete audit of every open branch or every
technology category. No new patient-journey case research, publisher license,
model evaluation or commercial technology clearance is claimed in this cycle.

The next integration task is to reconcile the existing connected source-reading
owners #305/#308/#309/#310 with this same canonical question/evidence path, after
checking their then-current heads and conflicts. Preserve their ownership rather
than recreating their UI. Separately qualify one real biomedical connector and
its allowed operations before replacing fictional catalog retrieval. Production
identity/delegation, clinical/PDF/annotation parity and professional review
remain distinct backlog items; #306's fictional grant editor does not close
production identity. Existing OI-004/007/008/009/010/013 remain open.

## Acceptance and remaining boundary

The combined candidate passed the bounded one-patient/source/question scenario
through metadata search/link, independently imported authored originals, literal
comparison, immutable reports, follow-through, source amendment, historical
reopening, independent permission denial and exact retry. Populated upgrade paths,
actual restart/restored HTTP, current rights, case-switch clearing and both
browser paths also passed. These results apply to the pinned runtime and stated
fictional contracts; later source changes require their own relevant acceptance.

This remains deterministic, human-authored software verification. It does not
establish live biomedical retrieval, model execution, scientific applicability,
professional signoff, production accounts/consent, full clinical/PDF/annotation
parity, real-patient readiness or deployment. An explicit catalog-to-passage link
would require its own provenance and rights contract; this increment does not
invent that relationship.

## Connected reading, citation history and report-download integration — 3 November 2026

This continuation serves OI-008/009/010/013 and existing issue #92. Reading an
original quotation, asking its canonical question, inspecting evidence and
downloading the resulting report must retain the same source and authority
boundaries. Separate passing branches did not establish this combined behavior.

### Inspected source and preserved owners

| Source | Exact revision | Contribution in this candidate |
| --- | --- | --- |
| Main | `24519839aa8ac1ea3aff88a956349ba72798a72a` | Still the earlier prototype; not the deployed or merged H1 workflow |
| #318, based on #314/#307 | `0db90a45ec256d380c01d503162e31ac8ee419b5` | Baseline connected source reading, question entry, evidence comparison, reports and follow-through |
| #315 | `58bc5f7bc5b8c5ba39e4d93768031aa22cedacd9` | Exact copies of the citation contract and its two added regression methods |
| #316 | `66f44d42b8d47a1b6e8da0bb82f968de8de311dc` | Exact copies of the report-download implementation, four client tests and both browser-helper changes |

Only six source/test files are transplanted. Each equals its cited owner's Git
blob. Original PRs and their documentation remain available and unchanged; this
is selective integration, not an assertion that all donor branches were merged.
The existing database, migration, patient, source, question, session, report and
rights owners are retained. No dependency, model, content source, asset or service
is adopted and no schema or permission is changed.

The current Notion precedence and accepted H1 decisions were read alongside the
repository instructions, plan, backlog and existing Google engineering record.
Historical PRs #56/#70/#74/#76/#85/#89/#93/#131 were checked and remain open,
unmerged drafts; their descriptions are not proof of integrated behavior.
This is a bounded integration audit, not a complete platform, history or privacy
audit. The long-term first-party clinical platform remains in scope.

### Reproduced gaps and local verification

Before copying production changes, the unchanged donor tests ran on the reading
baseline. Citation contracts produced 20 failing assertions across the two added
methods: malformed historical timestamps were accepted. The two positive report
download tests failed because the cover was absent; denial and patient-switch
negative controls already passed. These are observed behavioral failures, not
import errors or cancelled jobs.

After restoring the original owners' production changes:

- All **278 compiled client tests passed**, zero failures/skips, using the pinned
  TypeScript compiler and actual React component builds. `npm run build` passed.
- All **12 citation contract tests passed**, including exact valid timestamp
  preservation and rejection during full response preparation.
- Local API discovery ran **416 methods: 96 passed, 320 skipped** because a
  disposable PostgreSQL instance was unavailable. This is not full API acceptance.
  Local server setup failed because this runtime cannot change Unix user/groups;
  the existing hosted PG16 workflow remains the full acceptance environment.
- The frontend dependency gate passed with 18 installed and two optional
  uninspected packages. Its scope remains local synthetic development.
- A separate read-only review passed the static patient-data boundary scan, nine
  boundary regressions and ten dependency-gate negative controls. It identified
  no blocking boundary defect. The web-only workflow does not directly invoke
  that scanner; the API workflow does. Static scans do not prove runtime egress.
- The shared wheel cache contained an unrelated extra PDF wheel, which correctly
  failed the exact-set gate. No package was deleted and no policy was relaxed.
  A fresh directory containing only the 24 inventory-named artifacts then passed
  the unchanged exact-wheel/hash/notice gate (99 supplier-native and 13 embedded
  entries remain separately scoped declarations).
- A second code review confirmed all six donor blobs and found no material
  integration defect in fresh-read checks, preserved report bytes or browser
  helper ordering. Its focused download suite passed 4/4. This is an automated
  reviewer, not independent human, legal or clinical acceptance.

### Combined acceptance and continuation

Run the existing H1 API and H1 web workflows at the exact published candidate.
Required evidence is actual PostgreSQL/HTTP/browser execution, source reading and
native keyboard question handoff, current and historical report downloads,
separate whole-file/body hashes, original-byte preservation, fresh receipt/status,
rights denial, case isolation, restart and backup/restore. Donor workflow success
is not substituted for candidate evidence. The PR records the actual run URLs
and outcomes; an in-progress job is not a pass.

The download cover describes status returned by the fresh read, while the
preserved body and original preparation remain byte-identical. Earlier downloads
cannot be recalled. Strict citation timestamps prevent misleading history but do
not independently authenticate a publisher, actor or event.

No new patient-journey study, technology clearance, external biomedical retrieval
or scientific AI evaluation was performed. Those existing research registers
remain authoritative within their recorded scopes. The next milestone is owner
review of one combined candidate and its full dependency chain, followed by a
rights-qualified live-evidence connection through the existing question owner.
Production accounts/consent, professional review, source licensing, clinical
qualification and real-patient release remain separate unresolved gates.
No merge, deployment or clinical validation is authorized or claimed.

## Source-bound images in the same investigation — draft #327

**Verified source:** `9cdce3071f69f3d4c55556ff1c53d9f788d9b053`, tree
`771ee99a5f36afc4a2ae18eaa94b0974161ab36f`. Both complete hosted workflows
passed on this exact checkout: 297 client tests, 533 API/PostgreSQL methods,
287 reference methods, connected browser acceptance and all six recovery probes.
The subsequent delivery change updates documentation only; it does not change
the verified application, tests, migrations, dependency gates or workflows.
These results qualify the bounded synthetic engineering contribution. The
preceding sections retain their original dated scopes.

The patient-facing job is to inspect an original image from its current imaging
report, ask a question against that exact report, and keep the question's evidence,
preserved report and follow-up work together. The existing pathology scenario
remains unchanged. Images are attached to a separate independently fictional
imaging report with the source owner's qualified subject, issuer and study date.

### Exact owners and decisions

| Owner | Pinned input | Preserved responsibility |
| --- | --- | --- |
| #319, including #318/#314/#307 | `2475d924fddef6792076bdf9039fad5be7312b7a` | Existing source reading, exact-quotation question handoff, import disclosure and evidence/task application |
| #313 | `f6132e894a21a326f72660c3399499ccbf251831` | Original-image custody, bounded parser, three independent image grants, image/question/task/citation migration histories and recovery |
| #322, including #315/#316 | `19b75317701ae01fc93844077ac94c351fd982bd` | Strict citation-history timestamps and fresh report-download status around the unchanged historical report body |
| #316 documentation/ancestry | `66f44d42b8d47a1b6e8da0bb82f968de8de311dc` | Preserved #307 final receipts and exact original-body versus whole-download distinction |

All owners remain draft and unmerged. No donor PR is closed or rewritten. The
implementation adds no second patient, source, question or evidence ledger.
#312/#320 archive transport, #321 external bibliography, #323 reviewed document
intake, #324 verification-reason preservation and #325 metadata qualification are
separate owner work; their existence is not an integration claim here.

The new DDL-free `0012_image_report_convergence` joins the unchanged
`0011_evidence_convergence` and `0011_image_evidence_merge`. Preserve every
published revision, and require this new single head in current readiness.
Historical migration tests target their original joining node when testing its
DDL-free behavior. Current populated-parent upgrade tests additionally verify
rows, sequence state, schema definitions and authenticated HTTP after upgrade.
#304/#307's fully encoded source-original response remains inside the original
owner's final authorization/receipt transaction while adopting the image owner's
shared original validation helper.

### Bounded capability contract

This extends existing version-1 domain APIs and the existing `RegistrySession`;
no MCP or agent framework is added. The `/v1` manifest retains the image owner's
`synthetic_image_list` and `synthetic_image_original_read` capabilities.

| Contract aspect | Boundary |
| --- | --- |
| Canonical inputs | Current patient, case, imaging source and selected image IDs; source version/hash/date remain visible in Records |
| Outputs | Existing typed `SourceImageIndex`, image identity/digest/size and committed access receipt; original route returns bounded `application/dicom` bytes with a fresh receipt |
| Actors and purpose | Existing exact-patient, organization, active-binding and purpose checks; `image_read` and `image_original_read` are independent grants |
| Effects | Audited read and explicit local download; no clinical write, interpretation, pixel viewing, image import UI, model call or external outreach |
| Integrity | Source/date/ID validation; exact byte count and SHA-256 before a browser Blob; no untrusted filename or error payload presented as a successful original |
| Context lifecycle | Patient/case/source changes and dismissal discard late results; fresh denial cannot reuse a cached original; image denial does not grant or erase independently permitted report content |
| Retry/recovery | A fresh read requires current authority and creates its own read receipt; there is no exactly-once-delivery claim; image custody and linked work must survive actual restart and restore |
| Limits | Existing uncompressed single-frame CT profile, 2 MiB per object, 256 originals/64 MiB per case; independently fictional inputs only |
| Review boundary | Byte integrity and a fixture source mapping are not source authenticity, clinical image interpretation, professional review or clinical authorization |
| Replacement | Existing image/source API and canonical IDs own semantics; the browser and parser remain replaceable consumers |

Patient, evidence, report and image access remain separate. Source amendment
stales dependent work and closes the old current-image path. Explicit image
relinking neither reopens the old source nor endorses a replacement question or
report. Report downloads retain #316's fresh status cover while the original
prepared body stays byte-identical; already downloaded files cannot be recalled.

### Rights and research scope

Only one runtime artifact is added relative to #319: the already-qualified
code-only `pydicom-3.0.2-1oi1-py3-none-any.whl` from #313. Exact hash:
`cbd2edf9051da7cce3f53184cc16dde1238b065845acfa0ceb241d0e8f06acc4`.
The pinned [upstream license](https://github.com/pydicom/pydicom/blob/20aa4b73aef76bffb6fbc46a8827588dfa9bb89d/LICENSE)
requires **MIT AND BSD-3-Clause**, including the retained GDCM private dictionary;
the [3.0.2 release provenance](https://pypi.org/project/pydicom/3.0.2/) identifies
the reviewed preparation input. Keep all notices, the exact one-line documented
modification, source hash, derivation manifest and offline verification gate.
Ordinary unqualified `pip install pydicom` is not this approved artifact path.

Local preparation reproduced the derived hash, 84 retained files and 206 excluded
sample/nonruntime entries. The exact 25-wheel gate passed, retaining the existing
24 package records, 99 supplier-native entries and 13 embedded-runtime entries.
No optional extras, pixel codecs, sample datasets, hosted service or model is
adopted. Frontend manifest/lock and Compose files remain unchanged. Approval is
only `local-synthetic-h1-development`; inherited distribution, native/OS/container,
model, clinical-content and deployment questions remain separately scoped.

No new patient-journey dataset or clinical evidence was collected. The existing
workflow research supports source traceability, second-time-point review and
coordinated follow-up as product requirements; this integration does not measure
clinical benefit or generalize an individual person's treatment. The current
workflow patient-data entrypoint audit passes within its stated static scope.

### Observed tests-first evidence

Checkpoint `96ea369df0a560c8a325d33d66ef5b6b4a4865ef`, tree
`17c1d6251ff1f3a0be50d6056b1cb0495868523b`, adds only five test/fixture files.
The root reproduced four intended missing image-route/migration assertions in
two pure API methods. No import/setup error is counted as behavior.
[Hosted React run 41666345453](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666345453)
compiled and ran **291 tests: all 274 inherited tests passed, 17 new image
behavior/render checks failed, zero skips**. These failures preserve the actual
missing source-reader behavior.
[Hosted API/PostgreSQL run 41666345934](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666345934)
checked the same source and ran **421 methods in 440.531 seconds**: all 414
inherited methods passed; the seven new methods produced nine intended missing
image-route/joining-migration failure assertions, with zero errors or skips.
Later recovery steps did not run after this expected failure. These negative
tests are retained separately from the later combined qualification.

### First combined run and corrected verification assumptions

Runtime `d149f56e93ab1f0186b820da4fa72e6da2268fa1`, tree
`ed8daac9c0140f222f2aac00bdf4fc7728df71f1`, preserves the exact donor commit
ancestry. [API run 41670316303](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41670316303)
passed **533 API/PostgreSQL methods in 554.519 seconds** and **287 reference
tests in 12.853 seconds**, with no skips. Inherited browser journeys and actual
registry/source restart/restore passed. The new image recovery helper then
incorrectly expected one origin row for every authored command; subsequent
recovery steps were skipped. The preserved origin owner intentionally records
origins for assessments and reports, not imports.

[Web run 41670316231](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41670316231)
passed **297 client tests**, build and inherited browser paths. Its new scenario
completed downloads, independent denials and authored-report amendment/restart,
then a whole-card substring selector mistook the current source's Supersedes
reference for the original source-ID field. Explicit relinking and final
isolation had not run; this failed run is not full browser acceptance.

Two helper-only corrections preserve application/runtime, migration, rights,
dependency and workflow bytes. `d9be3f137d5a56cd688f6f6711e1ebddb8203a59` matches
the exact original-ID field, asserts both current/superseded row identities and
retains the old-source no-image-control assertion. `9cdce307` replaces the false
origin count with exact command/result and assessment/report origin sets,
including object/question, request key, authority, intent and report packet/
renderer binding. Two valid checkpoints and 12 corruption controls passed.
Complete row/sequence comparisons and all original recovery assertions remain.

Independent review also reproduced timeout during image hashing: an aborted
request could otherwise complete a download. Two failing regressions preceded
the cancellation correction. Explicit post-read/decode/digest guards and a
visible terminal timeout state now pass. Review separately verified image/report
denial isolation, exact request-size limits and all 18 distinct published
migration files. This is engineering review, not clinical or whole-product
legal clearance.

### Completed browser and retained artifact verification

[Corrected web run 41673061732](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41673061732)
completed **SUCCESS** on `9cdce3071f69f3d4c55556ff1c53d9f788d9b053`:
**297 client tests, zero failures/skips**, TypeScript/Vite build, dependency gates
and actual React/FastAPI/PostgreSQL/Chromium acceptance. All inherited journeys
remain. The new same-question image scenario now completes explicit amendment
relinking and final access/session isolation.

[Artifact 13249556104](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41673061732/artifacts/13249556104)
was downloaded and checked against its uploaded SHA-256
`05e4222e5c571f89523996700da0a6934a2177e8af084e585a0fe907648491cf`.
All **447 source blobs** match the tested commit; desktop and 390-pixel browser
captures were inspected. Hosted artifact retention ends **10 November 2026**.
The scenario and reproducible assertions remain in the repository.

The retained `image-evidence-continuity.json` links one canonical source/question,
metadata citation, task and authored report. Four **578-byte** original downloads
are byte-identical, have four distinct access receipts, and retain image SHA-256
`a2361e5fc9c65371a890e4f450a61689f44da020cbc93d850ed11ce881f4e6b9`.
The fourth follows an explicit link of the same image ID to the amended source;
the original question/task retain their historical source and reassessment state.
Three retained report downloads match their file/body digests and fresh status
covers. The first and historical exports preserve exactly the same body.

The historical report cover follows a **separate authored-evidence amendment**.
The later imaging-source amendment occurs after that helper has withdrawn the
evidence content; no newly readable report from withdrawn evidence is claimed.
API image import is explicitly operator fixture setup. These checks establish
neither browser image upload nor pixel interpretation, model execution, clinical
approval, live biomedical retrieval or production accounts/consent.

### Completed API and actual recovery verification

[Corrected API run 41673062382](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41673062382)
completed **SUCCESS** on the same exact `9cdce307` checkout. The completed job
log records **533 API/PostgreSQL methods in 508.396 seconds**, **287 inherited
reference methods in 12.443 seconds**, both `OK` with no skips, and all inherited
loopback browser paths. The job also passed the current data-boundary checks,
exact reviewed-wheel/offline-install gates, populated migrations, resolved
container identities and package inventory.

All six separate Compose probes passed against actual PostgreSQL 16, API
processes and recovered databases:

| Recovery probe | Observed result |
| --- | --- |
| Registry | Scoped HTTP, tenant denial, API/database restart, dump/restore and revoked-binding denial |
| Sources | Exact original bytes, amendments, current authority, receipts and originals served from the restored database |
| Images and the same investigation | Current/historical source and question, original image bytes, citation, task, frozen authored report and same-key retry identities reopened through the restored API; metadata redacted after rights revocation |
| Review returns | Same-key recovery, amendment history, independent grants, restart/restore and access revocation |
| Follow-through | Existing task lifecycle and acknowledgment, exact retries, three tasks/nine events, metadata/citation recovery and append-only rights withdrawal |
| Authored evidence | Complete logical-row/sequence recovery; readable, restricted and withdrawn report/original states; exact retries, independent grants and revoked restored binding |

The joined image probe retained complete logical-row hashes and sequence state,
source amendment and explicit image relinking. It exercised the recovered copy
through HTTP while verifying that the original database remained unchanged. The
separate authored-evidence probe independently verified the same-question
citation/report/task relationship after restore; it is not substituted for the
joined image probe.

[API artifact 13249897783](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41673062382/artifacts/13249897783)
was downloaded and its ZIP SHA-256 verified:
`24ca3bfadc17c3b4b1b34fd22729eae503a9d28be75446710ff7eef3238afc1a`.
Its `oi.h1-evidence-recovery-acceptance/3` receipt records the actual object IDs,
report body/snapshot hashes, complete row counts and the
`0012_image_report_convergence` schema. It confirms restored readable/withheld
HTTP, exact retry identity, independent export denial, revoked-binding denial
and an unchanged original database. `model_executed` and `clinical_approval`
remain false. Hosted artifact retention ends **10 November 2026**; the source
probes and full run log retain the reproducible acceptance record.

The suite counts above describe separate engineering executions, not unique
patients, independent clinical reference cases or clinical validation. Local
execution did not establish PostgreSQL acceptance; the hosted completed jobs
provide that evidence. No passing result from an earlier or donor head is used
as the combined candidate's result.

### Acceptance scope and release boundary

The connected Records journey and all inherited source/question/evidence/report/
review/task paths now pass at the named source. Actual original downloads,
independent grants, current/historical report covers, source amendment with
deliberate relinking, late-response suppression, exact retries, restart and
complete logical history/sequence recovery were exercised. API fixture image
import is labeled setup and is not browser image-import functionality.

Publication remains **draft, unmerged and undeployed**. Complete scientific
investigation, qualified live biomedical retrieval, actual model execution,
professional signoff, production identity/delegation/consent, general medical
document and annotation parity, broad image support and real-patient release
remain incomplete. The next integration decision should inspect the existing
reviewed-document, bibliography/rights and review-reason owners rather than
creating another source, evidence or review implementation. No donor work is
merged or closed by this contribution.


## Archive originals with authored reports — continuation

This bounded continuation starts from #327 delivery commit
`50c68a331ccc25034ef53b1b78bec868921d0b17`, whose six documentation updates retain
the verified runtime `9cdce3071f69f3d4c55556ff1c53d9f788d9b053` and its complete
acceptance record above. The archive/report contribution below requires its own
combined verification; no parent result is substituted for that execution.

### Bounded next contribution

Connect archived originals to that same image/question/citation/task/comparison/
report workflow. The product experience and canonical owners already exist;
this continuation must extend their retrieval and recovery behavior without
creating another patient, source, question, evidence, report or event ledger.

| Input | Exact revision | Contribution retained |
| --- | --- | --- |
| #327 | `9cdce3071f69f3d4c55556ff1c53d9f788d9b053` | Verified image-inspection UI, authored reports, source reading and all six recovery gates |
| #331 | `55ea8f96868125ee802d840e779a76f1b8c8e3b3` | Verified archive disclosure, independent grants, no-fallback failures and restored archive/question/task/citation history |
| #332 | `f7136bbc5ef7c7224bf5ed7172c82ddab83dc49d` | Additional exact citation/search audit accounting and context assertions for selective reuse |

#331's source-original response correction from #304 is already present in
#327. Preserve its complete JSON preparation and shared `_validated_original`
unchanged; only the existing original-image route receives the trusted archive
reader. Keep #311's strict citation contract, #316's fresh download cover and all
19 current migration revision files (the 18 parent revisions and #327's join).
The existing DDL-free
`0012_image_report_convergence` remains the only current head. No new migration,
dependency, model, permission, public API field or frontend change is required.

### Combined acceptance contract

- Use only stored canonical identifiers after source/custody/authority preflight.
  Release owner locks during archive I/O, then validate current binding, source
  and exact bytes in a fresh transaction before response preparation, final
  authorization and receipt commit. Never fall back to intact local bytes when
  the configured archive fails. Image-index reads must not fetch originals.
- On the same v1/v2 imaging questions, preserve citations, verification returns,
  task events, authored comparisons, report body/hash, preparation time, source
  snapshot and exact-command origins. Deliberate image relinking cannot make an
  old report current or replace its immutable body. Existing retry authority and
  rights rules continue to govern the original request and receipt.
- Keep image metadata, image originals, authored-content reads, report export and
  citation metadata independently governed. Content withdrawal withholds the
  affected report/original content without silently revoking independently
  permitted images or metadata. Revoked patient binding denies the scoped reads
  and retries before any archive invocation or new receipt.
- Preserve #327's complete row digests, schema/catalog state and sequences.
  Read-only cycle comparisons may exclude exactly `ACCESS_SNAPSHOT_KEYS`:
  `events`, `rows:identity.identity_domain_events`, and
  `sequence:identity.identity_domain_events_id_seq`. Preserve every business row
  and sequence plus the complete prior event prefix; account for each appended
  read event and reject business writes.
- Adapt #332's per-question citation counts, exact patient/case/actor metadata,
  query digest, zero-result count and empty-result-manifest checks to the actual
  combined read schedule. Added authored-report reads need their own exact
  scoped accounting; do not copy numerical expectations from a shorter scenario.
- Retain all six actual HTTP/restart/dump/restore gates. Extend the current image
  helper in place with the bounded read-only file fixture, report reads/retries,
  independent denials and withholding through archive failures and service
  restarts. New access receipts belong only to the actively restored database;
  the source and required intermediate snapshots remain unchanged.

### Verification and limits

This archive/report candidate's implementation and exact-head acceptance are
in progress. The parent results above and #331's 487 API/282 reference/219 web
passes are separate evidence; neither proves the new combined candidate.
Record actual local checks, hosted API/browser results, all six recovery gates
and any failed attempts in the continuation PR and existing canonical records.

The first local contract check generated OpenAPI from the immutable #327 parent
and compared it with both default and archive-injected applications. All three
are equal: **32 paths and 82 schemas**. All **21 migration-directory files** are
byte-identical to that parent. The source-original, authored-evidence and strict
citation owners, frontend, workflow and dependency declarations remain unchanged.
These are contract/preservation checks, not PostgreSQL or recovery execution.
The local focused run passed **37 tests with zero failures/errors/skips**:
five image-ordering, 12 citation-contract, 16 authored-evidence-contract and four
convergence-contract checks. The 14 retained archive methods and three extended
archive/report methods are collected, but their PostgreSQL behavior is not yet
claimed from local execution. Actual withdrawal is distinct from grant removal:
the new scenarios require original-content denial, a `content_withheld` report
with preserved identifiers/hash/preparation time, permitted independent image
reads and original command-receipt recovery.
Full API discovery collects **550 executions and 503 distinct test IDs**. The 47
repeated historical source-version/source-question IDs come from unchanged
imported suites; all 17 added archive methods appear exactly once. Collection is
not a database pass, and these counts are not independent clinical examples.

The file fixture is absent from the normal API image, has no environment-based
activation and does not qualify live PACS, network transport or external archive
backup. Preserve #248 HOLD. All records, images and evidence are independently
authored fiction. The reports contain human-authored comparisons, not model
execution, scientific appraisal or clinical approval. Draft integration does not
establish deployment, production identity/consent or real-patient readiness.
