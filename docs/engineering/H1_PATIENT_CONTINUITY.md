# Patient Overview on the connected question workflow

This is the bounded continuation in draft [#288](https://github.com/OpenxIntelligence/open-intelligence/pull/288).
It brings the existing Overview projection onto the shared authored-question,
source-inspection, verification-return and brief workflow. It creates no patient,
question, task, review or source store.

## Source ownership

The final base is [#287](https://github.com/OpenxIntelligence/open-intelligence/pull/287)
at `247705700080052705817fee9e8f7b54afa8ffaa`, tree
`e5764062351a83a20b4cc41ce8da8deee28fc688`. The available local commit
`b025f53b1aefe9a02e0aad69b0fdc054b26c0435` has exactly that tree. All API code
and tests, migrations, source/domain code, inherited reference tests, workflows,
dependency locks, and the shared owner's project-state assessment are retained
unchanged. The shared session differs only by the Overview projection re-export.
The owner's final four-file documentation receipt is preserved; its runtime is
identical to the earlier `f7b0f683ab64ba2de7363744b65b8e26528f3138` checkpoint.

Overview comes from [#286](https://github.com/OpenxIntelligence/open-intelligence/pull/286)
at `eb3cff81a4edeaf433d25cc069c9894c3bc52d0b`. Its projection, component and
seven projection tests are byte-for-byte reused. Its actual-session uncertain-save
test and browser assertions are retained with the existing owner fixtures.
The [source manifest](H1_PATIENT_CONTINUITY_SOURCE_REUSE.json) records these identities and the protected parent trees.

#287 appeared after the first ownership audit. This continuation adopts its
published implementation and extends its existing combined browser helper.
The earlier overlapping tests-first work is retained in Git history as diagnostic
evidence, rather than maintained as another API implementation or acceptance lane.

## Patient behavior

Overview offers the existing question editor, Records and Investigations. It
distinguishes an unfinished question, an in-flight save, an uncertain result and
a server-confirmed save. Drafts remain in this tab's memory and retain the existing
source fingerprint and exact retry identity. Reload and disconnect clear them.

Current/unreviewed and source-reassessment counts come only from a successful
history read for the loaded active patient/case mapping. Unknown, loading, failed
or mixed-scope histories are withheld; they are not reported as zero. A zero
count does not establish an absence of care needs. A verification return remains
an operational request, and does not turn a source question into clinical review.

All section navigation now uses the same packet/brief clearing behavior. This
includes the rail, Overview and contextual buttons between source questions and
Review. Clearing invalidates pending deliveries as well as prepared views. It
preserves the existing authored draft and uncertain-return intent. Disconnect
continues to use the existing complete session reset.

## Observed defect and acceptance

The tests-first candidate `61a4734138c6961e221a9a14b833a325c0c516c0`
(tree `42ae4c2b53a8a9c8d2d3eacd9118e1ea5f609714`) passed 143 client checks and
the locked build in [browser run 41627928286](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41627928286).
The actual PostgreSQL/FastAPI/React/Chromium journey then failed:
`Contextual navigation must invalidate the prepared source packet`.
Prepared context reappeared after navigating back from Review through its own
button. The assertion is retained unchanged and checks the remounted source panel.

The same checkpoint's [API run 41627928161](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41627928161)
ran 298 methods with 47 failing assertions/subtests in eight new disclosure
methods, zero test errors and zero skips. It demonstrated the inherited encoding
and commit-order gap. Final runtime repair and tests are owned by #287 and are
adopted unchanged here; the discarded overlapping test variant is historical.

The final browser journey extends #287's existing fourth authored question:

1. Leave its unfinished draft for Records, open Overview, and resume the exact text.
2. Save against the existing source preflight, inspect the exact original quotation,
   and show the scoped counts: three current/unreviewed questions and one historical
   question requiring source reassessment.
3. Record an explicit independent-verification reason and retain its return ID.
4. Revisit Overview and the same question, inspect the unchanged source identity,
   prepare a fresh brief and perform the actual freshly authorized download.
5. Verify the return history remains attached and clinical/model/evidence flags
   remain false. Keep the inherited amendment, original download, permission,
   delayed-response and uncertain-retry assertions.

The artifact `patient-continuity-workflow.json` connects the actual question,
source anchor, return, fresh brief receipts and downloaded bytes. Its linked
`source-brief-<question-id>.json` records the independent download request.
Desktop and 390 px Overview screenshots remain in the existing browser artifact.
Final exact-head test counts, run links, archive checksum/source comparison and
image inspection belong in the draft PR verification receipt. Local discovery
without PostgreSQL is not database acceptance.

## Limits

This uses independently authored fictional records and operator fixture grants.
It does not provide production identity, consent, clinical review, biomedical
evidence qualification, model execution, patient authorization or deployment.
The source-only brief is not the full reference application's PDF/governed-report
parity. Review returns are not external notifications or completed review.

The projection describes the last successful reads in this tab. Server operations
recheck their own permissions; external revocation, database commit and HTTP
delivery are not one atomic operation. Receipts are not delivery proof and
downloaded files cannot be recalled. Repository-wide historical data cleanup
remains a separate administration/integration issue. Keep this PR draft and unmerged.

## Verification-reason continuity — 3 November 2026

Draft [#324](https://github.com/OpenxIntelligence/open-intelligence/pull/324) extends
[#319](https://github.com/OpenxIntelligence/open-intelligence/pull/319) at
`2475d924fddef6792076bdf9039fad5be7312b7a` (tree
`b87461e4ff32bc2088678055e9c6fbf03f2fdf29`). All 403 baseline tracked blobs
were compared with GitHub before implementation. This is a bounded OI-007,
OI-009, OI-010 and OI-013 correction, not an architecture or permissions change.

### Defect and correction

Writing a reason in Review, choosing **View source questions**, and returning
unmounted the editor. Its local unsaved reason map disappeared and the valid
fictional example reason returned. An operator could consequently submit wording
other than the text they had just authored.

Only unsaved presentation text now lives at the existing App lifetime. The
patient/case scope is shared with the original Review panel. Navigating between
Review, Investigations, Records and Overview preserves exact unfinished text.
Disconnect, case/identity loss and relevant failed access checks clear it; it is
not written to browser storage. A fresh matching authorized Review queue can
restore editing independently of an earlier failed World Model request. Captured
in-flight and uncertain return intents keep their existing RegistrySession
precedence and exact retry identity. No automatic submission is introduced.

Two product files change: `apps/web/src/main.tsx` and
`apps/web/src/review-panel.tsx`. Three existing browser helpers exercise the
original user flow, denial, recovery, case and session boundaries. Backend,
SQL/migrations, API contracts, RegistrySession, review rules, dependencies,
workflow definitions and source fixtures retain their parent bytes.

### Verification history

- Tests-first `6bcd8fd079fe51895a8e5c9b2e2bf538a9e03996`,
  [run 41665269329](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41665269329):
  274 client checks/build passed; the actual React/FastAPI/PostgreSQL/Chromium
  journey failed the new exact unfinished-reason assertion after navigation.
- First repair `52d14ddee98997457878a74876583e0e40abebc1`,
  [run 41666036789](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666036789):
  all 274 client checks and the full browser journey passed, including new
  A/B/A case, disconnect/reconnect, independent read-denial and no-submission
  checks. This intermediate pass did not cover independent Review recovery.
- Independent code review then reproduced a valid fresh Review queue alongside
  a retained World Model error. The first repair made its enabled reason field
  reject typing. A separate browser regression and correction are recorded
  below; the earlier pass does not establish this recovery behavior.
- Recovery tests-first `b0801fa9cd2f58a1420da3f638136c5d717c83fc`,
  [run 41666378072](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666378072),
  passed the preceding journey then failed waiting for the enabled reason field
  to accept text after the fresh Review read. The actual DOM event left its value
  unchanged; the assertion was retained for the final repair.

### Final tested runtime

Runtime `0d08fa657c0416201536a84da9af60a8f8be7b53`, tree
`dd23617d567648c01cb281e92afbaff1fa188e65`:
[run 41666930017](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666930017)
completed successfully. Checkout logs name that exact feature SHA, not an
inferred temporary merge. All 274 client checks passed with zero skips, the
pinned TypeScript/Vite build and existing dependency gates passed, and the actual
React/FastAPI/PostgreSQL 16/Chromium journey passed. It includes literal reason
preservation with no implicit submission, recording that exact reason, independent
queue/question denial, editing after restored Review access while World Model
still shows its earlier error, A/B/A case isolation, disconnect/reconnect clearing,
empty browser storage, and the inherited source/evidence/report/task flows.

Local final verification also passed all 274 client tests, the production build,
Python browser-helper compilation and git whitespace checks. Local Chromium and
PostgreSQL were unavailable; browser/database results are hosted, not local.
The first local npm attempt could not resolve the TypeScript launcher because a
cached dependency copy dereferenced its bin symlink; restoring the generated bin
links fixed setup. No product/lockfile/test change was used to hide that failure.
The existing npm http-proxy warning remains an environment warning.

Downloaded artifact [13247015056](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666930017/artifacts/13247015056)
matched GitHub SHA-256
`8b25227079f9d043d8e97f5fcd6abc120a319e7879a58331ed066b61923c2a33`.
Its commit receipt is the tested SHA; all **403** archived source files match the
local verified runtime. The retained `review-reason-boundaries.json` records the
actual synthetic patient, both existing cases, question and clearing checks.
The artifact expires 10 November 2026. Independent code review found no remaining
blocker after the recovery correction. This documentation is appended after the
runtime checkpoint; no application, test, workflow or dependency bytes change.

### Audit scope and limits

The two supplied briefs, repository contributor rules/main plan/backlog, current
#181/#183 and the #307/#314/#318/#319 integration chain were inspected, together
with canonical Notion precedence/H1 decisions and the linked historical Drive
research. The current accepted H1 stack is React/Vite/TypeScript with
FastAPI/PostgreSQL; the earlier broadly undecided stack wording is historical.
The full patient-centered first-party platform remains the goal. This correction
preserves its existing connected workflow rather than starting another frontend.

The existing workflow-pattern audit passed, and four retired named-person data
entrypoint tests passed with network calls intercepted. This is not a complete
history/artifact/data audit. The existing installed-package license/notice gate
reported 18 installed packages, two optional packages uninspected, and zero
errors. No software/model/data/content artifact is newly adopted or cleared.
Public patient narratives, competitor workflows, the broader technology atlas,
biomedical rights and clinical validation were not newly researched in this
bounded correction; earlier source evidence is not upgraded by these tests.

Independently authored fictional data and operator fixture grants only. No real
identity/consent, professional clinical review, model inference, clinical
recommendation, merge or deployment. Full separate API unit/restore suites were
not rerun for this UI-only change. Parent and sibling integrations still need
source-owner and maintainer review; #315 citation-history and #316 report-cover
fixes are separate and are not included merely because they were inspected.
