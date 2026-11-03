# H1 question evidence and patient follow-through convergence

Latest preparation record: [main reconciliation and chronology corrections](#main-reconciliation-and-chronology-corrections--3-november-2026). Earlier receipts below retain their original pinned scope.

**Status:** original convergence in draft #307; subsequent combined acceptance
is recorded below. All contributions remain subject to explicit review.
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

## Connected follow-up attention — 3 November 2026

The next bounded continuation restores the existing follow-up attention feature
from #299 into the source-reading/evidence/report candidate #322. The latter's
combined application still showed only an undifferentiated task list. This is
reuse of the original presentation owner, not a second work ledger or urgency
model. Existing OI-007/009/010/013 remain the acceptance items.

### Design and execution plan

- Base: #322 `19b75317701ae01fc93844077ac94c351fd982bd`, tree
  `9f120084d641ad340a0ee3d85b755480d990e45b`. The isolated local checkout
  reconstructed this exact tree from #318 plus the seven-file #322 patch.
- Donor: #299 `b47cc6ddde922bb53aa399b7d05adaee2d07620c`.
  Preserve its two production files, 21 unit tests and browser journey byte for
  byte. Its existing design remains the behavior contract.
- Reuse All work, Source changed, Revisit date passed, Unassigned and Completed /
  deferred filters. Counts overlap and use the server's dated snapshot. Preserve
  exact task identities/order/history and unsaved transition text while filtering.
- Withhold tasks/counts on absent, loading, denied or contradictory scope; a
  known empty authorized result is distinct from unavailable work. A new receipt
  resets to All work. Filtering itself performs no reads or writes.
- Add one real composed React/session regression for simultaneous authored
  evidence and follow-up attention, including independent task-read denial.
- Run compiled client tests, production build, dependency gate and the existing
  hosted PostgreSQL/FastAPI/Chromium journey at the published head. Preserve all
  source-reading, report-download, amendment, recovery and permission assertions.
  Obtain a separate read-only code review before declaring completion.

### Observed local checkpoint

Tests first: all 278 inherited client checks passed and all 21 unchanged donor
attention tests failed on the #322 tree because the projection was absent. The
new composed-screen test separately failed at the missing attention controls,
after successfully loading and rendering the existing evidence packet.
After applying the donor implementation, all **300 compiled client tests passed**
with zero failures, cancellations or skips. The four donor code/test/browser
blobs exactly match their published #299 object hashes. Build, hosted combined
acceptance and independent review are recorded in the continuation PR as they
complete; they are not inferred from either parent's prior green workflow.

No backend, migrations, session/authentication code, dependency, CSS or workflow
changes. Source owners and main remain unchanged; only a draft child is prepared.
Next: converge owner-reviewed candidates and exercise the same connected workflow
with reviewed document intake and the separately governed DOI connector. These
are separate pending branches, not capabilities delivered by this increment.

## Client chronology continuation — 3 November 2026

The report/follow-through work in the interrupted handoff had already shipped as
draft #174. This continuation uses the later connected source-reading/report
candidate #322 at `19b75317701ae01fc93844077ac94c351fd982bd`, preserving its source,
question, evidence, report and task owners. It addresses OI-008/009/010: dates in
evidence history and preserved reports must represent actual calendar instants.

The client accepted February 30, hour 24 and year zero in evidence/report history
because JavaScript date parsing normalizes some impossible values. Citation
history also accepted precision forms excluded by its existing API. One shared
calendar/clock validator now enforces each existing evidence contract without
normalizing the input: authored timestamps retain minute precision and longer
fractions; citation timestamps require seconds and at most six fractional digits.
Nested question timestamps and date-only source/evidence fields receive the same
calendar checks at the authored-evidence boundary. Other source consumers are not
changed or claimed to be comprehensively audited.

Preserved report bodies, original offsets, fractional strings, hashes, status
covers, independent permissions and fresh download authorization remain intact.
Invalid refreshed history clears a previously opened report and prevents export;
an explicit valid refresh restores access to the unchanged body. No backend,
database, migration, dependency, workflow or clinical state changes.

Verification sequence:

- Original #322 client baseline: 278 tests passed, no skips.
- Tests-only baseline reproduction: 12 targeted tests, 7 expected failures and
  5 passing controls. All failures were assertion failures in the actual client,
  not setup errors. These include the blocked-download regression.
- Automated read-only review found two further nested-date gaps. Both added
  regressions failed on the first correction before being fixed. Review is
  engineering feedback, not independent clinical validation.
- Final local implementation `74088fef9c7efb7d9a83cfe4be38634da70fc6ca`:
  all 288 client tests passed with no skips, TypeScript/Vite production build
  passed, and the existing dependency gate reported no errors (18 installed,
  two optional artifacts uninspected). The lock and dependency selection did
  not change. The following documentation-only commit does not alter runtime.
- Hosted browser results belong to the continuation PR's exact published head.
  Earlier passing runs are not substituted for final combined acceptance.

The candidate remains draft, unmerged and undeployed. It uses only independently
authored fictional test records; real-patient operation and clinical qualification
remain outside this correction.

## Verified #322 / #328 integration review — 3 November 2026

This checkpoint records live GitHub reads, immutable source review and retained
artifact verification. It supersedes the earlier pending-run wording for these
exact heads; it does not approve the wider parent chain or a future merge.

### Exact dependency and ownership

- #322 head: `19b75317701ae01fc93844077ac94c351fd982bd`; sole parent
  #318 `0db90a45ec256d380c01d503162e31ac8ee419b5`.
- #328 head: `5a188d4e18e4d80bc2ba1d662c966abc3096301f`; sole parent
  is the #322 head above. Its tree is
  `269ce69e54fa1338dbfa87ae6e043b36f11d6ba6`.
- #299 is a selectively reused donor, not an ancestor. All four intended
  production/test/browser blobs match donor
  `b47cc6ddde922bb53aa399b7d05adaee2d07620c` exactly.
- The two changes together touch 12 paths relative to #318. The 397 files
  unchanged by #328 retain their #322 Git blob IDs and modes. The #328 document appends
  to the complete #322 document without replacing its existing content.

### Directly checked hosted evidence

| Exact head | Run | Observed coverage |
| --- | --- | --- |
| #322 `19b7531` | [41664891696](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664891696) | 278 client tests; build; actual PostgreSQL/FastAPI/React browser journey |
| #322 `19b7531` | [41664891742](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664891742) | 416 API tests without skips; 287 prototype tests; HTTP, restart and backup/restore acceptance |
| #328 `5a188d4` | [41666427184](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666427184) | 300 client tests without skips; build; complete connected browser journey, including follow-through attention |

All three runs completed successfully on attempt 1. Checkout logs identify the
exact PR heads above, rather than GitHub's synthetic merge commits.
Artifact `13246611987` has SHA-256
`a954037043d7fbf8321e2641530d30d9ce6cd9d27ea93660392dbbee984f825f`.
Its commit record and all 403 source files match the #328 tree; executable
file modes were also checked. This audit did not repeat the full test suites.

The separate full API workflow did not run on #328. Its path filters exclude
#328's frontend/documentation-only delta. Parent backend acceptance is retained
as parent evidence, not relabelled as a child run. The current #328 merge-preview
commit has the same tree as its head, but was not the checkout used in the run.

### Review and remaining gates

Separate automated reviews found no material defect in the bounded evidence
contract/export or follow-through changes. Canonical patient, source, question,
evidence, report, task and authorization owners are retained. These reviews are
not submitted GitHub approvals or human, legal or clinical acceptance.

Both PRs remain open drafts with no submitted review. #322 targets the #318
branch; #328 targets the #322 branch. Neither targets main. Relative to main
`24519839aa8ac1ea3aff88a956349ba72798a72a`, #328 is 168 commits ahead,
zero behind, with 262 changed paths. A review of this two-commit delta does not
approve that full inherited change set.

Before merge: identify the destination and parent-chain review scope; obtain
the appropriate human owner acceptance; run both existing H1 workflows on the
actual approved candidate; record its commit, tree, checkout identities and
results. A later documentation or code commit is a new candidate. Do not merge
the child into an obsolete parent branch without an explicit retargeting plan.

No source change, merge, deployment, branch-protection change, real-patient
use or clinical approval is authorized by this evidence record.

## Main reconciliation and chronology corrections — 3 November 2026

This is a locally prepared continuation of the verified #365 candidate. The
proposed destination is a new draft integration PR against main, with #322 then
#328 retained in Git ancestry. It is not approval to merge either original PR,
change its base or history, close an owner PR, or deploy. Published #365 remains
unchanged at `b71b5390b4d587bbad77d57c8edf9f80c070f2b8`.

### Frozen inputs and selective reuse

| Input | Pinned identity | Treatment |
| --- | --- | --- |
| Verified #365 | `b71b5390b4d587bbad77d57c8edf9f80c070f2b8` | Preserve the combined #322/#328 implementation and its audit record |
| Accepted main | `824ed8c415068bd31c67929cb9f79e79b2df0892` | Retain all 13 commits beyond the previous `24519839` baseline; all 44 changed paths have no overlap with the original H1 delta |
| #360 | `f200dd107871d89703267ee0d1a14b2d1ca64d36` | Reuse #330 chronology and #339 dependency-identity corrections; preserve the shared document histories |
| #367 workflow | Git blob `0052ad3c134b55f681838b617db6df94835aa70f` | Reuse this exact H1 web workflow only; include shared source/reference paths and the existing synthetic-data audit |
| #369 follow-through | `3c028ddfb4b408571b36140a5e5b52115c7bd790` | Reuse its exact validator, client-test and browser-helper files; these three files' donor bases equal the #365 files |
| #307 final documentation | `c35219dc5eb244874a7df6e9bf00cfbfda18251f` | Reconcile its four final evidence documents with the later continuity additions |
| #193 omitted regression | Test blob `e400814e082efafb7e3e8b7581feda9caea60baa` | Restore the exact owner test file; no production API change |

#360's artifact `13254432621` was downloaded and independently hashed:
`ccd34323ba053accdf159ea2a8c80c348f4450a425bf08525c2456367aa95f06`.
Its commit record and all 407 source blobs match the donor tree; executable
modes were retained. The #367 workflow matches its exact published blob.
No new package, H1 schema, canonical ledger, grant or model is introduced.

The 13 accepted main commits retain their existing prototype owners, including
the already accepted fictional actor-grant and subject-binding work. This
reconciliation does not design a replacement H1 permission system or turn
synthetic actor fixtures into production identity.

### Findings resolved in the proposal

The evidence clients' permissive JavaScript date parsing accepted impossible
calendar values; #330's existing strict validator, carried by #360, addresses
that gap. The same issue remained in follow-through history. Running #369's
unchanged tests before its production fix produced 16 failures and 26 passing
controls. The failed cases included February 30, non-leap February 29, year zero,
hour 24, missing seconds and excess fractional precision in task creation or
history timestamps. The exact donor correction rejects these responses, removes
actionable history/counts, and requires a fresh valid read.

The original installed-package gate did not require package identity and declared
license to match the lock, and followed filesystem links. #339's existing
correction adds those checks and 13 filesystem regression controls. The
inventory still records two absent optional packages as uninspected and does
not claim commercial-release or native-linkage clearance.

The original H1 web PR filter omitted shared `src/**`, reference `tests/**`
and the existing boundary audit. The exact #367 workflow covers those paths and
executes the boundary audit before acquiring packages. A newly named branch
requires an opened or synchronized matching PR; its push trigger alone is not a
validation mechanism.

Ancestry review identified two historical differences. #314 consumes #307's
verified runtime `477f24826a8a102c7437c993d69877c1f250b951`, but not its later
four-document receipt. #200 diverges from the final #193 head by two test
commits. The candidate retained the datetime instant comparisons but omitted
the 28-line amendment-before-first-receipt test. Its exact restored owner file
checks rejection of the superseded source, no durable receipt on rejection,
and successful receipt of the current source. The runtime guard was retained;
this finding establishes test-coverage loss, not a demonstrated production
regression.

### Executed local checks and remaining hosted evidence

- 327 compiled React client tests passed, with zero failures, skips or
  cancellations. TypeScript checking and the Vite production build passed.
- 13 dependency-gate controls passed. The real installed gate inspected 18
  locked packages, reported no errors, and left two absent optional packages
  explicitly uninspected.
- After the final accepted-main refresh, 406 reference Python/HTTP tests passed
  with no skips. The separately invoked reference Node suite passed 15 tests.
  These counts overlap in exercised behavior and are not summed.
- The existing static synthetic-data entrypoint audit passed. The restored
  PostgreSQL test and reused browser helper parse successfully; parsing is not
  execution of either acceptance path.
- The client/build/rights checks preceded the last main refresh. That refresh
  changed reference-source/test/UI files only; all web client, test, package,
  lock and dependency-gate inputs remain byte-identical to the tested inputs.
- One mistakenly unscoped `node --test` invocation ran from the repository root
  and failed web test setup because it did not use the web package's prescribed
  working directory. The corrected scoped reference Node command passed;
  the prescribed `npm test` web command independently passed all 327 tests.
- Source whitespace checking retains five trailing-blank-line warnings from
  unchanged donor/main files. No clean whitespace-check claim is made.

#365's successful web run
[41699683211](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41699683211)
and API run
[41699683626](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41699683626)
still apply to that immutable head: 300 client, 416 API and 287 reference tests,
plus real PostgreSQL/browser/recovery acceptance. They are not relabelled as
verification of this new proposal. Fresh exact-head H1 API/PostgreSQL,
React/Chromium, reference UI and restart/dump/restore evidence remains required,
including execution of the restored #193 regression and #369 browser controls.

### Review boundary and next gate

The automated CI/dependency review confirmed the two gate corrections within its
inspected scope. The inherited API revisit covered authentication, connection
ownership, case/source scope, source disclosure, canonical questions and part of
authored-evidence integrity; it did not finish every follow-through, migration,
historical-report or restored-authority path. No full-chain approval is inferred.

A source-based frontend review identified inherited P2 loss of unsent task
creation and transition inputs when navigation unmounts their component. The
existing #379 continuation owns this issue; its implementation and final
acceptance were not included in this minimum correction. No browser reproduction
of this finding was executed in this review. Resolve or explicitly accept that
bounded issue before final merge.

The 28 inspected original, parent and correction PRs had no submitted GitHub
reviews. The branch API reported main unprotected and the rulesets list was
empty, but the detailed branch-protection endpoint returned 403. This is not an
administrative certification or permission to change governance.

Before publication, recheck the pinned heads, present the exact proposed patch
and source tree, and obtain the repository-change approval required by the
integration review. After approval, create a new draft targeting main and run
the existing acceptance workflows on its frozen published head. Preserve the
original PRs and record any new main movement explicitly. Human owner acceptance,
whole-chain review, final merge authorization and clinical/production qualification
remain separate. All engineering inputs remain independently fictional.


### Post-publication main movement and refreshed candidate — 3 November 2026

After draft #390 was published at `427f5222320fc86d9da8093bcc952d3a0e3f3fcf`, `main` advanced by two accepted commits from `824ed8c415068bd31c67929cb9f79e79b2df0892` to `c2aa2054fa746fb26576150f27ec1f229b003f6f`.
The intervening commits are `f02d2427f9314c0d258425a809ee5e95f8857bf6` (clear the Patient Mission projection when grant authority is lost) and `c2aa2054fa746fb26576150f27ec1f229b003f6f` (QA-11/12/13/15/17 guards and their new regression file).

Six paths changed on main. Five overlap the integration proposal only because the proposal had retained the immediately prior accepted-main versions of those files; no H1-specific correction in those paths is displaced. The refreshed candidate therefore takes the direct successor main blobs for `src/open_intelligence/__main__.py`, `src/open_intelligence/store.py`, `tests/test_qa_adversarial_cycle3.py`, `web/app.js` and `web/mission.js`, and adds `tests/test_qa_regressions_qa11_12_13_15_17.py` unchanged from main.

The earlier exact-head #390 web/API success applies only to `427f5222`. This refreshed head requires a new exact-head hosted run before merge. No earlier run is relabelled as verification of the refreshed tree.


### Second post-publication main movement — 3 November 2026

After refreshed head `73f6eb838a966399173bc753833048d567b3ea3a` completed both H1 hosted gates successfully, `main` advanced once more from `c2aa2054fa746fb26576150f27ec1f229b003f6f` to `e7c6b02e06ff76d0276ffa11cf09215c0b6f65b0` via QA cycle-1 fixes #346.

The accepted commit changes `src/open_intelligence/changes.py`, `src/open_intelligence/discovery.py`, `src/open_intelligence/investigation.py`, `src/open_intelligence/store.py`, `web/app.js`, and adds `tests/test_qa_c1_remaining.py`. The overlapping integration files are direct accepted-main successors; no H1-specific chronology, workflow, evidence-report, follow-through, or dependency-gate change is displaced. The refreshed candidate takes those exact accepted blobs and must again pass exact-head H1 web and API/recovery workflows before merge. Earlier successful runs remain evidence for their own immutable heads only.
