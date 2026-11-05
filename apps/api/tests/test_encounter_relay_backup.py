"""Only a complete, reauthorized receiver snapshot can become a recovery file."""
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

    def test_withdrawal_after_staging_cannot_publish(self):
        with patch.object(relay, "read_page", side_effect=[self.events, relay.FeedUnavailable()]) as reads:
            with self.assertRaises(relay.FeedUnavailable):
                relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)
        self.assertEqual(reads.call_count, 2)
        self.assertEqual(list(self.source.parent.iterdir()), [self.source])

    def test_concurrent_publication_never_overwrites_winner(self):
        def feed(*_):
            self.backup.write_bytes(b"earlier backup")
            return self.events
        with patch.object(relay, "read_page", side_effect=feed), self.assertRaises(FileExistsError):
            relay.backup_receiver(self.source, self.backup, 8000, PATIENT, self.token)
        self.assertEqual(self.backup.read_bytes(), b"earlier backup")
