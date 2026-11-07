"""Only a complete, reauthorized receiver snapshot can become a recovery file."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from unittest.mock import patch

from oi_api import encounter_relay as relay
from test_encounter_relay import PATIENT, NOTE, event, page


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.source = Path(self.directory.name) / "running.sqlite"
        self.backup = self.source.with_name("copy.sqlite")
        self.token = lambda: "t" * 32
        self.events = page(event(2), event(5, NOTE))
        with patch.object(relay, "read_page", return_value=self.events):
            relay.receive_once(self.source, 8000, PATIENT, self.token)

    def test_copy_carries_original_receipts_and_ignores_foreign_tables(self):
        with sqlite3.connect(self.source) as db:
            db.execute("CREATE TABLE unrelated (body TEXT)")
            db.execute("INSERT INTO unrelated VALUES ('unrelated local data')")
            intended = list(db.execute("SELECT * FROM activity_receipts ORDER BY event_id"))
        with patch.object(relay, "read_page", return_value=self.events):
            result = relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)
        self.assertEqual(result, {"status":"backup_verified","through_event_id":5,"verified_events":2})
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o600)
        with sqlite3.connect(self.backup) as db:
            self.assertEqual(list(db.execute("SELECT * FROM activity_receipts ORDER BY event_id")), intended)
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_schema WHERE name='unrelated'").fetchone())
        with self.assertRaises(FileExistsError):
            relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)

    def test_denial_or_old_event_divergence_cannot_publish_a_copy(self):
        for denied in (True, False):
            chosen = ({"side_effect":relay.FeedUnavailable()} if denied else
                      {"return_value":page(event(3), event(5, NOTE))})
            with patch.object(relay, "read_page", **chosen), self.assertRaises((relay.FeedUnavailable, ValueError)):
                relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)
            self.assertEqual(list(self.source.parent.iterdir()), [self.source])

    def test_concurrent_publication_never_overwrites_winner(self):
        def feed(*_):
            self.backup.write_bytes(b"earlier backup")
            return self.events
        with patch.object(relay, "read_page", side_effect=feed), self.assertRaises(FileExistsError):
            relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)
        self.assertEqual(self.backup.read_bytes(), b"earlier backup")

    def test_restore_pending_draft_and_compare_retained_local_acknowledgement(self):
        with patch.object(relay, "read_page", side_effect=relay.FeedUnavailable), self.assertRaises(relay.FeedUnavailable):
            relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)
        self.assertFalse(self.backup.exists())
        with patch.object(relay, "read_page", return_value=self.events):
            self.assertEqual(relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)["verified_events"], 2)
        with patch.object(relay, "read_page", return_value=page(event(5, NOTE))):
            pending = relay.receive_once(self.backup, 8000, PATIENT, self.token, inbox_after=0)
            self.assertEqual((pending["applied"], pending["pending_drafts"][0]["event_id"]), (0, 5))
            self.assertEqual(relay.receive_once(self.backup, 8000, PATIENT, self.token, acknowledge=5)["acknowledged_event"], 5)
        other = self.source.with_name("second.sqlite")
        with patch.object(relay, "read_page", return_value=self.events):
            saved = relay.backup_receiver(self.backup, other, 8000, PATIENT, self.token)
            receipt = saved["local_acknowledgements"]
            self.assertEqual((receipt["count"], receipt["source"]), (1, "local_operations_receiver"))
            digest = receipt["sha256"]
            self.assertEqual(relay.verify_history(other, 8000, PATIENT, self.token,
                             expected_ack_sha256=digest)["local_acknowledgements"], receipt)
            with closing(sqlite3.connect(other)) as db, db:
                db.execute("DELETE FROM draft_acknowledgements")
            with self.assertRaisesRegex(ValueError, "saved backup receipt"):
                relay.verify_history(other, 8000, PATIENT, self.token, expected_ack_sha256=digest)

    def test_cannot_publish_altered_receipt_projection_or_empty_snapshot(self):
        for statement in ("UPDATE activity_receipts SET event_sha256='changed' WHERE event_id=2",
                          "UPDATE activity_receipts SET access_receipt='changed' WHERE event_id=2",
                          "INSERT INTO draft_acknowledgements VALUES (2, 'ACCESS-00000000000000000000000000000000')",
                          "INSERT INTO draft_acknowledgements VALUES (5, 'invalid')",
                          "UPDATE latest_drafts SET note_version=9",
                          "DELETE FROM latest_drafts",
                          "UPDATE draft_checkpoint SET through_id=2",
                          "PRAGMA user_version=1"):
            with self.subTest(statement=statement):
                altered = self.source.with_name("altered.sqlite")
                altered.touch(mode=0o600)
                try:
                    with closing(sqlite3.connect(self.source)) as src, closing(sqlite3.connect(altered)) as dst, dst:
                        src.backup(dst)
                        dst.execute(statement)
                    with patch.object(relay, "read_page", return_value=self.events), self.assertRaises(ValueError):
                        relay.backup_receiver(altered, self.backup, 8000, PATIENT, self.token)
                    self.assertFalse(self.backup.exists())
                finally:
                    altered.unlink()
        empty = self.source.with_name("empty.sqlite")
        with patch.object(relay, "read_page", return_value=page()):
            relay.receive_once(empty, 8000, PATIENT, self.token)
            with self.assertRaisesRegex(ValueError, "empty"):
                relay.backup_receiver(empty, self.backup, 8000, PATIENT, self.token)
        self.assertFalse(self.backup.exists())

    def test_v1_backup_remains_readable_and_upgrades_with_authorized_history(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            for name in ("draft_acknowledgements", "latest_drafts", "draft_checkpoint"):
                db.execute("DROP TABLE " + name)
            db.execute("PRAGMA user_version=1")
        with patch.object(relay, "read_page", return_value=self.events):
            relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)
            with closing(sqlite3.connect(self.backup)) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone(), (1,))
            result = relay.receive_once(self.backup, 8000, PATIENT, self.token, inbox_after=0)
            self.assertEqual((result["applied"], result["pending_drafts"][0]["event_id"]), (0, 5))
            self.assertEqual(relay.verify_history(self.backup, 8000, PATIENT, self.token)["verified_events"], 2)
