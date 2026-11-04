# Issue #20 — Gate 1: exact current-implementation contract map

**Status:** research draft only, branch work, **not** a schema change, **not** merged into core.
All data referenced here is fictional synthetic demo data. No real patient data.
No new dependency, graph database, agent runtime, or infrastructure introduced.

Source files read at contract level (function/table/state names only, no behavior change):
`src/open_intelligence/store.py`, `src/open_intelligence/investigation.py`,
plus `AGENTS.md`, `README.md`, `docs/FIRST_PRINCIPLES_PLAN.md`,
`docs/EXECUTION_BACKLOG.csv`, `docs/research/EXPERIMENTAL_LOOP_EXTENSION_2026-10-31.md`.

## 1. Core ledger contracts (observed, not modified)

### 1.1 Synthetic report ingest — OI-006

- Format: `OI-SYNTHETIC-REPORT/1`, UTF-8, ≤64 KiB, no NUL/CR. Header fields:
  `Patient`, `Document`, `Type`, `Event-Date`, `Issued-At`, optional `Specimen`,
  optional `Amends: DOCUMENT-ID@VERSION`.
- `Finding: key|state|quotation` lines; key `KEY` regex
  (`[a-z][a-z0-9_-]{0,59}`), state in
  `reported|negative|pending|indeterminate|not-reported|not-assessed|conflicting`,
  quotation non-empty and ≤1200 chars, keys unique per report.
- `parse_report(raw: bytes) -> ParsedReport` raises `InvalidInput` on any violation.
  Further exact rules (loop cycle 1 addition): `Patient`/`Document`/`Specimen`
  match `ID` (`[A-Z][A-Z0-9-]{1,39}`); `Type ∈ pathology|molecular|imaging|
  laboratory|clinical|other`; dates strict `YYYY-MM-DD`; blank lines skipped;
  unknown/duplicate/empty fields rejected; `Amends` must name the same document.
- `import_report(case_id, raw)`:
  - Wrong `Patient != case_id` → quarantined (`patient_mismatch`), idempotent on
    `(target_case, sha256)`; no assertions created.
  - Adapter rejections use `quarantine_adapter_delivery`, idempotent on
    `(target_case, sha256, reason)`; same `quarantine` table, same
    `source_quarantined` event kind. No assertions in either path.
  - Same-bytes `(case, document, sha256)` → `duplicate`, no events.
  - Changed text requires `Amends: DOCUMENT@LATEST-VERSION`; first version must not
    carry `Amends`; amendment cannot change `Type`, `Event-Date`, or `Specimen`
    (a different specimen/assay is a distinct document, never a silent correction).
  - On amendment: previous `source_versions.state` → `superseded`, new row `current`;
    dependent non-stale snapshots → `stale`; their questions → `open`;
    dependent options reopened via `_invalidate_options` (transitive, this case
    only); anchor-exact inventory assertions on the superseded version → `stale`.
    Case `investigations.stale` → 1 for all rows in the case, but ONLY when at
    least one snapshot was invalidated (no snapshot hit → investigations untouched).
    One transaction emits `source_imported` with `document_id`, `version`,
    `source_id`, `amends_id`, `invalidated_snapshots`, `invalidated_options`,
    `invalidated_inventory_assertions`.

### 1.2 Questions and snapshots — OI-007

- `questions.state ∈ {open, addressed}`. `add_question(case_id, 5–500 chars)`.
- `snapshots.state ∈ {draft, reviewed_in_demo, stale}`.
- `create_snapshot(case_id, question_id, summary 10–3000 chars, source_ids[1..50 unique current], evidence_assessment_ids[0..50 unique]?, broker_link_ids[0..50 unique]?)`:
  sources must be `current` and in-case; assessments must be current, in-case,
  in-question, `original-synthetic`; broker links must be active-rights, in-case,
  in-question, and not (`supports` + `not_applicable`). Emits `draft_created`
  with `snapshot_id`, `question_id`, `evidence_assessment_ids`, `broker_link_ids`.
