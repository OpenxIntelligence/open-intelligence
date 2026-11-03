# Restored evidence HTTP acceptance

> Execute natively in the isolated recovery checkout; request an independent final review.

**Goal:** Close the explicitly recorded #300 recovery gap under OI-008/009/013: prove the actual API serves restored originals, immutable reports and exact retries, while retaining current rights and revoked patient binding.

**Architecture:** Extend only the existing disposable Compose verification script. Reuse the existing API image, PostgreSQL schema, source transactions, fixture credential file and exact request bodies. No application, schema, dependency, clinical authority or UI changes.

**Spec:** `docs/engineering/H1_AUTHORED_EVIDENCE_REPORTS.md`, particularly its recorded logical-only dump/restore boundary.

## Approach and acceptance

SQL equality alone is the existing baseline. Add actual restored HTTP, using a temporary Compose override to recreate the same API against a named restored database. Require fresh access events in that database and byte-identical original-database snapshots; this detects accidentally testing the original service. Preserve all existing assertions.

1. Restore the readable report checkpoint. Reopen both originals and the report, recover exact assessment/report requests, verify immutable state and receipt locality, then reconnect the original database.
2. Restore the later amended/withdrawn checkpoint. Recheck withheld report content and denied original access, recover old receipt IDs, reject a fresh stale assessment, and check missing independent export authority without writes.
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
- [ ] Extend verification and execute local checks.
- [ ] Independent review; publish a bounded child draft; execute hosted acceptance.
- [ ] Record results in existing project documentation.
