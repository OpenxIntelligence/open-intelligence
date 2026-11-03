"""Consolidated case packet export: store, HTTP, and UI-contract tests.

The packet composes existing builders (state, mission, timeline, changes,
options, investigations) and never re-derives their logic. Every assertion
below is falsifiable: it fails when the packet module, route, or UI hook
is absent, and it fails when the packet invents content, leaks across
cases, drops citations, or renders markup as text.
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

from open_intelligence import CaseStore
from open_intelligence.__main__ import Handler, seed
from open_intelligence.changes import changes_since_review
from open_intelligence.investigation import validate_output
from open_intelligence.mission import build_patient_mission
from open_intelligence.store import InvalidInput
from open_intelligence.packet import (
    FICTIONAL_MARKING,
    GENERATED_FROM,
    LIMITATIONS,
    build_case_packet,
    render_packet_text,
)
from open_intelligence.timeline import case_timeline

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"


def report(name: str) -> bytes:
    return (SAMPLE / name).read_bytes()


def seed_alpha(store: CaseStore) -> None:
    store.add_case("CASE-ALPHA", "Fictional Alpha")
    store.add_case("CASE-BETA", "Fictional Beta")
    store.import_report("CASE-ALPHA", report("alpha-pathology-original.txt"))
    store.import_report("CASE-ALPHA", report("alpha-imaging.txt"))
    store.import_report("CASE-BETA", report("beta-pathology.txt"))


class PacketStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "packet.sqlite")
        seed_alpha(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_seeded_packet_reuses_every_builder_with_identical_citations(self):
        qid = self.store.add_question("CASE-ALPHA", "What does the fictional record report?")
        state = self.store.state("CASE-ALPHA")
        source_ids = [s["id"] for s in state["sources"] if s["state"] == "current"]
        sid = self.store.create_snapshot("CASE-ALPHA", qid, "Human draft for packet testing.", source_ids)
        imported = self.store.import_synthetic_evidence(
            b"OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVID-PACKET\n"
            b"Title: Fictional packet evidence example\nIssued-At: 2026-05-10\n"
            b"Rights: original-synthetic\n"
            b"Statement: A fictional statement used only to exercise packet evidence.\n"
        )
        aid = self.store.assess_synthetic_evidence(
            "CASE-ALPHA", qid, imported["evidence_version_id"],
            "context", "limited", "Fictional rationale long enough to pass validation.")
        oid = self.store.create_option(
            "CASE-ALPHA", sid, "Fictional discussion item",
            "A fictional item under discussion, with its uncertainty.", "unknown")
        facts = self.store.investigation_facts("CASE-ALPHA", qid)
        first_source = next(iter(facts["valid_sources"]))
        validated = validate_output(
            {"claims": [{
                "text": "The sources report a fictional finding.",
                "support": "context",
                "citations": [{"type": "source", "id": first_source}],
                "uncertainty": "moderate",
                "limits": "Synthetic only.",
            }], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"],
        )
        validated.model = "recorded-replay"
        validated.mode = "replay"
        inv_id = self.store.save_investigation("CASE-ALPHA", qid, "evidence-summary", validated, "replay")

        state = self.store.state("CASE-ALPHA")
        mission = build_patient_mission(state)
        timeline = case_timeline(self.store, "CASE-ALPHA")
        changes = changes_since_review(self.store, "CASE-ALPHA")
        packet = build_case_packet(self.store, "CASE-ALPHA")

        # Cover block carries identity, fictional marking, origin, and position.
        self.assertEqual(packet["cover"]["case_id"], "CASE-ALPHA")
        self.assertEqual(packet["cover"]["fictional_marking"], FICTIONAL_MARKING)
        self.assertIn("Composed from", packet["cover"]["generated_from"])
        self.assertIn("no re-derivation", packet["cover"]["generated_from"])
        self.assertEqual(packet["cover"]["generated_from"], GENERATED_FROM)
        self.assertIsNotNone(packet["cover"]["report_position"]["as_of_event_id"])
        self.assertEqual(packet["cover"]["report_position"]["source_count"], 2)
        self.assertEqual(packet["cover"]["report_position"]["assertion_count"], 5)

        # Every section reuses its builder output identically, not a copy with edits.
        self.assertEqual(packet["reported_findings"]["items"], mission["what_we_know"])
        self.assertEqual(packet["journey_stage"]["workflow_status"], mission["workflow_status"])
        self.assertEqual(packet["journey_stage"]["where_am_i"], mission["where_am_i"])
        self.assertEqual(packet["follow_ups"]["next_actions"], mission["next_actions"])
        self.assertEqual(packet["follow_ups"]["unresolved"], mission["what_remains_unresolved"])
        self.assertEqual(packet["follow_ups"]["material_changes"], mission["material_changes"])
        self.assertEqual(packet["limitations"]["guardrails"], mission["guardrails"])
        self.assertEqual(packet["timeline"]["entries"], timeline["entries"])
        self.assertEqual(packet["timeline"]["gaps"], timeline["gaps"])
        self.assertEqual(packet["timeline"]["conflicts"], timeline["conflicts"])
        self.assertEqual(packet["timeline"]["history"], timeline["history"])
        self.assertEqual(packet["timeline"]["counts"], timeline["counts"])
        self.assertEqual(packet["timeline"]["disclaimer"], timeline["disclaimer"])
        self.assertEqual(packet["timeline"]["as_of"], timeline["as_of"])
        self.assertEqual(packet["changes_since_review"]["new_sources"], changes["new_sources"])
        self.assertEqual(packet["changes_since_review"]["amendments"], changes["amendments"])
        self.assertEqual(
            packet["changes_since_review"]["stale_investigations"],
            changes["stale_investigations"],
        )
        self.assertEqual(packet["changes_since_review"]["new_questions"], changes["new_questions"])
        self.assertEqual(packet["changes_since_review"]["disclaimer"], changes["disclaimer"])
        self.assertEqual(packet["questions"]["items"], state["questions"])
        self.assertEqual(packet["investigations"]["snapshots"], state["snapshots"])
        self.assertEqual(packet["evidence"]["assessments"], state["evidence_assessments"])
        self.assertEqual(packet["evidence"]["broker_links"], state["broker_links"])
        self.assertEqual(packet["sources"]["items"], state["sources"])
        self.assertEqual(packet["sources"]["quarantines"], state["quarantines"])
        self.assertEqual(packet["activity"]["items"], state["events"])
        self.assertEqual(packet["options"]["items"], state["options"])
        self.assertEqual(packet["options"]["disclaimer"], state["option_disclaimer"])
        self.assertEqual(packet["biological_assets"]["assets"], state["biological_assets"])
        # Non-empty evidence and option sections survive composition.
        self.assertTrue(any(a["id"] == aid for a in packet["evidence"]["assessments"]))
        self.assertTrue(any(o["id"] == oid for o in packet["options"]["items"]))

        # Citations survive composition: source version and line anchors intact.
        by_key = {item["finding_key"]: item for item in packet["reported_findings"]["items"]}
        self.assertEqual(by_key["marker-a"]["source_line"], 9)
        self.assertIsInstance(by_key["marker-a"]["source_version_id"], int)
        self.assertEqual(by_key["marker-a"]["statement"], "Marker A was not tested in this specimen.")
        # Unknowns and pending stay distinct, never collapsed.
        states = {item["finding_key"]: item["state"] for item in packet["reported_findings"]["items"]}
        self.assertEqual(states["marker-a"], "not-reported")
        self.assertEqual(states["margin"], "indeterminate")
        self.assertEqual(states["comparison"], "pending")

        # Human drafts and model hypotheses stay separate with review states.
        snapshots = {s["id"]: s for s in packet["investigations"]["snapshots"]}
        self.assertIn(sid, snapshots)
        self.assertEqual(snapshots[sid]["state"], "draft")
        models = {m["id"]: m for m in packet["investigations"]["model_investigations"]}
        self.assertIn(inv_id, models)
        self.assertEqual(models[inv_id]["kind"], "hypothesis")
        self.assertEqual(models[inv_id]["review_state"], "pending")
        self.assertEqual(models[inv_id]["claims"][0]["kind"], "hypothesis")
        # Evidence review state and option review state survive composition.
        assessments = {a["id"]: a for a in packet["evidence"]["assessments"]}
        self.assertEqual(assessments[aid]["evidence_state"], "current")
        options = {o["id"]: o for o in packet["options"]["items"]}
        self.assertEqual(options[oid]["review_state"], "current")
        text = render_packet_text(packet)
        self.assertIn("EVID-PACKET", text)
        self.assertIn("(current)", text)
        self.assertIn("Fictional discussion item", text)

        # Fictional marking on every page-equivalent block.
        for key in ("cover", "journey_stage", "reported_findings", "timeline",
                    "questions", "investigations", "evidence", "sources",
                    "activity", "changes_since_review", "options", "follow_ups",
                    "biological_assets", "limitations"):
            self.assertEqual(packet[key]["fictional_marking"], FICTIONAL_MARKING, key)

    def test_empty_packet_has_empty_sections_without_invention(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-EMPTY", "Fictional empty")
        packet = build_case_packet(store, "CASE-EMPTY")
        mission = build_patient_mission(store.state("CASE-EMPTY"))

        self.assertEqual(packet["reported_findings"]["items"], [])
        self.assertEqual(packet["questions"]["items"], [])
        self.assertEqual(packet["investigations"]["snapshots"], [])
        self.assertEqual(packet["investigations"]["model_investigations"], [])
        self.assertEqual(packet["timeline"]["entries"], [])
        self.assertEqual(packet["timeline"]["gaps"], [])
        self.assertEqual(packet["timeline"]["conflicts"], [])
        self.assertEqual(packet["timeline"]["history"], [])
        self.assertEqual(packet["changes_since_review"]["counts"],
                         {"new_sources": 0, "amendments": 0,
                          "stale_investigations": 0, "new_questions": 0})
        self.assertEqual(packet["options"]["items"], [])
        self.assertEqual(packet["sources"]["items"], [])
        self.assertEqual(packet["sources"]["quarantines"], [])
        self.assertEqual(packet["evidence"]["assessments"], [])
        self.assertEqual(packet["evidence"]["broker_links"], [])
        self.assertEqual(packet["evidence"]["discovery_links"], [])
        self.assertEqual(packet["biological_assets"]["assets"], [])
        self.assertEqual(packet["biological_assets"]["inventory_assertions"], [])
        # Follow-ups reuse the mission's bounded action (gather_source);
        # nothing beyond the existing builder is invented.
        self.assertEqual(packet["follow_ups"]["next_actions"], mission["next_actions"])
        self.assertEqual(packet["journey_stage"]["workflow_status"], "awaiting_sources")
        rendered = repr(packet)
        for invented in ("Marker A", "31 mm", "PATH-ALPHA", "IMG-ALPHA"):
            self.assertNotIn(invented, rendered)
        store.close()

    def test_case_isolation_holds(self):
        alpha = build_case_packet(self.store, "CASE-ALPHA")
        beta = build_case_packet(self.store, "CASE-BETA")
        alpha_text = repr(alpha)
        beta_text = repr(beta)
        self.assertIn("Marker A was not tested in this specimen.", alpha_text)
        self.assertNotIn("Marker A testing was not assessed for this sample.", alpha_text)
        self.assertIn("Marker A testing was not assessed for this sample.", beta_text)
        self.assertNotIn("Marker A was not tested in this specimen.", beta_text)
        self.assertNotIn("PATH-BETA", alpha_text)
        self.assertNotIn("PATH-ALPHA", beta_text)
        self.assertNotIn("IMG-ALPHA", beta_text)
        beta_source_ids = {s["id"] for s in self.store.state("CASE-BETA")["sources"]}
        for item in beta["reported_findings"]["items"]:
            self.assertIn(item["source_version_id"], beta_source_ids)
        for entry in beta["timeline"]["entries"]:
            self.assertNotEqual(entry["document_id"], "PATH-ALPHA")

    def test_unknown_case_raises_existing_boundary(self):
        with self.assertRaises(InvalidInput) as raised:
            build_case_packet(self.store, "CASE-UNKNOWN")
        self.assertEqual(str(raised.exception), "Unknown case")

    def test_text_rendering_is_plain_with_marking_on_every_block(self):
        packet = build_case_packet(self.store, "CASE-ALPHA")
        text = render_packet_text(packet)
        self.assertTrue(text.endswith("\n"))
        self.assertGreaterEqual(text.count(FICTIONAL_MARKING), 14)
        for header in ("CASE PACKET", "JOURNEY STAGE", "REPORTED FINDINGS",
                       "TIMELINE", "QUESTIONS", "INVESTIGATIONS",
                       "EVIDENCE", "SOURCES", "CHANGES SINCE REVIEW",
                       "OPTIONS", "FOLLOW UPS", "BIOLOGICAL ASSETS",
                       "RECENT ACTIVITY", "LIMITATIONS"):
            self.assertIn(header, text)
        # Plain text: no HTML structure, no JSON envelope, no script hooks.
        for leaked in ("<div", "<span", "<article", "<script", "</div>",
                       "innerHTML", '{"case_id"', '{"cover"'):
            self.assertNotIn(leaked, text)
        self.assertFalse(text.lstrip().startswith("{"))
        # Unknowns and pending preserved as words, not resolved.
        self.assertIn("Unknowns stay unknown", text)
        self.assertIn("Pending stays pending", text)
        self.assertIn("not-reported", text)
        self.assertIn("indeterminate", text)
        self.assertIn("pending", text)

    def test_empty_text_states_emptiness_without_invention(self):
        store = CaseStore(":memory:")
        store.add_case("CASE-EMPTY", "Fictional empty")
        text = render_packet_text(build_case_packet(store, "CASE-EMPTY"))
        self.assertIn("No reported findings yet in this fictional case.", text)
        self.assertIn("No questions recorded in this fictional case.", text)
        self.assertIn("No source documents in this fictional case.", text)
        self.assertIn("No biological assets recorded for this case.", text)
        self.assertIn("BIOLOGICAL ASSETS", text)
        self.assertIn("RECENT ACTIVITY", text)
        for invented in ("Marker A", "PATH-ALPHA", "IMG-ALPHA"):
            self.assertNotIn(invented, text)
        store.close()

    def test_limitations_block_is_explicit(self):
        packet = build_case_packet(self.store, "CASE-ALPHA")
        items = packet["limitations"]["items"]
        self.assertEqual(items, LIMITATIONS)
        joined = " ".join(items)
        self.assertIn("Unknowns stay unknown", joined)
        self.assertIn("Pending stays pending", joined)
        self.assertIn("Hypotheses are separate from facts", joined)
        self.assertIn("Amendments supersede, never delete", joined)
        self.assertTrue(packet["limitations"]["guardrails"])

    def test_amendment_supersedes_without_deleting_history(self):
        state = self.store.state("CASE-ALPHA")
        original = next(s for s in state["sources"] if s["document_id"] == "PATH-ALPHA")
        qid = self.store.add_question("CASE-ALPHA", "What was reported about Marker A?")
        sid = self.store.create_snapshot(
            "CASE-ALPHA", qid, "The original source reports Marker A status.", [original["id"]])
        self.store.acknowledge_demo_review("CASE-ALPHA", sid, "Synthetic reviewer")
        facts = self.store.investigation_facts("CASE-ALPHA", qid)
        first_source = next(iter(facts["valid_sources"]))
        validated = validate_output(
            {"claims": [{
                "text": "The sources report a fictional finding.",
                "support": "context",
                "citations": [{"type": "source", "id": first_source}],
                "uncertainty": "moderate",
                "limits": "Synthetic only.",
            }], "abstentions": []},
            facts["valid_sources"], facts["valid_assessments"],
        )
        validated.model = "recorded-replay"
        validated.mode = "replay"
        inv_id = self.store.save_investigation("CASE-ALPHA", qid, "evidence-summary", validated, "replay")
        amendment = self.store.import_report("CASE-ALPHA", report("alpha-pathology-amended.txt"))
        self.assertEqual(amendment["invalidated_snapshots"], [sid])

        packet = build_case_packet(self.store, "CASE-ALPHA")
        versions = [(s["version"], s["state"]) for s in packet["sources"]["items"]
                    if s["document_id"] == "PATH-ALPHA"]
        self.assertEqual(sorted(versions), [(1, "superseded"), (2, "current")])
        self.assertEqual(packet["timeline"]["counts"]["superseded_versions"], 1)
        self.assertTrue(any(h["document_id"] == "PATH-ALPHA" for h in packet["timeline"]["history"]))
        snapshots = {s["id"]: s for s in packet["investigations"]["snapshots"]}
        self.assertEqual(snapshots[sid]["state"], "stale")
        models = {m["id"]: m for m in packet["investigations"]["model_investigations"]}
        self.assertEqual(models[inv_id]["stale"], 1)
        self.assertEqual(packet["changes_since_review"]["counts"]["amendments"], 1)
        self.assertEqual(packet["changes_since_review"]["counts"]["stale_investigations"], 1)
        self.assertEqual(self.store.state("CASE-BETA")["snapshots"], [])

        text = render_packet_text(packet)
        for expected in ("Superseded history, kept: PATH-ALPHA",
                         "Amendment: PATH-ALPHA version 1 to 2",
                         "Stale investigation", ", stale"):
            self.assertIn(expected, text)


class PacketHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "packet-http.sqlite")
        seed(cls.path)
        bound = type("BoundPacketHandlerForTest", (Handler,), {"db_path": cls.path})
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

    def get_json(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.headers.get_content_type(), json.loads(response.read())
        except HTTPError as error:
            return error.code, error.headers.get_content_type(), json.loads(error.read())

    def get_text(self, path: str):
        request = Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.headers.get_content_type(), response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.headers.get_content_type(), error.read().decode("utf-8")

    def test_json_by_default_contains_packet_cover(self):
        status, ctype, packet = self.get_json("/api/cases/CASE-ALPHA/packet")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/json")
        self.assertEqual(packet["cover"]["case_id"], "CASE-ALPHA")
        self.assertEqual(packet["cover"]["fictional_marking"], FICTIONAL_MARKING)
        self.assertEqual(packet["reported_findings"]["count"], 5)
        self.assertEqual(packet["timeline"]["counts"]["entries"], 2)

    def test_text_format_is_plain_without_markup_leakage(self):
        status, ctype, text = self.get_text("/api/cases/CASE-ALPHA/packet?format=text")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/plain")
        self.assertGreaterEqual(text.count(FICTIONAL_MARKING), 14)
        for leaked in ("<div", "<span", "innerHTML", '{"cover"'):
            self.assertNotIn(leaked, text)
        self.assertFalse(text.lstrip().startswith("{"))
        self.assertIn("CASE-ALPHA", text)
        self.assertIn("LIMITATIONS", text)
        self.assertIn("BIOLOGICAL ASSETS", text)
        self.assertIn("RECENT ACTIVITY", text)

    def test_unknown_case_uses_existing_422_boundary(self):
        status, _, body = self.get_json("/api/cases/CASE-UNKNOWN/packet")
        self.assertEqual(status, 422)
        self.assertEqual(body["error"], "Unknown case")

    def test_http_packet_preserves_case_isolation(self):
        _, _, alpha = self.get_json("/api/cases/CASE-ALPHA/packet")
        _, _, beta = self.get_json("/api/cases/CASE-BETA/packet")
        self.assertIn("Marker A was not tested in this specimen.", repr(alpha))
        self.assertNotIn("Marker A testing was not assessed for this sample.", repr(alpha))
        self.assertIn("Marker A testing was not assessed for this sample.", repr(beta))
        self.assertNotIn("Marker A was not tested in this specimen.", repr(beta))


class PacketUiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        cls.js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")

    def test_packet_section_and_download_buttons_exist(self):
        for token in ('id="packet"', 'id="packet-heading"',
                      'id="packet-download-json"', 'id="packet-download-text"',
                      'id="packet-print"', 'id="packet-status"',
                      'id="packet-summary"', 'href="#packet"',
                      "Download packet (JSON)", "Download packet (text)",
                      "Print packet", "FICTIONAL DEMO DATA"):
            self.assertIn(token, self.html)

    def test_packet_js_uses_guards_clear_lists_and_fictional_labels(self):
        for token in ("downloadPacket", "loadPacketSummary", "renderPacketSummary",
                      "packet-download-json", "packet-download-text", "packet-print",
                      "readyCase()", "requested !== caseId", "requestedCase !== caseId",
                      "clear('packet-summary')", "FICTIONAL DEMO DATA",
                      "Biological assets", "Recent activity", "Limitations"):
            self.assertIn(token, self.js)
        # The packet summary refreshes with the case view, like changes/model lists.
        self.assertIn("loadPacketSummary();", self.js)
        # Packet rendering is textContent-only: no innerHTML in packet functions.
        start = self.js.index("async function downloadPacket")
        end = self.js.index("el('dialog-close')", start)
        packet_code = self.js[start:end]
        self.assertNotIn("innerHTML", packet_code)
        self.assertIn("node('article'", packet_code)
        self.assertIn("pill('FICTIONAL DEMO DATA'", packet_code)

    def test_print_hook_reuses_existing_patterns(self):
        self.assertIn("#packet", self.css)
        self.assertIn("@media print", self.css)
        print_blocks = [m.start() for m in re.finditer(r"@media print", self.css)]
        self.assertGreaterEqual(len(print_blocks), 3)
        tail = self.css[print_blocks[-1]:]
        for token in ("#packet", "#packet .actions", "#packet .pill-warn",
                      "display: none", "border: 2px solid #000"):
            self.assertIn(token, tail)

    def test_packet_markup_reuses_existing_css_classes_only(self):
        allowed = {
            "panel", "panel-head", "eyebrow", "pill", "pill-warn",
            "pill-neutral", "muted", "tiny", "actions", "button",
            "secondary", "subhead", "cards", "source-card", "source-top",
            "source-title", "snapshot-meta", "empty",
        }
        full_section = re.search(r'<section class="panel" id="packet".*?</section>',
                                 self.html, re.DOTALL)
        self.assertIsNotNone(full_section)
        classes = set()
        for match in re.finditer(r'class="([^"]+)"', full_section.group(0)):
            classes.update(match.group(1).split())
        self.assertTrue(classes)
        self.assertEqual(classes - allowed, set())
        start = self.js.index("function renderPacketSummary")
        end = self.js.index("el('packet-download-json')", start)
        js_classes = set()
        for match in re.finditer(r"node\('[a-z]+',[^,]*,\s*'([^']+)'\)", self.js[start:end]):
            js_classes.update(match.group(1).split())
        for match in re.finditer(r"pill\([^,]+,\s*'([^']+)'\)", self.js[start:end]):
            js_classes.update(("pill", *match.group(1).split()))
        self.assertTrue(js_classes)
        self.assertEqual(js_classes - allowed, set())


if __name__ == "__main__":
    unittest.main()
