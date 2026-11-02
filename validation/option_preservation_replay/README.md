# Open Intelligence — actual-application option-preservation replay

Complementary engineering coverage, 2 November 2026. This is not a new architecture, a clinical evaluation, a replacement for the merged OI-019 fixtures, or permission for patient data or clinical action.

## Relationship to existing work

Issue #11's original scope was delivered by merged PR #31. The separately produced `Open_Intelligence_Option_Preservation_Test_Packet_v1.zip` was a packaging-only practice artifact; its 20 packaging checks did not establish compatibility with the application. This follow-up replays a corrected derivative through the existing `CaseStore`, option/review/dependency machinery and biological-asset inventory. It adds no production code, schema, dependency, provider, API or UI change. Existing tests and fixtures remain unchanged.

## Files and provenance

- `original_packet.json`: byte-preserved packet from the earlier local archive, including its original reference commit. These original inputs intentionally fail the current strict import parsers. Do not use them as an import-ready packet.
- `replay_packet.json`: explicitly corrected **authored synthetic fixtures**, not transformed clinical documents. Two fictional cases, 15 source objects, 16 receipts and three cutoffs are retained.
- `lineage.json`: whole-file and per-source SHA-256 values, original line numbers, exact before/after edits and their reasons.
- `../../tests/test_option_preservation_replay.py`: real database integration tests; repository path is `tests/test_option_preservation_replay.py`.

Reference application commit: `7626ec8bd91ea7451b042389cb6559339e9f332c`.
Original application source was obtained through the authenticated artifact for [CI run 41479806380](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41479806380). Its outer archive digest was `f6cd54e00a43468b585a532f71279ed0edb6262a38a1a68552dacd6160c60702`. The complete reconstructed Git tree matched `b4a10c8bc60b947e83d7dbe9af9e07b034c44524`; the local snapshot commit was not represented as an upstream commit.

## Observed fixture defects and explicit repairs

| Original defect | Derived repair | Boundary preserved |
| --- | --- | --- |
| Thirteen reports used unsupported `oncology` or `coordination` Type values. | Map only these authored headers to existing `clinical` or `other` kinds. | No parser relaxation and no clinical classification inference. |
| Both evidence items repeated the single-valued `Statement` field. | Combine the original sentences, in order, into one space-separated field. | All wording is retained; original line anchors and new hashes are recorded. |
| Two later planning records declared amendments while changing the clinical event date. | Give those records distinct document identities (`PLAN-A-UPDATE`, `PLAN-B-UPDATE`) and remove the amendment declaration. | Preserve actual event dates, narratives and the earlier records. Do not backdate data or erase an earlier event to satisfy the parser. |

The inventory correction and fictional evidence correction remain genuine explicit amendments. A rescheduling event now coexists with the earlier plan; this test does **not** claim that the application automatically understands or invalidates every semantic dependency of a new event. Source-derived planning interpretation still requires review.

The legacy designer key is **not** copied as a new gold standard. Its plan-amendment assumptions no longer describe the corrected derivative. The test assertions below are a same-author engineering reference, not independent medical adjudication.

## Replay coverage

1. Original bytes/hash lineage and strict rejection of unsupported originals.
2. Receipt-cutoff import using the existing `tools.evaluation_packet.bundle`, with duplicate and wrong-case quarantine accounting.
3. T0 source/export isolation from T1/T2 information.
4. Original source bytes, hashes, source-line anchors and receipt timestamps across close/reopen of the real SQLite database.
5. A true inventory amendment invalidates its snapshot, attributed inventory row, root option and transitive dependents, but not unrelated options or another case.
6. Historical physical quantity, a newly attributed zero quantity and a separate digital-data pointer coexist without implying physical material was replenished.
7. A corrected fictional evidence item stales its linked snapshot/option; old exports retain old content and are visibly stale; stale assessments cannot enter new drafts.
8. Later planning events retain their own dates and do not rewrite earlier event records or imply an operation occurred.
9. A laboratory acknowledgment remains distinct from acceptance; no option is automatically created by importing narrative text.
10. Rejection reasons and terminal option status survive new records and restart; an invalid approval attempt adds no review event.
11. Duplicate and repeated wrong-case delivery do not create new events; out-of-order amendments and cross-case snapshots are rejected.
12. A routine no-threat control has no invented discussion deadline or preparation task.

Only `now_utc` during import is controlled to reproduce receipt timestamps. Database writes, parsing, source/evidence correction, dependency invalidation, review rejection, exports and restart are actual application operations. No model or external service is invoked. Questions, summaries, evidence assessments, inventory quantities and review actions are deliberately human/author-supplied test inputs, not AI-discovered conclusions.

Cutoff isolation is tested by staged receipt import into a fresh database. This is **not** an implementation of an arbitrary historical-state query after all future data have been loaded.

## Run

```bash
PYTHONPATH=src python -m unittest discover -s tests -p test_option_preservation_replay.py -v
PYTHONPATH=src python -m unittest discover -s tests -v
node --test tests/test_source_dialogs.js tests/test_source_line_diff.js tests/test_text_changes.js
```

Generate a participant input for a single cutoff using the existing builder:

```bash
PYTHONPATH=src python -m tools.evaluation_packet \
  --packet validation/option_preservation_replay/replay_packet.json \
  --cutoff T0 --output /tmp/oi-preservation-t0.json
```

The builder creates a new output exclusively. Give participants the cutoff output, not this directory or the whole repository. This public, AI-assisted practice set cannot establish blinded or independent evaluation.

## Verification and limits

An initial actual-application run against the uncorrected copied packet ran 11 tests and failed at the strict parser boundary (12 subtest errors and one consequent assertion failure). After the explicit fixture repairs and correction of one test-side state-key spelling, the 12 final focused tests passed. All 30 `test_*.py` modules were run in four isolated subprocess workers: **248 tests passed**, including the 12 new tests. Compile and JavaScript syntax checks passed; **39 Node tests passed**.

The single-process whole-suite command exceeded the local execution deadline without completing; it is not reported as a successful local single-process run. Local Chromium launched but navigation to `127.0.0.1` was blocked by the managed environment policy, so no local browser-pass claim is made. Do not bypass that policy. The existing PR CI runs the unmodified single-process suite and browser journeys; its exact-head result is separate evidence to inspect.

No performance, clinical correctness, patient benefit, real trial eligibility, material availability, consent, professional identity, production security or independent reviewer agreement was established. Demo option review is not medical authorization. The application remains synthetic-only. A green test package does not clear clinical deployment.
