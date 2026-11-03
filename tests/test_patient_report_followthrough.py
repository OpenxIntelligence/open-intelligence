"""Report integration over real, independently authored synthetic task records."""

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore
from open_intelligence.followthrough import followthrough_view
from open_intelligence.patient_report import REPORT_GUARDS, build_patient_report, render_text


SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "synthetic"


class PatientReportFollowthroughTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "report-followthrough.sqlite"
        self.store = CaseStore(self.db_path)
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.original_bytes = (SAMPLE / "alpha-pathology-original.txt").read_bytes()
        self.store.import_report("CASE-ALPHA", self.original_bytes)
        self.source_id = self.store.state("CASE-ALPHA")["sources"][0]["id"]
        self.question_id = self.store.add_question(
            "CASE-ALPHA", "Which source versions belong in the fictional review packet?"
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def create_task(self, title="Prepare the fictional review packet", **overrides):
        fields = {
            "actor_label": "Fictional Author",
            "reason": "Recorded for the upcoming fictional discussion.",
            "detail": "Collect the existing source references in one place.",
            "review_trigger": "When the source packet changes",
            "due_date": "2026-06-02",
            "question_id": self.question_id,
            "source_version_id": self.source_id,
        }
        fields.update(overrides)
        return self.store.create_followthrough_task("CASE-ALPHA", title, **fields)

    def report(self, case_id="CASE-ALPHA", day="2026-06-01"):
        state = self.store.state(case_id)
        # Use the real projection's explicit clock; no flags are manufactured.
        state["followthrough"] = followthrough_view(self.store, case_id, today=day)
        return build_patient_report(state)

    def section(self, payload):
        section = next((row for row in payload["sections"] if row["id"] == "followthrough"), None)
        self.assertIsNotNone(section, "The readable report omits persisted follow-through work")
        return section

    def task_item(self, payload, task_id):
        matches = [item for item in self.section(payload)["items"]
                   if f"Follow-through task #{task_id}." in item["citation"]]
        self.assertEqual(len(matches), 1, "Each task is an attributable report entry")
        return matches[0]

    def transition(self, task_id, status):
        fields = {"actor_label": "Fictional Recorder", "reason": f"Recorded the {status} status for this packet."}
        if status == "assigned":
            fields["owner_label"] = "Fictional Owner"
        return self.store.update_followthrough_task("CASE-ALPHA", task_id, status, **fields)

    def test_missing_projection_is_unavailable_rather_than_no_tasks(self):
        state = self.store.state("CASE-ALPHA")
        state.pop("followthrough")
        payload = build_patient_report(state)
        section = self.section(payload)
        self.assertIn("unavailable", section["summary"].lower())
        self.assertNotIn("no follow-through tasks", section["empty_text"].lower())
        self.assertIsNone(payload["as_of"]["due_evaluated_on"])

    def test_empty_projection_preserves_its_due_evaluation_day(self):
        payload = self.report(day="2026-06-01")
        section = self.section(payload)
        self.assertEqual(section["items"], [])
        self.assertIn("0 open", section["summary"])
        self.assertIn("No follow-through tasks", section["empty_text"])
        self.assertEqual(payload["as_of"]["due_evaluated_on"], "2026-06-01")
        self.assertIn("2026-06-01", section["summary"])
        self.assertIn("Due dates evaluated on 2026-06-01", render_text(payload))

    def test_lifecycle_keeps_all_recorded_actors_reasons_and_completion_boundary(self):
        task_id = self.create_task()
        for status in ("created", "assigned", "acknowledged", "completed"):
            with self.subTest(status=status):
                if status != "created":
                    self.transition(task_id, status)
                payload = self.report()
                item = self.task_item(payload, task_id)
                self.assertIn("Prepare the fictional review packet", item["text"])
                self.assertIn(f"Recorded status: {status}", item["detail"])
                self.assertIn("2026-06-02", item["detail"])
                self.assertIn('Recorded detail: "Collect the existing source references in one place."', item["detail"])
                self.assertIn('Recorded review trigger: "When the source packet changes"', item["detail"])
                self.assertIn(f"Question record #{self.question_id}", item["citation"])
                self.assertIn(f"Source version #{self.source_id}", item["citation"])
                self.assertIn("PATH-ALPHA@1", item["citation"])
                self.assertIn(hashlib.sha256(self.original_bytes).hexdigest(), item["citation"])
                history = followthrough_view(self.store, "CASE-ALPHA")["tasks"][0]["history"]
                for event in history:
                    self.assertIn(f"Task event #{event['id']}", item["detail"])
                    self.assertIn(event["actor_label"], item["detail"])
                    self.assertIn(event["reason"], item["detail"])
                    self.assertIn(event["noted_at"], item["detail"])
                if status != "created":
                    self.assertIn('Current recorded owner: "Fictional Owner"', item["detail"])
                if status == "completed":
                    self.assertIn("Recorded as completed after acknowledgment", item["detail"])
                    self.assertIn("history", item["detail"])
                else:
                    self.assertNotIn("Recorded as completed", item["detail"])
                    self.assertIn("open", item["detail"])

    def test_saved_work_and_history_survive_store_restart(self):
        task_id = self.create_task()
        self.transition(task_id, "assigned")
        self.transition(task_id, "acknowledged")
        before = render_text(self.report())
        self.section(self.report())
        self.store.close()
        self.store = CaseStore(self.db_path)
        self.assertEqual(render_text(self.report()), before)
        self.assertIn("acknowledged", self.task_item(self.report(), task_id)["detail"])

    def test_amendment_flags_open_work_but_preserves_deferred_and_completed_history(self):
        open_id = self.create_task("Open fictional packet work")
        deferred_id = self.create_task("Deferred fictional packet work")
        completed_id = self.create_task("Completed fictional packet work")
        self.transition(deferred_id, "deferred")
        for status in ("assigned", "acknowledged", "completed"):
            self.transition(completed_id, status)
        self.store.import_report("CASE-ALPHA", (SAMPLE / "alpha-pathology-amended.txt").read_bytes())

        payload = self.report(day="2026-06-03")
        open_item = self.task_item(payload, open_id)
        self.assertIn("linked source amended — recheck is open", open_item["detail"])
        self.assertIn("overdue", open_item["detail"])
        for task_id, status in ((deferred_id, "deferred"), (completed_id, "completed")):
            with self.subTest(status=status):
                item = self.task_item(payload, task_id)
                self.assertIn(f"Recorded status: {status}", item["detail"])
                self.assertIn("superseded", item["detail"])
                self.assertIn("remains history", item["detail"])
                self.assertNotIn("recheck is open", item["detail"])
                self.assertNotIn("overdue", item["detail"])
                self.assertIn("PATH-ALPHA@1", item["citation"])
                self.assertNotIn("PATH-ALPHA@2", item["citation"])
                self.assertIn(hashlib.sha256(self.original_bytes).hexdigest(), item["citation"])

    def test_evaluation_day_changes_due_flags_without_a_new_ledger_event(self):
        task_id = self.create_task()
        before_ledger = list(self.store.db.iterdump())
        before = self.report(day="2026-06-01")
        after = self.report(day="2026-06-03")
        self.assertIn("due soon", self.task_item(before, task_id)["detail"])
        self.assertNotIn("overdue", self.task_item(before, task_id)["detail"])
        self.assertIn("overdue", self.task_item(after, task_id)["detail"])
        self.assertEqual(before["as_of"]["event_id"], after["as_of"]["event_id"])
        self.assertEqual(before["as_of"]["occurred_at"], after["as_of"]["occurred_at"])
        self.assertEqual(before["as_of"]["due_evaluated_on"], "2026-06-01")
        self.assertEqual(after["as_of"]["due_evaluated_on"], "2026-06-03")
        self.assertEqual(list(self.store.db.iterdump()), before_ledger)

    def test_other_case_records_and_mismatched_projection_are_not_disclosed(self):
        self.create_task("Alpha-only packet title")
        self.store.create_followthrough_task(
            "CASE-BETA", "Beta-only packet title", actor_label="Beta-only Actor",
            reason="Beta-only history explanation.",
        )
        alpha = self.report()
        beta = self.report("CASE-BETA")
        self.section(alpha)
        self.assertNotIn("Beta-only", render_text(alpha))
        self.assertNotIn("Alpha-only", render_text(beta))
        state = self.store.state("CASE-ALPHA")
        state["followthrough"] = followthrough_view(self.store, "CASE-BETA")
        mismatched = build_patient_report(state)
        self.assertIn("unavailable", self.section(mismatched)["summary"].lower())
        self.assertNotIn("Beta-only", render_text(mismatched))
        self.assertIsNone(mismatched["as_of"]["due_evaluated_on"])

    def test_missing_source_anchor_is_explicit_not_filled_from_another_version(self):
        task_id = self.create_task()
        state = self.store.state("CASE-ALPHA")
        state["sources"] = []
        item = self.task_item(build_patient_report(state), task_id)
        self.assertIn(f"Source version #{self.source_id} unavailable", item["citation"])
        self.assertNotIn("SHA-256", item["citation"])

    def test_recorded_text_is_quoted_without_control_or_newline_header_spoofing(self):
        task_id = self.create_task(
            "Préparer notes\nFORGED HEADER",
            actor_label="Fictional\rActor\u202e",
            reason="Recorded\u2028FORGED REASON",
            detail="Keep\x00FORGED DETAIL",
            review_trigger="Packet changes\u2029FORGED TRIGGER",
        )
        self.store.update_followthrough_task(
            "CASE-ALPHA", task_id, "assigned", actor_label="Recorder\x1b[0m",
            owner_label="Fictional\nOwner", reason="Recorded\nFORGED STATUS",
        )
        state = self.store.state("CASE-ALPHA")
        untouched = copy.deepcopy(state)
        payload = build_patient_report(state)
        item = self.task_item(payload, task_id)
        output = render_text(payload)
        self.assertIn("Préparer notes", output)
        for escaped in ("\\nFORGED HEADER", "\\rActor\\u202e", "\\u2028FORGED REASON",
                        "\\u0000FORGED DETAIL", "\\u2029FORGED TRIGGER", "\\u001b[0m",
                        "Fictional\\nOwner", "\\nFORGED STATUS"):
            self.assertIn(escaped, output)
        for control in ("\r", "\u202e", "\u2028", "\u2029", "\x00", "\x1b"):
            self.assertNotIn(control, output)
        self.assertNotIn("\nFORGED", output)
        self.assertEqual(state, untouched)
        self.assertIn('"Préparer notes\\nFORGED HEADER"', item["text"])

    def test_recorded_case_label_cannot_disrupt_report_or_its_voice_guard(self):
        # add_case permits Unicode, newlines and clinical words in a label.
        # The case's stored label must remain unchanged, but its report
        # presentation must neither forge a new line nor block report output.
        label = "Fictional therapy\nFORGED REVIEW APPROVAL\u202e"
        self.store.add_case("CASE-GAMMA", label)
        state = self.store.state("CASE-GAMMA")
        report = build_patient_report(state)
        exported = render_text(report)
        safe = r"Fictional therapy\nFORGED REVIEW APPROVAL\u202e"
        self.assertEqual(report["case_label"], safe)
        self.assertIn(safe, exported)
        self.assertNotIn("\nFORGED REVIEW APPROVAL", exported)
        self.assertNotIn("\u202e", exported)
        self.assertEqual(self.store.state("CASE-GAMMA")["case"]["label"], label)

    def test_recorded_findings_questions_options_and_source_ids_render_literally(self):
        # Exercise the projection boundary independently of parser-specific
        # restrictions. The report never mutates its original case snapshot.
        state = self.store.state("CASE-ALPHA")
        state["assertions"][0]["quote"] = "Marker not measured\nFORGED CLINICIAN SIGNOFF\u202e"
        state["assertions"][0]["finding_key"] = "finding\rINJECTED KEY"
        state["sources"][0]["document_id"] = "PATH-ALPHA\nINJECTED DOCUMENT"
        state["sources"][0]["specimen_id"] = "SPEC\u2028INJECTED SPECIMEN"
        state["questions"][0]["question"] = "What is known?\nINJECTED QUESTION"
        state["options"] = [{
            "id": 9876, "label": "Option\u202eINJECTED LABEL",
            "description": "See a source\nINJECTED OPTION",
        }]
        untouched = copy.deepcopy(state)
        report = build_patient_report(state)
        exported = render_text(report)
        for escaped in (
            r"Marker not measured\nFORGED CLINICIAN SIGNOFF\u202e",
            r"finding\rINJECTED KEY",
            r"PATH-ALPHA\nINJECTED DOCUMENT",
            r"SPEC\u2028INJECTED SPECIMEN",
            r"What is known?\nINJECTED QUESTION",
            r"Option\u202eINJECTED LABEL",
            r"See a source\nINJECTED OPTION",
        ):
            self.assertIn(escaped, exported)
        for control in ("\r", "\u202e", "\u2028"):
            self.assertNotIn(control, exported)
        for spoofed_heading in (
            "\nFORGED CLINICIAN SIGNOFF", "\nINJECTED DOCUMENT",
            "\nINJECTED QUESTION", "\nINJECTED OPTION",
        ):
            self.assertNotIn(spoofed_heading, exported)
        self.assertEqual(state, untouched)

    def test_new_report_framing_preserves_existing_language_guard(self):
        task_id = self.create_task()
        self.transition(task_id, "deferred")
        payload = self.report()
        section = self.section(payload)
        # Clean synthetic values allow scanning both fixed framing and filled details.
        for pattern in REPORT_GUARDS:
            self.assertIsNone(pattern.search(repr(section)), pattern.pattern)
        for text in (section["summary"], section["empty_text"]):
            for sentence in text.split("."):
                self.assertLessEqual(len(sentence.split()), 30)


if __name__ == "__main__":
    unittest.main()
