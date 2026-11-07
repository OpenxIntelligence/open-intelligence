# Imaging report chronology — bounded continuation

## Intent
Enable a clinician or patient using the connected Imaging workspace to locate an earlier report version by recorded event date without leaving the authorized case context. Extend PR #610's study/series display rather than create a second image ledger.

## Existing contracts and option chosen
`SourceIndex.sources` already contains permitted current and superseded source versions, source IDs, document IDs, dates and source kind. `SourceReading` displays each exact version and already has a section-scoped source query filter. We will use that projection alone.

A separate longitudinal DICOM API or clinical image comparison feature would exceed this increment's authorization and inference guarantees. A simple list of all sources already exists but does not present a compact imaging-specific chronology. Implement a derived view with a 'Show this report' action that filters to the exact source ID, reusing the existing original and image actions.

## Requirements
- Only sources with recorded `kind === 'imaging'` belong in the chronology. No cross-patient or cross-case query, new API, persistent state, or speculative linkage of different studies.
- Arrange by reported `event_date` newest first, stable ordering for ties. Group by date; do not infer trends or progression. Do not collapse separate document versions.
- Display each source's version, source-reported status and recorded issued date. Present a controlled source-ID action to show exactly that report in the existing reader; preserve current/superseded state and all original-image authorization boundaries.
- Keep a text-only empty/one-report state that doesn't imply completeness. Count *available report versions*, not imaging studies or lesions.
- Explicitly say that no longitudinal image comparison or clinical review is performed. Historical image pixels are not automatically loaded.
- No new runtime dependency, permission, backend, migration, release or real data. Fictional test input only.

## Acceptance
Pure projection tests: mixed source kinds, tie order, versions from one report, date grouping, empty and unchanged identities. React SSR tests: source-ID action, status, no hidden original controls/implicit pixel loading, empty state. Existing browser and backend workflows must run on the exact candidate, and a new real-browser check should target a prior report version using the already available source-index fixture when feasible.
