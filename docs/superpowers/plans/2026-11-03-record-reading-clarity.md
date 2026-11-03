# Record-reading clarity implementation plan

> For agentic workers: use superpowers:executing-plans to implement this bounded task.

**Goal:** make case actions identifiable and keep report reading focused on useful context.

**Architecture:** retain the existing React presenters, authorized case/source
responses and RegistrySession. Change only two presentation expressions; extend
the existing real browser journey over its two already-created fictional cases.

**Tech Stack:** existing React 19.3.1, TypeScript 5.9.3, Vite 7.3.7 and Python CDP harness.

**Spec:** `docs/ux/2026-11-03-record-reading-audit.md`.

## Global constraints

- Base: #382 at `0e243e175dfdfe6e6d055531032c3dc284a1adc1`.
- No dependency, API, backend, migration, authority or session-state changes.
- Keep specimen, dates, source version/state, finding key, line and review status visible.
- Keep exact source ID/hash/supersession inside the existing native disclosure.
- Preserve visible case-action text and the existing callback target.

## Review focus

Two cases must have distinguishable computed action names and activate the named
case. An identifier must stay within its authorized row. Current/historical
versions, source denial, navigation clearing and narrow/enlarged-text reading
remain covered by the inherited actual browser journey. No extra tests for the
purely presentational removal of a duplicate ID.

## Task 1 — case action identity and quotation hierarchy

Files: `apps/web/src/main.tsx`, `apps/web/src/source-reading.tsx`,
`apps/web/tools/record_intake_journey.py`, this plan and the audit.

- [x] Inspect the current source, authoritative instructions and OI-010 context.
- [x] Extend the existing two-case browser journey to choose by computed name,
  focus that exact DOM node, activate with Enter and require its own source index.
- [ ] Run the tests-only hosted checkpoint; observe the missing case action name.
- [ ] Add the case-specific accessible name and remove only the duplicate ID
  from the quotation footer.
- [ ] Run `npm test`, `npm run rights`, `npm run build`, Python syntax and diff scope checks.
- [ ] Run the existing hosted browser journey on the exact published head.
- [ ] Review the full bounded diff; record actual results and unresolved limits.

## Execution ledger

Scope decision: the supplied UX-01 implementation is mostly present; refresh its
audit and complete the remaining two presentation details. Existing working
Review and keyboard-reader behavior must be retained.

Pre-flight: no new shared interfaces. The action-name acceptance exercises the
existing two-case fixture after intake creates the second mapping; it introduces
no new patient or case setup. The production mutation it catches is a missing,
duplicated or mismatched case name/callback.
