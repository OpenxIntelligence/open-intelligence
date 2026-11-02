"""Exercise the local demo HTTP boundary using fictional records only."""
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore
from open_intelligence.__main__ import Handler


class NewSourceReviewHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=str(Path(cls.tmp.name)/'http.sqlite')
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),type('ReviewHandler',(Handler,),{'db_path':cls.path}))
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5);cls.tmp.cleanup()

    def setUp(self):
        # Unique cases keep tests independent on the same local server.
        self.case='CASE-'+self._testMethodName.replace('test_','').replace('_','-').upper()[:25]
        store=CaseStore(self.path)
        try:
            store.add_case(self.case,'Original fictional HTTP test')
            def raw(doc,date,quote):
                return (f'OI-SYNTHETIC-REPORT/1\nPatient: {self.case}\nDocument: {doc}\nType: other\n'
                        f'Event-Date: {date}\nIssued-At: 2026-06-02\nFinding: plan|reported|{quote}\n').encode()
            old=store.import_report(self.case,raw('OLD','2026-06-01','Fictional earlier plan.'))['source_id']
            question=store.add_question(self.case,'What changed in the fictional plan?')
            self.snapshot=store.create_snapshot(self.case,question,'A fictional earlier discussion.',[old])
            self.source=store.import_report(self.case,raw('NEW','2026-06-02','Fictional later plan.'))['source_id']
        finally:store.close()
        self.url=f'/api/cases/{self.case}/snapshots/{self.snapshot}/new-source-review'
        self.body={'source_version_id':self.source,'source_line':7,'reviewer_label':'Demo coordinator',
                   'rationale':'Later planning information needs a bounded discussion review.'}

    def request(self,path,data=None,headers=None):
        request=Request(f'http://127.0.0.1:{self.port}{path}',
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Content-Type':'application/json',**(headers or {})})
        try:
            with urlopen(request,timeout=5) as response:return response.status,json.loads(response.read())
        except HTTPError as error:
            try:return error.code,json.loads(error.read())
            finally:error.close()

    def test_context_request_and_duplicate(self):
        status,context=self.request(self.url);self.assertEqual(status,200)
        self.assertFalse(context['clinical_relevance_assessed'])
        self.assertEqual(context['sources'][0]['source_version_id'],self.source)
        status,receipt=self.request(self.url,self.body);self.assertEqual(status,200)
        self.assertEqual(receipt['result'],'review_requested')
        status,retry=self.request(self.url,self.body);self.assertEqual(status,200)
        self.assertEqual(retry['event_id'],receipt['event_id'])
        _,history=self.request(self.url);self.assertEqual(len(history['requests']),1)
        _,changes=self.request(f'/api/cases/{self.case}/changes-since-review')
        self.assertEqual(changes['stale_investigations'][0]['causes'][0]['cause'],'new_source_review_request')

    def test_invalid_anchor_and_ambiguous_type(self):
        for altered in ({'source_line':4},{'source_line':True},{'source_version_id':'1'},{'rationale':''},{'approve':True}):
            status,_=self.request(self.url,{**self.body,**altered});self.assertEqual(status,422)
        _,context=self.request(self.url);self.assertEqual(context['requests'],[])

    def test_cross_case_and_foreign_origin(self):
        status,_=self.request(self.url.replace(self.case,'CASE-NOT-HERE'),self.body)
        self.assertEqual(status,422)
        status,_=self.request(self.url,self.body,{'Origin':'https://example.invalid'})
        self.assertEqual(status,403)
        _,context=self.request(self.url);self.assertEqual(context['requests'],[])

    def test_host_guard_and_get_is_not_a_write(self):
        connection=HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            connection.request('GET',self.url,headers={'Host':'example.invalid'})
            response=connection.getresponse();self.assertEqual(response.status,403);response.read()
        finally:connection.close()
        for _ in range(2):
            status,context=self.request(self.url);self.assertEqual(status,200)
            self.assertEqual(context['requests'],[])
            self.assertTrue(context['request_allowed'])


if __name__=='__main__':unittest.main()
