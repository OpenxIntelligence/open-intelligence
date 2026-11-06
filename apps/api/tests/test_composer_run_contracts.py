"""Bounded execution controls cannot imply AI execution or clinical authority."""
from datetime import datetime, timezone
import importlib
import unittest

from pydantic import ValidationError


class ComposerRunContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts = importlib.import_module("oi_api.composer_run_contracts")

    def intent(self, **changes):
        return {
            "synthetic": True, "request_key": "BRIEF-RUN-ONE",
            "source_snapshot_contract": "oi.pg-source-world-model/1",
            "expected_source_snapshot_sha256": "a" * 64,
            "expected_preflight_sha256": "b" * 64, **changes,
        }

    def test_enqueue_requires_explicit_fictional_intent_and_exact_pins(self):
        model = self.contracts.EnqueueComposerRun
        self.assertEqual(model(**self.intent()).request_key, "BRIEF-RUN-ONE")
        for changes in (
            {"synthetic": False}, {"synthetic": "true"}, {"synthetic": 1},
            {"expected_source_snapshot_sha256": "latest"},
            {"expected_preflight_sha256": "B" * 64},
            {"source_snapshot_contract": "unversioned"},
            {"request_key": "bad\nkey"}, {"request_key": "x" * 129},
            {"model": "arbitrary-model"}, {"max_attempts": 1000},
            {"bearer_token": "private"}, {"kind": "arbitrary-code"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                model(**self.intent(**changes))

    def test_cancel_is_bounded_and_requires_explicit_fictional_intent(self):
        model = self.contracts.CancelComposerRun
        self.assertIs(model(synthetic=True).synthetic, True)
        for data in ({}, {"synthetic": False}, {"synthetic": "true"},
                     {"synthetic": True, "command": "shell"}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                model(**data)

    def test_public_status_withholds_worker_credentials_and_unproven_authority(self):
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        data = {
            "contract": "oi.synthetic-composer-run/1", "synthetic": True,
            "run_id": "RUN-" + "A" * 32, "patient_id": "PATIENT-ONE",
            "case_id": "CASE-ALPHA", "question_id": "QUESTION-" + "B" * 32,
            "kind": "source-question-brief/1", "state": "queued",
            "revision": 1, "attempt_count": 0, "max_attempts": 3,
            "source_snapshot_contract": "oi.pg-source-world-model/1",
            "source_snapshot_sha256": "a" * 64, "preflight_sha256": "b" * 64,
            "created_at": now, "updated_at": now, "available_at": now,
            "lease_expires_at": None, "result_sha256": None,
            "model_executed": False, "clinical_approval": False,
        }
        model = self.contracts.ComposerRunStatus
        self.assertEqual(model(**data).state, "queued")
        for changes in (
            {"lease_token": "PRIVATE-LEASE"}, {"actor": "PRIVATE-ACTOR"},
            {"state": "clinically_approved"}, {"model_executed": True},
            {"clinical_approval": True}, {"attempt_count": 4},
            {"created_at": "2026-11-05T00:00:00"},
            {"state": "running", "attempt_count": 1, "lease_expires_at": None},
            {"state": "completed", "result_sha256": None},
            {"result_sha256": "c" * 64},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                model(**{**data, **changes})


if __name__ == "__main__":
    unittest.main()
