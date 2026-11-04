# Open Intelligence — semantic mapping adversarial challenge v2

**Date:** 2026-11-04  
**Status:** new 72-case synthetic, author-labeled research challenge. Draft/unmerged/undeployed. **Not NVIDIA inference, not independently adjudicated, not clinical validation.**

## Why a second test was necessary

The original 54-case evaluation used a simple literal concept/field matcher and a fixed set of guard phrases. Some guards closely resemble the 24 authored negatives, so 24/24 abstentions in that set cannot establish generalization. NVIDIA Auto Ontology's genuine catalog import/export is verified in [PR #451](https://github.com/OpenxIntelligence/open-intelligence/pull/451), but neither that test nor the earlier schema checks measure actual model-generated semantic mappings.

This extension is deliberately separate from the Patient World Model's patient, source, authorization, evidence, review and amendment owners. It **does not change** clinical records, create an agent, call NVIDIA NIM, run SQL, or approve any relationship as clinical truth.

## Frozen challenge design

[PR #474](https://github.com/OpenxIntelligence/open-intelligence/pull/474) contains:
- `tests/fixtures/semantic_adversarial_challenge_v2.json` — 72 new synthetic questions, with IDs B-201–B-272; none have identical normalized text or case IDs from the original set.
- 36 positive lookup references, 12 per source-projection concept (source version, source observation, source disagreement). Gold mappings were authored manually using only the first-party 22-field allowlist.
- 36 negatives that *should abstain*: ambiguous (7), unsupported (7), unsafe (10), and false-join claims (12).
- `tools/semantic_adversarial_eval.py` — immutable-corpus shape/disjointness checks, reuse of the **unchanged original** first-party baseline, source/manifest digests and per-category/per-concept confusion metrics; optional external predictions must use the existing strict offline replay contract and remain explicitly UNVERIFIED.
- `tests/test_semantic_adversarial_eval.py` — 17 negative controls including altered gold, overlap, stale replay hashes, false join/unsafe injections, forged extra patient fields and deterministic report identity.
- `.github/workflows/semantic-adversarial-eval.yml` — exact-checkout, stdlib-only, no NVIDIA keys, no DB/no network/model calls, test and scoring receipt uploads.

**Methodology boundary:** No independent reviewer adjudicated the gold references. The data are public in the repository, so a future run is NOT truly blinded by default. The cases were constructed after the first 54 examples were available and are meant to expose failure modes, **not** to estimate real-world clinical risk. The baseline's literal guard rules were not modified for this experiment.

## Observed baseline results

From exact-head [GitHub run 41925545482](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41925545482) at source `836d57644cfaf7f810b8a2b11859745a0ba4ebb2` (the tested head before this documentation update):

| Measure | Original 54-case authored set | New 72-case challenge |
| --- | ---: | ---: |
| Positive lookup reference cases | 30 | 36 |
| Correct source concept + field | 10 | **2** |
| Positive lookup abstentions | 20 | **34** |
| Wrong-field outputs on positive lookups | 0 | 0 |
| Negative cases | 24 | 36 |
| Correct negative abstentions | 24 | **32** |
| False mappings on negatives | 0 | **4** |
| Unsafe-negative false mappings | Not separately established | **1 / 10** |
| False-join-negative false mappings | Not separately established | **3 / 12** |

The new positive correct rate is 2/36 (5.6%); negative abstention is 32/36 (88.9%). This is **baseline software behavior on different author-labeled question sets**, not NVIDIA model performance, a population estimate, or evidence of clinical safety.

**By concept, positive correct / abstained:** source version 0/12, source observation 0/12, source disagreement 2/12. **By negative category, abstained / wrongly mapped:** ambiguous 7/0, unsupported 7/0, unsafe 9/1, false join 9/3.

**Tracked failure IDs:** B-252 (unsafe mapping), B-263/B-264/B-271 (unjustified relationship mapping). Inspect the synthetic questions and the source-quoted model proposal separately before any interpretation. The baseline sometimes chooses a valid *field name* for a request that should not be treated as an authorized mapping or clinical action. No request executed: these are output labels only.

## Verified receipt and reproducibility

The initial exact-head workflow finished **59/59** Python tests (42 inherited semantic checks + 17 new adversarial checks), no failures or skips, and generated the challenge report; this is **historical evidence superseded by the complete 74-test run below**. [Artifact 13368264053](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41925545482/artifacts/13368264053) was independently downloaded and checked against the GitHub ZIP digest `sha256:9315fce4f398a1f4778a186b56940da4524596686f445e422b30a95c523ef478`. ZIP integrity, receipt commit SHA and JSON metrics were checked. Dataset canonical digest: `36f490872174bcf2bebf9662aaead236d9b3632f41275a650e172b4defaf3132`.

Reproduce the baseline without a provider credential:

```bash
python -m unittest discover -s tests -p 'test_semantic*.py' -v
python tools/semantic_adversarial_eval.py \
  --cases tests/fixtures/semantic_adversarial_challenge_v2.json \
  --original tests/fixtures/semantic_benchmark_cases_v1.json \
  --output /tmp/oi-semantic-adversarial.json
```

An external prediction file, if later supplied, is **not authenticated vendor evidence** by this harness. Its entries must pass all strict existing mapping tests; the source and model runtime cannot be proven from the JSON. Do not describe replay scores as NVIDIA, clinician-reviewed, or live data unless verified through a separate trusted execution receipt.

## Question-only packet and updated verification

To create a safer **input boundary** for a separately approved future model experiment, the research branch now contains `tools/semantic_question_packet.py` and **15 new regression checks**. It emits a deterministic `oi.synthetic-semantic-question-packet/1` file containing 72 fictional questions, three source-projection concepts, 22 allowlisted field names, and non-authorizing constraints. It **omits all answer mappings and negative-case category labels**, does not call a model or database, refuses changed prompts when checked against the locked synthetic reference corpus, and writes exclusively to a new output path.

The packet is **not** NVIDIA's inference API schema and is **not truly blinded**: the original reference labels are visible elsewhere in this public research repository. Before a credible vendor comparison, a separate trusted runner must keep independently adjudicated gold labels outside the model's input context and must record inference provenance instead of trusting a model-supplied receipt.

**Latest verified test result:** [exact-head GitHub run 41926176834](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41926176834), source `a5890d6a37d01a9e9d015a35aede69b55264797d`, **74/74** Python tests passed. The unchanged baseline produced **2/36** valid field mappings and **4/36** false mappings on negative cases (1 unsafe, 3 false joins). All fields, source manifests and the 72-item question packet were confirmed through the hosted artifact. [Artifact 13369332682](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41926176834/artifacts/13369332682), GitHub ZIP digest `sha256:26b66f18fd1dcdde9252b4120dc96aaa0e7bc06dcb6d4a2c3fbd0574cece0026`, was independently downloaded, hash-verified and ZIP-integrity checked; its `questions-only.json`, `report.json`, `receipt.json` and `tests.txt` were inspected. This is an exact head **prior to this documentation-only update**; later commits require their own receipt.

The input-only packet does not authorize importing clinical sources, granting cases, prescribing, running SQL, making patient conclusions or calling hosted models. Passing its safety-structure tests does not demonstrate compliance, real access control or clinical correctness.

Reproduce the packet locally:

```bash
python tools/semantic_question_packet.py \
  --challenge tests/fixtures/semantic_adversarial_challenge_v2.json \
  --original tests/fixtures/semantic_benchmark_cases_v1.json \
  --output /tmp/oi-questions-only.json
```

## Decision and next real evaluation

1. **Do not promote the baseline or Auto Ontology into a patient-facing AI system.** A metadata field lookup is never a grant to access a case, merge subjects/specimens, infer clinical significance, perform treatment selection or send records.
2. Preserve this v2 challenge unchanged; do not tune guard phrases to its failures and then claim held-out generalization. If engineering updates are made, version a fresh training/development set and compare against a truly independent, unreleased challenge with prespecified criteria.
3. Use the now-implemented **question-only packet** as an input-only artifact for a separately authorized NVIDIA sandbox test. It excludes gold labels from the input but is not a blinded study, because the public corpus contains the answers. A trusted model runner must independently record endpoint/version, invocation ID, task scope, latency, token counts, egress policy, request/response hashes and costs. A model response cannot sign its own provenance; independent adjudication is still required.
4. Independently review and adjudicate the source versions, specimen/assay/time relationships, missing/negative/unknown semantics and clinical intent classes. Do not infer that field-only metadata can answer questions requiring record values, cross-case permissions or actual clinical judgment.
5. Measure exact field-mapping correctness, false joins, unsafe-field acceptance, abstention, reviewer correction burden, latency and total cost **on genuine model-generated outputs**. Predefine stop conditions before running. Passing this small corpus must not constitute clinical release clearance.
6. Reconcile integration owners, licenses, model weights, patient privacy, identity and authorization before any real record access. The existing Open Intelligence architecture remains authoritative.

The inherited single-cell-analysis workflow is independently owned; a failing unrelated run does not invalidate these scoped 59 semantic tests, and scoped success does not imply every repository check is green.
