"""First-party domain-event outbox for Open Intelligence.

This is a durable delivery/transport boundary, not an operational EHR or an
authorization service. All event contents are *references*, never clinical
payloads. The caller must authenticate actor/purpose, validate domain effects,
and insert its authoritative state and this outbox entry in ONE transaction.

SQLite adapter for the existing app; a transaction-equivalent PostgreSQL
adapter is required before selecting the production persistence architecture.
Delivery is at-least-once, and consumers MUST be idempotent.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from datetime import date, datetime
from typing import Any, Callable, Mapping

SCHEMA_ID = "oi.domain-event/1"
EVENT_KEYS = frozenset({
    "schema", "event_id", "event_type", "owner_domain", "issuer_namespace",
    "aggregate", "subject_binding_id", "source_version_ref",
    "supersedes_source_ref", "occurred_at", "recorded_at", "correlation_id",
    "causation_id", "authorization_decision_ref", "payload_ref",
})
AGGREGATE_KEYS = frozenset({"type", "id", "revision"})
OCCURRED_KEYS = frozenset({"value", "precision"})
IDENT = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{1,127}\Z")
DOMAIN = re.compile(r"[a-z][a-z0-9_]{1,63}\Z")
EVENT_TYPE = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}\Z")


class OutboxContractError(ValueError):
    """Event/consumer command fails a deterministic platform contract."""


def _id(value: Any, key: str, optional: bool = False) -> None:
    if optional and value is None:
        return
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise OutboxContractError(f"{key} must be a bounded identifier/reference")


def _instant(value: Any, key: str) -> None:
    if not isinstance(value, str):
        raise OutboxContractError(f"{key} must be a timezone-aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise OutboxContractError(f"{key} invalid ISO timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OutboxContractError(f"{key} must have explicit timezone")


def validate_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Reject unknown fields, weak identity/time shapes, and inline payloads.

    This checks shape and reference identity, not whether refs exist or whether
    the actor actually has authority. Cross-domain reference qualification and
    trusted authorization are separate required production services.
    """
    if not isinstance(event, dict) or set(event) != EVENT_KEYS:
        raise OutboxContractError("event must have the exact domain-event/1 fields")
    if event["schema"] != SCHEMA_ID:
        raise OutboxContractError("unsupported event schema")
    _id(event["event_id"], "event_id")
    if not isinstance(event["owner_domain"], str) or not DOMAIN.fullmatch(event["owner_domain"]):
        raise OutboxContractError("invalid owner_domain")
    if not isinstance(event["event_type"], str) or not EVENT_TYPE.fullmatch(event["event_type"]):
        raise OutboxContractError("invalid event_type")
    if not event["event_type"].startswith(event["owner_domain"] + "."):
        raise OutboxContractError("event_type must belong to owner_domain")
    for key in ("issuer_namespace", "correlation_id", "causation_id", "payload_ref"):
        _id(event[key], key)
    # No narrative "approved" field can mint a trusted grant. This field
    # records the claim; a policy service must independently verify it.
    _id(event["authorization_decision_ref"], "authorization_decision_ref", optional=True)
    for key in ("subject_binding_id", "source_version_ref", "supersedes_source_ref"):
        _id(event[key], key, optional=True)
    if event["supersedes_source_ref"] is not None and event["source_version_ref"] is None:
        raise OutboxContractError("supersession requires a current source reference")
    aggregate = event["aggregate"]
    if not isinstance(aggregate, dict) or set(aggregate) != AGGREGATE_KEYS:
        raise OutboxContractError("aggregate requires type/id/revision")
    _id(aggregate["type"], "aggregate.type")
    _id(aggregate["id"], "aggregate.id")
    if type(aggregate["revision"]) is not int or aggregate["revision"] < 1:
        raise OutboxContractError("aggregate.revision must be a positive integer")
    occurred = event["occurred_at"]
    if not isinstance(occurred, dict) or set(occurred) != OCCURRED_KEYS:
        raise OutboxContractError("occurred_at must have value and precision")
    if occurred["precision"] == "day":
        try:
            if date.fromisoformat(occurred["value"]).isoformat() != occurred["value"]:
                raise ValueError
        except (ValueError, TypeError):
            raise OutboxContractError("day-precision time must be YYYY-MM-DD") from None
    elif occurred["precision"] == "second":
        _instant(occurred["value"], "occurred_at.value")
    else:
        raise OutboxContractError("unsupported time precision")
    _instant(event["recorded_at"], "recorded_at")
    # A JSON round-trip also rejects unexpected non-serializable Python types.
    try:
        normalized = json.loads(json.dumps(event, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError):
        raise OutboxContractError("event must be strict JSON") from None
    return normalized


def install(conn: sqlite3.Connection) -> None:
    """Install transport-only tables on an existing domain-owned connection.

    Run during a migration, outside a caller's clinical transaction. Never
    installs a second patient, specimen or evidence ledger.
    """
    if conn.in_transaction:
        raise OutboxContractError("outbox migration cannot run inside domain transaction")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_outbox (
          seq INTEGER PRIMARY KEY AUTOINCREMENT,
          event_id TEXT NOT NULL UNIQUE,
          event_type TEXT NOT NULL,
          owner_domain TEXT NOT NULL,
          aggregate_id TEXT NOT NULL,
          event_hash TEXT NOT NULL,
          envelope_json TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending'
            CHECK(state IN ('pending', 'leased', 'dispatched', 'dead_letter')),
          attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
          leased_by TEXT,
          lease_until INTEGER,
          dispatched_at INTEGER,
          failure_code TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_platform_outbox_queue "
        "ON platform_outbox (state, lease_until, seq)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_inbox_receipts (
          consumer_id TEXT NOT NULL,
          event_id TEXT NOT NULL,
          event_hash TEXT NOT NULL,
          applied_at INTEGER NOT NULL,
          PRIMARY KEY(consumer_id,event_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_consumer_aggregate_versions (
          consumer_id TEXT NOT NULL,
          issuer_namespace TEXT NOT NULL,
          owner_domain TEXT NOT NULL,
          aggregate_type TEXT NOT NULL,
          aggregate_id TEXT NOT NULL,
          subject_binding_id TEXT NOT NULL,
          last_revision INTEGER NOT NULL CHECK(last_revision >= 1),
          last_event_id TEXT NOT NULL,
          PRIMARY KEY(consumer_id,issuer_namespace,owner_domain,aggregate_type,aggregate_id)
        )
    """)



def enqueue(conn: sqlite3.Connection, event: Mapping[str, Any]) -> bool:
    """Atomically enqueue with caller's state change; never commits.

    True means created. False means byte-identical event ID already present.
    A reused event ID carrying different content is an explicit conflict.
    """
    canonical = validate_event(event)
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    try:
        conn.execute(
            "INSERT INTO platform_outbox "
            "(event_id,event_type,owner_domain,aggregate_id,event_hash,envelope_json) "
            "VALUES (?,?,?,?,?,?)",
            (canonical["event_id"], canonical["event_type"], canonical["owner_domain"],
             canonical["aggregate"]["id"], digest, serialized),
        )
        return True
    except sqlite3.IntegrityError:
        found = conn.execute(
            "SELECT event_hash FROM platform_outbox WHERE event_id=?",
            (canonical["event_id"],),
        ).fetchone()
        if found is not None and found[0] == digest:
            return False
        raise OutboxContractError("event_id collision with different content") from None


def claim(conn: sqlite3.Connection, worker: str, *, now: int | None = None,
          lease_seconds: int = 30, limit: int = 50) -> list[dict[str, Any]]:
    """Lease pending/expired events using a SQLite write lock.

    Caller must not be inside an operational transaction. A crashed worker's
    lease expires, allowing at-least-once redelivery. Consumers deduplicate.
    """
    _id(worker, "worker")
    if not 1 <= lease_seconds <= 3600 or not 1 <= limit <= 100:
        raise OutboxContractError("invalid lease_seconds/limit")
    if conn.in_transaction:
        raise OutboxContractError("claim needs its own transaction")
    ts = int(time.time()) if now is None else now
    if type(ts) is not int or ts < 0:
        raise OutboxContractError("now must be nonnegative integer epoch seconds")
    conn.execute("BEGIN IMMEDIATE")
    try:
        rows = conn.execute(
            "SELECT seq,event_id,envelope_json,attempts FROM platform_outbox "
            "WHERE state='pending' OR (state='leased' AND lease_until<=?) "
            "ORDER BY seq LIMIT ?", (ts, limit),
        ).fetchall()
        for seq, _, _, _ in rows:
            conn.execute(
                "UPDATE platform_outbox SET state='leased',leased_by=?,lease_until=?,"
                "attempts=attempts+1 WHERE seq=?",
                (worker, ts + lease_seconds, seq),
            )
        conn.commit()
        return [
            {"event_id": event_id, "event": json.loads(payload), "attempt": attempts + 1}
            for _, event_id, payload, attempts in rows
        ]
    except BaseException:
        conn.rollback()
        raise


def complete(conn: sqlite3.Connection, event_id: str, worker: str,
             *, now: int | None = None) -> None:
    """Record downstream broker acceptance, NOT consumer processing or clinical review."""
    _id(event_id, "event_id")
    _id(worker, "worker")
    ts = int(time.time()) if now is None else now
    if type(ts) is not int or ts < 0:
        raise OutboxContractError("invalid epoch seconds")
    changed = conn.execute(
        "UPDATE platform_outbox SET state='dispatched',leased_by=NULL,"
        "lease_until=NULL,dispatched_at=? WHERE event_id=? AND state='leased' "
        "AND leased_by=? AND lease_until>?",
        (ts, event_id, worker, ts),
    ).rowcount
    if changed != 1:
        raise OutboxContractError("no current matching lease for completion")
    # No commit: caller controls acknowledgment transaction.


def fail(conn: sqlite3.Connection, event_id: str, worker: str, code: str,
         *, dead_letter_after: int = 5) -> None:
    """Register an opaque error code; never store secrets/PHI error messages."""
    _id(event_id, "event_id")
    _id(worker, "worker")
    if not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,39}", code):
        raise OutboxContractError("failure_code must be a fixed opaque enum")
    if not 1 <= dead_letter_after <= 1000:
        raise OutboxContractError("invalid dead_letter_after")
    changed = conn.execute(
        "UPDATE platform_outbox SET state=CASE WHEN attempts>=? THEN 'dead_letter' "
        "ELSE 'pending' END,leased_by=NULL,lease_until=NULL,failure_code=? "
        "WHERE event_id=? AND state='leased' AND leased_by=?",
        (dead_letter_after, code, event_id, worker),
    ).rowcount
    if changed != 1:
        raise OutboxContractError("no matching lease for failure")
    # Dead-letter records remain inspectable. No silent abandonment or commit.


def consume_once(conn: sqlite3.Connection, consumer: str,
                 event: Mapping[str, Any],
                 apply_effect: Callable[[sqlite3.Connection, dict[str, Any]], None],
                 *, now: int | None = None) -> bool:
    """Apply one **authorized** consumer effect in the caller's transaction.

    A duplicate valid delivery is a no-op; same ID with different bytes fails.
    Receipt and domain projection are committed/rolled back together. The
    callback MUST independently verify source identity, permissions, aggregate
    versions, and policy; this transport primitive is not an auth gate.
    """
    _id(consumer, "consumer")
    if not conn.in_transaction:
        raise OutboxContractError("consumer effect and receipt require caller transaction")
    canonical = validate_event(event)
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    previous = conn.execute(
        "SELECT event_hash FROM platform_inbox_receipts "
        "WHERE consumer_id=? AND event_id=?",
        (consumer, canonical["event_id"]),
    ).fetchone()
    if previous is not None:
        if previous[0] != digest:
            raise OutboxContractError("consumer event-id collision with changed content")
        return False
    ts = int(time.time()) if now is None else now
    if type(ts) is not int or ts < 0:
        raise OutboxContractError("invalid consumer epoch timestamp")
    # Isolate callback writes even if its exception is caught by the caller.
    # No callback may COMMIT or perform irreversible external side effects.
    conn.execute("SAVEPOINT oi_consumer_effect")
    try:
        apply_effect(conn, canonical)
        conn.execute(
            "INSERT INTO platform_inbox_receipts "
            "(consumer_id,event_id,event_hash,applied_at) VALUES (?,?,?,?)",
            (consumer, canonical["event_id"], digest, ts),
        )
        conn.execute("RELEASE SAVEPOINT oi_consumer_effect")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK TO SAVEPOINT oi_consumer_effect")
            conn.execute("RELEASE SAVEPOINT oi_consumer_effect")
        raise
    return True


def consume_ordered(conn: sqlite3.Connection, consumer: str,
                    event: Mapping[str, Any],
                    apply_effect: Callable[[sqlite3.Connection, dict[str, Any]], None],
                    *, now: int | None = None) -> bool:
    """Apply only sequential revisions to a stable, explicitly bound subject.

    Reference fencing is not clinical authorization. Each caller must verify
    trusted grants, actual patient/specimen mapping and source rights.
    """
    canonical = validate_event(event)
    binding = canonical["subject_binding_id"]
    if binding is None:
        raise OutboxContractError("ordered consumer requires explicit subject binding")
    agg = canonical["aggregate"]

    def guarded(db: sqlite3.Connection, ev: dict[str, Any]) -> None:
        key = (consumer, ev["issuer_namespace"], ev["owner_domain"], agg["type"], agg["id"])
        previous = db.execute(
            "SELECT subject_binding_id,last_revision FROM platform_consumer_aggregate_versions "
            "WHERE consumer_id=? AND issuer_namespace=? AND owner_domain=? "
            "AND aggregate_type=? AND aggregate_id=?", key,
        ).fetchone()
        if previous is not None and previous[0] != binding:
            raise OutboxContractError("aggregate subject binding changed; reconcile explicitly")
        expected = 1 if previous is None else previous[1] + 1
        if agg["revision"] != expected:
            raise OutboxContractError(f"aggregate revision expected {expected}; got {agg['revision']}")
        apply_effect(db, ev)
        if previous is None:
            db.execute(
                "INSERT INTO platform_consumer_aggregate_versions "
                "(consumer_id,issuer_namespace,owner_domain,aggregate_type,aggregate_id,"
                "subject_binding_id,last_revision,last_event_id) VALUES (?,?,?,?,?,?,?,?)",
                key + (binding, agg["revision"], ev["event_id"]),
            )
        else:
            db.execute(
                "UPDATE platform_consumer_aggregate_versions SET last_revision=?,last_event_id=? "
                "WHERE consumer_id=? AND issuer_namespace=? AND owner_domain=? "
                "AND aggregate_type=? AND aggregate_id=?",
                (agg["revision"], ev["event_id"]) + key,
            )

    return consume_once(conn, consumer, canonical, guarded, now=now)
