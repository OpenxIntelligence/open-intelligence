# H1 question evidence and patient follow-through convergence

**Status:** original convergence in draft #307; subsequent combined acceptance
is recorded below. All contributions remain subject to explicit review.
**Scope:** independently authored fictional engineering inputs only.
**Product job:** keep one saved patient question, its citation discovery, separately
authored comparisons/reports and follow-up work in the same governed application.
This is an integration of existing owners, not a new patient or evidence ledger.

## Source ownership and current truth

The live audit on 3 November 2026 found `main` at
`24519839aa8ac1ea3aff88a956349ba72798a72a`. The owners below remained draft and
unmerged. Existing Notion/Drive progress stopped at #298, so their proposed next
passage/report implementation was already overtaken by #300. Accepted product,
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
- The final combined candidate remains to be verified below. Donor success is not
  substituted for a combined-head result. #303's first API attempt passed its
  database/reference suites but failed inherited Chrome startup; its unchanged
  rerun subsequently passed. That failure remains part of the donor record.

Independent client review reproduced protected uncertain-write payload retention
after common authority denial. Four case/source/question/binding-removal
regressions and two same-patient 403/404 regressions failed before the bounded
reset corrections. The transient 503 case still retains exact recovery intent
without authorizing a retry before renewed access. No unauthorized server write
was demonstrated. The corrected local Node runtime suite passes 258 non-render
tests; it uses Node's type stripping and is not a TypeScript/React build claim.
All 287 reference tests also pass locally. Full database/browser acceptance is
still the required combined gate.

## Acceptance and remaining boundary

The combined candidate must preserve one patient/source/question through metadata
search/link, an independently imported authored original, literal comparison,
immutable report, follow-through task, source amendment, historical reopening,
independent permission denial and exact retry. Upgrade paths, actual restart and
restored HTTP, current rights, case-switch clearing and both browser paths must
also pass. Existing tests must remain effective; changing assertions to suppress
a convergence defect is not acceptance.

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

## Record intake within the connected follow-up workspace — 3 November 2026

