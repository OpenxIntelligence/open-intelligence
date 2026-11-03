"""Regressions for QA cycle-2 defects fixed on this branch (fictional data only).

Covers QA-11, QA-12, QA-13, QA-15, QA-17. QA-14 (non-reconfirm review
actions silently ignoring snapshot_id) and QA-16 (Patient Mission omitting
option review state) are HELD: QA-14 needs a UI decision (the review form
sends a snapshot_id for every action, so a backend-only rejection changes
live UI submits), and QA-16 is a projection enhancement, not a guard.
The QA cycle-2 adversarial file itself is NOT landed: its QA-14/QA-16
tests still fail by design.
"""

from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from open_intelligence import __main__ as oi_main  # noqa: E402
from open_intelligence.store import CaseStore, InvalidInput  # noqa: E402

REPORT_V1 = (
    "OI-SYNTHETIC-REPORT/1\n"
    "Patient: CASE-QA2\n"
    "Document: QA-DOC2\n"
    "Type: pathology\n"
    "Event-Date: 2026-01-05\n"
    "Issued-At: 2026-01-06\n"
    "Specimen: QA-SPECIMEN2\n"
    "Finding: qa-finding|reported|Fictional QA cycle-2 note for adversarial testing only.\n"
).encode("utf-8")

QUESTION = "Fictional QA cycle-2 question about the test source?"
REVIEWER = "QA Reviewer"
SCOPE = "Fictional QA review scope text here."
OPTION_LABEL = "QA option label"
OPTION_DESC = "Fictional QA option description text."
TASK_LABEL = "QA task"
TASK_OWNER = "QA Owner"
THREAT_DESC = "Fictional QA threat description text."


def _seed_case(store: CaseStore, case_id: str = "CASE-QA2") -> tuple[int, int]:
    store.add_case(case_id, "Fictional QA cycle-2 case")
    report = store.import_report(case_id, REPORT_V1)
    qid = store.add_question(case_id, QUESTION)
    return int(report["source_id"]), int(qid)


def _seed_option(store: CaseStore, case_id: str, qid: int, sid: int) -> tuple[int, int]:
    snap_id = store.create_snapshot(
        case_id, qid, "Fictional QA cycle-2 draft summary text.", [sid])
    opt_id = store.create_option(
        case_id, snap_id, OPTION_LABEL, OPTION_DESC, "unknown")
    return int(snap_id), int(opt_id)


def _reject_option(store: CaseStore, opt_id: int) -> None:
    store.review_option("CASE-QA2", opt_id, REVIEWER, "reject", SCOPE, None)


class TestTerminalOptionGuards(unittest.TestCase):
    def test_add_task_to_rejected_option_raises(self):
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            _, opt_id = _seed_option(store, "CASE-QA2", qid, sid)
            _reject_option(store, opt_id)
            with self.assertRaises(InvalidInput):
                store.add_preparation_task(
                    "CASE-QA2", opt_id, TASK_LABEL, TASK_OWNER, None)
        finally:
            store.close()

    def test_add_threat_to_rejected_option_raises(self):
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            _, opt_id = _seed_option(store, "CASE-QA2", qid, sid)
            _reject_option(store, opt_id)
            with self.assertRaises(InvalidInput):
                store.add_optionality_threat(
                    "CASE-QA2", opt_id, "other", THREAT_DESC, None, "unknown", "")
        finally:
            store.close()


class TestTaskStatusIdStrict(unittest.TestCase):
    def test_boolean_and_string_task_ids_raise(self):
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            _, opt_id = _seed_option(store, "CASE-QA2", qid, sid)
            task_id = store.add_preparation_task(
                "CASE-QA2", opt_id, TASK_LABEL, TASK_OWNER, None)
            self.assertEqual(task_id, 1)
            for bad, target in ((True, "done"), ("1", "in_progress")):
                with self.subTest(task_id=bad):
                    with self.assertRaises(InvalidInput):
                        store.set_preparation_task_status("CASE-QA2", bad, target)
        finally:
            store.close()


class TestUnknownAnchorStrict(unittest.TestCase):
    def test_non_string_unknown_anchor_raises(self):
        store = CaseStore(":memory:")
        try:
            sid, qid = _seed_case(store)
            _, opt_id = _seed_option(store, "CASE-QA2", qid, sid)
            with self.subTest(path="threat"):
                with self.assertRaises(InvalidInput):
                    store.add_optionality_threat(
                        "CASE-QA2", opt_id, "other", THREAT_DESC,
                        None, "unknown", 123)  # type: ignore[arg-type]
            with self.subTest(path="dependency"):
                with self.assertRaises(InvalidInput):
                    store.add_option_dependency(
                        "CASE-QA2", opt_id, "source", source_version_id=sid,
                        deadline_date=None, deadline_basis="unknown",
                        anchor=123)  # type: ignore[arg-type]
        finally:
            store.close()


class TestEmptyPostBodyMessage(unittest.TestCase):
    def test_empty_body_does_not_claim_exceeds_limit(self):
        tmp = tempfile.TemporaryDirectory(prefix="oi-qa2-")
        try:
            db_path = str(Path(tmp.name) / "qa2.sqlite")
            store = CaseStore(db_path)
            try:
                _seed_case(store)
            finally:
                store.close()
            handler = type("QA2BoundHandler", (oi_main.Handler,), {"db_path": db_path})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever,
                                      kwargs={"poll_interval": 0.05}, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    conn.request("POST", "/api/cases", body=b"",
                                 headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 422)
                    message = str(payload.get("error", ""))
                    self.assertNotIn("exceed", message.lower())
                    self.assertTrue(any(word in message.lower()
                                        for word in ("empty", "missing", "required", "length")))
                finally:
                    conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
