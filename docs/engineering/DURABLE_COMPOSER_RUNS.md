# Persistent Composer work journal — bounded first implementation

Status: synthetic-only candidate stacked on the verified Composer integration PR #83. One existing numeric lab calculation is queued and executed explicitly. This is not an autonomous agent service, clinical order system, scheduler, or a second patient ledger.

The journal stores run ID, case ID, question ID, context fingerprint, tool/finding, idempotency key, state transitions, timestamps and actual result/hold. It uses additive composer_tool_runs and composer_tool_run_events tables in the **same local SQLite file** as canonical CaseStore, with no replacement of patient/source data. Failing or cancelled operations remain inspectable; previous version-bound outcomes are retained when new sources make them stale. A read/list reconciles stale outcomes and writes an audit transition.

HTTP contract (JSON only, local demo):
- POST /api/cases/{case}/composer/runs with question_id, context_fingerprint, finding_key, idempotency_key;
- POST /api/cases/{case}/composer/runs/{id}/execute with an empty JSON object;
- POST /api/cases/{case}/composer/runs/{id}/cancel with an empty JSON object;
- GET /api/cases/{case}/composer/runs and GET /api/cases/{case}/composer/runs/{id}.

An enqueue requires an exact current source/evidence context. Execution checks the same fingerprint before and after running the deterministic calculation, with separate persisted queued/running/completed/blocked/stale/cancelled/failed receipts. Repeated idempotency keys are not double-executed; altered parameters with a previous key are rejected. A source amendment invalidates unfinished runs and flags completed results on the next read, without deleting historical result bytes or silently recomputing.

Limits: execution is synchronous and explicitly initiated by the operator. It is not backed by a background worker, job lease, automatic crash recovery or clinical authorization system. If the process dies while a run is marked running, that state remains for operator review; safe restart/abandonment policy is future work. Cancellation can prevent queued work or supersede running-result publication; it does not forcibly terminate CPU execution. There is no production identity, PHI processing, medical interpretation, model-generated treatment advice or patient alert.

Tests: tests/test_durable_runs.py covers persistence across process/reopen, duplicate requests, wrong-case isolation, amendment before/during/after execution, QC holds, cancellation and local HTTP actions. Version-bound lab data is an independently authored fictional format; source QC is not real laboratory quality verification.

Review requirements: reconcile stacked #68, #72, #83 and this PR before any main integration; preserve all existing source history and rights controls; re-run exact integrated CI and independent review. No Next.js and no new third-party dependency.
