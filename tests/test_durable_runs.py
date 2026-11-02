"""Durable synthetic Composer work: isolated source-bound queue and execution receipts."""
from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler
from open_intelligence.composer import build_composer_context
from open_intelligence.durable_runs import DurableComposerRuns
from open_intelligence.store import CaseStore, InvalidInput


def report(document, event_date, value, qc="passed", amends=None):
    parts = [
        "OI-SYNTHETIC-REPORT/1","Patient: CASE-ALPHA",
        f"Document: {document}","Type: laboratory",
        f"Event-Date: {event_date}",f"Issued-At: {event_date}",
        "Specimen: BLOOD-ALPHA",
    ]
    if amends:
        parts.append(f"Amends: {amends}")
    parts.append(
        f"Finding: hemoglobin|reported|OI-LAB-VALUE/1;value={value};unit=g/dL;qc={qc}")
    return ("\n".join(parts)+"\n").encode("utf-8")


class DurableRunTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=str(Path(self.temp.name)/"synthetic.sqlite")
        self.store=CaseStore(self.db)
        self.store.add_case("CASE-ALPHA","Fictional Alpha")
        self.store.add_case("CASE-BETA","Fictional Beta")
        self.store.import_report("CASE-ALPHA",report("LAB-A1","2026-05-01","10.2"))
        self.store.import_report("CASE-ALPHA",report("LAB-A2","2026-06-01","9.8"))
        self.question=self.store.add_question("CASE-ALPHA","Compare fictional authored numbers")
        self.fingerprint=build_composer_context(self.store,"CASE-ALPHA",self.question)["fingerprint"]
        self.journal=DurableComposerRuns(self.store)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def queue(self,key="TEST-RUN-0001"):
        return self.journal.queue(
            "CASE-ALPHA",self.question,self.fingerprint,"hemoglobin",key)

    def test_queue_execute_persist_restart_and_source_anchors(self):
        first=self.queue()
        self.assertEqual(first["state"],"queued")
        final=self.journal.execute("CASE-ALPHA",first["run_id"])
        self.assertEqual(final["state"],"completed")
        self.assertEqual(final["result"]["result"]["delta"],"-0.4")
        self.assertEqual([e["state"] for e in final["events"]],
                         ["queued","running","completed"])
        self.assertEqual(final["clinical_review_state"],"not_performed")
        self.assertTrue(final["result"]["result"]["points"][0]["source"]["source_sha256"])
        self.store.close()
        self.store=CaseStore(self.db)
        self.journal=DurableComposerRuns(self.store)
        self.assertEqual(final,self.journal.get("CASE-ALPHA",first["run_id"]))

    def test_duplicate_key_does_not_double_queue_or_change_arguments(self):
        first=self.queue()
        self.assertEqual(first,self.queue())
        self.assertEqual(len(self.journal.list("CASE-ALPHA")),1)
        with self.assertRaises(InvalidInput):
            self.journal.queue("CASE-ALPHA",self.question,self.fingerprint,
                               "sodium","TEST-RUN-0001")
        self.assertEqual(len(self.journal.get("CASE-ALPHA",first["run_id"])["events"]),1)

    def test_cancelled_queued_work_cannot_execute(self):
        item=self.queue()
        final=self.journal.cancel("CASE-ALPHA",item["run_id"])
        self.assertEqual(final["state"],"cancelled")
        with self.assertRaises(InvalidInput):
            self.journal.execute("CASE-ALPHA",item["run_id"])

    def test_amended_source_stops_queued_work(self):
        item=self.queue()
        self.store.import_report("CASE-ALPHA",report(
            "LAB-A2","2026-06-01","8.5",amends="LAB-A2@1"))
        outcome=self.journal.execute("CASE-ALPHA",item["run_id"])
        self.assertEqual(outcome["state"],"stale")
        self.assertIsNone(outcome["result"])
        self.assertEqual([e["state"] for e in outcome["events"]],["queued","stale"])

    def test_completed_result_preserves_old_receipt_and_becomes_stale(self):
        item=self.queue()
        self.journal.execute("CASE-ALPHA",item["run_id"])
        self.store.import_report("CASE-ALPHA",report(
            "LAB-A2","2026-06-01","8.5",amends="LAB-A2@1"))
        old=self.journal.get("CASE-ALPHA",item["run_id"])
        self.assertEqual(old["state"],"stale")
        self.assertEqual(old["result"]["result"]["delta"],"-0.4")
        self.assertEqual(old["events"][-1]["reason"],"source_context_changed")
        self.assertEqual(len(old["events"]),4)
        self.assertEqual(len(self.journal.get("CASE-ALPHA",item["run_id"])["events"]),4)

    def test_change_while_running_refuses_to_persist_output(self):
        item=self.queue()
        from open_intelligence import durable_runs
        original=durable_runs.composer_lab_trend
        def mutate(store,case,question,fingerprint,key):
            result=original(store,case,question,fingerprint,key)
            other=CaseStore(self.db)
            try:
                other.import_report("CASE-ALPHA",report(
                    "LAB-A2","2026-06-01","7.1",amends="LAB-A2@1"))
            finally:
                other.close()
            return result
        with patch("open_intelligence.durable_runs.composer_lab_trend",side_effect=mutate):
            final=self.journal.execute("CASE-ALPHA",item["run_id"])
        self.assertEqual(final["state"],"stale")
        self.assertIsNone(final["result"])

    def test_wrong_case_question_and_invalid_tokens_fail_closed(self):
        run=self.queue()
        for operation in (
            lambda: self.journal.get("CASE-BETA",run["run_id"]),
            lambda: self.journal.cancel("CASE-BETA",run["run_id"]),
            lambda: self.journal.queue("CASE-BETA",self.question,self.fingerprint,
                                        "hemoglobin","BETARUN-0001"),
            lambda: self.journal.queue("CASE-ALPHA",self.question,"x"*64,
                                        "hemoglobin","BADRUN-0001")
        ):
            with self.assertRaises(InvalidInput):
                operation()
        self.assertEqual(self.journal.list("CASE-BETA"),[])

    def test_bad_qc_is_blocked_with_reproducible_receipt(self):
        self.store.import_report("CASE-ALPHA",report(
            "LAB-A2","2026-06-01","9.8",qc="failed",amends="LAB-A2@1"))
        refreshed=build_composer_context(self.store,"CASE-ALPHA",self.question)["fingerprint"]
        run=self.journal.queue("CASE-ALPHA",self.question,refreshed,
                               "hemoglobin","BLOCKEDRUN-0001")
        result=self.journal.execute("CASE-ALPHA",run["run_id"])
        self.assertEqual(result["state"],"blocked")
        self.assertFalse(result["result"]["result"]["analysis_executed"])
        self.assertIsNone(result["result"]["result"]["delta"])
        self.assertEqual(result["clinical_authorization"],"not_verified")


