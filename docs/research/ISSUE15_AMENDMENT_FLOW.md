# Issue #15 — Amendment → selective invalidation → regeneration → human review flow

**Status:** DRAFT FLOW / EVALUATE; the existing-machinery steps are implemented and cited; the candidate/regeneration steps are proposed.
**Date:** 2026-11-02
**Tracker:** [Issue #15](https://github.com/OpenxIntelligence/open-intelligence/issues/15)
**Parent:** [HL7 crosswalk](ISSUE15_HL7_CROSSWALK.md); builds on the OI-009 second-time-point contract.
**Boundary:** additive only. Every step below names its existing owner or marks itself PROPOSED. Nothing here replaces canonical state, evidence, provenance, consent, or human authority. All data fictional, labeled everywhere.

## 1. Existing machinery this flow stands on (all IN-REPO-VERIFIED)

| Step capability | Owner |
|---|---|
| Durable ingest with versioning, hashing, duplicate detection, wrong-subject quarantine | `CaseStore.import_report` ([store.py](../../src/open_intelligence/store.py)) |
| Amendment supersession (prior version → `superseded`, never rewritten) | `import_report`, same transaction |
| Anchor-exact snapshot invalidation + question reopening | `import_report` (`snapshot_sources` join on the superseded id) |
| Investigation staleness on amendment | `import_report` (`investigations.stale=1`) |
| Option and inventory-assertion anchor-exact invalidation | `_invalidate_options`, `biological_inventory_assertions` update |
| Single-transaction atomicity (ingest + all invalidation + event) | `import_report` (`BEGIN IMMEDIATE`) |
| Change projection since last review | `changes_since_review` ([changes.py](../../src/open_intelligence/changes.py)) |
| Canonical timeline with history-only superseded versions | `case_timeline` ([timeline.py](../../src/open_intelligence/timeline.py)) |
| Scoped human review of drafts | `acknowledge_demo_review` + `review_events`; option path via `review_option` |

## 2. The flow, end to end

Numbered steps. Each step names EXISTING machinery or PROPOSED addition. The running example uses fictional case `CASE-FLOW` and document `PATH-FLOW`, versions 1 → 2.

### Step 1 — Amendment arrives (EXISTING)

The caller imports new bytes carrying `Amends: PATH-FLOW@1` via `import_report`. The contract enforces: same document, latest version referenced, unchanged report type / event date / specimen (else `InvalidInput` — a genuinely new specimen or assay is a distinct document, never a silent correction).

### Step 2 — Supersession + selective invalidation, one transaction (EXISTING)

`import_report` marks version 1 `superseded`, inserts version 2 as `current` with `supersedes_id` pointing at version 1, writes the new assertions, and — in the same transaction — stales exactly the dependents of version 1:

- snapshots citing version 1 → `stale`, their questions reopened;
- case investigations → `stale=1` (they cited the superseded facts);
- options citing version 1 or a now-stale snapshot → `needs_review` with an `option_review_reopened` event;
- inventory assertions anchored on version 1 → `stale`.

Dependents of other versions, other documents, and other cases are untouched. Duplicates emit no events. One `source_imported` event records every invalidated id.

### Step 3 — Candidate invalidation (PROPOSED, same anchor-exact rule)

Derived candidates and run receipts follow the identical rule, which is why the receipt carries `input_refs` + `input_fingerprint` and each candidate carries one exact `source_ref`:

- every [DerivedTimelineCandidate](ISSUE15_DERIVED_TIMELINE_CANDIDATE.md) whose `source_ref.source_version_id` is the superseded version → `validity: stale`;
- every [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) whose `input_refs` include the superseded version → `validity: stale`;
- candidates and receipts anchored elsewhere stay `current`.

Staleness never deletes. No silent promotion, no auto-repair.

### Step 4 — Reviewable change surfacing (EXISTING + PROPOSED display)

EXISTING: `changes_since_review` reports the new source version, the amended document, the staled drafts, and the finding-key diff (added/removed/reported-state changes) — ledger facts, no interpretation. `case_timeline` shows version 2 in `entries` and version 1 in `history` with its `superseded_by_source_id` pointer.

PROPOSED: the same surfacing lists staled candidates/receipts beside the staled snapshots, in the visually separate "proposed" region the candidate spec requires, each with its epistemic level, anchor, and fictional label.

### Step 5 — Regeneration as a new run (PROPOSED, via specified contracts)

A caller — human-initiated or a deterministic worker, never the model itself deciding — issues a new run request over the now-current inputs:

1. The [ModelCapabilityRegistry](ISSUE15_MODEL_CAPABILITY_REGISTRY.md) gate re-evaluates (capability still `cleared`, terms still known, rights still active). Revocation since the last run blocks regeneration with a denial receipt instead of candidates.
2. The run executes (mock harness today; a cleared model path only after separate approval) and emits a new [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) with a new `run_id` and fresh `input_fingerprint`.
3. New [DerivedTimelineCandidate](ISSUE15_DERIVED_TIMELINE_CANDIDATE.md) records are created at `extracted_candidate` (or, for a qualified run, higher) level, `review_state: pending`, citing only current versions.
4. The stale predecessors remain inspectable; the new receipt does not overwrite them.

Idempotence: re-issuing the identical request yields the identical `run_id` (content hash), so retries and duplicate deliveries are detectable and produce no duplicate candidates.

### Step 6 — Scoped human review (EXISTING path, PROPOSED candidate actions)

The reviewer works from the change surfacing in Step 4. EXISTING actions: acknowledge corrected drafts (`acknowledge_demo_review`), re-decide options (`review_option`), record evidence assessments. PROPOSED candidate actions, reusing the same scoped-review pattern: accept a candidate (human action sets the accepted level, up to `clinician_reviewed`), correct it (new human-authored content citing the source), or reject it (recorded with reason). Between receipt and review, exports show version, date, and stale/review-pending status; no export presents a stale conclusion as current.

### Step 7 — New reviewed snapshot (EXISTING semantics)

Only the scoped review in Step 6 creates the new reviewed state. Previous versions — sources, snapshots, candidates, receipts — remain recoverable with supersession pointers. Previously downloaded files cannot be recalled or rewritten; they keep their recorded version and date.

## 3. Walk-through (fictional)

T0: `CASE-FLOW` holds `PATH-FLOW@1` (current). A mock run over version 1 produced receipt `R1` and candidates `C1`, `C2` (`pending`, reviewer untouched). A snapshot `S1` citing version 1 was demo-acknowledged.

T1: amended bytes `PATH-FLOW@2` arrive (`Amends: PATH-FLOW@1`, same event date/specimen, one finding's reported state changed from `pending` to `reported`).

- `import_report` supersedes version 1, inserts version 2, stales `S1`, reopens its question, flags case investigations stale. `R1`, `C1`, `C2` stale by the Step-3 rule (PROPOSED step; the ledger steps are EXISTING).
- `changes_since_review` shows: new version 2, `S1` stale, finding-key diff (`marker-x`: `pending` → `reported` as ledger comparison, not interpretation). Timeline `entries` show version 2; `history` shows version 1.
- A new run over version 2 yields receipt `R2` and candidates `C3`, `C4` (`pending`). `R1`/`C1`/`C2` remain visible as stale history.
- The reviewer inspects the diff, accepts `C3`, corrects `C4`, acknowledges the replacement draft. Only then is there a new reviewed snapshot. `S1`, `R1`, `C1`, `C2` stay recoverable.

## 4. Failure modes handled

| Failure | Behavior | Owner |
|---|---|---|
| Amendment references a non-latest version | `InvalidInput`; nothing written | EXISTING (`import_report`) |
| Amendment changes event date / specimen / type | `InvalidInput`; caller must author a distinct document | EXISTING |
| Duplicate delivery of the same bytes | `duplicate` result; no events, no new candidates | EXISTING + Step-5 idempotence |
| Out-of-order arrival | Ordering stays by occurred time (`case_timeline`); no spurious invalidation | EXISTING |
| Rights revoked between T0 and regeneration | Regeneration blocked; inspectable denial receipt; stale artifacts stay stale-pending, never auto-refreshed | PROPOSED gate (Step 5.1); revocation primitive EXISTING for broker/discovery scope |
| Run produces output without valid anchors | Output rejected at creation; abstention or error recorded | PROPOSED (candidate `source_ref` rule); investigation-path precedent EXISTING (`validate_output`) |
| Reviewer disagrees with a candidate | Reject/correct with recorded reason; disagreement preserved | PROPOSED actions on the EXISTING scoped-review pattern |

## 5. Open checks

- [ ] Step 3 and Step 5 need a separately scoped persistence proposal (rows vs `events.details` projections). This flow requires no decision here.
- [ ] Candidate review actions (Step 6) need UX review to confirm they cannot be mistaken for canonical-timeline edits.
- [ ] Cross-case isolation for candidate stores must be tested with the second-case probe from the [evaluation design](ISSUE15_EVALUATION_DESIGN.md) §3.
