# One H1 source-reading experience — convergence receipt

**Date:** 3 November 2026. **Product:** Open Intelligence. **Status:** implemented in draft #329, not merged or deployed; independently fictional test data only.

## Decision and source ownership

Migrate the **proven** source-adjacent, version-aware React reading behavior into the existing patient/source/question/evidence/report/follow-through H1 application, rather than make another standalone UI or copy the `web/` DOM controller from reference #183. The parent is [#315](https://github.com/OpenxIntelligence/open-intelligence/pull/315) at `58bc5f7bc5b8c5ba39e4d93768031aa22cedacd9`; all its backend and client domain contracts remain the authorities. The reading donor is [#310](https://github.com/OpenxIntelligence/open-intelligence/pull/310) at `c5dc8ab90398d7a509c88ca8c3d926a0788e5419`, itself extending [#305](https://github.com/OpenxIntelligence/open-intelligence/pull/305).

This is a presentation migration only. The existing `RegistrySession` remains the **one transient client adapter**, while FastAPI/PG16 continues owning patient, case, original source, World Model, authored questions, citation metadata, evidence comparisons/reports, review and follow-through. Patient/clinical *reading density* is presentation only, not a grant or verified professional identity.

## Bounded source-level change

- Reused `SourceReading` from the verified #310 owner with only the existing integrated action test ID adapted to `ask-source-question`. This component presents loaded versions, in-response local filters, adjacent current literal quotations, historical source clarification, exact SHA/ID/version details and original-read action without issuing its own HTTP requests.
- Integrated it into **existing** `apps/web/src/main.tsx`; the old flat source list and detached finding section no longer compete with it. The existing patient context, draft/review/evidence state and data-client implementation are not forked. Added the source owner's presentation-only patient/clinical preference and responsive identity/context header, plus focus-on-navigation behavior.
- Transferred the narrow responsive/provenance CSS patterns without a new dependency, font, role authorization or design-system rewrite.
- Reused the real PostgreSQL/React/Chromium `reading_convergence_journey.py` from #310 with its source-action selector adapted to the existing combined app. It runs at the amended source point **before** the inherited question/evidence/report/review/follow-through flows, preserving those original tests.
- Fixed misleading Overview wording: after original sources are actually loaded, the UI says source information exists separately but does **not** establish a reviewed clinical conclusion.

## Actual verification trail

| Exact commit | Hosted run | Observed outcome |
| --- | --- | --- |
| `2db3a2fbfc85b93c6f1efae7d4cf970c8e6868c2` | [41666787127](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41666787127) | Tests-first red. Inherited client/build passed; real PG16/Chromium reached the new reading journey and failed at the **missing source filter**, as expected. |
| `715fdc3889bb6924a9f15f1e920404e99715b3bc` | [41667483117](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41667483117) | Typed client/build passed, browser progressed beyond the filter and found **Overview contradicted loaded sources**; it was corrected, not waived. |
| `9cce996f0bee0c1aeebcd1035d58036da1095dd4` | [41667838706](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41667838706) | **COMPLETED SUCCESS**, 274/274 typed client tests, pinned TypeScript/Vite build, dependency notices, real PG16/FastAPI/Chromium entire journey. Source filter/reflow/provenance, exact fresh World Model question handoff, permission denial/reconnect, quote history, saved questions, citation metadata, authored evidence/reports, review and follow-through all passed. |

The final hosted run also logged `PASS READING QUESTION HANDOFF` (one fresh source-scoped World Model GET, no implicit Composer/model execution or write) and `PASS READING CONVERGENCE` (current/historical separation, filters retained without extra requests, 320/390/768/1280 widths, keyboard and larger-text checks). The full preexisting source, question/evidence, review, follow-through, binding revocation, cross-patient and original-intake browser checks continued to run.

The parent #315 separately passed [API/PG16 41661435587](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41661435587) (416 tests, 287 reference regressions and recovery probes) and [React 41661435637](https://github.com/OpenxIntelligence/open-intelligence/actions/runs/41661435637). **Do not** misattribute parent backend acceptance to this frontend-only child; no backend file changed here.

## Unresolved gates

This fixes a clear product-experience parity gap; it does not establish patient/caregiver/clinician accounts, trusted authorization, clinical review, licensed literature rights, real source interoperability, AI medical interpretation or production release. Source code still awaits independent human review, actual patient/clinician usability research, native assistive-technology evaluation, extended browser coverage and explicit parent-first integration. The preceding draft source owners and main remain untouched. No merge or deployment is authorized by these software tests.
