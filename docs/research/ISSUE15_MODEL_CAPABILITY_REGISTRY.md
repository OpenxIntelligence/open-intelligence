# Issue #15 — ModelCapabilityRegistry contract (specification)

**Status:** PROPOSED SPEC / EVALUATE; not implemented, not adopted, not clinical validation.
**Date:** 2026-11-02
**Tracker:** [Issue #15](https://github.com/OpenxIntelligence/open-intelligence/issues/15)
**Parent:** [HL7 crosswalk](ISSUE15_HL7_CROSSWALK.md) (gaps G-7, G-8)
**Boundary:** configuration for the model-call boundary, not a model store, not a training system, not an approval. Capabilities are optional and replaceable; the case survives any capability's removal. No vendor is approved by this spec. All records here are fictional-scope configuration, labeled as such.

## 1. Purpose

Declare, per specialist-model capability, what it may do, what it may touch, under which terms, with which QC, and with what measured fitness — so that every run can be gated *before* contact and every denial is inspectable. This closes crosswalk gaps G-7 (no capability record) and G-8 (rights gate not wired to the model boundary).

## 2. What already exists (extended, not replaced)

- Task prompts: the `TEMPLATES` dict in [investigation.py](../../src/open_intelligence/investigation.py).
- Fail-closed evaluation: `permitted` / `excerpt_mode` in [rights.py](../../src/open_intelligence/rights.py).
- Decided provider boundary: Meta Model API exclusively ([META_MODEL_API.md](../META_MODEL_API.md)). This registry does not reopen that decision: any non-Meta capability record additionally requires the separate provider approval the addendum §6 demands, and without it the record stays `BLOCKED`.

A registry record is configuration data consumed by the run gate. It grants nothing by itself; the gate evaluates it per run.

## 3. Contract

### 3.1 Record identity

| Field | Type | Meaning |
|---|---|---|
| `capability_id` | string | Stable id (e.g. `mock-chronology/1`). Version-suffixed; terms or behavior changes require a new version, never an edit. |
| `model_provider` | string | Provider identity for this capability (e.g. `local-mock`). The run receipt copies this value; it is never defaulted. |
| `provider_approval_ref` | string or null | Pointer to the separately recorded provider approval, required unless `model_provider` is `local-mock` or `local-deterministic`. Null otherwise blocks (gate §4.7). |
| `task_type` | enum | One of the closed [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) task types. One task per record. |
| `modality` | string | e.g. `text-report`, `pathology-wsi`, `genomics-vcf`. Must match the run's input modality exactly. |
| `owner_label` | string | Human-readable owner of the record (fictional-scope label for issue-#15 records). |
| `record_state` | enum | `proposed`, `cleared`, or `BLOCKED`. Only `cleared` records may authorize a run, and only when every gate in §4 passes. |

### 3.2 Interface declaration

| Field | Type | Meaning |
|---|---|---|
| `input_schema` | string | Schema id the run inputs must validate against (e.g. `issue15-task-input/1`). |
| `output_schema` | string | Schema id the run outputs must validate against (e.g. `issue15-task-output/1`). |
| `required_context` | list | Required specimen/assay/episode metadata keys. Missing keys abstain or block; they are never defaulted. |
| `qc_rules` | list | Named QC/rejection conditions evaluated before and after the run (e.g. `anchor-resolves`, `no-clinical-vocabulary`, `uncertainty-present`). |
| `abstention_conditions` | list | Named conditions under which the run must abstain rather than guess. |

### 3.3 Execution and data terms

| Field | Type | Meaning |
|---|---|---|
| `execution_modes` | list | Subset of `local_only`, `authorized_remote`. The run's mode must be listed. |
| `allowed_data_classes` | list | Data classes the capability may receive (for issue-#15 work: fictional synthetic only). |
| `forbidden_data_classes` | list | Classes that block the run if present. |
| `retention_terms` | string | Retention statement with source pointer, or `unknown`. |
| `training_use_terms` | string | Whether run data may be used for training, with source pointer, or `unknown`. Default expectation: never. |
| `dependency_licenses` | string | License status of weights/code/data dependencies with source pointers, or `unknown`. |
| `per_use_rights` | string | How per-use rights provenance is established, or `unknown`. |
| `cost_latency` | object or `unknown` | Measured cost/latency or `unknown`. |

### 3.4 Fitness declaration

| Field | Type | Meaning |
|---|---|---|
| `evaluation_ref` | string or `none` | Pointer to the benchmark record (see the [evaluation design](ISSUE15_EVALUATION_DESIGN.md)), or `none`. |
| `evaluation_date` | string or `none` | Date of the last qualifying evaluation, or `none`. |
| `failure_thresholds` | object or `none` | Per-metric pass/fail thresholds the capability was judged against, or `none`. |
| `known_limitations` | list | Human-authored limitation statements. Empty only with a recorded justification. |

No global "model score" is defined or used. Fitness is per task, per benchmark version, with raw counts — never a single unqualified number.

## 4. Run gate (fail closed)

A run is authorized only if **all** hold; any failure yields a `blocked` [ModelRunReceipt](ISSUE15_MODEL_RUN_RECEIPT.md) with the failing gate named:

1. The referenced capability record exists and is in `cleared` state.
2. The run's task type and modality match the record exactly.
3. Inputs validate against `input_schema`; required context keys are present.
4. The rights evaluation (`rights.permitted` over the case's applicable permissions, plus the record's own terms) returns allowed for every item/use the run needs; `unknown` or `denied` anywhere blocks.
5. Every `retention_terms`, `training_use_terms`, `dependency_licenses`, and `per_use_rights` field needed for the run's execution mode is known and satisfied; any `unknown` blocks.
6. The run's execution mode is listed in `execution_modes`.
7. If `model_provider` is anything other than `local-mock` or `local-deterministic`, a non-null `provider_approval_ref` points at a separately recorded provider approval (which, under the decided boundary, must additionally be the Meta Model API); otherwise block.

## 5. Lifecycle

- Records are versioned and append-only: corrections supersede (old versions stay readable as history), revocation sets `BLOCKED` with a reason and date.
- Revoking or superseding a record stales dependent *future* runs; already-produced receipts and candidates keep their recorded terms and are invalidated only through the normal amendment/invalidation machinery.
- Disabling or deleting a capability never touches the case ledger: canonical sources, assertions, timeline, and reviews are untouched. The capability is replaceable by design.

## 6. Worked shape (illustrative, fictional; the mock record)

```json
{
  "capability_id": "mock-chronology/1",
  "model_provider": "local-mock",
  "provider_approval_ref": null,
  "task_type": "chronology_extraction",
  "modality": "text-report",
  "owner_label": "Fictional issue-15 harness (branch only)",
  "record_state": "cleared",
  "input_schema": "issue15-task-input/1",
  "output_schema": "issue15-task-output/1",
  "required_context": ["specimen_id"],
  "qc_rules": ["anchor-resolves", "no-clinical-vocabulary", "uncertainty-present"],
  "abstention_conditions": ["missing-required-context", "conflicting-input-dates"],
  "execution_modes": ["local_only"],
  "allowed_data_classes": ["fictional-synthetic"],
  "forbidden_data_classes": ["real-patient-data"],
  "retention_terms": "none-stored-pure-function (mock design statement)",
  "training_use_terms": "no-training-use (mock design statement)",
  "dependency_licenses": "stdlib-only, no weights, no data (mock design statement)",
  "per_use_rights": "explicit mock allow-list in request (mock design statement)",
  "cost_latency": {"cost": "0", "latency": "negligible-local"},
  "evaluation_ref": "none",
  "evaluation_date": "none",
  "failure_thresholds": "none",
  "known_limitations": ["Mock harness only; proves contract shapes, not model behavior."],
  "synthetic": true
}
```

Real (non-mock) records would carry `evaluation_ref`, dated thresholds, and sourced terms — or stay `BLOCKED`.

## 7. Relation to the mock adapter

The branch-only [mock adapter](../../tools/mock_specialist_adapter.py) consumes capability records in exactly this shape and enforces the §4 gate (with mock-scoped term statements). It demonstrates G-8 closure for the harness path without touching the decided live path.

## 8. Open checks

- [ ] Reviewer confirms the registry is configuration, not authority: no record can approve a vendor, dependency, or clinical function (that requires the separate review AGENTS.md mandates).
- [ ] Schema ids (`issue15-task-input/1`, `issue15-task-output/1`) are placeholders pending a separately scoped schema decision.
- [ ] Wiring the gate to the decided live path is explicitly out of scope here; it needs its own proposal and approval.
