"""Patient attention list: read-only projection over existing ledger state.

Fictional/demo data only. No clinical urgency is inferred; ordering uses
recorded YYYY-MM-DD dates only, undated entries sort last with an explicit
marker. Nothing here authorizes, schedules, or executes anything.
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
from open_intelligence.patient_attention import NO_DATE, case_patient_attention

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"

FORBIDDEN_TITLE_WORDS = (
    "urgent", "emergency", "critical", "priority", "immediately",
    "recommend", "prescrib", "eligible", "treatment", "therapy",
    "should", "must", "order",
)


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


def _acceptance_setup(store: CaseStore, case_id: str = "CASE-ALPHA") -> dict:
    """One open question, one draft pending review, one open follow-up task."""
    store.add_case(case_id, f"Fictional {case_id.title()}")
    imported = store.import_report(case_id, report("alpha-pathology-original.txt"))
    question_id = store.add_question(
        case_id, "What does the fictional Alpha source report about Marker A?")
    snapshot_id = store.create_snapshot(
        case_id, question_id,
        "A human-authored fictional draft awaiting demo review.",
        [imported["source_id"]])
    option_id = store.create_option(
        case_id, snapshot_id, "Fictional discussion item",
        "A fictional item discussed for planning purposes only.", "unknown")
    task_id = store.add_preparation_task(
        case_id, option_id, "Fictional follow-up step", "Fictional owner")
    return {"question_id": question_id, "snapshot_id": snapshot_id,
            "option_id": option_id, "task_id": task_id,
            "source_id": imported["source_id"]}


class PatientAttentionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "attention.sqlite")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_empty_case_shows_honest_empty_state(self):
        self.store.add_case("CASE-EMPTY", "Fictional empty case")
        result = case_patient_attention(self.store, "CASE-EMPTY")

        self.assertEqual(result["case_id"], "CASE-EMPTY")
        self.assertTrue(result["synthetic"])
        self.assertIn("FICTIONAL", result["disclaimer"])
        self.assertIn("read-only", result["disclaimer"].lower())
        self.assertIn("no date recorded", result["disclaimer"].lower())
        self.assertIn("Nothing here authorizes", result["disclaimer"])
        self.assertEqual(result["counts"], {"entries": 0})
        self.assertEqual(result["entries"], [])

    def test_acceptance_three_entries_with_correct_citations(self):
        ids = _acceptance_setup(self.store)
        result = case_patient_attention(self.store, "CASE-ALPHA")

        self.assertEqual(result["counts"], {"entries": 3})
        self.assertEqual(len(result["entries"]), 3)
        by_kind = {}
        for entry in result["entries"]:
            by_kind.setdefault(entry["kind"], []).append(entry)
        self.assertEqual(set(by_kind), {"open_question", "pending_review", "follow_up"})
        open_entry = by_kind["open_question"][0]
        self.assertEqual(open_entry["record_type"], "question")
        self.assertEqual(open_entry["record_id"], ids["question_id"])
        self.assertIn(str(ids["question_id"]), open_entry["source_anchor"])
        draft_entry = by_kind["pending_review"][0]
        self.assertEqual(draft_entry["record_type"], "snapshot")
        self.assertEqual(draft_entry["record_id"], ids["snapshot_id"])
        task_entry = by_kind["follow_up"][0]
        self.assertEqual(task_entry["record_type"], "task")
        self.assertEqual(task_entry["record_id"], ids["task_id"])
        # All three are undated, so they sort by kind in documented order.
        self.assertEqual([e["kind"] for e in result["entries"]],
                         ["open_question", "pending_review", "follow_up"])
        for entry in result["entries"]:
            self.assertTrue(entry["fictional"])
            self.assertIsNone(entry["recorded_date"])
            self.assertEqual(entry["date_display"], NO_DATE)
            self.assertEqual(entry["date_display"], "no date recorded")
            self.assertLessEqual(len(entry["title"].split()), 30)
            lowered = entry["title"].lower()
            for word in FORBIDDEN_TITLE_WORDS:
                self.assertNotIn(word, lowered)
            self.assertIn("FICTIONAL", entry["title"])
            self.assertTrue(entry["review_state"])
            self.assertTrue(entry["source_anchor"])
            self.assertTrue(entry["detail"])

    def test_completing_followup_removes_it_on_next_read(self):
        ids = _acceptance_setup(self.store)
        before = case_patient_attention(self.store, "CASE-ALPHA")
        self.assertEqual(before["counts"], {"entries": 3})

        self.store.set_preparation_task_status("CASE-ALPHA", ids["task_id"], "done")
        after = case_patient_attention(self.store, "CASE-ALPHA")

        self.assertEqual(after["counts"], {"entries": 2})
        remaining_tasks = [e for e in after["entries"]
                           if e["record_type"] == "task"]
        self.assertEqual(remaining_tasks, [])
        remaining_ids = {(e["record_type"], e["record_id"]) for e in after["entries"]}
        self.assertIn(("question", ids["question_id"]), remaining_ids)
        self.assertIn(("snapshot", ids["snapshot_id"]), remaining_ids)

    def test_cancelled_followup_also_leaves_the_list(self):
        ids = _acceptance_setup(self.store)
        self.store.set_preparation_task_status(
            "CASE-ALPHA", ids["task_id"], "cancelled")
        result = case_patient_attention(self.store, "CASE-ALPHA")

        self.assertEqual(result["counts"], {"entries": 2})
        self.assertFalse([e for e in result["entries"]
                          if e["record_type"] == "task"])

    def test_dated_entries_order_oldest_first_undated_last(self):
        ids = _acceptance_setup(self.store)
        late = self.store.add_option_dependency(
            "CASE-ALPHA", ids["option_id"], "source",
            source_version_id=ids["source_id"],
            deadline_date="2026-07-01", deadline_basis="sourced",
            anchor="A human-recorded anchor of at least ten characters.")
        early = self.store.add_option_dependency(
            "CASE-ALPHA", ids["option_id"], "source",
            source_version_id=ids["source_id"],
            deadline_date="2026-06-01", deadline_basis="sourced",
            anchor="Another human-recorded anchor for ordering.")
        result = case_patient_attention(self.store, "CASE-ALPHA")

        self.assertEqual(result["counts"], {"entries": 5})
        dates = [e["recorded_date"] for e in result["entries"]]
        self.assertEqual(dates[:2], ["2026-06-01", "2026-07-01"])
        self.assertEqual([e["record_id"] for e in result["entries"][:2]],
                         [early, late])
        for entry in result["entries"][2:]:
            self.assertIsNone(entry["recorded_date"])
            self.assertEqual(entry["date_display"], "no date recorded")
        self.assertEqual([e["kind"] for e in result["entries"][2:]],
                         ["open_question", "pending_review", "follow_up"])
        # Dated deadlines never invent urgency language.
        for entry in result["entries"][:2]:
            self.assertEqual(entry["kind"], "follow_up")
            self.assertEqual(entry["record_type"], "dependency")
            self.assertLessEqual(len(entry["title"].split()), 30)
            for word in FORBIDDEN_TITLE_WORDS:
                self.assertNotIn(word, entry["title"].lower())

    def test_threat_dates_join_dated_order_without_soonness_filter(self):
        ids = _acceptance_setup(self.store)
        threat = self.store.add_optionality_threat(
            "CASE-ALPHA", ids["option_id"], "expiring_window",
            "A fictional window that may close for planning purposes.",
            threat_date="2026-05-01", threat_basis="sourced",
            anchor="A human-recorded threat anchor of ten plus chars.")
        dependency = self.store.add_option_dependency(
            "CASE-ALPHA", ids["option_id"], "source",
            source_version_id=ids["source_id"],
            deadline_date="2026-08-01", deadline_basis="sourced",
            anchor="A human-recorded anchor of at least ten characters.")
        result = case_patient_attention(self.store, "CASE-ALPHA")

        self.assertEqual(result["counts"], {"entries": 5})
        self.assertEqual([e["recorded_date"] for e in result["entries"][:2]],
                         ["2026-05-01", "2026-08-01"])
        dated_ids = {(e["record_type"], e["record_id"]) for e in result["entries"][:2]}
        self.assertIn(("threat", threat), dated_ids)
        self.assertIn(("dependency", dependency), dated_ids)
        for entry in result["entries"][2:]:
            self.assertIsNone(entry["recorded_date"])
            self.assertEqual(entry["date_display"], "no date recorded")

    def test_stale_draft_with_open_question_lists_as_unanswered(self):
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        original = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        question_id = self.store.add_question(
            "CASE-ALPHA", "What does the fictional source report?")
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id,
            "A human-authored fictional draft for review.",
            [original["source_id"]])
        self.store.acknowledge_demo_review(
            "CASE-ALPHA", snapshot_id, "Synthetic reviewer")
        amended = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-amended.txt"))
        self.assertEqual(amended["invalidated_snapshots"], [snapshot_id])

        result = case_patient_attention(self.store, "CASE-ALPHA")
        kinds = {(e["kind"], e["record_type"], e["record_id"]) for e in result["entries"]}
        self.assertIn(("open_question", "question", question_id), kinds)
        self.assertIn(("unanswered", "snapshot", snapshot_id), kinds)
        stale_entry = next(e for e in result["entries"]
                           if e["record_id"] == snapshot_id and e["kind"] == "unanswered")
        self.assertEqual(stale_entry["date_display"], "no date recorded")
        self.assertLessEqual(len(stale_entry["title"].split()), 30)

    def test_option_needing_rereview_lists_as_pending_review(self):
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        original = self.store.import_report(
            "CASE-ALPHA", report("alpha-pathology-original.txt"))
        question_id = self.store.add_question(
            "CASE-ALPHA", "What options are discussed in this fictional case?")
        snapshot_id = self.store.create_snapshot(
            "CASE-ALPHA", question_id,
            "A human-authored synthetic discussion draft.",
            [original["source_id"]])
        option_id = self.store.create_option(
            "CASE-ALPHA", snapshot_id, "Fictional discussion item",
            "A fictional item discussed for planning purposes only.", "unknown")
        self.store.add_option_dependency(
            "CASE-ALPHA", option_id, "source",
            source_version_id=original["source_id"])
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))

        result = case_patient_attention(self.store, "CASE-ALPHA")
        option_entries = [e for e in result["entries"]
                          if e["record_type"] == "option"]
        self.assertEqual(len(option_entries), 1)
        self.assertEqual(option_entries[0]["kind"], "pending_review")
        self.assertEqual(option_entries[0]["record_id"], option_id)
        self.assertIn("needs_review", option_entries[0]["review_state"])

    def test_strict_case_isolation(self):
        ids = _acceptance_setup(self.store, "CASE-ALPHA")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        beta_question = self.store.add_question(
            "CASE-BETA", "What does the distinct Beta fictional source report?")

        alpha = case_patient_attention(self.store, "CASE-ALPHA")
        beta = case_patient_attention(self.store, "CASE-BETA")
        rendered_beta = json.dumps(beta)

        self.assertEqual(beta["counts"], {"entries": 1})
        self.assertEqual(beta["entries"][0]["record_id"], beta_question)
        # Structured check, not a dumps substring: small integer ids
        # occur all over any serialized payload (dates, counts, ids).
        self.assertNotIn(
            ids["question_id"],
            [e["record_id"] for e in beta["entries"]
             if e["record_type"] == "question"])
        self.assertNotIn("Marker A", rendered_beta)
        self.assertIn("Beta fictional source", rendered_beta)
        rendered_alpha = json.dumps(alpha)
        self.assertNotIn("Beta fictional source", rendered_alpha)
        # Same structured form as above: '2' occurs all over any payload.
        self.assertNotIn(
            beta_question,
            [e["record_id"] for e in alpha["entries"]
             if e["record_type"] == "question"])

    def test_dependency_and_threat_case_isolation_via_option_join(self):
        alpha_ids = _acceptance_setup(self.store, "CASE-ALPHA")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        beta_source = self.store.import_report(
            "CASE-BETA", report("beta-pathology.txt"))
        beta_q = self.store.add_question(
            "CASE-BETA", "What does the Beta fictional source report?")
        beta_snap = self.store.create_snapshot(
            "CASE-BETA", beta_q, "A human-authored Beta fictional draft.",
            [beta_source["source_id"]])
        beta_option = self.store.create_option(
            "CASE-BETA", beta_snap, "Fictional Beta discussion item",
            "A fictional Beta item discussed for planning only.", "unknown")
        self.store.add_option_dependency(
            "CASE-ALPHA", alpha_ids["option_id"], "source",
            source_version_id=alpha_ids["source_id"],
            deadline_date="2026-06-01", deadline_basis="sourced",
            anchor="An Alpha-only human-recorded anchor text.")
        self.store.add_optionality_threat(
            "CASE-ALPHA", alpha_ids["option_id"], "other",
            "An Alpha-only fictional threat description.",
            threat_date="2026-06-02", threat_basis="sourced",
            anchor="An Alpha-only threat anchor text here.")

        beta = case_patient_attention(self.store, "CASE-BETA")
        self.assertEqual(
            {(e["record_type"], e["record_id"]) for e in beta["entries"]},
            {("question", beta_q), ("snapshot", beta_snap)})
        self.assertFalse([e for e in beta["entries"]
                          if e["recorded_date"] is not None])

    def test_unknown_case_raises(self):
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        with self.assertRaises(InvalidInput):
            case_patient_attention(self.store, "CASE-NOPE")

    def test_projection_is_read_only_and_adds_no_tables(self):
        ids = _acceptance_setup(self.store)
        tables_before = {r[0] for r in self.store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        events_before = self.store.db.execute(
            "SELECT id, kind, details FROM events ORDER BY id").fetchall()
        first = case_patient_attention(self.store, "CASE-ALPHA")
        second = case_patient_attention(self.store, "CASE-ALPHA")

        self.assertEqual(first, second)
        tables_after = {r[0] for r in self.store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        events_after = self.store.db.execute(
            "SELECT id, kind, details FROM events ORDER BY id").fetchall()
        self.assertEqual(tables_before, tables_after)
        self.assertEqual(list(events_before), list(events_after))
        cited = {(e["record_type"], e["record_id"]) for e in first["entries"]}
        self.assertIn(("question", ids["question_id"]), cited)
        self.assertIn(("snapshot", ids["snapshot_id"]), cited)
        self.assertIn(("task", ids["task_id"]), cited)

    def test_terminal_option_deadlines_and_threats_stay_historical(self):
        ids = _acceptance_setup(self.store)
        dependency = self.store.add_option_dependency(
            "CASE-ALPHA", ids["option_id"], "source",
            source_version_id=ids["source_id"],
            deadline_date="2026-06-01", deadline_basis="sourced",
            anchor="A human-recorded anchor of at least ten characters.")
        threat = self.store.add_optionality_threat(
            "CASE-ALPHA", ids["option_id"], "other",
            "A fictional threat recorded before withdrawal.",
            threat_date="2026-06-02", threat_basis="sourced",
            anchor="A human-recorded threat anchor text here.")
        before = case_patient_attention(self.store, "CASE-ALPHA")
        self.assertIn(("dependency", dependency),
                      {(e["record_type"], e["record_id"]) for e in before["entries"]})
        self.assertIn(("threat", threat),
                      {(e["record_type"], e["record_id"]) for e in before["entries"]})

        self.store.review_option(
            "CASE-ALPHA", ids["option_id"], "Synthetic reviewer",
            "withdraw", "Withdrawing this fictional discussion item.")
        after = case_patient_attention(self.store, "CASE-ALPHA")
        cited = {(e["record_type"], e["record_id"]) for e in after["entries"]}
        self.assertNotIn(("dependency", dependency), cited)
        self.assertNotIn(("threat", threat), cited)
        # The open question, draft, and task remain; only historical dates leave.
        self.assertIn(("question", ids["question_id"]), cited)
        self.assertIn(("snapshot", ids["snapshot_id"]), cited)
        self.assertIn(("task", ids["task_id"]), cited)


class PatientAttentionHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "attention-http.sqlite")
        seed(cls.path)
        bound_handler = type(
            "BoundAttentionHandlerForTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path: str, data: dict | None = None):
        headers = {"Content-Type": "application/json"} if data is not None else {}
        body = None if data is None else json.dumps(data).encode()
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=body, headers=headers)
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_seeded_case_exposes_ordered_read_only_attention(self):
        status, payload = self.request("/api/cases/CASE-ALPHA/patient-attention")

        self.assertEqual(status, 200)
        self.assertEqual(payload["case_id"], "CASE-ALPHA")
        self.assertTrue(payload["synthetic"])
        self.assertIn("FICTIONAL", payload["disclaimer"])
        self.assertIn("Nothing here authorizes", payload["disclaimer"])
        self.assertEqual(payload["counts"], {"entries": 0})
        self.assertEqual(payload["entries"], [])

    def test_open_question_appears_with_citation_through_http(self):
        status, created = self.request(
            "/api/cases", {"case_id": "CASE-HTTP-Q", "label": "Fictional HTTP case"})
        self.assertEqual(status, 201)
        status, question = self.request(
            "/api/cases/CASE-HTTP-Q/questions",
            {"question": "What does this fictional HTTP case still need?"})
        self.assertEqual(status, 201)
        status, payload = self.request("/api/cases/CASE-HTTP-Q/patient-attention")

        self.assertEqual(status, 200)
        self.assertEqual(payload["counts"], {"entries": 1})
        entry = payload["entries"][0]
        self.assertEqual(entry["kind"], "open_question")
        self.assertEqual(entry["record_id"], question["question_id"])
        self.assertEqual(entry["date_display"], "no date recorded")
        self.assertLessEqual(len(entry["title"].split()), 30)

    def test_http_case_isolation(self):
        self.request("/api/cases",
                     {"case_id": "CASE-HTTP-A", "label": "Fictional HTTP A"})
        self.request("/api/cases",
                     {"case_id": "CASE-HTTP-B", "label": "Fictional HTTP B"})
        self.request("/api/cases/CASE-HTTP-A/questions",
                     {"question": "What is the Alpha-only fictional HTTP question?"})
        status_a, payload_a = self.request("/api/cases/CASE-HTTP-A/patient-attention")
        status_b, payload_b = self.request("/api/cases/CASE-HTTP-B/patient-attention")

        self.assertEqual(status_a, 200)
        self.assertEqual(status_b, 200)
        self.assertEqual(payload_a["counts"], {"entries": 1})
        self.assertEqual(payload_b["counts"], {"entries": 0})
        self.assertNotIn("Alpha-only", json.dumps(payload_b))
        self.assertIn("Alpha-only", json.dumps(payload_a))

    def test_unknown_case_uses_existing_case_boundary(self):
        status, payload = self.request("/api/cases/CASE-UNKNOWN/patient-attention")

        self.assertEqual(status, 422)
        self.assertEqual(payload["error"], "Unknown case")


class PatientAttentionUiContractTests(unittest.TestCase):
    def test_patient_view_contains_what_needs_attention_panel(self):
        html = (ROOT / "web" / "index.html").read_text()

        self.assertIn("What needs attention", html)
        self.assertIn('id="patient-attention"', html)
        self.assertIn('<div id="patient-attention" class="questions"', html)
        self.assertIn("no date recorded", html)
        self.assertIn("Nothing here authorizes, schedules, or executes anything.", html)
        # The panel lives inside the existing patient view section.
        view_start = html.index('id="patient-view"')
        attention_at = html.index('id="patient-attention"')
        mission_at = html.index('id="patient-mission"')
        self.assertLess(view_start, attention_at)
        self.assertLess(attention_at, mission_at)

    def test_renderer_is_case_scoped_text_only_and_refreshable(self):
        javascript = (ROOT / "web" / "app.js").read_text()

        self.assertIn("'/api/cases/' + requested + '/patient-attention'", javascript)
        self.assertIn("loadPatientAttention", javascript)
        self.assertIn("renderPatientAttention", javascript)
        self.assertIn("clear('patient-attention')", javascript)
        self.assertIn("Discard stale attention responses after case changes.", javascript)
        self.assertIn("pill('FICTIONAL'", javascript)
        self.assertIn("no date recorded", javascript)
        self.assertIn("Citation: ", javascript)
        self.assertIn("Recorded date: ", javascript)

    def test_local_server_routes_patient_attention(self):
        server = (ROOT / "src" / "open_intelligence" / "__main__.py").read_text()

        self.assertIn("patient-attention", server)
        self.assertIn("case_patient_attention", server)
        self.assertIn('re.fullmatch(rf"/api/cases/{ID_PART}/patient-attention", path)',
                      server)


if __name__ == "__main__":
    unittest.main()
