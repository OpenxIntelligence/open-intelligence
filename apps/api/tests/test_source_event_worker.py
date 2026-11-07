"""Delivery worker requires current independent authority before database access."""
from datetime import datetime, timedelta, timezone
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from oi_api.access import Principal
from oi_api.config import Settings
from test_patients import credential


ACTIONS = frozenset({"patient_read", "question_read", "source_read", "source_brief_export"})
TOKEN = "synthetic-event-worker-" + "e" * 32


class SourceEventWorkerTests(unittest.TestCase):
    def worker(self):
        self.assertIsNotNone(importlib.util.find_spec("oi_api.event_worker"),
                             "Durable event delivery has no independently authorized worker")
        return importlib.import_module("oi_api.event_worker")

    def test_missing_each_required_grant_blocks_before_unconfigured_database(self):
        worker = self.worker()
        for absent in sorted(ACTIONS):
            class Provider:
                def authenticate(self, token):
                    return Principal(actor="ACTOR-ONE", organization="ORG-ONE", purpose="operations",
                                     actions=ACTIONS - {absent}, patient_ids=frozenset({"PATIENT-ONE"}),
                                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=1))
            with self.subTest(absent=absent):
                self.assertEqual(worker.run_once(Settings(), lambda: TOKEN,
                                                  "PATIENT-ONE", "CASE-ALPHA", authentication=Provider()),
                                 {"status": "blocked"})
                for reader in (worker.read_status, worker.read_dead_letters):
                    self.assertEqual(reader(Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA",
                                            authentication=Provider()), {"status": "blocked"})
                self.assertEqual(worker.request_recovery(
                    Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA", authentication=Provider(),
                    delivery_id="DELIVERY-" + "A" * 32, event_id=1, expected_revision=3),
                    {"status": "blocked"})

    def test_wrong_patient_or_purpose_cannot_claim_delivery(self):
        worker = self.worker()
        for purpose, patients in (("research", {"PATIENT-ONE"}), ("operations", {"PATIENT-OTHER"})):
            class Provider:
                def authenticate(self, token):
                    return Principal(actor="ACTOR-ONE", organization="ORG-ONE", purpose=purpose,
                                     actions=ACTIONS, patient_ids=frozenset(patients),
                                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=1))
            with self.subTest(purpose=purpose, patients=patients):
                self.assertEqual(worker.run_once(Settings(), lambda: TOKEN,
                                                  "PATIENT-ONE", "CASE-ALPHA", authentication=Provider()),
                                 {"status": "blocked"})
                for reader in (worker.read_status, worker.read_dead_letters):
                    self.assertEqual(reader(Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA",
                                            authentication=Provider()), {"status": "blocked"})

    def test_provider_failure_never_discloses_credential_or_exception_details(self):
        worker = self.worker()
        private = "PRIVATE-EVENT-WORKER-PROVIDER-DETAIL"
        class Provider:
            def authenticate(self, token):
                raise RuntimeError(private + token)
        result = worker.run_once(Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA",
                                 authentication=Provider())
        self.assertEqual(result, {"status": "blocked"})
        self.assertEqual(worker.read_status(Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA",
                                            authentication=Provider()), {"status": "blocked"})
        for secret in (private, TOKEN):
            self.assertNotIn(secret, json.dumps(result))

    def test_missing_access_configuration_does_not_inherit_a_stored_actor(self):
        self.assertEqual(self.worker().run_once(Settings(), lambda: TOKEN,
                                                "PATIENT-ONE", "CASE-ALPHA"),
                         {"status": "blocked"})

    def test_invalid_lease_never_reads_a_credential(self):
        worker = self.worker()
        def forbidden_read():
            raise AssertionError("Invalid delivery lease must not read a credential")
        for value in (0, -1, 301, True, "30", 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                worker.run_once(Settings(), forbidden_read, "PATIENT-ONE", "CASE-ALPHA",
                                lease_seconds=value)

    def test_dead_letter_page_bounds_reject_before_reading_credentials(self):
        def forbidden_read():
            raise AssertionError("Invalid page must not read credentials")
        for key, values in (("limit", (0, -1, 101, True, "20", 1.5)),
                            ("after_event", (-1, 9223372036854775808, True, "0", 1.5))):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.worker().read_dead_letters(Settings(), forbidden_read,
                                                    "PATIENT-ONE", "CASE-ALPHA", **{key: value})

    def test_recovery_identity_and_revision_reject_before_reading_credentials(self):
        def forbidden_read():
            raise AssertionError("Invalid recovery request must not read credentials")
        valid = dict(delivery_id="DELIVERY-" + "A" * 32, event_id=1, expected_revision=3)
        for key, values in (("delivery_id", (None, "", "DELIVERY-invalid")),
                            ("event_id", (0, -1, True, "1", 9223372036854775808)),
                            ("expected_revision", (0, -1, True, "3", 2147483647))):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    self.worker().request_recovery(Settings(), forbidden_read,
                        "PATIENT-ONE", "CASE-ALPHA", **{**valid, key: value})

    def test_recovery_cli_requires_exact_identity_and_exclusive_mode(self):
        identity = "DELIVERY-" + "A" * 32
        for flags in (("--recover", identity),
                      ("--recover", identity, "--event-id", "1"),
                      ("--recover", identity, "--event-id", "1", "--expected-revision", "0"),
                      ("--recover", identity, "--event-id", "1", "--expected-revision", "3", "--once"),
                      ("--recover", identity, "--event-id", "1", "--expected-revision", "3", "--limit", "1"),
                      ("--status", "--event-id", "1", "--expected-revision", "3")):
            with self.subTest(flags=flags):
                result = subprocess.run([sys.executable, "-m", "oi_api.event_worker", *flags,
                                         "--patient", "PATIENT-ONE", "--case", "CASE-ALPHA"],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("error:", result.stderr)

    def test_cli_rejects_ambiguous_modes_and_invalid_pagination(self):
        for flags in (("--once", "--dead-letters"), ("--status", "--dead-letters"),
                      ("--status", "--limit", "1"), ("--once", "--after-event", "0"),
                      ("--dead-letters", "--after-event", "-1"),
                      ("--dead-letters", "--after-event", "9223372036854775808"),
                      ("--dead-letters", "--limit", "101")):
            with self.subTest(flags=flags):
                result = subprocess.run([sys.executable, "-m", "oi_api.event_worker", *flags,
                                         "--patient", "PATIENT-ONE", "--case", "CASE-ALPHA"],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("error:", result.stderr)

    def test_cli_does_not_reuse_composer_worker_credential_file(self):
        self.worker()
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "composer-token.txt"
            token_path.write_text(TOKEN)
            access_path = Path(directory) / "access.json"
            access_path.write_text(json.dumps({"version": "oi.synthetic-access/1", "credentials": [
                credential(TOKEN, actor="ACTOR-ONE", organization="ORG-ONE",
                           patients=("PATIENT-ONE",), actions=sorted(ACTIONS)),
            ]}))
            env = {key: value for key, value in os.environ.items() if not key.startswith("OI_API_")}
            env.update(OI_API_ACCESS_FILE=str(access_path), OI_API_WORKER_TOKEN_FILE=str(token_path),
                       OI_API_ENVIRONMENT="synthetic")
            result = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--once",
                                     "--patient", "PATIENT-ONE", "--case", "CASE-ALPHA"],
                                    env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"status": "blocked"})
            self.assertEqual(result.stderr, "")
            self.assertNotIn(TOKEN, result.stdout)


if __name__ == "__main__":
    unittest.main()
