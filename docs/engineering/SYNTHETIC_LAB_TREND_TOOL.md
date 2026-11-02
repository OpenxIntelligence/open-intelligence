# OI synthetic laboratory trend tool — engineering contract (C4 candidate)
**Status:** standalone deterministic code candidate. This is **not** an integrated Composer tool, production LIS, clinical analytics engine or validated medical decision support.

## Intended function
Read a canonical \`CaseStore.state(case_id)\` snapshot, identify current laboratory assertions for one explicitly named finding key, and calculate only the decimal difference between the first and last unique-day eligible values. Preserve all eligible source version, SHA-256, line, event, issue, receipt and specimen links. Never write to the source ledger, infer an assay, convert units, diagnose, interpret clinical meaning, imply QC verification or claim professional sign-off.

## Authoring syntax, intentionally not a general lab parser
An independently authored synthetic \`OI-SYNTHETIC-REPORT/1\` with \`Type: laboratory\` may contain a finding with an exact quotation:

\`\`\`text
Finding: hemoglobin|reported|OI-LAB-VALUE/1;value=10.2;unit=g/dL;qc=passed
\`\`\`

The measurement quotation is original synthetic annotation, not extraction from narrative real-world records. Accepted units are explicitly enumerated in \`lab_trends.py\` and compared as case-sensitive exact strings. There are no reference ranges, physiological bounds, analyte-to-unit mappings, clinical validity or meaningful trend interpretations. Unit/assay/specimen comparability beyond this narrow format remains **unverified**.

## Actual supported calls
\`\`\`python
from open_intelligence.lab_trends import case_lab_trend
from open_intelligence.store import CaseStore
store = CaseStore("local-synthetic-demo.sqlite")
try:
    result = case_lab_trend(store, "CASE-ALPHA", "hemoglobin")
finally:
    store.close()
\`\`\`

Use with synthetic-only databases. \`CaseStore\` initializes schema on opening; do not invoke it on real data, external EHRs or production systems. No CLI, API endpoint, UI, background automation or external egress is created here.

## Fail-closed result contract
- \`status=computed\`: at least two eligible current reports on unique event days with identical unit and source-authored \`qc=passed\`. \`analysis_executed=true\`, \`delta\`, numerical direction, provenance, but \`interpretation=none\` and \`clinical_review_state=not_performed\`.
- \`status=held\`: any relevant pending/negative/not-assessed finding, unsupported quote, failed/pending/unknown QC, source issue/event mismatch, same-day ambiguity or incompatible units. No \`delta\`; do not silently omit a bad sample to calculate an apparently clean trend.
- \`status=insufficient_current_measurements\`: fewer than two eligible values and no explicit holds; no \`delta\`.
- A source amendment preserves earlier versions while only the current version participates. This function generates a fresh read-only receipt; it does not persist runs, manage downstream staleness or authorize a newly computed result. A future Composer orchestration layer must version/fingerprint the source inputs and reject stale saves.

## Why separate from PR #68
The active native Composer PR #68 owns \`src/open_intelligence/{composer,__main__,store}.py\` and existing UI/investigation controls. This bounded tool **only** adds \`lab_trends.py\` and its tests. It does not attempt to wire a second tool route while those contracts are undergoing concurrent implementation; later Composer integration requires accepted typed capability registration, case/version fingerprint and human-reviewed PR.

## Test commands
\`\`\`bash
PYTHONPATH=src python -m unittest tests.test_lab_trends -v
PYTHONPATH=src python -m unittest discover -s tests -v
\`\`\`

CI success is required before any implementation claims. A synthetic \`qc=passed\` is merely an authored field; it is not real laboratory quality assurance or appropriate clinical authorization.
