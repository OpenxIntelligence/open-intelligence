"""Tests for owned scientific questions (B-06, closes G-06), owned-questions part only.

Fictional cases CASE-FIG-01 / CASE-FIG-02 with freshly authored fictional
report bytes imported through import_report. Owner labels are fictional
attribution, never authorization. No live model call, no API key, no
operator-key path is exercised anywhere in this file.
"""

import json
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.mission import UNRESOLVED_SOURCE_STATES
from open_intelligence.owned_questions import question_gap_rollup


def report_bytes(patient, document, findings, event_date="2026-01-10",
                 issued_at="2026-01-12", kind="pathology", amends=None):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", f"Type: {kind}",
             f"Event-Date: {event_date}", f"Issued-At: {issued_at}"]
    if amends is not None:
        lines.append(f"Amends: {amends}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode("utf-8")


MIXED_FINDINGS = (
    ("histology", "reported", "The sample shows recorded tissue features."),
    ("marker-a", "pending", "Marker A testing is pending at the fictional laboratory."),
    ("margin", "indeterminate", "Margin status is indeterminate on this fictional section."),
    ("node-count", "conflicting", "Node counts conflict between fictional worksheets."),
    ("marker-b", "not-reported", "Marker B was not reported in this fictional document."),
    ("stain", "negative", "The fictional stain shows no recorded uptake."),
)


class OwnedQuestionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "test.sqlite")
        self.store.add_case("CASE-FIG-01", "Fictional fig one")
        self.store.add_case("CASE-FIG-02", "Fictional fig two")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _import_mixed(self, case_id="CASE-FIG-01"):
        raw = report_bytes(case_id, "DOC-FIG-A", MIXED_FINDINGS)
        result = self.store.import_report(case_id, raw)
        return raw, result["source_id"]

    def test_question_carries_owner_label_and_status(self):
        plain = self.store.add_question("CASE-FIG-01", "What did the fictional report record?")
        owned = self.store.add_question(
            "CASE-FIG-01", "Which fictional finding needs follow-up?", "FICTIONAL-NAVIGATOR-A")
        by_id = {q["id"]: q for q in self.store.state("CASE-FIG-01")["questions"]}
        self.assertEqual(by_id[plain]["state"], "open")
        self.assertIsNone(by_id[plain]["owner_label"])
        self.assertEqual(by_id[plain]["triage"], "unsorted")
        self.assertEqual(by_id[owned]["state"], "open")
        self.assertEqual(by_id[owned]["owner_label"], "FICTIONAL-NAVIGATOR-A")
        self.assertEqual(by_id[owned]["triage"], "owned")
        for bad in ("x", "x" * 81, "  ", 42, ["FICTIONAL-NAVIGATOR-A"]):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidInput):
                    self.store.add_question("CASE-FIG-01", "Another fictional question here?", bad)
        for triage in ("owned", "awaiting_evidence", "ready_for_review", "unsorted"):
            self.store.set_question_triage("CASE-FIG-01", plain, triage)
            row = {q["id"]: q for q in self.store.state("CASE-FIG-01")["questions"]}[plain]
            self.assertEqual(row["triage"], triage)
            self.assertEqual(row["state"], "open")
        for bad_triage in ("urgent", "", None, ["owned"], 42):
            with self.subTest(bad_triage=bad_triage):
                with self.assertRaises(InvalidInput):
                    self.store.set_question_triage("CASE-FIG-01", plain, bad_triage)
        with self.assertRaises(InvalidInput):
            self.store.set_question_triage("CASE-FIG-01", 9999, "owned")

    def test_owner_assign_action_appends_history_and_rewrites_nothing(self):
        qid = self.store.add_question("CASE-FIG-01", "Which fictional finding needs follow-up?")
        before = {q["id"]: q for q in self.store.state("CASE-FIG-01")["questions"]}[qid]
        self.store.assign_question_owner("CASE-FIG-01", qid, "FICTIONAL-NAVIGATOR-A")
        self.store.assign_question_owner("CASE-FIG-01", qid, "FICTIONAL-REVIEWER-B")
        history = self.store.list_question_owner_history("CASE-FIG-01", qid)
        self.assertEqual([h["owner_label"] for h in history],
                         ["FICTIONAL-NAVIGATOR-A", "FICTIONAL-REVIEWER-B"])
        self.assertLess(history[0]["id"], history[1]["id"])
        after = {q["id"]: q for q in self.store.state("CASE-FIG-01")["questions"]}[qid]
        self.assertEqual(after["owner_label"], "FICTIONAL-REVIEWER-B")
        self.assertEqual(after["question"], before["question"])
        self.assertEqual(after["created_at"], before["created_at"])
        self.assertEqual(len(self.store.state("CASE-FIG-01")["questions"]), 1)
        self.assertEqual(len(self.store.list_question_owner_history("CASE-FIG-01", qid)), 2)
        with self.assertRaises(InvalidInput):
            self.store.assign_question_owner("CASE-FIG-01", qid, "z")
        with self.assertRaises(InvalidInput):
            self.store.assign_question_owner("CASE-FIG-02", qid, "FICTIONAL-NAVIGATOR-A")
        with self.assertRaises(InvalidInput):
            self.store.assign_question_owner("CASE-FIG-01", 9999, "FICTIONAL-NAVIGATOR-A")
        # Re-assignment never re-sorts an explicitly triaged question.
        self.store.set_question_triage("CASE-FIG-01", qid, "awaiting_evidence")
        self.store.assign_question_owner("CASE-FIG-01", qid, "FICTIONAL-NAVIGATOR-A")
        row = {q["id"]: q for q in self.store.state("CASE-FIG-01")["questions"]}[qid]
        self.assertEqual(row["triage"], "awaiting_evidence")
        self.assertEqual(len(self.store.list_question_owner_history("CASE-FIG-01", qid)), 3)

    def test_existing_open_addressed_transitions_preserved(self):
        raw, source_id = self._import_mixed()
        qid = self.store.add_question(
            "CASE-FIG-01", "What did the fictional report record?", "FICTIONAL-NAVIGATOR-A")
        self.store.set_question_triage("CASE-FIG-01", qid, "ready_for_review")
        snapshot_id = self.store.create_snapshot(
            "CASE-FIG-01", qid, "Human-authored fictional draft of reported findings.",
            [source_id])
        self.store.acknowledge_demo_review("CASE-FIG-01", snapshot_id, "FICTIONAL-REVIEWER-B")
        addressed = {q["id"]: q for q in self.store.state("CASE-FIG-01")["questions"]}[qid]
        self.assertEqual(addressed["state"], "addressed")
        self.assertEqual(addressed["owner_label"], "FICTIONAL-NAVIGATOR-A")
        self.assertEqual(addressed["triage"], "ready_for_review")
        amended = report_bytes(
            "CASE-FIG-01", "DOC-FIG-A",
            (("histology", "reported", "The sample shows re-recorded tissue features."),
             ("marker-a", "pending", "Marker A testing is pending at the fictional laboratory."),
             ("margin", "indeterminate", "Margin status is indeterminate on this fictional section."),
             ("node-count", "conflicting", "Node counts conflict between fictional worksheets."),
             ("marker-b", "not-reported", "Marker B was not reported in this fictional document."),
             ("stain", "negative", "The fictional stain shows no recorded uptake.")),
            amends="DOC-FIG-A@1")
        self.assertNotEqual(amended, raw)
        result = self.store.import_report("CASE-FIG-01", amended)
        self.assertEqual(result["result"], "imported")
        reopened = {q["id"]: q for q in self.store.state("CASE-FIG-01")["questions"]}[qid]
        self.assertEqual(reopened["state"], "open")
        self.assertEqual(reopened["owner_label"], "FICTIONAL-NAVIGATOR-A")
        self.assertEqual(reopened["triage"], "ready_for_review")
        snapshots = {s["id"]: s for s in self.store.state("CASE-FIG-01")["snapshots"]}
        self.assertEqual(snapshots[snapshot_id]["state"], "stale")

    def test_gap_rollup_matches_underlying_states_with_anchors(self):
        raw, source_id = self._import_mixed()
        qid = self.store.add_question(
            "CASE-FIG-01", "What remains unresolved in the fictional report?",
            "FICTIONAL-NAVIGATOR-A")
        self.store.create_snapshot(
            "CASE-FIG-01", qid, "Human-authored fictional draft of reported findings.",
            [source_id])
        self.store.add_question_evidence_note(
            "CASE-FIG-01", qid, "The fictional laboratory slip for marker A is still needed.")
        rollup = question_gap_rollup(self.store, "CASE-FIG-01", qid)
        self.assertEqual(rollup["question"]["id"], qid)
        self.assertEqual(rollup["question"]["owner_label"], "FICTIONAL-NAVIGATOR-A")
        expected = {key for key, state, _ in MIXED_FINDINGS if state in UNRESOLVED_SOURCE_STATES}
        got = {item["finding_key"] for item in rollup["unresolved_items"]}
        self.assertEqual(got, expected)
        self.assertNotIn("histology", got)
        self.assertNotIn("stain", got)
        lines = raw.decode("utf-8").splitlines()
        for item in rollup["unresolved_items"]:
            self.assertEqual(item["source_version_id"], source_id)
            self.assertIn(item["quote"], lines[item["source_line"] - 1])
            self.assertIn(item["state"], UNRESOLVED_SOURCE_STATES)
        self.assertEqual(sum(rollup["counts_by_state"].values()), len(expected))
        self.assertEqual(len(rollup["snapshots"]), 1)
        self.assertEqual(rollup["snapshots"][0]["source_ids"], [source_id])
        self.assertEqual(len(rollup["needed_evidence_notes"]), 1)
        self.assertEqual(len(rollup["owner_history"]), 1)
        self.assertIn("ordering_rule", rollup)
        with self.assertRaises(InvalidInput):
            question_gap_rollup(self.store, "CASE-FIG-02", qid)
        with self.assertRaises(InvalidInput):
            question_gap_rollup(self.store, "CASE-FIG-01", 9999)

    def test_rollup_is_projection_pure_and_deterministic(self):
        _, source_id = self._import_mixed()
        qid = self.store.add_question(
            "CASE-FIG-01", "What remains unresolved in the fictional report?",
            "FICTIONAL-NAVIGATOR-A")
        self.store.create_snapshot(
            "CASE-FIG-01", qid, "Human-authored fictional draft of reported findings.",
            [source_id])
        self.store.add_question_evidence_note(
            "CASE-FIG-01", qid, "The fictional laboratory slip for marker A is still needed.")
        events_before = len(self.store.state("CASE-FIG-01")["events"])
        questions_before = len(self.store.state("CASE-FIG-01")["questions"])
        history_before = len(self.store.list_question_owner_history("CASE-FIG-01", qid))
        notes_before = len(self.store.list_question_evidence_notes("CASE-FIG-01", qid))
        first = question_gap_rollup(self.store, "CASE-FIG-01", qid)
        second = question_gap_rollup(self.store, "CASE-FIG-01", qid)
        self.assertEqual(first, second)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(len(self.store.state("CASE-FIG-01")["events"]), events_before)
        self.assertEqual(len(self.store.state("CASE-FIG-01")["questions"]), questions_before)
        self.assertEqual(len(self.store.list_question_owner_history("CASE-FIG-01", qid)),
                         history_before)
        self.assertEqual(len(self.store.list_question_evidence_notes("CASE-FIG-01", qid)),
                         notes_before)

    def test_needed_evidence_notes_versioned_append_only(self):
        self._import_mixed()
        qid = self.store.add_question("CASE-FIG-01", "What remains unresolved in the fictional report?")
        first = "The fictional laboratory slip for marker A is still needed."
        second = "A second fictional worksheet would settle the node-count conflict."
        self.store.add_question_evidence_note("CASE-FIG-01", qid, first)
        self.store.add_question_evidence_note("CASE-FIG-01", qid, second)
        notes = self.store.list_question_evidence_notes("CASE-FIG-01", qid)
        self.assertEqual([(n["version"], n["note"]) for n in notes], [(1, first), (2, second)])
        self.assertLess(notes[0]["id"], notes[1]["id"])
        state_notes = [n for n in self.store.state("CASE-FIG-01")["question_evidence_notes"]
                       if n["question_id"] == qid]
        self.assertEqual(len(state_notes), 2)
        with self.assertRaises(InvalidInput):
            self.store.add_question_evidence_note("CASE-FIG-01", qid, "too short")
        with self.assertRaises(InvalidInput):
            self.store.add_question_evidence_note("CASE-FIG-01", qid, "x" * 801)
        with self.assertRaises(InvalidInput):
            self.store.add_question_evidence_note("CASE-FIG-02", qid, first)
        with self.assertRaises(InvalidInput):
            self.store.add_question_evidence_note("CASE-FIG-01", 9999, first)
        reread = self.store.list_question_evidence_notes("CASE-FIG-01", qid)
        self.assertEqual([(n["version"], n["note"]) for n in reread], [(1, first), (2, second)])

    def test_no_autoprioritization_label_in_rollup(self):
        self._import_mixed()
        first_q = self.store.add_question(
            "CASE-FIG-01", "What remains unresolved in the fictional report?",
            "FICTIONAL-NAVIGATOR-A")
        second_q = self.store.add_question(
            "CASE-FIG-01", "Which fictional worksheet holds the node count?")
        for qid in (first_q, second_q):
            text = json.dumps(question_gap_rollup(self.store, "CASE-FIG-01", qid)).lower()
            self.assertNotIn("most important", text)
            self.assertNotIn("highest priority", text)
            self.assertNotIn("top priority", text)
        rollup = question_gap_rollup(self.store, "CASE-FIG-01", first_q)
        self.assertTrue(rollup["ordering_rule"])
        keys = [(item["source_version_id"], item["source_line"])
                for item in rollup["unresolved_items"]]
        self.assertEqual(keys, sorted(keys))

    def test_question_ownership_rollup_notes_case_isolated(self):
        self._import_mixed("CASE-FIG-01")
        other_raw, other_source = self._import_mixed("CASE-FIG-02")
        q1 = self.store.add_question(
            "CASE-FIG-01", "What remains unresolved in the fictional report?",
            "FICTIONAL-NAVIGATOR-A")
        self.store.add_question_evidence_note(
            "CASE-FIG-01", q1, "The fictional laboratory slip for marker A is still needed.")
        q2 = self.store.add_question("CASE-FIG-02", "What does the other fictional case record?")
        state_two = self.store.state("CASE-FIG-02")
        owners_two = [q["owner_label"] for q in state_two["questions"]]
        self.assertNotIn("FICTIONAL-NAVIGATOR-A", owners_two)
        self.assertEqual(state_two["question_owner_history"], [])
        self.assertEqual(state_two["question_evidence_notes"], [])
        rollup_two = question_gap_rollup(self.store, "CASE-FIG-02", q2)
        self.assertEqual(rollup_two["owner_history"], [])
        self.assertEqual(rollup_two["needed_evidence_notes"], [])
        for item in rollup_two["unresolved_items"]:
            self.assertEqual(item["source_version_id"], other_source)
            self.assertIn(item["quote"], other_raw.decode("utf-8"))
        state_one = self.store.state("CASE-FIG-01")
        self.assertEqual(len(state_one["question_owner_history"]), 1)
        self.assertEqual(len(state_one["question_evidence_notes"]), 1)


if __name__ == "__main__":
    unittest.main()
