# Browser startup diagnostics — OI-010

The H1 API run for draft #303, attempt 1 of run 41654044993, passed its Python suites but failed while waiting for Chrome DevTools. Its unchanged retry passed. Both inherited legacy browser journeys discarded Chrome stderr, leaving the underlying startup cause unknown.

Both journeys now capture Chrome stderr in their disposable temporary directory and share a startup wait that reports an early process exit immediately. A failed startup includes the process exit status and only the last 4096 stderr bytes, decoded with replacement and JSON-escaped to prevent control characters or newlines from becoming terminal controls or standalone workflow commands. A missing log cannot replace the primary failure. Successful startup returns the original target payload. Existing browser flags, sandbox settings, 12-second deadline, assertions and process-group cleanup are preserved; there is no automatic retry or failure waiver.

Four standard-library subprocess/loopback tests cover early exit, bounded/escaped diagnostic output, live-process timeout, unavailable stderr and successful target discovery. All four passed locally after implementation; the tests-first checkpoint failed because the diagnostic helper was absent. Python compilation passed. Full hosted suite and real-browser evidence is recorded in the associated draft PR; local focused checks do not establish full PostgreSQL or browser acceptance.

This is verification instrumentation, not a fix or explanation for the original intermittent Chrome startup failure. No application, API, dependency, schema, permission or clinical behavior changes. Independently authored fictional data only; draft and unmerged.

