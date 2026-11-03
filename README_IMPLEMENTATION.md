## Running the first implementation locally

This is an **original, dependency-free Python 3.11+** experimental implementation. No clinical backend, model, hosted API, third-party UI library, or professional license is required for the synthetic-only exercise.

```bash
PYTHONPATH=src python -m open_intelligence seed
PYTHONPATH=src python -m open_intelligence serve
# Visit http://127.0.0.1:8765
```

To run the verification suite:

```bash
PYTHONPATH=src python -m compileall -q src
node --check web/app.js
node --check web/mission.js
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python tests/browser_journey.py
PYTHONPATH=src python tests/patient_mission_browser_journey.py
```

The browser journeys require an installed Chrome or Chromium executable. GitHub Actions runs all of these checks for the implementation pull request.

For the demonstration: create a question in `CASE-ALPHA`, save an investigation draft linked to the pathology document, acknowledge it in demo mode, load the example amendment, and import it. The prior investigation becomes `stale`, the question reopens, and the original source remains accessible. Draft a replacement against the amended document. `CASE-BETA` remains unaffected.

**Scope and warnings:** this is local-only software with no authentication, no access controls suitable for PHI, no clinical inference, no live literature or trials, and no clinical review. Never insert real patient data. The supported structured test format is `OI-SYNTHETIC-REPORT/1`, not a general-purpose clinical document parser. Source statements are author-supplied within report bytes. There is no treatment recommender, trial matching, or AI agent. The demo reviewer acknowledgment cannot attest professional credentials. The engineering controls are not evidence of medical safety or regulatory status.

The project distribution license remains undecided. Public source visibility is not an open-source license grant. All test reports and UI code are independently authored for this repository.

## Patient Mission workflow projection

The portal now includes a read-only **Patient Mission** panel near the top of the existing case workspace. It projects the canonical case ledger into five workflow questions:

1. Where is this synthetic case workflow now?
2. What do the current authored sources report?
3. What remains unresolved, stale, or quarantined?
4. Which material source or evidence changes were recorded?
5. Which bounded workflow action is supported by the capabilities already present in the demo?

The JSON form is available at:

```text
GET /api/cases/{CASE-ID}/mission
```

The endpoint and panel do not create or persist a second patient record. They deterministically derive their contents from the current `CaseStore.state()` snapshot and preserve source-version and source-line references. Workflow states are limited to `awaiting_sources`, `ready_to_define_question`, `investigation_in_progress`, `review_required`, and `reviewed_in_demo`. These are **workflow/review states, not medical or patient-condition states**.

The panel automatically follows the selected synthetic case and refreshes after the canonical workspace changes. A source amendment can therefore move the projection to `review_required`, surface the exact stale investigation IDs, describe the recorded amendment, and suggest reconciliation as a bounded workflow action. Stale responses are discarded after case changes, and the test suite verifies that Alpha source text cannot appear in Beta's mission projection.

This slice does **not** add identity, consent, patient goals, PHI support, medication intelligence, acute-safety escalation, diagnostic inference, literature appraisal, trial matching, treatment selection, therapeutic development, care coordination, outcome interpretation, or platform learning. It is a source-grounded workflow orientation surface for the synthetic engineering reference only.

## Plain-language patient/caregiver report

The portal includes a read-only **Plain-language report** view, reachable from the workspace navigation and from the patient view. It renders five sections — overview, timeline highlights, open questions, option portfolio status, goals — deterministically from the current recorded case state. No model is called and no new inference is performed; templates and recorded data only.

```text
GET /api/cases/{CASE-ID}/patient-report          # JSON
GET /api/cases/{CASE-ID}/patient-report?format=text  # printable plain text
```

Behavior contract: every section names its source for each entry or states plainly that it has none; pending, unknown, stale, and quarantined states stay visibly unsettled and are never smoothed over; the report's own voice carries no clinical interpretation, recommendation, or directive language (fixed templates checked by a language guard at build time, with recorded entries shown verbatim as attributed quotations); the ledger has no goals entity, so the goals section reports that absence instead of inferring goals. The report and its UI are labeled fictional/demo throughout, and the view offers Print plus a plain-text download.

