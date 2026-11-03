"""B-05 behaviors 1-4: explicit subject binding + quarantine correction.

Fictional fixtures only (CASE-FIG-01 / CASE-FIG-02, independently authored
inline bytes). UNVERIFIED: the reviewer runs the suite; nothing here was
executed by the author.
"""

import json
import unittest

from open_intelligence.store import CaseStore, InvalidInput


def _fig_report(patient, document, findings, event_date="2026-08-01",
                issued_at="2026-08-03", kind="laboratory", specimen=None):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", f"Type: {kind}",
             f"Event-Date: {event_date}", f"Issued-At: {issued_at}"]
    if specimen is not None:
        lines.append(f"Specimen: {specimen}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode()


FIG01_PATH = _fig_report("CASE-FIG-01", "FIG-PATH-01", [
    ("histology", "reported", "Fictional biopsy note records atypical cells."),
    ("margin", "indeterminate", "Fictional margin note cannot be assessed."),
])
FIG01_LAB = _fig_report("CASE-FIG-01", "FIG-LAB-01", [
    ("marker-b", "reported", "Fictional laboratory note records Marker B as present."),
])
FIG02_PATH = _fig_report("CASE-FIG-02", "FIG-PATH-02", [
    ("histology", "reported", "Fictional biopsy note for the second subject."),
])
FIG02_LAB = _fig_report("CASE-FIG-02", "FIG-LAB-02", [
    ("marker-c", "negative", "Fictional laboratory note records Marker C as absent."),
])


def _events_by_kind(state, kind):
    return [event for event in state["events"] if event["kind"] == kind]


class SubjectBindingTests(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-FIG-01", "Fictional figure one")
        self.store.add_case("CASE-FIG-02", "Fictional figure two")

    def tearDown(self):
        self.store.close()

    def test_same_id_sources_assemble_with_recorded_match_decisions(self):
        first = self.store.import_report("CASE-FIG-01", FIG01_PATH)
        second = self.store.import_report("CASE-FIG-01", FIG01_LAB)
        self.assertEqual(first["result"], "imported")
        self.assertEqual(second["result"], "imported")
        links = self.store.list_subject_links("CASE-FIG-01")
        self.assertEqual(len(links), 2)
        self.assertEqual({link["source_version_id"] for link in links},
                         {first["source_id"], second["source_id"]})
        for link in links:
            self.assertEqual(link["declared_subject_id"], "CASE-FIG-01")
            self.assertEqual(link["decision"], "bound_by_declared_id_equality")
            self.assertTrue(link["decided_at"])
            self.assertTrue(link["actor_label"])
        state = self.store.state("CASE-FIG-01")
        self.assertEqual(len(state["sources"]), 2)
        self.assertEqual({item["finding_key"] for item in state["assertions"]},
                         {"histology", "margin", "marker-b"})
        # Same listing is exposed through the case state read.
        self.assertEqual(len(state["subject_links"]), 2)
        # Nothing leaks into the other case.
        self.assertEqual(self.store.list_subject_links("CASE-FIG-02"), [])
        self.assertEqual(self.store.state("CASE-FIG-02")["sources"], [])

    def test_different_id_sources_quarantine_with_collision_record(self):
        first = self.store.import_report("CASE-FIG-01", FIG02_PATH)
        self.assertEqual(first["result"], "quarantined")
        self.assertEqual(first["reason"], "patient_mismatch")
        before = self.store.state("CASE-FIG-01")
        again = self.store.import_report("CASE-FIG-01", FIG02_PATH)
        self.assertEqual(again["quarantine_id"], first["quarantine_id"])
        self.assertTrue(again["duplicate"])
        after = self.store.state("CASE-FIG-01")
        self.assertEqual(len(after["quarantines"]), 1)
        record = after["quarantines"][0]
        self.assertEqual(record["declared_patient_id"], "CASE-FIG-02")
        self.assertEqual(record["reason"], "patient_mismatch")
        self.assertIsNone(record["resolved_destination_case_id"])
        self.assertIsNone(record["resolved_destination_source_id"])
        self.assertEqual(len(after["events"]), len(before["events"]))
        quarantined = _events_by_kind(after, "source_quarantined")
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(json.loads(quarantined[0]["details"])["quarantine_id"],
                         first["quarantine_id"])
        self.assertEqual(after["sources"], [])
        self.assertEqual(after["assertions"], [])
        self.assertEqual(after["subject_links"], [])
        self.assertEqual(self.store.state("CASE-FIG-02")["sources"], [])

    def test_quarantined_bytes_reversible_into_right_case_with_receipt(self):
        delivered = self.store.import_report("CASE-FIG-01", FIG02_PATH)
        quarantine_id = delivered["quarantine_id"]
        result = self.store.correct_quarantined_delivery(
            "CASE-FIG-01", quarantine_id, "CASE-FIG-02",
            actor_label="fig-correction-demo")
        self.assertEqual(result["result"], "corrected")
        self.assertEqual(result["destination_case_id"], "CASE-FIG-02")
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["import_result"], "imported")
        # Original bytes land in the right case through the import path.
        self.assertEqual(
            self.store.source_text("CASE-FIG-02", result["destination_source_id"]).encode(),
            FIG02_PATH)
        destination = self.store.state("CASE-FIG-02")
        self.assertEqual(len(destination["sources"]), 1)
        self.assertEqual(destination["assertions"][0]["finding_key"], "histology")
        links = self.store.list_subject_links("CASE-FIG-02")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["declared_subject_id"], "CASE-FIG-02")
        # The quarantine row survives with its bytes and a disposition pointer.
        source = self.store.state("CASE-FIG-01")
        self.assertEqual(len(source["quarantines"]), 1)
        record = source["quarantines"][0]
        self.assertEqual(record["resolved_destination_case_id"], "CASE-FIG-02")
        self.assertEqual(record["resolved_destination_source_id"],
                         result["destination_source_id"])
        self.assertTrue(record["resolved_at"])
        kept = self.store.db.execute(
            "SELECT raw FROM quarantine WHERE id=?", (quarantine_id,)).fetchone()
        self.assertEqual(bytes(kept["raw"]), FIG02_PATH)
        # Receipts on both cases: out on the source; imported + in on dest.
        out = _events_by_kind(source, "quarantine_resolved_out")
        self.assertEqual(len(out), 1)
        out_details = json.loads(out[0]["details"])
        self.assertEqual(out_details["quarantine_id"], quarantine_id)
        self.assertEqual(out_details["destination_case_id"], "CASE-FIG-02")
        imported = _events_by_kind(destination, "source_imported")
        received = _events_by_kind(destination, "quarantine_resolved_in")
        self.assertEqual(len(imported), 1)
        self.assertEqual(len(received), 1)
        self.assertGreater(received[0]["id"], imported[0]["id"])
        in_details = json.loads(received[0]["details"])
        self.assertEqual(in_details["quarantine_id"], quarantine_id)
        self.assertEqual(in_details["source_case_id"], "CASE-FIG-01")
        # Repeat correction is idempotent: original disposition, nothing new.
        events_before = (len(source["events"]), len(destination["events"]))
        repeat = self.store.correct_quarantined_delivery(
            "CASE-FIG-01", quarantine_id, "CASE-FIG-02")
        self.assertTrue(repeat["duplicate"])
        self.assertEqual(repeat["destination_source_id"],
                         result["destination_source_id"])
        self.assertEqual(len(self.store.state("CASE-FIG-02")["sources"]), 1)
        self.assertEqual(len(self.store.state("CASE-FIG-01")["events"]),
                         events_before[0])
        self.assertEqual(len(self.store.state("CASE-FIG-02")["events"]),
                         events_before[1])

    def test_quarantine_rows_never_deleted_and_no_silent_merge_path(self):
        first = self.store.import_report("CASE-FIG-01", FIG02_PATH)
        second = self.store.import_report("CASE-FIG-01", FIG02_LAB)
        self.assertEqual(
            self.store.db.execute("SELECT COUNT(*) AS n FROM quarantine").fetchone()["n"], 2)
        self.store.correct_quarantined_delivery(
            "CASE-FIG-01", first["quarantine_id"], "CASE-FIG-02")
        # Correction deletes nothing: both quarantine rows remain with bytes.
        rows = self.store.db.execute(
            "SELECT id, raw FROM quarantine ORDER BY id").fetchall()
        self.assertEqual([row["id"] for row in rows],
                         [first["quarantine_id"], second["quarantine_id"]])
        self.assertTrue(all(bytes(row["raw"]) for row in rows))
        # No source version is bound to two cases: per-case link sets are
        # disjoint and every version carries exactly one link.
        links_one = self.store.list_subject_links("CASE-FIG-01")
        links_two = self.store.list_subject_links("CASE-FIG-02")
        bound_one = {link["source_version_id"] for link in links_one}
        bound_two = {link["source_version_id"] for link in links_two}
        self.assertEqual(bound_one & bound_two, set())
        counts = self.store.db.execute(
            "SELECT source_version_id, COUNT(*) AS n FROM subject_links "
            "GROUP BY source_version_id").fetchall()
        self.assertTrue(counts)
        self.assertTrue(all(row["n"] == 1 for row in counts))
        snapshot = (self.store.db.execute("SELECT * FROM subject_links ORDER BY id").fetchall(),
                    self.store.db.execute("SELECT * FROM quarantine_corrections ORDER BY quarantine_id").fetchall())
        # Wrong destination fails closed: no new quarantine, no new version.
        quarantines_before = self.store.db.execute(
            "SELECT COUNT(*) AS n FROM quarantine").fetchone()["n"]
        versions_before = self.store.db.execute(
            "SELECT COUNT(*) AS n FROM source_versions").fetchone()["n"]
        with self.assertRaisesRegex(InvalidInput, "declared subject id"):
            self.store.correct_quarantined_delivery(
                "CASE-FIG-01", second["quarantine_id"], "CASE-FIG-01")
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.correct_quarantined_delivery(
                "CASE-FIG-02", second["quarantine_id"], "CASE-FIG-02")
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.correct_quarantined_delivery(
                "CASE-FIG-01", 9999, "CASE-FIG-02")
        with self.assertRaisesRegex(InvalidInput, "Unknown case"):
            self.store.correct_quarantined_delivery(
                "CASE-FIG-01", second["quarantine_id"], "CASE-NOPE")
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) AS n FROM quarantine").fetchone()["n"], quarantines_before)
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) AS n FROM source_versions").fetchone()["n"], versions_before)
        # Recorded decisions are never rewritten in place by any attempt.
        self.assertEqual(
            [dict(row) for row in self.store.db.execute(
                "SELECT * FROM subject_links ORDER BY id").fetchall()],
            [dict(row) for row in snapshot[0]])
        self.assertEqual(
            [dict(row) for row in self.store.db.execute(
                "SELECT * FROM quarantine_corrections ORDER BY quarantine_id").fetchall()],
            [dict(row) for row in snapshot[1]])


if __name__ == "__main__":
    unittest.main()
