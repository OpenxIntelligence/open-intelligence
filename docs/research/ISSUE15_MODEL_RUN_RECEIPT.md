# Issue #15 — ModelRunReceipt contract (specification)

**Status:** PROPOSED SPEC / EVALUATE; not implemented, not adopted, not clinical validation.
**Date:** 2026-11-02
**Tracker:** [Issue #15](https://github.com/OpenxIntelligence/open-intelligence/issues/15)
**Parent:** [HL7 crosswalk](ISSUE15_HL7_CROSSWALK.md) (gaps G-1, G-3, G-6)
**Boundary:** extends the existing `investigations` / `events` machinery; never duplicates canonical patient state, evidence, provenance, consent, or human authority. All data fictional, labeled everywhere. No Nano dependency, no live model integration, no clinical recommendations.

## 1. Purpose

Record, for any specialist-model (or deterministic-tool) run, everything a reviewer needs to answer: *what ran, on exactly which inputs, under which policy decision, producing exactly which outputs, and what review state those outputs hold.* This closes crosswalk gaps G-3 (no transformation receipt) and G-6 (run receipts lack version/inputs/hash/egress fields), and carries the optional per-input purpose/class fields of G-1.

## 2. What already exists (extended, not replaced)

- `investigations` rows: `template`, `status`, `mode`, `model`, claims/abstentions/dropped JSON, `stale` flag ([store.py](../../src/open_intelligence/store.py), `save_investigation`).
- `events` ledger rows, including the `ADAPTER_EVENT_KINDS` family written by `record_adapter_event`.
- Fail-closed rights evaluation in [rights.py](../../src/open_intelligence/rights.py) (`permitted`, `excerpt_mode`).

A ModelRunReceipt is a *projection over and extension of* these rows. Where the existing schema can express a field, it is reused verbatim. New persistence is introduced only for fields with no existing home, and only after a concrete missing capability is demonstrated (per the addendum §4 rule).

## 3. Contract

### 3.1 Identity and scope

| Field | Type | Meaning | Existing home, if any |
|---|---|---|---|
| `run_id` | string | Deterministic fingerprint of the run request (canonical JSON of capability ref + input refs + config + task version, sha256). Identical requests yield identical ids. | New (receipt field) |
| `case_scope` | string | Fictional case id the run is scoped to. | `investigations.case_id` |
| `investigation_id` | integer or null | Existing investigation row this receipt extends, when one exists. | `investigations.id` |
| `task_type` | enum | One of `chronology_extraction`, `contradiction_detection`, `missingness_detection`, `context_preparation`. Closed set; anything else is rejected. | New (receipt field) |
| `purpose` | string | Human-authored, reviewable statement of why the run was requested (5–500 chars). | New (receipt field) |
| `task_interface_version` | string | Version of the task contract the run conforms to (e.g. `issue15-task/1`). | New (receipt field) |

### 3.2 Model and capability reference

| Field | Type | Meaning | Existing home, if any |
|---|---|---|---|
| `model_provider` | string | Provider identity as declared in the capability record, or `local-deterministic` / `local-mock`. | Partially `investigations.model` (name only; no version) |
| `model_ref` | string | Immutable model/version/build reference (e.g. `vendor/model@sha-or-version`). `unknown` is permitted as a value and forces `egress_mode=blocked` (fail closed). | New (receipt field) |
| `capability_ref` | string | Pointer to the [ModelCapabilityRegistry](ISSUE15_MODEL_CAPABILITY_REGISTRY.md) record authorizing this task. | New (receipt field) |
| `runtime_location` | enum | `local_only` or `authorized_remote`. | New (receipt field) |
| `deterministic_config` | object or null | Seed, temperature-equivalent, and tool versions when the run is reproducible; null with `reproducible: false` otherwise. | New (receipt field) |

### 3.3 Inputs (references only)

| Field | Type | Meaning | Existing home, if any |
|---|---|---|---|
| `input_refs` | list | One entry per input: `source_version_id`, `document_id`, `version`, `sha256`, plus field-level scope (which finding keys were in scope). References only — no payload bytes are copied into the receipt. | `assertions`/`source_versions` (referenced, not duplicated) |
| `input_fingerprint` | string | sha256 over the canonical serialization of `input_refs` + preprocessing version. Stale-output detection compares this, never wall-clock time. | New (receipt field) |
| `preprocessing_version` | string | Exact normalization/extraction preprocessing version applied before the run. | New (receipt field) |
| `purpose_class` | string (optional) | Per-run usage purpose label (G-1). | New (receipt field) |
| `privacy_class` | string (optional) | Per-run data class label (G-1). For issue-#15 work this is always fictional synthetic data. | New (receipt field) |

### 3.4 Policy decision

| Field | Type | Meaning | Existing home, if any |
|---|---|---|---|
| `egress_mode` | enum | `local_only`, `authorized_remote`, or `blocked`. Decided before any model contact. | New (receipt field) |
| `policy_decision` | object | The evaluated rights check: capability permissions snapshot, per-item/use outcomes, revocation/supersession flags, deciding record ids, and the resulting allow/deny with reason. Denials are inspectable receipts, not silent drops. | Evaluated by `rights.permitted`; recorded on the receipt |
| `token_compute_cost` | object or null | Tokens, compute, latency, cost when measurable; null when not. | New (receipt field) |

### 3.5 Outputs and review state

| Field | Type | Meaning | Existing home, if any |
|---|---|---|---|
| `output_hash` | string | sha256 of the canonical output bytes. | New (receipt field) |
| `parse_result` | enum | `parsed`, `parse_failed`, or `not_applicable`. | New (receipt field) |
| `errors` | list | Machine-readable run errors. | `investigations.dropped_json` (partial; extended) |
| `abstentions` | list | Valid abstentions with reasons from the closed reason set. | `investigations.abstentions_json` |
| `validity` | enum | `current` or `stale`. Set to `stale` by the same amendment machinery that stales investigations (see the [amendment flow](ISSUE15_AMENDMENT_FLOW.md)). | `investigations.stale` |
| `review_state` | enum | Always `pending` at creation. Only a scoped human review action transitions it. Model output, confidence scores, and JSON-syntax validity never transition it. | `get_investigation` convention (`pending`) |
| `derived_artifacts` | list | Pointers to [DerivedTimelineCandidate](ISSUE15_DERIVED_TIMELINE_CANDIDATE.md) records produced by this run. | New (receipt field) |

### 3.6 Universal labels

Every receipt carries `synthetic: true` and the fictional-data disclaimer: "Fictional synthetic demonstration data only. This receipt describes a proposed model run, not a clinical determination."

## 4. Invariants

1. **References, not copies.** A receipt never embeds source bytes, quotes, or patient-like fields. Payload minimization is structural: the receipt schema has no field that can hold them.
2. **No PHI egress by construction.** The mock implementation performs no I/O at all (pure functions, no network imports). A future live implementation must log `egress_mode` and the policy decision before contact, and `blocked` runs produce no candidates.
3. **Fail closed.** Unknown model ref, unknown capability, unknown or denied permission, revoked/superseded rights record, or unlisted task type yields a `blocked` receipt with an inspectable reason — never candidates.
4. **No self-authorization.** Nothing the run produces can set `review_state` to anything but `pending`. Promotion requires the existing scoped human review path.
5. **Deterministic identity.** `run_id` and `input_fingerprint` are content hashes, so duplicate requests are detectable and replays are comparable.
6. **Staleness is inherited.** Amendment of any input version stales the receipt and its derived artifacts through the existing invalidation machinery; the receipt row itself is preserved as history.

## 5. Worked shape (illustrative, fictional)

```json
{
  "run_id": "sha256:<hex of canonical request>",
  "case_scope": "CASE-FIXTURE-A",
  "investigation_id": null,
  "task_type": "chronology_extraction",
  "purpose": "Fictional demo: order two synthetic reports by occurred date.",
  "task_interface_version": "issue15-task/1",
  "model_provider": "local-mock",
  "model_ref": "mock-specialist/1",
  "capability_ref": "mock-chronology/1",
  "runtime_location": "local_only",
  "deterministic_config": {"reproducible": true, "seed": "n/a-deterministic-rules"},
  "input_refs": [
    {"source_version_id": 3, "document_id": "PATH-FIXA", "version": 1,
     "sha256": "<hex>", "finding_scope": ["marker-b"]}
  ],
  "input_fingerprint": "sha256:<hex>",
  "preprocessing_version": "mock-preprocess/1",
  "egress_mode": "local_only",
  "policy_decision": {"outcome": "allowed", "reason": "explicit mock allow-list in request"},
  "output_hash": "sha256:<hex>",
  "parse_result": "parsed",
  "errors": [],
  "abstentions": [],
  "validity": "current",
  "review_state": "pending",
  "derived_artifacts": ["candidate:<run_id>:0"],
  "synthetic": true,
  "disclaimer": "Fictional synthetic demonstration data only. ..."
}
```

## 6. Relation to the mock adapter

The branch-only [mock adapter](../../tools/mock_specialist_adapter.py) emits receipts in exactly this shape (with `model_provider: local-mock`), demonstrating G-3/G-6 closure for the harness path. It does not modify the `investigations` table or the decided live path.

## 7. Open checks

- [ ] Reviewer confirms no field duplicates canonical authority (cross-check against the [crosswalk](ISSUE15_HL7_CROSSWALK.md) §3).
- [ ] Decide, in a separately scoped proposal, whether receipts persist as new rows/columns or as `events.details` projections. This spec requires no decision here.
- [ ] G-1 optional fields (`purpose_class`, `privacy_class`) need vocabulary agreement before use beyond the mock.
