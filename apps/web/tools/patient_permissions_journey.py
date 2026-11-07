"""Actual React/HTTP/PostgreSQL patient permission creation, recovery and revocation."""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tests'))
from browser_journey import ChromeSession, free_port, wait_for


def main():
    if 'oi_api_test' not in os.environ.get('OI_API_DATABASE_URL', ''):
        raise RuntimeError('Disposable oi_api_test PostgreSQL database required')
    chrome = next((p for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if (p:=shutil.which(n))), None)
    if not chrome:
        raise RuntimeError('Chromium unavailable')
    with tempfile.TemporaryDirectory(prefix='oi-permissions-') as temporary:
        directory=Path(temporary); token=secrets.token_urlsafe(32)
        credential=dict(token_sha256=hashlib.sha256(token.encode()).hexdigest(),actor='ACTOR-PERMISSION',
            organization='ORG-PERMISSION',purpose='operations',patient_ids=[],
            actions=['patient_create','patient_read','source_read','patient_permissions_read','patient_permissions_manage'],
            expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        access=directory/'access.json'
        def write():
            access.write_text(json.dumps(dict(version='oi.synthetic-access/1',credentials=[credential])))
        write()
        env=dict(os.environ,PYTHONPATH=str(ROOT/'apps/api/src')+os.pathsep+str(ROOT/'src'),
                 OI_API_ACCESS_FILE=str(access),OI_API_REQUIRE_PERSISTED_GRANTS='1')
        subprocess.run([sys.executable,'-m','oi_api.migrate','upgrade','head'],cwd=ROOT,env=env,check=True)
        processes=[];cd=None
        def start_api():
            process=subprocess.Popen([sys.executable,'-m','oi_api'],cwd=ROOT,env=env,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            processes.append(process)
            wait_for(lambda:json.load(urlopen('http://127.0.0.1:8000/health/ready'))['status']=='ready','permission API',30)
            return process
        def api(path,body=None):
            req=Request('http://127.0.0.1:8000'+path,data=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            try:
                reply=urlopen(req,timeout=5)
            except HTTPError as exc:
                reply=exc
            with reply:
                return reply.status,json.load(reply)
        try:
            backend=start_api()
            code,created=api('/v1/patients',dict(synthetic=True,request_key='CREATE-PERMISSION'))
            assert code==201
            pid=created['patient_id'];credential['patient_ids']=[pid];write()
            assert api('/v1/patients/'+pid)[0]==404
            web=subprocess.Popen(['npm','run','preview'],cwd=ROOT/'apps/web',env=env,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);processes.append(web)
            wait_for(lambda:urlopen('http://127.0.0.1:4173').status==200,'React permission UI',30)
            port=free_port()
            browser=subprocess.Popen([chrome,'--headless=new','--disable-gpu','--disable-dev-shm-usage',
                '--disable-background-networking','--disable-component-update','--disable-features=OptimizationHints','--no-first-run','--disable-extensions','--no-default-browser-check',
                '--remote-allow-origins=*',f'--remote-debugging-port={port}',f'--user-data-dir={directory}/chrome','about:blank'],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);processes.append(browser)
            targets=wait_for(lambda:json.load(urlopen(f'http://127.0.0.1:{port}/json/list')),'permission browser',30)
            cd=ChromeSession(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'))
            cd.command('Page.enable');cd.command('Runtime.enable');cd.command('Page.navigate',{'url':'http://127.0.0.1:4173'})
            cd.wait("document.querySelector('[data-testid=readiness]')?.textContent==='PostgreSQL API ready'",'ready')
            def value(selector,content):
                cd.evaluate(f"(()=>{{const e=document.querySelector({json.dumps(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,{json.dumps(content)});e.dispatchEvent(new Event('input',{{bubbles:true}}));}})()")
            def click_text(text):
                cd.evaluate("[...document.querySelectorAll('button')].find(b=>b.textContent==="+json.dumps(text)+").click()")
            def console():
                cd.evaluate("document.querySelector('[data-testid=patient-permissions]').open=true")
            def nav(section):
                cd.evaluate("[...document.querySelectorAll('#workspace-navigation button')].find(b=>b.textContent==="+json.dumps(section)+").click()")
                cd.wait("document.querySelector('#workspace-navigation [aria-current=page]')?.textContent==="+json.dumps(section),'section')
            def history():
                click_text('Check permission history')
                cd.wait("Boolean(document.querySelector('#permission-actor'))",'persisted history')
            def screenshot(name,width):
                cd.command('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':width<500})
                cd.evaluate("document.querySelector('[data-testid=patient-permissions]').scrollIntoView()")
                assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                target=Path(os.environ.get('OI_WEB_ARTIFACT_DIR',str(ROOT/'verification-web/screenshots')));target.mkdir(parents=True,exist_ok=True)
                (target/name).write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
            value('#credential',token);cd.evaluate("document.querySelector('#credential').form.requestSubmit()")
            cd.wait("document.body.textContent.includes('Credential present')",'session')
            value('#patient-id',pid);console();click_text('Manage permissions for this patient ID');history()
            assert cd.evaluate("document.body.textContent.includes('Stored grants are required')")
            value('#permission-actor','ACTOR-PERMISSION');value('#permission-reference','AUTHORITY-FICTIONAL')
            value('#permission-expiry',(datetime.now()+timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M'))
            cd.evaluate("[...document.querySelectorAll('fieldset label')].find(e=>e.textContent==='patient read').querySelector('input').click()")
            cd.evaluate("document.querySelector('[data-testid=permission-confirm]').click()")
            # Drop the response only after the real server has committed it.
            cd.evaluate("""(()=>{const fetchOriginal=window.fetch;let once=true;window.permissionStatuses=[];window.fetch=async(...args)=>{
              const r=await fetchOriginal(...args);if(String(args[0]).endsWith('/permissions')&&args[1]?.method==='POST'){
                window.permissionStatuses.push(r.status);
                if(once){once=false;await r.clone().text();throw Error('synthetic lost reply');}}return r;};})()""")
            cd.evaluate("document.querySelector('[data-testid=permission-submit]').click()")
            cd.wait("document.body.textContent.includes('outcome is unknown')",'unknown receipt')
            for section in ('Labs','Imaging','Pathology','Molecular','Visits'):
                nav(section)
                assert cd.evaluate("document.querySelector('#patient-id').form.querySelector('button').disabled")
            nav('Overview');console()
            # A later refusal cannot prove that the lost first request did not commit.
            credential['actions'].remove('patient_permissions_manage');write()
            click_text('Retry exact permission change')
            cd.wait("window.permissionStatuses.length===2 && [...document.querySelectorAll('button')].some(b=>b.textContent==='Retry exact permission change'&&!b.disabled)", 'refused retry retains recovery')
            assert cd.evaluate("window.permissionStatuses[1]===404 && document.body.textContent.includes('outcome is unknown')")
            assert cd.evaluate("document.querySelector('#patient-id').form.querySelector('button').disabled")
            credential['actions'].append('patient_permissions_manage');write()
            click_text('Retry exact permission change')
            cd.wait("document.body.textContent.includes('Permission change recorded')",'exact recovery')
            code,page=api('/v1/patients/'+pid+'/permissions');assert code==200 and len(page['grants'])==1
            history();screenshot('permissions-desktop.png',1280)
            value('#patient-id',pid);cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
            cd.wait("Boolean(document.querySelector('[data-testid=patient-card]'))",'new stored read grant')
            console();click_text('Manage permissions for this patient ID');history()
            value('#permission-reference','AUTHORITY-REVOKED');cd.evaluate("document.querySelector('[data-testid=permission-confirm]').click()")
            cd.evaluate("document.querySelector('[data-testid=permission-revoke]').click()")
            cd.wait("document.body.textContent.includes('Permission change recorded')",'revocation')
            history();cd.wait("document.querySelector('[data-testid=patient-permissions]').textContent.includes('· revoked')",'revoked history')
            screenshot('permissions-mobile.png',390)
            os.killpg(backend.pid,signal.SIGTERM);backend.wait(timeout=10);start_api()
            value('#patient-id',pid);cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
            cd.wait("document.querySelector('[data-testid=status]').textContent.includes('Patient unavailable')",'restored denial')
            assert cd.evaluate("!document.querySelector('[data-testid=patient-card]')")
            assert api('/v1/patients/'+pid)[0]==404
            print('PASS PATIENT PERMISSIONS: actual UI grant, lost response/refused retry/exact recovery across all diagnostic workspaces, one stored grant, allowed read, revocation, API restart denial, desktop and mobile containment.')
        finally:
            if cd:
                cd.close()
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()


if __name__=='__main__':
    main()
