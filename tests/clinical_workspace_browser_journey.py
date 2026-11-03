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
from patient_report_followthrough_browser_journey import (
 REPORT_PROBE, report_ready, download_report, task_transition)
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
   chrome_stderr=Path(tmp)/'chrome-stderr.txt'
   with chrome_stderr.open('wb') as log:
    browser=subprocess.Popen(
     [chrome,'--headless=new','--disable-gpu','--disable-dev-shm-usage',
      '--disable-background-networking','--no-first-run','--disable-extensions',
      '--no-default-browser-check','--remote-allow-origins=*',
      f'--remote-debugging-port={debug}',f'--user-data-dir={profile}','about:blank'],
     stdout=subprocess.DEVNULL,stderr=log,start_new_session=True)
   try:
    targets=wait_for(lambda:json.load(urlopen(
     f'http://127.0.0.1:{debug}/json/list',timeout=1)),'browser debugger',timeout=25)
   except AssertionError as exc:
    # Startup failures occurred before app navigation in earlier CI. Preserve
    # actual Chrome process status and stderr instead of suggesting that the
    # clinical UI's source/review checks ran when they did not.
    browser_log=chrome_stderr.read_text(encoding='utf-8',errors='replace')[-3200:]
    raise AssertionError(
     f'{exc}; chrome_exit={browser.poll()}; chrome_log_tail={browser_log}') from exc
   cd=ChromeSession(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'))
   cd.command('Page.enable');cd.command('Runtime.enable');cd.command('DOM.enable')
   downloads=Path(tmp)/'downloads'; downloads.mkdir()
   cd.command('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads)})
   cd.command('Page.addScriptToEvaluateOnNewDocument',{'source':REPORT_PROBE})
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
   cd.evaluate("document.querySelector('#composer-context button').click()")
   cd.wait("document.querySelector('#source-dialog').open",'Composer opens original source inspector')
   assert cd.evaluate("document.querySelector('#dialog-text mark.source-highlight').textContent.includes('not tested')")
   assert cd.evaluate("document.querySelector('#dialog-title').textContent.includes('START-PATH@1')")
   cd.evaluate("document.querySelector('#dialog-close').click()")
   # The actual new workspace now shares source/question-linked task history
   # with its readable report. No alternate task or source owner is used.
   def record_task(title):
    cd.evaluate("""(() => {
      document.querySelector('#ft-title').value=%s;
      document.querySelector('#ft-question').selectedIndex=1;
      document.querySelector('#ft-source').selectedIndex=1;
      document.querySelector('#ft-actor').value='Fictional navigator';
      document.querySelector('#ft-reason').value='Record preparation for the fictional discussion.';
      document.querySelector('#followthrough-form').requestSubmit();
    })()""" % json.dumps(title))
    cd.wait("document.querySelector('#ft-open').textContent.includes("+json.dumps(title)+")",'persisted follow-through task')
    report_ready(cd,CASE,title)
    return next(t['id'] for t in json.load(urlopen(url+'api/cases/'+CASE+'/state'))['followthrough']['tasks'] if t['title']==title)
   open_task=record_task('Open original-source follow-through')
   completed_task=record_task('Completed original-source preparation')
   cd.evaluate("document.querySelector('#ft-task-choice').value="+json.dumps(str(completed_task)))
   for status in ('assigned','acknowledged','completed'):
    task_transition(cd,status,'Recorded the fictional '+status+' transition.','Fictional coordinator' if status=='assigned' else '')
    cd.wait("document.querySelector('#ft-task-choice').selectedOptions[0]?.textContent.includes('("+status+")')",'task '+status)
   report_ready(cd,CASE,'completed')
   original_report=download_report(cd,downloads,CASE)
   assert hashlib.sha256(ORIGINAL).hexdigest() in original_report and 'START-PATH@1' in original_report
   assert 'Completed original-source preparation' in original_report and 'Open original-source follow-through' in original_report
   cd.wait("document.querySelector('#composer-context-fingerprint').value.length===64 && !document.querySelector('#model-investigation-run').disabled",'fresh context after recorded tasks')
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
   report_ready(cd,CASE)
   cd.evaluate("""(() => {
    const originalFetch=window.fetch.bind(window);
    window.__previousComposerAnchor=document.querySelector('#composer-context button');
    window.__holdOriginalImport=true;
    window.fetch=async(...args)=>{
      if(window.__holdOriginalImport && String(args[0])==='/api/cases/CASE-START/imports' && args[1]?.method==='POST') {
        window.__holdOriginalImport=false;
        await new Promise(resolve=>{window.__releaseOriginalImport=resolve;});
      }
      return originalFetch(...args);
    };
   })()""")
   upload(AMENDED,'amended.txt')
   cd.wait("typeof window.__releaseOriginalImport==='function'",'actual source import held before HTTP settlement')
   assert cd.evaluate("document.querySelector('#report-print').disabled && !document.querySelector('#report-text-link').getAttribute('href') && document.querySelector('#report-refresh').disabled")
   assert cd.evaluate("document.querySelector('#model-investigation-run').disabled && document.querySelector('#composer-context-fingerprint').value===''")
   cd.evaluate("window.__previousComposerAnchor.click()")
   assert not cd.evaluate("document.querySelector('#source-dialog').open"),'old preview action survived pending source write'
   cd.evaluate("window.__releaseOriginalImport()")
   cd.wait("document.querySelector('#journey-steps').textContent.includes('Update needs review')",'amendment reopens review')
   cd.wait("document.querySelectorAll('#source-list .source-card').length===2",'historical originals retained')
   state=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert state['snapshots'][0]['state']=='stale';assert state['questions'][0]['state']=='open'
   tasks={t['id']:t for t in state['followthrough']['tasks']}
   assert tasks[open_task]['needs_recheck'] and tasks[open_task]['status']=='created'
   assert tasks[completed_task]['status']=='completed' and not tasks[completed_task]['needs_recheck']
   assert len(tasks[completed_task]['history'])==4
   report_ready(cd,CASE,'linked source amended')
   updated_report=download_report(cd,downloads,CASE)
   assert hashlib.sha256(ORIGINAL).hexdigest() in updated_report and 'START-PATH@1' in updated_report
   assert 'this task remains history' in updated_report

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
   # The new patient case must never silently inherit unfinished content
   # from the previous case, even when a source file has been inspected.
   cd.evaluate("document.querySelector('#ft-title').value='Unsubmitted original-case task'")
   cd.evaluate("""(() => {
    document.querySelector('#new-workspace-button').click();
    document.querySelector('#case-create-code').value='CASE-OTHER';
    document.querySelector('#case-create-alias').value='Other';
    document.querySelector('#case-create-confirm').click();
    document.querySelector('#case-create-form').requestSubmit();
   })()""")
   cd.wait("document.querySelector('#case-create-status').textContent.includes('Save or clear')",'unfinished task blocks workspace creation')
   assert len(json.load(urlopen(url+'api/cases')))==1,'new workspace persisted despite unfinished task'
   assert cd.evaluate("document.querySelector('#ft-title').value==='Unsubmitted original-case task'")
   cd.evaluate("document.querySelector('#ft-title').value='';document.querySelector('#case-create-form').requestSubmit()")
   cd.wait("document.querySelector('#case-heading').textContent==='Fictional case Other' && document.body.dataset.workspaceState==='ready'",
           'second separate fictional case created in real UI')
   cd.evaluate("""(() => {
    const picker=document.querySelector('#case-picker');
    picker.value='CASE-START';picker.dispatchEvent(new Event('change'));
   })()""")
   cd.wait("document.querySelector('#case-heading').textContent==='Fictional case Start' && document.body.dataset.workspaceState==='ready'",
           'first fictional case reselected')
   cd.evaluate("if(!document.querySelector('#source-intake').open) document.querySelector('#source-intake > summary').click()")
   doc=cd.command('DOM.getDocument')
   file_input=cd.command('DOM.querySelector',{'nodeId':doc['root']['nodeId'],'selector':'#source-file'})
   cd.command('DOM.setFileInputFiles',{'files':[str(Path(tmp)/'original.txt')],'nodeId':file_input['nodeId']})
   cd.wait("!document.querySelector('#source-preview-details').hidden",
           'source bytes staged but not imported')
   cd.evaluate("""(() => {
    document.querySelector('#question-text').value='Unsubmitted fictional question for case Start';
    document.querySelector('#report-text').value='Unsubmitted original fictional source text';
    const picker=document.querySelector('#case-picker');
    picker.value='CASE-OTHER';picker.dispatchEvent(new Event('change'));
   })()""")
   cd.wait("document.querySelector('#case-picker').value==='CASE-START' && document.querySelector('#notice').textContent.includes('Save or explicitly clear')",
           'case switch veto preserves unfinished source and question')
   assert cd.evaluate("document.querySelector('#question-text').value==='Unsubmitted fictional question for case Start'")
   assert cd.evaluate("document.querySelector('#report-text').value==='Unsubmitted original fictional source text'")
   assert cd.evaluate("document.querySelector('#source-file').files.length===1")
   assert cd.evaluate("document.querySelector('#source-upload-preview').textContent") == ORIGINAL.decode('utf-8'), \
    'veto must not erase the exact inspected source'
   # Clearing all three drafts is an explicit user decision. The next switch
   # must clear the file preview and must not attach any work to the other case.
   cd.evaluate("""(() => {
    document.querySelector('#question-text').value='';
    document.querySelector('#report-text').value='';
    document.querySelector('#source-file').value='';
    const picker=document.querySelector('#case-picker');
    picker.value='CASE-OTHER';picker.dispatchEvent(new Event('change'));
   })()""")
   cd.wait("document.querySelector('#case-heading').textContent==='Fictional case Other' && document.body.dataset.workspaceState==='ready'",
           'explicitly cleared drafts permit next case')
   cd.wait("document.querySelector('#source-preview-details').hidden && !document.querySelector('#source-file').files.length",
           'source intake scope reset only after accepted case switch')
   other=json.load(urlopen(url+'api/cases/CASE-OTHER/state'))
   assert not other['sources'] and not other['questions'] and not other['snapshots'], \
    'unfinished work leaked into another fictional case'
   cd.evaluate("""(() => {
    const picker=document.querySelector('#case-picker');
    picker.value='CASE-START';picker.dispatchEvent(new Event('change'));
   })()""")
   cd.wait("document.querySelector('#case-heading').textContent==='Fictional case Start' && document.body.dataset.workspaceState==='ready'",
           'original case history reselected after denied switch')
   # The same first-party intake owner must now support multiple fictional
   # originals, while this clinical Composer v2 and governed review stack
   # retains its original source authority and review history.
   duplicate=Path(tmp)/'batch-amended-duplicate.txt';duplicate.write_bytes(AMENDED)
   foreign=Path(tmp)/'batch-foreign-subject.txt'
   foreign.write_bytes(ORIGINAL.replace(b'Patient: CASE-START',b'Patient: CASE-OTHER'))
   cd.evaluate("document.querySelector('#source-intake').open=true")
   dom=cd.command('DOM.getDocument')
   input_node=cd.command('DOM.querySelector',{
      'nodeId':dom['root']['nodeId'],'selector':'#source-file'})
   cd.command('DOM.setFileInputFiles',{'files':[str(duplicate),str(foreign)],
                                      'nodeId':input_node['nodeId']})
   cd.wait("document.querySelector('#source-file').files.length===2 && !document.querySelector('#source-preview-details').hidden",
           'two fictional originals inspected before any batch writes')
   assert cd.evaluate("document.querySelector('#source-upload-preview').textContent.includes('batch-amended-duplicate.txt') && document.querySelector('#source-upload-preview').textContent.includes('batch-foreign-subject.txt')")
   assert not cd.evaluate("document.querySelector('#source-import-receipts').children.length")
   cd.evaluate("document.querySelector('#source-upload-confirm').click();document.querySelector('#source-upload-form').requestSubmit()")
   cd.wait("document.querySelector('#source-import-receipts').children.length===2",
           'separate original batch-import receipts')
   receipt_status=cd.evaluate("[...document.querySelector('#source-import-receipts').children].map(n=>n.dataset.status).join(',')")
   assert receipt_status=='duplicate,quarantined',receipt_status
   report_ready(cd,CASE,'Completed original-source preparation')
   assert 'this task remains history' in download_report(cd,downloads,CASE)
   after_batch=json.load(urlopen(url+'api/cases/'+CASE+'/state'))
   assert len(after_batch['sources'])==2,'batch duplicate created a new source version'
   assert len(after_batch['quarantines'])==1,'foreign patient was not quarantined'
   assert len(after_batch['snapshots'])==2,'batch changed the original review lineage'
   assert json.load(urlopen(url+'api/cases/CASE-OTHER/state'))['sources']==[], \
      'foreign report incorrectly attached to the other case'
   assert next(s for s in after_batch['sources'] if s['state']=='current')['sha256']==hashlib.sha256(AMENDED).hexdigest()
   cd.command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
   artifacts=os.environ.get('OI_INTAKE_ARTIFACT_DIR')
   if artifacts:
    Path(artifacts).mkdir(parents=True,exist_ok=True)
    cd.evaluate("document.querySelector('#source-intake').scrollIntoView({block:'start'})")
    shot=cd.command('Page.captureScreenshot',{'format':'png'})
    (Path(artifacts)/'workspace-desktop.png').write_bytes(base64.b64decode(shot['data']))
   cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
   cd.wait('window.innerWidth===390','mobile viewport')
   assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
   if artifacts:
    shot=cd.command('Page.captureScreenshot',{'format':'png'})
    (Path(artifacts)/'workspace-mobile.png').write_bytes(base64.b64decode(shot['data']))
   assert not cd.evaluate("window.__oiReportProbe.diagnostics.length"),cd.evaluate("JSON.stringify(window.__oiReportProbe.diagnostics)")
   print('PASS: connected intake, original inspector, pending import report/Composer invalidation, unfinished-task guard, source-bound open/completed history and real report downloads; empty database -> UI case creation -> exact disk-file intake -> timeline -> question -> recorded replay -> human-authored source-cited report -> explicit demo review -> amended disk file -> stale/open -> new draft -> reload; UTF-8/LF preserved, markup inert, mobile contained. No live model/retrieval or clinical authorization.')
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
