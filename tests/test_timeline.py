import unittest
from pathlib import Path

from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.timeline import case_timeline

SYNTHETIC = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


def _report(document, event_date, issued_at, findings, specimen=None):
    lines = ["OI-SYNTHETIC-REPORT/1", "Patient: CASE-TIME",
             f"Document: {document}", "Type: laboratory",
             f"Event-Date: {event_date}", f"Issued-At: {issued_at}"]
    if specimen is not None:
        lines.append(f"Specimen: {specimen}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode()


EARLY_DOC = _report("DOC-EARLY", "2026-07-01", "2026-07-02",
                    [("marker-b", "reported", "Fictional note records Marker B as present.")])
LATE_DOC = _report("DOC-LATE", "2026-07-01", "2026-07-05",
                   [("marker-c", "reported", "Fictional note records Marker C as present.")])
CONFLICT_A = _report("DOC-A", "2026-05-10", "2026-05-11",
                     [("marker-b", "reported", "Fictional note A records Marker B as present.")],
                     specimen="SPECIMEN-X")
CONFLICT_B = _report("DOC-B", "2026-05-24", "2026-05-25",
                     [("marker-c", "reported", "Fictional note B records Marker C as present.")],
                     specimen="SPECIMEN-X")


def _alpha(store):
    store.add_case("CASE-ALPHA", "Fictional case Alpha")
    store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
    store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes())


