"""Contract tests for the issue 115 institutional ingest receipt.

Covers the pure wrapper in src/open_intelligence/institutional_ingest.py
against the real CaseStore on main. It does not claim a FHIR ingester:
FP-01..04 FHIR bundles are not in main, and these tests prove the
same acceptance, >=3 institutions, stable fingerprints, duplicate
idempotency, and mismatched-subject quarantine, over the existing
synthetic report format.
"""

import hashlib
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore
from open_intelligence.institutional_ingest import ingest_institutions


def report(document, patient="CASE-ALPHA", finding="marker-a"):
    return (
        "OI-SYNTHETIC-REPORT/1\n"
        f"Patient: {patient}\n"
        f"Document: {document}\n"
        "Type: pathology\n"
        "Event-Date: 2026-05-03\n"
        "Issued-At: 2026-05-05\n"
        f"Finding: {finding}|reported|Fictional finding for {document}.\n"
    ).encode()


class TestInstitutionalIngest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "test.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_three_institutions_distinct_fingerprints(self):
        result = ingest_institutions(
            self.store, "CASE-ALPHA",
            [("FICT-HOSPITAL-A", report("PATH-A")),
             ("FICT-HOSPITAL-B", report("PATH-B")),
             ("FICT-HOSPITAL-C", report("PATH-C"))],
        )
        self.assertEqual(result["counts"]["total"], 3)
        self.assertEqual(result["counts"]["ingested"], 3)
        self.assertEqual(result["counts"]["distinct_fingerprints"], 3)
        self.assertEqual(
            result["institutions"][0]["fingerprint"],
            hashlib.sha256(report("PATH-A")).hexdigest(),
        )
        self.assertTrue(all(r["source_id"] for r in result["institutions"]))

    def test_duplicate_delivery_is_idempotent(self):
        first = ingest_institutions(
            self.store, "CASE-ALPHA",
            [("FICT-HOSPITAL-A", report("PATH-A")),
             ("FICT-HOSPITAL-B", report("PATH-B")),
             ("FICT-HOSPITAL-C", report("PATH-C"))],
        )
        second = ingest_institutions(
            self.store, "CASE-ALPHA",
            [("FICT-HOSPITAL-A", report("PATH-A")),
             ("FICT-HOSPITAL-B", report("PATH-B")),
             ("FICT-HOSPITAL-C", report("PATH-C"))],
        )
        self.assertEqual(second["counts"]["duplicate"], 3)
        self.assertEqual(
            second["institutions"][0]["source_id"],
            first["institutions"][0]["source_id"],
        )

    def test_wrong_patient_quarantined_not_asserted(self):
        result = ingest_institutions(
            self.store, "CASE-ALPHA",
            [("FICT-HOSPITAL-A", report("PATH-A")),
             ("FICT-HOSPITAL-B", report("PATH-B")),
             ("FICT-WRONG", report("PATH-WRONG", patient="CASE-BETA"))],
        )
        self.assertEqual(result["counts"]["quarantined"], 1)
        wrong = result["institutions"][2]
        self.assertEqual(wrong["result"], "quarantined")
        self.assertIsNotNone(wrong["quarantine_id"])
        self.assertIsNone(wrong["source_id"])

    def test_fewer_than_three_denied(self):
        with self.assertRaises(ValueError):
            ingest_institutions(
                self.store, "CASE-ALPHA",
                [("FICT-HOSPITAL-A", report("PATH-A")),
                 ("FICT-HOSPITAL-B", report("PATH-B"))],
            )

    def test_duplicate_label_denied(self):
        with self.assertRaises(ValueError):
            ingest_institutions(
                self.store, "CASE-ALPHA",
                [("FICT-HOSPITAL-A", report("PATH-A")),
                 ("FICT-HOSPITAL-A", report("PATH-B")),
                 ("FICT-HOSPITAL-C", report("PATH-C"))],
            )


if __name__ == "__main__":
    unittest.main()