This slice does **not** add patient goals tracking, clinical interpretation, recommendations, or any new ledger state. It is a presentation projection over the existing case record for the synthetic engineering reference only.

## Fictional evidence and case applicability slice

The evidence form supports only the explicit `OI-SYNTHETIC-EVIDENCE/1` format with `Rights: original-synthetic`. Use the bundled `examples/synthetic/demo-evidence.txt` text. That declaration is not legal clearance for arbitrary user-supplied text. No third-party paper, article body, guideline, or real oncology data is retrieved or reused.

The UI can register an original fictional evidence item, attach a manually-authored relationship and applicability assessment to a case-specific question, include selected assessments when drafting an investigation, inspect the exact source text/line/hash, and withdraw a fictional item. An explicit `Amends: EVIDENCE-ID@LATEST-VERSION` replacement or withdrawal flags every dependent investigation in every affected synthetic case as stale, while retaining older source versions for audit. Assessments for superseded/withdrawn evidence cannot be included in new drafts.

The labels `supports`, `contradicts`, and `applicable` are human-entered **fictional engineering data**, not determinations of evidence quality, clinical benefit, trial eligibility, or clinical relevance. The prototype has no clinician identity verification or legal rights-verification service. Never use real patient records or copyrighted publication text. Run the unit/HTTP tests before reviewing the UI; browser execution requires a separate interactive verification.

## Clinician review queue and sign-off receipts

The case workspace includes a **Review queue** panel (nav link and case-overview button, `#review-queue`). It is a derived projection over the existing ledger — human investigation drafts, model investigations, amended source versions, held or re-review discussion options, and fictional evidence assessments — with age and status, oldest first. It creates no second ledger.

```text
GET  /api/cases/{CASE-ID}/review-queue
POST /api/cases/{CASE-ID}/review-queue/receipts
```

A receipt posts `{"queue_key": "...", "action": "reviewed|acknowledged|returned", "reviewer_label": "...", "reason": "..."}`. Reviewed and acknowledged resolve the current version of the item; returned requires a 10–600 character reason and keeps the item visibly queued with that reason. Receipts are append-only: there is no update or delete path, and a second terminal decision for the same version is rejected.

Each item carries a fingerprint of the ledger state it was reviewed against, so an amendment or evidence withdrawal reopens the item with its earlier decisions preserved as history instead of silently carrying them forward. The existing demo acknowledgment and option-review routes append a matching queue receipt in the same transaction, so no item leaves the queue without a recorded decision. Nothing is auto-approved, auto-dismissed, or removed because of age.

A sign-off records that a person looked; it never approves, authorizes, or recommends any treatment, test, or procedure. Recommendation/order/eligibility language is rejected in reviewer labels and reasons. Reviewer labels are unverified demo text, not credentialed identity. This slice covers evidence assessments as new evidence; broker and discovery links are not yet queued.
## Longitudinal biological explanation slice

The case view links to a **Biological explanation** panel for human-authored, source-anchored context records: each explanation ties one question to a fictional episode, specimen, lesion, and clinical time point, and each assay observation ties one fictional assay to exactly one tissue block (or explicitly unknown), a matched-control state (`recorded`, `missing`, or `unknown`), and a reference kind (`patient_normal`, `external_population`, or `unknown`). Competing explanations for one question survive side by side; a recorded specimen that contradicts its anchored source is rejected rather than merged; and both tables go stale anchor-exactly on source amendment. Authored text rejects staging, grading, variant-interpretation, response/progression, eligibility, and treatment language. See `docs/BIOLOGICAL_EXPLANATION.md` and `tests/test_bio_explanation.py`. This slice states no clinical meaning for any variant, stage, grade, or response, and is not evidence of benefit or a basis for administering anything.
## Counterevidence and safety-uncertainty surfacing (options)