class DurableRunHttpTests(DurableRunTests):
    def setUp(self):
        super().setUp()
        handler=type("SyntheticDurableHandler",(Handler,),{"db_path":self.db})
        self.server=ThreadingHTTPServer(("127.0.0.1",0),handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        super().tearDown()

    def request(self,path,payload=None):
        url=f"http://127.0.0.1:{self.server.server_port}{path}"
        headers={"Content-Type":"application/json"} if payload is not None else {}
        raw=json.dumps(payload).encode() if payload is not None else None
        try:
            with urlopen(Request(url,data=raw,headers=headers),timeout=8) as r:
                return r.status,json.loads(r.read())
        except HTTPError as e:
            return e.code,json.loads(e.read())

    def test_http_queue_execute_list_and_reopen_after_restart(self):
        root="/api/cases/CASE-ALPHA/composer/runs"
        code,new=self.request(root,{
            "question_id":self.question,"context_fingerprint":self.fingerprint,
            "finding_key":"hemoglobin","idempotency_key":"HTTP-RUN-0001"})
        self.assertEqual(code,201)
        self.assertEqual(new["state"],"queued")
        code,done=self.request(root+f"/{new['run_id']}/execute",{})
        self.assertEqual(code,200)
        self.assertEqual(done["state"],"completed")
        code,listed=self.request(root)
        self.assertEqual(code,200)
        self.assertEqual(len(listed["runs"]),1)
        self.assertEqual(listed["runs"][0]["result"]["result"]["delta"],"-0.4")
        code,wrong=self.request("/api/cases/CASE-BETA/composer/runs/"+str(new["run_id"]))
        self.assertEqual(code,422)
        self.assertNotIn("LAB-A1",json.dumps(wrong))

    def test_http_cancel_and_reject_unexpected_task_fields(self):
        root="/api/cases/CASE-ALPHA/composer/runs"
        payload={"question_id":self.question,
                 "context_fingerprint":self.fingerprint,
                 "finding_key":"hemoglobin","idempotency_key":"HTTP-CANCEL-01"}
        self.assertEqual(self.request(root,dict(payload,arbitrary="danger"))[0],422)
        _,new=self.request(root,payload)
        code,cancelled=self.request(root+f"/{new['run_id']}/cancel",{})
        self.assertEqual(code,200)
        self.assertEqual(cancelled["state"],"cancelled")
        self.assertEqual(self.request(root+f"/{new['run_id']}/execute",{})[0],422)


if __name__=="__main__":
    unittest.main()