- `acknowledge_demo_review(case_id, snapshot_id, reviewer_label 2–80 chars)`: only `draft` →
  `reviewed_in_demo`; writes one `review_events` row (`acknowledged_in_demo`);
  sets question → `addressed`. Demo acknowledgment only, never clinical sign-off.
- `export_markdown(case_id, snapshot_id)`: shows snapshot state, full source
  versions with SHA/event/issued, fictional evidence assessments with relation/
  applicability/rationale, and explicit limitations. It does NOT include broker
  links, discovery links, options, or model investigations.

### 1.3 Synthetic evidence — OI-008

- Format `OI-SYNTHETIC-EVIDENCE/1`, ≤32 KiB, fields `Evidence/Title/Issued-At/
  Rights/Statement/Amends`; `Rights` must equal `original-synthetic`.
  Title 4–180 chars; Statement 10–1200 chars.
- `evidence_versions.state ∈ {current, superseded, withdrawn}`; `import_synthetic_evidence`
  requires `Amends: EVIDENCE@LATEST` for changed bytes; same-bytes → `duplicate`
  with no event (returns `invalidated_snapshots: []`). Amendment supersedes the
  previous row, writes one `evidence_changes` row (`amended`, reason text
  `Explicit synthetic source version replacement`), and invalidates dependent
  snapshots **across all cases** (evidence is shared) plus dependent options;
  emits `evidence_invalidated` per affected case with `evidence_version_id`,
  `reason`, `invalidated_snapshots`, and separately `option_review_reopened`
  per option-holding case (loop cycle 1 correction: the options fan-out event
  was previously unmentioned). Investigations (`stale`) are NOT touched by
  evidence invalidation — only source amendments mark them stale (see §1.1).
- `withdraw_synthetic_evidence(id, reason 10–600 chars)`: current → `withdrawn`,
  writes `evidence_changes` (`withdrawn`), same fan-out with reason `withdrawal`.
  Withdrawn evidence cannot be silently replaced (a later import under the same
  key with a non-current predecessor raises).
- `assess_synthetic_evidence(case, question, evidence_version, relation, applicability, rationale 15–800)`:
  relation in `supports|contradicts|context|unknown`, applicability in
  `applicable|limited|not_applicable|unknown`; `supports + not_applicable` rejected.
  Question must be in-case; evidence must be current + `original-synthetic`.
  Human-authored only. `snapshot_evidence` binds assessments to snapshots.

### 1.4 Rights-gated broker — rights boundary

- `rights_sources.state ∈ {active, revoked, superseded}`; permissions map
  `item × use → allowed|denied|unknown` over items
  `metadata|abstract|full_text|figures|terminology|api_output` and uses
  `store|display|redistribute|ml_use`; unknown fails closed. The gate never
  verifies legal truth, only enforces the record.
- `create_broker_link` (rationale 15–800, title ≤180, excerpt 10–1200):
  `full` requires `full_text store+display allowed` (excerpt kept only here);
  a title requires `metadata store allowed` even when full is granted;
  else citation identity alone. Mode in `full|metadata_only|citation_only`.
- `revoke_rights_source` / `correct_rights_source` (reason 10–600) write
  `rights_events`, invalidate dependent snapshots (→ `stale`, questions → `open`,
  `broker_invalidated` per case) and dependent discovery links (→ `invalid`
  with cause `revocation|correction`, `discovery_invalidated` per case).
  History retained; title/excerpt redacted on read when rights are not active
  (`content_redacted: true`). `review_broker_link` (same rationale bounds)
  re-reviews meaning and also invalidates citing drafts (`broker_invalidated`,
  reason `review`); revoked sources cannot be re-blessed. Rights
  revocation/correction, like evidence invalidation, does NOT touch
  investigations (`stale`) — that flag is source-amendment-only (loop cycle 1).
