"""Counterevidence and safety-uncertainty surfacing for a case.

Fictional engineering fixtures only. No clinical benefit, toxicity,
response, eligibility, recommendation, order, dosing, or diagnosis claim.
These tests pin software behavior only:

* Newly arrived evidence can hold or invalidate a promising option, with
  its reason and triggering source or evidence assessment recorded
  append-only and kept visible after later amendments.
* Tumor expression alone or tracer uptake alone never establishes benefit
  or toxicity: the server refuses such wording and blocks promotion.
* Ex vivo / preclinical notes are labeled preclinical only, never an
  observed patient response or permission to administer, and the UI
  renders the server label verbatim so it cannot be stripped.
* Cross-modal safety uncertainty stays visible before any promotion.
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
from open_intelligence.__main__ import FICTIONAL_ACTOR_HEADER

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


def report(name):
    return (SAMPLE / name).read_bytes()


def evidence(name="demo-evidence.txt"):
    return (SAMPLE / name).read_bytes()


class CounterevidenceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "counter.sqlite")
        self.store.add_case("CASE-ALPHA", "Fictional Alpha")
        self.store.add_case("CASE-BETA", "Fictional Beta")
        self.path = self.store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
        self.img = self.store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
        self.beta = self.store.import_report("CASE-BETA", report("beta-pathology.txt"))
        self.q = self.store.add_question("CASE-ALPHA", "What fictional options stay discussable here?")
        self.q_beta = self.store.add_question("CASE-BETA", "What fictional options stay discussable here?")
        self.snap = self.store.create_snapshot(
            "CASE-ALPHA", self.q, "A human-authored synthetic discussion draft.",
            [self.path["source_id"]])
        self.snap_beta = self.store.create_snapshot(
            "CASE-BETA", self.q_beta, "A human-authored synthetic beta draft.",
            [self.beta["source_id"]])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _option(self, label="Fictional discussion item A"):
        return self.store.create_option(
            "CASE-ALPHA", self.snap, label,
            "A fictional item discussed for planning purposes only.", "unknown")

    def _view_option(self, option_id):
        for option in self.store.option_view("CASE-ALPHA")["options"]:
            if option["id"] == option_id:
                return option
        self.fail(f"option {option_id} not in view")

    def test_hold_records_reason_and_trigger_and_blocks_promotion(self):
        option = self._option()
        hold_id = self.store.add_option_counterevidence(
            "CASE-ALPHA", option, "hold",
            "New fictional imaging note argues against this option; holding for review.",
            source_version_id=self.img["source_id"])
        view = self._view_option(option)
        self.assertTrue(view["held_by_counterevidence"])
        self.assertEqual(view["display_operational_status"], "held")
        self.assertEqual(len(view["counterevidence"]), 1)
        record = view["counterevidence"][0]
        self.assertEqual(record["id"], hold_id)
        self.assertEqual(record["effect"], "hold")
        self.assertIn("holding for review", record["reason"])
        self.assertEqual(record["source_version_id"], self.img["source_id"])
        self.assertIsNone(record["evidence_assessment_id"])
        self.assertIn("IMG-ALPHA@1", record["trigger"])
        self.assertEqual(record["trigger_state"], "current")
        with self.assertRaisesRegex(InvalidInput, "held by recorded counterevidence"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                     "Discussion-only review scope for this item.")
        # Rejection stays available; the hold record stays visible as history.
        self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "reject",
                                 "Rejected while the recorded hold stays visible.")
        self.assertEqual(self._view_option(option)["operational_status"], "rejected")
        self.assertEqual(len(self._view_option(option)["counterevidence"]), 1)
        # The other fictional case is unaffected.
        beta_option = self.store.create_option(
            "CASE-BETA", self.snap_beta, "Fictional beta discussion item",
            "A fictional item in the independent beta case.", "unknown")
        beta_view = self.store.option_view("CASE-BETA")["options"][0]
        self.assertEqual(beta_view["id"], beta_option)
        self.assertFalse(beta_view["held_by_counterevidence"])
        self.assertEqual(beta_view["counterevidence"], [])

    def test_invalidate_reopens_review_and_survives_amendment_as_history(self):
        ev = self.store.import_synthetic_evidence(evidence())
        assessment = self.store.assess_synthetic_evidence(
            "CASE-ALPHA", self.q, ev["evidence_version_id"], "contradicts", "limited",
            "A human-authored rationale noting the new fictional limitation.")
        option = self._option()
        self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                 "Discussion-only review scope for this item.")
        self.assertEqual(self._view_option(option)["operational_status"], "reviewed")
        record_id = self.store.add_option_counterevidence(
            "CASE-ALPHA", option, "invalidate",
            "New fictional evidence note invalidates the basis; reopening review.",
            evidence_assessment_id=assessment)
        view = self._view_option(option)
        self.assertEqual(view["review_state"], "needs_review")
        self.assertEqual(view["counterevidence"][0]["id"], record_id)
        self.assertEqual(view["counterevidence"][0]["evidence_assessment_id"], assessment)
        self.assertIn("EVID-ASSAY@1", view["counterevidence"][0]["trigger"])
        with self.assertRaisesRegex(InvalidInput, "held by recorded counterevidence|not current"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                     "Discussion-only review scope for this item.")
        # A later source amendment keeps the invalidation record, marked stale-aware.
        amended = self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        self.assertIn("invalidated_options", amended)
        view = self._view_option(option)
        self.assertEqual(len(view["counterevidence"]), 1)
        self.assertEqual(view["counterevidence"][0]["reason"],
                         "New fictional evidence note invalidates the basis; reopening review.")
        # Reconfirmation cannot clear recorded counterevidence; a new proposal is required.
        current = [s for s in self.store.state("CASE-ALPHA")["sources"]
                   if s["document_id"] == "PATH-ALPHA" and s["state"] == "current"][0]
        q2 = self.store.add_question("CASE-ALPHA", "What is discussed after the amendment?")
        snap2 = self.store.create_snapshot(
            "CASE-ALPHA", q2, "A human-authored post-amendment discussion draft.",
            [current["id"]])
        with self.assertRaisesRegex(InvalidInput, "held by recorded counterevidence"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "reconfirm",
                                     "Re-review against the post-amendment draft.", snap2)
        replacement = self.store.create_option(
            "CASE-ALPHA", snap2, "Fictional replacement discussion item",
            "A separately authored proposal against the current fictional report.", "unknown")
        self.store.review_option("CASE-ALPHA", replacement, "Synthetic reviewer", "approve",
                                 "Discussion-only review scope for this item.")
        self.assertEqual(self._view_option(replacement)["operational_status"], "reviewed")

    def test_superseded_trigger_stays_visible_as_history(self):
        option = self._option()
        self.store.add_option_counterevidence(
            "CASE-ALPHA", option, "hold",
            "Fictional pathology note holds this option pending re-review.",
            source_version_id=self.path["source_id"])
        self.store.add_option_safety_flag(
            "CASE-ALPHA", option, "cross_modal_gap",
            "Fictional safety question tied to the pathology note; unresolved.",
            source_version_id=self.path["source_id"])
        self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        view = self._view_option(option)
        self.assertEqual(len(view["counterevidence"]), 1)
        self.assertEqual(view["counterevidence"][0]["trigger_state"], "superseded")
        self.assertIn("PATH-ALPHA@1", view["counterevidence"][0]["trigger"])
        self.assertEqual(len(view["safety_flags"]), 1)
        self.assertEqual(view["safety_flags"][0]["trigger_state"], "superseded")
        self.assertTrue(view["held_by_counterevidence"])
        self.assertEqual(view["display_operational_status"], "held")

    def test_expression_or_tracer_alone_never_establishes_benefit_or_toxicity(self):
        option = self._option()
        with self.assertRaisesRegex(InvalidInput, "never establishes benefit or toxicity"):
            self.store.add_option_safety_flag(
                "CASE-ALPHA", option, "expression_only",
                "Fictional tumor expression note shows benefit established for review.")
        with self.assertRaisesRegex(InvalidInput, "never establishes benefit or toxicity"):
            self.store.add_option_safety_flag(
                "CASE-ALPHA", option, "tracer_only",
                "Fictional tracer note shows toxicity proven in this case.")
        flag = self.store.add_option_safety_flag(
            "CASE-ALPHA", option, "expression_only",
            "Fictional tumor expression note alone; benefit and toxicity unknown.",
            source_version_id=self.path["source_id"])
        view = self._view_option(option)
        self.assertEqual(len(view["safety_flags"]), 1)
        self.assertEqual(view["safety_flags"][0]["id"], flag)
        self.assertIn("does not establish benefit or toxicity", view["safety_flags"][0]["display_label"])
        self.assertIn("Fictional", view["safety_flags"][0]["display_label"])
        self.assertIn("PATH-ALPHA@1", view["safety_flags"][0]["trigger"])
        with self.assertRaisesRegex(InvalidInput, "never establishes benefit or toxicity"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                     "Discussion-only review scope for this item.")
        # The flag stays visible after the refused promotion.
        self.assertEqual(len(self._view_option(option)["safety_flags"]), 1)
        self.assertIsNotNone(self._view_option(option)["safety_block"])

    def test_preclinical_is_labeled_and_never_a_patient_response_or_permission(self):
        option = self._option()
        with self.assertRaisesRegex(InvalidInput, "never an observed patient response"):
            self.store.add_option_safety_flag(
                "CASE-ALPHA", option, "preclinical_only",
                "Fictional ex vivo activity shows an observed patient response here.")
        with self.assertRaisesRegex(InvalidInput, "never an observed patient response"):
            self.store.add_option_safety_flag(
                "CASE-ALPHA", option, "preclinical_only",
                "Fictional preclinical activity gives permission to administer now.")
        flag = self.store.add_option_safety_flag(
            "CASE-ALPHA", option, "preclinical_only",
            "Fictional ex vivo activity only; patient-level meaning unknown.")
        view = self._view_option(option)
        label = view["safety_flags"][0]["display_label"]
        self.assertEqual(view["safety_flags"][0]["id"], flag)
        self.assertIn("Preclinical only", label)
        self.assertIn("not an observed patient response", label)
        self.assertIn("not permission to administer", label)
        detail = view["safety_flags"][0]["detail"].lower()
        self.assertNotIn("observed patient response", detail)
        self.assertNotIn("permission to administer", detail)
        with self.assertRaisesRegex(InvalidInput, "not an observed patient response"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                     "Discussion-only review scope for this item.")

    def test_cross_modal_safety_stays_visible_before_promotion(self):
        option = self._option()
        flag = self.store.add_option_safety_flag(
            "CASE-ALPHA", option, "cross_modal_gap",
            "Fictional safety question spans imaging and laboratory notes; unresolved.")
        view = self._view_option(option)
        self.assertEqual(view["safety_flags"][0]["id"], flag)
        self.assertIn("Cross-modal safety uncertainty", view["safety_flags"][0]["display_label"])
        with self.assertRaisesRegex(InvalidInput, "stays visible before any promotion"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                     "Discussion-only review scope for this item.")
        # Still visible after the refused promotion, and in the case state projection.
        state_options = {o["id"]: o for o in self.store.state("CASE-ALPHA")["options"]}
        self.assertEqual(len(state_options[option]["safety_flags"]), 1)
        self.assertEqual(state_options[option]["safety_flags"][0]["category"], "cross_modal_gap")

    def test_ui_renders_server_labels_verbatim_and_cannot_strip_preclinical(self):
        app_js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        index_html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        # The case view reaches the new surface and renders server records.
        self.assertIn("option-counterevidence-form", index_html)
        self.assertIn("option-safety-form", index_html)
        self.assertIn("counterevidence", app_js)
        self.assertIn("safety_flags", app_js)
        # The canonical server label is rendered as-is; the UI adds no
        # filtering branch that could drop the preclinical wording.
        self.assertIn("flag.display_label", app_js)
        self.assertIn("Safety uncertainties (visible before any promotion)", app_js)
        self.assertIn("Counterevidence (holds and invalidations stay visible)", app_js)
        self.assertIn("Fictional safety note", app_js)
        self.assertIn("Fictional counterevidence", app_js)

    def test_promotion_scope_cannot_claim_established_benefit_or_response(self):
        option = self._option()
        with self.assertRaisesRegex(InvalidInput, "never establishes benefit or toxicity"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                     "Promotion scope claims benefit established for review.")
        with self.assertRaisesRegex(InvalidInput, "never an observed patient response"):
            self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "approve",
                                     "Promotion scope claims an observed patient response here.")
        # Non-promotion actions keep their existing wording rules only.
        self.store.review_option("CASE-ALPHA", option, "Synthetic reviewer", "abstain",
                                 "Abstaining on this discussion item for now.")
        self.assertEqual(len(self._view_option(option)["review_events"]), 1)

    def test_triggers_and_language_are_validated(self):
        option = self._option()
        with self.assertRaisesRegex(InvalidInput, "exactly one"):
            self.store.add_option_counterevidence("CASE-ALPHA", option, "hold",
                                                  "A reason with no trigger at all here.",
                                                  source_version_id=None,
                                                  evidence_assessment_id=None)
        with self.assertRaisesRegex(InvalidInput, "exactly one"):
            self.store.add_option_counterevidence(
                "CASE-ALPHA", option, "hold", "A reason with two triggers at once here.",
                source_version_id=self.path["source_id"], evidence_assessment_id=1)
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.add_option_counterevidence("CASE-ALPHA", option, "hold",
                                                  "A reason citing another case source here.",
                                                  source_version_id=self.beta["source_id"])
        with self.assertRaisesRegex(InvalidInput, "recommendation"):
            self.store.add_option_counterevidence(
                "CASE-ALPHA", option, "hold", "We recommend this fictional item now.",
                source_version_id=self.path["source_id"])
        with self.assertRaisesRegex(InvalidInput, "dosing"):
            self.store.add_option_safety_flag("CASE-ALPHA", option, "other",
                                              "Fictional note mentions 50 mg dosing here.")
        with self.assertRaisesRegex(InvalidInput, "Invalid safety category"):
            self.store.add_option_safety_flag("CASE-ALPHA", option, "not_a_category",
                                              "A fictional detail of proper length here.")


class CounterevidenceSafetyHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from open_intelligence.__main__ import Handler, seed
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "counter-http.sqlite")
        seed(cls.path)
        bound = type("CounterHttpHandler", (Handler,), {"db_path": cls.path})
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

    def call(self, path, data=None):
        headers = {FICTIONAL_ACTOR_HEADER: "FICTIONAL-NAVIGATOR-A"}
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(),
                          headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_counterevidence_and_safety_routes(self):
        status, state = self.call("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        source_id = next(s["id"] for s in state["sources"] if s["state"] == "current")
        status, created_q = self.call("/api/cases/CASE-ALPHA/questions",
                                      {"question": "Which fictional options face new counterevidence?"})
        self.assertEqual(status, 201)
        status, created_s = self.call("/api/cases/CASE-ALPHA/snapshots",
                                      {"question_id": created_q["question_id"],
                                       "summary": "A human-authored synthetic discussion draft.",
                                       "source_ids": [source_id]})
        self.assertEqual(status, 201)
        status, created_o = self.call("/api/cases/CASE-ALPHA/options",
                                      {"snapshot_id": created_s["snapshot_id"],
                                       "label": "Fictional discussion item",
                                       "description": "A fictional item discussed for planning purposes only.",
                                       "epistemic_status": "unknown"})
        self.assertEqual(status, 201)
        option_id = created_o["option_id"]
        status, held = self.call(f"/api/cases/CASE-ALPHA/options/{option_id}/counterevidence",
                                 {"effect": "hold",
                                  "reason": "New fictional source note holds this option for review.",
                                  "source_version_id": source_id,
                                  "evidence_assessment_id": None})
        self.assertEqual(status, 201)
        self.assertIn("counterevidence_id", held)
        status, flagged = self.call(f"/api/cases/CASE-ALPHA/options/{option_id}/safety-flags",
                                    {"category": "preclinical_only",
                                     "detail": "Fictional ex vivo activity only; meaning unknown.",
                                     "source_version_id": None,
                                     "evidence_assessment_id": None})
        self.assertEqual(status, 201)
        self.assertIn("safety_flag_id", flagged)
        status, view = self.call("/api/cases/CASE-ALPHA/options")
        self.assertEqual(status, 200)
        option = next(o for o in view["options"] if o["id"] == option_id)
        self.assertEqual(option["display_operational_status"], "held")
        self.assertEqual(len(option["counterevidence"]), 1)
        self.assertIn("Preclinical only", option["safety_flags"][0]["display_label"])
        status, denied = self.call(f"/api/cases/CASE-ALPHA/options/{option_id}/review",
                                   {"reviewer_label": "Synthetic reviewer", "action": "approve",
                                    "scope": "Discussion-only review scope for this item.",
                                    "snapshot_id": None})
        self.assertEqual(status, 422)
        self.assertIn("held", denied["error"].lower())


if __name__ == "__main__":
    unittest.main()
