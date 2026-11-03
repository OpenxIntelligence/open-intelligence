# Worklist currentness and recovery

**Work package:** OI-010. This continues Gate 2 of the existing [UX convergence record](2026-11-02-forward-convergence.md).

**Starting revision:** PR #183 at `725b7f78b77ac247b97a0c0df71caf5575ac0b5c`, stacked on #166 at `334d863b2206b290c02cd2606dcb93c93afe3a68`.

## Problem and intended behavior

The chart accepts and renders a fresh case response after a saved question, demo review or pasted source. Its Patients row is separately loaded at initialization and connected intake, so the worklist can retain earlier counts and ordering. A successful chart load can also leave an obsolete worklist error visible. Returning to Patients does not correct those rows.

Whenever the existing selected-case owner accepts and renders a successful response, its worklist row should reflect that same response. An independent worklist reload must not overwrite a newer projection, change the selected chart or reset local editing state. An explicit **Refresh list** action checks all listed cases using the existing APIs and gives visible loading, partial-failure and retry feedback.

## Implementation choice and alternatives

The implementation choice is to reuse the canonical accepted response for immediate case-local projection, and retain `renderIncomingBoard` as the single owner of full worklist reads. Independent request generations and row revisions are rendering metadata; no additional case store, source ledger or full-state cache is introduced.

Reloading every case after every chart operation would repeat reads and couple unrelated chart work to the entire roster. Refreshing only when the user returns to Patients would leave background rows inconsistent and add unrelated case reads to navigation. Neither is needed for this increment. No polling, push service or new endpoint is introduced.

The user authorized continuation of the existing frontend scope. These are implementation decisions for that scope, not a new architecture or a change to the H1 migration plan. Live inspection found no equivalent worklist fix in #192 or #218; H1 Records, World Model and reading interfaces remain under their current owners.

## Acceptance contract

1. Preserve the four existing values: maximum source `event_date`; sources whose state is `current`; questions whose state is `open`; all historical snapshots whose state is `stale`. A later amendment issue date does not change the source event or imply clinical priority.
2. Save question, save draft, demo review, pasted import/amendment, model-to-draft and file intake continue through their existing handlers and canonical `refresh()`. Only its accepted and successfully rendered response updates that case's worklist row. No extra state read is needed for this projection.
3. Update keyed existing rows and their original Open buttons. Preserve search, filtering, focus, source-event ordering, selected case, in-progress forms and same-case navigation behavior.
4. Full list requests have their own generation. A delayed response or failure cannot replace a newer successful row or a newer full list. Board-only work never changes `active`, `caseId`, `renderedCaseId` or `refreshSequence`.
5. Refresh list reuses the existing roster/state APIs. Newly returned roster entries remain openable through the existing picker. Loading is visible; unavailable summaries are identified explicitly rather than represented as zero counts. Retry restores successful summaries without a page reload.
6. Shared evidence import and withdrawal can affect multiple cases. Their existing successful workflow also requests a full worklist refresh. This does not change evidence invalidation or review rules.
7. Historical stale drafts remain counted after a replacement draft is reviewed. Use the clearer label **Historical drafts marked stale**, which also covers evidence-driven invalidation.
8. Protect all original forms, source bytes, APIs, backend/schema, authorization, model behavior, dependencies and authored fixtures. Add one non-submit worklist action outside the forms.

## Verification and boundaries

First reproduce stale counts in a real browser on the starting revision. Exercise question/review/amendment history, a distinct later-event source, duplicate/quarantine handling, search/focus, file intake, delayed success/failure, initial summary error recovery, explicit refresh and cross-case evidence invalidation. Retain the existing responsive navigation, case-continuity and scope-recovery journeys; publish exact-revision hosted evidence.

This is currentness after observed successful reads, not transactional or continuous cross-session synchronization. A write that finishes after its existing handler has abandoned the originating case may require Refresh list or revisiting that chart. The explicit action also checks changes from other sessions. No authenticated role boundary, clinical validation or deployment is established by this frontend work.

## Execution results

### Implemented behavior

Runtime changes are confined to `web/app.js`, `web/index.html` and `web/workspace-entry.js`. The accepted chart-response path projects the four values into the matching worklist row. Full-list reads use a separate generation and capture each row's revision before reading its state. A newer projection wins over both late data and late errors. Existing Open buttons are retained, including focus when event-date ordering changes.

Refresh list reads the existing roster and state endpoints. Search and editing state remain intact; newly discovered cases receive matching picker options. Partial failures replace unavailable values with explicit feedback, and retries recover without reloading the page. Shared evidence import/withdrawal requests a full refresh; file intake no longer repeats that sweep after its accepted chart refresh.

### Observed verification

| Check | Actual result |
|---|---|
| Baseline hosted regression, unchanged product runtime | [Run 41565780861](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41565780861): 12 assertions, 11 passed, one intended failure. A saved Alpha question existed while its worklist still reported zero open questions. |
| Focused hosted browser journey after the repair | [Run 41566509936](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41566509936): all 13 scenarios and 387 assertions passed; 13 screenshots; no captured application JavaScript errors. |
| Complete local Python/HTTP suite | 347 passed in 72.601 seconds. |
| Existing JavaScript suites, executed directly per file | 80 named tests passed across 8 files. |
| Original forms and served templates | All 16 original field/validation contracts and unique IDs preserved; the additional worklist button is outside the forms. |
| Independent code and test review | No material blocker found; read-only review, separate from browser execution. |

The focused journey covers both launchers, question/draft/demo review, source amendment and replacement review, historical stale counts, distinct source-event ordering, duplicate/quarantine handling, exact file intake, explicit failure/retry, retained search/button focus/question/File state, a real second tab's saved question and case creation, delayed success/failure after switching cases, competing full reads, initial summary-error recovery, and shared evidence withdrawal/amendment across both cases.

The initial local Chrome attempt was blocked before application loading by the environment's socket policy. Its escalation request was automatically rejected because sandbox approvals are disabled. No local browser pass is claimed for this increment. The repository's hosted Chromium runner supplied the actual failing and passing browser evidence, using a dedicated verification branch without creating a duplicate product PR. Downloaded artifact SHA-256 digests matched GitHub's reported values before inspection.

[Machine-readable evidence](evidence/2026-11-02-worklist-currentness.json) records the runtime fingerprints and run identities. The [execution archive](evidence/2026-11-02-worklist-currentness.zip) preserves baseline and fixed reports, logs, local suite output and browser-environment failure diagnostics. The expanded main UI workflow also runs the new journey alongside the seven established journeys, responsive navigation, case continuity and scope recovery. **The complete published revision's hosted result and exact source tree are recorded in PR #183**, since they are obtained after this source snapshot is committed.

### Bounded review decisions

- The existing completion guard can abandon a write's frontend follow-up when its original case is no longer selected. Refresh list or revisiting that chart reconciles this case; this increment does not rewrite mutation ownership.
- A failure of the very first startup roster request remains outside the per-case summary recovery path. Initial per-case summary failures and failures of an already started worklist refresh are covered.
- Verification uses independently authored fictional data in Chromium. It does not establish authenticated roles, clinical validation, formal accessibility conformance, cross-browser parity or deployment.
