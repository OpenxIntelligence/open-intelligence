"""Exercise real receiver transactions with independently fictional encounter journals."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from oi_api import encounter_relay as relay
from test_encounter_relay import CHANGED, NOTE, PATIENT, RECEIPT, SCHEDULED, event, page


def visit(index, visit_id, revision, before, after):
    kind = SCHEDULED if revision == 1 else CHANGED
    return dict(event(index, kind), encounter_id=visit_id, encounter_revision=revision,
                from_status=before, to_status=after)


def legacy(record):
    return {key: value for key, value in record.items() if key not in ("from_status", "to_status")}


class WorkloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "receiver.sqlite"

    def deliver(self, document, *, workload=True):
        with patch.object(relay, "read_page", return_value=document):
            return relay.receive_once(self.path, 8000, PATIENT, lambda: "a" * 32, visit_workload=workload)

    def test_lifecycle_replay_and_backup(self):
        start = visit(5, 11, 1, None, "scheduled")
        active = visit(8, 11, 2, "scheduled", "in_progress")
        other = visit(9, 20, 1, None, "scheduled")
        progress = self.deliver(page(start, active, other))
        self.assertEqual(progress["visit_workload"], {"scheduled": 1, "in_progress": 1})
        done = visit(10, 11, 3, "in_progress", "completed")
        cancelled = visit(12, 20, 2, "scheduled", "cancelled")
        note = dict(event(15, NOTE), encounter_id=11, from_status=None, to_status=None)
        backup = self.path.with_name("restored")
        backup.touch(mode=0o600)
        with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(backup)) as target:
            source.backup(target)
        later = page(other, done, cancelled, note)
        final = self.deliver(later)
        self.assertEqual(final["visit_workload"], {"cancelled": 1, "completed": 1})
        self.assertEqual(self.deliver(page(note))["applied"], 0)
        self.path = backup
        self.assertEqual(self.deliver(later), final)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT count(*), count(DISTINCT access_receipt) FROM workload_receipts")
                             .fetchone(), (6, 1))
        self.assertNotIn(b"NOTE-ONE", self.path.read_bytes())

    def test_populated_legacy_backfill_then_interleaved_legacy_reader(self):
        records = [visit(i, i, 1, None, "scheduled") for i in range(1, 32)]
        self.deliver(page(*map(legacy, records[:25]), has_more=True), workload=False)
        self.deliver(page(*map(legacy, records[24:])), workload=False)
        first = self.deliver(page(*records[:25], has_more=True))
        self.assertIsNone(first["visit_workload"])
        self.assertEqual(first["applied"], 0)
        self.assertEqual(self.deliver(page(*records[24:]))["visit_workload"], {"scheduled": 31})
        move = visit(35, 1, 2, "scheduled", "cancelled")
        self.deliver(page(legacy(records[-1]), legacy(move)), workload=False)
        result = self.deliver(page(records[-1], move, access_receipt_id="ACCESS-"+"C"*32))
        self.assertEqual((result["applied"], result["visit_workload"]), (0, {"scheduled": 30, "cancelled": 1}))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT access_receipt FROM activity_receipts WHERE event_id=35").fetchone(), (RECEIPT,))
            self.assertNotEqual(db.execute("SELECT access_receipt FROM workload_receipts WHERE event_id=35").fetchone(), (RECEIPT,))

    def test_missing_revision_bad_source_and_denial_do_not_advance(self):
        start = visit(5, 11, 1, None, "scheduled")
        self.deliver(page(start))
        moved = visit(7, 11, 2, "scheduled", "in_progress")
        for invalid in [visit(8, 11, 4, "in_progress", "completed"),
                        visit(8, 11, 3, "in_progress", "scheduled"),
                        visit(8, 11, 3, "scheduled", "cancelled"),
                        visit(8, 12, 2, "scheduled", "cancelled")]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.deliver(page(start, moved, invalid))
        with patch.object(relay, "read_page", side_effect=relay.FeedUnavailable), self.assertRaises(relay.FeedUnavailable):
            relay.receive_once(self.path, 8000, PATIENT, lambda: "a" * 32, visit_workload=True)
        self.assertEqual(self.deliver(page(start))["visit_workload"], {"scheduled": 1})
        self.assertEqual(self.deliver(page(start, moved))["applied"], 1)
        with self.assertRaisesRegex(ValueError, "changed a previously applied"):
            self.deliver(page(dict(moved, to_status="cancelled")))

    def test_partial_projection_refuses_delivery_without_recreating_missing_state(self):
        start = visit(5, 11, 1, None, "scheduled")
        self.deliver(page(start))
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DROP TABLE workload_visits")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.deliver(page(start, visit(7, 11, 2, "scheduled", "in_progress")))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_schema WHERE name='workload_visits'").fetchone())
            self.assertEqual(db.execute("SELECT max(event_id) FROM activity_receipts").fetchone(), (5,))

    def test_concurrent_consumption_applies_one_transition(self):
        start = visit(5, 11, 1, None, "scheduled")
        self.deliver(page(start))
        moved = visit(7, 11, 2, "scheduled", "in_progress")
        ready = threading.Barrier(2)
        def fetch(*args, **kwargs):
            ready.wait(timeout=5)
            return page(start, moved)
        with patch.object(relay, "read_page", side_effect=fetch), ThreadPoolExecutor(2) as pool:
            attempts = [pool.submit(relay.receive_once, self.path, 8000, PATIENT, lambda: "a" * 32,
                                    visit_workload=True) for _ in range(2)]
            results = [f.result() for f in attempts]
        self.assertEqual(sorted(r["applied"] for r in results), [0, 1])
        self.assertTrue(all(r["visit_workload"] == {"in_progress": 1} for r in results))

    def test_verified_backup_preserves_partially_caught_up_workload(self):
        first = visit(5, 11, 1, None, "scheduled")
        moved = visit(9, 11, 2, "scheduled", "in_progress")
        self.deliver(page(first))
        self.deliver(page(legacy(first), legacy(moved)), workload=False)
        backup = self.path.with_name("operator-backup.sqlite")
        previous = self.path
        with patch.object(relay, "read_page", return_value=page(first, moved)) as read:
            result = relay.backup_receiver(previous, backup, 8000, PATIENT, lambda: "a"*32)
            self.assertEqual(result, {"status": "backup_verified", "verified_events": 2,
                                      "through_event_id": 9, "workload_through_event_id": 5})
            self.assertEqual(read.call_args.kwargs, {"visit_workload": True})
        self.path = backup
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT * FROM workload_receipts").fetchall(),
                             [(5, None, "scheduled", RECEIPT)])
        self.assertEqual(self.deliver(page(first, moved))["visit_workload"], {"in_progress": 1})
        with patch.object(relay, "read_page", return_value=page(first, moved)):
            verified = relay.verify_history(backup, 8000, PATIENT, lambda: "a"*32)
            self.assertEqual(verified["workload_through_event_id"], 9)

    def test_workload_drift_and_denied_replay_prevent_verification_and_backup(self):
        first = visit(5, 11, 1, None, "scheduled")
        second = visit(8, 11, 2, "scheduled", "in_progress")
        current = page(first, second)
        self.deliver(current)
        backup = self.path.with_name("unpublished.sqlite")
        cases = [
            ("UPDATE workload_visits SET status='cancelled'", current),
            ("UPDATE workload_receipts SET access_receipt='invalid' WHERE event_id=5", current),
            ("DELETE FROM workload_receipts WHERE event_id=5", current),
            ("DROP TABLE workload_visits", current),
            (None, page(first, dict(second, to_status="cancelled"))),
        ]
        for statement, source in cases:
            with self.subTest(statement=statement):
                specimen = self.path.with_name("tampered.sqlite")
                specimen.touch(mode=0o600)
                with closing(sqlite3.connect(self.path)) as original, closing(sqlite3.connect(specimen)) as db:
                    original.backup(db)
                    if statement:
                        db.execute(statement)
                        db.commit()
                with patch.object(relay, "read_page", return_value=source):
                    with self.assertRaises(ValueError):
                        relay.verify_history(specimen, 8000, PATIENT, lambda: "a"*32)
                    with self.assertRaises(ValueError):
                        relay.backup_receiver(specimen, backup, 8000, PATIENT, lambda: "a"*32)
                self.assertFalse(backup.exists())
                specimen.unlink()
        with patch.object(relay, "read_page", side_effect=relay.FeedUnavailable):
            with self.assertRaises(relay.FeedUnavailable):
                relay.backup_receiver(self.path, backup, 8000, PATIENT, lambda: "a"*32)
        self.assertFalse(backup.exists())

    def test_common_backup_preserves_inbox_ahead_of_workload_then_reopens_amended_draft(self):
        records = [visit(1, 3, 1, None, "scheduled")]
        records.extend(dict(event(i, NOTE), note_version=i - 1, from_status=None, to_status=None)
                       for i in range(2, 32))
        def feed(port, patient, token, after, *, visit_workload=False):
            remaining = [e for e in records if e["id"] > after]
            rows = remaining[:relay.PAGE_SIZE]
            return page(*(rows if visit_workload else map(legacy, rows)), has_more=len(remaining) > len(rows))
        def sync(**options):
            return relay.receive_once(self.path, 8000, PATIENT, lambda: "a"*32, **options)
        backup = self.path.with_name("restored.sqlite")
        with patch.object(relay, "read_page", side_effect=feed):
            self.assertEqual(sync(inbox_after=0)["status"], "catching_up")
            self.assertEqual(sync(inbox_after=0)["pending_drafts"][0]["event_id"], 31)
            self.assertEqual(sync(acknowledge=31)["acknowledged_event"], 31)
            self.assertIsNone(sync(visit_workload=True)["visit_workload"])
            saved = relay.backup_receiver(self.path, backup, 8000, PATIENT, lambda: "a"*32)
            self.assertEqual((saved["through_event_id"], saved["workload_through_event_id"]), (31, 25))
            digest = saved["local_acknowledgements"]["sha256"]
            self.path = backup
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute("SELECT through_id FROM draft_checkpoint").fetchall(), [(31,)])
                self.assertEqual(db.execute("SELECT event_id,access_receipt FROM draft_acknowledgements").fetchall(),
                                 [(31, RECEIPT)])
            self.assertEqual(sync(inbox_after=0)["pending_drafts"], [])
            self.assertEqual(sync(visit_workload=True)["visit_workload"], {"scheduled": 1})
            records.append(dict(event(32, NOTE), note_version=31, from_status=None, to_status=None))
            pending = sync(inbox_after=0)
            self.assertEqual((pending["applied"], pending["pending_drafts"]),
                             (1, [{"event_id": 32, "encounter_id": 3, "note_version": 31}]))
            self.assertEqual(sync(visit_workload=True)["applied"], 0)
            self.assertEqual(relay.verify_history(self.path, 8000, PATIENT, lambda: "a"*32,
                             expected_ack_sha256=digest)["workload_through_event_id"], 32)
        with patch.object(relay, "read_page", side_effect=relay.FeedUnavailable):
            for options in ({"inbox_after": 0}, {"acknowledge": 32}, {"visit_workload": True}):
                with self.assertRaises(relay.FeedUnavailable):
                    sync(**options)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT event_id FROM draft_acknowledgements").fetchall(), [(31,)])
