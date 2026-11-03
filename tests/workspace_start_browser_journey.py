"""Actual empty-workspace to versioned review journey; original fictional inputs only."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.request import urlopen
from browser_journey import ChromeSession, free_port, wait_for
ROOT=Path(__file__).resolve().parents[1]
CASE='CASE-START'
ORIGINAL=('OI-SYNTHETIC-REPORT/1\nPatient: '+CASE+'\nDocument: START-PATH\nType: pathology\n'
 'Event-Date: 2026-01-02\nIssued-At: 2026-01-03\nSpecimen: START-TISSUE\n'
 'Finding: marker|not-reported|The fictional marker was not tested; café <script>literal</script>.\n').encode('utf-8')
AMENDED=ORIGINAL.replace(b'Issued-At: 2026-01-03',b'Issued-At: 2026-01-04').replace(
 b'Finding:',b'Amends: START-PATH@1\nFinding:',1).replace(b'not-reported|The fictional marker was not tested',
 b'negative|The amended fictional report records a negative marker')

def main():
 chrome=next((p for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if (p:=shutil.which(n))),None)
 if not chrome: raise AssertionError('Chromium unavailable; journey not verified')
 with tempfile.TemporaryDirectory(prefix='oi-workspace-start-') as tmp:
  db=str(Path(tmp)/'empty.sqlite');profile=str(Path(tmp)/'chrome');app_port=free_port();debug=free_port()
  env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
  server=subprocess.Popen([sys.executable,str(ROOT/'run_open_intelligence.py'),'--db',db,'--port',str(app_port)],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  browser=None;cd=None
  try:
   url=f'http://127.0.0.1:{app_port}/'
   wait_for(lambda:urlopen(url,timeout=1).status==200,'workspace server')
   browser=subprocess.Popen([chrome,'--headless=new','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--no-first-run','--disable-extensions','--no-default-browser-check','--remote-allow-origins=*',f'--remote-debugging-port={debug}',f'--user-data-dir={profile}','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
   targets=wait_for(lambda:json.load(urlopen(f'http://127.0.0.1:{debug}/json/list',timeout=1)),'browser debugger')
   cd=ChromeSession(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'))
   cd.command('Page.enable');cd.command('Runtime.enable');cd.command('DOM.enable')
   cd.command('Page.navigate',{'url':url})
   cd.wait("document.body.dataset.workspaceState==='empty'",'empty application without seed command')
   assert json.load(urlopen(url+'api/cases'))==[]
   cd.evaluate("document.querySelector('#case-create-code').value='CASE-START';document.querySelector('#case-create-alias').value='Start';document.querySelector('#case-create-confirm').click();document.querySelector('#case-create-form').requestSubmit()")
   cd.wait("document.querySelector('#case-heading').textContent==='Fictional case Start' && document.body.dataset.workspaceState==='ready'",'new persistent case')
   # Create a second fictional case through the real browser workspace.
   # The original case must remain selected when an unfinished source-linked
   # question later vetoes a patient switch.
   cd.evaluate("document.querySelector('#case-create-code').value='CASE-OTHER';document.querySelector('#case-create-alias').value='Other';document.querySelector('#case-create-confirm').click();document.querySelector('#case-create-form').requestSubmit()")
   cd.wait("document.querySelector('#case-heading').textContent==='Fictional case Other'",'second fictional workspace created')
   cd.evaluate("document.querySelector('#case-picker').value='CASE-START';document.querySelector('#case-picker').dispatchEvent(new Event('change'))")
   cd.wait("document.querySelector('#case-heading').textContent==='Fictional case Start'",'return to original workspace')
   cd.evaluate("document.querySelector('#record-acquisition').open=true;document.querySelector('#record-request-label').value='Fictional pathology report';document.querySelector('#record-request-from').value='Fictional pathology center';document.querySelector('#record-request-kind').value='pathology';document.querySelector('#record-request-form').requestSubmit()")
   cd.wait("document.querySelector('#record-request-list').textContent.includes('awaiting record')",'persistent record acquisition request')
   acquisitions=json.load(urlopen(url+'api/cases/'+CASE+'/record-requests'))
   assert len(acquisitions['requests'])==1
   request_id=acquisitions['requests'][0]['id']
   assert acquisitions['requests'][0]['status']=='requested'
   def upload(raw,name):
    cd.evaluate("if(!document.querySelector('#source-intake').open) document.querySelector('#source-intake > summary').click()")
    file=Path(tmp)/name;file.write_bytes(raw)
    dom=cd.command('DOM.getDocument')
    node=cd.command('DOM.querySelector',{'nodeId':dom['root']['nodeId'],'selector':'#source-file'})
    cd.command('DOM.setFileInputFiles',{'files':[str(file)],'nodeId':node['nodeId']})
    cd.wait("!document.querySelector('#source-preview-details').hidden",'local file inspected')
    assert cd.evaluate("document.querySelector('#source-upload-preview').textContent")==raw.decode('utf-8')
    assert cd.evaluate("document.querySelectorAll('#source-upload-preview script').length") == 0
    if name=='original.txt':
     # A veto must preserve BOTH the unsaved question and the inspected file,
     # including the exact source preview and selected local File.
     cd.evaluate("""(() => {
       document.querySelector('#question-text').value='What remains uncertain about this invented source?';
       const picker=document.querySelector('#case-picker');
       picker.value='CASE-OTHER';
       picker.dispatchEvent(new Event('change'));
     })()""")
     assert cd.evaluate("document.querySelector('#case-picker').value==='CASE-START'"), 'case switched despite an unsaved question'
     assert cd.evaluate("document.querySelector('#question-text').value.includes('invented source')"), 'unsaved question was erased'
     assert cd.evaluate("document.querySelector('#source-upload-preview').textContent.length>0 && !document.querySelector('#source-preview-details').hidden"), 'veto discarded the inspected source preview'
     assert cd.evaluate("document.querySelector('#source-file').files.length===1"), 'veto discarded selected original file'
     cd.evaluate("document.querySelector('#question-text').value=''")
    cd.evaluate("document.querySelector('#source-upload-confirm').click();document.querySelector('#source-upload-form').requestSubmit()")
   upload(ORIGINAL,'original.txt')
   cd.wait("document.querySelectorAll('#source-list .source-card').length===1",'file import updates original record')
   state=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert state['sources'][0]['sha256']==hashlib.sha256(ORIGINAL).hexdigest()
   assert state['assertions'][0]['certainty']=='not-reported'
   assert cd.evaluate("document.querySelector('#timeline-events').textContent.includes('START-PATH')")
   cd.wait("!![...document.querySelectorAll('#record-request-list button')].find(b=>b.textContent.includes('Mark received'))",'current original can be linked')
   cd.evaluate("[...document.querySelectorAll('#record-request-list button')].find(b=>b.textContent.includes('Mark received')).click()")
   cd.wait("document.querySelector('#record-request-list').textContent.includes('source current')",'original source explicitly reconciled to request')
   linked=json.load(urlopen(url+'api/cases/'+CASE+'/record-requests'))['requests'][0]
   assert linked['received_source_id']==state['sources'][0]['id']
   assert linked['source_sha256']==hashlib.sha256(ORIGINAL).hexdigest()
   cd.evaluate("document.querySelector('#question-text').value='Which original finding requires clarification?';document.querySelector('#question-form').requestSubmit()")
   cd.wait("document.querySelector('#composer-context-fingerprint').value.length===64 && !document.querySelector('#model-investigation-run').disabled",'canonical source preview')
   cd.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
   cd.wait("document.querySelectorAll('#model-investigation-list .snapshot').length===1",'recorded replay saved; no model request')
   cd.evaluate("[...document.querySelectorAll('#model-investigation-list button')].find(b=>b.textContent==='Prepare review draft').click()")
   cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length===1",'source-linked report')
   before=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   old=before['snapshots'][0];assert old['state']=='draft';assert before['questions'][0]['state']=='open'
   cd.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(b=>b.textContent.includes('Demo review acknowledgment')).click()")
   cd.wait("document.querySelector('#journey-steps').textContent.includes('Demo review recorded')",'explicit review acknowledged')
   upload(AMENDED,'amended.txt')
   cd.wait("document.querySelector('#journey-steps').textContent.includes('Update needs review')",'amendment reopens review')
   cd.wait("document.querySelector('#record-request-list').textContent.includes('source superseded reconciliation needed')",'acquisition receipt detects corrected source')
   historical=json.load(urlopen(url+'api/cases/'+CASE+'/record-requests'))['requests'][0]
   assert historical['receipt_state']=='source_superseded_reconciliation_needed'
   cd.evaluate("[...document.querySelectorAll('#record-request-list button')].find(b=>b.textContent.includes('Reconcile amended original')).click()")
   cd.wait("document.querySelector('#record-request-list').textContent.includes('source current')",'amended original explicitly reconciled')
   revised=json.load(urlopen(url+'api/cases/'+CASE+'/record-requests'))['requests'][0]
   assert revised['received_source_id']!=historical['received_source_id']
   assert revised['document_version']==2
   cd.wait("document.querySelectorAll('#source-list .source-card').length===2",'historical originals retained')
   state=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert state['snapshots'][0]['state']=='stale';assert state['questions'][0]['state']=='open'
   exported=urlopen(url+f"api/cases/{CASE}/snapshots/{old['id']}/export").read().decode()
   assert 'START-PATH@1' in exported and 'stale' in exported
   cd.wait("document.querySelector('#composer-context-fingerprint').value.length===64 && !document.querySelector('#model-investigation-run').disabled",'revised source preview')
   cd.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
   cd.wait("document.querySelectorAll('#model-investigation-list .snapshot').length===2",'new explicit reassessment')
   cd.evaluate("[...document.querySelectorAll('#model-investigation-list button')].find(b=>b.textContent==='Prepare review draft').click()")
   cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length===2",'new report; original history untouched')
   cd.command('Page.reload')
   cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length===2",'persistent case and reports after browser reload')
   assert len(json.load(urlopen(url+'api/cases')))==2
   assert json.load(urlopen(url+'api/cases/CASE-OTHER/state'))['sources']==[]
   assert json.load(urlopen(url+'api/cases/'+CASE+'/record-requests'))['requests'][0]['receipt_state']=='source_current'
   cd.evaluate("document.querySelector('#record-acquisition').open=true")
   cd.wait("document.querySelector('#record-request-list').textContent.includes('source current')",'durable request receipt after browser reload')
   state=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert next(s for s in state['snapshots'] if s['id']==old['id'])['summary']==old['summary']
   assert next(s for s in state['snapshots'] if s['id']!=old['id'])['state']=='draft'
   cd.command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
   artifacts=os.environ.get('OI_INTAKE_ARTIFACT_DIR')
   if artifacts:
    Path(artifacts).mkdir(parents=True,exist_ok=True)
    shot=cd.command('Page.captureScreenshot',{'format':'png'})
    (Path(artifacts)/'workspace-desktop.png').write_bytes(base64.b64decode(shot['data']))
   cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
   cd.wait('window.innerWidth===390','mobile viewport')
   assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
   if artifacts:
    shot=cd.command('Page.captureScreenshot',{'format':'png'})
    (Path(artifacts)/'workspace-mobile.png').write_bytes(base64.b64decode(shot['data']))
   print('PASS: empty database -> UI case creation -> exact disk-file intake -> timeline -> question -> replay -> report -> explicit demo review -> amended disk file -> stale/open -> new draft -> reload; UTF-8/LF preserved, markup inert, mobile contained. No live model/retrieval or clinical authorization.')
  except Exception:
   if cd:
    print('BROWSER_DIAGNOSTIC', cd.evaluate("JSON.stringify({url:location.href,ready:document.readyState,state:document.body?.dataset,notice:document.querySelector('#notice')?.textContent,intake:typeof OIIntake,app:typeof initialize,body:document.body?.textContent.slice(0,800)})"))
   raise
  finally:
   if cd:cd.close()
   if browser:
    try:os.killpg(browser.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:browser.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(browser.pid,signal.SIGKILL);browser.wait(timeout=5)
   server.terminate()
   try:server.wait(timeout=5)
   except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
if __name__=='__main__': main()
