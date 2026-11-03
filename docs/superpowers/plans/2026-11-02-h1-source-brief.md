# H1 source-linked brief implementation plan

**Goal:** Let an authorized H1 user download a readable, exact-source brief of the World Model currently inspected, without implying clinical review or copying the older report authority.
**Architecture:** Extend existing #216 FastAPI/PG16/React source-owner workspace. One deterministic renderer and a read-only, separately authorized POST; original patient/source/PWM contracts remain authoritative. No schema, dependency, model or review transition.
**Spec:** OI-007/008/009/010 and current founder mandate; first-class original/source uncertainty and traceability. This source-only brief is not the biomedical investigation/report receipt from #203.

## Scope and decisions
- Use exact `source_snapshot_sha256` from the inspected World Model; re-read actual sources before preparing, and recheck source state and current authentication before returning.
- Require `patient_read`, `source_read`, and separately `source_brief_export`; fail closed for wrong case, revoked binding, changed context, invalid input or oversized result.
- Export literal UTF-8 plain text, not rendered HTML or clickable source content. Include original IDs/hashes/lines/dates, reported states, unresolved findings, source disagreements, historical versions and explicit unreviewed/synthetic boundaries.
- Keep output transient in the tab; never persist tokens or report text to browser storage. An exported copy cannot be recalled. No completed-review/delivery/audit-write claim.
- No reinterpretation, AI call, actual clinical data, licensed external content, source-body download or clinical endorsement.
- Read-only source preparation is not fully atomic with the final network delivery. Current synthetic auth is not real identity/consent.

## Review focus
Wrong-patient and stale/ABA responses; no implicit export from read grants; source changes while preparing; literal markup/control-like text; bounded output/no partial brief.

## Tasks
- [ ] Add failing renderer and endpoint/PG16 tests using existing source fixtures, plus client race/denial checks.
- [ ] Implement bounded renderer, existing-authority API composition and typed manifest.
- [ ] Connect source-brief action/preview/download to existing React Investigations panel with context guards.
- [ ] Run focused checks and unchanged regressions; publish narrow draft against #216 and inspect exact-head PG16/browser CI where available.
- [ ] Record tested source, results, remaining limits and source-owner reconciliation without auto-merging.

## Execution checkpoint

Renderer/API and typed client implemented and locally checked. Actual PG16/full React/browser verification remains a hosted gate; see `docs/engineering/H1_SOURCE_LINKED_BRIEF.md`. No local PG or browser pass is claimed.
