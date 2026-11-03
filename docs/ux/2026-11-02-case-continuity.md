# Healthcare redesign: case continuity and recovery

**Work package:** OI-010, preserving the existing investigation workflow through the frontend redesign.  
**Baseline:** PR #183 at `1cd5a17f8def6c13c7be230fb56fbfa748a3f24a`, source tree `9532038cbd653d8081d5d2e09154eabfc11fbc3a`.  
**Project date:** 2 November 2026 (America/New_York; execution receipts may use 3 November UTC).  
**Status:** implemented and locally verified. See PR #183 for the published revision's hosted verification status.

## Why this follow-up is needed

The redesign handoff is already published. Its six original runtime frontend changes, complete audit, 16 form contracts, research and verification archive remain the reference. Rebuilding the interface or replacing the backend is unnecessary for this repair.

Read-only comparison with source-owner PRs [#176](https://github.com/OpenxIntelligence/open-intelligence/pull/176) (`fbfab2226989d4cc201499297877bebd695aa1ba`) and [#184](https://github.com/OpenxIntelligence/open-intelligence/pull/184) (`728a5741b7ab4faced4f41c44a931661df9dcfe1`) found that their unfinished-question and original-file protections are absent from #183. This work reconciles those frontend behaviors without importing their unrelated record-acquisition backend or changing the branch dependency.

Actual Chromium reproduction on the baseline found:

- A question-only patient switch succeeds and erases the unfinished question. Pasted text and an unsubmitted selected original also require protection.
- The intake adapter resets its local file scope for every picker event, even if the canonical case owner vetoes the change or the same patient is reopened.
- An Alpha saved-report notice remains visible under a successfully loaded Beta chart.
- The active original-record intake disclosure collapses when the selected case changes to a case that already has records.
- A deliberately failed Beta state load leaves Alpha's question/report progress visible on the global workspace setup page.

These are frontend context and editing-continuity failures, not new clinical functions. The linked source-owner fixes are inputs to reconcile; their passing CI does not prove the combined redesign works.

## Acceptance and implementation boundaries

1. Use the existing canonical case owner and readiness guard. Same-case worklist navigation retains editing state; a different-case change is vetoed for unsaved questions, pasted originals, existing narrative fields, or a selected original file.
2. Provide explicit local discard for an unsubmitted original; it must not remove imported versions, reports or history. Import payloads, validation, source bytes and database behavior remain unchanged.
3. Apply intake scope changes only after the canonical case has actually changed. Do not depend on asynchronous listener-registration order or microtask timing between native browser listeners.
4. Keep a saved-report action attached to its originating case. Preserve unrelated global notices.
5. While a selected case is unavailable, hide previous-case progress. Restore projections only from the existing successful state owner.
6. Keep an explicitly selected intake destination usable after initial loading or case changes. Preserve intentional disclosure state on ordinary same-case refreshes.
7. Preserve all original form fields and validation, both launchers, source readers, review/amendment behavior, responsive navigation, and the presentation-only audience distinction.

No backend, schema, API, authentication, authorization, source/parser rules, model behavior, production dependency, or fixture data change belongs in this increment. Keep the existing draft and parent relationship; merging and deployment remain outside this repair.

## Verification plan

First record failing real-browser cases on the exact baseline. After the repair, run both focused journeys, the complete Python and JavaScript suites, the existing browser workflows, and the full responsive navigation/form journey. Include the new navigation and recovery journeys in hosted verification. Compare protected product paths with the baseline and inspect the published head before claiming completion.

## Final results

### Implemented behavior

- One shared unfinished-work predicate now serves the existing case picker and workspace-creation preflight. Questions, pasted original text, the already protected narrative fields and selected originals block a different-case selection.
- Reopening a ready chart preserves its text, question/source selections and exact browser File without issuing another state read. Reopening an unavailable chart through its actual worklist row retries the existing state owner.
- **Discard selected source** clears only an unsubmitted browser File, preview and confirmation. It advances the existing read sequence so a delayed file read cannot reattach the discarded preview to another case. It is disabled, and its handler also rejects discard, during an active import.
- The canonical case owner emits `oi:case-selection-changed` after accepting a new selection and making the old state unavailable. Both presentation consumers observe that event. Vetoed and same-case navigation do not emit an accepted transition.
- Saved-report actions and switch warnings carry their originating case. An accepted different-case transition removes those notices; unrelated global notices retain their existing behavior.
- Previous-case progress and identity projections are hidden while a selected state is pending or unavailable. Recovery uses the existing successful projection. The active intake disclosure stays open after first/new-case loading, while ordinary same-case rendering preserves a user's chosen open/closed state.

Runtime changes in this increment are limited to `web/app.js`, `web/intake.js`, `web/workspace-entry.js` and `web/workspace-entry.html`. All 16 original forms retain their fields, native validation and select values. The unchanged baseline manifest permits exactly one additional `type="button"` discard control. No backend, schema, API, authentication, authorization, parser/source-byte rule, model behavior, production dependency or existing fixture changed.

### Actual execution evidence

| Verification on the final runtime files | Result |
|---|---|
| Complete Python/HTTP suite | 347 tests passed |
| JavaScript suites executed directly per file | 80 named tests passed across 8 files |
| Seven established Chromium journeys | Passed: integrated workflow, source-dialog races, original-text comparison, Composer, Mission, empty-workspace intake, source-first layout/keyboard |
| Responsive navigation and all forms | 792 assertions passed, both launchers, 22 captures; 320/390/768/1024/1440px checks |
| Unfinished work, real keyboard picker, worklist and local discard | 14 scenarios, 310 assertions passed |
| Native selection, disclosure state, scoped report notices, delayed/failed loads and actual worklist retry | 68 assertions passed |
| Captured application JavaScript errors in focused and navigation receipts | Zero |
| Scope, original form manifest and whitespace | Passed |

[Machine-readable summary](evidence/2026-11-02-case-continuity.json) records runtime SHA-256 values and results. The [execution archive](evidence/2026-11-02-case-continuity.zip) contains raw final reports, Python/JavaScript/browser logs and earlier failing receipts. The hosted UI workflow now runs all of these journeys, records the actual checked-out Git tree and runtime fingerprints, and uploads source, reports and screenshots.

The initial unfinished-work run had 13 failing scenarios and one passing successful-import control. The initial disclosure/scope journey recorded nine failed assertions. Independent review then caught a same-case retry regression; its real worklist check failed before the correction. A further trusted keyboard test reproduced four assertions failing because a native event can execute microtasks between listeners. The canonical-owner notification corrected that path, and the final keyboard and recovery runs passed.

One intermediate browser scenario timed out while initializing the viewport, before application checks. That unsuccessful environment attempt is preserved in the archive; the final complete native-keyboard run passed. The earlier redesign's documented intermittent backend conditions were not modified or claimed fixed.

### Reproduction

Use an existing Chrome/Chromium installation on `PATH`; no new application or browser-package dependency is required.

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -v
for test_file in tests/test_*.js; do node "$test_file"; done
PYTHONPATH=src OI_UI_STANDARD_SMOKE=1 python tests/workspace_navigation_journey.py
PYTHONPATH=src python tests/workspace_case_safety_journey.py
PYTHONPATH=src python tests/workspace_scope_recovery_journey.py
```

`.github/workflows/ui-glance.yml` lists the additional established browser commands and artifact destinations. Tests use isolated temporary databases and independently authored fictional text. The focused file-race scenario delays a real `File.arrayBuffer()` read; the state-recovery scenario exercises real keyboard selection and the visible worklist action. There is no separately delayed already-submitted HTTP import response test.

### Review and remaining boundaries

Independent code review found the retry and native-listener defects before publication; both received failing regressions and targeted corrections. Follow-up review found no remaining material blocker within this scope. These are Chromium software checks, not cross-browser certification, a formal accessibility audit, clinician usability research or clinical validation. The audience selector remains a presentation preview. The existing draft/parent relationship and broader H1 convergence gates remain unchanged.
