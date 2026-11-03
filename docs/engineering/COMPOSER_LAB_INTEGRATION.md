# Native Composer C4 integration — staged candidate
Status: **stacked draft**, source-bound numerical synthetic analysis; no clinical approval, deployed service, production identity or persistent job executor.

## Dependencies
- Parent PR #68 (existing Composer question/case fingerprint, preview and browser flow).
- Independent PR #72 (verified original synthetic lab_trends.py and its 12 tests).
- This integration branch contains both modules and adds a read-only HTTP GET plus contextual UI actions. Base PR #68 is not modified; main and PR #72 remain untouched.
- Do not merge this branch to main before coordinating acceptance and merge ordering of both parents. Resolve source-version conflict and re-run tests after any rebase.

## What is genuinely implemented
- GET /api/cases/{CASE-ID}/composer/tools/lab-trend?question_id=<int>&context_fingerprint=<sha256>&finding_key=<key>.
- Reads one CaseStore.state() snapshot, verifies the question, case, eligible current sources and evidence context against the supplied fingerprint, computes an exact source-anchored decimal difference only from eligible synthetic OI-LAB-VALUE/1 laboratory findings, then rechecks the context to detect concurrent invalidation.
- Uses the *existing* Composer preview for source-context selection and shows a source-inspectable numerical result, explicit holds, computation receipt and unreviewed status.
- Does not create/persist a Run, invoke a model or scientific data pipeline, call external services, translate units, generate a medical plan or claim clinical interpretation.

## Scope and limits
- Synthetic-only, 127.0.0.1 local HTTP demo. The fingerprint is **not authentication**. No patient or clinician identity, consent, review or HIPAA-grade data handling.
- A successful numeric calculation is not an evidentiary judgment. The source's qc=passed flag is only authored fiction; the tool cannot assert lab validity or clinical significance.
- The numeric result is a **read-only ephemeral receipt**; if new source material arrives after response, historical output can be stale. No durable scheduler, automated re-run or medical alert is implemented.
- A report lacking the exact measurement grammar cannot be treated as a numeric lab. Wrong case/question/token, incompatible units, invalid QC, same-day ambiguity and missing data must fail closed.

## Test verification
- Tests in tests/test_composer_lab_tool.py (HTTP/case/fingerprint/stale/review/no-write/JS) and tests/test_lab_trends.py (12 deterministic cases).
- Run Python compile, JS syntax, unit/HTTP and headless Chromium regression suite via existing GitHub Actions. Record exact SHA/run and independent review status; no inference from older parent CI.
