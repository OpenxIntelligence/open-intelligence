# Restored evidence HTTP acceptance

> Execute natively in the isolated recovery checkout; request an independent final review.

**Goal:** Close the explicitly recorded #300 recovery gap under OI-008/009/013: prove the actual API serves restored originals, immutable reports and exact retries, while retaining current rights and revoked patient binding.

**Architecture:** Extend only the existing disposable Compose verification script. Reuse the existing API image, PostgreSQL schema, source transactions, fixture credential file and exact request bodies. No application, schema, dependency, clinical authority or UI changes.

**Spec:** `docs/engineering/H1_AUTHORED_EVIDENCE_REPORTS.md`, particularly its recorded logical-only dump/restore boundary.

## Approach and acceptance

SQL equality alone is the existing baseline. Add actual restored HTTP, using a temporary Compose override to recreate the same API against a named restored database. Require fresh access events in that database and byte-identical original-database snapshots; this detects accidentally testing the original service. Preserve all existing assertions.

1. Restore the readable report checkpoint. Reopen both originals and the report, recover exact assessment/report requests, verify immutable state and receipt locality, then reconnect the original database.
2. Restore a content-class amendment before withdrawal to isolate rights enforcement, then restore the later amended/withdrawn checkpoint. Recheck withheld report content and denied original access, recover old receipt IDs, reject a fresh stale assessment, and check missing independent export authority without writes.
3. Revoke the binding through restored HTTP, back up that revoked copy, restore again and prove reads and retries remain denied without new effects.
4. Run static checks and local reference tests, then the actual hosted API/PostgreSQL/Compose workflow. Local Docker is unavailable; local skips do not establish database success. Capture exact revision, run and artifact evidence.

## Review focus

- False-positive recovery against the original database: require restored-only access events and an unchanged original snapshot.
- Replay creates a duplicate clinical object: compare all immutable tables and business events after retries.
- Authorization restored from a cached response: use current mounted grants and persisted revoked binding through actual HTTP.
- Withheld body sneaks into a report: assert null body/snapshot and preserved identity/digests.
- Restoration rewrites history: compare complete rows and all sequence states before any HTTP operation.

## Progress

- [x] Inspected attachment, current Notion/Drive records, published #300 and local identical tree `39b897a67da9a212e466c9ff7caf6241a219c980`.
- [x] Extend verification and execute local checks: compilation, whitespace, patient-data guard; 250 reference tests; 64 local API passes and 283 explicitly skipped DB cases.
- [x] Independent review and bounded child draft #302 published; withdrawal/rights masking and denial-only database-target gaps addressed.
- [x] Hosted PostgreSQL/HTTP acceptance passed at c89b22df38a0ede3fff12ee65adb9c9ef1e347cc: 347 API/database, 250 reference, all recovery probes; 206 client tests and real browser workflow. Runs 41653217105 and 41653217136; both downloaded artifact digests verified, all 353 browser source files matched.
- [x] Record results in the existing engineering contract and OI-013 backlog; update existing Notion Engineering 12 and Google Docs Engineering Progress. The Drive append was verified by readback.

Review disposition: both Important findings addressed. Non-access sequence comparison was also tightened because the stated exact-retry acceptance requires no business-sequence side effect. Local verification-gate mutation checks reject five false-success comparisons and a mismatched target. Production recovery qualification and clinical correctness remain outside this test-only scope; Docker execution is judged only from hosted evidence.
