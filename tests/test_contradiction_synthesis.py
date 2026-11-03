"""Contradiction synthesis + bounded source-linked reports (B-08, closes G-08).

Software-contract checks only, on freshly authored fictional bytes. No
clinical correctness is asserted. Nothing here grades a claim: the tests
require supporting and contradicting items side by side with no quality
number, and stale-basis reports marked REVIEW-PENDING, never current.
"""

import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import Handler, seed

FIXTURES = Path(__file__).resolve().parent / "fixtures"

FULL_PERMS = {
    "metadata": {"store": "allowed", "display": "allowed"},
    "full_text": {"store": "allowed", "display": "allowed"},
}

REPORT_V1 = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-PATH
Type: pathology
Event-Date: 2026-04-02
Issued-At: 2026-04-04
Specimen: FIG-SPECIMEN
Finding: growth-pattern|reported|Fictional cells form small clusters at the edge of the sample.
Finding: marker-q|pending|Marker Q testing is still in progress for this fictional sample.
"""

REPORT_V2 = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-PATH
Type: pathology
Event-Date: 2026-04-02
Issued-At: 2026-04-06
Specimen: FIG-SPECIMEN
Amends: FIG-PATH@1
Finding: growth-pattern|reported|Fictional cells form small clusters at the edge of the sample; wording clarified.
Finding: marker-q|indeterminate|Marker Q testing ended without a readable result for this fictional sample.
"""

REPORT_OTHER = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-02
Document: FIG2-PATH
Type: pathology
Event-Date: 2026-04-03
Issued-At: 2026-04-05
Specimen: FIG2-SPECIMEN
Finding: growth-pattern|reported|Fictional cells in the second case form loose sheets.
"""

EVID_SUPPORTS = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-S
Title: Fictional cluster-pattern background note
Issued-At: 2026-03-10
Rights: original-synthetic
Statement: This fictional note describes cluster patterns seen in invented samples; it draws no conclusion about any person.
"""

EVID_CONTRADICTS = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-C
Title: Fictional dissenting methods note
Issued-At: 2026-03-12
Rights: original-synthetic
Statement: This fictional note records that small samples were hard to read in invented cases; it draws no conclusion about any person.
"""

EVID_UNKNOWN = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-U
Title: Fictional inconclusive assay note
Issued-At: 2026-03-14
Rights: original-synthetic
Statement: This fictional note leaves the assay reading open; it draws no conclusion about any person.
"""

