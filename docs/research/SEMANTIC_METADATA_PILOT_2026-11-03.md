# Open Intelligence — semantic metadata benchmark, first executable slice

**Date:** 2026-11-03  
**Stage:** offline synthetic *engineering* evaluation; draft PR #399; unmerged, undeployed, not a clinical system or NVIDIA product integration.  
**Backlog alignment:** OI-004 (license/rights), OI-005 (architectural selection), OI-011 (bounded baseline comparison), OI-013 (authority isolation); **none is marked complete** by this experiment.

## Current result, measured locally

| Measure | First-party **literal field-name** baseline |
| --- | ---: |
| Synthetic metadata questions | 54 |
| Field-lookup questions with a reference mapping | 30 |
| Exact correct field mappings | 10 |
| Abstentions on valid field lookups | 20 |
| Incorrect field mappings on valid lookups | 0 |
| Ambiguous, unsupported, unsafe or false-join negatives | 24 |
| Correct abstentions on negatives | 24 |
| False acceptances on negatives | 0 |
| Exact overall accuracy (not a clinical metric) | 63.0% |
| Total separate safety and harness tests | 42 / 42 passed locally |
| NVIDIA Auto Ontology inference executed | **No** |
| SQL / patient-data access / external model calls | **No / No / 0** |

The baseline matches literal field/concept names from the known, bounded read-only H1 source projection, plus a small guard-phrase list for unsafe or out-of-scope wording. Several guard phrases mirror the negative cases' wording, so the 24/24 abstention rate on these authored cases is not independent evidence that the guards generalize; it shows the guards fire on the cases they were written against. It is an engineering floor, **not a clinically meaningful comparator or proof of safety**. The challenge set is authored with the harness, not independently adjudicated; before technology adoption, add held-out and expert-reviewed challenges with separate gold labels. Timing on this local machine is not an apples-to-apples vendor measurement; vendor latency and cost are unmeasured.

Frozen case set canonical SHA-256: `338d79a7536f953f917f464c2c554ae8654c3bbbba1009ee895c88cbe06b96bc`.  
Projection vocabulary canonical SHA-256: `901fd03a30ed825db93be9f3ebf71f8b70fd81a562cea585a1ee00e748f2ae6f`.

## What is implemented

- `tools/semantic_contract_probe.py` — a static schema-only projection vocabulary and fail-closed, unreviewed candidate mapping contract; no direct connection to Postgres or any service.
- `tools/semantic_benchmark.py` — a pure standard-library evaluator with a literal baseline, strict gold-case validation, and an **optional offline replay** mode for external semantic mapping proposals. External replays must provide all challenge IDs, hash the exact manifest and case set, include no SQL/row values/extra keys and retain `unreviewed_proposal` status.
- `tests/fixtures/semantic_benchmark_cases_v1.json` — 54 independently fictional metadata questions: source identity/version, finding and specimen context, report date/custody, contradiction references, ambiguity, updates, missing fields and unsafe cross-case requests.
- `tests/test_semantic_benchmark.py` — 21 regression methods covering calibration, deterministic reproducibility, stale IDs, wrong mapping, replay completeness, unsafe payloads and false-review promotion. Together with the 11 earlier boundary tests and the 10 native-model tests, 42 tests pass locally.
- `.github/workflows/semantic-metadata-pilot.yml` — narrowly scoped synthetic-only CI with pinned checkout/Python action SHAs, stdlib tests, frozen-case gate, and source-hash/commit receipts. **Hosted results must be checked on the final PR head; no run is claimed by this document.**

## Reproduce without credentials

```bash
python -m unittest discover -s tests -p 'test_semantic*.py' -v
python tools/semantic_benchmark.py --cases tests/fixtures/semantic_benchmark_cases_v1.json --output /tmp/semantic-baseline.json
```

`--external-predictions` accepts a local JSON file matching `oi.semantic-benchmark-predictions/1`. Such files are labeled `external_offline_replay_unverified` in the output even if named after a vendor: the evaluator **cannot** establish their provenance, model runtime, access posture or absence of PHI egress. No external endpoint is called and no JSON response is promoted to human-approved or clinical fact.

## NVIDIA integration reality

NVIDIA Auto Ontology 1.1.0 exposes an authenticated Next.js API, including `/api/terms`, `/api/model/export` and `/api/chat/completions`, and an MCP façade; official docs: https://nvidia.github.io/auto-ontology/ , https://github.com/NVIDIA/auto-ontology . The export endpoint is **admin-only** and can contain broad connected schemas; the chat endpoint can generate/execute SQL; its MCP `ask_question` may return SQL and rows. Therefore **none is safe to wire directly into OI's canonical patient/source owners**. A future vendor evaluation requires an entirely fictional, independently provisioned datasource; a manual/offline extraction of *allowed metadata only*; strict checking before replay; and an audited model/endpoint/egress and licenses manifest.

The intermediate `oi.semantic-mapping-candidate/1` is deliberately first-party. It does not claim to be an NVIDIA model import/export dialect. Do not implement an adapter by assuming structure that has not been checked against an exact upstream version.

## Stop/go for the next slice

1. **Pass** (engineering isolation): locally verifiable, no DB/network/model imports or secrets; all results clearly label their evidence scope.
2. **Pending**: host CI on exact current PR commit, artifact readback and independent source review.
3. **Pending**: build a sandboxed metadata-only fixture, then run NVIDIA in a sealed synthetic deployment with no production credentials, no real-case data, no public FastAPI port, no default plaintext datasource credentials and controlled inference egress. Record exact git SHA/image digest, terms, dependency SBOM and provider/model configuration.
4. **Pending**: independently author a held-out evaluation suite with at least 30 non-leaky examples, compare accuracy, wrong-link rate, abstentions, review/correction burden, latency and cost. Guard against identical specimen IDs with different time points, different specimen IDs with identical time, amended/superseded records, and access-revocation races.
5. **Never automatic**: permission promotion, clinical certification, treatment logic, source rewrite or SQL against the patient database. Model output remains a proposal pending scoped authorized review.

**Decision at this stage:** Continue investigation; **do not adopt/vendor-deploy to clinical systems** on this benchmark alone.