- Discovery items (`trial|literature`, `original-synthetic` only) bind immutably
  to at most one rights row at import (unlinked allowed, never assumed permitted;
  rebinding or changed-bytes re-import rejected); `link_discovery` (rationale
  15–800, ≤50 unique broker links, UNIQUE per case/question/discovery) fails
  closed on non-active rights, wrong case/question, revoked broker links, or
  guarded clinical-claim terms in the rationale. The guarded terms (loop cycle 1
  addition, from `discovery.py` `BANNED_TERMS`, substring match on title,
  summary, and link rationale) are exactly: `eligible`, `eligibility`,
  `effective`, `efficacy`, `recommended`, `proven`, `benefit`.

### 1.5 Bounded model investigation — OI-011 slice (already narrow)

- `investigation.py` is the **only** model-calling module. No caller free text:
  `build_prompt(template_id, question, assertions≤100, assessments≤50)` with
  fixed templates `evidence-summary|timeline-gaps|evidence-applicability`.
- `validate_output`: claims need non-empty text, `uncertainty ∈ low|moderate|high`,
  `support ∈ supports|contradicts|context`, ≥1 citation resolving to a current
  in-case source version id (from `investigation_facts`, current assertions only)
  or in-question current assessment id, and must pass the language guard
  (`recommend*`, `prescri*`, `dos(e|age)`, `best (treatment|therapy|option|drug)`,
  `should (receive|be treated|take|undergo|start|stop)`, `you should`).
  Failures are **dropped with reason** (`missing_text|invalid_uncertainty|
  invalid_support|language_guard|missing_citations|unresolved_citation`), never
  repaired. Abstentions carry `reason ∈ no_evidence|insufficient_evidence|
  out_of_scope|conflicting_evidence`; empty output abstains with
  `insufficient_evidence`. Stored kind is always `hypothesis`, review state
  always `pending` (added in getters, not stored).
- `save_investigation` persists `status ∈ completed|abstained|blocked_by_policy|failed`,
  `mode ∈ live|replay`; `stale` defaults 0; sets question → `addressed`; emits
  `investigation_created` with `investigation_id`, `template`, `status`, `mode`.
  Amendments mark case investigations `stale=1` only when ≥1 snapshot
  invalidates (see §1.1). Status provenance (loop cycle 1 correction):
  `validate_output` yields only `completed` (≥1 kept claim) or `abstained`;
  the HTTP path in `__main__.py` converts `InvestigationError` into a 502/503
  response and never saves, so `blocked_by_policy`/`failed` are schema-allowed
  but currently produced by no code path.
- Key from `META_API_KEY` env only, server-side, never logged/stored/sent to browser.
  Live call: `POST https://api.meta.ai/v1/messages`, model `muse-spark-1.3`,
  `max_tokens 4096`, timeout 90s; failures raise with no partial claim.
  `investigation.py` holds the only model-call code (`urllib.request.urlopen`
  appears nowhere else in `src/`; `__main__.py` uses only `urllib.parse`).
  Replay mode (`__main__.py`): loads recorded human-authored
  `examples/synthetic/demo-investigation.json`, substitutes `FIRST_SOURCE` /
  `FIRST_ASSESSMENT` placeholders with the first current in-case ids, then
  runs the same `validate_output`; labeled `mode=replay`,
  `model=recorded-replay`. Placeholders left unsubstituted (no valid ids)
  drop as `unresolved_citation`.

### 1.6 Options projection — OI-021 (derived, not canonical)

- `options` are proposals tied to a snapshot (label 1–120, description 10–1000);
  epistemic `supported|contradicted|unsupported|unknown`, operational
  `proposed|reviewed|held|rejected|withdrawn|expired`, `review_state ∈
  current|needs_review`. Narrow clinical-language guard on option
  label/description, preparation-task label, threat description, review scope
  (10–300 chars), and sourced-date anchors (loop cycle 1 correction: task and
  threat fields were previously unmentioned): `recommend*|prescri*|eligible`,
  `should (receive|undergo|get|start)`, `must (receive|undergo)`,
  `order (this|the) (treatment|therapy|procedure)`, `start treatment`;
  not a clinical classifier.
