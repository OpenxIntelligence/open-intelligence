# Crossref provenance boundary implementation plan

**Goal:** prevent ambiguous provider metadata and invalid retrieval times from entering the existing DOI-only bibliography response.

**Architecture:** retain `tools/crossref_metadata.py`, its stdlib HTTP caller and its factual-field allowlist. One strict decoder serves live responses and explicit offline fixtures. This is a bounded correction under the founder's autonomous engineering mandate, not a new connector or an H1 catalog activation.

**Tech stack:** existing Python standard library only; base `24519839aa8ac1ea3aff88a956349ba72798a72a`.

**Spec:** existing `docs/CROSSREF_METADATA_BOUNDARY.md`; master mandate sections 3, 5, 10, 14 and 16, supplied 3 November 2026.

## Constraints and decisions

- Preserve DOI-only egress, fixed endpoint, no redirects, byte/timeout limits, disabled-by-default live access, and exclusion of abstracts/full text.
- Preserve canonical patient/evidence ownership. Do not import real metadata into H1's explicitly fictional catalog or change its grants.
- Retain valid explicit retrieval timestamps exactly. Accept a strict RFC3339 subset: calendar date, `T`, seconds, optional 1–6 fractional digits, `Z` or a numeric offset. Reject unknown `-00:00`, invalid offsets/dates, naive or control-bearing values. Only `None` requests a generated UTC time.
- Reject duplicate object keys and nonstandard numeric constants in upstream JSON; report a fixed error without reflecting provider payloads. Decode before allowlist projection.
- Require the actual `application/json` media type, allowing parameters and case variation.
- No schema, dependency, clinical authority or deployment change.

## Approach

Chosen by the implementer: fix the existing connector before extending it. Replacing it adds unnecessary dependencies; accepting malformed input and labeling it uncertain would preserve false provenance. A live H1 import remains a separate qualified contract with its existing owners.

## Review focus

Impossible/leap dates; timezone rollover and unknown offsets; explicit falsey values; repeated JSON keys at any depth; MIME lookalikes; errors through real local HTTP; valid multilingual metadata and timestamp round-trip. Each is covered below or by existing fixture projection tests.

## Task 1 — strict provenance and raw-input parsing

Files: `tools/crossref_metadata.py`, `tests/test_crossref_metadata.py`.

- [x] Write failing timestamp, duplicate-key, nonstandard-number and media-type regressions. Keep positive valid UTC/offset/leap-date tests.
- [x] Run `python -m unittest discover -s tests -p 'test_crossref_metadata.py' -v`; confirm the new negative cases fail for accepted invalid inputs.
- [x] Implement `_retrieval_timestamp(value)` and `_decode_payload(data)` and use them in the projection/live/fixture paths.
- [x] Re-run the targeted suite and the documented `PYTHONPATH=src python -m unittest discover -s tests -v` command. Preserve failures and distinguish blocked checks.

## Task 2 — application boundary and durable evidence

Files: `tests/test_http.py`, `docs/CROSSREF_METADATA_BOUNDARY.md`, bounded audit/continuation report under `docs/research/`.

- [x] Exercise actual loopback HTTP with the real projection and a controlled fictional upstream transport. Verify safe rejection and subsequent successful lookup; no fabricated publisher/service success.
- [x] Run unit/HTTP and existing browser journeys, if the available runtime supports them. Separately attempt one opt-in live DOI-only lookup of a general publication; report any network restriction without bypassing it.
- [x] Review the final diff independently, correct material findings, commit and publish a draft PR targeting main. Preserve all other PRs.
- [x] Record current repository/architecture, research coverage, rights scope, measured results, limitations and the next executable integration task. Link the existing Notion engineering record to this receipt.

## Execution ledger

Baseline: existing Crossref suite 6/6 passed. Reproduction accepted arbitrary dates, February 30, naive time, offset `+01:99`, trailing newline and an explicit empty timestamp. Empty input silently became current time. Root cause: truthiness default plus a length-only check.


Task 1 complete: 13 Crossref tests passed after 25 RED subcase failures; complete suite 244/244, no skips. Task 2 complete: real local HTTP exercised controlled fictional upstream rejection/recovery; separate permitted live DOI lookup succeeded. Local browser blocked by missing executable; hosted UI and both application browser journeys passed. Independent review found no material defect; fixed HTTP example uses its original decoder and is explicitly outside CLI/live decoder parity.

Published runtime `dd5a4e5eacacc572b49a761a9c6aabd14d7a1be7`, tree `7a1025cee7e5d02da4848650fc537ecd6ebda32e`, equals the locally tested/reviewed tree. PR #325 remains draft. The GitHub API published the tree after ordinary git push lacked credentials. Existing Notion Engineering 12 was updated with exact evidence and next task.

Hosted application attempt 1 passed 244 tests but timed out starting Chrome; identical-commit attempt 2 passed the tests and both browser journeys. UI and Crossref workflows passed on their first attempts. No timeout, fixture, assertion or application change was made to obtain the retry pass. See the audit's completion receipt for exact run links.
