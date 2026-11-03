"""B-11 enrichment projections: visits, journey stages, biological context.

Fictional fixtures only (CASE-FIG-01 / CASE-FIG-02). Behavior-3 goal tests
are deliberately NOT authored here: goals are draft-#80 territory and the
reviewer-verified reconciliation excludes them from this slice. The
stage-tag case is likewise excluded: human tag systems are draft-#77
territory. See PROGRESS.md.
"""

import hashlib
import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler
from open_intelligence.enrichments import (
    case_biological_context,
    case_journey_stages,
    case_visits,
)
from open_intelligence.investigation import GUARD_PATTERNS
from open_intelligence.mission import build_patient_mission
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.timeline import case_timeline


def _report(patient, document, event_date, issued_at, findings,
            specimen=None, amends=None, kind="pathology"):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {patient}",
             f"Document: {document}", f"Type: {kind}",
             f"Event-Date: {event_date}", f"Issued-At: {issued_at}"]
    if specimen is not None:
        lines.append(f"Specimen: {specimen}")
    if amends is not None:
        lines.append(f"Amends: {amends}")
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode()


FIG_PATH = _report(
    "CASE-FIG-01", "PATH-FIG-A", "2026-05-03", "2026-05-05",
    [("lesion-q", "reported", "Fictional FIG-01 pathology note records Lesion Q as observed."),
     ("margin-state", "pending", "Fictional FIG-01 pathology note leaves margin state pending.")],
    specimen="SPECIMEN-FIG-A")
FIG_IMG = _report(
    "CASE-FIG-01", "IMG-FIG-A", "2026-05-17", "2026-05-18",
    [("nodule-count", "reported", "Fictional FIG-01 imaging note records nodule count as observed.")],
    kind="imaging")
FIG_IMG2 = _report(
    "CASE-FIG-01", "IMG-FIG-A2", "2026-05-17", "2026-05-20",
    [("nodule-size", "indeterminate", "Fictional FIG-01 second imaging note leaves size indeterminate.")],
    kind="imaging")
FIG_PATH_AMENDED = _report(
    "CASE-FIG-01", "PATH-FIG-A", "2026-05-03", "2026-05-22",
    [("lesion-q", "reported", "Fictional FIG-01 pathology note records Lesion Q as observed."),
     ("margin-state", "reported", "Fictional FIG-01 amended note records margin state as observed."),
     ("stain-quality", "indeterminate", "Fictional FIG-01 amended note leaves stain quality indeterminate.")],
    specimen="SPECIMEN-FIG-A", amends="PATH-FIG-A@1")
FIG_BETA = _report(
    "CASE-FIG-02", "PATH-FIG-B", "2026-06-02", "2026-06-03",
    [("lesion-z", "reported", "Fictional FIG-02 pathology note records Lesion Z as observed.")],
    specimen="SPECIMEN-FIG-B")

FIG_QUESTION = "Which recorded FIG-01 findings need reconciliation before the next review?"
FIG_SUMMARY = "FIG-01 draft: pathology and imaging findings recorded; margin state pending; no interpretation made."

INVENTORY_KNOWN = dict(
    location_state="known", location_value="Freezer FIG-A, slot 7",
    quantity_state="known", quantity_value="3 sections remaining (fictional count)",
    custody_state="known", custody_value="Synthetic biobank, FIG site",
    consent_state="unknown", consent_value=None,
    rights_state="unknown", rights_value=None)

LEDGER_TABLES = (
    "cases", "source_versions", "assertions", "questions", "snapshots",
    "snapshot_sources", "review_events", "quarantine", "events",
    "biological_assets", "biological_inventory_assertions",
)


def _ledger_digest(store):
    digest = {}
    for table in LEDGER_TABLES:
        rows = store.db.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        digest[table] = hashlib.sha256(
            repr([tuple(row) for row in rows]).encode()).hexdigest()
    return digest


def _seed_fig01(store):
    """Fresh fictional FIG-01 ledger: three sources, one question, one draft, one asset."""
    store.add_case("CASE-FIG-01", "Fictional case FIG-01")
    path = store.import_report("CASE-FIG-01", FIG_PATH)
    img = store.import_report("CASE-FIG-01", FIG_IMG)
    img2 = store.import_report("CASE-FIG-01", FIG_IMG2)
    question_id = store.add_question("CASE-FIG-01", FIG_QUESTION)
    snapshot_id = store.create_snapshot(
        "CASE-FIG-01", question_id, FIG_SUMMARY, [path["source_id"]])
    asset_pk = store.add_biological_asset(
        "CASE-FIG-01", "BLOCK-FIG-A", "ffpe_block", "EPISODE-FIG-A",
        "2026-05-03", path["source_id"], specimen_state="recorded",
        specimen_id="SPECIMEN-FIG-A")
    assertion_id = store.add_inventory_assertion(
        "CASE-FIG-01", asset_pk, path["source_id"],
        "Synthetic registrar FIG", **INVENTORY_KNOWN)
    return {"path": path, "img": img, "img2": img2, "question_id": question_id,
            "snapshot_id": snapshot_id, "asset_pk": asset_pk,
            "assertion_id": assertion_id}


