"""Operational note intake under the real receiver transaction and authorized feed contract."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from oi_api import encounter_relay as relay
from test_encounter_relay import event, page, NOTE, PATIENT, RECEIPT


def note(index, version, encounter=3, key="NOTE-ONE"):
    return dict(event(index, NOTE), note_version=version, encounter_id=encounter, note_key=key)


class DraftInboxTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "activity.sqlite"
        self.events = []

    def fetch(self, port, patient, token, after):
        rows = [row for row in self.events if row["id"] > after]
        return page(*rows[:25], has_more=len(rows) > 25,
                    resume_after_id=rows[min(len(rows), 25)-1]["id"] if rows else after)

    def sync(self, **options):
        with patch.object(relay, "read_page", side_effect=self.fetch):
            return relay.receive_once(self.database, 8000, PATIENT, lambda: "t"*32, **options)

    def test_acknowledgement_tracks_exact_revision_and_recovers_lost_response(self):
        self.events = [event(2), note(4, 1), note(10, 1, encounter=7)]
        items = self.sync(inbox_after=0)["pending_drafts"]
        self.assertEqual(items, [{"event_id": 4, "encounter_id": 3, "note_version": 1},
                                 {"event_id": 10, "encounter_id": 7, "note_version": 1}])
        self.assertEqual(self.sync(acknowledge=4)["acknowledged_event"], 4)
        self.assertEqual(self.sync(acknowledge=4)["acknowledged_event"], 4)
        self.assertEqual(self.sync(inbox_after=0)["pending_drafts"], items[1:])
        self.events.append(note(16, 2))
        self.assertEqual(self.sync(acknowledge=4)["status"], "superseded_or_unknown")
        self.assertEqual([item["event_id"] for item in self.sync(inbox_after=0)["pending_drafts"]], [10, 16])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT event_id, access_receipt FROM draft_acknowledgements").fetchall(),
                             [(4, RECEIPT)])
        self.assertNotIn(b"NOTE-ONE", self.database.read_bytes())

    def test_version_gap_rolls_back_receipt_counts_and_work_together(self):
        self.events = [note(4, 1)]
        self.sync(acknowledge=4)
        self.events.extend([note(5, 1, key="NOTE-TWO"), note(8, 3)])
        with self.assertRaisesRegex(ValueError, "version"):
            self.sync(inbox_after=0)
        self.events.pop()
        result = self.sync(inbox_after=0)
        self.assertEqual((result["applied"], result["counts"][NOTE]), (1, 2))
        self.assertEqual([item["event_id"] for item in result["pending_drafts"]], [5])

    def create_v1_store(self):
        self.database.touch(mode=0o600)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executescript("""
                CREATE TABLE activity_scope(scope_sha256 TEXT PRIMARY KEY);
                CREATE TABLE activity_receipts(event_id INTEGER PRIMARY KEY, event_sha256 TEXT NOT NULL,
                                              event_type TEXT NOT NULL, access_receipt TEXT NOT NULL);
                CREATE TABLE activity_totals(event_type TEXT PRIMARY KEY,total INTEGER NOT NULL CHECK(total >= 1));
                PRAGMA user_version=1;
            """)
            scope = hashlib.sha256(f"encounter-activity/1:127.0.0.1:8000:{PATIENT}".encode()).hexdigest()
            db.execute("INSERT INTO activity_scope VALUES (?)", (scope,))
            for row in self.events:
                body = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
                db.execute("INSERT INTO activity_receipts VALUES (?,?,?,?)",
                           (row["id"], hashlib.sha256(body).hexdigest(), NOTE, RECEIPT))
            db.execute("INSERT INTO activity_totals VALUES (?,?)", (NOTE, len(self.events)))

    def test_populated_receiver_rebuild_is_bounded_without_duplicate_counts(self):
        self.events = [note(i, 1, encounter=i) for i in range(1, 31)]
        self.create_v1_store()
        partial = self.sync(acknowledge=1)
        self.assertEqual(partial["status"], "catching_up")
        self.assertNotIn("acknowledged_event", partial)
        result = self.sync(inbox_after=0)
        self.assertEqual((result["applied"], result["counts"][NOTE]), (0, 30))
        self.assertEqual(len(result["pending_drafts"]), 25)
        self.assertEqual([x["event_id"] for x in self.sync(inbox_after=25)["pending_drafts"]], list(range(26, 31)))
        self.assertEqual(self.sync(acknowledge=1)["acknowledged_event"], 1)

    def test_v1_replay_rejects_changed_truncated_or_invented_history(self):
        self.events = [note(2, 1), note(6, 1, encounter=4)]
        self.create_v1_store()
        original = self.events.copy()
        for changed in (original[:1], original[1:], [*original[:1], note(3, 1, encounter=5), original[1]],
                        [dict(original[0], note_key="OTHER"), original[1]]):
            self.events = changed
            with self.assertRaises(ValueError):
                self.sync(acknowledge=2)
        self.events = original
        self.assertEqual(len(self.sync(inbox_after=0)["pending_drafts"]), 2)

    def test_restore_preserves_acknowledgement_then_reopens_on_next_version(self):
        self.events = [note(2, 1)]
        self.sync(acknowledge=2)
        backup = self.database.with_suffix(".backup")
        with patch.object(relay, "read_page", side_effect=self.fetch):
            summary = relay.backup_receiver(self.database, backup, 8000, PATIENT, lambda: "token")
        self.assertEqual(summary["verified_events"], 1)
        self.database = backup
        self.assertEqual(self.sync(inbox_after=0)["pending_drafts"], [])
        self.assertEqual(self.sync(acknowledge=2)["acknowledged_event"], 2)
        self.events.append(note(7, 2))
        pending = self.sync(inbox_after=0)
        self.assertEqual(pending["pending_drafts"], [dict(event_id=7, encounter_id=3, note_version=2)])
        self.assertEqual(self.sync(acknowledge=2)["status"], "superseded_or_unknown")
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT * FROM draft_acknowledgements").fetchall(), [(2, RECEIPT)])

    def test_backup_preserves_v1_and_partial_v2_backfill_without_modifying_source(self):
        self.events = [note(i, 1, encounter=i) for i in range(1, 31)]
        self.create_v1_store()
        for version, cursor in [(1, 0), (2, 25)]:
            with self.subTest(version=version):
                backup = self.database.with_suffix(f".v{version}")
                before = self.database.read_bytes()
                with patch.object(relay, "read_page", side_effect=self.fetch):
                    result = relay.backup_receiver(self.database, backup, 8000, PATIENT, lambda: "token")
                self.assertEqual(result["verified_events"], 30)
                self.assertEqual(self.database.read_bytes(), before)
                with closing(sqlite3.connect(backup)) as db:
                    self.assertEqual(db.execute("PRAGMA user_version").fetchone(), (version,))
                    if version == 2:
                        self.assertEqual(db.execute("SELECT * FROM draft_checkpoint").fetchall(), [(cursor,)])
                self.database = backup
                progress = self.sync(inbox_after=0)
                self.assertEqual(progress["applied"], 0)
                if version == 1:
                    self.assertEqual(progress["status"], "catching_up")
                else:
                    self.assertEqual(len(progress["pending_drafts"]), 25)
                    self.assertEqual(len(self.sync(inbox_after=25)["pending_drafts"]), 5)

    def test_inconsistent_inbox_or_acknowledgement_blocks_publication(self):
        self.events = [event(1), note(3, 1)]
        self.sync(acknowledge=3)
        for sql in (
            "DELETE FROM latest_drafts",
            "UPDATE latest_drafts SET note_version=9",
            "UPDATE latest_drafts SET note_key_hash='wrong'",
            "UPDATE latest_drafts SET encounter_id=7",
            "UPDATE draft_acknowledgements SET event_id=1",
            "UPDATE draft_acknowledgements SET access_receipt='invalid'",
            "INSERT INTO draft_checkpoint VALUES(3)",
            "UPDATE draft_checkpoint SET through_id=2",
        ):
            with self.subTest(sql=sql):
                damaged = self.database.with_suffix(".damaged")
                damaged.touch(mode=0o600)
                with closing(sqlite3.connect(self.database)) as src, closing(sqlite3.connect(damaged)) as dst, dst:
                    src.backup(dst)
                    dst.execute(sql)
                destination = damaged.with_suffix(".recovery")
                with patch.object(relay, "read_page", side_effect=self.fetch), self.assertRaises(ValueError):
                    relay.backup_receiver(damaged, destination, 8000, PATIENT, lambda: "token")
                self.assertFalse(destination.exists())
                damaged.unlink()

    def test_snapshot_is_consistent_when_new_draft_and_ack_arrive_during_replay(self):
        self.events = [note(2, 1), note(3, 1, encounter=5)]
        self.sync(acknowledge=2)
        backup = self.database.with_suffix(".backup")

        def fetch_while_live_receiver_advances(*args):
            self.events.append(note(7, 2))
            self.sync(acknowledge=3)
            return self.fetch(*args)

        with patch.object(relay, "read_page", side_effect=fetch_while_live_receiver_advances):
            result = relay.backup_receiver(self.database, backup, 8000, PATIENT, lambda: "token")
        self.assertEqual(result["through_event_id"], 3)
        self.assertEqual(result["local_acknowledgements"]["count"], 1)
        self.assertEqual([i["event_id"] for i in self.sync(inbox_after=0)["pending_drafts"]], [7])
        self.database = backup
        self.assertEqual([i["event_id"] for i in self.sync(inbox_after=0)["pending_drafts"]], [3, 7])

    def test_withdrawal_on_later_replay_page_discards_staged_backup(self):
        self.events = [note(i, 1, encounter=i) for i in range(1, 31)]
        self.sync()
        self.sync(acknowledge=1)
        before = self.database.read_bytes()
        backup = self.database.with_suffix(".backup")
        first = self.fetch(8000, PATIENT, "token", 0)
        with patch.object(relay, "read_page", side_effect=[first, relay.FeedUnavailable()]) as reads:
            with self.assertRaises(relay.FeedUnavailable):
                relay.backup_receiver(self.database, backup, 8000, PATIENT, lambda: "token")
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(self.database.parent.iterdir()), [self.database])
