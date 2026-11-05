# Encounter change delivery

Under [WS-08 / #104](https://github.com/OpenxIntelligence/open-intelligence/issues/104), the synthetic encounter writer, platform relay and an independent operations consumer share a reference-only event contract. The receiver counts delivered changes and shows which current note revisions still await local intake acknowledgement for its configured fictional patient.

## Components and ownership

| Owner | Responsibility |
| --- | --- |
| EHR and canonical PostgreSQL journal | Persist the clinical command, retry receipt and event in one transaction. The existing per-patient writer lock makes the event cursor safe across committed commands. |
| H1 encounter feed | Serve up to 25 ordered event references for one patient, with fresh patient, organization, purpose, encounter, note and integration checks and an audited read receipt. |
| Loopback relay and independent activity consumer | Pull one authorized page. Commit event digests, producing read-receipt references, category totals and the resulting checkpoint in a private SQLite file. Return aggregate counts by default. The operations inbox below also supports exact-version local acknowledgement. |

The existing PostgreSQL journal supplies the transactional outbox for this path. The recipient owns its derived operational counts. The checkpoint is its highest committed event ID. Journal IDs may have gaps from unrelated activity. Subsequent reads include the last accepted event as an anchor. A missing or changed anchor stops the relay, including when the producer has been restored behind the consumer. A retry uses a new read receipt but the same event identity and digest. Concurrent relays serialize only the receiving transaction and verify the overlapping events. An interrupted page rolls back both its receipt and count changes.

This builds on the connected EHR feed introduced in [#535](https://github.com/OpenxIntelligence/open-intelligence/pull/535) and integrated in [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542). [#70](https://github.com/OpenxIntelligence/open-intelligence/pull/70) and [#89](https://github.com/OpenxIntelligence/open-intelligence/pull/89) contain earlier SQLite transport and adapter work with a different envelope. Here the governed HTTP feed is the contract. Receipt identity is the original journal ID within the pinned API origin and patient. Receiver storage contains a scope fingerprint, event IDs, hashes, categories, counts and read-receipt references. Note bodies, note keys, source contents and credentials stay outside the receiver database.

## Run against the local synthetic H1 API

Use the repository's locked API runtime and the [persistent demo setup](../H1_DEMO.md). Supply a current synthetic operations credential with the existing patient, encounter, note and encounter-event read grants. Keep the token and receiving database in an operator-private directory. Each invocation reads one bounded page. Run again while the response reports `has_more`, or later to catch up.

```sh
PYTHONPATH=apps/api/src:src python -m oi_api.encounter_relay \
  --patient "$OI_RELAY_PATIENT" --port 8000 \
  --token-file "$OI_RELAY_TOKEN_FILE" --database "$OI_RELAY_DATABASE"
```

Use one dedicated file per source and patient. The API port is part of the source identity and must be stable. The receiver accepts only IPv4 loopback and does not follow redirects. An unavailable feed, revoked grant, contract mismatch or storage error returns exit code 2 and withholds counts. Operators can retry transient outages. For a changed source lineage, preserve the old store for reconciliation and replay the intended source into a separate empty store. Ordinary delivery compares the boundary event. For a full comparison or a recoverable copy, use the commands below.

## Acceptance and scope

The receiver regression suite exercises pagination, duplicate deliveries, concurrent subscribers sharing a checkpoint, malformed and divergent pages, a real process kill during a multi-event transaction, a populated backup/restore and the loopback command with denied and redirected responses. The connected PostgreSQL test in `test_encounter_http.py` creates a visit, retries the command, transitions the visit, saves drafts, kills the real relay during the receiving transaction, recovers all three change types once, withdraws a grant and resumes delivery after fresh authorization. The draft PR records actual runs separately from test coverage. No new package, PostgreSQL migration, network service or background scheduler is required.

Delivery is at least once with an idempotent receiving effect. Authorization is evaluated at producer read time. Filesystem access to a previously populated receiver requires separate operator control. General service identity, production retention and revocation, distributed brokers, clinical effects, and other engines require their own scoped integration.

## Operations intake of revised drafts

The same receiver maintains a local operations inbox with one pending item per encounter and note. A first saved draft opens an item. A later saved version replaces it, including after an operator acknowledged the earlier version. Acknowledgement records receipt of a version for local operations. Clinical review, signing and external notifications require their own authorities.

Use the same relay command and private store as above, with one additional argument per operation.

| Argument | Result |
| --- | --- |
| `--pending-drafts-after 0` | Returns up to 25 pending entries with encounter ID, source journal event ID and note version. Pass the returned `next_after_event` to continue. Use the authorized encounter event feed to resolve a reference at its source. |
| `--acknowledge-draft-event EVENT_ID` | Records the exact current item with the fresh feed access receipt. Retrying a current acknowledged event returns its original intake effect. A superseded or unknown ID returns exit code 3. |

Each invocation checks the live operations feed and applies one bounded page. If the receiver needs another page, it returns `catching_up` and withholds the inbox and acknowledgement. Retry while `has_more` is true. A denied read or invalid history returns exit code 2. The local private file and current operations read grant together delimit this single-operator tool. Two distinct clinical users must not share it as a personal inbox. Acknowledgement is current through the last authorized feed snapshot. A draft saved subsequently appears when next delivered.

Receiver schema v2 preserves the original delivery receipts, authority references and totals. A v1 store backfills the inbox by re-reading pages from the beginning, verifying retained event hashes and order, and committing the projection cursor with each page. The absence of source history or a changed version stops the backfill. Original receipts are never counted again. The receiver keeps a hashed note key and encounter/version references, with no note text.

## Verify and recover a receiver

Use the same patient, port, credential file and database arguments as for delivery.

- Add `--verify-history` to check the receiver at a captured checkpoint. The relay releases the live database before replay so intake can continue. It requests each page with current authority, compares every event ID, digest and type, and checks the category totals. For a v2 receiver it reconstructs the latest draft for each encounter and hashed note key through the saved inbox checkpoint.
- Add `--backup-to /private/operator/directory/recovery.sqlite` to create a recovery file. The directory must belong to the operator and be accessible only to that account. Choose an unused filename. The relay checks access before copying, takes a consistent snapshot of the receiver-owned columns, then verifies that copy against the feed before publishing it. Denied access, divergent history, invalid inbox state or an existing destination prevents publication.
- To resume, use the recovery file as `--database` with the same patient and local API port. Run `--verify-history` against the intended producer, then `--pending-drafts-after 0` until catch-up completes. An acknowledged revision stays acknowledged. A subsequent revision opens a new pending item.

A v1 snapshot retains its schema until the next delivery. A v2 snapshot taken during v1 backfill preserves both the full receipt history and the separate inbox checkpoint. Replay checks each local acknowledgement against a delivered draft revision and validates its access-receipt format. The local operator owns the acknowledgement itself. The producer feed has no record of an operator clicking acknowledge and cannot reconstruct acknowledgements made after the backup. In the paired restore exercise the recorded access receipts are also checked against the restored producer audit journal.

This combines the replay and backup work from [#563](https://github.com/OpenxIntelligence/open-intelligence/pull/563) with the operations inbox from [#564](https://github.com/OpenxIntelligence/open-intelligence/pull/564). Synthetic operator testing only.

### Local verification on the combined receiver

The encounter suite ran 33 cases. Twenty-eight passed, including the loopback CLI, SIGKILL recovery, full replay, v1 and partial-v2 snapshots, acknowledgement preservation and rejection of a changed inbox. Five PostgreSQL cases skipped locally. The static boundary gate covered 60 H1 modules across 10 owners, with 86 recorded legacy imports. All 31 architecture tests passed.

The full API suite collected 968 tests on the candidate and 955 on its parent, `f22bae55f10440e491f889505064be8d1d5c8f50`. Both runs reported the same 75 socket-permission errors and the same 576 skips. The local environment allows the relay's TCP loopback tests but blocks the Unix-domain sockets used by the archive tests. The paired PostgreSQL dump/restore and Compose restart exercise still needs an exact-revision run.
