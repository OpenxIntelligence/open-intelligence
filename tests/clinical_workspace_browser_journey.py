"""Actual synthetic empty-workspace intake, v2 source preview and human-authored review journey."""
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
   def upload(raw,name):
    cd.evaluate("if(!document.querySelector('#source-intake').open) document.querySelector('#source-intake > summary').click()")
    file=Path(tmp)/name;file.write_bytes(raw)
    dom=cd.command('DOM.getDocument')
    node=cd.command('DOM.querySelector',{'nodeId':dom['root']['nodeId'],'selector':'#source-file'})
    cd.command('DOM.setFileInputFiles',{'files':[str(file)],'nodeId':node['nodeId']})
    cd.wait("!document.querySelector('#source-preview-details').hidden",'local file inspected')
    assert cd.evaluate("document.querySelector('#source-upload-preview').textContent")==raw.decode('utf-8')
    assert cd.evaluate("document.querySelectorAll('#source-upload-preview script').length") == 0
    cd.evaluate("document.querySelector('#source-upload-confirm').click();document.querySelector('#source-upload-form').requestSubmit()")
   upload(ORIGINAL,'original.txt')
   cd.wait("document.querySelectorAll('#source-list .source-card').length===1",'file import updates original record')
   state=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert state['sources'][0]['sha256']==hashlib.sha256(ORIGINAL).hexdigest()
   assert state['assertions'][0]['certainty']=='not-reported'
   assert cd.evaluate("document.querySelector('#timeline-events').textContent.includes('START-PATH')")
   cd.evaluate("document.querySelector('#question-text').value='Which original finding requires clarification?';document.querySelector('#question-form').requestSubmit()")
   cd.wait("document.querySelector('#composer-context-fingerprint').value.length===64 && !document.querySelector('#model-investigation-run').disabled",'canonical source preview')
   cd.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
   cd.wait("document.querySelectorAll('#model-investigation-list .snapshot').length===1",'recorded replay saved; no model request')
   cd.evaluate("""(() => {
    // Clinical branch has no automatic model-to-report promotion. A person
    // must author observations and explicitly select the current source.
    const inputs = [...document.querySelectorAll('#source-choice input')];
    if (!inputs.length) throw new Error('No current original source to cite');
    inputs.forEach(input => { input.checked = true; });
    document.querySelector('#draft-observations').value =
      'Original fictional pathology source requires human interpretation.';
    document.querySelector('#draft-summary').value =
      'Human-authored discussion draft, not an AI treatment recommendation.';
    document.querySelector('#draft-assumptions').value =
      'Recorded replay is an unreviewed hypothesis; interpretation remains uncertain.';
    document.querySelector('#draft-form').requestSubmit();
   })()""")
   cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length===1",'source-linked report')
   before=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   old=before['snapshots'][0];assert old['state']=='draft';assert before['questions'][0]['state']=='open'
   cd.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(b=>b.textContent.includes('Demo review acknowledgment')).click()")
   cd.wait("document.querySelector('#journey-steps').textContent.includes('Demo review recorded')",'explicit review acknowledged')
   upload(AMENDED,'amended.txt')
   cd.wait("document.querySelector('#journey-steps').textContent.includes('Update needs review')",'amendment reopens review')
   cd.wait("document.querySelectorAll('#source-list .source-card').length===2",'historical originals retained')
   state=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert state['snapshots'][0]['state']=='stale';assert state['questions'][0]['state']=='open'
   exported=urlopen(url+f"api/cases/{CASE}/snapshots/{old['id']}/export").read().decode()
   assert 'START-PATH@1' in exported and 'stale' in exported
   cd.wait("document.querySelector('#composer-context-fingerprint').value.length===64 && !document.querySelector('#model-investigation-run').disabled",'revised source preview')
   cd.evaluate("document.querySelector('#model-investigation-form').requestSubmit()")
   cd.wait("document.querySelectorAll('#model-investigation-list .snapshot').length===2",'new explicit reassessment')
   current_id=next(item['id'] for item in state['sources'] if item['state']=='current')
   superseded_id=next(item['id'] for item in state['sources'] if item['state']!='current')
   cd.wait("""(() => {
    const inputs=[...document.querySelectorAll('#source-choice input')];
    const prior=inputs.find(input=>input.value==='""" + str(superseded_id) + """');
    const fresh=inputs.find(input=>input.value==='""" + str(current_id) + """');
    return !!prior && prior.checked && !!fresh && !fresh.checked;
   })()""",'superseded source remains explicitly selected after amendment')
   cd.evaluate("""(() => {
    // Try the superseded selection first. It must not be silently promoted.
    document.querySelector('#draft-observations').value =
      'Original fictional pathology source requires human interpretation.';
    document.querySelector('#draft-summary').value =
      'Human-authored discussion draft, not an AI treatment recommendation.';
    document.querySelector('#draft-assumptions').value =
      'Recorded replay remains an unreviewed research hypothesis.';
    document.querySelector('#draft-form').requestSubmit();
   })()""")
   cd.wait("document.querySelector('#notice').textContent.includes('Source is missing, superseded, or belongs to another case')",
           'stale historical source rejected by canonical ledger')
   denied=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert len(denied['snapshots'])==1,'stale source acceptance created a second draft'
   cd.evaluate("""(() => {
    // User must explicitly reconcile the exact current version, not silently
    // treat an old citation as the new document.
    const inputs=[...document.querySelectorAll('#source-choice input')];
    const selected=inputs.find(input=>input.value==='""" + str(current_id) + """');
    if(!selected) throw new Error('Corrected source was not offered for review');
    inputs.forEach(input=>{input.checked=(input===selected);});
    document.querySelector('#draft-form').requestSubmit();
   })()""")
   cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length===2",
           'new human-authored report uses reconciled current source')
   checked=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert next(s for s in checked['snapshots'] if s['state']=='draft')['source_ids']==[current_id], \
    'new report kept stale source rather than explicit current selection'
   cd.command('Page.reload')
   cd.wait("document.querySelectorAll('#snapshot-list .snapshot').length===2",'persistent case and reports after browser reload')
   assert len(json.load(urlopen(url+'api/cases')))==1
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
   print('PASS: empty database -> UI case creation -> exact disk-file intake -> timeline -> question -> recorded replay -> human-authored source-cited report -> explicit demo review -> amended disk file -> stale/open -> new draft -> reload; UTF-8/LF preserved, markup inert, mobile contained. No live model/retrieval or clinical authorization.')
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
