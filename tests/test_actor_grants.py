"""B-01 fictional-actor grants for the synthetic case workspace.

Fictional actors/cases only (FICTIONAL-NAVIGATOR-*, CASE-FIG-01/02). Every
test imports freshly authored fictional bytes (never fixtures presented as
imports), provisions grants through the store API, and exercises the HTTP
gate. UNVERIFIED: the builder cannot execute code; the reviewer runs these.
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
from open_intelligence.__main__ import (
    FICTIONAL_ACTOR_HEADER,
    FICTIONAL_ACTOR_PURPOSE,
    GRANT_DENIAL_MESSAGE,
    Handler,
)
from open_intelligence.mission import build_patient_mission
from open_intelligence.timeline import case_timeline

ACTOR = "FICTIONAL-NAVIGATOR-A"
ACTOR_B = "FICTIONAL-NAVIGATOR-B"
ACTOR_C = "FICTIONAL-NAVIGATOR-C"
UNKNOWN_ACTOR = "FICTIONAL-NOBODY"
CASE_A = "CASE-FIG-01"
CASE_B = "CASE-FIG-02"
LABEL_A = "Fictional case Fig01"
LABEL_B = "Fictional case Fig02"
PURPOSE = FICTIONAL_ACTOR_PURPOSE

FIG01_FINDINGS = (
    ("fig01-rosettes", "reported",
     "Fictional Fig01 tissue shows imaginary rosettes under fictional stain seven."),
    ("fig01-marker", "not-reported",
     "Fictional Fig01 marker was not tested in this specimen."),
)
FIG02_FINDINGS = (
    ("fig02-whorls", "reported",
     "Fictional Fig02 sample shows spindle stromal whorls of unknown meaning."),
    ("fig02-marker", "not-reported",
     "Fictional Fig02 marker was not tested in this specimen."),
)
FIG01_MARKERS = ("FIG01-PATH", "imaginary rosettes", "fig01-rosettes",
                 "fig01-marker", LABEL_A, "FIG01-SPECIMEN")
FIG02_MARKERS = ("FIG02-PATH", "spindle stromal whorls", "fig02-whorls",
                 "fig02-marker", LABEL_B, "FIG02-SPECIMEN")


def fig_report(case_id, document_id, findings, specimen):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {case_id}",
             f"Document: {document_id}", "Type: pathology",
             "Event-Date: 2026-07-01", "Issued-At: 2026-07-03",
             f"Specimen: {specimen}"]
    for key, state, quote in findings:
        lines.append(f"Finding: {key}|{state}|{quote}")
    return ("\n".join(lines) + "\n").encode("utf-8")


class ActorGrantHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "grants.sqlite")
        self.store = CaseStore(self.db_path)
        self.store.add_case(CASE_A, LABEL_A)
        self.store.add_case(CASE_B, LABEL_B)
        self.fig01_bytes = fig_report(CASE_A, "FIG01-PATH", FIG01_FINDINGS, "FIG01-SPECIMEN")
        self.fig02_bytes = fig_report(CASE_B, "FIG02-PATH", FIG02_FINDINGS, "FIG02-SPECIMEN")
        self.srcA = self.store.import_report(CASE_A, self.fig01_bytes)["source_id"]
        self.srcB = self.store.import_report(CASE_B, self.fig02_bytes)["source_id"]
        self.qA = self.store.add_question(CASE_A, "Which fictional Fig01 findings need a second look?")
        self.sA = self.store.create_snapshot(
            CASE_A, self.qA,
            "Fig01 draft notes the imaginary rosettes for a later fictional review.",
            [self.srcA])
        self.qB = self.store.add_question(CASE_B, "Which fictional Fig02 findings need a second look?")
        self.sB = self.store.create_snapshot(
            CASE_B, self.qB,
            "Fig02 draft notes the spindle stromal whorls for a later fictional review.",
            [self.srcB])
        self.grantA = self.store.create_grant(
            ACTOR, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        bound = type("BoundHandlerForGrantTests", (Handler,), {"db_path": self.db_path})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), bound)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.store.close()
        self.tmp.cleanup()

    def request(self, path, data=None, actor=ACTOR):
        headers = {}
        if actor is not None:
            headers[FICTIONAL_ACTOR_HEADER] = actor
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        req = Request(f"http://127.0.0.1:{self.port}{path}",
                      data=None if data is None else json.dumps(data).encode(),
                      headers=headers)
        try:
            with urlopen(req, timeout=5) as response:
                raw = response.read()
                if "json" in (response.headers.get("Content-Type") or ""):
                    return response.status, json.loads(raw)
                return response.status, raw.decode("utf-8")
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def assertDenial(self, status, body):  # noqa: N802
        self.assertEqual(status, 403)
        self.assertEqual(body, {"error": GRANT_DENIAL_MESSAGE})
        self.assertEqual(set(body), {"error"})

    def test_grant_allows_own_case_state_mission_timeline_export(self):
        status, state = self.request(f"/api/cases/{CASE_A}/state")
        self.assertEqual(status, 200)
        # Only the grant check is added: payload shapes are byte-identical
        # to the ungated store projections.
        self.assertEqual(state, self.store.state(CASE_A))
        status, mission = self.request(f"/api/cases/{CASE_A}/mission")
        self.assertEqual(status, 200)
        self.assertEqual(mission, build_patient_mission(self.store.state(CASE_A)))
        status, timeline = self.request(f"/api/cases/{CASE_A}/timeline")
        self.assertEqual(status, 200)
        self.assertEqual(timeline, case_timeline(self.store, CASE_A))
        status, exported = self.request(f"/api/cases/{CASE_A}/snapshots/{self.sA}/export")
        self.assertEqual(status, 200)
        self.assertEqual(exported, self.store.export_markdown(CASE_A, self.sA))

    def test_cross_case_read_denied_with_no_source_bytes_leaked(self):
        get_routes = ["state", "mission", "timeline", "changes-since-review",
                      "investigations", "investigations/1", "discovery",
                      f"sources/{self.srcB}", f"snapshots/{self.sB}/export",
                      "options"]
        for suffix in get_routes:
            with self.subTest(route=suffix):
                status, body = self.request(f"/api/cases/{CASE_B}/{suffix}")
                self.assertDenial(status, body)
                dumped = json.dumps(body)
                for marker in FIG02_MARKERS:
                    self.assertNotIn(marker, dumped)
        post_routes = ["imports", "questions", "evidence-assessments",
                       "discovery-links", "broker-links", "biological-assets",
                       "snapshots", "options", "investigations"]
        for suffix in post_routes:
            with self.subTest(route=suffix):
                status, body = self.request(f"/api/cases/{CASE_B}/{suffix}", {})
                self.assertDenial(status, body)
                dumped = json.dumps(body)
                for marker in FIG02_MARKERS:
                    self.assertNotIn(marker, dumped)

    def test_unknown_actor_denied_on_all_case_routes(self):
        get_routes = ["state", "mission", "timeline", "changes-since-review",
                      "investigations", "investigations/1", "discovery",
                      f"sources/{self.srcA}", f"snapshots/{self.sA}/export",
                      "options"]
        post_routes = ["imports", "questions", "evidence-assessments",
                       "discovery-links", "broker-links", "broker-links/1/review",
                       "biological-assets",
                       "biological-assets/1/inventory-assertions", "snapshots",
                       "snapshots/1/review", "options", "options/1/dependencies",
                       "options/1/tasks", "tasks/1/status", "options/1/threats",
                       "options/1/review", "investigations"]
        actors = [None, UNKNOWN_ACTOR, "not-valid!", ""]
        for actor in actors:
            for suffix in get_routes:
                with self.subTest(actor=actor, route=suffix):
                    status, body = self.request(
                        f"/api/cases/{CASE_A}/{suffix}", actor=actor)
                    self.assertDenial(status, body)
            for suffix in post_routes:
                with self.subTest(actor=actor, route=suffix):
                    status, body = self.request(
                        f"/api/cases/{CASE_A}/{suffix}", {}, actor=actor)
                    self.assertDenial(status, body)
        # A malformed body is still denied (never validated past the gate).
        conn_body = b"not json"
        req = Request(f"http://127.0.0.1:{self.port}/api/cases/{CASE_A}/questions",
                      data=conn_body, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=5) as response:
                status, body = response.status, json.loads(response.read())
        except HTTPError as err:
            status, body = err.code, json.loads(err.read())
        self.assertDenial(status, body)

    def test_revoked_grant_denies_future_reads_but_history_remains(self):
        self.store.acknowledge_demo_review(CASE_A, self.sA, "Fictional demo reviewer")
        status, _ = self.request(f"/api/cases/{CASE_A}/state")
        self.assertEqual(status, 200)
        events_before = self.store.state(CASE_A)["events"]
        self.assertTrue(any(e["kind"] == "demo_review_acknowledged" for e in events_before))
        export_before = self.store.export_markdown(CASE_A, self.sA)
        outcome = self.store.revoke_grant(
            self.grantA, "Fictional actor no longer supports this synthetic case in the demo.")
        self.assertEqual(outcome["result"], "revoked")
        status, body = self.request(f"/api/cases/{CASE_A}/state")
        self.assertDenial(status, body)
        status, body = self.request(f"/api/cases/{CASE_A}/snapshots/{self.sA}/export")
        self.assertDenial(status, body)
        # History is preserved, never deleted: every prior event row is still
        # present with identical bytes, and a still-authorized actor keeps
        # querying the reviewed snapshot and its export.
        self.store.create_grant(ACTOR_B, CASE_A, PURPOSE, "2020-01-01", "2999-12-31")
        status, state = self.request(f"/api/cases/{CASE_A}/state", actor=ACTOR_B)
        self.assertEqual(status, 200)
        for event in events_before:
            self.assertIn(event, state["events"])
        snap = next(s for s in state["snapshots"] if s["id"] == self.sA)
        self.assertEqual(snap["state"], "reviewed_in_demo")
        self.assertEqual(snap["reviewer_label"], "Fictional demo reviewer")
        self.assertEqual(self.store.export_markdown(CASE_A, self.sA), export_before)

    def test_expired_grant_denied(self):
        self.store.create_grant(ACTOR_B, CASE_A, PURPOSE, "1999-01-01", "2000-01-01")
        status, body = self.request(f"/api/cases/{CASE_A}/state", actor=ACTOR_B)
        self.assertDenial(status, body)
        # The window is two-sided like the AuthorizationReceipt retrieval
        # window: a grant that starts in the future is not active either.
        self.store.create_grant(ACTOR_C, CASE_A, PURPOSE, "2999-01-01", "2999-12-31")
        status, body = self.request(f"/api/cases/{CASE_A}/state", actor=ACTOR_C)
        self.assertDenial(status, body)

    def test_purpose_outside_grant_denied(self):
        self.store.create_grant(ACTOR_B, CASE_A, "care-coordination", "2020-01-01", "2999-12-31")
        status, body = self.request(f"/api/cases/{CASE_A}/state", actor=ACTOR_B)
        self.assertDenial(status, body)
        # No wildcard grants in this slice.
        for bad in ("*", "", " ", "ALL", "Individual-Access", "individual access"):
            with self.subTest(purpose=bad):
                with self.assertRaises(InvalidInput):
                    self.store.create_grant(ACTOR_C, CASE_A, bad, "2020-01-01", "2999-12-31")

    def test_cases_list_filtered_to_granted_cases_only(self):
        status, cases = self.request("/api/cases")
        self.assertEqual(status, 200)
        self.assertEqual([c["case_id"] for c in cases], [CASE_A])
        self.assertEqual(set(cases[0]), {"case_id", "label", "synthetic"})
        self.assertEqual(cases[0]["label"], LABEL_A)
        # Authenticated-but-grantless: 200 with an empty list, never 403.
        status, cases = self.request("/api/cases", actor=UNKNOWN_ACTOR)
        self.assertEqual(status, 200)
        self.assertEqual(cases, [])
        # Missing actor: denied, same fixed shape.
        status, body = self.request("/api/cases", actor=None)
        self.assertDenial(status, body)
        # A second grant widens this actor's list only.
        self.store.create_grant(ACTOR, CASE_B, PURPOSE, "2020-01-01", "2999-12-31")
        status, cases = self.request("/api/cases")
        self.assertEqual(status, 200)
        self.assertEqual([c["case_id"] for c in cases], [CASE_A, CASE_B])

    def test_access_log_has_actor_case_route_result_and_no_source_text(self):
        status, _ = self.request(f"/api/cases/{CASE_A}/state")
        self.assertEqual(status, 200)
        status, _ = self.request(
            f"/api/cases/{CASE_A}/questions",
            {"question": "Which fictional Fig01 marker needs review next?"})
        self.assertEqual(status, 201)
        status, _ = self.request(f"/api/cases/{CASE_B}/state")
        self.assertEqual(status, 403)
        status, _ = self.request(f"/api/cases/{CASE_A}/state", actor=UNKNOWN_ACTOR)
        self.assertEqual(status, 403)
        status, _ = self.request(f"/api/cases/{CASE_A}/state", actor=None)
        self.assertEqual(status, 403)
        rows_a = self.store.access_log(CASE_A)
        rows_b = self.store.access_log(CASE_B)
        self.assertTrue(rows_a)
        self.assertTrue(rows_b)
        for row in rows_a + rows_b:
            self.assertEqual(set(row),
                             {"id", "actor", "case_id", "route", "result", "occurred_at"})
            self.assertIn(row["result"], ("allowed", "denied"))
            self.assertTrue(row["route"].startswith("/api/cases/"))
        results_a = {r["result"] for r in rows_a}
        self.assertIn("allowed", results_a)
        self.assertIn("denied", results_a)
        actors_a = {r["actor"] for r in rows_a}
        self.assertIn(ACTOR, actors_a)
        self.assertIn(UNKNOWN_ACTOR, actors_a)
        self.assertIn("missing", actors_a)
        dumped = json.dumps(rows_a + rows_b)
        for marker in FIG01_MARKERS + FIG02_MARKERS:
            self.assertNotIn(marker, dumped)

    def test_unknown_case_still_422_and_quarantine_isolation_unchanged(self):
        events_b_before = len(self.store.state(CASE_B)["events"])
        for actor in (ACTOR, UNKNOWN_ACTOR, None):
            with self.subTest(actor=actor):
                status, body = self.request("/api/cases/CASE-NOPE/state", actor=actor)
                self.assertEqual(status, 422)
                self.assertEqual(body, {"error": "Unknown case"})
        # Wrong-subject bytes are quarantined for authorized callers, exactly
        # as today; a repeat delivery keeps one receipt (duplicate).
        status, first = self.request(
            f"/api/cases/{CASE_A}/imports", {"text": self.fig02_bytes.decode("utf-8")})
        self.assertEqual(status, 200)
        self.assertEqual(first["result"], "quarantined")
        self.assertEqual(first["reason"], "patient_mismatch")
        status, again = self.request(
            f"/api/cases/{CASE_A}/imports", {"text": self.fig02_bytes.decode("utf-8")})
        self.assertEqual(status, 200)
        self.assertEqual(again["result"], "quarantined")
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["quarantine_id"], first["quarantine_id"])
        # Same-bytes idempotent import of the case's own bytes.
        status, duplicate = self.request(
            f"/api/cases/{CASE_A}/imports", {"text": self.fig01_bytes.decode("utf-8")})
        self.assertEqual(status, 200)
        self.assertEqual(duplicate["result"], "duplicate")
        # Per-case isolation: CASE-FIG-02 is untouched by CASE-FIG-01's
        # quarantine traffic — one source, no quarantines, no new events.
        state_b = self.store.state(CASE_B)
        self.assertEqual(len(state_b["sources"]), 1)
        self.assertEqual(state_b["quarantines"], [])
        self.assertEqual(len(state_b["events"]), events_b_before)
        state_a = self.store.state(CASE_A)
        self.assertEqual(len(state_a["quarantines"]), 1)
        self.assertEqual(state_a["quarantines"][0]["declared_patient_id"], CASE_B)


if __name__ == "__main__":
    unittest.main()
