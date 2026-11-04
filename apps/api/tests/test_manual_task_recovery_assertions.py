"""Negative controls for the real recovery gate's retry-audit assertion.

These check the acceptance oracle, not database or HTTP behavior. Actual
application acceptance remains the populated Compose recovery journey.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "manual_task_recovery", Path(__file__).resolve().parents[1] / "tools/manual_task_recovery.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

EVENTS = "identity.identity_domain_events"
SEQUENCE = "identity.identity_domain_events_id_seq"
DEPENDENCIES = probe.DEPENDENCIES


class ManualTaskRetryAuditTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            "tables": {
                DEPENDENCIES: [{"task_id": "TASK-FICTIONAL", "references_sha256": "a" * 64}],
                "coordination.question_followthrough_events": [{"revision": 3, "status": "acknowledged"}],
                EVENTS: [{"id": 1, "patient_id": "PAT-FICTIONAL", "event_type": "historical",
                          "metadata_json": {"receipt_id": "ACCESS-" + "1" * 32}}],
            },
            "sequences": {SEQUENCE: {"last_value": 1, "is_called": True},
                          "other.sequence": {"last_value": 7, "is_called": True}},
            "sequence_properties": [{"increment_by": 1}],
        }
        self.expected = [{"patient_id": "PAT-FICTIONAL", "event_type": event,
                          "metadata_json": {"case_id": "CASE-FICTIONAL", "actor": "ACTOR-FICTIONAL"}}
                         for event in ("investigation.question_passages_access_prepared", "source.read_authorized")]
        self.after = deepcopy(self.before)
        for index, expected in enumerate(self.expected, 2):
            self.after["tables"][EVENTS].append({**expected, "id": index,
                "metadata_json": {**expected["metadata_json"], "receipt_id": "ACCESS-" + "2" * 32}})
        self.after["sequences"][SEQUENCE] = {"last_value": 3, "is_called": True}

    def test_accepts_only_exact_audited_retries_and_no_event_correction_retry(self):
        probe.assert_retry_audit(self.before, self.after, self.expected)
        probe.assert_retry_audit(self.before, deepcopy(self.before), [])
        single = deepcopy(self.after)
        single["tables"][EVENTS].pop()
        single["sequences"][SEQUENCE]["last_value"] = 2
        probe.assert_retry_audit(self.before, single, self.expected[:1])

    def test_rejects_lost_dependency_and_business_mutation(self):
        for alteration in ("missing_row", "changed_digest", "task_event", "missing_table"):
            with self.subTest(alteration=alteration):
                after = deepcopy(self.after)
                if alteration == "missing_row": after["tables"][DEPENDENCIES] = []
                if alteration == "changed_digest": after["tables"][DEPENDENCIES][0]["references_sha256"] = "b" * 64
                if alteration == "task_event": after["tables"]["coordination.question_followthrough_events"][0]["status"] = "completed"
                if alteration == "missing_table": del after["tables"][DEPENDENCIES]
                with self.assertRaises(AssertionError):
                    probe.assert_retry_audit(self.before, after, self.expected)

    def test_rejects_unauthorized_or_rewritten_event_and_receipt(self):
        for alteration in ("old_event", "duplicate_business", "wrong_patient", "wrong_case", "wrong_actor",
                           "reused_receipt", "split_receipt", "missing_event", "bad_receipt"):
            with self.subTest(alteration=alteration):
                after = deepcopy(self.after)
                row = after["tables"][EVENTS][-1]
                if alteration == "old_event": after["tables"][EVENTS][0]["event_type"] = "changed"
                if alteration == "duplicate_business": row["event_type"] = "coordination.followthrough.transitioned"
                if alteration == "wrong_patient": row["patient_id"] = "PAT-OTHER"
                if alteration == "wrong_case": row["metadata_json"]["case_id"] = "CASE-OTHER"
                if alteration == "wrong_actor": row["metadata_json"]["actor"] = "ACTOR-OTHER"
                if alteration == "reused_receipt": row["metadata_json"]["receipt_id"] = "ACCESS-" + "1" * 32
                if alteration == "split_receipt": row["metadata_json"]["receipt_id"] = "ACCESS-" + "3" * 32
                if alteration == "missing_event": after["tables"][EVENTS].pop()
                if alteration == "bad_receipt": row["metadata_json"]["receipt_id"] = "not-a-receipt"
                with self.assertRaises(AssertionError):
                    probe.assert_retry_audit(self.before, after, self.expected)

    def test_rejects_unaccounted_sequence_consumption_and_properties(self):
        for alteration in ("gap", "counter", "business_sequence", "properties", "no_event_consumption"):
            with self.subTest(alteration=alteration):
                after, expected = deepcopy(self.after), self.expected
                if alteration == "gap": after["tables"][EVENTS][-1]["id"] = 4
                if alteration == "counter": after["sequences"][SEQUENCE]["last_value"] = 4
                if alteration == "business_sequence": after["sequences"]["other.sequence"]["last_value"] += 1
                if alteration == "properties": after["sequence_properties"][0]["increment_by"] = 2
                if alteration == "no_event_consumption":
                    after, expected = deepcopy(self.before), []
                    after["sequences"][SEQUENCE]["last_value"] += 1
                with self.assertRaises(AssertionError):
                    probe.assert_retry_audit(self.before, after, expected)
