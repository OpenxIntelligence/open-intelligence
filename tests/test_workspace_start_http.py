"""Fresh-database HTTP operations reused by the connected intake UI."""
from pathlib import Path
import hashlib
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from open_intelligence.workspace_host import workspace_handler, workspace_html
from open_intelligence.store import CaseStore

RAW=b'OI-SYNTHETIC-REPORT/1\nPatient: CASE-START\nDocument: SOURCE-ONE\nType: clinical\nEvent-Date: 2026-01-02\nIssued-At: 2026-01-03\nFinding: goal|reported|An original fictional goal.\n'
class WorkspaceStartHttpTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.db=str(Path(self.tmp.name)/'empty.sqlite')
  handler=workspace_handler(self.db)
  self.server=ThreadingHTTPServer(('127.0.0.1',0),handler)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.addCleanup(self.stop);self.url=f'http://127.0.0.1:{self.server.server_port}'
 def stop(self):
  self.server.shutdown();self.thread.join(timeout=5);self.server.server_close()
 def read(self,path,payload=None):
  req=Request(self.url+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
  with urlopen(req,timeout=5) as r:
   data=r.read();return json.loads(data) if 'json' in r.headers.get('Content-Type','') else data.decode()
 def test_fresh_database_to_case_and_exact_uploaded_bytes_survives_reopen(self):
  self.assertEqual(self.read('/api/cases'),[])
  self.read('/api/cases',{'case_id':'CASE-START','label':'Fictional case Start'})
  result=self.read('/api/cases/CASE-START/imports',{'text':RAW.decode()})
  self.assertEqual(result['result'],'imported')
  store=CaseStore(self.db)
  try:
   state=store.state('CASE-START');src=state['sources'][0]
   self.assertEqual(src['sha256'],hashlib.sha256(RAW).hexdigest())
   self.assertEqual(store.source_text('CASE-START',src['id']).encode(),RAW)
  finally:store.close()
 def test_entry_ui_and_script_are_available_without_seeding(self):
  page=self.read('/');script=self.read('/intake.js')
  for required in ['case-create-form','source-upload-form','journey-steps']:self.assertIn(required,page)
  self.assertIn('decodeSource',script)
  self.assertEqual(self.read('/api/cases'),[])
 def test_role_views_layer_is_linked_and_served(self):
  page=self.read('/')
  self.assertIn('<link rel="stylesheet" href="/views.css">',page)
  self.assertIn('<script src="/views.js" defer></script>',page)
  self.assertLess(page.index('/workspace-entry.js'),page.index('/views.js'))
  self.assertIn('LAYOUT',self.read('/views.js'))
  self.assertIn('.view-panel',self.read('/views.css'))
 def test_duplicate_case_does_not_replace_existing_sources(self):
  payload={'case_id':'CASE-START','label':'Fictional case Start'}
  self.read('/api/cases',payload);self.read('/api/cases/CASE-START/imports',{'text':RAW.decode()})
  with self.assertRaises(HTTPError) as err:self.read('/api/cases',dict(payload,label='Different'))
  self.assertEqual(err.exception.code,422)
  state=self.read('/api/cases/CASE-START/state');self.assertEqual(state['case']['label'],payload['label']);self.assertEqual(len(state['sources']),1)
 def test_wrong_subject_upload_remains_quarantined(self):
  self.read('/api/cases',{'case_id':'CASE-START','label':'Fictional case Start'})
  result=self.read('/api/cases/CASE-START/imports',{'text':RAW.decode().replace('CASE-START','CASE-OTHER')})
  self.assertEqual(result['result'],'quarantined')
  self.assertEqual(self.read('/api/cases/CASE-START/state')['sources'],[])
if __name__=='__main__':unittest.main()
