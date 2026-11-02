"""Real-browser request/reopen workflow. Original synthetic records, no model/network research."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

from browser_journey import ChromeSession, ROOT, free_port, wait_for
from browser_source_dialogs import stop


def main():
    chrome=next((p for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser')
                 if (p:=shutil.which(name))),None)
    if chrome is None: raise AssertionError('Chromium required; new-source review UI not verified')
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'))
    with tempfile.TemporaryDirectory(prefix='oi-review-browser-') as tmp:
        db=str(Path(tmp)/'case.sqlite')
        subprocess.run([sys.executable,'-m','open_intelligence','seed','--db',db],cwd=ROOT,env=env,check=True,stdout=subprocess.DEVNULL)
        port,debug=free_port(),free_port()
        server=subprocess.Popen([sys.executable,'-m','open_intelligence','serve','--db',db,'--port',str(port)],
            cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        browser=session=None
        try:
            url=f'http://127.0.0.1:{port}/'
            wait_for(lambda:urlopen(url,timeout=1).status==200,'local app')
            browser=subprocess.Popen([chrome,'--headless=new','--disable-gpu','--disable-dev-shm-usage',
                '--disable-background-networking','--no-first-run','--disable-extensions',
                '--remote-allow-origins=*',f'--remote-debugging-port={debug}',f'--user-data-dir={tmp}/chrome','about:blank'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            targets=wait_for(lambda:json.load(urlopen(f'http://127.0.0.1:{debug}/json/list',timeout=1)),'browser target')
            session=ChromeSession(next(t for t in targets if t.get('type')=='page')['webSocketDebuggerUrl'])
            session.command('Page.enable');session.command('Runtime.enable');session.command('Page.navigate',{'url':url})
            session.wait("typeof active !== 'undefined' && active?.case.case_id === 'CASE-ALPHA' && renderedCaseId === caseId",'Alpha ready')
            session.evaluate(r"""(async()=>{
              const q=await api('/api/cases/CASE-ALPHA/questions',{question:'What changed in the fictional schedule?'});
              const old=active.sources.find(s=>s.state==='current');
              const draft=await api('/api/cases/CASE-ALPHA/snapshots',{question_id:q.question_id,
                summary:'Fictional prior discussion, not a clinical conclusion.',source_ids:[old.id]});
              window.__reviewSnapshot=draft.snapshot_id;
              await api('/api/cases/CASE-ALPHA/snapshots/'+draft.snapshot_id+'/review',{reviewer_label:'Demo reader'});
              const text='OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: NEW-PLAN-BROWSER\nType: other\nEvent-Date: 2026-06-02\nIssued-At: 2026-06-02\nFinding: plan|reported|Fictional rescheduled procedure; not documented as performed.\n';
              await api('/api/cases/CASE-ALPHA/imports',{text});
              await refresh(); location.hash='#investigations';
            })()""")
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(b=>b.textContent==='Review newer source').click()")
            # Find by text instead of assuming how many action buttons were inserted.
            session.wait("document.querySelector('#snapshot-list section form textarea') !== null",'source review form')
            session.evaluate("document.querySelector('#snapshot-list section form textarea').value='Later scheduling information needs review of this fictional discussion.'; document.querySelector('#snapshot-list section form').requestSubmit()")
            session.wait("active.snapshots.find(s=>s.id===window.__reviewSnapshot)?.state==='stale'",'stale snapshot')
            session.evaluate("[...document.querySelectorAll('#snapshot-list button')].find(b=>b.textContent==='View review requests').click()")
            session.wait("document.querySelector('#snapshot-list').textContent.includes('Later scheduling information needs review')",'durable reason')
            assert session.evaluate("document.querySelector('#snapshot-list').textContent.includes('not documented as performed')")
            assert session.evaluate("!document.querySelector('#snapshot-list section form')")
            print('PASS: real-browser source-line request, stale snapshot, and durable review receipt; synthetic only.')
        except Exception:
            if session:
                print('Browser location:', session.evaluate('location.href'))
                print('Browser text:', session.evaluate('document.body?.innerText?.slice(0,1200)'))
            raise
        finally:
            if session:session.close()
            stop(browser,group=True);stop(server)


if __name__=='__main__':main()
