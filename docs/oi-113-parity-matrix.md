# Issue 113 parity matrix, DRAFT ONLY, 2026-11-02

Baseline SHA: 2451983, clean worktree /tmp/oi-113-clean, no modifications.
Baseline commands and results, verified 2026-11-02, 16:40 PT:
- `PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'` : Ran 236 tests, OK.
- `python3 -m unittest discover -s tools/research -p 'test_*.py'` : Ran 206 tests, OK (skipped=18, pre-existing).
- Test-method counts below are grep counts of `def test` in each file, and they sum to 236 for tests/, matching the unittest run. They are a counting check, not a substitute for the run.

## Journey map, legacy test to proposed API contract test

| Legacy journey, from issue 113 | Legacy test files on main, with test-method counts | Baseline result on main | Proposed API contract test, NOT yet written | Failure difference, main vs contract |
|---|---|---|---|---|
| Synthetic-case store | test_store.py (14), test_iv01_store.py (3) | Pass, as part of 236 OK | Contract test for case store read projections, to be written after reading PR 138 and PR 142 | None yet, no contract test exists to compare |
| Chronology | test_timeline.py (14), test_timeline_http.py (2) | Pass, as part of 236 OK | Contract test for timeline read projection, to be written after reading PR 138 and PR 142 | None yet |
| Rights | test_rights_broker.py (16), test_discovery_rights.py (11) | Pass, as part of 236 OK | Contract test for rights-gated read projection, to be written after reading PR 138 and PR 142 | None yet |
| Amendment | test_changes.py (5), test_changes_http.py (2), plus option_review_regressions for review staleness context | Pass, as part of 236 OK | Contract test for amendment versioning and staleness read projection, to be written after reading PR 138 and PR 142 | None yet |
| Evidence / investigation, supporting context | test_evidence.py (9), test_evidence_http.py (2), test_investigation.py (11), test_iv01_evidence_replay.py (2), test_iv02_iv03_contract.py (22), test_http.py (8) | Pass, as part of 236 OK | Map only, do not duplicate PR 138 MRT-01 acceptance or PR 142 question-state work | None yet |

## What this matrix does NOT claim

- It does not claim all historical tests are green in a new API implementation, because no new API implementation has been written.
- It does not claim a port is complete, or testable before the Nov 4 go/no-go gate, until the contract tests above are written and run.
- It does not change any legacy file, and the legacy files must stay runnable as fallback, per issue 113.
- PR 138 and PR 142 read 2026-11-02, 16:48 PT, bodies only, not full diffs:
  - PR 138, test(mrt01): one connected synthetic source to evidence to review to correction acceptance, draft, unmerged. Adds validation/mrt01/review_boundary_gate.py, owner/acceptance map, and read-only mrt01-composed.yml workflow, no other application implementation. Three new real-HTTP checks reproduced premature question closure for a fresh completed run, an abstained run, and a new replay after amendment, plus a supporting/counterevidence-withdrawal control, all passing by reusing PR 136's store repair exactly. Dedicated run passed 4/4 strict review-boundary HTTP tests, 4/4 retired-entrypoint tests, 250 Python unit/HTTP tests, plus Chromium journeys. Note discrepancy: issue 121 checkpoint said 237 tests for PR 138, its body says 250, do not use either number without stating its source. Baseline shared inspected: main 2451983, safety owner PR 137 head 533afd3, lifecycle owner PR 136 head 9417665. This PR does NOT settle PR 137 / PR 139 overlap, does NOT prove all main workflows safe, and does NOT inspect historical data/artifacts/caches/secrets, issue 122 remains open.
  - PR 142, fix(investigation): prevent cross-case question references in saved results, stacked, draft, unmerged. Stacked on PR 136 question lifecycle, guards CaseStore.save_investigation against a question ID from a different case, a nonexistent ID, or a boolean masquerading as an integer. Exact-head implementation SHA 363644c, UI-glance run SUCCESS 241 Python/HTTP tests plus JS, Chromium, source-dialog, layout/keyboard. No hosted red-run captured for its test-only head, source inspection established the missing ownership check. Merge gate: independent review, PR 136 reconciliation, final exact-head tests against updated main.
  - Consequence for 113: PR 138 covers review-boundary MRT-01 acceptance, PR 142 covers investigation ownership at the store write boundary. Neither is a general API contract test mapping for store, chronology, rights, and amendment journeys, so a 113 contract test mapping must not duplicate their review-boundary and ownership tests, and must cite them as related, not as the contract suite itself.
- Related links to add before any PR: OI-23 REQ IDs, OI-25 CMP IDs, OI-27 MRT-01 steps, PR 138, PR 142. Those IDs are not filled in here because they have not been verified from the source docs in this draft.

## Next steps, in order

1. Read PR 138 and PR 142 in full, and record which contract tests they already cover.
2. Write only the contract tests that are still missing, with no behavior change to legacy files.
3. Run legacy suite and new contract suite side by side, and update the failure-difference column with real results, not assumptions.
4. Only then, with Kaiju approval of the exact PR text, open a scoped draft PR containing the matrix plus the minimal contract test mapping.

Status: DRAFT ONLY. Not posted, not a PR, not approved for publication.