The options panel can record, per option, append-only **counterevidence**
(`hold` or `invalidate`, with a plain-words reason and exactly one
triggering source version or evidence assessment) and **safety uncertainty**
flags (`expression_only`, `tracer_only`, `preclinical_only`,
`cross_modal_gap`, `other`, each with a server-issued plain-language
label). Both stay visible in the derived option view even after later
amendments supersede their triggers, and both block promotion: a held,
invalidated, or safety-flagged option cannot be approved or reconfirmed,
and promotion scopes claiming established benefit/toxicity or a patient
response/permission are refused. A new proposal on current inputs is the
only path forward. Single-modality notes never read as established benefit
or toxicity; preclinical notes always read as preclinical only, never as an
observed patient response or permission to administer. Routes:

```text
POST /api/cases/{CASE-ID}/options/{ID}/counterevidence
POST /api/cases/{CASE-ID}/options/{ID}/safety-flags
```

All records are fictional engineering data for clinician review; the
platform surfaces uncertainty and never resolves it by itself. See
`tests/test_counterevidence_safety.py`. Wording guards are narrow
pattern checks, not classifiers, and human-authored descriptions outside
these fields are not policed.

## Bibliographic metadata panel

The public bibliography panel is **not linked to the selected synthetic patient**. It displays an authored Crossref-format test record using an offline local JSON fixture. The local demo server denies live lookups by default. To explicitly enable an operator-requested DOI-only Crossref lookup:

```bash
PYTHONPATH=src python -m open_intelligence serve --enable-crossref-live
```

Optional: `--crossref-contact operator@example.org` adds the operator-supplied contact email to the DOI-only metadata request, not a patient address. Crossref's current [access policy](https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/) describes rate limits and polite contact requirements. The prototype enforces one concurrent DOI lookup and a conservative one-second gap.

Only the public DOI is transmitted to a fixed Crossref API endpoint, and only bibliographic metadata fields are rendered. Abstracts, article text, full-text links, evidence grades and patient identifiers are never included in the output. The UI does not attach metadata to a clinical assertion or claim patient relevance. Live service behavior and medical usefulness require separate evaluation. No patient data should ever be used in this demo.

## Meta investigation layer (Meta Model API, OI-008)

The investigation layer is the first visible Meta tool use in the
product. It is server-side only and bounded by design:

- `POST /api/cases/{case}/investigations` with
  `{"question_id": N, "template": "evidence-summary"|"timeline-gaps"|"evidence-applicability", "mode": "live"|"replay"}`
- `GET /api/cases/{case}/investigations` lists investigations;
  `GET /api/cases/{case}/investigations/{id}` returns one, always
  labeled `kind=hypothesis`, `review_state=pending`.
- Live mode calls Meta Model API (`muse-spark-1.3`) with a fixed
  template plus the case's current assertions and fictional evidence
  assessments; the operator key comes from `META_API_KEY` only.
  Without the key, live returns 503 and points at replay.
- Every model claim is validated before storage: citations must
  resolve, uncertainty must be low/moderate/high, and
  recommendation/treatment/dosing language is dropped by the guard
  and recorded. Claims that fail any check are dropped, never
  repaired. Empty results abstain with a reason instead of guessing.
- Replay mode serves the recorded fixture
  (`examples/synthetic/demo-investigation.json`) through the same
  validation, labeled `mode=replay`, `model=recorded-replay`.
- A source amendment marks the case's investigations stale, like
  drafts. See `docs/META_MODEL_API.md` for the provider record.

Run it locally:

```bash
PYTHONPATH=src python -m open_intelligence seed
PYTHONPATH=src python -m open_intelligence serve
# Create a question, then POST an investigation with mode=replay
# (offline) or mode=live (with META_API_KEY set in the server env).
```

Remaining proof step: a live-server run against the real API with
the operator key set, before the demo. The API completion itself
was verified separately on 2026-10-31.

## Investigation workspace slice

Durable investigation questions that survive amendments and stay linked to
their evidence. All records below are fictional demo data; nothing here is
clinically reviewed and nothing selects a treatment.

