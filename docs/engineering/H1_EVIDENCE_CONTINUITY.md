# H1 question evidence and patient follow-through convergence

## Authorized publication follow-up — shared CI coverage and current documentation

On 3 November 2026 the founder authorized the prepared candidate for publication
and hosted verification. A fresh read found that [draft #355](https://github.com/OpenxIntelligence/open-intelligence/pull/355)
at `6f836b451c2e8426e5c3b2be194408424f95c69f` already contains all 13 reviewed
implementation/package/test/helper blobs from local candidate
`c1484ed0ef6ac5a18359577446486e71a08845b6`, with identical modes and bytes.
Its [web run 41677951355](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41677951355)
passed on that exact head. This continuation therefore targets #355's branch
`integration/h1-connected-evidence-safety-20261103` and carries only the remaining
workflow and documentation contribution. #355's backlog and safety plan are
preserved unchanged. The earlier #328 composition below is historical evidence.

The workflow change includes shared `src/**`, `tests/**` and the boundary script
in H1 web triggers, and executes the existing static data-boundary check before
package acquisition. It preserves all existing dependency, build and actual
PostgreSQL/API/Chromium steps. Runtime, tests, dependencies, migrations, authority
and recovery owners are unchanged from #355.

Fresh local checks on the identical approved runtime again passed 310 client
tests, 13 rights controls (18 installed, two optional uninspected, no errors) and
287 reference tests. These are local evidence. This child's own published-head
API/PostgreSQL/browser/recovery results must be recorded in its PR verification
receipt after publication; #355's success is not inherited as the child's result.
Publication authorization does not authorize merge, deployment or clinical use.

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

## Historical local reconciliation — c1484ed, 3 November 2026

The direct founder instruction was to investigate the documentation and actual
repository, identify missing scope, then take concrete action. The audit read the
complete founding mandate, all unique uploaded discussion content, existing
Notion/Drive owners, live GitHub metadata and actual source. Research is
complementary to accepted decisions; the current H1 stack and canonical owners
remain authoritative.

### Pinned composition and changes

- Base #328: `5a188d4e18e4d80bc2ba1d662c966abc3096301f`.
- Chronology #330: `312ad9379311901f8a69a7c20d4ea09f98027481`.
- Native intake disclosure #335: `9d173843f924b40becba3a7dffd71717c12afb5d`.
- Installed-package identity/rights #339:
  `d694db4ca12206e815d6045b73baa9b6f7394290`.

The application and regression donors are preserved. Two #339 files
(`package.json` and `license-gate.mjs`) have only an extra trailing blank line
removed; their behavior is unchanged. The workflow also removes its extra
trailing blank line and gains the explicit changes below. Historical continuity
appendices from #330 and #335 are both preserved; neither donor's pass is labeled
as the new combination's hosted acceptance.

A concrete coverage gap was confirmed: H1 web CI imports shared `src` and
`tests/browser_journey.py` while its pull-request path filter omitted both.
`h1-web.yml` now watches `src/**`, `tests/**`, and the existing
`tools/audit_ci_data_boundaries.py`, and runs that same boundary scan before
package acquisition. The existing rights step from #339 is retained. No new
package, backend behavior, schema, migration, permission or canonical ledger
is introduced.

### Actual local verification

| Check | Observed result |
|---|---|
| Pristine archived #328 client baseline | 300 passed, no failures/skips |
| Donor chronology tests on the unfixed #328 client | 14 tests: nine intended assertion failures, five passing controls |
| Donor rights tests on the old gate | 13 tests: eight intended negative-control failures, five passing controls |
| Combined `npm test` | 310 passed, no failures/skips |
| Combined `npm run build` | TypeScript and Vite production build passed |
| Combined `npm run rights` | 13 controls passed; actual installed gate: 18 inspected, two optional uninspected, zero errors |
| Existing synthetic boundary scan | Passed; this source-pattern scan is not runtime network enforcement |
| Browser helper compilation | Passed; compilation is not browser execution |
| Donor/source preservation | Exact donor comparisons recorded; API/shared-domain/test/lock/migration/recovery runtime unchanged from #328; only API README wording changed in those directories |
| Whitespace review | `git diff --cached --check` passed after trailing-blank-line normalization |

The original checkout carried two untracked donor files from its reconstruction.
Early broad test commands therefore were not treated as pristine baseline
receipts. The clean baseline above was created using `git archive` of the exact
#328 commit and passed all 300 inherited tests. Reproduction and combined runs
were then assessed separately.

Local tooling has no PostgreSQL server, Docker or Chromium installed, so this
candidate has **no local combined PostgreSQL/browser or backup/restore execution
receipt**. Parent #322's successful API/PostgreSQL/recovery workflow
[41664891742](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41664891742)
remains evidence for its unchanged backend source, not a new run of this head.
A fresh hosted H1 web run is required after separately approved publication.
Owner/parent-chain review and any changed backend/migration acceptance remain
required before integration. No clinical or commercial release is established.

### Audit-driven documentation and next implementation gates

The existing API README, project state, requirements, integration inventory and
gap assessment now recognize the already implemented H1 evidence/report/task
owners and distinguish the complete 15-step founding MVP from this bounded
synthetic milestone. The existing #339 30-domain crosswalk is reused. All 28
founding documentation responsibilities have an existing owner, partial content
or an indexed source; they need evidence and scoped decisions rather than 28
new competing documents.

The next product gates are: (1) connect the existing supported-document and
reviewed-assertion owners to the World Model; (2) connect one permitted evidence
source to governed investigation and version-specific human review; (3) qualify
account/profile/caregiver/professional authority through existing ports; and
(4) evaluate the complete journey, including access constraints and practical
care handoffs. Preserve source truth, uncertainty, consent, current authority,
recovery and the synthetic-only development decision at every boundary.

Publishing this local candidate, modifying existing PRs, merging and deployment
remain subject to the founder's earlier explicit approval boundary. The local
work and documentation reconciliation do not imply those actions occurred.

### Independent code review of the local composition

A fresh read-only reviewer found no introduced Critical, Important or Minor
runtime/test/workflow issue. It independently checked donor identities, calendar
contracts, report invalidation, disclosure mounting/context reset, filesystem
rights controls and shared-source CI coverage. This is automated engineering
review, not human owner acceptance, clinical validation or merge approval.

One inherited minor test weakness remains under OI-010: the intake browser helper
waits for the source index to disappear, which can occur at load start before the
denial response finishes. The unchanged reading-convergence helper separately
waits for terminal denial and checks no protected content. No runtime authority
defect was observed. A later bounded test-hardening change should make the intake
assertion wait for the same terminal condition.

The final documentation pass found no material inaccurate claim in the seven
coordinator-updated API/project-state/continuity/plan files. The completed local
reference command `PYTHONPATH=src python -m unittest discover -s tests -v`
reported 287 tests and `OK`. That is additional reference evidence, not a
substitute for combined PostgreSQL/API/browser or restore acceptance. The
preservation receipt checks 193 files: 192 unchanged, with only the API README
changed; backend/shared runtime, tests, locks, migrations and recovery inputs
remain unchanged.
