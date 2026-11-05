"""Durable, actor-scoped transport for the canonical H1 source journal.

Only coordination state is owned here. Trusted composition supplies domain
authorization, effects and receipt callbacks; transport never writes a run or
reads source content. This is a PostgreSQL H1 binding, not a general event bus.
"""
from __future__ import annotations

from collections.abc import Callable
import hmac
import re
import uuid

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry

CONSUMER = "composer-source-context/1"
FIELDS = (
    "delivery_id", "event_id", "consumer", "patient_id", "case_id", "origin_org",
    "actor", "purpose", "state", "revision", "attempt_count", "failure_count",
    "lease_token", "lease_expires_at", "available_at", "created_at", "updated_at",
)
SELECT_DELIVERY = (
    "SELECT " + ",".join("d." + field for field in FIELDS)
    + ",COALESCE(d.lease_expires_at>clock_timestamp(),false) "
      "FROM coordination.source_event_deliveries d "
)


class EventLeaseLost(PatientRegistryConflict):
    """An expired or replaced claim cannot acknowledge or apply an event."""


class PostgresSourceEventDelivery:
    def __init__(self, registry: PostgresPatientRegistry, *,
                 authorize_scope_locked: Callable, consume_locked: Callable,
                 receipt_locked: Callable):
        if not isinstance(registry, PostgresPatientRegistry):
            raise TypeError("Canonical PostgreSQL patient registry required")
        self.registry = registry
        self.authorize_scope_locked = authorize_scope_locked
        self.consume_locked = consume_locked
        self.receipt_locked = receipt_locked

    @staticmethod
    def _unpack(row):
        return dict(zip((*FIELDS, "lease_current"), row)) if row else None

    def _scope(self, patient_id, case_id, organization, actor, purpose, recheck_authority):
        recheck_authority()
        self.authorize_scope_locked(patient_id, case_id, organization=organization,
                                    actor=actor, purpose=purpose)

    def _load(self, claim, *, lock=False):
        identifier = claim.get("delivery_id")
        if type(identifier) is not str or re.fullmatch(r"DELIVERY-[0-9A-F]{32}", identifier) is None:
            raise PatientRegistryDenied("Event delivery unavailable")
        row = self._unpack(self.registry._fetchone(
            SELECT_DELIVERY + "WHERE d.delivery_id=%s AND d.consumer=%s AND d.patient_id=%s "
            "AND d.case_id=%s AND d.origin_org=%s AND d.actor=%s AND d.purpose=%s"
            + (" FOR UPDATE OF d" if lock else ""),
            (identifier, CONSUMER, claim["patient_id"], claim["case_id"],
             claim["origin_org"], claim["actor"], claim["purpose"])))
        if row is None or row["event_id"] != claim["event_id"]:
            raise PatientRegistryDenied("Event delivery unavailable")
        return row

    def _event(self, row, reason):
        self.registry._execute(
            "INSERT INTO coordination.source_event_delivery_events "
            "(delivery_id,revision,state,attempt_count,failure_count,reason_code) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (row["delivery_id"], row["revision"], row["state"],
             row["attempt_count"], row["failure_count"], reason))
        self.registry.append_event(
            row["patient_id"], "source.delivery." + row["state"],
            delivery_id=row["delivery_id"], source_event_id=row["event_id"],
            consumer=CONSUMER, case_id=row["case_id"], actor=row["actor"],
            purpose=row["purpose"], revision=row["revision"],
            attempt_count=row["attempt_count"], failure_count=row["failure_count"],
            reason_code=reason)

    def _transition(self, row, state, reason, *, failures, delay=0):
        self.registry._execute(
            "UPDATE coordination.source_event_deliveries SET state=%s,revision=revision+1,"
            "failure_count=%s,lease_token=NULL,lease_expires_at=NULL,"
            "available_at=clock_timestamp()+(%s * interval '1 second'),"
            "updated_at=clock_timestamp() WHERE delivery_id=%s",
            (state, failures, delay, row["delivery_id"]))
        current = self._load(row)
        self._event(current, reason)
        return current

    def _next(self, patient_id, case_id, organization, actor, purpose):
        return self._unpack(self.registry._fetchone(
            SELECT_DELIVERY + "WHERE d.patient_id=%s AND d.case_id=%s AND d.origin_org=%s "
            "AND d.actor=%s AND d.purpose=%s AND d.consumer=%s AND "
            "((d.state='queued' AND d.available_at<=clock_timestamp()) OR "
            "(d.state='running' AND d.lease_expires_at<=clock_timestamp())) "
            "ORDER BY d.event_id,d.delivery_id LIMIT 1 FOR UPDATE OF d SKIP LOCKED",
            (patient_id, case_id, organization, actor, purpose, CONSUMER)))

    def claim_next(self, patient_id: str, case_id: str, *, organization: str, actor: str,
                   purpose: str, recheck_authority: Callable[[], None], lease_seconds: int = 30):
        """Claim one event for the current actor, or expose an exhausted lease.

        No global sequence cursor or acknowledgement is used: another actor and
        a lower event ID that commits later remain independently discoverable.
        """
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise PatientRegistryError("Lease duration must be between 1 and 300 seconds")
        with self.registry.transaction():
            self._scope(patient_id, case_id, organization, actor, purpose, recheck_authority)
            row = self._next(patient_id, case_id, organization, actor, purpose)
            if row is None:
                outbox = self.registry._fetchone(
                    "SELECT o.event_id FROM coordination.source_event_outbox o "
                    "WHERE o.patient_id=%s AND o.case_id=%s AND o.origin_org=%s AND o.purpose=%s "
                    "AND NOT EXISTS (SELECT 1 FROM coordination.source_event_deliveries d "
                    "WHERE d.event_id=o.event_id AND d.consumer=%s AND d.origin_org=%s "
                    "AND d.actor=%s AND d.purpose=%s) ORDER BY o.event_id LIMIT 1",
                    (patient_id, case_id, organization, purpose, CONSUMER, organization, actor, purpose))
                if outbox is None:
                    recheck_authority()
                    return None
                identifier = "DELIVERY-" + uuid.uuid4().hex.upper()
                self.registry._execute(
                    "INSERT INTO coordination.source_event_deliveries "
                    "(delivery_id,event_id,consumer,patient_id,case_id,origin_org,actor,purpose) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (identifier, outbox[0], CONSUMER, patient_id, case_id, organization, actor, purpose))
                row = self._load(dict(delivery_id=identifier, event_id=outbox[0],
                                     patient_id=patient_id, case_id=case_id, origin_org=organization,
                                     actor=actor, purpose=purpose))
                self._event(row, "queued")
            expired = row["state"] == "running"
            failures = row["failure_count"] + int(expired)
            if failures >= 3:
                terminal = self._transition(row, "dead_letter", "lease_expired", failures=3)
                recheck_authority()
                return terminal
            token = "LEASE-" + uuid.uuid4().hex.upper()
            self.registry._execute(
                "UPDATE coordination.source_event_deliveries SET state='running',revision=revision+1,"
                "attempt_count=attempt_count+1,failure_count=%s,lease_token=%s,"
                "lease_expires_at=clock_timestamp()+(%s * interval '1 second'),"
                "updated_at=clock_timestamp() WHERE delivery_id=%s",
                (failures, token, lease_seconds, row["delivery_id"]))
            current = self._load(row)
            self._event(current, "lease_expired" if expired else "claimed")
            recheck_authority()
            return current

    def _fence(self, claim):
        row = self._load(claim, lock=True)
        if (row["state"] != "running" or not row["lease_current"]
                or row["attempt_count"] != claim["attempt_count"]
                or type(claim.get("lease_token")) is not str
                or not hmac.compare_digest(row["lease_token"], claim["lease_token"])):
            raise EventLeaseLost("Event delivery lease is no longer current")
        return row

    def deliver(self, claim: dict, *, recheck_authority: Callable[[], None]) -> dict:
        """Apply at most one domain batch and atomically acknowledge its receipt."""
        with self.registry.transaction():
            self._scope(claim["patient_id"], claim["case_id"], claim["origin_org"],
                        claim["actor"], claim["purpose"], recheck_authority)
            self._load(claim, lock=True)
            receipt = self.receipt_locked(claim)
            if receipt is not None:
                recheck_authority()
                self.registry.append_event(
                    claim["patient_id"], "source.delivery.receipt_read_authorized",
                    delivery_id=claim["delivery_id"], source_event_id=claim["event_id"],
                    case_id=claim["case_id"], actor=claim["actor"], purpose=claim["purpose"],
                    attempt_count=claim["attempt_count"])
                recheck_authority()
                return {**receipt, "duplicate": True}
            current = self._fence(claim)
            receipt = self.consume_locked(current, recheck_authority=recheck_authority)
            # Source access auditing is inside the consumer's callback. A slow
            # callback or grant check must not turn an expired claim into an ack.
            self._fence(claim)
            state = receipt["status"]
            if state not in {"queued", "delivered"}:
                raise PatientRegistryError("Invalid source event acknowledgement")
            self._transition(current, state, "continued" if state == "queued" else "delivered", failures=0)
            recheck_authority()
            if not self.registry._fetchone("SELECT clock_timestamp()<%s", (current["lease_expires_at"],))[0]:
                raise EventLeaseLost("Event delivery lease expired before acknowledgement")
            return {**receipt, "duplicate": False}

    def finish_failure(self, claim: dict, *, reason_code: str) -> str:
        """A held lease allows failure bookkeeping only, never domain effects.

        No credentials are required to discard a held attempt after revocation.
        This command has no HTTP exposure and cannot disclose source content.
        """
        if reason_code not in {"retryable_failure", "authority_unavailable", "invalid_event"}:
            raise PatientRegistryError("Unknown bounded event failure")
        with self.registry.transaction():
            try:
                row = self._fence(claim)
            except EventLeaseLost:
                return "fenced"
            failures = row["failure_count"] + 1
            state = "queued" if reason_code == "retryable_failure" and failures < 3 else "dead_letter"
            self._transition(row, state, reason_code, failures=failures,
                             delay=min(2 ** failures, 30) if state == "queued" else 0)
            return state
