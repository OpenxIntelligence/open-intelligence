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
from unittest.mock import patch

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

    def test_retry_requires_a_separate_current_grant_before_database_access(self):
        class Provider:
            def authenticate(self, token):
                return Principal(actor="ACTOR-ONE", organization="ORG-ONE", purpose="operations",
                                 actions=ACTIONS, patient_ids=frozenset({"PATIENT-ONE"}),
                                 expires_at=datetime.now(timezone.utc) + timedelta(minutes=1))
        self.assertEqual(self.worker().retry_delivery(
            Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA", delivery_id="DELIVERY-" + "A" * 32,
            expected_revision=3, authentication=Provider()), {"status": "blocked"})

    def test_invalid_recovery_intent_never_reads_credentials(self):
        def forbidden_read():
            self.fail("Invalid retry read a credential")
        for identifier, revision in (("bad", 3), ("DELIVERY-" + "A" * 32, 0),
                                     ("DELIVERY-" + "A" * 32, True),
                                     ("DELIVERY-" + "A" * 32, 2**31 - 1)):
            with self.subTest(identifier=identifier, revision=revision), self.assertRaises(ValueError):
                self.worker().retry_delivery(Settings(), forbidden_read, "PATIENT-ONE", "CASE-ALPHA",
                                             delivery_id=identifier, expected_revision=revision)

    def test_cli_rejects_partial_or_mixed_recovery_intents(self):
        for flags in (("--retry-delivery", "bad", "--expected-revision", "3"),
                      ("--once", "--expected-revision", "3"),
                      ("--retry-delivery", "DELIVERY-" + "A" * 32),
                      ("--once", "--retry-delivery", "DELIVERY-" + "A" * 32, "--expected-revision", "3")):
            result = subprocess.run([sys.executable, "-m", "oi_api.event_worker", *flags,
                                     "--patient", "PATIENT-ONE", "--case", "CASE-ALPHA"],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, "")

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

    def test_cli_rejects_ambiguous_modes_and_invalid_pagination(self):
        for flags in (("--drain", "--once"), ("--status", "--max-batches", "2"),
                      ("--drain", "--max-batches", "101"), ("--drain", "--limit", "1"),
                      ("--once", "--dead-letters"), ("--status", "--dead-letters"),
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

    def test_bounded_drain_stops_at_budget_and_retains_batch_counts(self):
        worker = self.worker()
        with patch.object(worker, "run_once", side_effect=[
                {"status": "queued", "invalidated_count": 7},
                {"status": "delivered", "invalidated_count": 1}]) as execute:
            self.assertEqual(worker.run_bounded(Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA",
                                                max_batches=2),
                             {"status": "limit_reached", "batches_attempted": 2,
                              "delivered_batches": 1, "continued_batches": 1})
            self.assertEqual(execute.call_count, 2)

    def test_bounded_drain_stops_without_retrying_failure_or_fence(self):
        worker = self.worker()
        for status in ("idle", "queued", "blocked", "unavailable", "dead_letter", "fenced"):
            with self.subTest(status=status), patch.object(worker, "run_once", side_effect=[
                    {"status": "delivered", "invalidated_count": 0}, {"status": status}]) as execute:
                result = worker.run_bounded(Settings(), lambda: TOKEN, "PATIENT-ONE", "CASE-ALPHA")
                self.assertEqual(result, {"status": status, "batches_attempted": 2,
                                          "delivered_batches": 1, "continued_batches": 0})
                self.assertEqual(execute.call_count, 2)

    def test_bounded_drain_rejects_invalid_budget_before_reading_credentials(self):
        def forbidden_read():
            raise AssertionError("Invalid budget must not read credentials")
        for value in (0, -1, 101, True, "20", 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.worker().run_bounded(Settings(), forbidden_read, "PATIENT-ONE", "CASE-ALPHA",
                                          max_batches=value)

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
