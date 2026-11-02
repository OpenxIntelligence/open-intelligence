# Source-derived Patient World Model projection — synthetic engineering slice

Status: **Proposed / implemented on a draft branch; not merged or authorized for PHI**  
Tracker: [#116](https://github.com/OpenxIntelligence/open-intelligence/issues/116) (WS-04, patient world model)  
Source owners: existing `CaseStore.state(case_id)`, original source versions, assertions, questions and investigation snapshots  
Contract: `oi.synthetic-world-model/1`  
Local-only endpoint: `GET /api/cases/{CASE-ID}/world-model`

## Product purpose

This provides a narrow, actual API projection of a case's current observations, original document/version/hash/line, specimen identifier, the distinct event/issued/received times, source history, bounded within-specimen disagreement and the review-needed questions/snapshots. It is a starting point for an integrated patient-first workspace. It **does not add a canonical patient master or a source/fact ledger**. It reads exactly one existing `CaseStore.state()` transaction snapshot and returns no cross-case or globally pooled scientific evidence.

## Owner boundaries

1. **Facts**: `source_versions` and `assertions` remain the source authority. The output is explicitly a `source_report_only_unreviewed` projection. A finding is an authored statement, not a clinical diagnosis, negative assay result independently established by OI, or a clinician's decision.
2. **Identity**: `case_id` is a fictional demo identifier. `synthetic_world_model(state, expected_case_id)` denies a mismatched case. Real patient identity, validated source-system identities, consent and clinical authority remain with the corresponding first-party integration owners #85/#51/#53/#95.
3. **Time**: `event_date` (reported event), `issued_at` (document finalization), `received_at` (ingest) and current/superseded status are preserved separately. `as_of_ledger` reports the latest visible ledger receipt, not a historical as-of query or a bitemporal model.
4. **Specimens**: Same finding key is not an identity link. The narrow disagreement check requires the **same known specimen ID and same event date** plus explicitly opposing source-reported `reported` / `negative` states. Unknown specimens are never fused and longitudinal differences are not automatically classified as conflicts.
5. **Amendment**: Current assertions come from current source versions only. Older source refs remain in `history`; case-specific draft/stale snapshot references are surfaced from existing review ledger; no new clinical interpretation is promoted.
6. **Security and content rights**: Only the current loopback-only synthetic demo may serve this endpoint. It is unauthenticated and **must not** process PHI or be exposed as a production route. External evidence, restricted clinical guideline text, patient biographies and unverified model claims are deliberately absent.

## Test acceptance

`PYTHONPATH=src python -m unittest discover -s tests -p 'test_synthetic_world_model.py' -v`

Tests assert actual original fixture references and three time facets, uncertainty versus explicit negative, amendment-version preservation, no cross-specimen grouping, one intentionally conflicting same-specimen report, case isolation, no source writes, current review/stale states, malformed snapshot denial and a loopback HTTP route. All fixtures are independently authored fictional cases.

Run the complete repository Python/HTTP + Chromium source/keyboard checks at the **exact draft branch head** and record the run URL and SHA. This contribution is not complete until CI and independent review; local or hosted synthetic tests do not establish clinical readiness.

## Next workstream integration (still open)

The actual clinical operational workflow in #95, original patient registry, encounter/note, LIS order/accession/QC/release, source adapters, review receiver, and rights-qualified knowledge/Composer #130/#132 must be reconciled under **one signed patient/case/source and authorization contract**. Later PWM extensions must add assay, genome assembly, allele/variant identity, specimen/lesion lineage and as-known-at bitemporal queries from real source metadata; do not infer them from source text or create shadow operational tables.

No new dependencies, migrated database schema, unsupervised AI agents, medical recommendations, PHI, prohibited source, real-patient data or clinical action were added.
