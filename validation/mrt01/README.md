# MRT-01 composed acceptance — source to evidence to review

Open Intelligence is the first-party patient-centered environment that connects
records, longitudinal patient understanding, scientific investigation and care
coordination. Its first useful MVP must complete that loop, not merely display
records or chat. Public patient narratives inform capability discovery; no Sid
records/catalogs or other unapproved personal-case data are development inputs.

This directory extends the existing MRT-01 acceptance PR #138. It is **not a new
architecture, new runtime implementation, clinical study or parallel test packet**.
The application remains the existing local synthetic demonstration.

## What this increment proves

The earlier connected HTTP test executes replay only after a demo acknowledgment.
It therefore cannot detect a fresh/unreviewed model receipt closing a question.
The four additional real-HTTP tests cover completed and abstained runs before
review, another run after a source amendment reopens a question, and preservation
of explicitly authored supporting/counterevidence after withdrawal. All model
runs are labelled **recorded replay**, never live reasoning. Actual model/API
transports are tripwires; a successful callback is not permitted by the test.

On the exact safety candidate plus the original #138 test, three tests failed
and the counterevidence control passed. Reusing the original #136 store repair
made all four pass. No duplicate application fix was written.

## Ownership and reproducible composition

| Existing owner | Exact version | Role |
| --- | --- | --- |
| Main baseline | `24519839aa8ac1ea3aff88a956349ba72798a72a` | Inspected application baseline |
| #137 | `533afd3ca6dd0c011e2e47397d3d5cae04e62512` | Retired personal-case entrypoints, fictional research workflows |
| #136 | `94176658fe126647aaeea83886bff1ccf776aae8` | Preserve open questions until explicit scoped demo review |
| #138 | Current workflow checkout | Original connected test plus this strict gate |

The dedicated workflow makes a disposable detached checkout of #137, verifies
its store matches the shared baseline, copies only #136's exact store and tests,
and adds the current #138 acceptance files. The code blob is explicitly checked
as `9a5913ee27b10945e2270ecd4d447f6b8b4b9c10`. It runs the no-data source/entrypoint
guards, four strict checks, full application regression and existing browser
journeys. It cannot write remote refs or merge PRs. It installs no new packages.

The receipt records the **uncommitted tested tree** and hashes of every tracked
file; `tested_commit` is null. The workflow checkout/constituent SHAs are separate.
Successful constituent runs are not substituted for this combined execution.
Any changed owner SHA requires new review and a new combined run.

## Current audit findings and merge disposition

- Preserve #136/#137/#138 ownership. #139 overlaps #137 and needs explicit code
  comparison/reconciliation; this test does not approve either safety proposal.
- Keep #70/#74/#56/#85/#89/#93 and the #95/#132 integration work. Their descriptions
  identify valuable identity, EHR, LIS, event and knowledge-context implementations,
  but those descriptions are not a full combined-source/authorization review.
- The main policy document forbids personal data, yet the inspected baseline still
  had residual code/CI paths. The safety composition verifies selected retirement
  behavior; main itself is not changed by a composed test.
- Historical artifacts/caches, old branches/history, source derivation, credential
  stores and external services are not comprehensively inspected or purged here.
  Keep issue #122 open; do not download suspect patient archives merely to inspect.

## Local observed evidence, before publication

- Strict checks: **3 reproduced assertion failures + 1 preservation pass** before
  #136; **4/4 passed** with its original fix.
- Combined Python unit/HTTP suite: **250/250 passed** (25.775 seconds in this
  environment); research helper suite **204/204 passed**; source CI boundary guard
  passed. These are software tests and are not independent clinical observations.
- No local browser claim. Inspect the dedicated hosted run at the final head.

## Not yet a complete MVP

Source files are an authored text contract, not general medical PDF/OCR extraction.
Evidence and support/contradiction labels are fictional human inputs, not lawful
scientific retrieval or a clinical appraisal. Replay is not real model inference.
A reviewer label is not authenticated clinician identity, actual patient consent,
or a legal signature. No patient/clinical deployment, licensing clearance,
health-outcome benefit or independent clinical validation is established.

Next integration remains the founder's sequence: trusted identity/authorization,
source ingestion with human correction, longitudinal context, permitted knowledge,
reviewable investigation and updated reports. Research/catalog work complements
that implementation; it does not reset it or define new canonical patient state.
