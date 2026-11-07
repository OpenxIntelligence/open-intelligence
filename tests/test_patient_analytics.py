"""Analysis dimension (slice D4): patient analytics — lab trends,
symptom progression, record completeness, outcomes tracking.

D4 acceptance: trends render from stored labs; completeness flags
missing elements without inventing them; suite green with zero new
failures.

Fixtures are independently authored synthetic reports imported
through the one import path, plus synthetic patient notes, goals,
and follow-through tasks recorded through the store's own methods.
No live model call is made here: every view is deterministic code
over the ledger. Lab trends are computed over real T2 series built
by the D3 toolset and passed in as plain mappings.
"""

import ast
import dataclasses
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
from session_auth import signin_demo
from open_intelligence.lab_series import lab_series
from open_intelligence.patient_analytics import (
    lab_trends,
    outcomes_tracking,
    patient_analytics,
    record_completeness,
    symptom_progression,
)
from open_intelligence.therapy import record_therapy_lines

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "open_intelligence"

D4_MODULES = ("patient_analytics",)


def report(patient, document, kind, event_date, findings, *, specimen=None,
           issued=None, amends=None):
    """Build one synthetic report in the OI-SYNTHETIC-REPORT/1 format."""
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", f"Type: {kind}",
             f"Event-Date: {event_date}", f"Issued-At: {issued or event_date}"]
    if specimen:
        lines.append(f"Specimen: {specimen}")
    if amends:
        lines.append(f"Amends: {amends}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode("utf-8")


class AnalyticsTestBase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.dir.name) / "t.db")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")

    def tearDown(self):
        self.dir.cleanup()

    def import_report(self, case_id, raw):
        return self.store.import_report(case_id, raw)["source_id"]

    def _lab(self, document, event_date, quote, *, specimen="SPEC-LAB"):
        return self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", document, "laboratory", event_date,
            [("hemoglobin", "reported", quote)], specimen=specimen))

    def _lab_series(self):
        return dataclasses.asdict(lab_series(self.store, "CASE-ALPHA"))


