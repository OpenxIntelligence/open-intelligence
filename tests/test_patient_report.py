import re
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore
from open_intelligence.patient_report import (
    DETAIL_FINDING,
    NO_SOURCE_NOTE,
    OPTION_DETAIL,
    QUESTION_DETAIL,
    REPORT_GUARDS,
    TIMELINE_ENTRY_DETAIL,
    TIMELINE_ENTRY_TEXT,
    TIMELINE_HISTORY_DETAIL,
    TIMELINE_HISTORY_TEXT,
    build_patient_report,
    render_text,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


def framing_text(payload: dict) -> str:
    """The report's own voice: banners, notes, titles, summaries, empties."""
    parts = [
        payload["demo_notice"],
        payload["reading_note"],
        payload["generated_from"],
    ]
    for section in payload["sections"]:
        parts.extend([
            section["title"],
            section["fictional_note"],
            section["summary"],
            section["empty_text"],
            section["sources_note"],
        ])
    return "\n".join(parts)


class PatientReportProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "patient-report.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def payload(self, case_id: str) -> dict:
        return build_patient_report(self.store.state(case_id))

    def by_id(self, payload: dict) -> dict:
        return {section["id"]: section for section in payload["sections"]}

    def test_empty_case_reports_absence_without_inference(self):
        payload = self.payload("CASE-ALPHA")

        self.assertTrue(payload["fictional"])
        self.assertIn("Fictional", payload["demo_notice"])
        self.assertIn("no new inference", payload["generated_from"])
        self.assertEqual(
            payload["section_ids"],
            ["overview", "timeline", "questions", "options", "followthrough", "goals"],
        )
        for section in payload["sections"]:
            self.assertEqual(section["items"], [])
            self.assertTrue(section["empty_text"])
            self.assertIn("Fictional", section["fictional_note"])
            self.assertIn("no entries", section["sources_note"])
        sections = self.by_id(payload)
        self.assertIn("Unknown", sections["goals"]["empty_text"])
        self.assertIn("No goals are recorded", sections["goals"]["summary"])
        # as_of points at the case-creation event: creating the case is
        # itself a recorded event, so a fresh case has one, not none.
        creation = self.store.state("CASE-ALPHA")["events"][0]
        self.assertEqual(payload["as_of"]["event_id"], creation["id"])

    def test_seeded_case_sections_cite_recorded_sources_only(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        state = self.store.state("CASE-ALPHA")

        payload = build_patient_report(state)
        sections = self.by_id(payload)
        source_ids = {row["id"] for row in state["sources"]}

        self.assertEqual(len(sections["overview"]["items"]), 5)
        self.assertEqual(
            sections["overview"]["cited_count"], sections["overview"]["item_count"]
        )
        for item in sections["overview"]["items"]:
            match = re.search(r"Source version #(\d+)", item["citation"])
            self.assertIsNotNone(match, item)
            self.assertIn(int(match.group(1)), source_ids)
            self.assertNotEqual(item["citation"], NO_SOURCE_NOTE)
        timeline_docs = [item["citation"] for item in sections["timeline"]["items"]]
        self.assertEqual(len(timeline_docs), 2)
        for citation in timeline_docs:
            match = re.search(r"Source version #(\d+)", citation)
            self.assertIn(int(match.group(1)), source_ids)
        # Nothing recorded yet for questions, options, or goals: said plainly.
        self.assertEqual(sections["questions"]["items"], [])
        self.assertEqual(sections["options"]["items"], [])
        self.assertEqual(sections["goals"]["items"], [])
        self.assertIsNotNone(payload["as_of"]["event_id"])
        # Pre-amendment states are repeated exactly, including not-reported.
        plain_by_key = {
            item["detail"].split(";")[0]: item["detail"]
            for item in sections["overview"]["items"]
        }
        self.assertIn("not reported", plain_by_key["Finding marker-a"])
        self.assertIn("not certain yet", plain_by_key["Finding margin"])
        self.assertIn("pending", plain_by_key["Finding comparison"])

    def test_pending_and_unknown_states_stay_visible_never_settled(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        question_id = self.store.add_question(
            "CASE-ALPHA", "Which recorded findings are still awaiting clarification?"
        )
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id,
            "Human-authored draft noting the recorded pending items.",
            [row["id"] for row in self.store.state("CASE-ALPHA")["sources"]
             if row["document_id"] == "PATH-ALPHA" and row["state"] == "current"],
        )
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))

        payload = self.payload("CASE-ALPHA")
        sections = self.by_id(payload)
        details = {
            item["detail"].split(";")[0]: item["detail"]
            for item in sections["overview"]["items"]
        }

        self.assertIn("pending", details["Finding comparison"])
        self.assertIn("not certain yet", details["Finding margin"])
        # The amendment re-records marker-a as negative; the report repeats
        # the amended state exactly instead of the superseded one.
        self.assertIn("reported as not found", details["Finding marker-a"])
        for detail in details.values():
            self.assertNotIn("settled", detail)
        self.assertIn("Open (pending)", sections["questions"]["items"][0]["detail"])
        self.assertIn(
            "waiting for another look (pending)", sections["overview"]["summary"]
        )
        self.assertIn("1 earlier draft", sections["overview"]["summary"])
        self.assertIn("stale (waiting for another look)", sections["questions"]["summary"])
        self.assertGreaterEqual(len(sections["timeline"]["items"]), 3)
        self.assertIn("Question record #", sections["questions"]["items"][0]["citation"])

    def test_report_voice_carries_no_clinical_or_directive_language(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        self.store.add_question("CASE-ALPHA", "What does the Alpha pathology source report?")

        payload = self.payload("CASE-ALPHA")

        voice = framing_text(payload)
        for pattern in REPORT_GUARDS:
            self.assertIsNone(pattern.search(voice), pattern.pattern)
        # Seeded recorded data is clean too: the whole output scans clean.
        whole = repr(payload)
        for pattern in REPORT_GUARDS:
            self.assertIsNone(pattern.search(whole), pattern.pattern)

    def test_recorded_entries_are_quoted_not_rewritten(self):
        # Hostile recorded text stays verbatim and attributed; the report's
        # own voice still passes the guard.
        question = "Should we start the new tablets tomorrow, in your opinion?"
        self.store.add_question("CASE-ALPHA", question)

        payload = self.payload("CASE-ALPHA")
        sections = self.by_id(payload)

        self.assertEqual(sections["questions"]["items"][0]["text"], question)
        self.assertIn("Question record #", sections["questions"]["items"][0]["citation"])
        voice = framing_text(payload)
        for pattern in REPORT_GUARDS:
            self.assertIsNone(pattern.search(voice), pattern.pattern)

    def test_options_appear_with_plain_standing_and_discussion_only(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        question_id = self.store.add_question(
            "CASE-ALPHA", "Which recorded items merit a discussion entry?"
        )
        source_id = next(
            row["id"] for row in self.store.state("CASE-ALPHA")["sources"]
            if row["state"] == "current"
        )
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id,
            "Human-authored draft supporting one discussion entry.",
            [source_id],
        )
        option_id = self.store.create_option(
            "CASE-ALPHA", snapshot_id, "Fictional discussion item",
            "A fictional item under discussion with its uncertainty noted.",
            "unknown",
        )

        sections = self.by_id(self.payload("CASE-ALPHA"))
        options = sections["options"]

        self.assertEqual(len(options["items"]), 1)
        item = options["items"][0]
        self.assertIn("Fictional discussion item", item["text"])
        self.assertIn("Recorded standing: unknown", item["detail"])
        self.assertIn("proposed (under discussion)", item["detail"])
        self.assertIn(f"snapshot #{snapshot_id}", item["detail"])
        self.assertIn("Listed for discussion only.", item["detail"])
        self.assertEqual(item["citation"], f"Option record #{option_id}.")

    def test_render_text_is_printable_bannered_and_source_cited(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))

        text = render_text(self.payload("CASE-ALPHA"))

        self.assertTrue(text.startswith("OPEN INTELLIGENCE — PLAIN-LANGUAGE CASE REPORT\n"))
        self.assertEqual(text.count("Fictional demo report."), 8)
        for title in ("OVERVIEW", "TIMELINE HIGHLIGHTS", "OPEN QUESTIONS",
                      "OPTION PORTFOLIO", "FOLLOW-THROUGH", "GOALS"):
            self.assertIn(title, text)
        self.assertIn("Source: Source version #", text)
        self.assertIn("Unknown — not stated in the record.", text)
        self.assertTrue(text.endswith("End of report.\n"))
        for pattern in REPORT_GUARDS:
            self.assertIsNone(pattern.search(text), pattern.pattern)

    def test_detail_skeletons_carry_no_clinical_or_directive_language(self):
        skeletons = [
            DETAIL_FINDING.format(finding_key="X", plain="X", certainty="X"),
            TIMELINE_ENTRY_TEXT.format(
                event_date="X", kind="X", document_id="X", version="X",
                issued_at="X"),
            TIMELINE_ENTRY_DETAIL.format(specimen="X", received_at="X"),
            TIMELINE_HISTORY_TEXT.format(
                document_id="X", version="X", event_date="X"),
            TIMELINE_HISTORY_DETAIL,
            QUESTION_DETAIL.format(created_at="X"),
            OPTION_DETAIL.format(
                epistemic="X", operational="X", snapshot_id="X",
                snapshot_state="X", counts="X"),
        ]
        for skeleton in skeletons:
            for pattern in REPORT_GUARDS:
                self.assertIsNone(pattern.search(skeleton), pattern.pattern)

    def test_framing_sentences_stay_short_plain_and_fictional(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        self.store.add_question("CASE-ALPHA", "What does the Alpha pathology source report?")

        voice = framing_text(self.payload("CASE-ALPHA"))

        sentences = [part.strip() for part in voice.replace("!", ".").split(".")]
        sentences = [part for part in sentences if part]
        self.assertGreater(len(sentences), 10)
        for sentence in sentences:
            self.assertLessEqual(
                len(sentence.split()), 30,
                f"Overlong framing sentence: {sentence}",
            )

    def test_projection_never_leaks_another_case(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        self.store.add_question("CASE-ALPHA", "What does the Alpha pathology source report?")

        rendered = repr(self.payload("CASE-BETA"))

        self.assertNotIn("Marker A was not tested in this specimen.", rendered)
        self.assertNotIn("What does the Alpha pathology source report?", rendered)
        self.assertIn("CASE-BETA", rendered)


if __name__ == "__main__":
    unittest.main()
