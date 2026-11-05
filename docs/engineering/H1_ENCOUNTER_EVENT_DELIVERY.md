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

Use the repository's locked API runtime and the [persistent demo setup](../H1_DEMO.md). Supply a current synthetic operations credential with the existing patient, encounter, note and encounter-event read grants. Keep the token and receiving database in an operator-private directory. Each delivery invocation reads one bounded page. Run again while the response reports `has_more`, or later to catch up.

```sh
PYTHONPATH=apps/api/src:src python -m oi_api.encounter_relay \
  --patient "$OI_RELAY_PATIENT" --port 8000 \
  --token-file "$OI_RELAY_TOKEN_FILE" --database "$OI_RELAY_DATABASE"
```

Use one dedicated file per source and patient. The API port is part of the source identity and must be stable. The receiver accepts only IPv4 loopback and does not follow redirects. An unavailable feed, revoked grant, contract mismatch or storage error returns exit code 2 and withholds counts. Operators can retry transient outages. For a changed source lineage, preserve the old store for reconciliation and replay the intended source into a separate empty store. A database file backup is suitable while the receiver is stopped. For a running receiver use SQLite's backup API.

## Verify a restored receiver

Before resuming delivery, repeat the command above with `--verify-history`. The check opens an existing receiver read-only, confirms its source and patient, and captures its checkpoint and category totals. It rereads the authorized feed from the beginning through that checkpoint, comparing the order, event IDs, hashes, categories and derived counts. This catches a change to an earlier event even when the last event still matches. Credentials and patient grants are checked on each page, including for an empty receiver.

A successful result reports `through_event_id` and `verified_events`. Newer events are not verified or counted; run normal delivery to catch up. Missing storage, changed history, inconsistent totals, invalid read-receipt references or lost access return exit code 2 without disclosing counts. The original read-receipt reference is checked for valid format; a fresh authorized read cannot establish whether that historic grant was valid. Verification uses successive feed reads rather than a single PostgreSQL snapshot. Keep the source lineage stable during reconciliation; restart verification if the source itself is restored or rewritten mid-scan.

## Acceptance and scope

The receiver regression suite exercises pagination, duplicate deliveries, concurrent subscribers sharing a checkpoint, malformed and divergent pages, a real process kill during a multi-event transaction, a populated backup/restore and the loopback command with denied and redirected responses. The connected PostgreSQL test in `test_encounter_http.py` creates a visit, retries the command, transitions the visit, saves drafts, kills the real relay during the receiving transaction, recovers all three change types once, withdraws a grant and resumes delivery after fresh authorization. The draft PR records actual runs separately from test coverage. No new package, PostgreSQL migration, network service or background scheduler is required.

Delivery is at least once with an idempotent receiving effect. Authorization is evaluated at producer read time. Filesystem access to a previously populated receiver requires separate operator control. General service identity, production retention and revocation, distributed brokers, clinical effects, and other engines require their own scoped integration.

## Visit workload for Operations

Add `--visit-workload` to the same relay invocation to count visits by their current operational state. For example, a visit moving from scheduled to in progress leaves the scheduled group and enters the in-progress group. Note drafts preserve the visit state. The feed option `include_visit_state=true` supplies the previous and new state recorded in the immutable EHR journal for that revision. The ordinary feed and count-only command retain their existing response formats and hashes.

For a populated receiver, the first workload run starts at the beginning of the authorized feed and checks prior event hashes while rebuilding in pages. Existing activity receipts and their original access references survive. The command returns `visit_workload: null` while more pages are needed. After catch-up it returns the distribution as of the last authorized page. Each page commits visit states, workload receipts, and new activity counts together. An unexpected revision or transition rolls back the page. Restore or retry uses the same cursor and patient scope. This local operational projection stores encounter identifiers and aggregate states. Clinical records, note content and decisions stay with the owning application.

## Operations intake of revised drafts

The same receiver maintains a local operations inbox with one pending item per encounter and note. A first saved draft opens an item. A later saved version replaces it, including after an operator acknowledged the earlier version. Acknowledgement records receipt of a version for local operations. Clinical review, signing and external notifications require their own authorities.

Use the same relay command and private store as above, with one additional argument per operation.

| Argument | Result |
| --- | --- |
| `--pending-drafts-after 0` | Returns up to 25 pending entries with encounter ID, source journal event ID and note version. Pass the returned `next_after_event` to continue. Use the authorized encounter event feed to resolve a reference at its source. |
| `--acknowledge-draft-event EVENT_ID` | Records the exact current item with the fresh feed access receipt. Retrying a current acknowledged event returns its original intake effect. A superseded or unknown ID returns exit code 3. |

Each invocation checks the live operations feed and applies one bounded page. If the receiver needs another page, it returns `catching_up` and withholds the inbox and acknowledgement. Retry while `has_more` is true. A denied read or invalid history returns exit code 2. The local private file and current operations read grant together delimit this single-operator tool. Two distinct clinical users must not share it as a personal inbox. Acknowledgement is current through the last authorized feed snapshot. A draft saved subsequently appears when next delivered.

Receiver schema v2 preserves the original delivery receipts, authority references and totals. A v1 store backfills the inbox by re-reading pages from the beginning, verifying retained event hashes and order, and committing the projection cursor with each page. The absence of source history or a changed version stops the backfill. Original receipts are never counted again. The receiver keeps a hashed note key and encounter/version references, with no note text. The verified backup procedure below also checks the draft projection against a fresh replay.
### Recover the independent receiver alongside PostgreSQL

Use `--backup-to /private/operator-directory/new.sqlite` with the same patient, port, token file and running receiver database arguments. The backup operation copies the receiver's owned records from one SQLite read transaction, checks the copied history against the authorized feed, then publishes the private file at a previously unused path. An outage, denied feed, mismatched event, inconsistent count, or occupied destination prevents publication. Use an operator-owned directory with mode 0700. Backup and verification operate on the independently fictional activity receiver.

After restoring the producer at its original loopback port, run `--verify-history` against the restored receiver. A verified prefix can be behind the producer. Run the normal relay to catch up and verify again. Preserve divergent copies for reconciliation. The Compose acceptance deliberately restores a three-event receiver against a four-event producer, appends a fifth event after restore, checks the original producer read receipts, and withdraws the feed grant.

A verified backup requires nonempty delivery history. The receiver copies the activity, draft, local acknowledgement and visit workload records together. Each derived projection retains its own checkpoint during backfill. Verification requests authorized transition fields whenever workload records exist. It reconstructs the inbox and per-visit state through their captured checkpoints and compares them with the snapshot. The first authorized delivery upgrades an older v1 backup.

An acknowledgement belongs to the local operations receiver. Backup checks its event against EHR draft history and compares the source and copied local records, including their access receipt identifiers. The result reports their count and SHA-256 under `local_acknowledgements` when present. Preserve this receipt separately. To check a restored copy for removed, added or changed local actions, run `--verify-history --expect-ack-sha256 DIGEST` before resuming delivery. The EHR attests to the draft event; the operator's saved receipt supplies the reference for the local action. A later draft revision opens a new pending item.
