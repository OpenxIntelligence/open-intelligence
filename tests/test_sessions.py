"""Slice 1 server-side sessions (store level, fictional only).

Sessions carry a 24-hour expiry and server-side revocation. Only the
SHA-256 hash of a token is stored; the token itself is never persisted.
"""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

DEMO = "FICTIONAL-NAVIGATOR-A"
PASSWORD = "fictional-demo-1"


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "sessions.sqlite")
        self.store = CaseStore(self.db_path)
        self.store.create_account(DEMO, "Fictional demo navigator", "clinician", PASSWORD)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_issue_and_validate_round_trip(self):
        token, record = self.store.issue_session(DEMO)
        self.assertTrue(token)
        self.assertEqual(record["account_id"], DEMO)
        expires = datetime.fromisoformat(record["expires_at"])
        created = datetime.fromisoformat(record["created_at"])
        self.assertEqual((expires - created), timedelta(hours=24))
        account = self.store.validate_session(token)
        self.assertIsNotNone(account)
        self.assertEqual(account["account_id"], DEMO)
        self.assertEqual(account["role"], "clinician")
        self.assertNotIn("password_hash", account)
        # The raw token is never stored; only its hash is.
        rows = self.store.db.execute("SELECT token_hash FROM sessions").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotEqual(rows[0]["token_hash"], token)
        self.assertEqual(len(rows[0]["token_hash"]), 64)

    def test_validate_rejects_unknown_and_malformed_tokens(self):
        self.assertIsNone(self.store.validate_session("not-a-real-token"))
        self.assertIsNone(self.store.validate_session(""))
        self.assertIsNone(self.store.validate_session(None))

    def test_revoke_session(self):
        token, _ = self.store.issue_session(DEMO)
        self.assertTrue(self.store.revoke_session(token))
        self.assertIsNone(self.store.validate_session(token))
        self.assertFalse(self.store.revoke_session(token))
        self.assertFalse(self.store.revoke_session("not-a-real-token"))

    def test_expired_session_does_not_validate(self):
        token, _ = self.store.issue_session(DEMO)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        self.store.db.execute("UPDATE sessions SET expires_at=?", (past,))
        self.store.db.commit()
        self.assertIsNone(self.store.validate_session(token))

    def test_issue_requires_active_account(self):
        with self.assertRaises(InvalidInput):
            self.store.issue_session("FICTIONAL-NOBODY")
        self.store.set_account_status(DEMO, "disabled")
        with self.assertRaises(InvalidInput):
            self.store.issue_session(DEMO)

    def test_revoke_account_sessions(self):
        first, _ = self.store.issue_session(DEMO)
        second, _ = self.store.issue_session(DEMO)
        self.assertEqual(self.store.revoke_account_sessions(DEMO), 2)
        self.assertIsNone(self.store.validate_session(first))
        self.assertIsNone(self.store.validate_session(second))
        self.assertEqual(self.store.revoke_account_sessions(DEMO), 0)
        self.assertEqual(self.store.revoke_account_sessions("FICTIONAL-NOBODY"), 0)

    def test_two_sessions_are_independent(self):
        first, _ = self.store.issue_session(DEMO)
        second, _ = self.store.issue_session(DEMO)
        self.assertNotEqual(first, second)
        self.assertTrue(self.store.revoke_session(first))
        self.assertIsNone(self.store.validate_session(first))
        self.assertIsNotNone(self.store.validate_session(second))


if __name__ == "__main__":
    unittest.main()
