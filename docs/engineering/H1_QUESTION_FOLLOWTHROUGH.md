# H1 saved-question follow-through

## Overview continuation — 3 November 2026

The Overview now composes the existing case-owned follow-through read into its
care-preparation card. It shows the five established operational counts and up
to three open tasks, including recorded owner and revisit basis, in server order.
The server evaluation date and preview coverage remain explicit. These counts
do not rank clinical urgency, establish complete care coverage or confer authority.

The card reuses `projectFollowthroughAttention` and additionally requires its
case to match Overview's successfully loaded World Model. A first read, a read
in progress and an unavailable read remain distinct from a verified empty list.
Independently readable question context survives a task-read denial. Refresh
uses the existing separately authorized GET; navigation returns to Investigations.
Saving and uncertain task writes disable refresh, and an uncertain write links
back to its existing exact-intent recovery controls.

This continuation starts from PR #375 at
`1bdc44ac8507ec3a05398c3965bed5fcae0d59eb`. It adds no dependencies, schema,
routes or persisted state. Unsent-task draft navigation (#379), report disclosure
(#378) and source keyboard focus (#353) remain separate changes. The bounded
design and acceptance plan is
`docs/superpowers/plans/2026-11-03-overview-followup-work.md`.

Local verification for this continuation: **408 client tests passed with zero
failures or skips**, TypeScript/Vite production build passed, 13 installed-package
rights controls passed, and npm audit reported zero vulnerabilities. The existing
gate inspected 18 installed packages and retains two omitted optional packages as
uninspected. The browser helpers compile and the inherited synthetic-data boundary
check passed. No dependencies or license determinations were expanded.

The focused test-first run had 18 executions: seven existing tests passed and
11 new assertions failed because the projection/card did not exist. After the
implementation, all 18 focused tests and the complete client suite passed.

### Verified Overview implementation checkpoint — draft PR #383

[Draft PR #383](https://github.com/OpenxIntelligence/open-intelligence/pull/383)
is verified at implementation/test commit
[`8ad846c3b3e8d70c360cc6ea3d0f80551ae018cf`](https://github.com/OpenxIntelligence/open-intelligence/commit/8ad846c3b3e8d70c360cc6ea3d0f80551ae018cf),
tree `8b914a34d59c32bda109195b9b3de3ac4659be85`.
[Hosted run 41714223067](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41714223067)
passed the complete 408-test client suite, production build, installed-package
and wheel gates, and the actual React/FastAPI/PostgreSQL 16 Chromium journey.

The new browser sequence uses four persisted tasks from two saved questions.
It verifies the five counts, recorded owner, read-only refresh, held-response
clearing, unchecked versus verified empty results, exact-intent recovery after
a committed response is lost, denial that preserves question context, and a
delayed prior-case response that cannot restore old task content. Existing source,
review, evidence/report, import, restart, reading and session-boundary journeys
also passed. Separate backend/restore suites are not claimed as rerun for this
UI-only change; local PostgreSQL and Chromium were unavailable.

[Artifact 13269696276](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41714223067/artifacts/13269696276)
has SHA-256 `d438b9a5937ae414aa635cbea1001c9fc7c0fd4fd57081ed0fa8f9bd7b693d31`.
Its commit receipt matches the verified head, and all **425** archived source
blobs were byte-checked against remote Git and the local tested files. The
desktop and 390px mobile Overview captures were visually inspected; the browser
also verifies horizontal containment. Artifact retention ends 10 November 2026.

Independent code review found **no Critical, Important or Minor issues** in
the bounded diff. It inspected case/patient isolation, canonical counting,
unavailable versus empty reads, unknown-write recovery, preview limits,
semantic/responsive structure, tests and the repaired browser prerequisite.
Hosted execution, artifact matching and screenshot inspection were separately
verified by the implementation owner; this is not a screen-reader audit.

This documentation-only receipt follows the verified implementation/test
checkpoint above and changes no runtime, tests, dependencies or workflows.
Status remains a synthetic-only draft, unmerged and undeployed; this does not
complete OI-010 or establish production/clinical readiness.

The historical checkpoint below belongs to its original commit and is not
evidence for the new combined head.

### First hosted attempt and harness repair

[Run 41713597645](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41713597645)
on `c21fa9cfab583c91c2f690af2bdaf61afe720e92` passed all 408 client tests,
build and dependency gates. The browser passed the new initial unchecked/empty
read and unknown-write Overview recovery steps, then failed when the new
second-question scenario assumed that previously authorized question history
was still present. The actual failure capture showed that earlier independent
permission-denial checks had correctly cleared that history while canonical
tasks remained readable. The harness now performs a fresh authorized question
read before opening that question's task form. No runtime permission check was
relaxed. This failed run does not establish completed browser acceptance.

## Verified implementation checkpoint — 3 November 2026

The implementation in [draft PR #293](https://github.com/OpenxIntelligence/open-intelligence/pull/293)
is verified at commit `635f357048eb27e52e6ec5c3d7b6714215070127`, tree
`74c4a2ab65bf54a0908246199bb67c300ae2662b`. This evidence-only follow-up changes
documentation, not runtime, tests, dependencies, migrations or workflow behavior.

| Gate | Observed result | Evidence |
|---|---|---|
| API and actual PostgreSQL 16 | 326 executions passed; zero failures, errors or skips. Concurrent create/transition retries, competing revisions, final authority, serialization rollback, SQL history guards and migrations executed. | [Run 41633216511](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216511) verified the proposed commit. |
| Original reference | All 245 tests and both inherited Chromium journeys passed. These do not imply H1 biomedical-evidence integration. | Same API run. |
| Restart and recovery | Existing patient/source/review probes passed. Three tasks and nine task events survived API/DB restart and actual pg_dump/pg_restore; the restored DB served real HTTP reads and the same retry receipts, then denied revoked bindings. | Same API run, follow-through Compose step. |
| Client and built React | 195 client tests passed, zero failures/skips; production build passed. Actual question → task → attributed lifecycle → amendment → case-switch journey passed alongside inherited intake, quotation, review and brief flows. | [Run 41633216590](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216590). |
| UI glance | Existing synthetic UI gate passed. | [Run 41633216653](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216653). |
| Dependency checks | Existing wheel/component and installed frontend rights profiles passed; npm audit reported zero vulnerabilities. No dependency was added. Production/distribution clearance remains separate. | API and React gates. |
| Artifact integrity and visual review | Exact commit, all 334 source blobs and archive SHA-256 verified. Desktop and 390px mobile task captures inspected; layout remains contained. | [Artifact 13228693741](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41633216590/artifacts/13228693741), expires 10 November 2026. |

Artifact SHA-256: `7cd60c8a39520b883553cea7f84b67c4f861f149118e785fd9db9b471aafb869`.

Independent review found the actor-length mismatch and unrelated-draft loss;
actual PostgreSQL exposed the lock-upgrade deadlock. All were repaired, reviewed
and exercised successfully on the verified implementation. The historical RED
and fixture corrections below remain part of the evidence trail.

Status: implemented and tested within the independently authored synthetic
contract; draft, unmerged and undeployed. Issue #81 and OI-008/010 remain open.
Next integration is the existing evidence/report owners through explicit H1
persistence and permission contracts. This task continuation does not perform
scientific evidence appraisal, professional review or external coordination.

## Purpose and current basis

Give a patient or authorized coordinator a durable place to record the next
piece of work arising from an existing saved question, its owner and revisit
date/trigger, and its attributed status history. This advances OI-007, OI-009,
OI-010 and existing integration issue #81; it does not introduce clinical orders,
notifications, verified clinician identity or a second patient/source record.

Implementation starts from the verified H1 #276 source
`c154bfbc5f99f76801d37903959943659c0b6a71` (API run 41576166308,
React/browser run 41576166303). All 299 archived file blobs were checked against
the upstream Git tree. During implementation, #287 completed its canonical
authored-question, exact-quotation, verification-return and brief convergence at
`f7b0f683ab64ba2de7363744b65b8e26528f3138`. Both its API run `41629005788`
and built React/browser run `41629005777` passed. Its 321-file source archive
was independently matched to Git tree `a72d810aaf32a76f9c736aa1df4232e3bcd9ced0`
before adoption. This increment now builds on that completed source; the
combined head still requires its own hosted acceptance. Parent green results
are never substituted for combined validation.

The behavioral owner is #84/#174 question/source follow-through, carried into
reference #250 at `ef2949521911ecac8164aece851674d3df4e4965`. The first-party
`src/open_intelligence/followthrough.py` is reused verbatim (Git blob
`5c099507cbd76d84f99f38eb248cad623bd2b1bb`); H1 imports its text/date/lifecycle
rules, never its SQLite runtime. Option preparation tasks (#273), automatic snapshot re-review
tasks (#258) and record-acquisition requests (#178) retain their distinct owners.
H1 will use its existing canonical patient, case, original source, question and
event journal. Reference SQLite identifiers are never coerced into H1 IDs.

## Decisions and alternatives

- **Established:** Python/FastAPI/PostgreSQL 16 and React/Vite/TypeScript; no new
  dependencies, original synthetic fixtures, independent authority grants,
  immutable original source and question provenance.
- **Recommended reversible implementation:** port the existing lifecycle into
  H1 with one task owner and append-only event history. Reusing the SQLite
  runtime would create a competing authority boundary; deriving tasks only from
  a UI would lose ownership/history on restart. Neither alternative meets the
  existing durable-work requirement.
- **Recorded choice:** task text/due date/review trigger are immutable after
  creation in this first port. Assignment can change only through the existing
  deferred-to-assigned transition. A later editing contract needs its own
  history rules. No automatic reassignment or external action occurs.
- **Recorded choice:** question/source freshness is derived by the existing
  canonical question projection on each authorized read. Open tasks show
  `needs_recheck` when that context is stale; completed/deferred work stays
  historical. An attributed task update does not approve its source context.
- **Unresolved:** production identity/delegation, clinical consent, notifications,
  deployment and clinical validation remain existing workstreams.

## Stable contract for this increment

Independent actions: `followthrough_create`, `followthrough_read`,
`followthrough_update`. Every route additionally requires `patient_read`,
`question_read`, `source_read`, exact patient/organization/case scope, active
bindings, and operations purpose. Actor comes from the trusted principal;
recorded owner is a display label, never an authority credential.

Routes share `/v1/patients/{patient_id}/cases/{case_id}`:

| Route | Contract |
|---|---|
| `GET /followthrough` | Current task projection and append-only history; all case tasks, bounded |
| `POST /questions/{question_id}/followthrough` | Create against exact saved question/source context; idempotent |
| `POST /followthrough/{task_id}/transitions` | Append one legal lifecycle transition with expected revision; idempotent |

Both write contracts require explicit `synthetic: true`.
Creation fields: `request_key`, `title`, `detail` (default empty),
`owner_label` (default empty), `due_date` (ISO date or null), `review_trigger`
(default empty), `reason`, `source_snapshot_contract`,
`expected_source_snapshot_sha256`, `expected_preflight_sha256`.
At least a due date or nonempty review trigger is required. Title 3–160,
detail 0–2000, owner 0–80, trigger 0–500, reason 3–600 visible characters.
Use the original follow-through text/date validators and lifecycle; reject
controls/formatting characters at the H1 boundary. Inputs are never silently
changed into clinical advice. The inherited text guard is not a clinical
classifier or a safety-validation claim.

Transition fields: `request_key`, `expected_revision` (positive integer),
`status`, `owner_label` (default empty; required for assignment), `reason`.
Legal lifecycle: created→assigned/deferred; assigned→acknowledged/deferred;
acknowledged→completed/deferred; deferred→assigned; completed is terminal.
New transitions require the caller's current revision. Exact retries recover
the original receipt before checking later revision/source freshness; changed
intent with the same key conflicts. A source amendment never retargets an old
task. Completion requires acknowledged status, records an assertion about work,
and does not change question/review/source state.

Create/transition receipts:
`{task_id, question_id, event_id, revision, duplicate}`. IDs use `TASK-` and
`TASK-EVENT-` plus 32 uppercase hexadecimal characters. New writes return 201;
identical replay returns 200. Unknown or unauthorized scoped targets share 404;
stale revision/context or conflicting idempotency returns 409; invalid input
422; access/database/serialization failures withhold the response and new write.

List envelope: `contract: oi.pg-question-followthrough/1`, `patient_id`,
`case_id`, `access_receipt_id`, `evaluated_on` (UTC ISO day), `tasks`,
`synthetic: true`, `clinical_approval: false`,
`external_notification_sent: false`. Maximum 250 tasks and 750 total events;
overflow fails explicitly, never silently truncates.

Each task includes `task_id`, `question_id`, `patient_id`, `case_id`,
`title`, `detail`, `owner_label`, `due_date`, `review_trigger`, `created_at`,
`status`, `revision`, `source_id`, `source_line`, `source_sha256`,
`source_version`, `source_snapshot_contract`, `source_snapshot_sha256`,
`preflight_sha256`, `source_context_state`, `needs_recheck`, `is_overdue`,
`is_due_soon`, `clinical_approval: false`, and `history`.
History: `event_id`, `revision`, `previous_status` (null on creation),
`status`, `owner_label`, `actor_label`, `reason`, `recorded_at`.

## Implementation plan and file ownership

1. **Persistence and lifecycle.** Add
   `apps/api/src/oi_api/question_followthrough.py` and explicit
   `0009_question_followthrough.py` migration after `0008_review_convergence`.
   Preserve published migrations. Reuse first-party lifecycle/validators from
   the inspected reference followthrough module. Immutable task origin and
   append-only events live in `coordination`; database guards check question,
   patient/case/organization, legal transition and revision. The canonical
   patient/case/source locks enclose reads/writes, actual response preparation,
   final authority and audit commit. Add focused real PostgreSQL tests.
2. **Typed API.** Extend the existing router/authority/manifest, not a parallel
   authentication system. Prepare actual `JSONResponse` bytes in the task
   owner callback before final reauthorization and commit. Write failing route,
   input, authority, rollback and concurrent-replay tests; run them against the
   inherited real PostgreSQL fixture. Keep body/no-store limits.
3. **Patient UI.** Extend `RegistrySession`, add typed follow-through parsing
   and a small panel connected to saved questions. Show source/recheck/history,
   status/owner/date and explicit retry for uncertain writes. Never persist
   bearer tokens or task data in browser storage. Patient/case/disconnect
   invalidation rejects late reads and write receipts; preserve exact uncertain
   intent only for the same patient/case until explicit recovery or abandonment.
   Use existing dependencies/styles and test actual client behavior first.
4. **Connected acceptance and review.** Extend the existing built React/real
   PostgreSQL browser gate with question→task→assignment→acknowledgement→
   completion/history, source amendment and patient switching. Verify restart
   persistence and actual database backup/restore using the existing container
   gate. Obtain independent code review, fix material findings, run required
   exact-head API/PG/client/browser gates, then record evidence in this file,
   the existing engineering pages and issue #81. Publish a draft only.

## Review focus

- Ambiguous write outcome must not duplicate a task/transition on retry.
- Another patient/case, revoked grant, or mismatched principal must never receive
  task text or a successful write receipt, including during response encoding.
- Amendment must keep original source identity and completed history; due-date
  evaluation must not fabricate a new ledger event or clinical urgency.
- Concurrent status updates cannot both consume the same revision or skip
  acknowledgement; immutable history must also resist direct SQL modification.
- Patient navigation and failed refresh must not leave another case's task,
  editable draft, stale history, or action controls available.

## Verification ledger

- Baseline: exact parent archive verified; no new clinical data or dependencies.
- Local PostgreSQL execution is unavailable: this executor maps only UID 0;
  PostgreSQL refuses root. Do not bypass that boundary or claim skipped tests
  are database acceptance. Use the existing hosted PostgreSQL 16 gate.
- Observed initial task-route/body-boundary failures: two tests, seven failed
  assertions before route wiring; both subsequently passed. Domain tests began
  with six service/logic failures plus the absent migration head. The first
  frontend run had 19 new failures; subsequent recovery/navigation regressions
  reproduced two additional errors. A valid distinct PostgreSQL task/event
  timestamp reproduced a decoder rejection and was corrected without rewriting
  database history or requiring timestamp equality.
- Pre-convergence local reference regression: 245 tests passed. Task client:
  129 tests passed; production build and installed dependency rights gate passed.
  These precede the final #287 reconciliation and are not its acceptance.
- Combined local API discovery: 326 executions, 60 passed and 266 explicitly
  skipped for absent PostgreSQL. Hosted acceptance must run with zero skips.
- Independent review identified an 80-character client actor bound conflicting
  with the canonical 3–128-character identity contract. A legal 128-character
  actor failed before the decoder correction and passes afterward. The combined
  client now passes 195 tests and its production build. Two observed merge
  regressions also established independent recovery of uncertain task and
  review-return intents across case-permission refresh.
- Independent review also found that a same-question task transition could
  erase an unrelated unsaved creation draft. The actual React/FastAPI/PostgreSQL
  browser run `41631363181` reproduced this on `d897280b516730d06c006ee9fcfcdb4b3169a5a9`:
  `Successful existing-task assignment discarded the unsaved second-task creation form`.
  The effect now resets only for creation receipts (revision 1); operational
  transitions have revision 2 or later. The same browser scenario must pass on
  the repaired head, including acknowledgment and retained title/detail values.
- Upstream #287's completed evidence-only follow-up
  `247705700080052705817fee9e8f7b54afa8ffaa` was inspected and preserved; its four
  documentation changes do not alter the verified parent runtime.
- The first hosted API run `41631363377` completed 326 test executions with one
  failure and ten errors before its job was cancelled by the next candidate.
  The failure exposed a real concurrent-retry deadlock: the new trigger upgraded
  the already-held patient `FOR SHARE` lock to `FOR UPDATE` after taking the case
  binding lock, while another caller held the shared patient lock waiting for
  that binding. Both new trigger patient locks now match the established
  `FOR SHARE` → binding `FOR UPDATE` sequence; patient suspension remains blocked
  and event task locking is unchanged. The existing HTTP 200/201 concurrency
  assertion is retained without retries or exception suppression.
- The ten storage errors came from treating an existing fixture helper's source
  fingerprint string as a preflight object. Setup now obtains both digests from
  the exact saved-question API row and checks that the helper fingerprint agrees.
  Seven local logic/migration-graph checks pass; actual database acceptance is
  still required after these corrections.
- Browser run `41631874629` proved the creation-draft repair and the complete
  task lifecycle, amendment, revoked-read and inherited question/review/brief
  flows. Its final case-switch step exposed a harness timing error while the
  preceding record read still disabled controls. The helper now waits within the
  existing bounded timeout for an enabled control; it also checks the exact case
  and waits for a decoded `ready` empty list. Every cross-case and delayed-response
  assertion remains active. The entire browser gate must pass on the new head.
- Current limits: independently authored synthetic fixtures only; no external
  notifications, professional clinical approval, real identity/delegation,
  patient-data authorization, model execution or biomedical evidence appraisal.
