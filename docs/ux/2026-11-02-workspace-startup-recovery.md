# Recoverable workspace startup

**Work package:** OI-010, Gate 2 of the existing UX convergence plan.  
**Starting point:** PR #183 at `18c494fb998d1fe9878cce2ca730480f8ba60553`, on #166 at `334d863b2206b290c02cd2606dcb93c93afe3a68`.

## Problem and outcome

A failure of the first `/api/cases` read currently leaves Refresh list disabled and the canonical case-picker listener unbound. Empty, loading and failed startup all have no selected case, but require different explanations and next actions. The connected adapter currently infers an empty roster from heading strings. A second initialization after creation can also race an older startup read.

The user should be able to retry a failed initial read without reloading, retain the intended destination and entered setup fields, and reach the existing chart and intake workflow. A proven-empty workspace must remain refreshable so cases created elsewhere can be discovered. Creation that has already succeeded must not require another POST merely because the following list read failed.

## Chosen approach

Keep the existing initializer as the only owner that establishes initial selection. Add a small explicit startup phase and generation, representing request/presentation state rather than another case store. A globally visible status and native retry/refresh button remain available outside case views, including patient deep links and empty connected setup. The existing worklist refresh action delegates to initialization while no case has been selected.

Bind the existing picker handler once. New initialization generations supersede older roster and board work before they can change options, selection, errors or startup status. Preserve a newly created case as the intended initial selection. Build the worklist before enabling the initial chart, retaining the existing accepted-response projection guarantee.

The connected creation callback reports whether its successful POST was followed by activation. If loading fails, the creation status states that the workspace was saved and directs the user to retry. Retain that activation intent and complete the original source-intake navigation after a successful retry, without resubmitting creation. A later accepted selection cancels obsolete activation intent.

### Alternatives considered

- Merely enable Refresh list: insufficient because the board reader deliberately does not establish canonical selection or its listener.
- Share only an in-flight initialization Promise: insufficient because creation can complete after that request captured an older roster.
- Disable all creation until startup succeeds: smaller concurrency surface, but blocks useful existing creation behavior during a transient read failure. Generation ownership preserves that behavior.

These are implementation decisions within the user's authorized continuation of the existing frontend scope. The live overlap audit found no equivalent startup repair in #192, #218, #232 or #246. H1 reading, patient attention and domain-summary expansion remain with their separate owners.

## Acceptance contract

1. Distinguish loading, unavailable, proven empty and available roster states. Neither a failed read nor a pending read may imply there are no cases.
2. Provide a visible, keyboard-operable retry outside all forms and case views. Pending attempts disable the action and expose loading state; failure remains recoverable without page reload.
3. Retry preserves the current route/presentation, search and entered setup fields. A successful retry clears only its own startup error, leaving unrelated notices intact.
4. Successful initial reads create unique picker options, select through the existing owner, and bind its handler exactly once. A later native case selection causes one canonical state read and retains all dirty-work/source protections.
5. An already established case owner cannot be reset by a repeated initializer or a late startup completion. It remains protected by `readyCase`, `refreshSequence` and the existing selection event.
6. An empty connected workspace offers creation and a reachable refresh action. Another session's created case can be discovered and opened.
7. Creation during a delayed initial read supersedes that older read. Its late success or error cannot replace the created case, append duplicate options or change the newer status.
8. If initial creation succeeds but its follow-up roster read fails, retain the saved creation and intended case. Retry activates it without another POST or misleading readiness claim.
9. Roster success remains distinct from selected-chart readiness. Preserve existing case-state failure/Open recovery and per-case summary error semantics.
10. Preserve all original form fields/validation, source bytes, backend/schema/API contracts, processing/review rules, dependencies and fictional fixtures. No polling, new endpoint or second record authority.

## Verification plan

Use real Chromium and the existing connected/standard launchers. Intercept only selected startup GET responses before a fresh page load to produce controlled HTTP/network/malformed/delayed outcomes; all successful reads and writes use the real application and server. Read persisted state independently over HTTP. Exercise initial failure/retry, repeated failure, delayed loading, patient deep links, empty creation/discovery, creation/read races, saved creation followed by a failed read, unrelated notices, one native selection listener and retained unfinished work.

Record an actual failing baseline before changing runtime code. Run the complete existing Python, JavaScript and browser gates, including navigation, case continuity, scope recovery and worklist currentness. Preserve actual failures, fingerprints and exact-source hosted evidence. The final published run is recorded in #183 after the source snapshot is committed.

## Boundaries

This repairs first-load presentation and activation through the current reference owner. It does not change authentication, H1 ownership, backend mutation rules, clinical interpretation or deployment. Existing post-start mutation completion behavior and external-session currentness still follow the documented worklist contract. Verification uses independently authored fictional records.