EVID_CONTEXT = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-X
Title: Fictional sampling background note
Issued-At: 2026-03-16
Rights: original-synthetic
Statement: This fictional note describes how invented samples were handled; it draws no conclusion about any person.
"""

QUESTION = "What does the fictional pathology note record about the sample pattern?"
SUMMARY = "Human-authored draft: the fictional note records clusters, with dissent noted."


def _payload_keys(value, found):
    if isinstance(value, dict):
        for key, item in value.items():
            found.append(key)
            _payload_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            _payload_keys(item, found)
    return found


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "cases.sqlite")
        self.store.add_case("CASE-FIG-01", "Fictional synthesis case one")
        self.store.add_case("CASE-FIG-02", "Fictional synthesis case two")
        self.source_v1 = self.store.import_report("CASE-FIG-01", REPORT_V1)["source_id"]
        self.question_1 = self.store.add_question("CASE-FIG-01", QUESTION)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _assess(self, raw, relation, applicability, rationale):
        version = self.store.import_synthetic_evidence(raw)["evidence_version_id"]
        return self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.question_1, version, relation, applicability, rationale)

    def _broker_link(self, relation="context", applicability="limited"):
        rights_id = self.store.register_rights_source(
            "FIG-ARCHIVE-1", "Fictional Archive", "v1", "2026-02-01", FULL_PERMS,
            attribution="Fictional archive, demo only")["rights_source_id"]
        return self.store.create_broker_link(
            "CASE-FIG-01", self.question_1, rights_id, relation, applicability,
            "Fictional archive entry is background only; it says nothing about any person.",
            citation_title="Fictional archive background entry",
            excerpt="Invented background text with no conclusion about any person.")["broker_link_id"]

    def _full_snapshot(self):
        aid_s = self._assess(EVID_SUPPORTS, "supports", "applicable",
                             "Fictional cluster text matches the question topic; applicability is a reviewer label.")
        aid_c = self._assess(EVID_CONTRADICTS, "contradicts", "limited",
                             "Fictional dissent text disagrees on small-sample reading; kept visible beside support.")
        aid_u = self._assess(EVID_UNKNOWN, "unknown", "unknown",
                             "Fictional assay note leaves the reading open; recorded as unknown, not absent.")
        aid_x = self._assess(EVID_CONTEXT, "context", "applicable",
                             "Fictional handling note is background for the question; no finding follows.")
        link = self._broker_link()
        snapshot = self.store.create_snapshot(
            "CASE-FIG-01", self.question_1, SUMMARY, [self.source_v1],
            [aid_s, aid_c, aid_u, aid_x], [link])
        return {"supports": aid_s, "contradicts": aid_c, "unknown": aid_u,
                "context": aid_x, "link": link, "snapshot": snapshot}

    def test_synthesis_groups_support_contradict_context_unknown_per_claim(self):
        built = self._full_snapshot()
        payload = self.store.question_synthesis("CASE-FIG-01", self.question_1)
        groups = payload["groups"]
        self.assertEqual([item["id"] for item in groups["supporting"]], [built["supports"]])
        self.assertEqual([item["id"] for item in groups["contradicting"]], [built["contradicts"]])
        self.assertEqual([item["relation"] for item in groups["contradicting"]], ["contradicts"])
        self.assertEqual([item["id"] for item in groups["unknown_limited"]], [built["unknown"]])
        context_ids = sorted(item["id"] for item in groups["context"])
        self.assertIn(built["context"], context_ids)
        self.assertIn(built["link"], context_ids)
        item = groups["supporting"][0]
        for key in ("relation", "applicability", "review_state", "anchor",
                    "cutoff_event_id", "rationale", "limitation_notes"):
            self.assertIn(key, item)
        self.assertEqual(item["anchor"]["evidence_key"], "FIG-EVID-S")
        self.assertEqual(item["anchor"]["statement_line"], 6)
        self.assertEqual(payload["counts"]["total"], 5)
        self.assertIn("no claim-splitting", payload["granularity"])

    def test_no_contradicting_item_dropped_from_synthesis(self):
        built = self._full_snapshot()
        payload = self.store.question_synthesis("CASE-FIG-01", self.question_1)
        underlying = self.store.state("CASE-FIG-01")
        expected = [row for row in underlying["evidence_assessments"]
                    if row["question_id"] == self.question_1 and row["relation"] == "contradicts"]
        expected += [row for row in underlying["broker_links"]
                     if row["question_id"] == self.question_1 and row["relation"] == "contradicts"]
        shown = payload["groups"]["contradicting"]
        self.assertEqual(len(expected), 1)
        self.assertEqual(len(shown), len(expected))
        self.assertEqual(shown[0]["id"], built["contradicts"])
        report = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertIn("## Contradicting items (1)", report)
        self.assertIn("FIG-EVID-C@1", report)

    def test_unknown_limited_rendered_distinctly_from_absent(self):
        built = self._full_snapshot()
        report = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertIn("## Unknown or limited items (1)", report)
        self.assertIn("FIG-EVID-U@1", report)
        empty_snapshot = self.store.create_snapshot(
            "CASE-FIG-01", self.question_1,
            "Human-authored draft with no linked items at all.", [self.source_v1])
        empty_report = self.store.synthesis_report("CASE-FIG-01", empty_snapshot)
        self.assertIn("## Supporting items (0)", empty_report)
        self.assertIn("None included; no supporting item is linked at this cutoff.", empty_report)
        self.assertIn("## Unknown or limited items (0)", empty_report)
        self.assertIn("None included; no unknown or limited item is linked at this cutoff.", empty_report)
        self.assertIn("Linked items: 0 ", empty_report)

    def test_every_report_carries_snapshot_and_event_cutoff(self):
        built = self._full_snapshot()
        payload = self.store.snapshot_synthesis("CASE-FIG-01", built["snapshot"])
        latest_event = self.store.state("CASE-FIG-01")["events"][0]["id"]
        self.assertEqual(payload["cutoff"]["snapshot_id"], built["snapshot"])
        self.assertEqual(payload["cutoff"]["event_id"], latest_event)
        self.assertRegex(payload["cutoff"]["occurred_at"], r"^\d{4}-\d{2}-\d{2}T")
        report = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertIn(f"Cutoff: snapshot #{built['snapshot']}, event #{latest_event} at ", report)
        patient = self.store.synthesis_patient_report("CASE-FIG-01", built["snapshot"])
        self.assertIn(f"draft #{built['snapshot']}, record event #{latest_event} at ", patient)
        question_payload = self.store.question_synthesis("CASE-FIG-01", self.question_1)
        self.assertEqual(question_payload["cutoff"]["event_id"], latest_event)

    def test_same_cutoff_renders_byte_identical(self):
        built = self._full_snapshot()
        first = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        second = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertEqual(first, second)
        first_patient = self.store.synthesis_patient_report("CASE-FIG-01", built["snapshot"])
        second_patient = self.store.synthesis_patient_report("CASE-FIG-01", built["snapshot"])
        self.assertEqual(first_patient, second_patient)
        self.assertEqual(self.store.snapshot_synthesis("CASE-FIG-01", built["snapshot"]),
                         self.store.snapshot_synthesis("CASE-FIG-01", built["snapshot"]))

    def test_stale_basis_export_carries_review_pending_versions_and_date(self):
        built = self._full_snapshot()
        self.store.import_report("CASE-FIG-01", REPORT_V2)
        report = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertIn("REVIEW-PENDING", report)
        self.assertIn("State: **stale**", report)
        self.assertIn("FIG-PATH@1", report)
        self.assertIn("superseded", report)
        self.assertRegex(report, r"event #\d+ at \d{4}-\d{2}-\d{2}T")
        self.assertIn("2026-04-02", report)
        patient = self.store.synthesis_patient_report("CASE-FIG-01", built["snapshot"])
        self.assertIn("needs another look", patient)
        self.assertIn("FIG-PATH@1", patient)
        payload = self.store.snapshot_synthesis("CASE-FIG-01", built["snapshot"])
        self.assertTrue(payload["basis"]["stale_basis"])
        self.assertTrue(any("stale" in reason for reason in payload["basis"]["reasons"]))

    def test_stale_basis_triggers_include_rights_and_evidence_changes(self):
        contra_version = self.store.import_synthetic_evidence(EVID_CONTRADICTS)["evidence_version_id"]
        aid_c = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.question_1, contra_version, "contradicts", "limited",
            "Fictional dissent text disagrees on small-sample reading; kept visible beside support.")
        rights_id = self.store.register_rights_source(
            "FIG-ARCHIVE-9", "Fictional Archive", "v1", "2026-02-01", FULL_PERMS,
            attribution="Fictional archive, demo only")["rights_source_id"]
        link = self.store.create_broker_link(
            "CASE-FIG-01", self.question_1, rights_id, "supports", "applicable",
            "Fictional archive entry agrees on background only; applicability is a reviewer label.",
            citation_title="Fictional archive background entry",
            excerpt="Invented background text with no conclusion about any person.")["broker_link_id"]
        snapshot = self.store.create_snapshot(
            "CASE-FIG-01", self.question_1, SUMMARY, [self.source_v1], [aid_c], [link])
        self.assertNotIn("REVIEW-PENDING", self.store.synthesis_report("CASE-FIG-01", snapshot))
        self.store.revoke_rights_source(rights_id, "Fictional archive entry retired from the demo.")
        self.store.withdraw_synthetic_evidence(
            contra_version, "Fictional dissent text intentionally retired from the demo.")
        report = self.store.synthesis_report("CASE-FIG-01", snapshot)
        self.assertIn("REVIEW-PENDING", report)
        self.assertIn("State: **stale**", report)
        self.assertIn("is revoked", report)
        self.assertIn("is withdrawn", report)
        payload = self.store.snapshot_synthesis("CASE-FIG-01", snapshot)
        self.assertTrue(payload["basis"]["stale_basis"])
        contradicting = payload["groups"]["contradicting"]
        self.assertEqual([item["id"] for item in contradicting], [aid_c])
        self.assertEqual(contradicting[0]["review_state"], "needs_review")
        supporting = payload["groups"]["supporting"]
        self.assertEqual([item["id"] for item in supporting], [link])
        self.assertEqual(supporting[0]["review_state"], "needs_review")
        self.assertTrue(supporting[0]["content"]["content_withheld"])
        self.assertIsNone(supporting[0]["content"]["excerpt"])
        patient = self.store.synthesis_patient_report("CASE-FIG-01", snapshot)
        self.assertIn("needs another look", patient)
        self.assertIn("marked as disagreeing", patient)
        self.assertNotIn("Invented background text", patient)
        self.assertNotIn("Invented background text", report)

    def test_stale_export_never_presents_old_conclusion_as_current(self):
        built = self._full_snapshot()
        fresh = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertNotIn("REVIEW-PENDING", fresh)
        self.store.import_report("CASE-FIG-01", REPORT_V2)
        stale = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertIn("REVIEW-PENDING", stale)
        self.assertIn("history, not a current conclusion", stale)
        forbidden = ["up to date", "still current", "remains current", "no further review",
                     "nothing to review", "no review needed", "all clear"]
        for text in (fresh, stale):
            lowered = text.lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, lowered)

    def test_patient_rendering_adds_no_certainty_on_fixture_pair(self):
        report_bytes = (FIXTURES / "synthesis_certainty_report.txt").read_bytes()
        evidence_bytes = (FIXTURES / "synthesis_certainty_evidence.txt").read_bytes()
        source_id = self.store.import_report("CASE-FIG-01", report_bytes)["source_id"]
        question = self.store.add_question(
            "CASE-FIG-01", "What does the fictional visit note say about tiredness?")
        support_version = self.store.import_synthetic_evidence(evidence_bytes)["evidence_version_id"]
        aid_s = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", question, support_version, "supports", "applicable",
            "Fictional background note lists everyday causes; kept as background, not a finding.")
        contra_version = self.store.import_synthetic_evidence(EVID_CONTRADICTS)["evidence_version_id"]
        aid_c = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", question, contra_version, "contradicts", "limited",
            "Fictional dissent text disagrees on small-sample reading; kept visible beside support.")
        snapshot = self.store.create_snapshot(
            "CASE-FIG-01", question,
            "Human-authored draft: tiredness is recorded, cause left open.", [source_id],
            [aid_s, aid_c])
        professional = self.store.synthesis_report("CASE-FIG-01", snapshot)
        patient = self.store.synthesis_patient_report("CASE-FIG-01", snapshot)
        payload = self.store.snapshot_synthesis("CASE-FIG-01", snapshot)
        cutoff_event = payload["cutoff"]["event_id"]
        self.assertIn(f"event #{cutoff_event}", professional)
        self.assertIn(f"event #{cutoff_event}", patient)
        self.assertIn("## Contradicting items (1)", professional)
        self.assertIn("marked as disagreeing", patient)
        self.assertIn("FICTIONAL", patient)
        self.assertIn(f"assessment #{aid_s}", patient)
        self.assertIn(f"assessment #{aid_c}", patient)
        certainty_gain = re.compile(
            r"\b(proves?|proven|confirms?|confirmed|established?|definitely|"
            r"certainly|guarantees?|undoubtedly)\b", re.IGNORECASE)
        self.assertIsNone(certainty_gain.search(patient))
        self.assertIsNone(certainty_gain.search(professional))
        clinical_directive = ["you should", "we recommend", "is recommended",
                              "prescribed", "eligible for", "order the", "authorized"]
        for phrase in clinical_directive:
            self.assertNotIn(phrase, patient.lower())
            self.assertNotIn(phrase, professional.lower())

    def test_limitation_notes_human_entered_append_only_no_autograding(self):
        built = self._full_snapshot()
        first = self.store.add_limitation_note(
            "CASE-FIG-01", self.question_1, assessment_id=built["supports"],
            note="FIG-01 note: fictional cluster text is background only, with no checked finding.",
            author_label="FICTIONAL-REVIEWER-B")
        second = self.store.add_limitation_note(
            "CASE-FIG-01", self.question_1, broker_link_id=built["link"],
            note="FIG-01 note: fictional archive entry lacks methods detail for this question.",
            author_label="FICTIONAL-NAVIGATOR-A")
        third = self.store.add_limitation_note(
            "CASE-FIG-01", self.question_1, assessment_id=built["supports"],
            note="FIG-01 note: second remark on the same item stays beside the first remark.",
            author_label="FICTIONAL-REVIEWER-B")
        notes = self.store.list_limitation_notes("CASE-FIG-01", self.question_1)
        self.assertEqual([note["id"] for note in notes], [first, second, third])
        self.assertEqual(notes[0]["note"],
                         "FIG-01 note: fictional cluster text is background only, with no checked finding.")
        payload = self.store.question_synthesis("CASE-FIG-01", self.question_1)
        supporting_notes = payload["groups"]["supporting"][0]["limitation_notes"]
        self.assertEqual([note["id"] for note in supporting_notes], [first, third])
        report = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertIn("FICTIONAL-REVIEWER-B", report)
        self.assertIn("stays beside the first remark", report)
        with self.assertRaisesRegex(InvalidInput, "exactly one"):
            self.store.add_limitation_note(
                "CASE-FIG-01", self.question_1, assessment_id=built["supports"],
                broker_link_id=built["link"], note="A note naming two targets at once here.",
                author_label="FICTIONAL-REVIEWER-B")
        with self.assertRaisesRegex(InvalidInput, "exactly one"):
            self.store.add_limitation_note(
                "CASE-FIG-01", self.question_1,
                note="A note with no target record named at all here.",
                author_label="FICTIONAL-REVIEWER-B")
        with self.assertRaisesRegex(InvalidInput, "15–800"):
            self.store.add_limitation_note(
                "CASE-FIG-01", self.question_1, assessment_id=built["supports"],
                note="Too short.", author_label="FICTIONAL-REVIEWER-B")
        other_question = self.store.add_question("CASE-FIG-02", "What does the second case record?")
        with self.assertRaisesRegex(InvalidInput, "not in this case and question"):
            self.store.add_limitation_note(
                "CASE-FIG-02", other_question, assessment_id=built["supports"],
                note="A cross-case note attempt that must fail closed here.",
                author_label="FICTIONAL-REVIEWER-B")
        self.assertFalse(hasattr(self.store, "update_limitation_note"))
        self.assertFalse(hasattr(self.store, "delete_limitation_note"))
        keys = _payload_keys(payload, [])
        for key in keys:
            self.assertNotRegex(key, r"(grade|score|rank)")
        grading_words = re.compile(r"\b(grades?|graded|grading|scores?|scored|ranked|established?)\b",
                                   re.IGNORECASE)
        self.assertIsNone(grading_words.search(report))
        self.assertIsNone(grading_words.search(
            self.store.synthesis_patient_report("CASE-FIG-01", built["snapshot"])))

    def test_contradictory_evidence_survives_amendment_with_history(self):
        built = self._full_snapshot()
        self.store.import_report("CASE-FIG-01", REPORT_V2)
        self.assertEqual(self.store.state("CASE-FIG-01")["snapshots"][0]["state"], "stale")
        payload = self.store.snapshot_synthesis("CASE-FIG-01", built["snapshot"])
        contradicting = payload["groups"]["contradicting"]
        self.assertEqual(len(contradicting), 1)
        self.assertEqual(contradicting[0]["id"], built["contradicts"])
        self.assertIn("disagrees on small-sample reading", contradicting[0]["rationale"])
        self.assertTrue(payload["basis"]["stale_basis"])
        report = self.store.synthesis_report("CASE-FIG-01", built["snapshot"])
        self.assertIn("## Contradicting items (1)", report)
        self.assertIn("REVIEW-PENDING", report)
        current_source = self.store.import_report("CASE-FIG-01", REPORT_V2)
        self.assertEqual(current_source["result"], "duplicate")
        new_snapshot = self.store.create_snapshot(
            "CASE-FIG-01", self.question_1,
            "Human-authored replacement draft on the current source only.",
            [current_source["source_id"]])
        new_payload = self.store.snapshot_synthesis("CASE-FIG-01", new_snapshot)
        self.assertEqual(new_payload["counts"]["total"], 0)
        new_report = self.store.synthesis_report("CASE-FIG-01", new_snapshot)
        self.assertIn("None included; no contradicting item is linked at this cutoff.", new_report)
        self.assertNotIn("REVIEW-PENDING", new_report)

    def test_synthesis_and_reports_case_isolated(self):
        built = self._full_snapshot()
        self.store.add_limitation_note(
            "CASE-FIG-01", self.question_1, assessment_id=built["supports"],
            note="FIG-01-only note text that must never leak across cases here.",
            author_label="FICTIONAL-REVIEWER-B")
        other_source = self.store.import_report("CASE-FIG-02", REPORT_OTHER)["source_id"]
        other_question = self.store.add_question("CASE-FIG-02", "What does the second case record?")
        other_snapshot = self.store.create_snapshot(
            "CASE-FIG-02", other_question,
            "Human-authored draft for the unrelated second case.", [other_source])
        other_payload = self.store.question_synthesis("CASE-FIG-02", other_question)
        self.assertEqual(other_payload["counts"]["total"], 0)
        other_snapshot_payload = self.store.snapshot_synthesis("CASE-FIG-02", other_snapshot)
        self.assertEqual(other_snapshot_payload["counts"]["total"], 0)
        for text in (self.store.synthesis_report("CASE-FIG-02", other_snapshot),
                     self.store.synthesis_patient_report("CASE-FIG-02", other_snapshot)):
            self.assertNotIn("FIG-EVID", text)
            self.assertNotIn("FIG-PATH@", text)
            self.assertNotIn("FIG-01-only note", text)
            self.assertIn("FIG2-PATH@1", text)
        first_payload = self.store.question_synthesis("CASE-FIG-01", self.question_1)
        self.assertEqual(first_payload["counts"]["total"], 5)
        with self.assertRaisesRegex(InvalidInput, "Question not in this case"):
            self.store.question_synthesis("CASE-FIG-01", other_question)
        with self.assertRaisesRegex(InvalidInput, "Investigation not in this case"):
            self.store.snapshot_synthesis("CASE-FIG-01", other_snapshot)


class SynthesisHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerForSynthesisTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def _url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def _get_json(self, path):
        try:
            with urlopen(self._url(path), timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def _get_text(self, path):
        try:
            with urlopen(self._url(path), timeout=5) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as err:
            return err.code, err.read().decode("utf-8")

    def _post_json(self, path, payload):
        request = Request(self._url(path), data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_synthesis_routes_round_trip(self):
        status, state = self._get_json("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        source_id = state["sources"][0]["id"]
        status, created = self._post_json("/api/cases/CASE-ALPHA/questions",
                                          {"question": "What does the seeded fictional note record?"})
        self.assertEqual(status, 201)
        question_id = created["question_id"]
        status, imported = self._post_json(
            "/api/evidence/imports", {"text": EVID_SUPPORTS.decode("utf-8")})
        self.assertEqual(status, 200)
        status, assessed = self._post_json(
            "/api/cases/CASE-ALPHA/evidence-assessments",
            {"question_id": question_id, "evidence_version_id": imported["evidence_version_id"],
             "relation": "supports", "applicability": "applicable",
             "rationale": "Seeded-case check: fictional text matches the question topic only."})
        self.assertEqual(status, 201)
        status, drafted = self._post_json(
            "/api/cases/CASE-ALPHA/snapshots",
            {"question_id": question_id, "summary": "Seeded-case draft for the synthesis route check.",
             "source_ids": [source_id],
             "evidence_assessment_ids": [assessed["assessment_id"]]})
        self.assertEqual(status, 201)
        snapshot_id = drafted["snapshot_id"]
        status, noted = self._post_json(
            "/api/cases/CASE-ALPHA/limitation-notes",
            {"question_id": question_id, "assessment_id": assessed["assessment_id"],
             "note": "Seeded-case note: fictional text is background only, nothing follows.",
             "author_label": "FICTIONAL-REVIEWER-B"})
        self.assertEqual(status, 201)
        self.assertIn("note_id", noted)
        status, payload = self._get_json(
            f"/api/cases/CASE-ALPHA/questions/{question_id}/synthesis")
        self.assertEqual(status, 200)
        self.assertEqual(payload["counts"]["supporting"], 1)
        self.assertEqual(payload["groups"]["supporting"][0]["limitation_notes"][0]["id"],
                         noted["note_id"])
        status, bound = self._get_json(f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/synthesis")
        self.assertEqual(status, 200)
        self.assertEqual(bound["cutoff"]["snapshot_id"], snapshot_id)
        status, report = self._get_text(f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/synthesis-report")
        self.assertEqual(status, 200)
        self.assertIn("Cutoff: snapshot #", report)
        self.assertIn("Seeded-case note", report)
        status, patient = self._get_text(
            f"/api/cases/CASE-ALPHA/snapshots/{snapshot_id}/synthesis-report-patient")
        self.assertEqual(status, 200)
        self.assertIn("FICTIONAL", patient)
        self.assertIn("Seeded-case note", patient)

    def test_synthesis_route_errors(self):
        status, _ = self._get_json("/api/cases/CASE-NOPE/questions/1/synthesis")
        self.assertEqual(status, 422)
        status, _ = self._get_json("/api/cases/CASE-ALPHA/questions/999999/synthesis")
        self.assertEqual(status, 422)
        status, _ = self._get_json("/api/cases/CASE-ALPHA/snapshots/999999/synthesis")
        self.assertEqual(status, 422)
        status, _ = self._get_text("/api/cases/CASE-ALPHA/snapshots/999999/synthesis-report")
        self.assertEqual(status, 422)
        status, _ = self._post_json("/api/cases/CASE-ALPHA/limitation-notes",
                                    {"question_id": 1, "note": "Too short.", "author_label": "X"})
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
