# Open Intelligence — unified patient history and exact originals

Construction candidate; synthetic-only, draft/unmerged/undeployed. This record extends the existing G01–G24 roadmap and OI-009 second-time-point acceptance, without narrowing the full human/veterinary clinical and scientific platform.

## Frozen inputs and discovered integration defect

Parent is #640 `606e22a0fba78d52f4aec7cef0e44ec10d9ef565` (tree `1399a040ae77b5ed70ae9f5e9d1db66031a3246d`). Its ancestry includes #624 `631c3e0cea30d4b859a2e428d200d352c97c6567`, #620 `8d1b4b48400e8708ff4552c1b58c46f3821caa2c`, #618 `7f266e1c389c8a0a3d00111ba295ab0bc8186898`, #617 `842c2cd70c78e454d0233d753806c2155bf78858`, #615 imaging and #619 Composer binding. Persisted permissions, Labs, Imaging study/series and chronology, execution and follow-through remain in the connected candidate.

Inspection reproduced two `SourceHistory` class definitions in #640's patient routes. The later World Model wrapper shadows the metadata wrapper, so constructing the metadata response fails with a literal-contract mismatch, missing world_model and forbidden metadata fields. The merged test_source_history.py also replaces the six original World Model HTTP replay methods with the separate metadata suite. A textual merge success was not combined contract acceptance.

The concurrent #640 repair `11f09a3219201a4a9bb0baa08529e182de5af03e` renamed the duplicate metadata DTO/handler/operation and added an AST collision check. This follow-up explicitly incorporates that head as a merge parent, preserves its documentary record and adapts the collision check to the single canonical history route. It additionally restores the displaced World Model replay suite and eliminates the duplicated history client/API.

## Constructed behavior

One canonical GET `/v1/patients/{patient_id}/cases/{case_id}/world-model/history?received_through=...` now serves Journey and Records. It retains the existing `oi.pg-source-history/1` response, source version owner, source-reported observations and typed FHIR values. No schema, dependency, separate source ledger or clinical interpretation is introduced.

- Receipt cutoffs are strict timezone-aware RFC3339 with at most PostgreSQL's six fractional digits; future, naive, invalid calendar and lossy cutoffs are refused. Backwards receipt chronology in a document lineage fails closed.
- The client checks the complete returned source membership, hashes, dates and cutoff-relative version states against its currently authorized source index or World Model. Current context is kept separate from history. The two screens share one parser, state machine and view.
- Selecting a historical report resolves the exact original ID/version/hash through today's source reader and separately authorized original endpoint. Journey refreshes the source index before this handoff. Original permission denial never grants access through history; retry rechecks current rights, and independently authorized historical browsing remains available after an original denial.
- Refresh, patient/context changes, navigation, disconnect and later selections cancel/invalidate prior history work. Late transport replies cannot restore stale content. Original-reader focus returns to the initiating Records history action.
- The duplicate unmerged `/source-history` API, DTO/parser, state and component are removed. Its strict receipt precision, exact source matching, original navigation and recovery intent are retained in the shared path. Donor documents remain as historical records, explicitly superseded here.
- #619's exact current-snapshot Composer binding and all 35 tests remain byte-identical through #624. Before importing that fix locally, 21/35 adversarial checks failed; afterwards all 35 pass. This is a client integrity correction, not evidence of a backend authorization bypass.

## Verification and recovery gates

Local combined checks: 838 client tests passed, zero failures or skips; hosted results are recorded in the dependent PR. Locked production TypeScript/Vite build passed; dependency-rights gate passed 13 tests with no errors (two existing optional uninspected packages remain excluded). Local API/wire/recovery assertions: 38 discovered, 29 passed, nine actual PostgreSQL cases explicitly skipped because PostgreSQL16 is unavailable locally. No database pass is inferred from that run.

Focused hosted gate runs all nine historical HTTP scenarios, strict cutoff/wire controls and the original FHIR historical-value scenario, rejecting skips. The source Compose probe runs before the broad regression and checks exact historical context before/after amendment, API restart, database restart and backup/restore, independent current grants, revoked binding and unchanged original database. Recovery assertions independently account for the paired history-prepared/read-authorized audit events with a shared fresh receipt; every other business row, prior event and sequence remains checked.

The real React/FastAPI/PostgreSQL/Chromium journey checks one historical fingerprint across Journey and Records, exact superseded/amended bytes, original denial and grant, focus return, 390/1440 layouts and return to current Journey. Full locked client/build/rights, persistent demo, execution and API/migration/recovery suites must qualify the exact published head; donor success does not qualify this candidate.

## Resume and remaining construction

1. Inspect this draft's exact-head focused history/recovery, web/browser, execution and broad API results; repair actual failures before qualification. No main merge or deployment.
2. Reconcile #616 semantic projection and #629 purpose enforcement against this single source contract and the existing owners. Do not overlay an entire donor tree or reintroduce competing history APIs.
3. Reconcile advancing accepted main and remaining chart/diagnostic/episode comparison owners before merge review.
4. Full diagnostic, treatment, research/biology, trials, care operations, professional review, real-data identity/consent and clinical validation remain open. Historical receipt context is limited to supported structured originals and FHIR; manual document annotation history has its own existing owner and is not fabricated here.
