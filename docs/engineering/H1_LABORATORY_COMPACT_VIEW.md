# Open Intelligence — compact laboratory view

## Current continuation

This candidate carries the earlier local Labs patch onto connected-product PR #602 at `2e37d7579f3d748dfe2918a1ec4d02872e0e625c`. It preserves Visits, Labs, Imaging, Pathology, Molecular, source questions, follow-through, durable execution and patient suspension. It does not replace their owners. Tracks the existing GH-119 / OI-007 / OI-010 user-workflow work.

## Behavior

Cards remain the default. Table uses the same exact LOINC, original/specimen and result-state filters, server ordering, 25-row pagination and original action children. Counts describe loaded records only. Literal numbers, units, times, absent reasons, source identifiers and digests remain unaltered. A stale page clamps after results shrink.

The table has a caption, scoped headers, named keyboard-focusable scroll region and expandable provenance. Layout switching preserves filters and page; the existing access-receipt key owns clearing and reset. Scoped component CSS preserves the shared stylesheet byte-for-byte; the filter rule's specificity makes three-column layout independent of stylesheet order.

No dependency, API, database migration, authorization owner, inference, unit conversion, clinical assessment or external service is added.

## Verification before publication

- The downloaded #602 artifact (`13556119029`) matches SHA-256 `20b27e58536c2a39af5fe2b33b79901210405e181510d9b6ce741cc10d85f770`. Reconstructed source tree matches `1582c686199ad7e4ba873c48063b26f895e145a6`.
- 707 locally executable client tests pass, including 12 projection regressions. Client type-check passes with available TypeScript 5.8.3, not the pinned 5.9.3 compiler. Seven Vite/React server-rendering suites require hosted execution.
- 14 Chromium component checks pass using the archived exact React 19.3.1 runtime and locally transpiled changed source: CSS ordering, cards/table, pagination/filter retention, literal values, escaped text, exact action callback, widths 320/390/768, clearing and access-receipt reset. The stylesheet-order regression was observed failing before repair. This is an in-memory fictional component test, not a backend-connected application.
- Four table/server-rendering regressions are included for the normal pinned-toolchain suite. No test is disabled or skipped in the repository.

## Acceptance boundary

The initial handoff was local and unpublished. This continuation is prepared for an isolated dependent draft so the existing pinned dependency-rights, full client, production-build and actual PostgreSQL/FastAPI/browser checks can run on its exact commit. Those results must be read from the candidate's own runs; #602's results do not qualify this change.

No merge, deployment, independent reviewer approval or clinical/production qualification is claimed. The complete shared foundation and clinical/scientific product remain under construction.
