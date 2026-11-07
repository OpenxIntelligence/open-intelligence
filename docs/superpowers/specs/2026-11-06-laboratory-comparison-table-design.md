# Laboratory comparison table — bounded UI continuation

## Intent
Continue the existing diagnostic-workspace owner from PR #568 on the connected-product candidate, PR #602 at `2e37d7579f3d748dfe2918a1ec4d02872e0e625c`. Make multiple source-reported laboratory results easier to inspect without creating a new patient record, an interpretation service, or another specialty branch.

## Scope and approach
Retain the existing card layout as the default and add an explicit Table view with the same exact-code, source/specimen and result-state filters. The table uses the existing authorized World Model projection and original action callbacks. Show record-level counts as counts, never as completeness or health indicators. Keep literal units, values, dates, absent reasons, document versions and provenance.

Considered a separate lab dashboard and a chart-first redesign; neither is needed for this step and both would overlap existing analytical work. Extend the current browser instead. This implementation choice is a continuation proposal, not an architectural adoption.

## Constraints and acceptance
- React/Vite/TypeScript, unchanged runtime dependencies, backend and permissions.
- Fictional data only; absent is not negative; no normalization, ranges, trend arrows or clinical scoring.
- Default cards and all source actions remain available. Table has caption, scoped headers, keyboard-focusable horizontal scroll region and per-row provenance.
- Layout switching retains filters and page. Filter changes reset page. Shrinking data cannot leave a nonempty set on a blank out-of-range page.
- Case/patient/session clearing remains owned by existing session and access-receipt keys. No persistent storage or new requests.
- Verify controlled rendering, keyboard/mobile overflow, unusual source text, repeated bundle-local references, exact values and absent reasons.
- The initial local-only handoff is preserved as a historical checkpoint. This continuation may publish an isolated dependent draft for exact-head verification; donor branches and main remain untouched. No merge or deployment.