- New append-only tables: `workspace_questions` (question text, status,
  created timestamp plus derived created date), `workspace_question_history`
  (every status change with its reason and preserved answer), and
  `workspace_question_links` (question-to-source-version records).
  Statuses are restricted to `open`, `in_progress`, `answered`,
  `needs_review` in both SQL checks and Python validation.
- Routes (case-scoped; unknown case returns 422 as elsewhere):
  `POST /api/cases/{case}/workspace-questions` creates a question;
  `GET .../workspace-questions` lists questions with links and history;
  `POST .../workspace-questions/{id}/links` links a current source version;
  `POST .../workspace-questions/{id}/links/{link}/unlink` supersedes a link
  (the row is kept, never deleted);
  `POST .../workspace-questions/{id}/status` records a human status change
  with a required reason. Answer text is only accepted when marking a
  question `answered`.
- Questions are never auto-answered: only the explicit status route moves a
  question to `answered`. When a linked source version is amended, every
  `answered` question with an active link to the superseded version reopens
  to `needs_review` in the same import transaction; its prior answer is
  preserved in history and its current answer reads back empty. Unlinked or
  unanswered questions are untouched, as is every other case.
- UI: an "Investigations" panel (`#workspace-investigations`) in the case
  view lists each question with its status pill, linked sources as
  `DOCUMENT@VERSION` with source and link states, and per-question history.
  Every item carries a FICTIONAL label; answers render only for `answered`
  questions while history keeps earlier recorded answers for review.
  Rendering uses existing CSS classes and text-only DOM updates, follows
  the case-switch guards, and discards stale responses after a case change.
- Tests: `tests/test_investigations.py` covers the store
  (create → link → answer → amend → `needs_review` with history intact,
  reason/answer rules, append-only links, case isolation), the HTTP routes
  (including 422 for unknown cases and cross-case links), and the UI/server
  contract (panel markup, case-scoped text-only renderer, route presence).

Limitations: no authentication or real-patient support; amendment reopening
applies only to source-version amendments, not to evidence or rights changes;
the demo reviewer label is unverified and is not clinical sign-off.
## Source provenance and amendment history

A read-only projection over existing sources, snapshots, and events.
No new tables, no new writes. Every call reads live ledger state, so an
amendment appears as a new chain link and chain event the moment its
import commits. Superseded versions stay retrievable with anchors intact.

```text
GET /api/cases/{CASE-ID}/provenance
```

Per source document, the payload lists the ordered chain original →
amendments. Each link carries version number, received date
(`received_at` plus `received_date`), exact anchor (`DOCUMENT@VERSION`),
state (`current`/`superseded`), supersession links, the import event that
recorded it, and the saved investigations citing it with their ledger
review state quoted verbatim (`draft`, `reviewed_in_demo`, `stale`).
Per-document `chain_events` record each receipt and which investigations
were marked stale. Unknown case IDs return 422 with `Unknown case`, as
elsewhere. Case isolation holds: only the requested case's rows appear.

The portal adds a **Provenance** panel after the timeline. It lists
documents, expands each chain oldest-first, marks superseded versions
explicitly while keeping them viewable with anchors, and shows citing
work in plain language. Every item is labeled FICTIONAL. Rendering uses
existing CSS classes and `textContent` only, follows the selected case,
clears on case switch, discards stale responses, and refreshes when the
ledger changes. It makes no medical judgment and suggests no treatment.

Falsifiable coverage lives in `tests/test_provenance.py` (store +
HTTP + UI-contract): a twice-amended source shows a 3-link ordered chain
with correct flags, superseded text stays retrievable, a single-version
source shows one link, citing review states match the ledger exactly,
case isolation holds, and unknown cases return 422.
## Consent and identity records slice (display and history only)

Fictional consent entries and identity-qualifier notes are inspectable
records. This slice adds no identity resolution, matching, or cross-case
logic, no treatment selection, and no clinical approval.

Tables (additive, in `src/open_intelligence/store.py`):

