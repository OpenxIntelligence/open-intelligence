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

## Fictional evidence and case applicability slice

The evidence form supports only the explicit `OI-SYNTHETIC-EVIDENCE/1` format with `Rights: original-synthetic`. Use the bundled `examples/synthetic/demo-evidence.txt` text. That declaration is not legal clearance for arbitrary user-supplied text. No third-party paper, article body, guideline, or real oncology data is retrieved or reused.

The UI can register an original fictional evidence item, attach a manually-authored relationship and applicability assessment to a case-specific question, include selected assessments when drafting an investigation, inspect the exact source text/line/hash, and withdraw a fictional item. An explicit `Amends: EVIDENCE-ID@LATEST-VERSION` replacement or withdrawal flags every dependent investigation in every affected synthetic case as stale, while retaining older source versions for audit. Assessments for superseded/withdrawn evidence cannot be included in new drafts.

The labels `supports`, `contradicts`, and `applicable` are human-entered **fictional engineering data**, not determinations of evidence quality, clinical benefit, trial eligibility, or clinical relevance. The prototype has no clinician identity verification or legal rights-verification service. Never use real patient records or copyrighted publication text. Run the unit/HTTP tests before reviewing the UI; browser execution requires a separate interactive verification.

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

## Unified case home (Engineering-core composition)

One read-only endpoint composes the existing builders for a single case,
citation-for-citation, with no new facts and no second record:

```text
GET /api/cases/{CASE-ID}/home
```

Implemented in `src/open_intelligence/home.py` (registered in
`__main__.py`); covered by `tests/test_case_home.py`. Sections:

- `cover`: fictional marking, scope, case identity, `generated_from`
  (the exact builder each section came from), `report_position` (the latest
  ledger event id reflected), plus the changes anchor and timeline as-of.
- `mission`, `timeline`, `changes`: the existing builder outputs embedded
  verbatim, with all source-version, source-line, snapshot, and event
  citations preserved.
- `attention`: the mission projection's `next_actions` and
  `material_changes` by reference — the existing workflow queue, not a new one.
- `goals`: reported unavailable. This build has no goals builder and no
  goals table; nothing is substituted or inferred.
- `follow_ups`: owned preparation tasks from the existing option view,
  each with its option citation, owner label, and status.
- `review_state`: direct ledger reads with exact ids and states —
  snapshots, options, model investigations, discovery links, and inventory
  assertions.
- `stage`: the mission workflow status by reference, labeled as
  workflow/review state only. This build performs no clinical staging.
- `limitations`: the honest boundary list, including demo-review limits
  and the default changes anchor.

Unknown cases follow the existing `422 Unknown case` boundary. The
composition performs only reads; the test suite pins that by comparing a
full database dump before and after composing.

Patient goals, clinical staging, and the draft-slice builders (journey
stages, attention panel, follow-through, review queue) do not exist in this
tree; the home endpoint reports that absence instead of re-deriving their
content from ledger rows.

## Update/revocation propagation map (Engineering-core audit)

Every trigger below reaches its dependent rows and the per-case event queue
in the same write transaction. Amendments supersede; nothing is deleted.
Covered by `tests/test_propagation.py` for the three audit fixes and by the
pre-existing suites for the established paths.

1. Source amendment (`import_report` with `Amends`, case-scoped):
   old version → `superseded`, new version `current`; snapshots citing the
   superseded version → `stale` and their questions reopen; the case's model
   investigations → stale on **any** amendment (audit fix A: previously only
   when a snapshot cited the superseded version, contradicting the documented
   contract); questions of newly stale investigations reopen only when no
   fresh snapshot or investigation remains; dependent options in this case →
   `needs_review` (transitive over option→option edges); inventory assertions
   anchored to the superseded version → `stale` (anchor-exact, not transitive
   to derivatives by OI-020 design). Events: `source_imported` (now carrying
   `invalidated_investigations` alongside the existing lists) and
   `option_review_reopened` when options are affected. First imports,
   duplicates, and quarantines emit no fan-out; other cases are untouched.

2. Evidence amendment / withdrawal (`import_synthetic_evidence` with
   `Amends`, `withdraw_synthetic_evidence`; global, because evidence
   versions are shared): old version → `superseded` / `withdrawn` with an
   `evidence_changes` row; snapshots citing an assessment of that exact
   version → `stale` in every affected case and their questions reopen;
   model investigations whose stored claims cite an assessment of that exact
   version → stale (audit fix B: citation-exact, never whole-case, since a
   coarse global marking would stale unrelated cases; unparseable claims
   payloads are skipped, never blindly invalidated and never fatal);
   questions of newly stale investigations reopen only when no fresh support
   remains; dependent options → `needs_review`. Events: `evidence_invalidated`
   per affected case — including investigation-only cases that previously got
   no event — now carrying `invalidated_investigations`, plus per-case
   `option_review_reopened`. New assessments, drafts, and option dependencies
   on non-current versions are refused.

3. Rights revocation / correction (`revoke_rights_source`,
   `correct_rights_source`; global to citing cases): row → `revoked`, or
   `superseded` with a new active row; snapshots citing links on that row →
   `stale` and their questions reopen; discovery links bound to that row
   (item binding or cited broker link) → `invalid` with cause `revocation`
   or `correction`, rows preserved. Events: `broker_invalidated`,
   `discovery_invalidated`, and `rights_events` rows. New imports, links,
   and drafts on non-active rows are refused.

4. Broker-link re-review (`review_broker_link`, case-scoped): the link's
   relation/applicability/rationale is updated; snapshots citing it → `stale`
   and their questions reopen; valid discovery links citing it are flagged
   for re-review through the `broker_invalidated` event and the return value
   (audit fix C: `affected_discovery_links`). Those link rows stay `valid`:
   a re-review changes interpretation, not permission, and the stored
   invalidation causes remain exactly `revocation` and `correction`.
   Re-review on a non-active rights row is refused.

5. Option assembly and review (case-scoped): adding a dependency, task, or
   threat, changing a task status, or recording a terminal review action
   reopens reviewed downstream options to `needs_review` (transitive).
   Approval and reconfirmation re-check current dependencies inside the
   write transaction; contradicted proposals are never approved; terminal
   options are preserved, never edited in place.

6. Terminal writes (no fan-out by design): `acknowledge_demo_review`
   (draft → `reviewed_in_demo`, question → `addressed`), `save_investigation`
   (stored pending, question → `addressed`), and pure creations
   (`add_question`, `create_snapshot`, assessments, discovery/broker links,
   rights registration, option creation) emit only their creation events.

7. Adapter deliveries (`patient_access`, OI-017): `deliver` validates the
   envelope and calls `import_report`, inheriting path 1 plus adapter
   receipt events; `revoke` blocks future deliveries only and preserves
   history.

Audited non-edges (no citation edge exists, so no propagation is missing):
source amendments do not reach discovery or broker links (those cite rights
and questions, not sources); evidence changes do not reach inventory
assertions (anchored to source versions only); rights changes do not reach
model investigations (those cite synthetic assessments only, never broker
links); options never restale snapshots (invalidation flows downstream
only).

Known partial path: question reopening on investigation staleness applies
to newly staled rows; investigations already stale before this change are
not backfilled, and their questions keep whatever state they had.
