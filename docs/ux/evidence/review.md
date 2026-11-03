# Independent frontend review and resolution

Date: 2 November 2026 (America/New_York). Scope: H1 presentation/tests/documentation only.

## Review method

An independent agent inspected the full source diff, design decisions, real-browser assertions and saved screenshots against the inspected #200 baseline. It did not independently rerun the client suite and did not provide merge, clinical or accessibility certification. A separate agent executed the retained reference regression suite and inspected final captures. The primary agent executed the frontend/client/build/browser checks.

## Findings and completed corrections

| Finding | Evidence before fix | Correction | Executed verification |
| --- | --- | --- | --- |
| Important: Overview said no clinical record was loaded after sources were retained | `review-red-browser.txt` fails the Overview assertion after loading and returning | Hide the successful identity-read status whenever a source index is present; errors/loading remain visible | Navigate Home then back to Records; identical sources retained with no extra request |
| Keyboard Clear filters removed the focused button | Same pre-fix run reports the focus assertion | Focus the source-filter input when clearing | Native Enter activation from the focused clear button restores all versions and returns focus to the input |
| Expiry check began after a denial had already cleared sources | Independent inspection identified weak precondition | Reload real cases/sources and assert 2 versions/1 quotation before expiry | Expire credential and refresh; identity, source index, rows and quotations disappear; reconnect remains available |
| New stress check: maximum accepted case heading overflowed at 320px | `long-source-red-browser.txt`: case heading right 354.95px on 320px viewport | Constrain and wrap the section-heading child | Full journey passes with 40-character case/document IDs, 128-character source organization and 1,200-character quotation at 320px |

Current source versions also precede historical versions. Statements are matched by exact source ID and remain literal text. Historical rows explicitly state that their quotations are not supplied by this response.

## Final evidence

The initial remote implementation head `4718c9003193bd936ecede16ae180adfbd41e9a9` has tree `0ab810415d82f04bc8b37d5bea01ac214a63188d`, exactly matching the local validated checkpoint. Final presentation files retain the SHA-256 values in `boundary-report.json`; subsequent documentation commits do not change them. [Draft PR218](https://github.com/OpenxIntelligence/open-intelligence/pull/218) provides the hosted head/check history.

- 24 client tests passed; TypeScript and Vite build passed.
- Actual Chromium/FastAPI/PostgreSQL 16 journey passed, including source history, case switching, filter scope, expiry, revocation, cross-organization denial, reload clearing, keyboard recovery and sticky focus at 320/390/768/1440px.
- No observed uncaught JavaScript or console.error events in that journey.
- 245 retained-reference tests passed in a separate unchanged-source run.
- Independent screenshot inspection covered 8 final captures; the 320px stress capture has a documented partial case-eyebrow crop at the observer's scroll position, while patient context, source heading, filters and document identifier remain readable.
- 198 protected files are byte/mode-identical to reconciled parent `68935c9fc60ef229aa9ff6cc4238153dc01a9b91`.

## Bounds

The browser uses independent fictional data and operator-owned synthetic grants. It does not demonstrate real patient/clinician roles, production identity/consent, clinical correctness, screen-reader usability, full WCAG conformance or field performance. Two cases for one patient are exercised; maximum accepted patient/organization identity strings and switching between two loaded patients are not established by this browser run. Existing client tests cover late-response and patient-scope isolation. No participant study or efficiency improvement has been measured.
