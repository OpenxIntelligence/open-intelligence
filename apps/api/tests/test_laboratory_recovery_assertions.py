"""Negative controls for the restored laboratory rejection check."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "laboratory_recovery", Path(__file__).resolve().parents[1] / "tools/verify_fhir_laboratory_compose.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class LaboratoryRecoveryAssertions(unittest.TestCase):
    def setUp(self):
        self.before = {"review_returns": [{"receipt_id": "REVIEW-FICTIONAL"}],
            "snapshots": [{"snapshot_id": "SNAPSHOT-FICTIONAL"}], "sequence_state": [
                {"schemaname": "identity", "sequencename": "identity_domain_events_id_seq",
                 "increment_by": 1, "cache_size": 1, "last_value": 40},
                {"schemaname": "investigation", "sequencename": "fictional_seq",
                 "increment_by": 1, "cache_size": 1, "last_value": 9}]}
        self.after = deepcopy(self.before)
        self.after["sequence_state"][0]["last_value"] = 42
        self.events = [{"id": 40, "event_type": "source.read_authorized"}]

    def check(self, after=None, events=None):
        return probe.assert_rejected_inspection_unchanged(self.before,
            self.after if after is None else after, self.events, self.events if events is None else events)

    def test_allows_uncommitted_audit_sequence_allocations_only(self):
        self.assertEqual(self.check(), 2)
        self.assertEqual(self.check(after=deepcopy(self.before)), 0)

    def test_rejects_changed_business_rows_and_committed_audit_events(self):
        for table in ("review_returns", "snapshots"):
            changed = deepcopy(self.after)
            changed[table].append({"unexpected": "committed"})
            with self.subTest(table=table), self.assertRaises(AssertionError):
                self.check(after=changed)
        for events in ([], self.events + [{"id": 41, "event_type": "investigation.laboratory_snapshot.reopened"}]):
            with self.subTest(events=events), self.assertRaises(AssertionError):
                self.check(events=events)

    def test_rejects_other_sequence_changes_rewinds_or_metadata_changes(self):
        for index, field, value in ((1, "last_value", 10), (0, "last_value", 39),
                                    (0, "increment_by", 2), (0, "cache_size", 10)):
            changed = deepcopy(self.after)
            changed["sequence_state"][index][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(AssertionError):
                self.check(after=changed)

    def test_rejects_missing_or_duplicate_sequence_inventory(self):
        for operation in ("remove", "duplicate"):
            changed = deepcopy(self.after)
            if operation == "remove":
                changed["sequence_state"].pop(0)
            else:
                changed["sequence_state"].append(deepcopy(changed["sequence_state"][0]))
            with self.subTest(operation=operation), self.assertRaises(AssertionError):
                self.check(after=changed)
