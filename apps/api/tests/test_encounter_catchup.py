"""Bounded recovery uses the existing transactional receiver on every authorized page."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from oi_api import encounter_relay as relay
from test_encounter_relay import PATIENT, SCHEDULED, event, page
from test_encounter_workload import legacy, visit


class CatchUpTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = Path(directory.name) / "receiver.sqlite"
        self.events = [dict(event(i), encounter_id=i) for i in range(1, 61)]
        self.requests = []

    def feed(self, port, patient, token, after, *, visit_workload=False):
        self.requests.append((after, token))
        remaining = [row for row in self.events if row["id"] > after]
        rows = remaining[:25]
        if not visit_workload:
            rows = list(map(legacy, rows))
        return page(*rows, has_more=len(remaining) > 25,
                    resume_after_id=rows[-1]["id"] if rows else after)

    def run_catchup(self, budget, **options):
        with patch.object(relay, "read_page", side_effect=self.feed):
            return relay.catch_up(self.database, 8000, PATIENT, lambda: "token",
                                  max_pages=budget, **options)

    def test_budget_stops_then_resume_counts_only_new_deliveries(self):
        partial = self.run_catchup(1)
        self.assertEqual((partial["status"], partial["stop_reason"], partial["pages"], partial["applied"]),
                         ("catching_up", "page_budget", 1, 25))
        final = self.run_catchup(10)
        self.assertEqual((final["status"], final["stop_reason"], final["pages"], final["applied"]),
                         ("ok", "caught_up", 2, 35))
        self.assertEqual(final["counts"], {SCHEDULED: 60})
        self.assertEqual([r[0] for r in self.requests], [0, 24, 48])
        duplicate = self.run_catchup(10)
        self.assertEqual((duplicate["applied"], duplicate["pages"]), (0, 1))

    def test_withdrawal_keeps_committed_pages_and_rechecks_token_on_resume(self):
        def fetch(*args, **options):
            if len(self.requests) == 1:
                raise relay.FeedUnavailable("grant withdrawn")
            return self.feed(*args, **options)
        tokens = iter(["first", "revoked"])
        with patch.object(relay, "read_page", side_effect=fetch), self.assertRaises(relay.FeedUnavailable):
            relay.catch_up(self.database, 8000, PATIENT, tokens.__next__, max_pages=10)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM activity_receipts").fetchone(), (25,))
        self.assertEqual(self.run_catchup(10)["applied"], 35)
        self.assertEqual(self.requests[0][1], "first")

    def test_later_divergent_page_preserves_prior_commit_and_can_resume(self):
        def fetch(*args, **options):
            document = self.feed(*args, **options)
            if len(self.requests) == 2:
                document["events"][0] = dict(document["events"][0], encounter_id=999)
            return document
        with patch.object(relay, "read_page", side_effect=fetch), self.assertRaises(ValueError):
            relay.catch_up(self.database, 8000, PATIENT, lambda: "token", max_pages=10)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT total FROM activity_totals").fetchone(), (25,))
        self.assertEqual(self.run_catchup(10)["applied"], 35)

    def test_workload_backfill_uses_budget_without_recounting_old_receipts(self):
        self.events = [visit(i, i, 1, None, "scheduled") for i in range(1, 61)]
        self.run_catchup(10)
        partial = self.run_catchup(1, visit_workload=True)
        self.assertEqual((partial["applied"], partial["visit_workload"]), (0, None))
        final = self.run_catchup(10, visit_workload=True)
        self.assertEqual((final["applied"], final["visit_workload"]), (0, {"scheduled": 60}))
        with patch.object(relay, "read_page", side_effect=self.feed):
            self.assertEqual(relay.verify_history(self.database, 8000, PATIENT, lambda: "token")["verified_events"], 60)

    def test_invalid_budget_does_not_read_or_create_a_receiver(self):
        for budget in (0, -1, 101, True, None, 1.5, "2"):
            with self.subTest(budget=budget), patch.object(relay, "read_page") as read:
                with self.assertRaises(ValueError):
                    relay.catch_up(self.database, 8000, PATIENT, lambda: "token", max_pages=budget)
                read.assert_not_called()
                self.assertFalse(self.database.exists())
