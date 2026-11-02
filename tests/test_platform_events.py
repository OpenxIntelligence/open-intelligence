"""Durable first-party domain outbox: transaction, restart, lease and schema tests."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path

from open_intelligence.platform_events import (
    OutboxContractError, claim, complete, consume_once, enqueue, fail, install, validate_event,
)
from open_intelligence.store import CaseStore


def fixture(event_id="EV-PLATFORM-001"):
    return {
        "schema": "oi.domain-event/1",
        "event_id": event_id,
        "event_type": "pathology.report.amended",
        "owner_domain": "pathology",
        "issuer_namespace": "urn:oi:fixture:lab-a:pathology",
        "aggregate": {"type": "report", "id": "PATH-A", "revision": 2},
        "subject_binding_id": "BINDING-FICTIONAL-001",
        "source_version_ref": "SOURCE-V2",
        "supersedes_source_ref": "SOURCE-V1",
        "occurred_at": {"value": "2026-01-01", "precision": "day"},
        "recorded_at": "2026-01-03T10:00:00Z",
        "correlation_id": "WORKFLOW-001",
        "causation_id": "CMD-002",
        "authorization_decision_ref": "AUTH-FICTIONAL-001",
        "payload_ref": "ARTIFACT-FICTIONAL-002",
    }


class PlatformEventTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "operational.sqlite"
        self.db = sqlite3.connect(self.path)
        self.addCleanup(self.db.close)
        install(self.db)

    def test_durable_at_least_once_claim_ack_across_restarts(self):
        with self.db:
            self.assertTrue(enqueue(self.db, fixture()))
            self.assertFalse(enqueue(self.db, fixture()))
        leased = claim(self.db, "WORKER-A", now=100, lease_seconds=10)
        self.assertEqual(len(leased), 1)
        self.assertEqual(leased[0]["event"], fixture())
        self.assertEqual(claim(self.db, "WORKER-B", now=105), [])
        self.db.close()
        reopened = sqlite3.connect(self.path)
        self.db = reopened
        # Expired lease is redelivered, preserving the exact payload and ID.
        leased_again = claim(reopened, "WORKER-B", now=111, lease_seconds=10)
        self.assertEqual(leased_again[0]["attempt"], 2)
        with self.assertRaises(OutboxContractError):
            complete(reopened, "EV-PLATFORM-001", "WORKER-A", now=112)
        with reopened:
            complete(reopened, "EV-PLATFORM-001", "WORKER-B", now=112)
        self.assertEqual(claim(reopened, "WORKER-C", now=200), [])
        self.assertEqual(
            reopened.execute("SELECT state FROM platform_outbox").fetchone()[0],
            "dispatched",
        )

    def test_rollback_keeps_event_and_operational_write_atomic(self):
        self.db.execute("CREATE TABLE operational_orders(id TEXT PRIMARY KEY)")
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            with self.db:
                self.db.execute("INSERT INTO operational_orders VALUES ('ORDER-A')")
                enqueue(self.db, fixture())
                raise RuntimeError("simulated failure")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM operational_orders").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 0)
        with self.db:
            self.db.execute("INSERT INTO operational_orders VALUES ('ORDER-A')")
            self.assertTrue(enqueue(self.db, fixture()))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 1)

    def test_uses_existing_case_store_connection_not_duplicate_patient_state(self):
        store = CaseStore(self.path)
        self.addCleanup(store.close)
        install(store.db)
        with store.db:
            store.db.execute(
                "INSERT OR IGNORE INTO cases(case_id,label,synthetic) VALUES (?,?,1)",
                ("CASE-ALPHA", "Fictional Alpha"),
            )
            store._event("CASE-ALPHA", "clinical_order_recorded", order="ORDER-1")
            self.assertTrue(enqueue(store.db, fixture("EV-PLATFORM-CASE-001")))
        with store.db:
            self.assertEqual(
                store.db.execute("SELECT COUNT(*) FROM events WHERE case_id='CASE-ALPHA'").fetchone()[0], 1
            )
            self.assertEqual(
                store.db.execute("SELECT COUNT(*) FROM platform_outbox "
                                 "WHERE event_id='EV-PLATFORM-CASE-001'").fetchone()[0], 1
            )
        # This module has only a transport journal, no competing patient record.
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cases").fetchone()[0], 1)

    def test_conflicting_duplicate_id_never_replaces_previous_payload(self):
        with self.db:
            enqueue(self.db, fixture())
            changed = fixture()
            changed["aggregate"]["revision"] = 3
            with self.assertRaises(OutboxContractError):
                enqueue(self.db, changed)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 1)

    def test_bounded_retry_and_visible_dead_letter(self):
        with self.db:
            enqueue(self.db, fixture())
        for attempt in range(1, 4):
            leased = claim(self.db, "WORKER-A", now=100 + attempt, lease_seconds=20)
            self.assertEqual(leased[0]["attempt"], attempt)
            with self.db:
                fail(self.db, "EV-PLATFORM-001", "WORKER-A", "BROKER_REJECTED", dead_letter_after=3)
        self.assertEqual(claim(self.db, "WORKER-A", now=10000), [])
        self.assertEqual(
            self.db.execute("SELECT state,failure_code FROM platform_outbox").fetchone(),
            ("dead_letter", "BROKER_REJECTED"),
        )

    def test_rejects_broker_ack_by_wrong_worker(self):
        with self.db:
            enqueue(self.db, fixture())
        claim(self.db, "WORKER-A", now=100)
        with self.assertRaises(OutboxContractError):
            complete(self.db, "EV-PLATFORM-001", "WORKER-B", now=101)
        with self.db:
            complete(self.db, "EV-PLATFORM-001", "WORKER-A", now=101)

    def test_schema_rejects_inline_claims_and_bad_dates(self):
        for key, value in [
            ("schema", "oi.domain-event/2"),
            ("event_type", "oncology.stage.advanced"),
            ("recorded_at", "2026-01-02T03:00:00"),
        ]:
            event = fixture()
            event[key] = value
            with self.subTest(key=key), self.assertRaises(OutboxContractError):
                validate_event(event)
        event = fixture()
        event["clinical_data"] = {"medication": "not allowed"}
        with self.assertRaises(OutboxContractError):
            validate_event(event)
        event = fixture()
        event["occurred_at"] = {"value": "2026-02-30", "precision": "day"}
        with self.assertRaises(OutboxContractError):
            validate_event(event)
        event = fixture()
        event["aggregate"]["revision"] = True
        with self.assertRaises(OutboxContractError):
            validate_event(event)

    def test_consumer_receipt_prevents_duplicate_operational_effect(self):
        self.db.execute("CREATE TABLE clinical_projection(event_id TEXT PRIMARY KEY)")
        event = fixture()
        calls = []

        def apply(conn, accepted):
            calls.append(accepted["event_id"])
            conn.execute("INSERT INTO clinical_projection VALUES (?)", (accepted["event_id"],))

        self.db.execute("BEGIN IMMEDIATE")
        with self.db:
            self.db.execute("SELECT COUNT(*) FROM platform_inbox_receipts")
            self.assertTrue(consume_once(self.db, "ONCOLOGY-READER", event, apply, now=12))
        self.db.execute("BEGIN IMMEDIATE")
        with self.db:
            self.assertFalse(consume_once(self.db, "ONCOLOGY-READER", event, apply, now=13))
        self.assertEqual(calls, ["EV-PLATFORM-001"])
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM clinical_projection").fetchone()[0], 1
        )
        changed = fixture()
        changed["aggregate"]["revision"] = 3
        self.db.execute("BEGIN IMMEDIATE")
        with self.db:
            with self.assertRaises(OutboxContractError):
                consume_once(self.db, "ONCOLOGY-READER", changed, apply, now=14)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM platform_inbox_receipts").fetchone()[0], 1
        )

    def test_consumer_effect_rolls_back_with_receipt(self):
        self.db.execute("CREATE TABLE clinical_projection(event_id TEXT PRIMARY KEY)")

        def apply(conn, accepted):
            conn.execute("INSERT INTO clinical_projection VALUES (?)", (accepted["event_id"],))

        self.db.execute("BEGIN IMMEDIATE")
        with self.assertRaisesRegex(RuntimeError, "rolled back"):
            with self.db:
                self.assertTrue(
                    consume_once(self.db, "ONCOLOGY-READER", fixture(), apply, now=12)
                )
                raise RuntimeError("rolled back")
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM platform_inbox_receipts").fetchone()[0], 0
        )
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM clinical_projection").fetchone()[0], 0
        )
        self.db.execute("BEGIN IMMEDIATE")
        with self.db:
            self.assertTrue(consume_once(self.db, "ONCOLOGY-READER", fixture(), apply, now=12))
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM clinical_projection").fetchone()[0], 1
        )

    def test_consumer_refuses_effect_without_a_transaction(self):
        with self.assertRaises(OutboxContractError):
            consume_once(self.db, "ONCOLOGY-READER", fixture(), lambda c, e: None)

    def test_claim_refuses_to_commit_unrelated_open_transaction(self):
        with self.db:
            enqueue(self.db, fixture())
        self.db.execute("CREATE TABLE work(id INTEGER)")
        self.db.execute("INSERT INTO work VALUES (1)")
        with self.assertRaises(OutboxContractError):
            claim(self.db, "WORKER-A", now=100)
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM work").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
