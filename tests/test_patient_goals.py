"""Patient goals + lived experience: fictional patient words, never clinical claims.

All cases and words are independently authored and fictional. Nothing here
asserts a diagnosis, staging, response, eligibility, or recommendation.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import Handler, seed
from open_intelligence.mission import build_patient_mission

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


def report(name):
    return (SAMPLE / name).read_bytes()


class PatientGoalStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "goals.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _goal(self, statement="Fictional goal: keep walking each morning"):
        return self.store.add_patient_goal(
            "CASE-ALPHA", statement, "2026-06-01",
            "Revisit at the next planned visit", "2026-07-01")

    def test_goal_can_be_set_with_dates_and_review_trigger(self):
        created = self._goal()
        goals = self.store.patient_goals("CASE-ALPHA")
        self.assertEqual(len(goals), 1)
        goal = goals[0]
        self.assertEqual(goal["goal_id"], created["goal_id"])
        self.assertEqual(goal["provenance"], "fictional-patient-words")
        self.assertTrue(goal["patient_reported"])
        self.assertIsNone(goal["clinical_interpretation"])
        current = goal["current"]
        self.assertEqual(current["version"], 1)
        self.assertEqual(current["statement"], "Fictional goal: keep walking each morning")
        self.assertEqual(current["stated_date"], "2026-06-01")
        self.assertEqual(current["review_trigger"], "Revisit at the next planned visit")
        self.assertEqual(current["review_date"], "2026-07-01")
        self.assertEqual(current["status"], "active")
        self.assertEqual(current["record_state"], "current")
        self.assertIsNone(current["previous_id"])

    def test_goal_amendment_preserves_old_version(self):
        created = self._goal()
        amended = self.store.amend_patient_goal(
            "CASE-ALPHA", created["goal_id"],
            "Fictional goal: keep walking each morning with a friend",
            "2026-06-01", "Revisit at the next planned visit", "2026-08-01")
        self.assertEqual(amended["version"], 2)
        goals = self.store.patient_goals("CASE-ALPHA")
        self.assertEqual(len(goals), 1)
        versions = goals[0]["versions"]
        self.assertEqual([v["version"] for v in versions], [1, 2])
        self.assertEqual(versions[0]["record_state"], "superseded")
        self.assertEqual(versions[0]["statement"],
                         "Fictional goal: keep walking each morning")
        self.assertEqual(versions[1]["record_state"], "current")
        self.assertEqual(versions[1]["statement"],
                         "Fictional goal: keep walking each morning with a friend")
        self.assertEqual(versions[1]["previous_id"], versions[0]["id"])
        self.assertEqual(versions[1]["status"], "active")
        self.assertEqual(goals[0]["current"]["id"], versions[1]["id"])

    def test_goal_status_changes_require_reason_and_preserve_history(self):
        ids = [self._goal(f"Fictional goal number {n} for status").get("goal_id")
               for n in range(3)]
        outcomes = [
            self.store.set_patient_goal_status(
                "CASE-ALPHA", ids[0], "achieved",
                "Fictional reason: the patient said mornings feel manageable."),
            self.store.set_patient_goal_status(
                "CASE-ALPHA", ids[1], "changed",
                "Fictional reason: the patient prefers evenings now."),
            self.store.set_patient_goal_status(
                "CASE-ALPHA", ids[2], "abandoned",
                "Fictional reason: the patient set this goal aside for now."),
        ]
        self.assertEqual([o["status"] for o in outcomes],
                         ["achieved", "changed", "abandoned"])
        goals = {g["goal_id"]: g for g in self.store.patient_goals("CASE-ALPHA")}
        for goal_id, status in zip(ids, ["achieved", "changed", "abandoned"]):
            goal = goals[goal_id]
            self.assertEqual(goal["current"]["status"], status)
            self.assertTrue(goal["current"]["status_reason"].startswith("Fictional reason"))
            self.assertEqual(len(goal["versions"]), 2)
            self.assertEqual(goal["versions"][0]["status"], "active")
            self.assertEqual(goal["versions"][0]["record_state"], "superseded")
        with self.assertRaisesRegex(InvalidInput, "already marked"):
            self.store.set_patient_goal_status(
                "CASE-ALPHA", ids[0], "achieved", "Fictional reason: repeated.")
        with self.assertRaisesRegex(InvalidInput, "Goal status must be"):
            self.store.set_patient_goal_status(
                "CASE-ALPHA", ids[0], "remission", "Fictional reason: not a status.")
        with self.assertRaisesRegex(InvalidInput, "Status reason"):
            self.store.set_patient_goal_status("CASE-ALPHA", ids[0], "changed", "bad")

    def test_identical_amendment_and_cross_case_access_refused(self):
        created = self._goal()
        with self.assertRaisesRegex(InvalidInput, "must change"):
            self.store.amend_patient_goal(
                "CASE-ALPHA", created["goal_id"],
                "Fictional goal: keep walking each morning",
                "2026-06-01", "Revisit at the next planned visit", "2026-07-01")
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.amend_patient_goal(
                "CASE-BETA", created["goal_id"], "Fictional other wording here",
                "2026-06-02", "Revisit later")
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.set_patient_goal_status(
                "CASE-BETA", created["goal_id"], "achieved",
                "Fictional reason: wrong case.")
        self.assertEqual(self.store.patient_goals("CASE-BETA"), [])
        self.assertEqual(self.store.patient_notes("CASE-BETA"), [])

    def test_symptom_notes_stay_patient_reported_and_never_clinical(self):
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        before = self.store.state("CASE-ALPHA")
        assertion_count = len(before["assertions"])
        mission_before = build_patient_mission(before)
        note = self.store.add_patient_note(
            "CASE-ALPHA", "symptom",
            "Fictional note: I felt tired after my morning walk.",
            "2026-06-03")
        self.assertEqual(note["version"], 1)
        after = self.store.state("CASE-ALPHA")
        self.assertEqual(len(after["assertions"]), assertion_count)
        mission_after = build_patient_mission(after)
        self.assertEqual(mission_after["what_we_know"], mission_before["what_we_know"])
        rendered = json.dumps(mission_after)
        self.assertNotIn("tired after my morning walk", rendered)
        self.assertNotIn("tired after my morning walk",
                         json.dumps(after["assertions"]))
        notes = after["patient_notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["kind"], "symptom")
        self.assertTrue(notes[0]["patient_reported"])
        self.assertIsNone(notes[0]["clinical_interpretation"])
        self.assertEqual(notes[0]["current"]["note_text"],
                         "Fictional note: I felt tired after my morning walk.")
        for forbidden in ("diagnosis", "staging", "response", "eligible",
                          "recommendation"):
            self.assertNotIn(forbidden, set(notes[0].keys()))
            self.assertNotIn(forbidden, set(notes[0]["current"].keys()))
        blob = json.dumps(notes[0]).lower()
        self.assertNotIn("diagnos", blob)
        self.assertNotIn("staging", blob)

    def test_notes_are_amendable_with_history_and_case_scoped(self):
        lived = self.store.add_patient_note(
            "CASE-ALPHA", "lived_experience",
            "Fictional note: I enjoy reading in the garden.",
            "2026-06-02")
        symptom = self.store.add_patient_note(
            "CASE-ALPHA", "symptom",
            "Fictional note: I coughed twice this morning.",
            "2026-06-03")
        amended = self.store.amend_patient_note(
            "CASE-ALPHA", symptom["note_id"],
            "Fictional note: I coughed twice this morning and rested.",
            "2026-06-03")
        self.assertEqual(amended["version"], 2)
        notes = {n["note_id"]: n for n in self.store.patient_notes("CASE-ALPHA")}
        self.assertEqual(set(notes), {lived["note_id"], symptom["note_id"]})
        self.assertEqual(len(notes[symptom["note_id"]]["versions"]), 2)
        old = notes[symptom["note_id"]]["versions"][0]
        new = notes[symptom["note_id"]]["versions"][1]
        self.assertEqual(old["record_state"], "superseded")
        self.assertIn("coughed twice this morning.", old["note_text"])
        self.assertEqual(new["record_state"], "current")
        self.assertEqual(new["previous_id"], old["id"])
        with self.assertRaisesRegex(InvalidInput, "must change"):
            self.store.amend_patient_note(
                "CASE-ALPHA", lived["note_id"],
                "Fictional note: I enjoy reading in the garden.", "2026-06-02")
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.amend_patient_note(
                "CASE-BETA", lived["note_id"], "Fictional changed wording here",
                "2026-06-04")
        with self.assertRaisesRegex(InvalidInput, "Note kind must be"):
            self.store.add_patient_note(
                "CASE-ALPHA", "diagnosis", "Fictional invalid kind note here",
                "2026-06-04")

    def test_state_carries_goals_notes_and_plain_disclaimer(self):
        self._goal()
        self.store.add_patient_note("CASE-ALPHA", "lived_experience",
                                    "Fictional note: I napped in the afternoon.",
                                    "2026-06-04")
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(len(state["patient_goals"]), 1)
        self.assertEqual(len(state["patient_notes"]), 1)
        disclaimer = state["patient_words_disclaimer"]
        self.assertIn("own words", disclaimer)
        self.assertIn("Never a diagnosis", disclaimer)
        self.assertEqual(self.store.state("CASE-BETA")["patient_goals"], [])


class PatientGoalsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "goals-http.sqlite")
        seed(cls.path)
        bound = type("BoundGoalsHandlerForTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers=headers)
        try:
            with urlopen(req, timeout=5) as response:
                body = response.read()
                ctype = response.headers.get("Content-Type", "")
                return response.status, json.loads(body) if "json" in ctype else body
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_goal_and_note_roundtrip_through_api(self):
        status, created = self.request("/api/cases/CASE-ALPHA/patient-goals", {
            "statement": "Fictional HTTP goal: rest every afternoon",
            "stated_date": "2026-06-05",
            "review_trigger": "Revisit at the next planned visit",
            "review_date": None,
            "diagnosis": "MUST-NOT-BE-STORED"})
        self.assertEqual(status, 201)
        goal_id = created["goal_id"]
        status, amended = self.request(
            f"/api/cases/CASE-ALPHA/patient-goals/{goal_id}/amendments", {
                "statement": "Fictional HTTP goal: rest every afternoon quietly",
                "stated_date": "2026-06-05",
                "review_trigger": "Revisit at the next planned visit"})
        self.assertEqual(status, 201)
        self.assertEqual(amended["version"], 2)
        status, marked = self.request(
            f"/api/cases/CASE-ALPHA/patient-goals/{goal_id}/status", {
                "status": "achieved",
                "reason": "Fictional reason: afternoons feel restful now."})
        self.assertEqual(status, 201)
        self.assertEqual(marked["status"], "achieved")
        status, note = self.request("/api/cases/CASE-ALPHA/patient-notes", {
            "kind": "symptom",
            "text": "Fictional HTTP note: I slept well last night.",
            "noted_date": "2026-06-06",
            "staging": "MUST-NOT-BE-STORED"})
        self.assertEqual(status, 201)
        status, state = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        goals = {g["goal_id"]: g for g in state["patient_goals"]}
        self.assertIn(goal_id, goals)
        self.assertEqual(goals[goal_id]["current"]["status"], "achieved")
        self.assertEqual(len(goals[goal_id]["versions"]), 3)
        self.assertNotIn("MUST-NOT-BE-STORED", json.dumps(state["patient_goals"]))
        notes = {n["note_id"]: n for n in state["patient_notes"]}
        self.assertIn(note["note_id"], notes)
        self.assertNotIn("MUST-NOT-BE-STORED", json.dumps(state["patient_notes"]))
        self.assertIn("own words", state["patient_words_disclaimer"])

    def test_unknown_case_uses_existing_case_boundary(self):
        status, error = self.request("/api/cases/CASE-UNKNOWN/patient-goals", {
            "statement": "Fictional goal that must not persist here",
            "stated_date": "2026-06-05",
            "review_trigger": "Revisit later"})
        self.assertEqual(status, 422)
        self.assertEqual(error["error"], "Unknown case")


class PatientGoalsUiContractTests(unittest.TestCase):
    def test_case_view_links_and_renders_plain_fictional_surface(self):
        html = (ROOT / "web" / "index.html").read_text()
        self.assertIn('href="#patient-goals"', html)
        self.assertIn('id="patient-goals"', html)
        self.assertIn('id="goal-list"', html)
        self.assertIn('id="note-list"', html)
        self.assertIn('id="goal-form"', html)
        self.assertIn('id="goal-amend-form"', html)
        self.assertIn('id="goal-status-form"', html)
        self.assertIn('id="note-form"', html)
        self.assertIn('id="note-amend-form"', html)
        self.assertIn("in the patient's own words", html)
        self.assertIn("FICTIONAL DEMO DATA", html)
        self.assertIn("never a diagnosis", html.lower())

    def test_renderer_is_case_scoped_source_safe_and_plain(self):
        javascript = (ROOT / "web" / "app.js").read_text()
        self.assertIn("renderPatientWords", javascript)
        self.assertIn("/patient-goals", javascript)
        self.assertIn("/patient-notes", javascript)
        self.assertIn("patient-reported", javascript)
        self.assertIn("FICTIONAL", javascript)
        self.assertNotIn("innerHTML", javascript)


if __name__ == "__main__":
    unittest.main()