class LabTrendTests(AnalyticsTestBase):
    def test_rising_falling_and_stable(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 12 g/dL.")
        result = lab_trends(self._lab_series())
        trend = result["trends"]["hemoglobin"]
        self.assertEqual(trend["trend"], "rising")
        self.assertAlmostEqual(trend["percent_change"], 20.0)
        self.assertEqual(trend["points_used"], 2)
        self.assertEqual(trend["direction_changes"], 0)
        self.assertTrue(trend["monotone"])
        self.assertEqual(result["analytes_with_trend"], 1)

        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.import_report("CASE-BETA", report(
            "CASE-BETA", "LAB-A", "laboratory", "2026-05-03",
            [("hemoglobin", "reported", "Hemoglobin was 12 g/dL.")],
            specimen="SPEC-LAB"))
        self.import_report("CASE-BETA", report(
            "CASE-BETA", "LAB-B", "laboratory", "2026-05-10",
            [("hemoglobin", "reported", "Hemoglobin was 10 g/dL.")],
            specimen="SPEC-LAB"))
        beta = dataclasses.asdict(lab_series(self.store, "CASE-BETA"))
        self.assertEqual(lab_trends(beta)["trends"]["hemoglobin"]["trend"],
                         "falling")

    def test_small_change_is_stable_not_a_trend(self):
        # The 1% band is a pinned display convention: floating-point
        # dust must not read as a trend.
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10.0 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 10.05 g/dL.")
        trend = lab_trends(self._lab_series())["trends"]["hemoglobin"]
        self.assertEqual(trend["trend"], "stable")
        self.assertAlmostEqual(trend["percent_change"], 0.5)

    def test_single_point_is_not_computable(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        trend = lab_trends(self._lab_series())["trends"]["hemoglobin"]
        self.assertEqual(trend["trend"], "not_computable")
        self.assertEqual(trend["trend_reason"], "insufficient_points")
        self.assertEqual(trend["points_used"], 0)

    def test_unparseable_and_ambiguous_points_are_excluded_not_dropped(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 12 g/dL.")
        self._lab("LAB-C", "2026-05-17",
                  "Hemoglobin was low, no number recorded.")
        self._lab("LAB-D", "2026-05-24", "Hemoglobin was 10 and 12 g/dL.")
        self._lab("LAB-E", "2026-05-31", "Hemoglobin was 13 g/dL.")
        trend = lab_trends(self._lab_series())["trends"]["hemoglobin"]
        self.assertEqual(trend["trend"], "rising")
        self.assertEqual(trend["points_used"], 2)
        self.assertEqual(
            [e["reason"] for e in trend["excluded_points"]],
            ["unparseable", "ambiguous", "shorter_run"])

    def test_unit_change_splits_the_run(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 11 g/dL.")
        self._lab("LAB-C", "2026-05-17", "Hemoglobin was 110 g/L.")
        self._lab("LAB-D", "2026-05-24", "Hemoglobin was 115 g/L.")
        self._lab("LAB-E", "2026-05-31", "Hemoglobin was 120 g/L.")
        trend = lab_trends(self._lab_series())["trends"]["hemoglobin"]
        # The longest run wins; the earlier run is listed as excluded.
        self.assertEqual(trend["unit"], "g/L")
        self.assertEqual(trend["points_used"], 3)
        self.assertEqual(trend["trend"], "rising")
        self.assertEqual(
            [e["reason"] for e in trend["excluded_points"]],
            ["unit_change", "unit_change"])

    def test_tied_runs_earliest_wins(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 11 g/dL.")
        self._lab("LAB-C", "2026-05-17", "Hemoglobin was 110 g/L.")
        self._lab("LAB-D", "2026-05-24", "Hemoglobin was 115 g/L.")
        trend = lab_trends(self._lab_series())["trends"]["hemoglobin"]
        self.assertEqual(trend["unit"], "g/dL")
        self.assertEqual(trend["points_used"], 2)

    def test_direction_changes_and_non_monotone(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 13 g/dL.")
        self._lab("LAB-C", "2026-05-17", "Hemoglobin was 11 g/dL.")
        self._lab("LAB-D", "2026-05-24", "Hemoglobin was 14 g/dL.")
        trend = lab_trends(self._lab_series())["trends"]["hemoglobin"]
        self.assertEqual(trend["trend"], "rising")
        self.assertEqual(trend["direction_changes"], 2)
        self.assertFalse(trend["monotone"])

    def test_zero_baseline_leaves_percent_undefined(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 0 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 5 g/dL.")
        trend = lab_trends(self._lab_series())["trends"]["hemoglobin"]
        self.assertEqual(trend["trend"], "rising")
        self.assertIsNone(trend["percent_change"])
        self.assertEqual(trend["percent_status"], "undefined_zero_baseline")

    def test_malformed_series_is_rejected(self):
        with self.assertRaises(InvalidInput):
            lab_trends({"case_id": "CASE-ALPHA"})
        with self.assertRaises(InvalidInput):
            lab_trends({"case_id": "CASE-ALPHA", "series": {"x": {}}})


class SymptomProgressionTests(AnalyticsTestBase):
    def _symptom(self, text, noted_date):
        return self.store.add_patient_note(
            "CASE-ALPHA", "symptom", text, noted_date)["note_id"]

    def test_notes_are_ordered_and_repeats_marked(self):
        first = self._symptom("Fictional fatigue most days.", "2026-05-03")
        second = self._symptom("Fictional fatigue most days.", "2026-05-10")
        third = self._symptom("Fictional nausea after meals.", "2026-05-17")
        result = symptom_progression(self.store, "CASE-ALPHA")
        self.assertEqual(result["status"], "has_symptom_notes")
        self.assertEqual(result["note_count"], 3)
        self.assertEqual(result["repeat_count"], 1)
        self.assertEqual(
            [(n["note_id"], n["recurrence"]) for n in result["notes"]],
            [(first, "first_report"), (second, "repeat"),
             (third, "first_report")])

    def test_reworded_repeat_is_a_new_first_report(self):
        # Recurrence is exact-text only; a reworded repeat is never
        # silently merged with the earlier wording.
        self._symptom("Fictional fatigue most days.", "2026-05-03")
        self._symptom("Fictional tiredness most days.", "2026-05-10")
        result = symptom_progression(self.store, "CASE-ALPHA")
        self.assertEqual(result["repeat_count"], 0)
        self.assertEqual([n["recurrence"] for n in result["notes"]],
                         ["first_report", "first_report"])

    def test_amended_note_keeps_earlier_wording(self):
        note_id = self._symptom("Fictional fatigue most days.", "2026-05-03")
        self.store.amend_patient_note(
            "CASE-ALPHA", note_id, "Fictional fatigue every day.",
            "2026-05-04")
        result = symptom_progression(self.store, "CASE-ALPHA")
        entry = result["notes"][0]
        self.assertTrue(entry["amended"])
        self.assertEqual(entry["note_text"], "Fictional fatigue every day.")
        self.assertEqual(entry["version"], 2)
        self.assertEqual(
            [(v["version"], v["note_text"])
             for v in entry["previous_versions"]],
            [(1, "Fictional fatigue most days.")])

    def test_lived_experience_notes_are_not_symptoms(self):
        self.store.add_patient_note(
            "CASE-ALPHA", "lived_experience",
            "Fictional walk around the block daily.", "2026-05-03")
        result = symptom_progression(self.store, "CASE-ALPHA")
        self.assertEqual(result["status"], "no_symptom_notes")
        self.assertEqual(result["notes"], [])

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            symptom_progression(self.store, "CASE-NOPE")


class RecordCompletenessTests(AnalyticsTestBase):
    def test_empty_case_is_all_missing(self):
        result = record_completeness(self.store, "CASE-ALPHA")
        self.assertEqual(result["present"], 0)
        self.assertEqual(result["missing"], len(result["checks"]))
        self.assertEqual(sorted(result["missing_keys"]),
                         sorted(c["key"] for c in result["checks"]))
        sources = next(c for c in result["checks"] if c["key"] == "sources")
        self.assertEqual(sources["status"], "missing")
        self.assertEqual(sources["count"], 0)

    def test_seeded_case_marks_what_it_holds(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 12 g/dL.")
        self.store.add_patient_note(
            "CASE-ALPHA", "symptom", "Fictional fatigue most days.",
            "2026-05-03")
        self.store.add_question("CASE-ALPHA", "What does the trend show?")
        result = record_completeness(self.store, "CASE-ALPHA")
        by_key = {c["key"]: c for c in result["checks"]}
        self.assertEqual(by_key["sources"]["status"], "present")
        self.assertEqual(by_key["laboratory_sources"]["count"], 2)
        self.assertEqual(by_key["longitudinal_coverage"]["count"], 1)
        self.assertEqual(by_key["symptom_notes"]["count"], 1)
        self.assertEqual(by_key["questions"]["count"], 1)
        self.assertEqual(by_key["imaging_sources"]["status"], "missing")
        self.assertEqual(by_key["molecular_sources"]["status"], "missing")
        self.assertEqual(by_key["therapy_lines"]["status"], "missing")
        self.assertIn("imaging_sources", result["missing_keys"])
        # Missing items name what they block, never a placeholder.
        self.assertEqual(by_key["imaging_sources"]["enables"],
                         "imaging comparison")

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            record_completeness(self.store, "CASE-NOPE")


class OutcomesTrackingTests(AnalyticsTestBase):
    def _therapy(self, document, event_date, findings):
        return self.import_report("CASE-ALPHA", report(
            "CASE-ALPHA", document, "clinical", event_date, findings))

    def test_therapy_lines_current_vs_stale(self):
        self._therapy("CLIN-A", "2026-05-03", [
            ("regimen-a", "reported", "Fictional regimen A was given.")])
        self._therapy("CLIN-B", "2026-05-10", [
            ("regimen-b", "reported", "Fictional regimen B was given.")])
        record_therapy_lines(
            self.store, "CASE-ALPHA", ("regimen-a", "regimen-b"),
            ruleset_version="lot-rules-1")
        record_therapy_lines(
            self.store, "CASE-ALPHA", ("regimen-a", "regimen-b"),
            ruleset_version="lot-rules-2")
        result = outcomes_tracking(self.store, "CASE-ALPHA")
        therapy = result["therapy_lines"]
        self.assertEqual(therapy["current_count"], 2)
        self.assertEqual(
            [(r["line_number"], r["regimen_key"], r["ruleset_version"])
             for r in therapy["current"]],
            [(1, "regimen-a", "lot-rules-2"),
             (2, "regimen-b", "lot-rules-2")])
        self.assertEqual(therapy["stale_count"], 2)
        self.assertEqual(therapy["stale_by_reason"],
                         {"ruleset_changed": 2})

    def test_goals_carry_status_history(self):
        goal = self.store.add_patient_goal(
            "CASE-ALPHA", "Fictional goal: walk daily.", "2026-05-03",
            "Fictional review trigger: monthly check.", "2026-06-03")
        self.store.set_patient_goal_status(
            "CASE-ALPHA", goal["goal_id"], "achieved",
            "Fictional reason: walking daily for a month.")
        result = outcomes_tracking(self.store, "CASE-ALPHA")
        goals = result["patient_goals"]
        self.assertEqual(goals["goal_count"], 1)
        self.assertEqual(goals["by_status"], {"achieved": 1})
        entry = goals["goals"][0]
        self.assertEqual(entry["status"], "achieved")
        self.assertEqual(entry["version_count"], 2)
        self.assertEqual(entry["status_changes"], 1)
        self.assertEqual(
            [h["status"] for h in entry["status_history"]],
            ["active", "achieved"])

    def test_followthrough_counts_and_overdue(self):
        first = self.store.create_followthrough_task(
            "CASE-ALPHA", "Fictional task one.", due_date="2026-05-10",
            actor_label="Fictional Clinician", reason="Fictional setup.")
        second = self.store.create_followthrough_task(
            "CASE-ALPHA", "Fictional task two.", due_date="2026-06-01",
            actor_label="Fictional Clinician", reason="Fictional setup.")
        # Completion walks the recorded path: assigned, acknowledged,
        # completed — each step is a recorded event.
        self.store.update_followthrough_task(
            "CASE-ALPHA", second, "assigned",
            actor_label="Fictional Clinician", reason="Fictional assigned.",
            owner_label="Fictional Nurse")
        self.store.update_followthrough_task(
            "CASE-ALPHA", second, "acknowledged",
            actor_label="Fictional Clinician", reason="Fictional seen.")
        self.store.update_followthrough_task(
            "CASE-ALPHA", second, "completed",
            actor_label="Fictional Clinician", reason="Fictional done.")
        result = outcomes_tracking(self.store, "CASE-ALPHA", today="2026-05-20")
        tasks = result["followthrough_tasks"]
        self.assertEqual(tasks["task_count"], 2)
        self.assertEqual(tasks["by_status"],
                         {"created": 1, "completed": 1})
        self.assertEqual(tasks["overdue"], 1)
        self.assertEqual(tasks["overdue_status"], "computed")
        # Creation itself records one event per task; each status step
        # records another.
        self.assertEqual(
            {t["task_id"]: t["event_count"] for t in tasks["tasks"]},
            {first: 1, second: 4})

    def test_overdue_not_computed_without_today(self):
        self.store.create_followthrough_task(
            "CASE-ALPHA", "Fictional task one.", due_date="2026-05-10",
            actor_label="Fictional Clinician", reason="Fictional setup.")
        tasks = outcomes_tracking(self.store, "CASE-ALPHA")["followthrough_tasks"]
        self.assertIsNone(tasks["overdue"])
        self.assertEqual(tasks["overdue_status"], "not_computed_no_today")

    def test_bad_today_is_rejected(self):
        with self.assertRaises(InvalidInput):
            outcomes_tracking(self.store, "CASE-ALPHA", today="20 May 2026")

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            outcomes_tracking(self.store, "CASE-NOPE")


class AggregatorTests(AnalyticsTestBase):
    def test_full_analytics_shape(self):
        self._lab("LAB-A", "2026-05-03", "Hemoglobin was 10 g/dL.")
        self._lab("LAB-B", "2026-05-10", "Hemoglobin was 12 g/dL.")
        result = patient_analytics(self.store, "CASE-ALPHA",
                                   lab_series=self._lab_series())
        self.assertEqual(result["case_id"], "CASE-ALPHA")
        self.assertEqual(
            result["lab_trends"]["trends"]["hemoglobin"]["trend"], "rising")
        self.assertEqual(result["symptom_progression"]["status"],
                         "no_symptom_notes")
        self.assertEqual(result["record_completeness"]["present"], 3)
        self.assertEqual(
            result["outcomes_tracking"]["therapy_lines"]["current_count"], 0)

    def test_no_lab_series_is_reported_not_filled(self):
        result = patient_analytics(self.store, "CASE-ALPHA")
        self.assertEqual(result["lab_trends"]["status"], "not_computed")
        self.assertEqual(result["lab_trends"]["reason"],
                         "no_lab_series_supplied")
        self.assertEqual(result["lab_trends"]["trends"], {})

    def test_series_for_another_case_is_rejected(self):
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.import_report("CASE-BETA", report(
            "CASE-BETA", "LAB-A", "laboratory", "2026-05-03",
            [("hemoglobin", "reported", "Hemoglobin was 10 g/dL.")],
            specimen="SPEC-LAB"))
        beta = dataclasses.asdict(lab_series(self.store, "CASE-BETA"))
        with self.assertRaises(InvalidInput):
            patient_analytics(self.store, "CASE-ALPHA", lab_series=beta)

    def test_unknown_case_raises(self):
        with self.assertRaises(InvalidInput):
            patient_analytics(self.store, "CASE-NOPE")


class AnalyticsHttpTests(unittest.TestCase):
    """The read-only analytics route, served live like test_http.py."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound = type("BoundHandlerForTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, headers=None):
        values = {"Cookie": self._cookie}
        values.update(headers or {})
        req = Request(f"http://127.0.0.1:{self.port}{path}", headers=values)
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_analytics_route_returns_four_views(self):
        status, data = self.request("/api/cases/CASE-ALPHA/analytics")
        self.assertEqual(status, 200)
        self.assertEqual(data["case_id"], "CASE-ALPHA")
        self.assertIn("lab_trends", data)
        self.assertIn("symptom_progression", data)
        self.assertIn("record_completeness", data)
        self.assertIn("outcomes_tracking", data)
        # Seeded CASE-ALPHA has sources but no laboratory kind.
        self.assertEqual(data["lab_trends"]["trends"], {})
        sources = next(
            c for c in data["record_completeness"]["checks"]
            if c["key"] == "sources")
        self.assertEqual(sources["status"], "present")

    def test_analytics_route_requires_a_grant(self):
        # W1: the header is ignored — a header-only request is denied.
        req = Request(
            f"http://127.0.0.1:{self.port}/api/cases/CASE-ALPHA/analytics",
            headers={"X-Fictional-Actor": "FICTIONAL-NOBODY"})
        try:
            with urlopen(req, timeout=5) as resp:
                status = resp.status
        except HTTPError as err:
            status = err.code
        self.assertEqual(status, 403)


class NoModelCallTests(unittest.TestCase):
    def test_module_has_no_model_call_and_no_dimension_import(self):
        # D4 is deterministic code over the ledger: it never calls a
        # model and never imports another dimension module (the T2
        # series arrives as data, not as an import).
        tree = ast.parse((SRC / "patient_analytics.py").read_text())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        self.assertFalse({"investigation", "skeptic", "__main__"} & imports)
        dimension_modules = {
            "extraction", "specimen_chain", "terminology", "fhir_exchange",
            "dicom", "longitudinal", "lab_series", "imaging", "molecular",
            "therapy",
        }
        imported = {name.split(".")[-1] for name in imports}
        self.assertFalse(dimension_modules & imported)
        self.assertEqual(D4_MODULES, ("patient_analytics",))
