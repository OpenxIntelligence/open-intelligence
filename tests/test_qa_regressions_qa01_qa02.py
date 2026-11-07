"""Regression tests for QA-01 and QA-02 (QA adversarial sweep, night wave 2026-11-02).

These two tests were authored by the QA domain agent by code-trace inspection
(see docs/qa-defect-register.md in the QA workspace) and verified by the
reviewer: both FAILED on unfixed main (connection break / wrong question
state) and PASS with the fixes in this commit. The remaining 8 QA findings
(QA-03..QA-10) are not fixed here; their failing-first tests stay with the
QA register for follow-up fix cycles and are deliberately NOT included, so
this file never lands red tests.

Fictional data only. Run: PYTHONPATH=src python -m unittest tests.test_qa_regressions_qa01_qa02 -v
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
from open_intelligence.agent_writes import build_investigation_contract  # noqa: E402
from open_intelligence.investigation import ValidatedInvestigation  # noqa: E402
from open_intelligence.store import CaseStore  # noqa: E402

REPORT_V1 = (
    "OI-SYNTHETIC-REPORT/1\n"
    "Patient: CASE-QA1\n"
    "Document: QA-DOC\n"
    "Type: pathology\n"
    "Event-Date: 2026-01-05\n"
    "Issued-At: 2026-01-06\n"
    "Specimen: QA-SPECIMEN\n"
    "Finding: qa-finding|reported|Fictional QA note for adversarial testing only.\n"
).encode("utf-8")

QUESTION = "Fictional QA question about the test source?"


def _seed_case(store: CaseStore, case_id: str = "CASE-QA1") -> tuple[int, int]:
    store.add_case(case_id, "Fictional QA case")
    report = store.import_report(case_id, REPORT_V1)
    qid = store.add_question(case_id, QUESTION)
    return int(report["source_id"]), int(qid)

class TestOptionsSnapshotIdRouteValidation(unittest.TestCase):
    """Suspected defect QA-01 (High): GET /api/cases/<id>/options with a
    non-integer snapshot_id crashes instead of returning 422.

    Trace: src/open_intelligence/__main__.py lines 150-153 call int() on the
    raw query value, but do_GET (lines 187-188) catches only InvalidInput, so
    ValueError escapes the handler. The sibling changes-since-review route
    (lines 159-164) validates with isdigit and raises InvalidInput (422).
    """

    def test_non_integer_snapshot_id_returns_422(self):
        tmp = tempfile.TemporaryDirectory(prefix="oi-qa-")
        try:
            db_path = str(Path(tmp.name) / "qa.sqlite")
            store = CaseStore(db_path)
            try:
                _seed_case(store)
                store.create_grant("FICTIONAL-NAVIGATOR-A", "CASE-QA1",
                                   oi_main.FICTIONAL_ACTOR_PURPOSE,
                                   "2020-01-01", "2999-12-31")
                # W1: the header path is gone; the demo account signs in.
                store.create_account("FICTIONAL-NAVIGATOR-A",
                                     "Fictional demo navigator", "clinician",
                                     "fictional-demo-1")
            finally:
                store.close()
            handler = type("QABoundHandler", (oi_main.Handler,), {"db_path": db_path})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever,
                                      kwargs={"poll_interval": 0.05}, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]

                # Sign in over HTTP; the session cookie replaces the header.
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    conn.request("POST", "/api/auth/sign-in",
                                 body=json.dumps(
                                     {"account_id": "FICTIONAL-NAVIGATOR-A",
                                      "password": "fictional-demo-1"}),
                                 headers={"Content-Type": "application/json",
                                          "Origin": f"http://127.0.0.1:{port}"})
                    signin = conn.getresponse()
                    signin.read()
                    assert signin.status == 200, signin.status
                    cookie = signin.getheader("Set-Cookie").split(";", 1)[0]
                finally:
                    conn.close()

                def get(path: str) -> int:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    try:
                        conn.request("GET", path, headers={"Cookie": cookie})
                        response = conn.getresponse()
                        response.read()
                        return response.status
                    finally:
                        conn.close()

                # Control: the route works without the filter.
                self.assertEqual(get("/api/cases/CASE-QA1/options"), 200)
                # Suspected defect: malformed filter values must be 422, not a crash.
                # (parse_qs drops blank values, so only non-empty non-integers
                # reach int(); "abc" and "1.5" both raise ValueError today.)
                for bad in ("abc", "1.5"):
                    try:
                        status = get(f"/api/cases/CASE-QA1/options?snapshot_id={bad}")
                    except (http.client.HTTPException, OSError) as exc:
                        self.fail(f"snapshot_id={bad!r} broke the connection: {exc!r}")
                    self.assertEqual(status, 422, f"snapshot_id={bad!r}")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)
        finally:
            tmp.cleanup()


class TestAbstainedInvestigationKeepsQuestionOpen(unittest.TestCase):
    """Suspected defect QA-02 (High): saving a model investigation marks the
    question addressed even when the model abstained with zero claims.

    Trace: CaseStore.save_investigation (src/open_intelligence/store.py lines
    2183-2199) unconditionally flips the question to addressed (lines
    2195-2196). Human drafts do not: create_snapshot (lines 2075-2135) leaves
    the question open and only acknowledge_demo_review (line 2152) addresses
    it. An abstention (investigation.py lines 193-195) explicitly states there
    is no answer, and stored investigations are always review_state pending
    (store.py lines 2211-2212), so the question disappears from every open
    list with no reviewed answer and no review path.
    """

    def test_abstained_investigation_leaves_question_open(self):
        store = CaseStore(":memory:")
        try:
            _, qid = _seed_case(store)
            before = store.db.execute(
                "SELECT state FROM questions WHERE id=?", (qid,)).fetchone()["state"]
            self.assertEqual(before, "open")  # control: setup starts open
            abstained = ValidatedInvestigation(
                status="abstained", claims=[],
                abstentions=[{"topic": "Fictional QA topic",
                              "reason": "insufficient_evidence"}],
                dropped=[], model="qa-replay", mode="replay")
            store.save_investigation(
                "CASE-QA1", qid, "evidence-summary", abstained, "replay",
                write_contract=build_investigation_contract(
                    store, "CASE-QA1", qid, "evidence-summary", "qa-replay"))
            after = store.db.execute(
                "SELECT state FROM questions WHERE id=?", (qid,)).fetchone()["state"]
            self.assertEqual(after, "open")
        finally:
            store.close()


