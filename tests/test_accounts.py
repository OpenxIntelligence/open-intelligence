"""Slice 1 local demo accounts (store level, fictional only).

Accounts are operator-created local labels, not verified identities.
Passwords are stored only as salted pbkdf2 digests; plaintext is never
stored or returned. A patient account binds to one case at creation.
"""

import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import (
    DEMO_ACTOR,
    DEMO_OPERATOR,
    FICTIONAL_ACTOR_PURPOSE,
    seed,
)

DEMO = "FICTIONAL-NAVIGATOR-A"
OPERATOR = "FICTIONAL-OPERATOR-A"
PATIENT = "FICTIONAL-PATIENT-A"
CASE_A = "CASE-FIG-01"


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "accounts.sqlite")
        self.store = CaseStore(self.db_path)
        self.store.add_case(CASE_A, "Fictional case Fig01")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_create_account_returns_public_record_only(self):
        account = self.store.create_account(
            DEMO, "Fictional demo navigator", "clinician", "fictional-demo-1")
        self.assertEqual(account["account_id"], DEMO)
        self.assertEqual(account["display_name"], "Fictional demo navigator")
        self.assertEqual(account["role"], "clinician")
        self.assertEqual(account["status"], "active")
        self.assertIsNone(account["own_case_id"])
        self.assertNotIn("password_hash", account)
        self.assertNotIn("password_salt", account)
        # The stored digest is not the password, and a salt is kept.
        row = self.store.db.execute(
            "SELECT password_hash, password_salt FROM accounts WHERE account_id=?",
            (DEMO,)).fetchone()
        self.assertNotEqual(row["password_hash"], "fictional-demo-1")
        self.assertTrue(row["password_salt"])
        self.assertEqual(len(row["password_hash"]), 64)

    def test_create_account_without_password_cannot_sign_in(self):
        self.store.create_account(DEMO, "Fictional demo navigator", "clinician")
        self.assertFalse(self.store.verify_password(DEMO, "anything-at-all"))
        self.assertFalse(self.store.verify_password(DEMO, ""))

    def test_duplicate_account_rejected(self):
        self.store.create_account(DEMO, "Fictional demo navigator", "clinician")
        with self.assertRaises(InvalidInput):
            self.store.create_account(DEMO, "Second label", "auditor")

    def test_invalid_account_fields_rejected(self):
        with self.assertRaises(InvalidInput):
            self.store.create_account("lowercase", "Label", "clinician")
        with self.assertRaises(InvalidInput):
            self.store.create_account(DEMO, "  ", "clinician")
        with self.assertRaises(InvalidInput):
            self.store.create_account(DEMO, "Label", "superuser")
        with self.assertRaises(InvalidInput):
            self.store.create_account(DEMO, "Label", "clinician", "short")

    def test_patient_requires_case_binding_at_creation(self):
        with self.assertRaises(InvalidInput):
            self.store.create_account(PATIENT, "Fictional patient", "patient")
        with self.assertRaises(InvalidInput):
            self.store.create_account(
                PATIENT, "Fictional patient", "patient", own_case_id="CASE-NOPE")
        account = self.store.create_account(
            PATIENT, "Fictional patient", "patient", "fictional-demo-1",
            own_case_id=CASE_A)
        self.assertEqual(account["own_case_id"], CASE_A)
        # Other roles bind to no case.
        with self.assertRaises(InvalidInput):
            self.store.create_account(
                OPERATOR, "Fictional operator", "operator", own_case_id=CASE_A)

    def test_verify_password_round_trip_and_wrong_password(self):
        self.store.create_account(DEMO, "Fictional demo navigator", "clinician",
                                  "fictional-demo-1")
        self.assertTrue(self.store.verify_password(DEMO, "fictional-demo-1"))
        self.assertFalse(self.store.verify_password(DEMO, "fictional-demo-2"))
        self.assertFalse(self.store.verify_password("FICTIONAL-NOBODY", "fictional-demo-1"))
        # Same password, different salt: digests differ between accounts.
        self.store.create_account(OPERATOR, "Fictional operator", "operator",
                                  "fictional-demo-1")
        rows = self.store.db.execute(
            "SELECT password_hash FROM accounts ORDER BY account_id").fetchall()
        self.assertNotEqual(rows[0]["password_hash"], rows[1]["password_hash"])

    def test_set_account_password_and_unknown_account(self):
        self.store.create_account(DEMO, "Fictional demo navigator", "clinician")
        self.assertFalse(self.store.verify_password(DEMO, "fictional-demo-1"))
        self.store.set_account_password(DEMO, "fictional-demo-1")
        self.assertTrue(self.store.verify_password(DEMO, "fictional-demo-1"))
        with self.assertRaises(InvalidInput):
            self.store.set_account_password("FICTIONAL-NOBODY", "fictional-demo-1")
        with self.assertRaises(InvalidInput):
            self.store.set_account_password(DEMO, "short")

    def test_disable_revokes_sessions_and_blocks_sign_in(self):
        self.store.create_account(DEMO, "Fictional demo navigator", "clinician",
                                  "fictional-demo-1")
        token, _ = self.store.issue_session(DEMO)
        self.assertIsNotNone(self.store.validate_session(token))
        account = self.store.set_account_status(DEMO, "disabled")
        self.assertEqual(account["status"], "disabled")
        self.assertFalse(self.store.verify_password(DEMO, "fictional-demo-1"))
        self.assertIsNone(self.store.validate_session(token))
        with self.assertRaises(InvalidInput):
            self.store.issue_session(DEMO)
        account = self.store.set_account_status(DEMO, "active")
        self.assertEqual(account["status"], "active")
        self.assertTrue(self.store.verify_password(DEMO, "fictional-demo-1"))
        with self.assertRaises(InvalidInput):
            self.store.set_account_status(DEMO, "archived")
        with self.assertRaises(InvalidInput):
            self.store.set_account_status("FICTIONAL-NOBODY", "disabled")

    def test_list_and_get_accounts_hide_credentials(self):
        self.store.create_account(DEMO, "Fictional demo navigator", "clinician",
                                  "fictional-demo-1")
        self.store.create_account(OPERATOR, "Fictional operator", "operator")
        accounts = self.store.list_accounts()
        self.assertEqual([a["account_id"] for a in accounts], [DEMO, OPERATOR])
        for account in accounts:
            self.assertNotIn("password_hash", account)
            self.assertNotIn("password_salt", account)
        self.assertIsNone(self.store.get_account("FICTIONAL-NOBODY"))
        self.assertEqual(
            self.store.get_account(DEMO)["display_name"], "Fictional demo navigator")


