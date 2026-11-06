"""Worker entry never treats a stored actor or CLI argument as current authority."""
from datetime import datetime, timedelta, timezone
import importlib
import unittest

from oi_api.access import Principal
from oi_api.config import Settings


class ComposerRunWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = importlib.import_module("oi_api.worker")

    def test_denied_scope_stops_before_opening_unconfigured_database(self):
        class Provider:
            def authenticate(self, token):
                return Principal(actor="ACTOR-ONE", organization="ORG-ONE", purpose="operations",
                                 actions=frozenset(), patient_ids=frozenset({"PATIENT-ONE"}),
                                 expires_at=datetime.now(timezone.utc) + timedelta(minutes=1))
        self.assertEqual(self.worker.run_once(Settings(), lambda: "a" * 32,
                                             "PATIENT-ONE", "CASE-ALPHA", authentication=Provider()),
                         {"status": "blocked"})

    def test_credentials_and_provider_details_never_enter_failure_receipt(self):
        secret = "PRIVATE-WORKER-CREDENTIAL"
        class Provider:
            def authenticate(self, token):
                raise RuntimeError(secret)
        result = self.worker.run_once(Settings(), lambda: "a" * 32,
                                      "PATIENT-ONE", "CASE-ALPHA", authentication=Provider())
        self.assertEqual(result, {"status": "blocked"})
        self.assertNotIn(secret, repr(result))
        result = self.worker.run_once(Settings(), lambda: secret,
                                      "PATIENT-ONE", "CASE-ALPHA", authentication=Provider())
        self.assertEqual(result, {"status": "blocked"})

    def test_worker_requires_explicit_synthetic_access_configuration(self):
        self.assertEqual(self.worker.run_once(Settings(), lambda: "a" * 32,
                                             "PATIENT-ONE", "CASE-ALPHA"),
                         {"status": "blocked"})

    def test_lease_bound_rejected_before_any_credential_read(self):
        def unexpected():
            raise AssertionError("Invalid work must not read a credential")
        for value in (0, -1, 301, True, "30", 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.worker.run_once(Settings(), unexpected, "PATIENT-ONE", "CASE-ALPHA",
                                     lease_seconds=value)


if __name__ == "__main__":
    unittest.main()
