# Patient report and follow-through integration

## Scope and source ownership

This bounded increment connects the existing patient report to the existing persisted follow-through workflow. It advances OI-007 (durable questions and review), OI-009 (source amendment handling), and OI-010 (connected patient workflow). It does not select a production stack or narrow the platform vision.

Composition uses current main `24519839aa8ac1ea3aff88a956349ba72798a72a`, patient-report PR #78 at `5c43b718ee7d4cc3ce0e8216a3118549dfbab340`, and follow-through PR #84 at `72178f565548ba94d6a86dfeceb6800a75f4f4b4`. Both original deltas apply to main without dropping its subsequent changes. Their original component ownership remains visible; this branch is a connected integration of those components.

## Behavior to establish

1. A user records a source-linked task, assigns an owner, acknowledges it, and records completion through the existing transition rules.
2. The readable, printable, and downloadable case report includes the same persisted tasks, owner labels, due dates, review triggers, source version/hash, question links, and append-only transition history.
3. Source amendment flags open anchored work for another look. Deferred/completed work stays historical, retains its original source anchor, and visibly identifies a superseded source.
4. The report states its ledger event cutoff and due-date evaluation day separately. Task completion is an attributed record, not verified clinical action.
5. Report JSON and downloadable text share one `CaseStore.state` snapshot and one report projection. The browser downloads the accepted payload instead of silently regenerating a later version.
6. Case changes, refreshes, and writes immediately clear old report actions. Case and shared evidence/rights writes block Refresh, Print and Download until applicable pending writes settle. Late or wrong-case responses cannot re-enable stale print/download. Failed writes/refreshes remain unavailable with an explicit retry control. The read-only DOI metadata POST does not invalidate reports.
7. The report print action prints the accepted report only; the rest of the workspace remains outside that print view.

## Implementation plan and decisions

- **Established:** preserve the existing `CaseStore`, follow-through tables/events, report renderer, loopback HTTP boundary, and independent synthetic fixtures.
- **Recommended, reversible implementation:** project `state.followthrough` inside the existing patient report, use explicit browser invalidation/update events, and attach text to the same HTTP report payload.
- **Implementation sequence:** reconcile original deltas; write failing behavior tests; implement report projection and UI freshness; verify unit/HTTP/client/browser behavior; obtain independent engineering review; publish an unmerged integration PR with exact verification evidence.
- **Unresolved for the complete MVP:** production identity, caregiver/clinician grants, hosted deployment, licensed clinical content, and clinical validation remain owned by their existing workstreams. This change neither simulates nor grants those capabilities.

No new package, external service, model, source dataset, patient master, source ledger, report engine, or task ledger is introduced. Tests use independently authored fictional records only.

## Acceptance and verification

Required checks cover real task lifecycle and restart, read-only report rendering, amended-source provenance, deferred/completed history, cross-case isolation, changed evaluation day with unchanged ledger events, exact screen/download parity, slow/failed report requests, object URL revocation, and report-only print layout. The connected browser journey must exercise actual forms and local API persistence.

### Local engineering evidence

- Combined Python/unit/HTTP suite: **279 tests passed** in 40.641 seconds. This includes the actual report/task API composition and rejects malformed task statuses with HTTP422 without changing the record.
- Focused report/task projection suites: **32 passed**. Final browser-client behavior suite: **21 passed**, invoked by the four passing Python UI contract tests. The client tests were extended after the combined run; the final hosted suite rechecks the complete tree.
- Test-first checks observed missing report/task sections, missing text payload, stale report actions, pending-write races, global-write races, and malformed-status disconnects before their respective fixes.
- Independent engineering review found the malformed-status and shared-evidence invalidation defects. Both were corrected; the reviewer found no remaining code blocker after targeted re-verification.
- The local environment has no usable Chromium executable. The browser test is executable in the existing hosted Chromium workflow and must pass there before a browser verification claim.

The integration PR records the exact hosted commit, run links, actual browser result, and any correction history. The workflow archives its exact source-under-test, test logs, and synthetic report PNG/PDF. Original component tests passing separately do not establish that the composition passes. This remains engineering verification of an unmerged synthetic workflow, not clinical validation or release approval.