- `consent_records`: one row per fictional consent (`scope_text`,
  `date_recorded`, current `status`, optional same-case source anchor,
  `review_state='display_only'`).
- `consent_versions`: append-only history. Version 1 is `active`;
  withdrawal appends a `withdrawn` version with a reason. Prior versions
  stay, never deleted.
- `identity_qualifiers`: one fictional note per row (`qualifier_text`,
  required `anchor_source_version_id` in the same case, optional
  `anchor_line`, `date_recorded`, `review_state='display_only'`).

Statuses are restricted to `active` and `withdrawn`. Withdrawing changes
only its own status pointer and version chain; no other consent,
qualifier, source, question, or snapshot is touched. Qualifiers never
alter any existing identity field.

Routes (all case-scoped; unknown case returns 422 `Unknown case`):

```text
POST /api/cases/{CASE-ID}/consents
POST /api/cases/{CASE-ID}/consents/{ID}/withdraw
GET  /api/cases/{CASE-ID}/consents
POST /api/cases/{CASE-ID}/identity-qualifiers
GET  /api/cases/{CASE-ID}/identity-qualifiers
```

`GET /api/cases/{CASE-ID}/state` also includes `consents` (with ordered
`versions`) and `identity_qualifiers` (with `anchor_label`) for the
current case only.

UI: the case view has a `Consent & identity` panel (`web/index.html`,
`web/consent.js`) with plain-word forms, current consents, full history
per consent oldest-first, and qualifier notes with source anchors.
Every item carries a FICTIONAL label. Rendering uses `textContent` only,
never `innerHTML` with data. Case switching guards unfinished consent
text and clears consent inputs; stale responses are discarded by
sequence, and lists are cleared on switch so no case's data appears in
another case's view.

Verify with:

```bash
PYTHONPATH=src python -m unittest tests.test_consent_identity -v
```

Limitations: fictional/demo records only, no real consent management, no
verified identity, no access control, no clinical meaning. Physician
authority preserved; hypotheses stay separate from facts.
## Clinician overview projection

The case view now includes a read-only **Clinician overview** panel. It
organizes the recorded file for one fictional case; it makes no care decision.

```text
GET /api/cases/{CASE-ID}/clinician-overview
```

The projection is pure: `build_clinician_overview(state)` derives six
sections from the current `CaseStore.state()` snapshot with no new tables
and no writes — current sources with version numbers, open questions,
pending reviews, follow-up tasks, goals count, and journey stage. Every
item carries a citation to its source version or record id. Pending
reviews list draft snapshots, stale snapshots whose question is still
open, options with `needs_review`, and quarantined deliveries — the same
ledger the workspace already shows, not a second truth. Follow-up tasks
list preparation tasks that are not `done` or `cancelled`, exactly as
recorded. Historical stale snapshots whose question was later addressed
stay in history but leave pending. Goals are not recorded in the current
synthetic ledger, so the count is honestly `0` with an explicit note.
Journey stage is a workflow label only (`awaiting_sources`,
`ready_to_define_question`, `investigation_in_progress`,
`review_required`, `reviewed_in_demo`); it is `review_required` whenever
pending is non-empty, including drafts waiting for acknowledgment.

Both the JSON and the panel display the exact disclaimer:

```text
Summary of the recorded case file only — not a clinical recommendation, not a treatment decision.
```

The projection's own wording avoids authorize/prescribe/order/
recommend/direct-care language; the disclaimer carries the word
"recommendation" only in negated form. Verbatim question, task, and
option labels are quoted ledger facts. Empty sections render honest
empty text, never invented content. The renderer uses existing CSS
classes and `textContent` only, labels every item FICTIONAL, follows the
selected case, discards stale responses after case switches, and
refreshes when the workspace changes. Unknown case ids return `422`
with `Unknown case`, as elsewhere.

This slice adds no identity, consent, goals ledger, PHI support,
diagnostic inference, treatment selection, or clinical approval. See
`tests/test_clinician_overview.py` for the store, HTTP, and UI-contract
checks, including case isolation and a view-wide directive-wording scan.
## Evidence quality and limitations panel

