# Encounter change delivery

Under [WS-08 / #104](https://github.com/OpenxIntelligence/open-intelligence/issues/104), the synthetic encounter writer, platform relay and an independent operations consumer share a reference-only event contract. The consumer answers an operational question: how many scheduled visits, encounter transitions and draft-note revisions has this receiver processed for its configured fictional patient?

## Components and ownership

| Owner | Responsibility |
| --- | --- |
| EHR and canonical PostgreSQL journal | Persist the clinical command, retry receipt and event in one transaction. The existing per-patient writer lock makes the event cursor safe across committed commands. |
| H1 encounter feed | Serve up to 25 ordered event references for one patient, with fresh patient, organization, purpose, encounter, note and integration checks and an audited read receipt. |
| Loopback relay and independent activity consumer | Pull one authorized page. Commit event digests, producing read-receipt references, category totals and the resulting checkpoint in a private SQLite file. Report only aggregate counts after a successful fetch and commit. |

The existing PostgreSQL journal supplies the transactional outbox for this path. The recipient owns its derived operational counts. The checkpoint is its highest committed event ID. Journal IDs may have gaps from unrelated activity. Subsequent reads include the last accepted event as an anchor. A missing or changed anchor stops the relay, including when the producer has been restored behind the consumer. A retry uses a new read receipt but the same event identity and digest. Concurrent relays serialize only the receiving transaction and verify the overlapping events. An interrupted page rolls back both its receipt and count changes.

This builds on the connected EHR feed introduced in [#535](https://github.com/OpenxIntelligence/open-intelligence/pull/535) and integrated in [#542](https://github.com/OpenxIntelligence/open-intelligence/pull/542). [#70](https://github.com/OpenxIntelligence/open-intelligence/pull/70) and [#89](https://github.com/OpenxIntelligence/open-intelligence/pull/89) contain earlier SQLite transport and adapter work with a different envelope. Here the governed HTTP feed is the contract. Receipt identity is the original journal ID within the pinned API origin and patient. Receiver storage contains a scope fingerprint, event IDs, hashes, categories, counts and read-receipt references. Note bodies, note keys, source contents and credentials stay outside the receiver database.

## Run against the local synthetic H1 API

Use the repository's locked API runtime and the [persistent demo setup](../H1_DEMO.md). Supply a current synthetic operations credential with the existing patient, encounter, note and encounter-event read grants. Keep the token and receiving database in an operator-private directory. Each invocation reads one bounded page. Run again while the response reports `has_more`, or later to catch up.

```sh
PYTHONPATH=apps/api/src:src python -m oi_api.encounter_relay \
  --patient "$OI_RELAY_PATIENT" --port 8000 \
  --token-file "$OI_RELAY_TOKEN_FILE" --database "$OI_RELAY_DATABASE"
```

Use one dedicated file per source and patient. The API port is part of the source identity and must be stable. The receiver accepts only IPv4 loopback and does not follow redirects. An unavailable feed, revoked grant, contract mismatch or storage error returns exit code 2 and withholds counts. Operators can retry transient outages. For a changed source lineage, preserve the old store for reconciliation and replay the intended source into a separate empty store. A single anchor detects boundary divergence, not an exhaustive comparison of two histories. A database file backup is suitable while the receiver is stopped. For a running receiver use SQLite's backup API.

## Acceptance and scope

The receiver regression suite exercises pagination, duplicate deliveries, concurrent subscribers sharing a checkpoint, malformed and divergent pages, a real process kill during a multi-event transaction, a populated backup/restore and the loopback command with denied and redirected responses. The connected PostgreSQL test in `test_encounter_http.py` creates a visit, retries the command, transitions the visit, saves drafts, delivers counts, withdraws a grant and resumes delivery after fresh authorization. The draft PR records actual runs separately from test coverage. No new package, PostgreSQL migration, network service or background scheduler is required.

Delivery is at least once with an idempotent receiving effect. Authorization is evaluated at producer read time. Filesystem access to a previously populated receiver requires separate operator control. General service identity, production retention and revocation, distributed brokers, clinical effects, and other engines require their own scoped integration.