[Draft #335](https://github.com/OpenxIntelligence/open-intelligence/pull/335)
composes the existing record-import disclosure with the source-reading,
evidence-report and follow-up attention workspace. Existing records were still
preceded by the full import form in #328. The selected source history now leads;
the same deliberate import workflow remains available from a native disclosure.
This advances the existing OI-007/009/010/013 work, using the same canonical owners.

### Ownership and bounded behavior

- Base #328: `5a188d4e18e4d80bc2ba1d662c966abc3096301f`, tree
  `269ce69e54fa1338dbfa87ae6e043b36f11d6ba6`.
- Donor #319: `2475d924fddef6792076bdf9039fad5be7312b7a`, tree
  `b87461e4ff32bc2088678055e9c6fbf03f2fdf29`.
- All three production blobs and the complete intake browser helper are reused
  byte-for-byte from that donor. Only its two disclosure assertions are added to
  the newer reading helper; the parent's stronger terminal-denial wait remains.
- Empty source indexes start with import expanded. Populated indexes start
  collapsed. Native keyboard toggles preserve the selected File, exact preview
  and confirmation because the existing intake stays mounted.
- The patient/case key wraps the entire disclosure subtree. Existing source
  refresh, denied-access, case-switch and session-reset clearing is preserved.
- Only explicit form submission imports a source. No backend, migration,
  dependency, authority, session, evidence, report or follow-through owner changes.

### Evidence and limits

The tests-first [hosted run 41668978841](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41668978841)
at `9c7c27a1df2861eb7d5433327d8e64ff96d9c5f2` passed the client/build/dependency
steps and reached actual PostgreSQL/API/Chromium execution. It failed specifically
with `AssertionError: Loaded records start with the import form collapsed`,
demonstrating the missing behavior before implementation.

After composition, all **300 local client tests passed**, zero failures or skips;
the production build and existing dependency gate passed (18 installed, two
optional uninspected, no errors). A separate read-only code review found no
Critical, Important or Minor defect and independently verified the donor bytes,
scope-key behavior and preserved denial synchronization. This is automated
engineering review, not human or clinical acceptance.

The exact published-head workflow, final result, artifact identity and visual
inspection evidence are maintained in **#335's verification receipt**. They are
not inferred from donor success or from local client tests. The local executor
cannot start PostgreSQL under a nonroot Unix user; the existing hosted PG16
workflow is used unchanged. The parent's full backend/backup-restore verification
remains separately recorded on #322; this frontend-only change does not claim a
new full backend-suite run.

Required combined acceptance includes native disclosure and file retention,
existing task-attention controls, original-byte inspection, amendments and
quarantine, source-to-question entry, evidence/report downloads, independent
denial, exact retry recovery, API restart and case/session clearing. Browser
coverage is Chromium; it does not establish cross-browser or clinical validation.

The next integration boundary remains owner review of one combined candidate,
with separately verified review-draft, reviewed-document, imaging/archive and
live-evidence work reconciled through the existing contracts. These sibling
capabilities are not claimed by this increment. All inputs remain independently
fictional. The candidate is draft, unmerged and undeployed.

## Unfinished comparison in the connected workspace — 3 November 2026

[Draft #348](https://github.com/OpenxIntelligence/open-intelligence/pull/348)
brings #338's existing comparison draft into #335's combined source-reading,
record-intake, evidence-report and follow-up workspace. A writer can refresh
unchanged evidence or leave Investigations and resume the exact quote, relation,
applicability and rationale after a fresh matching access check. Editing does
not save an assessment. Existing OI-008/010/013 remain the acceptance owners.

### Source ownership and boundaries

- Base #335: `9d173843f924b40becba3a7dffd71717c12afb5d`, tree
  `57165fc8b1c6305336752eb948710a437eda9cf9`.
- Donor #338: `ac6d2be176ff4488aefde870a5f5286313a99210`. Its session
  implementation, all 30 draft tests, historical spec and historical plan are
  byte-identical. The new integration plan supersedes the donor plan's old
  publication checkpoint, without rewriting that provenance.
- Retain the current `AuthoredEvidencePanel` identity and CSS, the larger current
  registry session, and separate `authored_evidence_journey.py` and
  `question_metadata_journey.py` browser owners. The registry adds only the draft
  patch type import and four delegates. No duplicate ledger or authority owner.
- Draft identity binds patient, case, question, source snapshot, preflight,
  evidence version/hash and rights hash. Dirty input cannot silently retarget.
  Refresh/navigation conceal the draft until a fresh matching packet permits it;
  stale or denied context cannot submit. Patient/case/credential/reload reset it.
- Independent metadata or follow-through denial does not erase an independently
  authorized comparison. Common patient, binding, source or question denial
  clears the draft; a late earlier response cannot restore it.
- An uncertain save retains the exact original retry intent and locks edits and
  discard. A matching successful receipt clears the draft. This is in-memory
  input retention only, not durable autosave or clinical review.
- Backend, migrations, authorization contracts, workflow definitions,
  dependencies, current report-download code, source-reading and intake owners
  are unchanged. The separate #339 frontend rights correction, #330 strict-date
  correction, #324 review drafts, #323 reviewed document intake, #327/#332 imaging
  and archive convergence, and #321 DOI connector are not included by this PR.

### Tests and independent review

The tests-first commit `1611720ca8bb6e599d42f41edd87694fd66ba33e`
(tree `396438ecedd833604966c61e0a87401277952769`) compiled successfully and
produced 36 expected missing-behavior failures: the 30 unchanged donor tests and
six new composed-session cases. These were behavior failures, not missing imports
or setup failures. After adoption, all **336 compiled client tests passed** with
zero failures/skips; the TypeScript/Vite production build and current dependency
gate passed (18 installed packages, two optional uninspected, zero errors).

A separate read-only automated reviewer inspected the complete donor session and
integration diff, independently ran 64 focused tests, and found no important
runtime finding. Its P3 observation was accepted: the actual-browser POST count
now starts before selection/editing and is asserted both immediately after edits
and after refresh/navigation. A second review confirmed that change and the
correct metadata-helper path. This does not represent human or clinical review.

### Published execution evidence

Initial combined runtime `8d2ee0f4586db4dc5f7078d545262b3798c7b310`, tree
`8463bd26010783b78584ddf67b2505223f8e4ee6`, passed the complete existing
[hosted web workflow 41674964740](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41674964740):
336 client tests, production build, frontend and exact-wheel dependency gates,
and actual built React/FastAPI/PostgreSQL 16/Chromium journey. Artifact
`13249174330`, SHA-256
`2f73f3eaa1e2bca8a4b887f4e6cd0c929804471c71f7bd9024d6bf1c6975da4d`,
was downloaded and its digest verified. Every one of its 410 source files and
Git executable classifications matched the candidate tree. Local equivalent
commit was `b6cc6b69073a0bcf54bd67922b8edee4f7ffb983`.

The stronger browser assertion is published at
`297c9d4928105a77c9cf132a17b244409611c018`, tree
`b515b6379e373f92176cc23afa2f145438b4c0b7` (local equivalent
`af096a5347b01692822be8741c86f473e1d58b3e`). Attempt 1 of
[run 41675783452](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41675783452)
passed all 336 client tests and build but stopped before app navigation: the
Chromium debugging endpoint refused connections for 30 seconds. It never reached
the comparison assertions. Browser startup code was unchanged; browser stderr
was discarded by the inherited helper, so the underlying startup cause is not
established. The failed attempt remains recorded.

Attempt 2 on that **unchanged commit passed**, job `126057574593`: all 336 client
tests (zero failures/skips), production build, both dependency gates and the full
actual PostgreSQL/API/Chromium journey, including the stronger editing assertion.
Artifact `13250885948`, SHA-256
`267454af434fdb56f559859e87a25ba84d6c609119f006f0b5e8baa97b6eb3a2`,
was downloaded and its digest verified. All 410 source files and executable
classifications matched the strengthened candidate tree. The retry's three report
files/body hashes and distinct receipts were independently checked again, and
both draft captures were inspected. CI artifact retention ends 10 November 2026.
The PR carries the final documentation head and its automatic workflow result;
these documentation updates leave the verified application and browser code exact.

The artifacts' desktop draft status and 390px resume captures were
visually inspected; the browser asserts no horizontal overflow and no exposed
rationale before explicit fresh resume. Its receipt records exact input retention,
lost-response retry, real API restart, independent denial, amendment and
withdrawal. All three downloaded report files were independently checked against
whole-file/body hashes and distinct fresh access receipts; the earlier report's
body remains byte-identical when its cover changes to historical status.

This frontend-only increment does not claim another full standalone API or
backup/restore suite. The inherited full backend verification remains separately
recorded on #322. Browser evidence covers Chromium and independently authored
fictional records only. Draft, unmerged and undeployed; no model execution,
professional appraisal, production authorization or clinical validation.


## Connected chronology, draft and receipt recovery composition — 3 November 2026

Continues OI-008/009/010/013 from #355 `6f836b451c2e8426e5c3b2be194408424f95c69f` plus #359 `e2c888cf5b9065c8b6a60284666e6f35fe2c1e63`, including #348. Reuses eight exact donor application/test/browser files and historical design records. The new integration spec/plan is `docs/superpowers/plans/2026-11-03-evidence-safety-draft-recovery.md`. Both remote parent histories are to be preserved.

The composed client keeps an unfinished comparison across authorized refresh/navigation, rejects contradictory HTTP-status/duplicate receipt pairs while preserving exact recovery intent, and rejects impossible evidence chronology. Two additional tests show malformed refreshed chronology clears disclosed draft input without a write and cannot erase or replace an uncertain command; a coherent recovery does not authorize an invalid packet. Independent task/metadata grants and shared patient/source denial retain their existing tested semantics.

Observed local checks: baseline 310 client tests; tests-first 50 failures/322 passes; composed 372 client tests and 13 filesystem controls passed, zero failures/skips; 18 installed packages inspected, two optional uninspected, zero gate errors; TypeScript/Vite build and browser-helper compilation passed. Calendar-validation bypass makes both composition tests fail; restoring it makes both pass. Protected backend/migration/grant/lock/workflow and chronology/gate files remain byte-identical.

New exact-head hosted browser verification and independent review remain pending at this publication checkpoint; their results belong in the draft PR receipt. Ancestor runs are not combined acceptance. No standalone full API/backup-restore execution, production identity, real patient use, professional clinical review, model activation, merge or deployment is claimed.

## Truthful retained-comparison status continuation — 3 November 2026

A live reconciliation found #363 `ecadf0d45871e6581d65fa542390f2959ab26394`
already contains the #355/#359 convergence. This continuation starts from that
exact tree rather than opening another composition. All 419 blobs and modes
reproduce tree `f73caaca42a5fe1728e852764851a3564bbe065a`; its 163 production,
backend and workflow files match the independently reviewed original candidate.
The local reconstructed snapshot is not the upstream commit identity.

The independent review found no Critical or Important issue and one Minor copy
issue: a dirty comparison can coexist with an unrelated evidence import. If the
import response is lost, the global write phase is unknown, but the draft banner
previously said the comparison might already have been saved. The banner now
describes the pending evidence submission without assigning that submission to
the comparison. The adjacent exact-intent status still identifies the action and
question. Draft locking, disclosure checks, receipt verification and retry bytes
remain unchanged; no duplicate intent-matching logic was introduced.

The new rendered regression uses the real session and composed panel. It fails
on the unchanged #363 runtime with the inaccurate save claim, then passes with
the two-line copy correction. It also verifies that the retained draft stays
locked, retry preserves the exact import path/body, and an import receipt cannot
clear the comparison. Two complementary receipt/chronology regressions cover
both contradictory status/duplicate pairs, invalid assessment timestamps, cleared
report access, frozen recovery identity and valid refresh after receipt recovery.
Those two tests previously failed on unchanged #355 and pass on #363; #363's own
two draft/chronology composition tests remain intact.

Local acceptance: **375 compiled client tests**, **13 filesystem dependency-gate
tests**, zero failures/skips/cancellations; production TypeScript/Vite build
passes. The installed gate records 18 inspected artifacts, two optional artifacts
explicitly uninspected, and zero errors. The full change is limited to six paths.
All backend, migration, grants, package/lock, chronology, dependency-gate and
browser-journey code remains byte-identical to #363.

The patient-journey capability crosswalk is retained byte-for-byte from #360
`f200dd107871d89703267ee0d1a14b2d1ca64d36` at
`docs/research/PATIENT_JOURNEY_CAPABILITY_CROSSWALK_2026-11-03.md`. It remains
complementary research, not acceptance evidence for the whole program. Existing
OI-004/007/008/009/010/013 source owners remain authoritative.

Plan: `docs/superpowers/plans/2026-11-03-evidence-recovery-status.md`. Publish an
isolated draft targeting #363 and record the new head's actual hosted receipt in
its PR body. No new hosted success is claimed at this local checkpoint; the web
journey does not constitute a fresh standalone full API/backup-restore suite.
Independently authored fictional inputs only; no external notification, model
activation, real-patient processing, clinical approval, merge or deployment.

## Follow-up history timestamp validity — 3 November 2026

This bounded continuation extends OI-007/009/010 and the existing canonical
question/follow-through work (#295/#121). Its base is #364
`243d15fdaba112f93f7d3d258311d8b82e730015`. All 422 base source files were
recovered from the verified artifact and matched to their Git blob identities.
The existing patient-journey crosswalk and dependency-gate integration remain.

The task client used `Date.parse` as timestamp validation. It accepted nonexistent
calendar days, year zero, midnight rollover, minute-only timestamps and precision
outside the task API's seconds/up-to-six-fractional-digit PostgreSQL format.
A bad refreshed history therefore remained actionable. Sixteen independently
fault-injected real-session controls reproduced this (ready instead of error);
26 passing controls remained, including a valid timestamp preservation test.

The task decoder now reuses the existing strict PostgreSQL-shaped citation
validator. Both task creation and status-event timestamps must pass before the
list is exposed. Valid offsets, leap dates and microseconds remain verbatim.
Revision order is preserved; no clock-order assumption, timestamp rewriting,
new patient ledger, dependency, backend, schema or authority change is introduced.

Local validation: 72 task/attention/evidence-chronology controls and 13 filesystem
rights controls passed, with zero failures/skips. Python browser-helper syntax and
whitespace checks passed. Local TypeScript execution used Node's type stripping,
not a compiler/build claim. The existing hosted workflow must run full `npm test`,
TypeScript/Vite build, actual installed rights checks and PostgreSQL/API/Chromium
acceptance on the published head.

The browser regression corrupts only copies of actual authorized HTTP responses,
retains original/injected values separately, and requires task history, attention
counts and transition controls to disappear. Fresh valid reads must recover the
unchanged original tasks with no additional write or grant change. It does not
claim the genuine backend emits malformed timestamps. Exact hosted results belong
in the draft PR description after execution; they are pending at this checkpoint.

Independently authored fictional data only. No model activation, clinical
approval, real-patient processing, merge or deployment.

## Connected Review and follow-up chronology — 3 November 2026

This continuation extends OI-007/009/010/013 on the verified Review-draft owner
#368 `2d62b05357ad64524d561c2e05c903674cd4e54c`. Its source was recovered from
artifact `13265501154`; the downloaded SHA-256
`d0fa908782025a76312430cca3597ec691c2cb65ae83d2e9259ac04f74b174ed` matched,
and all 423 blobs and modes reproduced tree
`0544f4a2d58cf95fd48973adf4f68a475121f0b7`.

The composition retains #368's exact unsent Review-reason ownership and combines
#369 `3c028ddfb4b408571b36140a5e5b52115c7bd790` without overlapping application
edits. Its three task decoder/test/browser files are reused exactly. The H1 web
workflow is reused exactly from #367
`bbf56762e73f50fbe6432768deb605ed03edf09b`, blob
`0052ad3c134b55f681838b617db6df94835aa70f`: changes to shared source, reference
tests and the existing data-boundary audit now trigger web acceptance, and that
audit runs before package acquisition. It is a known-entrypoint source audit,
not an egress sandbox or general patient-data scanner.

The intended merge parents are #368, #369 and #360
`f200dd107871d89703267ee0d1a14b2d1ca64d36`, in that order. The third parent
preserves the original #330/#339 ancestry. Their runtime corrections and the
patient-journey crosswalk remain represented; the current ledger retains the
newer intake, draft and receipt-recovery history rather than copying every older
paragraph verbatim. #367's other documentation changes remain a separate
reconciliation. Existing contributor branches are not rewritten or retargeted.

Independent boundary review identified an inherited Review decoder gap: question
and return-history `created_at` fields accepted impossible calendar dates, year
zero and hour-24 rollover through `Date.parse`. This is a client contract and
disclosure defect, not evidence that the PostgreSQL owner emits invalid dates.
The decoder now reuses the same existing strict, timezone-bearing
seconds/up-to-six-fractional-digit validator as task and citation history. No
date is rewritten, no new review owner is introduced, and the three-field
immediate return receipt contract remains unchanged.

Observed local reproduction: the 54 existing Review client tests passed. Adding
five regressions produced four expected failures and 55 passing controls before
the decoder change. The minimal correction passes all 59 Review tests, with
zero failures, skips or cancellations. Tests cover both date fields, literal
valid offsets/leap dates/microseconds, withholding a malformed refreshed inbox,
preventing a new return, and retaining an uncertain return's exact reason/key
and identical retry body. Receipt recovery cannot restore an invalid inbox;
only a later valid read restores its projection. These local executions use
Node's TypeScript transform, not a pinned compiler or production-build claim.
The 13 filesystem rights controls and the existing data-boundary audit also pass.

The actual-browser regression corrupts copies of authorized Review responses,
retains the original values separately and checks removal of the queue, history
and new-return controls without additional writes. Fresh valid reads must restore
the original question/receipt identities, source anchors and timestamp text.
Full composed client/build/rights and PostgreSQL/FastAPI/React/Chromium acceptance
remains required at the published candidate. The draft PR receipt will record
that exact head, run and artifact without changing this source checkpoint.

Operational backend, migrations, shared source, reference tests, dependencies,
permissions and the API workflow are unchanged. The recent full backend evidence
on #365 and #367 remains separately attributed to its tested heads and identical
backend inputs; it is not a new standalone API/backup-restore run here.

The parent-chain review also found an omitted, test-only #193 method,
`ReceivedRecordHTTPTests.test_amended_original_before_first_receipt_cannot_satisfy_request`,
from commit `b00989c1887f094a1de03a4c6d9d6b8758260fb8`. Its production guard is
already present; the exact 28-line regression should be reconciled in the next
backend/whole-chain integration. Main changed shared source and browser inputs
during this review (observed `c4798ae85004713593f83458abd2102be6729095` at
14:38 EST). A future main composition needs a fresh pin and combined API,
reference/browser and H1 web acceptance, plus the scoped owner/merge decision.

Independently authored fictional inputs only. This bounded candidate is a draft;
it does not establish human owner acceptance, clinical validation, production
identity, whole-product commercial clearance, merge or deployment.

## Unsent follow-up creation drafts — 3 November 2026

Draft #379 continues #375 at `1bdc44ac8507ec3a05398c3965bed5fcae0d59eb`
(tree `8adcccc18f34e6f28cd178af9f213834dbc34cc8`) under OI-007/009/010/013.
Unsent coordination fields previously lived inside the mounted question form;
leaving Investigations discarded them. The tests-first hosted run
[41711236459](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41711236459)
at `bf63226af9c99eb9c30c38d1bcc958673a678aa5` passed all 397 compiled
client tests, build and dependency checks, then failed the new actual-browser
assertion: `Same-case navigation discarded unsent follow-up title`.

The correction stores unsent creation fields only in the existing tab's
RegistrySession, bound to patient, case, question, source snapshot and preflight.
Same-case navigation and matching source/question refreshes retain the literal
fields. Changed snapshots, missing/changed questions, revoked scope, patient/case
changes and disconnect clear them. The form never stores drafts in browser
storage or sends a command until explicit submission. Successful task transitions
retain another unsent creation draft; a confirmed creation consumes only its
question's draft. Existing captured command bodies and retry keys remain the
authority for uncertain writes, and edits are blocked until resolved or abandoned.
Ordinary rejected input retains editable fields; denied access clears them.

Local verification at the first implementation checkpoint: 46 follow-through
session tests and 13 filesystem rights controls passed; Python helper syntax,
whitespace and the existing synthetic-data boundary audit passed. New local
tests use Node's TypeScript transform, not a typecheck. The full local `npm test`
could not run because the pinned TypeScript toolchain is absent. Final hosted
TypeScript/Vite/client/PG16/FastAPI/Chromium acceptance and independent source
review are pending at this source checkpoint; the PR records subsequent
exact-head results without rewriting this historical checkpoint.

No backend, SQL, grants, dependencies or workflow changes. Status-transition
input retention across navigation is not added by this slice. It is not durable
autosave, a clinical order, notification or clinical approval. Synthetic only;
draft, unmerged and undeployed. Main and other owners' branches are unchanged.

### Status-change draft continuation — 3 November 2026

The same draft #379 now also addresses unfinished status-change reasons and
proposed owners. Tests-first [run 41715861398](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41715861398)
at `fedd78104b5e40e6583765797878fb6876650438` passed all 401 inherited
client tests, 13 rights controls and build, then reproduced the actual browser
failure: `Same-case navigation discarded unsent transition owner`.

These fields remain in the existing RegistrySession and are bound to the exact
task, revision, status, recorded owner and original source/question context.
Matching authorized task reads preserve them, including daily date-flag changes.
A changed revision, source reassessment or missing task clears the old input.
Case/patient/access/session boundaries clear both kinds of unsent work. Explicit
clear and confirmed submission consume only the selected draft; unrelated tasks
and creation drafts remain separate. The captured command and request key remain
authoritative for uncertain writes even if later task history advances.

At this implementation checkpoint, 54 follow-through session tests and 21
attention controls passed locally using Node's TypeScript transform. The browser
helper additionally exercises navigation, matching task refresh, explicit clear,
successful submission, unrelated task creation, source amendment and case-roundtrip
clearing. Final hosted compilation/build/database-backed browser acceptance and
independent review are pending here; subsequent evidence is recorded on #379.
This supersedes the earlier creation-only scope note without changing its
historical verification record. No backend, migration, dependency, grant or
workflow changes; memory-only synthetic engineering, no clinical action.

### Preparation agenda and retained follow-up input — 3 November 2026

This composition joins #395's question-linked preparation agenda at
`48d543609d96915c907bfab9d6a0eda2648977de` and #379's retained creation/status
fields at `61339216147154c2c3555933e6e1c7281f3c0460`. Both canonical owners and
parent histories are preserved. The three draft runtime files are reused exactly;
the shared browser helper retains both owners' acceptance scenarios.

Two composed-session regressions and real Overview navigation/refresh assertions
check that unsent task titles and proposed owners never appear as saved work.
Matching reads preserve literal input; a denied task read clears both draft kinds
and recorded work, while separately authorized questions remain readable.

The tests-first checkpoint passed 426 inherited tests and failed the 14 added
regressions on absent draft methods. The integrated candidate passes 440 client
tests, 13 installed-rights filesystem controls, TypeScript/Vite build, Python helper
compilation and the inherited synthetic-data audit locally. Full combined hosted
PostgreSQL/API/Chromium acceptance and independent review are pending at this source
checkpoint; the new draft PR records subsequent exact-head evidence. See the
[bounded plan](../superpowers/plans/2026-11-03-preparation-followup-drafts.md).

No backend, schema, grant, dependency or workflow changes. This does not implement
durable autosave, a referral, appointment, external handoff or clinical approval.

## Fresh report status invalidates stale comparison context — 3 November 2026

Bounded continuation of OI-009/OI-010/OI-013 on #375, pinned to
`1bdc44ac8507ec3a05398c3965bed5fcae0d59eb` (tree
`8adcccc18f34e6f28cd178af9f213834dbc34cc8`). Its 423 source blobs and executable
modes were verified against the retained hosted archive before editing. This
continues the existing evidence owner; no API, schema, grants, dependencies or
clinical authority change.

**Reproduced problem:** a report may become historical after another authorized
client amends evidence or replaces a comparison. A fresh report read disclosed
that change but left the older packet and editable comparison draft marked
current. Server write checks remained in force, but the displayed context and
available actions contradicted the freshest known report status.

The session now invalidates the older evidence packet and parallel original
reads when a previously current report first returns historical. An exact unsent
draft remains in memory, hidden and inactive until a matching fresh packet can
be verified. An uncertain write retains its exact request and receipt-recovery
path. Denial, malformed data and withheld content retain their stronger draft
clearing behavior. A report already known to be historical does not invalidate
an independently refreshed packet merely because the report remains historical.

The verified historical report's immutable references permit only another fresh
read of that exact report after packet invalidation, including download. They
cannot start a comparison, authorize another report identity, change original
body/snapshot hashes or promote the historical report to current. Every download
still rechecks the API; case, patient, session and navigation boundaries continue
to discard late reads. Previous files remain unchanged.

**Observed local evidence:** clean baseline 397 client tests. The seven added
session regressions initially produced five expected behavioral failures and two
passing controls at local tests-first commit `14cf0ff` (published identical tree
`d0dbaeec0987c8f74d353d4fe40e5b78710c102f` in
`62e32889c460f9246f21a1d0a7bba599225070ba`); all 404 client tests then passed
with zero failures, skips or cancellations. Production TypeScript/Vite build,
13 filesystem rights controls, 18 installed-package inspections, synthetic-data
boundary audit and Python browser-helper compilation passed. Two optional
packages remain uninspected. The gate initially rejected a symlinked local
dependency root; copying the same locked installed packages into this candidate
resolved that setup issue without changing the gate. A repeated historical-only download
check additionally exercises the actual Blob path.

**Hosted acceptance requirement:** the browser journey must create a real
amendment through the existing independently authorized HTTP helper while the
browser still holds the original packet and an unfinished draft. It then opens
the old report before refreshing evidence, verifies removal of stale comparison
controls and hidden draft text, downloads the historical report with a fresh
receipt, explicitly refreshes to the corrected evidence and discards the old
draft before authoring a new comparison. No automatic comparison/report write is
allowed. The existing denial, restart, recovery, withdrawal and retained-file
checks remain in the journey. Independent runtime review found no blocker and
reran all 404 tests; browser-helper and download review also found no actionable
issue. These are automated engineering reviews, not human clinical approval.

**Completed hosted acceptance — draft #378:** [run 41711007124](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41711007124),
[job 126178719241](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41711007124/job/126178719241),
passed on exact implementation head `807e3d9fd828be1bc1c3a75486e413c06d21d551`,
tree `867d3f5b5a65963ff7d0a61b7a556eefffd0fd9d`. Hosted results: 404 client tests
and 13 rights tests, zero failures or skips; TypeScript/Vite build, synthetic-data
audit, frontend/backend dependency gates and actual PostgreSQL 16/FastAPI/built
React/Chromium journey passed. The new external-amendment path and inherited
review, source-reading, evidence, follow-through, denial and restart paths all
completed. This frontend continuation does not claim a new full standalone
backend/backup-restore run.

Retained [artifact 13268033686](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41711007124/artifacts/13268033686):
5,400,216 bytes; downloaded SHA-256
`c791f530760193d4e67dfa7037e8b7041173addc71ae52a899b7254a7b4cc326`, matching
the hosted receipt. Its recorded head and all 424 tracked source blobs/executable
modes match the published implementation tree. All three retained report files
match full-file/body hashes and fresh access receipts. The original and historical
versions of the first report have identical 3,859-byte bodies; its later download
adds historical status and a fresh receipt. The replacement report has its own
3,860-byte body. The exact original-evidence file hash also matches. The retained
workflow JSON confirms external amendment version 2, stale control invalidation,
hidden draft retention and fresh historical-only download; the checked browser
code asserts these behaviors and no implicit comparison writes. Artifact
retention expires 10 November 2026.

The subsequent documentation-only delivery records these results without
changing the tested runtime, tests, browser probes, dependencies or workflows.

Synthetic engineering only; unmerged and undeployed. This change does not prove
scientific applicability, clinical usefulness, production identity or complete
platform readiness.

### Report freshness in the preparation workspace — 4 November 2026

The continuation of #402 (`547039fb3ea3e2d520cbbc4e2318c5b97d99ceae`)
incorporates #378 (`ecc8f6d8066178573c950ab537faea8094a1e81c`) while preserving
both source parents. Its evidence-session runtime is reused byte-for-byte.
Two composed-session checks verify that evidence-only report reassessment/denial
cannot erase independently authorized follow-up drafts or change saved preparation
work. Common session termination still clears both kinds of state. The real browser
adds unsent creation and transition fields before an externally authored evidence
amendment and requires those fields to survive the historical report read and
freshly authorized download without creating task writes.

Local tests first produced 442 passes and seven expected failures. The combined
implementation passes all 449 client tests, 13 rights controls, installed-package
inspection, TypeScript/Vite build, Python helper compilation and the synthetic-data
audit. Independent review and exact combined hosted acceptance are pending at this
source checkpoint; the new draft PR records subsequent results. See the
[bounded plan](../superpowers/plans/2026-11-04-preparation-report-freshness.md).

No backend, schema, grants, dependencies or workflow changes. This remains a draft
synthetic engineering candidate; no clinical release, external handoff or deployment.
