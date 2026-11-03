# Frontend patterns (vanilla stack)

Date: 2026-11-03. Scope: the CURRENT stack only — Python stdlib + SQLite +
vanilla JS/CSS, no build, no dependencies, no React, no Tailwind (all rejected
or gated per `coordination/frontend-technology-evaluation.md`). This document
formalizes patterns already established in `web/app.js`; it proposes no new
behavior. The user is "the user" — never a personal name.

## 1. textContent-only rendering

`node(tag, text, className)` (`web/app.js`) is the single element helper: text
goes through `textContent` only. `innerHTML`, `insertAdjacentHTML`, and `eval`
are forbidden anywhere in `web/`. Imported report/evidence bytes are painted
as text (`renderOriginalSource`, `renderReportLineComparison`) — a `<mark>`
highlights the anchored line without reparsing the bytes as markup.

## 2. Case-switch sequence guards

Two counters, one rule: never render a response that no longer matches the
selected case and view.

- `refresh()` captures `requestedCase` + `refreshSequence`; a response renders
  only if both still match.
- Source/evidence/comparison reads share one intent: `beginSourceRead()`
  captures `{caseId, sequence}`, `sourceReadIsCurrent()` re-checks before every
  render or notice. This catches same-case reordering and A→B→A round trips,
  which a bare `caseId` check misses.
- The picker `change` handler blocks switches while a narrative draft is
  unfinished; otherwise it calls `cancelSourceRead()`, clears drafts, closes
  dialogs, and reloads. `readyCase()` throws while loading; every write path
  captures its return before requesting and re-checks after.

## 3. Dialog open/close contracts

Native `<dialog>` only (`#source-dialog`, `#compare-dialog`) — no custom modal
divs. `showSourceView(id)` closes the other dialog, then `showModal()`s the
requested one. Every close path cancels the read intent first
(`cancelSourceRead()`): both Close buttons and native Esc. Esc is handled via
the `cancel` event, never `close`, so a queued programmatic close cannot kill a
newer read. A stale read renders nothing and raises no notice.

## 4. Notice-bar usage

`notice(message, isError)` writes the single `#notice` live region
(`role=status`, `aria-live=polite`). One message at a time, errors flagged
with `.notice.error`; there is no toast stack. Form errors surface here, never
via injected markup.

Forms (all handlers): `preventDefault` → `readyCase()` → `api()` → re-check
`requestedCase === caseId` → clear inputs → `notice()` → `refresh()`.

## 5. Tokens and color discipline

Primitives live in `web/tokens.css` (space, type, oklch color, fonts,
container, radii). Semantic aliases name MEANING, never a component, and
reference primitives via `var()`.

- Freshness (review state, "needs another look"): `--color-freshness*` — calm
  amber. Covers `pill-warn`, `pill-alert`, the needs-review wash, and the
  source-line highlight.
- System error (failure only): `--color-system-error*` — red. Covers
  `.notice.error`. Never used for staleness.
- Current ("no review flag set"): `--color-current-*` — deliberately neutral,
  never green. Fresh is not good; current is not approval.
- Info (neutral messaging): `--color-info*` — covers `.notice`.
- Review prose + dialog + geometry: `--color-review-ink`,
  `--color-dialog-backdrop`, `--space-dialog-pad`, `--radius-card`,
  `--focus-width`, `--focus-offset` (values match current rendering).

Rules: two-consumer rule for new tokens; no literal color/spacing outside
`tokens.css` except commented `color-mix()` derivations; oklch stays.
Note: `pill-alert` is a historical class name inside the FRESHNESS family (amber,
not red). A future rename is owner-track work; do not restyle it red here.
`style.css`/`base.css` still consume primitives directly; migrating them to the
aliases is a reviewer-owned step (values are identical by construction).

## 6. JSDoc convention (TypeScript later)

`api()`, `node()`, `render*`, guards, and dialog entry points carry
`@param`/`@returns`; the `/state` payload shape is a header `@typedef`
(documentary — the server owns the shape). Keep `node --check` green; no
`tsconfig` yet. The `vm`-slice tests read `web/app.js` as text between
`renderOriginalSource` and `downloadSnapshot` — keep those markers and keep the
region side-effect-free (comments only).

## 7. Visual reference

`web/style-tile.html` opens via `file://` (relative `./*.css` links, no JS, no
fetch) and shows every token plus the core components: buttons, forms, cards,
status indicators, dialogs, notices, and empty/loading/error states. Tables and
tabs appear there as clearly labeled PROPOSALS — the app has no grid or tab
component today. The tile is review-only: no nav link, no server route, no
backend change.

## 8. What was NOT changed; open reviewer items

No rendered value, route, schema, API, auth behavior, or copy changed in this
slice. Not verified here (no execution in this sandbox): visual rendering of
the tile and app, contrast ratios of the oklch tokens, axe pass, screen-reader
/ keyboard / zoom / print behavior, `node --check`, and the full test suite.
All are open reviewer items.