Each fictional source version can carry zero or more human-authored
quality notes. Notes are descriptive only — completeness note,
limitations text, conflict note, assessor label, date recorded — and
never a rating, score, or clinical judgment. A source with no note
renders an explicit "not assessed" marker; no quality is inferred.

Storage is append-only (`evidence_quality_assessments`, one row per
note, never updated or deleted). Recording a note never changes the
source itself or any review state. Amending a source leaves old notes
attached to the superseded version; the replacement starts unassessed.

```text
GET  /api/cases/{CASE-ID}/evidence-quality
POST /api/cases/{CASE-ID}/evidence-quality
```

GET returns one entry per current source version (source id, document
id, citation anchor, assessments or `not_assessed`) plus superseded
versions separately with their own assessments in recorded order.
Unknown case ids return 422, as elsewhere. POST records one note for
one exact source version in the same case and returns its id.

The case view includes an "Evidence quality" panel with one block per
source, FICTIONAL labels throughout, plain language, and text-only
rendering. Containers clear and reload per selected case, so no case's
notes appear in another case's view.

Covered by `tests/test_evidence_quality.py` (store + HTTP +
UI-contract). Fictional/demo data only; no clinical accuracy claim.
## Second-opinion and survivorship care records

The case workspace includes a **Second opinion & survivorship** panel for
fictional record-keeping only. A second-opinion request records the
question asked, the case question it is about, materials shared by exact
source-version reference, an optional link to the original case
conclusion under discussion, and a status. A response is recorded as a
separate record anchored to one source version; exactly one response per
request exists, so follow-up needs a new request. Recording a request or
response never modifies the original snapshots or questions: the case
state carries both, and the UI renders the original conclusion and the
response side by side.

Survivorship plans hold plain recorded items of three kinds: `followup`
(recorded schedule notes with an optional recorded date), `watch` (plain
descriptions), and `trigger` (recorded reasons to look again, which can
be marked as observed exactly once). Every item keeps its source anchor
and review state. A recorded date is a ledger note, never a clinical
due date.

All record text passes a descriptive-only guard at write time
(`src/open_intelligence/care_records.py`): directive and clinical-claim
wording (should, must, need to, recommend, prescribe, eligible, order or
start treatment, watch for, seek care, call/contact, effective, proven,
benefit, and similar) is rejected with an error naming the guarded
wording. The guard is narrow; human review remains the gate, and every
view carries a disclaimer stating what the records are not.

Source amendments reopen only dependent records in the amended case:
requests whose pinned materials, response anchor, or linked original
conclusion was superseded, and items whose anchor was superseded, move
to `needs_review` while history stays inspectable. New requests and
items must anchor to current versions. Other cases are unaffected.

```text
POST /api/cases/{CASE-ID}/second-opinion-requests
POST /api/cases/{CASE-ID}/second-opinion-requests/{N}/response
POST /api/cases/{CASE-ID}/second-opinion-requests/{N}/review
POST /api/cases/{CASE-ID}/survivorship-plans
POST /api/cases/{CASE-ID}/survivorship-plans/{N}/items
POST /api/cases/{CASE-ID}/survivorship-items/{N}/review
POST /api/cases/{CASE-ID}/survivorship-items/{N}/trigger
```

Covered by `tests/test_second_survivorship.py` (store, guard, and HTTP
flow). This slice adds no identity, consent, PHI support, clinical
review, diagnostic inference, treatment selection, or care coordination.
It is a source-grounded record surface for the synthetic engineering
reference only.
## Follow-through tasks (case records for humans)

Each case can carry follow-through tasks: what was agreed, who owns it,
and when to revisit it (a due date, a review trigger, or both). Tasks are
records only — creating or changing one performs no action and touches no
other ledger (sources, assertions, questions, snapshots, evidence, options).

- Lifecycle: `created → assigned → acknowledged → completed`, with
  `deferred` as a labeled side state that reopens only through a fresh
  assignment. Completion requires a prior recorded acknowledgment, so the
  platform never claims an action was taken without one.