- Dependencies on source / evidence_assessment / preparation_task / option
  (exactly one target, lead 0–3650d, cycle-checked); sourced deadline dates only
  on source/evidence edges with 10–300-char anchor. Preparation tasks
  (`not_started|in_progress|done|blocked|cancelled`, human owner) and
  optionality threats (`expiring_window|dependency_loss|evidence_withdrawal|other`,
  sourced/unknown basis) are human-owned. Transitive dependent-only invalidation;
  endorsement re-checks currency inside the write transaction; contradicted
  options (direct flag or any `contradicts` assessment edge) cannot be
  approved/reconfirmed and display as `held` when proposed/reviewed.
  Reconfirmation requires a replacement current snapshot; terminal
  (`rejected|withdrawn|expired`) options need a new proposal.
- `option_view` is explicitly **current-state-with-history, not as-known-at replay**
  (`historical_replay_supported: false`, `projection_mode:
  current_state_with_review_history`). Potential discussion deadlines are
  conditional planning arithmetic, never clinical deadlines.

### 1.7 Biological assets — OI-020 code label (not GitHub issue #20)

- Immutable `biological_assets` rows anchored to one exact current in-case source
  version; kinds `ffpe_block|fresh_frozen_aliquot|slide|digital_wsi|
  genomics_data_pointer`; derivatives (`slide←ffpe_block`, `digital_wsi←slide`,
  `genomics_data_pointer←ffpe_block|fresh_frozen_aliquot`) require a same-case
  same-episode parent; no update path. Pointer labels (digital only, 1–200 chars,
  never a URL/path) carry no bytes. Liveness only in
  `biological_inventory_assertions` (`current|stale`, anchor-exact) with five
  `known|unknown` fields (location/quantity/custody/consent/rights); consent/rights
  values are descriptive only and gate nothing. Staleness does **not** propagate
  transitively to derivatives by design.

## 2. Open-PR / branch-head position (what could be verified without git/shell)

Hard limit: git, shell, and network verification are unavailable in this session,
so open/merged status below is **as stated in repo text**, not freshly verified.
No branch head could be inspected; no PR could be opened, merged, or pushed.

PR/issue references found in repo text:

- PR #24 (IV-01–03 synthetic evaluation packet): described in `README.md` as an
  **unmerged draft**, not independent clinical validation.
- PR #18: proposed E0–E6/G0–G3/GX collaboration playbook; proposal status retained
  per `validation/iv04/README.md`.
- PR #32: IV-02 adjudication + IV-03 baseline procedures; described as **merged**
  into `validation/iv01/ADJUDICATION.md` and `validation/iv01/BASELINE.md`
  per `validation/iv04/README.md`.
- PR #38: Patient Mission slice; `IMPLEMENTATION_STATUS.md` says it must remain
  unmerged until review completes.
- PR #1: source-ledger slice; must remain unmerged until tracked review resolves
  per `IMPLEMENTATION_STATUS.md`.
- Issues #22 (IV-01–03 packet scope) and #23 (independence/roles source) cited by
  `validation/iv04/*`; this task is GitHub **issue #20** (experimental-loop
  research), distinct from backlog-code label **OI-020** (biological assets).
- Draft PR #61 (this issue-20 branch `loop/issue-20-falsify`): research-complementary
  drafts only, per the task boundary; no core change, no merge.
- UI review candidates PR #26, #27, #29, #37 (loop cycle 1 correction: the
  Pass-2 claim that these were "NOT located" was wrong — they are cited in
  readable repo text). Per `docs/UI_CHANGE_REVIEW_SPEC.md`: #26 and #27 are
  predecessor UI candidates, consolidated into review candidate #29. Per
  `docs/UI_GLANCE_ITERATION.md`: build on integrated PR #29; do not reopen
  superseded #26/#27 tracks; PR #37 is a draft stacked on #29 and neither is
  merged. Per `docs/superpowers/plans/2026-10-31-source-line-delta.md`: PR #29
  stays draft and unmerged. None is merged; none affects the issue-20 scope.

**Gate-1 rule applied:** no schema change is designed here. Gate-3 draft types live
only in isolated research/test code on this branch and are mapped onto the states
above; `SCHEMA` in `store.py` is untouched. A separate scoped decision is required
before any of this touches core.