class EnrichmentProjectionTests(unittest.TestCase):
    def test_every_enrichment_fact_resolves_to_source_anchor(self):
        store = CaseStore(":memory:")
        ids = _seed_fig01(store)
        source_ids = {row[0] for row in store.db.execute(
            "SELECT id FROM source_versions WHERE case_id='CASE-FIG-01'").fetchall()}
        anchors = {(row[0], row[1]) for row in store.db.execute(
            "SELECT source_version_id,source_line FROM assertions WHERE case_id='CASE-FIG-01'").fetchall()}

        visits = case_visits(store, "CASE-FIG-01")
        for group in visits["visits"]:
            for source in group["sources"]:
                self.assertIn(source["source_id"], source_ids)
            for item in group["assertions"]:
                self.assertIn((item["source_version_id"], item["source_line"]), anchors)
            for snap in group["snapshots"]:
                row = store.db.execute(
                    "SELECT state FROM snapshots WHERE id=?", (snap["snapshot_id"],)).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(snap["state"], row["state"])
            for question in group["questions"]:
                row = store.db.execute(
                    "SELECT state FROM questions WHERE id=?", (question["question_id"],)).fetchone()
                self.assertIsNotNone(row)

        journey = case_journey_stages(store, "CASE-FIG-01")
        by_stage = {stage["stage"]: stage for stage in journey["stages"]}
        for source_id in by_stage["ready_to_define_question"]["supporting_facts"]["current_source_ids"]:
            self.assertIn(source_id, source_ids)
        self.assertIn(ids["question_id"],
                      by_stage["under_review"]["supporting_facts"]["open_question_ids"])
        self.assertIn(ids["snapshot_id"],
                      by_stage["under_review"]["supporting_facts"]["draft_snapshot_ids"])
        for event in journey["stage_evidence_events"]:
            row = store.db.execute(
                "SELECT kind FROM events WHERE id=?", (event["event_id"],)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(event["kind"], row["kind"])

        biology = case_biological_context(store, "CASE-FIG-01")
        asset = biology["assets"][0]
        self.assertEqual(asset["asset_pk"], ids["asset_pk"])
        self.assertIn(asset["creation_anchor"]["source_version_id"], source_ids)
        stored = store.db.execute(
            "SELECT * FROM biological_inventory_assertions WHERE id=?",
            (ids["assertion_id"],)).fetchone()
        shown = asset["inventory_assertions"][0]
        self.assertEqual(shown["asserted_by"], stored["asserted_by"])
        self.assertEqual(shown["state"], stored["state"])
        for name in ("location", "quantity", "custody", "consent", "rights"):
            self.assertEqual(shown["fields"][name]["state"], stored[name + "_state"])
            self.assertEqual(shown["fields"][name]["value"], stored[name + "_value"])
        self.assertIn(shown["anchor"]["source_version_id"], source_ids)

    def test_enrichments_projection_pure_two_reads_identical(self):
        store = CaseStore(":memory:")
        _seed_fig01(store)
        before = _ledger_digest(store)
        first = (case_visits(store, "CASE-FIG-01"),
                 case_journey_stages(store, "CASE-FIG-01"),
                 case_biological_context(store, "CASE-FIG-01"))
        second = (case_visits(store, "CASE-FIG-01"),
                  case_journey_stages(store, "CASE-FIG-01"),
                  case_biological_context(store, "CASE-FIG-01"))
        self.assertEqual(first, second)
        self.assertEqual(before, _ledger_digest(store))

    def test_amendment_staleness_propagates_to_enrichments(self):
        store = CaseStore(":memory:")
        ids = _seed_fig01(store)
        update = store.import_report("CASE-FIG-01", FIG_PATH_AMENDED)

        visits = case_visits(store, "CASE-FIG-01")
        group = next(item for item in visits["visits"] if item["occurred"] == "2026-05-03")
        stale = next(item for item in group["snapshots"]
                     if item["snapshot_id"] == ids["snapshot_id"])
        self.assertEqual(stale["state"], "stale")
        self.assertEqual(stale["supersession_pointers"], [{
            "superseded_source_id": ids["path"]["source_id"],
            "superseded_by_source_id": update["source_id"],
            "document_id": "PATH-FIG-A",
        }])
        # History preserved: the superseded version stays listed with its pointer.
        historic = next(item for item in group["superseded_versions"]
                        if item["source_id"] == ids["path"]["source_id"])
        self.assertEqual(historic["state"], "superseded")
        self.assertEqual(historic["superseded_by_source_id"], update["source_id"])
        # The superseded version keeps its own original finding states.
        margin = next(item for item in historic["reported_findings"]
                      if item["finding_key"] == "margin-state")
        self.assertEqual(margin["reported_state"], "pending")
        self.assertEqual(visits["ungrouped_history"], [])
        # The untouched occurred date keeps a current, pointer-free view.
        other = next(item for item in visits["visits"] if item["occurred"] == "2026-05-17")
        self.assertTrue(all(source["state"] == "current" for source in other["sources"]))

        journey = case_journey_stages(store, "CASE-FIG-01")
        self.assertEqual(journey["current_stage"], "review_required")
        pointer = next(item for item in journey["stale_investigation_pointers"]
                       if item["snapshot_id"] == ids["snapshot_id"])
        self.assertEqual(pointer["state"], "stale")
        cited = next(item for item in pointer["cited_sources"]
                     if item["source_id"] == ids["path"]["source_id"])
        self.assertEqual(cited["state"], "superseded")
        self.assertEqual(cited["superseded_by_source_id"], update["source_id"])

        biology = case_biological_context(store, "CASE-FIG-01")
        shown = biology["assets"][0]["inventory_assertions"][0]
        self.assertEqual(shown["state"], "stale")
        self.assertEqual(shown["anchor"]["state"], "superseded")
        self.assertEqual(shown["anchor"]["superseded_by_source_id"], update["source_id"])

    def test_enrichments_case_isolated(self):
        store = CaseStore(":memory:")
        _seed_fig01(store)
        store.add_case("CASE-FIG-02", "Fictional case FIG-02")
        store.import_report("CASE-FIG-02", FIG_BETA)
        store.add_question("CASE-FIG-02", "What does the FIG-02 record report?")
        markers = ("FIG-01", "PATH-FIG-A", "IMG-FIG-A", "Lesion Q",
                   "SPECIMEN-FIG-A", "BLOCK-FIG-A", "EPISODE-FIG-A")
        payloads = (case_visits(store, "CASE-FIG-02"),
                    case_journey_stages(store, "CASE-FIG-02"),
                    case_biological_context(store, "CASE-FIG-02"))
        for payload in payloads:
            body = json.dumps(payload)
            for marker in markers:
                self.assertNotIn(marker, body)
        # And the FIG-02 record is genuinely present, so the check is not vacuous.
        self.assertIn("PATH-FIG-B", json.dumps(payloads[0]))

    def test_empty_case_renders_none_recorded_never_invented(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-FIG-EMPTY", "Fictional empty case")
        visits = case_visits(store, "CASE-FIG-EMPTY")
        self.assertEqual(visits["visits"], [])
        self.assertIn("No visits recorded", visits["empty_statement"])
        self.assertEqual(visits["counts"]["sources"], 0)
        journey = case_journey_stages(store, "CASE-FIG-EMPTY")
        self.assertEqual(journey["current_stage"], "pre_first_source")
        self.assertIn("No sources recorded", journey["empty_statement"])
        self.assertEqual(journey["timeline_span"]["entries"], 0)
        self.assertEqual(journey["stage_evidence_events"], [])
        biology = case_biological_context(store, "CASE-FIG-EMPTY")
        self.assertEqual(biology["assets"], [])
        self.assertIn("No biological assets recorded", biology["empty_statement"])
        for payload in (visits, journey, biology):
            self.assertTrue(payload["synthetic"])
            self.assertIn("Fictional synthetic data only", payload["disclaimer"])

    def test_unknown_case_raises_for_all_projections(self):
        store = CaseStore(":memory:")
        for projection in (case_visits, case_journey_stages, case_biological_context):
            with self.assertRaises(InvalidInput) as raised:
                projection(store, "CASE-NOPE")
            self.assertEqual(str(raised.exception), "Unknown case")

    def test_visits_are_date_groupings_of_existing_rows_only(self):
        store = CaseStore(":memory:")
        _seed_fig01(store)
        visits = case_visits(store, "CASE-FIG-01")
        self.assertEqual(visits["projection"], "occurred_date_grouping")
        self.assertEqual(visits["visit_entities"], [])
        self.assertEqual([group["occurred"] for group in visits["visits"]],
                         ["2026-05-03", "2026-05-17"])
        for group in visits["visits"]:
            self.assertEqual(group["kind"], "occurred_date_grouping")
            self.assertFalse(group["creates_entity"])
            self.assertEqual(group["visit_key"], f"occurred:{group['occurred']}")
            self.assertNotIn("visit_id", group)
        # Same occurred date shares one grouping; timeline tiebreaks decide order.
        day = next(item for item in visits["visits"] if item["occurred"] == "2026-05-17")
        self.assertEqual([source["document_id"] for source in day["sources"]],
                         ["IMG-FIG-A", "IMG-FIG-A2"])
        timeline = case_timeline(store, "CASE-FIG-01")
        self.assertEqual(
            [source["source_id"] for group in visits["visits"] for source in group["sources"]],
            [entry["source_id"] for entry in timeline["entries"]])
        self.assertEqual(visits["coverage_gaps"], timeline["gaps"])
        self.assertEqual(visits["occurred_conflicts"], timeline["conflicts"])
        # The drafted question is grouped; a snapshot-less question is not.
        lonely = store.add_question("CASE-FIG-01", "What remains unasked in this FIG-01 record?")
        regrouped = case_visits(store, "CASE-FIG-01")
        self.assertEqual([item["question_id"] for item in regrouped["ungrouped_questions"]], [lonely])
        for group in regrouped["visits"]:
            self.assertNotIn(lonely, [item["question_id"] for item in group["questions"]])

    def test_journey_stages_show_deterministic_rule(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-FIG-STEP", "Fictional stepping case")
        self.assertEqual(case_journey_stages(store, "CASE-FIG-STEP")["current_stage"],
                         "pre_first_source")
        path = store.import_report("CASE-FIG-STEP", _report(
            "CASE-FIG-STEP", "PATH-STEP", "2026-05-03", "2026-05-05",
            [("step-finding", "reported", "Fictional stepping note records one finding.")]))
        self.assertEqual(case_journey_stages(store, "CASE-FIG-STEP")["current_stage"],
                         "ready_to_define_question")
        question_id = store.add_question("CASE-FIG-STEP", "What does the stepping record report?")
        self.assertEqual(case_journey_stages(store, "CASE-FIG-STEP")["current_stage"],
                         "under_review")
        snapshot_id = store.create_snapshot(
            "CASE-FIG-STEP", question_id,
            "Stepping draft: one finding recorded; no interpretation made.",
            [path["source_id"]])
        store.acknowledge_demo_review("CASE-FIG-STEP", snapshot_id, "Synthetic reviewer")
        journey = case_journey_stages(store, "CASE-FIG-STEP")
        self.assertEqual(journey["current_stage"], "reviewed")
        # The rule rides beside the view: name, version, mapping, one match.
        self.assertEqual(journey["rule"]["name"], "b11-journey-stage-rule")
        self.assertEqual(journey["rule"]["version"], 1)
        self.assertEqual(len(journey["rule"]["mapping"]), 5)
        matched = [stage for stage in journey["stages"] if stage["met"]]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["stage"], journey["current_stage"])
        mission = build_patient_mission(store.state("CASE-FIG-STEP"))
        self.assertEqual(journey["workflow_status"], mission["workflow_status"])
        self.assertEqual(journey["workflow_status"], "reviewed_in_demo")
        self.assertEqual(journey["human_stage_tags"], [])
        # An amendment deterministically returns the same case to review_required.
        store.import_report("CASE-FIG-STEP", _report(
            "CASE-FIG-STEP", "PATH-STEP", "2026-05-03", "2026-05-22",
            [("step-finding", "reported", "Fictional stepping note records one finding."),
             ("step-addendum", "pending", "Fictional stepping amendment leaves one item pending.")],
            amends="PATH-STEP@1"))
        again = case_journey_stages(store, "CASE-FIG-STEP")
        self.assertEqual(again["current_stage"], "review_required")
        self.assertEqual(again, case_journey_stages(store, "CASE-FIG-STEP"))

    def test_biological_explanation_computes_no_rollup(self):
        store = CaseStore(":memory:")
        ids = _seed_fig01(store)
        # A second assertion on another source: values must stay separate.
        store.add_inventory_assertion(
            "CASE-FIG-01", ids["asset_pk"], ids["img"]["source_id"],
            "Second synthetic registrar",
            location_state="known", location_value="Freezer FIG-B, slot 1",
            quantity_state="unknown", quantity_value=None,
            custody_state="unknown", custody_value=None,
            consent_state="unknown", consent_value=None,
            rights_state="unknown", rights_value=None)
        biology = case_biological_context(store, "CASE-FIG-01")
        asset = biology["assets"][0]
        self.assertEqual(len(asset["inventory_assertions"]), 2)
        # No merged field exists at asset or payload level.
        for forbidden in ("rollup", "summary", "current_location", "current_quantity",
                          "current_custody", "current_consent", "current_rights",
                          "merged", "latest_value"):
            self.assertNotIn(forbidden, json.dumps(asset).lower())
            self.assertNotIn(forbidden, asset)
        first, second = asset["inventory_assertions"]
        self.assertEqual(first["fields"]["location"]["value"], "Freezer FIG-A, slot 7")
        self.assertEqual(second["fields"]["location"]["value"], "Freezer FIG-B, slot 1")
        self.assertEqual(first["asserted_by"], "Synthetic registrar FIG")
        self.assertEqual(second["asserted_by"], "Second synthetic registrar")
        self.assertNotEqual(first["anchor"]["source_version_id"],
                            second["anchor"]["source_version_id"])
        self.assertIn("no assertion values are merged", biology["counts"]["note"])

    def test_explanation_hypotheses_labeled_pending_with_guard(self):
        store = CaseStore(":memory:")
        _seed_fig01(store)
        biology = case_biological_context(store, "CASE-FIG-01")
        # This descriptive view offers no interpretive sentences at all; the
        # contract a future interpretive sentence must satisfy rides along.
        self.assertEqual(biology["interpretive_claims"], [])
        self.assertEqual(biology["labeling_contract"]["kind"], "hypothesis")
        self.assertEqual(biology["labeling_contract"]["review_state"], "pending")
        descriptions = [asset["description"] for asset in biology["assets"]]
        self.assertTrue(descriptions)
        for text in descriptions:
            for pattern in GUARD_PATTERNS:
                self.assertIsNone(pattern.search(text))
        # Claim-bearing text stays clear of inference vocabulary. Guardrail
        # fields (disclaimer, notes, contract) are excluded: like the mission
        # guardrails, they name the forbidden inferences only to disclaim them.
        claim_text = " ".join(descriptions)
        for word in ("response", "progression", "eligib", "efficacy",
                     "recommend", "prescri", "dosage", "treatment"):
            self.assertNotIn(word, claim_text.lower())
        visits = case_visits(store, "CASE-FIG-01")
        journey = case_journey_stages(store, "CASE-FIG-01")
        for payload in (visits, journey):
            body = json.dumps({key: value for key, value in payload.items()
                               if key not in ("disclaimer", "not_built_note")}).lower()
            for word in ("response", "progression", "eligib", "efficacy"):
                self.assertNotIn(word, body)


class EnrichmentHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "enrichments-http.sqlite")
        store = CaseStore(cls.path)
        try:
            store.add_case("CASE-FIG-01", "Fictional case FIG-01")
            store.import_report("CASE-FIG-01", FIG_PATH)
        finally:
            store.close()
        bound_handler = type(
            "BoundEnrichmentsHandlerForTest", (Handler,), {"db_path": cls.path}
        )
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_unknown_case_still_422_in_enrichment_routes(self):
        for route in ("visits", "journey-stages", "biological-context"):
            status, error = self.request(f"/api/cases/CASE-UNKNOWN/{route}")
            self.assertEqual(status, 422, route)
            self.assertEqual(error["error"], "Unknown case", route)

    def test_enrichment_routes_expose_read_only_views(self):
        status, visits = self.request("/api/cases/CASE-FIG-01/visits")
        self.assertEqual(status, 200)
        self.assertEqual(visits["case_id"], "CASE-FIG-01")
        self.assertEqual(len(visits["visits"]), 1)
        status, journey = self.request("/api/cases/CASE-FIG-01/journey-stages")
        self.assertEqual(status, 200)
        self.assertEqual(journey["case_id"], "CASE-FIG-01")
        self.assertEqual(journey["current_stage"], "ready_to_define_question")
        status, biology = self.request("/api/cases/CASE-FIG-01/biological-context")
        self.assertEqual(status, 200)
        self.assertEqual(biology["case_id"], "CASE-FIG-01")
        self.assertIn("No biological assets recorded", biology["empty_statement"])


if __name__ == "__main__":
    unittest.main()