- Every status change appends a history row (actor, timestamp, reason);
  history rows are never updated or deleted, and completed tasks stay
  readable as history. Assignment names a human owner; deferral requires
  a reason.
- Overdue (past due, still open) and due-soon (due within 7 days) flags
  are derived read-only in the case view; completed and deferred tasks
  are never overdue. A task anchored to a superseded source version is
  flagged for re-check without changing its history.
- Task text passes a narrow guard rejecting recommendation, order,
  eligibility, diagnosis, and dosing language; every view carries a
  disclaimer that these are fictional records for humans to act on.

```text
GET  /api/cases/{CASE-ID}/followthrough
POST /api/cases/{CASE-ID}/followthrough-tasks
POST /api/cases/{CASE-ID}/followthrough-tasks/{N}/status
```

The case view (`GET /api/cases/{CASE-ID}/state`) embeds the same
projection under `followthrough`, and the workspace renders a
Follow-through panel with a visible overdue/due-soon attention box plus
separate open, deferred, and completed-history lists. See
`tests/test_followthrough.py` for the lifecycle, history-preservation,
overdue-derivation, amendment-flag, and no-auto-execution checks.
## Patient goals and lived experience (fictional patient words)

The case workspace includes a **Patient goals** panel for goals the
fictional patient states in their own words (with stated date, review
trigger, and optional review date), lived-experience notes, and symptom
notes. Each record is durable, versioned, and amendable; old versions
are preserved with `record_state='superseded'` and never deleted. A
goal can be set, amended, and marked `achieved`, `changed`, or
`abandoned` with a required plain-language reason; each change creates
a new version.

```text
POST /api/cases/{CASE-ID}/patient-goals
POST /api/cases/{CASE-ID}/patient-goals/{goal_id}/amendments
POST /api/cases/{CASE-ID}/patient-goals/{goal_id}/status
POST /api/cases/{CASE-ID}/patient-notes
POST /api/cases/{CASE-ID}/patient-notes/{note_id}/amendments
```

Current goals and notes with full history appear in
`GET /api/cases/{CASE-ID}/state` as `patient_goals` and `patient_notes`.
Patient words stay patient words: these endpoints accept no diagnosis,
staging, or response fields, create no assertions or investigations,
and leave the mission projection unchanged. Every surface labels them
fictional, patient-reported, and never a clinical interpretation. See
`tests/test_patient_goals.py` for the acceptance checks.
## Option portfolio surface (authored, awaiting reviewer verification)

An evidence-backed portfolio over the existing option ledger. It adds
append-only records only; no existing table, route, or review contract
changed meaning:

- `option_flags`: documented objections, deferrals, and reservations, each
  with a reason, a recorder label, and at most one current same-case source
  or evidence premise. An open flag holds the option: approval and
  reconfirmation are refused until the reason is resolved, and resolving or
  reopening the reason reopens review of the option and its followers. A
  source amendment or evidence withdrawal also reopens options whose open
  flags cite the changed premise.
- `option_dimension_notes`: reviewable notes on the four portfolio
  dimensions — scientific plausibility, technical feasibility, access,
  clinical authorization. Each note carries an anchor, an optional premise,
  and stays `pending` until a clinician acknowledges it. Acknowledgment is a
  record of review, never a declaration of eligibility, benefit, or
  authorization; author-controlled text making such claims is rejected.
- `GET /api/cases/{case}/portfolio` (also embedded in case state) projects
  every option ever proposed: prerequisites, objections, access notes,
  readiness, lead-time uncertainty, and expiration/review triggers.
  Deferred, rejected, and reserved entries stay visible with their reasons
  and counts; nothing is silently dropped.
- The case workspace renders this as an "Option portfolio" section linked
  from the case navigation, in plain language with fictional labels.
- Tests: `tests/test_option_portfolio.py` (store behavior plus HTTP route
  coverage through the existing live-server pattern), including the held
  reason-change review flow and rejected-entry preservation.
