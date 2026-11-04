# H1 laboratory reader resize repair

Continuation of draft #482. Synthetic-only; no merge, deployment, new dependency, data access or clinical qualification.

## Failure retained

Initial combined head `7f66531546a9381e06907dce766c61e2f17edd8a` passed the client/build step in web run `41930142641`, then failed the actual PostgreSQL/FastAPI/Chromium journey at `laboratory_fhir_journey.py:144`: the entire laboratory reader was not visible below the patient context.

Artifact `13371526497` was downloaded. SHA-256 `4d33e2797cefd68be1f76d1be4e5013724fa4c355310420943b23a10a4818a49` and its commit marker match the initial head. Both retained preview screenshots and their geometry JSON were inspected:

| Viewport | Focus | Reader top/bottom | Context bottom | Outcome |
| --- | --- | --- | --- | --- |
| 390 x 844 | Reader | 360.5 / 750.5 | 243.5 | Visible |
| 320 x 256 | Reader | 257 / 441 | 0 | Below viewport |

Both rows retain zero requests/writes and unchecked confirmation. The failure is rendering, not a source mutation, permission issue or missing hosted dependency. Earlier journey components printed their passes, but the complete browser acceptance failed.

## Root cause and bounded change

The existing WorkspaceContext measures its height on resize, changes sticky state and updates the CSS reading offset. This changes the reader height and scroll geometry after native focus may already have scrolled the reader. The old measurement callback never rechecks that focused reader.

The correction in `apps/web/src/main.tsx` checks only the currently focused `.original-text` after measurement. If its rectangle is outside the visible area below the sticky header, it calls the existing centered scrolling behavior. It does not move focus, reset the inner reading position, fetch data, write records, change approval state or alter authorization. Unfocused readers are untouched.

The original failing hosted browser assertion remains unchanged, including native Tab/PageDown/Tab, accessible naming, exact text, zero requests/writes and unconfirmed import. No timeout or tolerance is relaxed. All backend, migrations, permissions, dependencies and workflows retain the initial combined bytes.

## Local evidence and limits

A local Chromium fixture on about:blank uses reconstructed fictional markup, existing CSS and the exact old versus corrected measurement logic. Across two repetitions of 390 x 844 -> 320 x 256, old logic fails: the short-screen reader reaches top 239.5 / bottom 423.5. Corrected logic passes all four transitions; its short-screen rectangle is top 47.5 / bottom 231.5. This is a browser layout diagnostic, not the React/PostgreSQL application journey.

The four new laboratory/manual-task RegistrySession tests also reran and passed (0 failed/skipped). Existing 103 focused-client, 8 parser and 13 dependency-gate control results belong to the initial composition; they are not additional distinct tests or full corrected-head acceptance.

Diagnostic setup history: a separate retained-built-UI localhost probe was blocked by this environment's browser URL policy. No bypass was attempted. The first local markup fixture failed from a duplicate top-level JavaScript const; it was corrected before recording the genuine behavioral red/green runs. Python/React/PostgreSQL dependency limitations and earlier local suite failures remain in the original local-results record.

## Source identity and acceptance

The original source-reuse manifest describes the initial 19 exact donor copies. This correction deliberately overlays only `apps/web/src/main.tsx`; the other 18 donor files remain byte-identical. The initial two-parent Git ancestry is preserved. The only other changed path is this additive repair record.

Fresh corrected-head hosted API/recovery and React/build/browser verification remains required; neither the old client pass nor either parent's green run qualifies the correction. Independent review and explicit human merge/release decisions remain open. The dedicated populated-manual-dependency restore and typed lab-observation-to-question binding remain separate work.
