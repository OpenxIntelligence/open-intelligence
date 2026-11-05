# Open Intelligence — NVIDIA-native metadata sandbox

Date: 2026-11-03. Status: **implemented offline; NVIDIA runtime not executed**. This is a bounded research adapter, not a new clinical source, authority, ontology or review owner.

## Upstream verified contract

- NVIDIA repository: https://github.com/NVIDIA/auto-ontology at commit `cdaf61e1bd0cf3820d11d72b43bb460816aebbd3`.
- `auto_ontology/server/model_interchange/schemas.py` defines `AutoOntologyModelDocument`: `data_layer.databases/schemas/tables/columns` plus `semantic_layer.terms/columns_attributes`, foreign keys, joins, SQL attributes, custom analyses and zones.
- `auto_ontology/server/model_interchange/service.py` uses `yaml.safe_load`, validates a native model, and applies it to NVIDIA's own catalog. `POST /api/model/import` is admin-only. The defaults `replace=true` and `embed=true` may replace catalog data and generate embeddings. Never use those defaults for this test.
- `auto_ontology/connectors/sqlite.py` supports a file-based SQLite connector but does not establish patient-level authorization or compliance.

## Reproduce the zero-data sandbox

From the Open Intelligence repository root:

```bash
python -m unittest discover -s tests -p 'test_semantic*.py' -v
python tools/semantic_native_model.py --output-dir /tmp/oi-native-sandbox
```

The output directory must not exist beforehand. Generated files:

| File | Content |
| --- | --- |
| `oi_native_model.yaml` | JSON-formatted YAML-compatible NVIDIA-native model shape: 1 fictional SQLite database; 3 metadata-only tables; 22 allowlisted source-projection columns; 3 synthetic semantic terms; 22 column attributes |
| `oi_metadata_sandbox.sqlite` | SQLite file with the exact 3 metadata-only tables and **zero rows**; file mode 0444, additionally mount read-only in a vendor container |
| `receipt.json` | Model/source fingerprints, counts and explicit evidence limits |

The generator does not contact a model, service, network or real database. Sample values, SQL, joins, foreign keys, clinical conclusions, patient ID/value fields and approvals are entirely absent. The built-in strict validator rejects any changed or additional model content. All terms are unreviewed synthetic field labels, not AI clinical inferences. The emitted JSON is parsed by `yaml.safe_load` as a YAML-compatible mapping (confirmed in the available local environment), but actual NVIDIA catalog import has **not** been run.

**Local results:** 42/42 regression tests passed; generator creates 3 empty tables with 22 columns and 3 terms; no PHI. The prior 54-case literal baseline remains 10/30 correct mappings and 24/24 negative-case abstentions. Neither result is NVIDIA semantic-model performance.

**Hosted verification:** [CI run 41743685870](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41743685870) passed on exact branch source `c620319` (the parent branch head before this fix), including the then-40 semantic tests and the native sandbox checks. GitHub recorded [artifact 13281873151](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41743685870/artifacts/13281873151). The earlier run 41743446307 on `19cd601` is superseded and must not be cited as current. Hosted CI re-runs on the parent PR's head once this fix lands there; no hosted run is claimed for this fix branch itself, whose head is verified by the local suite below.

## Next gate: isolated NVIDIA runtime, not the clinical app

1. Provision a disposable host/namespace with **no** Open Intelligence patient/system credentials and clone the pinned NVIDIA source. Audit container/dependency licenses and set nondefault administrator secrets. Keep UI/backend/ingest/PG ports private, prohibit unapproved egress and telemetry.
2. Mount only the zero-row SQLite fixture read-only and configure only that data source. The NVIDIA UI stores connection passwords in plaintext unless **all** Vault settings are configured; no real database credentials belong in this test.
3. Without an approved NIM or self-hosted inference endpoint, skip vendor inference and embeddings. No NVIDIA API key has been used in this PR. Before enabling a model, verify model/service terms, data egress, input scope and workload isolation.
4. For a separately approved disposable NVIDIA catalog, use explicit `replace=false&embed=false` flags with a sandbox admin API token. The command below writes **only to the isolated NVIDIA catalog**, never to Open Intelligence:

```bash
test -n "$AUTO_ONTOLOGY_SANDBOX_TOKEN" || exit 1
curl --fail --show-error --silent --request POST \
  --url "http://127.0.0.1:3000/api/model/import?replace=false&embed=false" \
  --header "x-api-key: $AUTO_ONTOLOGY_SANDBOX_TOKEN" \
  --header "content-type: application/x-yaml" \
  --data-binary "@/tmp/oi-native-sandbox/oi_native_model.yaml"
```

5. Validate round-trip IDs, 3 tables, 22 columns, 3 terms, zero samples and no inferred joins or SQL. For exports, specify an **explicit nonempty database ID scope**: NVIDIA's `databases: []` means export *all* catalog databases. Keep any vendor-generated export out of the public repository until rights and contents are inspected.
6. Evaluate against an independently adjudicated held-out synthetic set. Measure correct semantics, invalid joins, ambiguity/abstention, report amendments, reviewer effort, latency, all model usage and cost. Keep model outputs proposed/unreviewed; the first-party contract never grants data access or clinical authorization.

## Outstanding risks and negative evidence

NVIDIA's runtime is not installed here: the current environment lacks Docker and outbound git/network DNS, and no approved NVIDIA inference credentials are present. The Python tests validate the reproducible first-party artifact **shape**, not actual runtime compatibility or clinical usefulness. Clinical integration/production use remains blocked pending independent rights, identity, security, real-source isolation and owner-chain reviews.

An inherited [synthetic case ledger run 41740353321](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41740353321) failed to connect to Chrome DevTools after Chrome reported starting, although unit tests passed. That is separate from the metadata-only work but must not be hidden in a global CI-ready claim. Existing H1 PostgreSQL/React drafts remain unmerged and are not modified by this sandbox.