class SeedAccountTests(unittest.TestCase):
    def test_seed_creates_demo_accounts_and_grants_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "seed.sqlite")
            seed(db_path)
            store = CaseStore(db_path)
            try:
                demo = store.get_account(DEMO_ACTOR)
                operator = store.get_account(DEMO_OPERATOR)
                self.assertIsNotNone(demo)
                self.assertEqual(demo["role"], "clinician")
                self.assertEqual(demo["status"], "active")
                self.assertIsNotNone(operator)
                self.assertEqual(operator["role"], "operator")
                # Seeded accounts are passwordless until an operator sets one.
                self.assertFalse(store.verify_password(DEMO_ACTOR, "fictional-demo-1"))
                self.assertFalse(store.verify_password(DEMO_OPERATOR, "fictional-demo-1"))
                # The seeded grants are unchanged: the demo actor holds a live
                # grant on each seeded demo case.
                for case_id in ("CASE-ALPHA", "CASE-BETA"):
                    self.assertTrue(store.has_active_grant(
                        DEMO_ACTOR, case_id, FICTIONAL_ACTOR_PURPOSE))
                grants_before = store.db.execute(
                    "SELECT COUNT(*) FROM actor_grants").fetchone()[0]
                accounts_before = store.db.execute(
                    "SELECT COUNT(*) FROM accounts").fetchone()[0]
            finally:
                store.close()
            # Re-seeding never duplicates an account or a live grant.
            seed(db_path)
            store = CaseStore(db_path)
            try:
                self.assertIsNotNone(store.get_account(DEMO_ACTOR))
                self.assertIsNotNone(store.get_account(DEMO_OPERATOR))
                self.assertEqual(store.db.execute(
                    "SELECT COUNT(*) FROM actor_grants").fetchone()[0], grants_before)
                self.assertEqual(store.db.execute(
                    "SELECT COUNT(*) FROM accounts").fetchone()[0], accounts_before)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
