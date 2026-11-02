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
- `Finding: key|state|quotation` lines; key `KEY` regex, state in
  `reported|negative|pending|indeterminate|not-reported|not-assessed|conflicting`,
  quotation ≤1200 chars, keys unique per report.
- `parse_report(raw: bytes) -> ParsedReport` raises `InvalidInput` on any violation.
- `import_report(case_id, raw)`:
  - Wrong `Patient != case_id` → quarantined (`patient_mismatch`), idempotent on
    `(target_case, sha256)`; no assertions created.
  - Same-bytes `(case, document, sha256)` → `duplicate`, no events.
  - Changed text requires `Amends: DOCUMENT@LATEST-VERSION`; first version must not
    carry `Amends`; amendment cannot change `Type`, `Event-Date`, or `Specimen`
    (a different specimen/assay is a distinct document, never a silent correction).
  - On amendment: previous `source_versions.state` → `superseded`, new row `current`;
    dependent non-stale snapshots → `stale`; their questions → `open`;
    all current-case `investigations.stale` → 1; dependent options reopened via
    `_invalidate_options`; anchor-exact inventory assertions on the superseded
    version → `stale`. One transaction emits `source_imported` with
    `invalidated_snapshots`, `invalidated_options`, `invalidated_inventory_assertions`.

### 1.2 Questions and snapshots — OI-007

- `questions.state ∈ {open, addressed}`. `add_question(case_id, 5–500 chars)`.
- `snapshots.state ∈ {draft, reviewed_in_demo, stale}`.
- `create_snapshot(case_id, question_id, summary 10–3000 chars, source_ids[1..50 unique current], evidence_assessment_ids?, broker_link_ids?)`:
  sources must be `current` and in-case; assessments must be current, in-case,
  in-question, `original-synthetic`; broker links must be active-rights, in-case,
  in-question, and not (`supports` + `not_applicable`). Emits `draft_created`.
- `acknowledge_demo_review(case_id, snapshot_id, reviewer_label)`: only `draft` →
  `reviewed_in_demo`; sets question → `addressed`. Demo acknowledgment only,
  never clinical sign-off.
- `export_markdown(case_id, snapshot_id)`: shows snapshot state, full source
  versions, fictional evidence assessments, and explicit limitations.

### 1.3 Synthetic evidence — OI-008

- Format `OI-SYNTHETIC-EVIDENCE/1`, ≤32 KiB, fields `Evidence/Title/Issued-At/
  Rights/Statement/Amends`; `Rights` must equal `original-synthetic`.
- `evidence_versions.state ∈ {current, superseded, withdrawn}`; `import_synthetic_evidence`
  requires `Amends: EVIDENCE@LATEST` for changed bytes; amendment supersedes the
  previous row and invalidates dependent snapshots **across all cases**
  (evidence is shared) plus dependent options; emits `evidence_invalidated`.
- `withdraw_synthetic_evidence(id, reason 10–600 chars)`: current → `withdrawn`,
  same fan-out with reason `withdrawal`. Withdrawn evidence cannot be silently replaced.
- `assess_synthetic_evidence(case, question, evidence_version, relation, applicability, rationale 15–800)`:
  relation in `supports|contradicts|context|unknown`, applicability in
  `applicable|limited|not_applicable|unknown`; `supports + not_applicable` rejected.
  Human-authored only. `snapshot_evidence` binds assessments to snapshots.

### 1.4 Rights-gated broker — rights boundary

- `rights_sources.state ∈ {active, revoked, superseded}`; permissions map
  `item × use → allowed|denied|unknown`, unknown fails closed.
- `create_broker_link`: stores excerpt only in `full` mode, title only with
  metadata/full permission, else citation identity alone. Mode in
  `full|metadata_only|citation_only`.
- `revoke_rights_source` / `correct_rights_source` invalidate dependent snapshots
  (→ `stale`, questions → `open`) and dependent discovery links (→ `invalid`
  with cause `revocation|correction`). History retained; content redacted on read
  when rights are not active.
- Discovery items (`trial|literature`, `original-synthetic` only) bind immutably
  to at most one rights row at import; `link_discovery` fails closed on
  non-active rights, wrong case/question, or revoked broker links.

### 1.5 Bounded model investigation — OI-011 slice (already narrow)

- `investigation.py` is the **only** model-calling module. No caller free text:
  `build_prompt(template_id, question, assertions≤100, assessments≤50)` with
  fixed templates `evidence-summary|timeline-gaps|evidence-applicability`.
- `validate_output`: claims need non-empty text, `uncertainty ∈ low|moderate|high`,
  `support ∈ supports|contradicts|context`, ≥1 citation resolving to a current
  in-case source version or in-question assessment, and must pass the language
  guard (recommend/prescribe/dose/best-treatment/should-treat patterns).
  Failures are **dropped with reason**, never repaired. Stored kind is always
  `hypothesis`, review state always `pending`.
- `save_investigation` persists `status ∈ completed|abstained|blocked_by_policy|failed`,
  `mode ∈ live|replay`; sets question → `addressed`; emits `investigation_created`.
  Amendments mark case investigations `stale=1` (see §1.1).
- Key from `META_API_KEY` env only, server-side, never logged/stored/sent to browser.
  Replay mode uses recorded human-authored fixtures labeled `mode=replay`.

### 1.6 Options projection — OI-021 (derived, not canonical)

- `options` are proposals tied to a snapshot; epistemic `supported|contradicted|
  unsupported|unknown`, operational `proposed|reviewed|held|rejected|withdrawn|expired`,
  `review_state ∈ current|needs_review`. Clinical-language guard at proposal time.
- Dependencies on source / evidence_assessment / preparation_task / option;
  sourced deadline dates only on source/evidence edges with 10–300-char anchor.
  Transitive dependent-only invalidation; endorsement re-checks currency inside
  the write transaction; contradicted options cannot be approved/reconfirmed.
- `option_view` is explicitly **current-state-with-history, not as-known-at replay**
  (`historical_replay_supported: false`).

### 1.7 Biological assets — OI-020 code label (not GitHub issue #20)

- Immutable `biological_assets` rows anchored to one exact current source version;
  derivatives require same-case same-episode parent of allowed kind; no update path.
  Liveness only in `biological_inventory_assertions` (`current|stale`, anchor-exact).
  Staleness does **not** propagate transitively to derivatives by design.

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
  into `validation/iv01/ADJUDICATION.md` and `validation/iv01/BASELINE.md`.
- PR #26, #27, #29: UI review candidates (predecessors + consolidated candidate).
- PR #37: incremental UI glance iteration review artifact.
- PR #38: Patient Mission slice; `IMPLEMENTATION_STATUS.md` says it must remain
  unmerged until review completes.
- PR #1: source-ledger slice; must remain unmerged until tracked review resolves.
- Issues #22 (IV-01–03 packet scope) and #23 (independence/roles source) cited by
  `validation/iv04/*`; this task is GitHub **issue #20** (experimental-loop
  research), distinct from backlog-code label **OI-020** (biological assets).

**Gate-1 rule applied:** no schema change is designed here. Gate-3 draft types live
only in isolated research/test code on this branch and are mapped onto the states
above; `SCHEMA` in `store.py` is untouched. A separate scoped decision is required
before any of this touches core.
