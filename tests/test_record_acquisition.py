"""Synthetic record-acquisition persistence and real loopback HTTP acceptance."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.record_acquisition import RecordAcquisition
from open_intelligence.workspace_host import workspace_handler

ORIGINAL = ("OI-SYNTHETIC-REPORT/1\nPatient: CASE-FIRST\nDocument: IMG-ONE\n"
            "Type: imaging\nEvent-Date: 2026-01-08\nIssued-At: 2026-01-09\n"
            "Finding: observed|pending|Fictional imaging description is pending.\n").encode()
AMENDED = ("OI-SYNTHETIC-REPORT/1\nPatient: CASE-FIRST\nDocument: IMG-ONE\n"
           "Type: imaging\nEvent-Date: 2026-01-08\nIssued-At: 2026-01-10\n"
           "Amends: IMG-ONE@1\n"
           "Finding: observed|reported|Revised fictional image narrative.\n").encode()


class RecordAcquisitionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "records.sqlite")
        self.store = CaseStore(self.db)
        self.addCleanup(lambda: self.store.close())
        self.store.add_case("CASE-FIRST", "Fictional first case")
        self.store.add_case("CASE-OTHER", "Fictional other case")
        self.queue = RecordAcquisition(self.store)

    def make_request(self, key="REQUEST-FIRST-001", kind="imaging"):
        return self.queue.create("CASE-FIRST", key, kind,
                                 "Request fictional radiology report",
                                 "Fictional imaging center")

    def test_durable_idempotent_request_events_and_case_isolation(self):
        first = self.make_request()
        self.assertFalse(first["duplicate"])
        self.assertEqual(self.make_request()["request_id"], first["request_id"])
        self.assertTrue(self.make_request()["duplicate"])
        with self.assertRaises(InvalidInput):
            self.queue.create("CASE-FIRST", "REQUEST-FIRST-001", "laboratory",
                              "Request fictional radiology report", "Fictional imaging center")
        requests = self.queue.list("CASE-FIRST")["requests"]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["receipt_state"], "awaiting_record")
        self.assertEqual(self.queue.list("CASE-OTHER")["requests"], [])
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM events WHERE kind='record_acquisition_requested'"
        ).fetchone()[0], 1)
        self.store.close()
        self.store = CaseStore(self.db)
        self.queue = RecordAcquisition(self.store)
        self.assertEqual(self.queue.list("CASE-FIRST")["requests"][0]["id"], first["request_id"])

    def test_receipt_rejects_wrong_subject_kind_and_superseded_source(self):
        request_id = self.make_request()["request_id"]
        other = self.store.import_report(
            "CASE-OTHER", ORIGINAL.decode().replace("CASE-FIRST", "CASE-OTHER").encode()
        )["source_id"]
        source = self.store.import_report("CASE-FIRST", ORIGINAL)["source_id"]
        with self.assertRaises(InvalidInput):
            self.queue.receive("CASE-FIRST", request_id, other)
        with self.assertRaises(InvalidInput):
            self.queue.receive("CASE-OTHER", request_id, source)
        lab = self.queue.create("CASE-FIRST", "REQUEST-LAB-001", "laboratory",
                                "Fictional lab", "Fictional clinic")["request_id"]
        with self.assertRaises(InvalidInput):
            self.queue.receive("CASE-FIRST", lab, source)
        self.assertFalse(self.queue.receive("CASE-FIRST", request_id, source)["duplicate"])
        self.assertTrue(self.queue.receive("CASE-FIRST", request_id, source)["duplicate"])
        request = self.queue.list("CASE-FIRST")["requests"][0]
        self.assertEqual(request["receipt_state"], "source_current")
        self.assertEqual(request["source_sha256"], self.store.state("CASE-FIRST")["sources"][0]["sha256"])
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM events WHERE kind='record_acquisition_source_linked'"
        ).fetchone()[0], 1)

    def test_amendment_requires_explicit_reconciliation_and_preserves_history(self):
        request_id = self.make_request()["request_id"]
        old = self.store.import_report("CASE-FIRST", ORIGINAL)["source_id"]
        self.queue.receive("CASE-FIRST", request_id, old)
        new = self.store.import_report("CASE-FIRST", AMENDED)["source_id"]
        prior = self.queue.list("CASE-FIRST")["requests"][0]
        self.assertEqual(prior["received_source_id"], old)
        self.assertEqual(prior["receipt_state"], "source_superseded_reconciliation_needed")
        with self.assertRaises(InvalidInput):
            self.queue.receive("CASE-FIRST", request_id, old)
        self.queue.receive("CASE-FIRST", request_id, new)
        latest = self.queue.list("CASE-FIRST")["requests"][0]
        self.assertEqual(latest["received_source_id"], new)
        self.assertEqual(latest["receipt_state"], "source_current")
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM events WHERE kind='record_acquisition_source_linked'"
        ).fetchone()[0], 2)
        self.assertIn('"replaced_source_version_id": '+str(old),
                      self.store.db.execute(
                          "SELECT details FROM events WHERE kind='record_acquisition_source_linked' ORDER BY id DESC LIMIT 1"
                      ).fetchone()[0])

    def test_cancel_is_audited_and_cannot_erase_received_source(self):
        a = self.make_request()["request_id"]
        self.queue.cancel("CASE-FIRST", a, "No longer needed for fictional exercise")
        self.assertEqual(self.queue.list("CASE-FIRST")["requests"][0]["receipt_state"], "request_cancelled")
        self.assertTrue(self.queue.cancel("CASE-FIRST", a, "Already cancelled")["duplicate"])
        with self.assertRaises(InvalidInput):
            self.queue.receive("CASE-FIRST", a, 123)
        received = self.queue.create("CASE-FIRST", "REQUEST-SECOND-001", "imaging",
                                    "Another fictional report", "Fictional institution")["request_id"]
        sid = self.store.import_report("CASE-FIRST", ORIGINAL)["source_id"]
        self.queue.receive("CASE-FIRST", received, sid)
        with self.assertRaises(InvalidInput):
            self.queue.cancel("CASE-FIRST", received, "try to erase")
        self.assertEqual(self.queue.list("CASE-OTHER")["requests"], [])

    def test_invalid_and_cross_case_inputs_do_not_change_case_state(self):
        for bad in (None, 1, [], {}, "clinical"):
            with self.subTest(kind=bad):
                with self.assertRaises(InvalidInput):
                    self.queue.create("CASE-FIRST", "REQUEST-BAD-INPUT", bad, "report", "institution")
        for bad in (True, False, 0, -1, "1", 1.0, None):
            with self.subTest(id=bad):
                with self.assertRaises(InvalidInput):
                    self.queue.cancel("CASE-FIRST", bad, "No longer needed")
        self.assertEqual(self.queue.list("CASE-FIRST")["requests"], [])


class RecordAcquisitionHttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "records.sqlite")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), workspace_handler(self.db))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = "http://127.0.0.1:" + str(self.server.server_port)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def api(self, route, body=None):
        req = Request(self.url+route,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={"Content-Type": "application/json"})
        try:
            response = urlopen(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read().decode())

    def test_create_link_amend_reconcile_persist_and_no_external_actions(self):
        self.assertEqual(self.api("/api/cases", {"case_id": "CASE-FIRST", "label": "Fictional"})[0], 201)
        route = "/api/cases/CASE-FIRST/record-requests"
        _, created = self.api(route, {"request_key": "REQUEST-FIRST-001", "kind": "imaging",
                                      "label": "Get fictional image report", "organization": "Fictional center"})
        ident = created["request_id"]
        self.assertEqual(self.api(route)[1]["requests"][0]["status"], "requested")
        _, source = self.api("/api/cases/CASE-FIRST/imports", {"text": ORIGINAL.decode()})
        self.assertEqual(source["result"], "imported")
        received = route+"/"+str(ident)+"/receive"
        self.assertEqual(self.api(received, {"source_version_id": source["source_id"]})[0], 200)
        self.assertEqual(self.api(route)[1]["requests"][0]["receipt_state"], "source_current")
        _, changed = self.api("/api/cases/CASE-FIRST/imports", {"text": AMENDED.decode()})
        self.assertEqual(self.api(route)[1]["requests"][0]["receipt_state"], "source_superseded_reconciliation_needed")
        self.assertEqual(self.api(received, {"source_version_id": changed["source_id"]})[0], 200)
        self.assertEqual(self.api(route)[1]["requests"][0]["receipt_state"], "source_current")
        self.assertEqual(self.api(received, {"source_version_id": "1"})[0], 422)
        self.assertEqual(self.api(route, {"request_key": "REQUEST-OTHER-002", "kind": "imaging",
                                           "label": "wrong"})[0], 422)
        store = CaseStore(self.db)
        try:
            self.assertEqual(store.db.execute("SELECT count(*) FROM record_requests").fetchone()[0], 1)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
