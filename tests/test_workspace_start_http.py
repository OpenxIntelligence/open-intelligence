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
 def test_bound_composer_preview_from_same_original_source_and_question(self):
  self.read('/api/cases',{'case_id':'CASE-START','label':'Fictional case Start'})
  imported=self.read('/api/cases/CASE-START/imports',{'text':RAW.decode()})
  self.assertEqual(imported['result'],'imported')
  qid=self.read('/api/cases/CASE-START/questions',
                {'question':'Which fictional source finding requires clarification?'})['question_id']
  context=self.read(f'/api/cases/CASE-START/composer/context?question_id={qid}')
  self.assertEqual(context['context_kind'],'synthetic_source_bound_read_only')
  self.assertEqual(context['case_id'],'CASE-START')
  self.assertEqual(context['question_id'],qid)
  self.assertEqual(len(context['fingerprint']),64)
  self.assertTrue(all(letter in '0123456789abcdef' for letter in context['fingerprint']))
  self.assertEqual(context['source_count'],1)
  self.assertEqual(context['source_anchors'][0]['source_version_id'],imported['source_id'])
  self.assertEqual(context['source_anchors'][0]['reported_state'],'reported')
  self.assertEqual(context['rights_basis'],'recorded_declaration_only')
  self.assertEqual(context['tool_status']['clinical_authorization'],'not_verified')
  self.assertIn('model-investigation-run',self.read('/'))
  self.assertIn('composer-context-fingerprint',self.read('/'))
  self.assertIn('composer-context',self.read('/composer.js'))
  amended=RAW.decode().replace('Issued-At: 2026-01-03','Issued-At: 2026-01-05').replace(
   'Finding:','Amends: SOURCE-ONE@1\nFinding:',1)
  self.read('/api/cases/CASE-START/imports',{'text':amended})
  changed=self.read(f'/api/cases/CASE-START/composer/context?question_id={qid}')
  self.assertNotEqual(context['fingerprint'],changed['fingerprint'])
  self.assertEqual(changed['current_sources'][0]['version'],2)

 def test_composer_preview_rejects_invalid_or_cross_case_question(self):
  self.read('/api/cases',{'case_id':'CASE-START','label':'Fictional case Start'})
  self.read('/api/cases',{'case_id':'CASE-OTHER','label':'Fictional case Other'})
  qid=self.read('/api/cases/CASE-START/questions',
                {'question':'Which original fictional report should be reviewed?'})['question_id']
  for route in ('/api/cases/CASE-START/composer/context',
                '/api/cases/CASE-START/composer/context?question_id=0',
                '/api/cases/CASE-START/composer/context?question_id=bad',
                f'/api/cases/CASE-OTHER/composer/context?question_id={qid}'):
   with self.subTest(route=route), self.assertRaises(HTTPError) as err:
    self.read(route)
   self.assertEqual(err.exception.code,422)

if __name__=='__main__':unittest.main()
