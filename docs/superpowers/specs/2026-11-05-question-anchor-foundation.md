# Typed question-source anchors — bounded foundation for #428/#425

## Intent and scope
Continue the PR #503 preparation increment toward durable laboratory questions
without inventing text lines, a second question owner, or a second source ledger.
The user authorized continued engineering, not merge, deployment or clinical use.
This increment implements a reusable, immutable, scoped anchor contract and
integrates it into existing preparation and legacy question/task integrity checks.
It does **not** add laboratory persistence, a migration, a new API or UI.

## Baseline and execution limits
Work is based on the retained PR #503 source archive, remote source commit
`fcaf207d46b6fb99e735b0a417a5e2b552bcfa7e`, tree
`fe8b6ef291a600f905a2207818094c94ca21c4f4`. The archive checksum is verified.
Initial remote reads failed; local Git history was reconstructed, not presented
as remote ancestry. A later fresh GitHub read confirmed PR #503 remains draft,
unmerged, with the same exact head. The targeted open-PR search found no newer
typed question-anchor implementation. No current-main integration is claimed.
PostgreSQL 16 and the pinned complete runtime are unavailable locally. Exact-child
hosted acceptance and independent review remain required.

## Approach and alternatives
Use one discriminated identity contract over existing source ownership:
`text_line` or `fhir_observation`. Both require exact patient/case, source ID,
source version and source hash. Text requires one positive integer line. A
laboratory anchor requires local Observation, Specimen and DiagnosticReport
references and has no line. This is an implementation choice within the existing
next-slice boundary, not an independently approved architecture decision.
Encoding a laboratory resource as line 0/1 would falsify provenance. A separate
laboratory question table would split the canonical question system. Neither is
used. A complete persistence migration is deliberately a subsequent reviewed slice.

## Invariants and acceptance
- Immutable strict models; reject unknown/mixed fields, boolean/string numeric
  coercion, external/history/wrong-kind references and incomplete anchors.
- A syntactically valid anchor conveys identity only, not currentness, custody,
  source access, consent, clinical review or permission to write.
- Existing text and laboratory preparation wire payloads and preflight hashes
  remain exactly unchanged for representative independently fictional fixtures.
- Existing text question intent hashes, current/stale history and task output
  remain unchanged for valid fixtures; malformed legacy anchor types fail closed.
- Explicit adapters never infer a laboratory anchor from a missing text line.
- Do not change migration history, schema readiness, routes, action grants,
  dependency pins, source values/units/dates, review state or frontend contracts.

## Next persistence gate, not implemented here
Review an additive migration of the existing question and task tables together;
retain old fingerprints and all historical rows. Add typed save/read/revalidation,
reports, review and follow-through; then exact retry, wrong-scope/ref, late denial,
amendment, populated upgrade, restart/restore and actual browser acceptance.
Synthetic software checks do not establish clinical validity or real-patient use.
