# MRT-01 coverage matrix, scoped slice for issue 121 (WS-15)

This matrix maps MRT-01 steps to real tests on main at 2451983. It
never invents coverage: a step is covered only if a named test in
tests/test_121_mrt01_journey.py exercises it, and every other step
is listed as not covered.

## Covered by this slice

- Three fictional institutions ingest: test_journey_three_institutions_amendment_staleness_review, three import_report calls, all imported.
- Conflicting finding presence, not adjudication: the amended report changes marker-a from reported to not-reported; the store records both versions, it does not adjudicate between them.
- Source amendment: same document amended at version 2, previous version superseded.
- Targeted snapshot staleness: the old snapshot id appears in invalidated_snapshots and its state becomes stale; the other sources are untouched.
- Human review, demo only: acknowledge_demo_review moves the new draft to reviewed_in_demo.
- Mismatched subject quarantine: test_journey_wrong_patient_quarantined, patient_mismatch, quarantined, never asserted.

## Not covered by this slice

- Real identity, consent, or authenticated API access.
- FHIR or HL7 ingestion; FP-01..04 bundles are not in main.
- Live retrieval, real model inference, or external publisher grants.
- Professional sign-off; demo acknowledgement is not a clinical signature.
- PHI security or production deployment.
- Playwright browser journey; this slice is a unit journey only.
- World-model integration, genome assembly, or assay lineage.
