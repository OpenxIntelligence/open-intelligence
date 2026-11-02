"""First-party LIS events share a transactional outbox but never fake patient identity."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from open_intelligence.clinical_lab import ClinicalLabOperations
from open_intelligence.platform_events import OutboxContractError, consume_ordered, validate_event
from open_intelligence.platform_integration import LegacyLabOutboxPublisher, VerifiedEHRChangeConsumer, IntegrationError
from open_intelligence.store import CaseStore


def report(kind, document, *, case="CASE-LAB-A", specimen=None):
    fields = ["OI-SYNTHETIC-REPORT/1", "Patient: " + case, "Document: " + document,
              "Type: " + kind, "Event-Date: 2026-01-05", "Issued-At: 2026-01-06"]
    if specimen:
        fields.append("Specimen: " + specimen)
    key = "order" if kind == "clinical" else "result"
    fields.append(f"Finding: {key}|reported|Synthetic observational statement.")
    return ("\n".join(fields) + "\n").encode()


class LegacyLabTransportTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.store = CaseStore(Path(t.name) / "lab.sqlite")
        self.addCleanup(self.store.close)
        self.store.add_case("CASE-LAB-A", "Fictional lab-source patient")
        self.publisher = LegacyLabOutboxPublisher(self.store)
        self.ops = ClinicalLabOperations(self.store, event_hook=self.publisher)

    def _order(self):
        src = self.store.import_report("CASE-LAB-A", report("clinical", "ORDER-LAB-A"))["source_id"]
        return self.ops.request_lab_order("CASE-LAB-A", "ORDER-LAB-A", src,
                                          "Fictional assay", "Synthetic requester")

    def _events(self):
        return [json.loads(r[0]) for r in self.store.db.execute(
            "SELECT envelope_json FROM platform_outbox ORDER BY seq")]

    def test_real_lab_order_accession_qc_release_emit_unbound_atomic_events(self):
        self._order()
        self.ops.accession_specimen("CASE-LAB-A", "ORDER-LAB-A", "ACCESSION-LAB-A",
                                    "SPECIMEN-LAB-A", "Synthetic accessioner")
        lab_source = self.store.import_report(
            "CASE-LAB-A", report("laboratory", "RESULT-LAB-A", specimen="SPECIMEN-LAB-A"))["source_id"]
        self.ops.record_quality_check("CASE-LAB-A", "ACCESSION-LAB-A", "QC-LAB-A",
                                      lab_source, "passed", "Synthetic checker")
        self.ops.release_observation("CASE-LAB-A", "ACCESSION-LAB-A", "RELEASE-LAB-A",
                                     lab_source, "result", "Synthetic releaser")
        events = self._events()
        self.assertEqual([e["event_type"] for e in events],
                         ["lab.order.requested", "lab.specimen.accessioned",
                          "lab.qc.recorded", "lab.observation.released"])
        self.assertEqual({e["subject_binding_id"] for e in events}, {None})
        self.assertEqual({e["issuer_namespace"] for e in events}, {"OI-LEGACY-SOURCE"})
        self.assertEqual({e["authorization_decision_ref"] for e in events}, {None})
        self.assertNotIn("Fictional assay", json.dumps(events))
        self.assertNotIn("Synthetic observational", json.dumps(events))
        for ev in events:
            validate_event(ev)
            with self.assertRaises(OutboxContractError):
                with self.store.db:
                    self.store.db.execute("BEGIN IMMEDIATE")
                    consume_ordered(self.store.db, "OI-PWM", ev, lambda *_: None)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM platform_inbox_receipts").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM clinical_lab_releases").fetchone()[0], 1)

    def test_source_outbox_failure_rolls_back_lab_order_and_local_event(self):
        src = self.store.import_report("CASE-LAB-A", report("clinical", "ORDER-LAB-A"))["source_id"]
        before = self.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        with patch("open_intelligence.platform_integration.enqueue",
                   side_effect=RuntimeError("test publisher fault")):
            with self.assertRaisesRegex(RuntimeError, "publisher fault"):
                self.ops.request_lab_order("CASE-LAB-A", "ORDER-LAB-A", src,
                                           "Fictional assay", "Synthetic requester")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM clinical_lab_orders").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM platform_outbox").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0], before)
        self.ops.request_lab_order(
            "CASE-LAB-A", "ORDER-LAB-A", src, "Fictional assay", "Synthetic requester")
        self.assertEqual(len(self._events()), 1)

    def test_duplicate_lab_order_does_not_create_duplicate_transport(self):
        self._order()
        src = self.store.db.execute("SELECT source_version_id FROM clinical_lab_orders").fetchone()[0]
        again = self.ops.request_lab_order("CASE-LAB-A", "ORDER-LAB-A", src,
                                           "Fictional assay", "Synthetic requester")
        self.assertTrue(again["duplicate"])
        self.assertEqual(len(self._events()), 1)
        self.ops.cancel_order("CASE-LAB-A", "ORDER-LAB-A", "Synthetic cancellation")
        events = self._events()
        self.assertEqual(len(events), 2)
        self.assertEqual([e["aggregate"]["revision"] for e in events], [1, 2])
        self.assertEqual({e["subject_binding_id"] for e in events}, {None})


if __name__ == "__main__":
    unittest.main()