class TimelineTests(unittest.TestCase):
    def test_orders_by_occurred_regardless_of_import_order(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-ALPHA", "Fictional case Alpha")
        store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-imaging.txt").read_bytes())
        store.import_report("CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        result = case_timeline(store, "CASE-ALPHA")
        self.assertEqual([e["document_id"] for e in result["entries"]],
                         ["PATH-ALPHA", "IMG-ALPHA"])
        self.assertEqual([e["occurred"] for e in result["entries"]],
                         ["2026-05-03", "2026-05-17"])

    def test_documented_breaks_occurred_ties(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-TIME", "Fictional time case")
        store.import_report("CASE-TIME", LATE_DOC)
        store.import_report("CASE-TIME", EARLY_DOC)
        result = case_timeline(store, "CASE-TIME")
        self.assertEqual([e["document_id"] for e in result["entries"]],
                         ["DOC-EARLY", "DOC-LATE"])
        self.assertEqual([e["documented"] for e in result["entries"]],
                         ["2026-07-02", "2026-07-05"])

    def test_time_facets_never_collapsed(self):
        store = CaseStore(":memory:")
        _alpha(store)
        result = case_timeline(store, "CASE-ALPHA")
        entry = result["entries"][0]
        for facet in ("occurred", "documented", "received", "coverage",
                      "supersedes_source_id"):
            self.assertIn(facet, entry)
        # Fixture dates differ, so a collapsed single date cannot pass.
        self.assertEqual(entry["occurred"], "2026-05-03")
        self.assertEqual(entry["documented"], "2026-05-05")
        self.assertNotEqual(entry["occurred"], entry["documented"])
        self.assertNotEqual(entry["received"][:10], entry["occurred"])
        self.assertEqual(entry["coverage"], "known")
        self.assertIn("as_of", result)
        self.assertEqual(set(result["as_of"]), {"event_id", "occurred_at"})
        latest = max(e["id"] for e in store.state("CASE-ALPHA")["events"])
        self.assertEqual(result["as_of"]["event_id"], latest)

    def test_gaps_reported_unknown_never_filled(self):
        store = CaseStore(":memory:")
        _alpha(store)
        result = case_timeline(store, "CASE-ALPHA")
        self.assertEqual(result["counts"]["gaps"], 1)
        gap = result["gaps"][0]
        self.assertEqual(gap["start_date"], "2026-05-04")
        self.assertEqual(gap["end_date"], "2026-05-16")
        self.assertEqual(gap["coverage"], "unknown")
        self.assertEqual(gap["before"],
                         {"occurred": "2026-05-03", "document_ids": ["PATH-ALPHA"]})
        self.assertEqual(gap["after"],
                         {"occurred": "2026-05-17", "document_ids": ["IMG-ALPHA"]})
        # The gap invents no entries.
        self.assertEqual(result["counts"]["entries"], 2)

    def test_adjacent_dates_have_no_gap(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-TIME", "Fictional time case")
        store.import_report("CASE-TIME", _report(
            "DOC-ONE", "2026-06-01", "2026-06-01",
            [("marker-b", "reported", "Fictional note one.")]))
        store.import_report("CASE-TIME", _report(
            "DOC-TWO", "2026-06-02", "2026-06-02",
            [("marker-c", "reported", "Fictional note two.")]))
        result = case_timeline(store, "CASE-TIME")
        self.assertEqual(result["gaps"], [])
        self.assertEqual(result["counts"]["entries"], 2)

    def test_conflicting_specimen_dates_flagged_unknown(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-TIME", "Fictional time case")
        store.import_report("CASE-TIME", CONFLICT_A)
        store.import_report("CASE-TIME", CONFLICT_B)
        result = case_timeline(store, "CASE-TIME")
        self.assertEqual(result["counts"]["conflicts"], 1)
        conflict = result["conflicts"][0]
        self.assertEqual(conflict["conflict_key"], "specimen:SPECIMEN-X")
        self.assertEqual(conflict["status"], "unknown")
        self.assertEqual(conflict["asserted_occurred_dates"], ["2026-05-10", "2026-05-24"])
        self.assertEqual(len(conflict["sources"]), 2)
        # Both assertions stay visible; neither is picked or dropped.
        self.assertEqual(result["counts"]["entries"], 2)

    def test_agreeing_specimen_dates_have_no_conflict(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-TIME", "Fictional time case")
        store.import_report("CASE-TIME", _report(
            "DOC-A", "2026-05-10", "2026-05-11",
            [("marker-b", "reported", "Fictional note A.")], specimen="SPECIMEN-X"))
        store.import_report("CASE-TIME", _report(
            "DOC-B", "2026-05-10", "2026-05-12",
            [("marker-c", "reported", "Fictional note B.")], specimen="SPECIMEN-X"))
        result = case_timeline(store, "CASE-TIME")
        self.assertEqual(result["conflicts"], [])

    def test_document_date_conflict_flagged_not_guessed(self):
        store = CaseStore(":memory:")
        _alpha(store)
        # The import contract blocks this shape; simulate legacy rows to prove
        # the projection flags rather than resolves them.
        store.db.execute(
            """INSERT INTO source_versions (case_id,document_id,version,sha256,raw,kind,
            event_date,issued_at,received_at,specimen_id,state,supersedes_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("CASE-ALPHA", "PATH-ALPHA", 99, "0" * 64, b"legacy", "pathology",
             "2026-04-01", "2026-04-02", "2026-04-03T00:00:00+00:00",
             "BIOPSY-ALPHA", "superseded", None))
        store.db.commit()
        result = case_timeline(store, "CASE-ALPHA")
        document = [c for c in result["conflicts"] if c["conflict_key"] == "document:PATH-ALPHA"]
        self.assertEqual(len(document), 1)
        self.assertEqual(document[0]["status"], "unknown")
        self.assertEqual(document[0]["asserted_occurred_dates"], ["2026-04-01", "2026-05-03"])

    def test_amendment_supersession_history_only(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-ALPHA", "Fictional case Alpha")
        first = store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-original.txt").read_bytes())
        second = store.import_report(
            "CASE-ALPHA", (SYNTHETIC / "alpha-pathology-amended.txt").read_bytes())
        result = case_timeline(store, "CASE-ALPHA")
        self.assertEqual([e["source_id"] for e in result["entries"]], [second["source_id"]])
        entry = result["entries"][0]
        self.assertEqual(entry["version"], 2)
        self.assertEqual(entry["supersedes_source_id"], first["source_id"])
        self.assertEqual(result["counts"]["superseded_versions"], 1)
        historic = result["history"][0]
        self.assertEqual(historic["source_id"], first["source_id"])
        self.assertEqual(historic["state"], "superseded")
        self.assertEqual(historic["occurred"], "2026-05-03")
        self.assertEqual(historic["superseded_by_source_id"], second["source_id"])

    def test_no_clinical_inference_vocabulary(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-TIME", "Fictional time case")
        store.import_report("CASE-TIME", CONFLICT_A)
        store.import_report("CASE-TIME", CONFLICT_B)
        result = case_timeline(store, "CASE-TIME")
        body = str({k: v for k, v in result.items() if k != "disclaimer"}).lower()
        for word in ("response", "progression", "staging", "grading",
                     "eligibility", "efficacy", "treatment", "significan",
                     "benefit", "improved", "worsened"):
            self.assertNotIn(word, body)
        self.assertIn("unknown", body)

    def test_purity_two_calls_identical_no_writes(self):
        store = CaseStore(":memory:")
        _alpha(store)
        before = store.state("CASE-ALPHA")
        first = case_timeline(store, "CASE-ALPHA")
        second = case_timeline(store, "CASE-ALPHA")
        self.assertEqual(first, second)
        after = store.state("CASE-ALPHA")
        self.assertEqual(before["events"], after["events"])
        self.assertEqual(before["sources"], after["sources"])

    def test_empty_case_projection(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-EMPTY", "Fictional empty case")
        result = case_timeline(store, "CASE-EMPTY")
        self.assertEqual(result["counts"], {"entries": 0, "gaps": 0,
                                            "conflicts": 0, "superseded_versions": 0})
        self.assertEqual(result["entries"], [])
        self.assertEqual(result["gaps"], [])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["history"], [])

    def test_unknown_case(self):
        store = CaseStore(":memory:")
        _alpha(store)
        with self.assertRaises(InvalidInput):
            case_timeline(store, "CASE-NOPE")

    def test_fictional_labeling(self):
        store = CaseStore(":memory:")
        _alpha(store)
        result = case_timeline(store, "CASE-ALPHA")
        self.assertTrue(result["synthetic"])
        self.assertIn("Fictional synthetic data only", result["disclaimer"])


if __name__ == "__main__":
    unittest.main()
