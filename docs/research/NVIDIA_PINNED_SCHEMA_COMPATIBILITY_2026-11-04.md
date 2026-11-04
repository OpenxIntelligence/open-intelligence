# Open Intelligence — pinned NVIDIA schema-compatibility experiment

**Date:** 2026-11-04  
**Scope:** synthetic metadata only; stacked on research PR #399, not on the unmerged patient/PostgreSQL clinical stack.  
**Status:** first-party and upstream Pydantic schema check; no NVIDIA server, model, SQL runtime, clinical integration, approval, or licensed biomedical data.

## Concrete finding

NVIDIA's upstream `AutoOntologyModelDocument.model_validate()` **accepts** the native-format-shaped Open Intelligence sandbox and `model_dump(mode="json")` preserves the entire 3-table / 22-field / 3-term synthetic document without changes. The official Pydantic schema code was checked byte for byte against the pinned Git source.

A negative probe revealed that NVIDIA's Pydantic models **ignore an unexpected root key** by default. An untrusted input containing `patient_id` may be silently dropped instead of rejected when passed straight to the NVIDIA model. Therefore Open Intelligence's **first-party `validate_native_model` strict allowlist MUST run before NVIDIA's parser**, and no external schema, JSON, YAML or vendor response may bypass that gate.

## Exact upstream evidence

- Repository: https://github.com/NVIDIA/auto-ontology
- Commit: `cdaf61e1bd0cf3820d11d72b43bb460816aebbd3`
- Source path: `auto_ontology/server/model_interchange/schemas.py`
- Git blob SHA-1: `8e00725dc481ac485b6c55105181fa163dea9ce5`
- SHA-256: `54e3d56e3ffb1178d5b4bfc2872fce761ede8461c3d8ea0a753f7a0fa7ecfc39`
- Upstream code license: Apache-2.0. Evaluation-only library dependency: `pydantic==2.13.5` with its resolved transitive wheels recorded by the hosted workflow. These are not production dependency approvals.
- Runtime source validation uses the **exact downloaded file only after both hashes match**. Source is not vendored or installed as an Open Intelligence dependency.

## Implementation

- `tools/semantic_upstream_contract.py` reads the exact hashed upstream file (maximum 16 KiB) and a 64-KiB-bounded strict JSON/YAML-compatible native model. It calls OI's strict schema and empty-SQLite validators **first**, then loads the already hashed Pydantic definitions in memory and checks a lossless round trip. It reports the vendor's unexpected-key behavior without accepting it.
- `tools/upstream_schema_compat_test.py` has 13 targeted tests for exact vendor acceptance, round-trip, repeatability, root-key rejection at OI, modified source/hash mismatch, arbitrary executable rejection, SQL and foreign key injection, sample values, SQLite row insertion, malformed JSON, and oversized inputs.
- `.github/workflows/semantic-upstream-contract.yml` pins the upstream commit/content hashes and Pydantic version, fetches only public source to a temporary path, runs the separate evaluation workflow, records source and response hashes, and uploads evidence. This is separate from the standard patient/API/React suites.
- This PR **adds no vendor runtime, DB connector, patient API, model-serving dependency, migration or clinical workflow**.

## Reproduction and interpretation

To reproduce with the *existing first-party* generator in the same checkout, download the upstream file from the pinned URL, **verify the SHA-256 and Git blob above**, and set `OI_PINNED_NVIDIA_SCHEMA_PATH` to the resulting path. Then:

```bash
python -m pip install 'pydantic==2.13.5'
python tools/semantic_native_model.py --output-dir /tmp/oi-nvidia-compat-zero
export OI_PINNED_NVIDIA_SCHEMA_PATH=/tmp/nvidia-pinned-schemas.py
python tools/upstream_schema_compat_test.py -v
python tools/semantic_upstream_contract.py \
  --upstream-schema "$OI_PINNED_NVIDIA_SCHEMA_PATH" \
  --native-model /tmp/oi-nvidia-compat-zero/oi_native_model.yaml \
  --empty-sqlite /tmp/oi-nvidia-compat-zero/oi_metadata_sandbox.sqlite \
  --output /tmp/oi-nvidia-compat-receipt.json
```

The program executes only pinned NVIDIA Pydantic **data-contract declarations**, **not the NVIDIA server or service importer**. It does not generate ontology edges through a model, import into the vendor's catalog, call NIM or access PHI. Pydantic acceptance alone does **not** prove an end-to-end NVIDIA import/export round trip or ensure that unexpected fields would be rejected by the vendor.

## Next decisions

1. Maintain the first-party allowlist and refuse vendor-predicted joins, SQL, samples, patient fields and clinical approvals.
2. Run the same fixture in a separately isolated NVIDIA instance with no production credentials, only an empty read-only SQLite file and explicit import flags `replace=false&embed=false`. Record full container/SBOM, egress, logs, runtime warnings, model configuration and catalog readback. Do **not** enable hosted inference by default.
3. Before product adoption, collect independently adjudicated held-out synthetic questions; evaluate semantic recall, wrong joins, abstention, authority bypass, amendment propagation, reviewer effort, cost and latency. Compare to the untuned 54-case baseline, whose own gold labels are not independent.
4. Reconcile clinical source-ownership PRs and add exact-head full API/PostgreSQL/React/Chromium/recovery/rights tests before any first-party product integration.

**Go/no-go:** verified parser compatibility supports a future contained runtime test; it is **not** approval to import patient data or to ship Auto Ontology.
