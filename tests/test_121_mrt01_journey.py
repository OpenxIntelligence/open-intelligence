"""MRT-01 journey contract, issue 121 (WS-15), scoped slice.

A single end-to-end journey over the existing main store APIs only:
three fictional institutions ingest for one case, a draft snapshot
over those sources, an amendment to one source that makes the old
snapshot stale (targeted staleness, not case-wide deletion), a new
draft over the amended source, and a demo review acknowledgement.
A wrong-patient delivery is quarantined along the way.

This is a unit journey, not the full MRT-01 harness issue 121
describes: no Playwright browser journey, no FHIR bundles, no real
identity, consent, live retrieval, real model inference, professional
sign-off, PHI security, or production deployment. Those steps are
listed as not covered in docs/oi-121-mrt01-matrix.md, and this test
does not claim them.
"""

import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore


def report(document, patient="CASE-ALPHA", finding="marker-a", state="reported"):
    return (
        "OI-SYNTHETIC-REPORT/1\n"
        f"Patient: {patient}\n"
        f"Document: {document}\n"
        "Type: pathology\n"
        "Event-Date: 2026-05-03\n"
        "Issued-At: 2026-05-05\n"
        f"Finding: {finding}|{state}|Fictional finding for {document}.\n"
    ).encode()


def amended(document, version):
    return (
        "OI-SYNTHETIC-REPORT/1\n"
        "Patient: CASE-ALPHA\n"
        f"Document: {document}\n"
        "Type: pathology\n"
        "Event-Date: 2026-05-03\n"
        "Issued-At: 2026-05-06\n"
        f"Amends: {document}@{version}\n"
        "Finding: marker-a|not-reported|Fictional amended finding.\n"
    ).encode()


class TestMrt01Journey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "test.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_journey_three_institutions_amendment_staleness_review(self):
        a = self.store.import_report("CASE-ALPHA", report("PATH-A"))
        b = self.store.import_report("CASE-ALPHA", report("PATH-B"))
        c = self.store.import_report("CASE-ALPHA", report("PATH-C"))
        self.assertEqual([r["result"] for r in (a, b, c)], ["imported"] * 3)

        qid = self.store.add_question("CASE-ALPHA", "What do the three fictional reports say?")
        snap = self.store.create_snapshot(
            "CASE-ALPHA", qid, "Draft summary over three fictional reports.",
            [a["source_id"], b["source_id"], c["source_id"]],
        )
        state = self.store.state("CASE-ALPHA")
        snap_row = [s for s in state["snapshots"] if s["id"] == snap][0]
        self.assertEqual(snap_row["state"], "draft")

        amended_a = self.store.import_report("CASE-ALPHA", amended("PATH-A", a["version"]))
        self.assertEqual(amended_a["version"], a["version"] + 1)
        self.assertIn(snap, amended_a["invalidated_snapshots"])
        state = self.store.state("CASE-ALPHA")
        snap_row = [s for s in state["snapshots"] if s["id"] == snap][0]
        self.assertEqual(snap_row["state"], "stale")

        snap2 = self.store.create_snapshot(
            "CASE-ALPHA", qid, "Draft summary over the amended report set.",
            [amended_a["source_id"], b["source_id"], c["source_id"]],
        )
        self.store.acknowledge_demo_review("CASE-ALPHA", snap2, "Demo Reviewer")
        state = self.store.state("CASE-ALPHA")
        snap2_row = [s for s in state["snapshots"] if s["id"] == snap2][0]
        self.assertEqual(snap2_row["state"], "reviewed_in_demo")

    def test_journey_wrong_patient_quarantined(self):
        result = self.store.import_report("CASE-ALPHA", report("PATH-WRONG", patient="CASE-BETA"))
        self.assertEqual(result["result"], "quarantined")
        self.assertEqual(result["reason"], "patient_mismatch")


if __name__ == "__main__":
    unittest.main()
