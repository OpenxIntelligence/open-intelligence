# Meta Model API — investigation provider (decided 2026-10-31)

## Decision

The product's model provider is Meta's Model API, exclusively. No other
vendor's model, agent framework, or hosted AI is used in the product.
If a Meta tool cannot do something, that is recorded as a limitation
instead of substituting another vendor.

## Endpoint and model

- Base: `https://api.meta.ai/v1/messages` (Messages API)
- Model: `muse-spark-1.3` (Meta's coding/agent model; the same model
  behind Muse Code)
- Client: `src/open_intelligence/investigation.py` (`call_meta_api`),
  dependency-free standard library only (`urllib`)
- Call shape: one POST with `model`, `messages`, `max_tokens=4096`
- Verified 2026-10-31: a direct Meta Model API completion with
  `muse-spark-1.3` returned a clean result. `muse-wonder-1.0` was
  verified 2026-10-27; Wonder Full has no API route (404 on the API)
  and is not used.

## Key handling

- The key comes only from the operator environment: `META_API_KEY`.
- It is used server-side only, never stored in the repository, never
  logged, never sent to the browser, and never committed.
- Without the key, live investigations return HTTP 503 with a message
  pointing at replay mode. The local demo never fails silently into
  pretending a replay is a live run.

## What the model may and may not do

- Input: a fixed template (see `TEMPLATES` in `investigation.py`)
  plus the case's own current assertions and fictional evidence
  assessments. There is no free-text prompt from the browser.
- Output: claims and abstentions only. Every claim is validated
  before storage: citations must resolve to a current source version
  or an assessment for the question, uncertainty must be
  low/moderate/high, and output language recommending treatment,
  selecting therapy, dosing, or diagnosing is dropped by the language
  guard and recorded as dropped.
- Stored output is always `kind=hypothesis`, `review_state=pending`.
  An investigation is a proposal for review, never a conclusion,
  recommendation, or clinical determination.
- Payload minimization: only the fictional case id, the question text,
  and source/assessment statements are sent. No patient-like fields,
  no real data, no credentials.

## Replay mode

- `mode=replay` serves a recorded, human-authored fixture
  (`examples/synthetic/demo-investigation.json`) through the same
  citation validation and language guard. Placeholders are replaced
  with real current source/assessment ids from the case, then
  validated like live output.
- Replay output is labeled `mode=replay`, `model=recorded-replay`.
  It exists so the demo runs offline and the Nov 4 demo does not
  depend on network or key availability.

## Limits (not yet proven)

- Live end-to-end run against the real API from the local server
  has not yet been exercised (the server's live path is tested with
  a mocked HTTP response; the direct API completion was verified
  separately). That live-server run is the remaining proof step
  before the demo, and it requires the operator key in the
  environment where the server runs.
- Cost: Spark pricing at verification time was $1.25 / $4.25 per
  million input / output tokens. One investigation is a single
  bounded call; no streaming, no multi-turn agent loop.
- Muse Code CLI 1.4.14 is installed on the development machine as
  the coding agent, but it is not logged in and is not part of the
  product runtime. Product model use is the Meta Model API above.
