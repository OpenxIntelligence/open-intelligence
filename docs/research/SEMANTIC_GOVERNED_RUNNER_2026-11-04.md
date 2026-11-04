# Open Intelligence — governed synthetic model proposal runner and separate scorer

**Date:** 2026-11-04  
**Status:** research-only engineering interface and scripted local test-double verification. **Not** NVIDIA model inference, clinical evaluation, EHR integration or production deployment.  
**Stack:** draft PR #476 is based on #474 → #451 → #448 → #399; preserve canonical patient/source/evidence/review/permission owners.

## Why this exists

The original synthetic benchmark and subsequent 72-question adversarial set tested a first-party literal baseline, **not a generative model**. The new challenge revealed 4/36 false mappings on abstention cases (1 unsafe, 3 false joins) and 2/36 valid mapping recall. A future vendor experiment needs a tightly scoped interface to compute and an **independent scorer**. Neither a model's field proposal nor the name of a vendor can grant clinical action or establish a trustworthy evaluation.

## Implementation and boundaries

- `tools/semantic_local_model_runner.py` reads **only** the 72-question, gold-label-excluded `oi.synthetic-semantic-question-packet/1`. It must be supplied an **independently expected packet hash** at startup. The CLI does not read the gold answers; however, the repository containing its source also contains the public gold, so the **actual model process must be isolated** from the research repository and only mounted the packet and necessary runner code before any credible evaluation.
- The allowed model endpoint is strictly `http://127.0.0.1:PORT/v1/chat/completions` with an unprivileged port. Public IP addresses, hostnames, query strings, user-info, redirects and HTTP proxy use are denied. A separate operator may eventually run an explicitly cleared, locally hosted OpenAI-compatible inference server, but **no such vendor/model ran in this PR**. This is NOT Auto Ontology's catalog or SQL endpoint.
- System instructions allow only `{"status":"abstain"}` or `{"status":"proposed","concept":"...","field":"..."}`, with all fields drawn from the existing 22-field Open Intelligence allowlist. No external tools, SQL or sources are exposed. Untrusted user text can still induce errors; the first-party parser rejects unknown fields, extra keys, injected SQL, false approval states and unauthorized database joins.
- A structured, incomplete, oversized, malformed, truncated or transport-failed model response is **invalid/error**, **not** a safe abstention. The runner retains no raw model response, model credentials, clinical text or provider usage claims: each result stores only an identifier, field proposal or error status, local elapsed milliseconds and a response digest. It is explicitly `self_reported_unsigned`: a digest detects accidental changes but does **not** authenticate the model, environment, request origin or output provenance.
- `tools/semantic_model_scorer.py` is a **separate offline program** that loads a reference set only after the model run is complete. It checks matching ordered question IDs, packet/reference digests and strict run structure, then reports positive correctness, deliberate abstentions, invalid outputs, wrong mappings, unsafe mapping errors and false joins. It has conservative experimental stop flags on any unsafe/false-join/wrong-field/malformed/transport event; these are **not medical release thresholds**.
- The published reference answers are **not independently adjudicated, secret or blind**; a run using those answers is only software research. Model cost/tokens/weights/provenance, external egress, independent reviewer work, clinical validity and production adoption all remain **unverified**.

## Reproduce without running a model (scripted test double only)

```bash
python -m unittest discover -s tests -p 'test_semantic*.py' -v
python tools/semantic_question_packet.py \
  --output /tmp/oi-questions-only.json
```

To prepare an **authorized future model-only experiment**, move only the vetted question packet into a separate isolated sandbox; do not mount the repository/answers, databases, credentials, worktree or clinical records. Start a reviewed model service at a loopback address and supply an independently recorded packet digest:

```bash
python tools/semantic_local_model_runner.py \
  --packet /isolated/oi-questions-only.json \
  --expected-packet-sha256 "<independently verified sha256 from frozen packet>" \
  --endpoint http://127.0.0.1:18763/v1/chat/completions \
  --declared-model-id local-evaluation-model \
  --output /isolated/oi-local-model-run.json
```

The command above is **illustrative, not executed** by this research PR; a model endpoint is deliberately absent from CI. A model's declared ID is an unverified string. Do not add an API token or call NVIDIA-hosted NIM without separate approval for license, service cost, data egress and security policy.

For an **offline local-score experiment** with public, author-labeled fictional answers only, keep the scorer and reference files away from the model's read access and invoke:

```bash
python tools/semantic_model_scorer.py \
  --run /isolated/oi-local-model-run.json \
  --packet /isolated/oi-questions-only.json \
  --reference tests/fixtures/semantic_adversarial_challenge_v2.json \
  --original tests/fixtures/semantic_benchmark_cases_v1.json \
  --output /isolated/oi-local-model-score.json
```

The scorer refuses partial runs. Do not treat a perfect abstention rate or an absence of stop triggers as proof of useful mapping, and never route a passed result into clinical publishing, permissions or therapeutic decisions.

## Verification and next gates

- The **scripted test double** exercises the local HTTP request path, strict parser, malformed and failed response accounting, separate scoring, and tamper-resistant *identity checks* (not cryptographic origin attestation). Tests also reject non-loopback endpoints, proxy/redirect attempts and missing completion signals.
- The exact-head CI on this PR runs the inherited 74 synthetic tests plus 21 new runner/scorer regressions (expected **95**), then scores a deliberately scripted fake-model run. It must print `inference_execution=scripted_test_double_only` and explicitly **no NVIDIA inference** in its receipt; the outcomes are a test of software gates, not model quality.
- Pending before NVIDIA inference: isolated execution environment with **only** approved synthetic prompts, vendor model/weight/endpoint rights and actual source hashes; host-controlled request/response provenance and egress telemetry; measured tokens, latency and total cost; independent adjudicated held-out reference; prespecified go/no-go thresholds and threat model. No model should be given SQL tools, clinical data or patient authorization.
- Pending before product integration: reconcile the canonical PostgreSQL patient/source/review/evidence owner stack and pass exact-head authorization, amendment, clinical review, recovery, React/UI and rights checks.

**Decision:** the research runner/scorer can support a next governed model experiment. It establishes neither NVIDIA Auto Ontology semantic accuracy nor clinical safety. Keep all research PRs draft until review, rights and operational gates are resolved.
