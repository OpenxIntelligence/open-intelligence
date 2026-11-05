# Keyboard reading across laboratory and text originals

4 November 2026. Frontend-only continuation of OI-010 and the existing laboratory
workspace, with independently authored fictional inputs.

## Pinned composition

- Immediate parent #472: `2ccdfad6aeba3cb3378c4648f4dba3df604cc554`, tree
  `581ebd976ddbe9bbd924ebd623f03b85d97ae91e`.
- Existing navigation/source-entry/local-preview donor #450:
  `3fb6655f9e317dd2a4dd58e3e088e38cb39f7b21`, composed on #443.
- Donor comparison base: #413 `e3259bb2986206e4a7edf8bc3a29546471077beb`.
- Laboratory keyboard test checkpoint: `c3196620db0a92888e9c5f386bc43e77dd556e81`.

Source comparison establishes that #472 retains the laboratory importer, typed
Journey results, exact current/historical originals and uncertain-import retry,
but omits #450/#443's final navigation/source-entry and text-preview access.
Its laboratory preview uses the same bounded original-text class without the
explicit named keyboard target or focus positioning of the established reader.

## User behavior and scope

The intended composition preserves Change section, explicit source-history
entry and local text-preview inspection. Laboratory JSON receives the same
named, focusable, viewport-bounded reader. Native Tab enters it, PageDown reads
overflowing text, and Tab exits to the existing report-version selector.
The preview remains local; reading never confirms a file or imports it.

Only the six specified frontend/test paths from #450's delta are reused; its
older tree, historical documentation and backend are not copied over #472.
The new laboratory control, source metadata, retry behavior and image dismissal
remain intact. The laboratory preview adds presentation attributes only.

Backend, API, schema/migrations, permissions, RegistrySession, source parsing,
validation, clinical/business rules, dependency locks, workflows and the
reference application are unchanged. Sibling preparation and manual-task
integration branches remain separate.

## Acceptance

The parent local baseline passes 510 client tests, TypeScript/Vite build and 13
dependency controls. The existing >500 kB chunk-size advisory remains.

Tests-first run `41925236534` failed at the intended accessible-name assertion
against unchanged runtime: Chromium could focus the preview but its accessibility
tree had no named local-reader region. Client/build/rights checks passed; the
new assertion stopped before the short-height check. The baseline artifact is
`13368089363`, SHA-256
`5cad1424f636d083114adddfd59ea6c6ffc14ea4b722449c2339290187a40b6a`.
Final acceptance must run the same assertion and all inherited browser checks
on the completed composition, including:

- Native keyboard reading with 32 px text at 390×844 and 320×256; the whole
  reader visible below patient context and an accessible local-preview name.
- Exact JSON bytes, unchecked confirmation, disabled import, zero browser
  requests and no canonical source before deliberate confirmation.
- Existing text-preview keyboard inspection, source-entry cancellation and
  Change section state/request preservation.
- Laboratory import, lost-response exact retry, same-patient authority recheck,
  typed zero/negative/absent values, amendment history, exact originals and
  independent original/projection denial.
- Existing document/image/manual-passage question/report and review journeys.

The current PR and canonical Notion/Drive UX records will hold the final head,
run, downloaded artifact digest, source comparison and inspected captures.
This source checkpoint does not claim completed hosted acceptance. No final
source edit may be treated as verified by an earlier run.

## Limits

This is synthetic frontend software verification, not independent usability,
complete WCAG, cross-browser or clinical validation. It does not qualify the
separate backend recovery, identity/consent, owner/security/rights or release
gates. Draft, unmerged and undeployed.

## Window resize during active reading

Consolidation #481 brought the #473 reading workflow into main. Its browser
coverage enters the reader after each viewport change. Follow-up #505 exercises
a different sequence on main revision `62e218e1e2bd6996bb126fcc1ea956fcf18199e6`.
The user presses PageDown, keeps focus in the reader and changes the window
height from 844 to 256 pixels and back at a fixed width of 390 pixels.

[Baseline run 41965828560](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41965828560)
reproduced the failure. With the window 256 pixels high, the focused reader
occupied y=360.5–544.5 while retaining its internal scroll position of 339.
The workspace now measures the focused reader after applying its header inset
and scrolls the surrounding page when the reader falls outside the visible area.
The connected browser test checks focus, internal reading position, full
visibility, confirmation and request counts through both height changes.
[PR #505](https://github.com/OpenxIntelligence/open-intelligence/pull/505)
records the hosted results for this follow-up.
