"""React -> FastAPI -> actual PostgreSQL. No mocked patient HTTP, identity or DB.

Operator-controlled synthetic grants are updated outside the UI. No real account,
PHI, clinical content, external model or production authorization is demonstrated.
"""
from datetime import datetime,timedelta,timezone
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
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests'))
from browser_journey import ChromeSession,free_port,wait_for


def main():
    if 'oi_api_test' not in os.environ.get('OI_API_DATABASE_URL',''):
        raise RuntimeError('Requires an explicitly disposable oi_api_test PostgreSQL database.')
    chrome=next((p for n in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if (p:=shutil.which(n))),None)
    if not chrome:raise RuntimeError('Chromium missing; browser verification unavailable')
    with tempfile.TemporaryDirectory(prefix='oi-h1-react-') as tmp:
        directory=Path(tmp);tokens=[secrets.token_urlsafe(32),secrets.token_urlsafe(32)]
        credentials=[{'token_sha256':hashlib.sha256(t.encode()).hexdigest(),'actor':'ACTOR-'+str(i),
          'organization':'ORG-'+str(i),'purpose':'operations','actions':['patient_create','patient_read'],
          'patient_ids':[],'expires_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}
          for i,t in enumerate(tokens)]
        def write_grants():
            p=directory/'next.json';p.write_text(json.dumps({'version':'oi.synthetic-access/1','credentials':credentials}));p.replace(directory/'access.json')
        write_grants()
        env=dict(os.environ,PYTHONPATH=str(ROOT/'apps/api/src')+os.pathsep+str(ROOT/'src'),OI_API_ACCESS_FILE=str(directory/'access.json'))
        subprocess.run([sys.executable,'-m','oi_api.migrate','upgrade','head'],env=env,cwd=ROOT,check=True)
        api=subprocess.Popen([sys.executable,'-m','oi_api'],env=env,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        web=None;browser=None;cd=None
        try:
            wait_for(lambda:json.load(urlopen('http://127.0.0.1:8000/health/ready',timeout=2))['status']=='ready','PostgreSQL-backed API',30)
            web=subprocess.Popen(['npm','run','preview'],cwd=ROOT/'apps/web',env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            wait_for(lambda:urlopen('http://127.0.0.1:4173',timeout=2).status==200,'built React server',30)
            port=free_port()
            browser=subprocess.Popen([chrome,'--headless=new','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--no-first-run','--disable-extensions','--no-default-browser-check','--remote-allow-origins=*',f'--remote-debugging-port={port}',f'--user-data-dir={directory}/chrome','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            targets=wait_for(lambda:json.load(urlopen(f'http://127.0.0.1:{port}/json/list',timeout=2)),'Chromium target',30)
            cd=ChromeSession(next(t['webSocketDebuggerUrl'] for t in targets if t['type']=='page'))
            cd.command('Page.enable');cd.command('Runtime.enable');cd.command('Page.navigate',{'url':'http://127.0.0.1:4173'})
            cd.wait("document.querySelector('[data-testid=readiness]')?.textContent==='PostgreSQL API ready'",'real proxied API readiness')
            def value(selector,text):
                # React tracks controlled input setters. Use the native setter plus a real input event.
                cd.evaluate(f"(()=>{{const e=document.querySelector({json.dumps(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,{json.dumps(text)});e.dispatchEvent(new Event('input',{{bubbles:true}}));}})()")
            def connect(index=0):
                value('#credential',tokens[index]);cd.evaluate("document.querySelector('#credential').form.requestSubmit()")
                cd.wait("document.body.textContent.includes('Credential present')",'in-memory synthetic session')
                assert cd.evaluate("!document.querySelector('#credential')")
            def read():cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
            assert cd.evaluate("document.querySelector('#patient-id').disabled")
            connect()
            cd.evaluate("document.querySelector('.create-panel').open=true;document.querySelector('#synthetic-confirm').click();document.querySelector('#synthetic-confirm').form.requestSubmit()")
            cd.wait("Boolean(document.querySelector('[data-testid=created-id] code'))",'actual persisted identity creation')
            pid=cd.evaluate("document.querySelector('[data-testid=created-id] code').textContent")
            assert pid.startswith('PAT-') and len(pid)==36
            assert cd.evaluate("!document.querySelector('[data-testid=patient-card]')")
            cd.evaluate("document.querySelector('#synthetic-confirm').form.requestSubmit()")
            cd.wait("document.querySelector('[data-testid=created-id]').textContent.includes('Existing identity recovered')",'same-key idempotent create')
            read();cd.wait("document.querySelector('[data-testid=status]').textContent.includes('Patient unavailable')",'creation confers no read grant')
            assert cd.evaluate("!document.querySelector('[data-testid=patient-card]')")
            credentials[0]['patient_ids']=[pid];write_grants();read()
            cd.wait("Boolean(document.querySelector('[data-testid=patient-card]'))",'separate grant permits canonical patient read')
            assert cd.evaluate("document.querySelector('[data-testid=patient-card]').textContent").count(pid)==1
            assert cd.evaluate('localStorage.length===0 && sessionStorage.length===0')
            assert tokens[0] not in cd.evaluate('document.documentElement.outerHTML')

            # Construct a real fictional request, original source, and
            # receipt directly through the existing H1 PostgreSQL owner.
            # Browser records must never be mocks or a second record store.
            credentials[0]['actions'].extend([
                'record_request_create', 'record_request_read',
                'record_request_receive', 'case_binding_create',
                'case_binding_revoke', 'source_import', 'source_read',
                'source_original_read'])
            write_grants()
            def post(path,payload):
                req=Request('http://127.0.0.1:8000'+path,
                    data=json.dumps(payload).encode('utf-8'),
                    headers={'Authorization':'Bearer '+tokens[0],
                             'Content-Type':'application/json'},
                    method='POST')
                with urlopen(req,timeout=10) as response:
                    return response.status,json.load(response)
            root='/v1/patients/'+pid
            status,bound=post(root+'/case-bindings',{
                'synthetic':True,'case_id':'CASE-ALPHA',
                'source_organization':'FICT-INSTITUTION',
                'source_system':'FICT-REPORTS',
                'source_subject_ref':'FICT-SUBJECT-ALPHA',
                'review_ref':'FICT-OPERATOR-REVIEW'})
            assert status==201 and bound['patient_id']==pid
            status,requested=post(root+'/record-requests',{
                'synthetic':True,'request_key':'REQUEST-FICTION-ONE',
                'kind':'pathology','record_label':'Fictional pathology report',
                'source_organization':'Unverified fictional institution'})
            assert status==201
            raw=('OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\n'
                 'Document: DOC-ONE\nType: pathology\nEvent-Date: 2026-01-10\n'
                 'Issued-At: 2026-01-11\nSpecimen: SPECIMEN-ONE\n'
                 'Finding: marker|not-reported|Independently fictional browser source.\n')
            status,imported=post(root+'/cases/CASE-ALPHA/sources',{
                'synthetic':True,'original_text':raw})
            assert status==201 and imported['source_id'].startswith('SRC-')
            sid=imported['source_id']
            status,received=post(root+'/record-requests/'+requested['request_id']+'/receive',{
                'synthetic':True,'case_id':'CASE-ALPHA','source_id':sid})
            assert status==201 and received['source_id']==sid

            cd.evaluate("document.querySelector('[data-testid=records-nav]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=load-records]'))",
                'Records navigation preserves canonical selected patient')
            assert cd.evaluate("!document.querySelector('[data-testid=original-report]')")
            cd.evaluate("document.querySelector('[data-testid=load-records]').click()")
            cd.wait("document.querySelector('[data-testid=record-requests]')?.textContent.includes('Fictional pathology report')",
                'actual authorized PostgreSQL record receipt')
            assert cd.evaluate("document.querySelector('[data-testid=record-requests]').textContent.includes('source_current_unreviewed')") is False
            assert cd.evaluate("document.querySelector('[data-testid=record-requests]').textContent.includes('not clinically reviewed')")
            assert sid in cd.evaluate("document.querySelector('[data-testid=record-requests]').textContent")
            assert cd.evaluate("!document.querySelector('[data-testid=original-report]')")
            cd.evaluate("document.querySelector('[data-testid=view-original]').click()")
            cd.wait("document.querySelector('[data-testid=original-report]')?.textContent.includes('Independently fictional browser source.')",
                'exact original requires explicit second authorization')
            assert cd.evaluate("document.querySelector('[data-testid=original-report]').textContent.includes('not clinically verified')")
            assert tokens[0] not in cd.evaluate('document.documentElement.outerHTML')
            assert cd.evaluate('localStorage.length===0 && sessionStorage.length===0')

            # The real source-owned World Model is exposed through the
            # existing patient selection and independent source_read grant.
            cd.evaluate("document.querySelector('[data-testid=world-nav]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=world-case-id]'))",
                    'World Model navigation preserves selected patient')
            assert cd.evaluate("document.querySelector('[data-testid=world-case-id]').value")=='CASE-ALPHA'
            assert cd.evaluate("!document.querySelector('[data-testid=world-model-result]')")
            cd.evaluate("document.querySelector('[data-testid=world-case-id]').form.requestSubmit()")
            cd.wait("document.querySelector('[data-testid=world-model-result]')?.textContent.includes('Independently fictional browser source.')",
                    'PG16 source World Model shows exact unreviewed quote')
            original_view=cd.evaluate("document.querySelector('[data-testid=world-model-result]').textContent")
            assert sid in original_view and "not-reported" in original_view.lower()
            assert "LINE 8" in original_view
            assert "Review not established" in original_view
            assert "Clinical approval" not in original_view

            # Viewing source observations is not an export grant. A denied
            # operation must clear the draft before any downloaded text exists.
            cd.evaluate("document.querySelector('[data-testid=brief-prepare]').click()")
            cd.wait("!document.querySelector('[data-testid=world-model-result]') && document.body.textContent.includes('Brief unavailable')",
                    'separate source_brief_export grant is required')
            assert cd.evaluate("!document.querySelector('[data-testid=brief-body]')")
            credentials[0]['actions'].append('source_brief_export');write_grants()
            cd.evaluate("document.querySelector('[data-testid=world-case-id]').form.requestSubmit()")
            cd.wait("Boolean(document.querySelector('[data-testid=brief-prepare]'))", 'reload after explicit export grant')
            cd.evaluate("document.querySelector('[data-testid=brief-prepare]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=brief-body]'))", 'authorized source-only brief preview')
            prepared=cd.evaluate("document.querySelector('[data-testid=brief-body]').textContent")
            assert sid in prepared and hashlib.sha256(raw.encode()).hexdigest() in prepared
            assert 'Original line: 8' in prepared and 'not-reported' in prepared
            assert 'Clinical review: not established.' in prepared
            assert 'No external publications or clinical guidelines' in prepared
            assert cd.evaluate("document.querySelector('[data-testid=brief-body]').children.length===0")
            downloads=directory/'downloads';downloads.mkdir()
            cd.command('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(downloads)})
            cd.evaluate("document.querySelector('[data-testid=brief-download]').click()")
            downloaded=downloads/'open-intelligence-source-brief.txt'
            wait_for(lambda:downloaded.is_file(),'freshly authorized real text download',15)
            saved_bytes=downloaded.read_bytes()
            assert saved_bytes.decode('utf-8') == cd.evaluate("document.querySelector('[data-testid=brief-body]').textContent")
            assert tokens[0].encode() not in saved_bytes
            brief_out=Path(os.environ.get('OI_WEB_ARTIFACT_DIR',ROOT/'apps/web/.evidence'))
            brief_out.mkdir(parents=True,exist_ok=True)
            for width,height,label in ((1440,1100,'desktop'),(390,844,'narrow')):
                cd.command('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
                cd.wait(f'window.innerWidth==={width}', 'source brief viewport')
                cd.evaluate("document.querySelector('[data-testid=brief-body]').scrollIntoView({block:'center'})")
                assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
                screen=cd.command('Page.captureScreenshot',{'format':'png'})
                (brief_out/f'h1-source-brief-{label}.png').write_bytes(base64.b64decode(screen['data']))
            cd.command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})

            # A correction after receipt must never silently replace the
            # previously pinned original or describe it as current.
            amended=('OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\n'
                     'Document: DOC-ONE\nType: pathology\n'
                     'Event-Date: 2026-01-10\nIssued-At: 2026-01-12\n'
                     'Specimen: SPECIMEN-ONE\nAmends: DOC-ONE@1\n'
                     'Finding: marker|negative|Amended fictional marker is negative.\n')
            status,correction=post(root+'/cases/CASE-ALPHA/sources',{
                'synthetic':True,'original_text':amended})
            assert status==201 and correction['version']==2 and correction['source_id']!=sid
            # Download is a new checked request, not a cached Blob. The old
            # view must be refused after amendment without changing old files.
            cd.evaluate("document.querySelector('[data-testid=brief-download]').click()")
            cd.wait("!document.querySelector('[data-testid=world-model-result]') && document.body.textContent.includes('Sources changed')",
                    'amendment rejects stale inspected-snapshot export')
            assert cd.evaluate("!document.querySelector('[data-testid=brief-body]')")
            assert downloaded.read_bytes()==saved_bytes
            assert [x.name for x in downloads.iterdir()]==['open-intelligence-source-brief.txt']
            cd.evaluate("document.querySelector('[data-testid=world-case-id]').form.requestSubmit()")
            cd.wait("document.querySelector('[data-testid=world-model-result]')?.textContent.includes('Amended fictional marker is negative.')",
                    'corrected PostgreSQL source replaces only current observations')
            current_view=cd.evaluate("document.querySelector('[data-testid=world-model-result]').textContent")
            assert correction['source_id'] in current_view
            assert sid in current_view  # historical source retained
            assert "Superseded source versions" in current_view
            assert "Independently fictional browser source." not in current_view
            assert "Clinical review is not connected" in current_view
            cd.evaluate("document.querySelector('[data-testid=brief-prepare]').click()")
            cd.wait("document.querySelector('[data-testid=brief-body]')?.textContent.includes('Amended fictional marker is negative.')",
                    'new authorized brief contains current correction and historical references')
            corrected_brief=cd.evaluate("document.querySelector('[data-testid=brief-body]').textContent")
            assert sid in corrected_brief and correction['source_id'] in corrected_brief
            assert 'HISTORICAL SOURCE VERSIONS' in corrected_brief
            assert 'Independently fictional browser source.' not in corrected_brief
            credentials[0]['actions'].remove('source_brief_export');write_grants()
            cd.evaluate("document.querySelector('[data-testid=brief-download]').click()")
            cd.wait("!document.querySelector('[data-testid=brief-body]') && document.body.textContent.includes('Brief unavailable')",
                    'export grant revocation clears prepared text and blocks file creation')
            assert downloaded.read_bytes()==saved_bytes
            assert [x.name for x in downloads.iterdir()]==['open-intelligence-source-brief.txt']
            # Preserve baseline source-read grant for the independent original
            # receipt and source-permission tests below.
            cd.evaluate("document.querySelector('[data-testid=records-nav]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=load-records]'))",
                    'return to records without losing patient selection')
            cd.evaluate("document.querySelector('[data-testid=load-records]').click()")
            cd.wait("document.querySelector('[data-testid=record-requests]')?.textContent.includes('Historical source')",
                'source amendment reopens operational reconciliation')
            assert sid in cd.evaluate('document.querySelector("[data-testid=record-requests]").textContent')
            assert correction['source_id'] not in cd.evaluate('document.querySelector("[data-testid=record-requests]").textContent')
            assert cd.evaluate("!document.querySelector('[data-testid=original-report]')")
            cd.evaluate("document.querySelector('[data-testid=view-original]').click()")
            cd.wait("document.querySelector('[data-testid=original-report]')?.textContent.includes('Historical / superseded')",
                'historical exact source remains accessible but flagged')
            assert cd.evaluate("document.querySelector('[data-testid=original-report]').textContent.includes('Independently fictional browser source.')")
            assert not cd.evaluate("document.querySelector('[data-testid=original-report]').textContent.includes('Amended fictional marker')")

            # Revoking source metadata rights must leave only the request
            # status while erasing both its source reference and read original.
            credentials[0]['actions'].remove('source_read');write_grants()
            cd.evaluate("document.querySelector('[data-testid=load-records]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=record-requests]')) && !document.querySelector('[data-testid=view-original]')",
                'source_read withdrawal hides identifiers after refreshed grant')
            assert cd.evaluate("!document.querySelector('[data-testid=original-report]')")
            assert sid not in cd.evaluate('document.querySelector("[data-testid=record-requests]").textContent')
            cd.evaluate("document.querySelector('[data-testid=world-nav]').click()")
            value('#world-case-id','CASE-ALPHA')
            cd.evaluate("document.querySelector('[data-testid=world-case-id]').form.requestSubmit()")
            cd.wait("document.querySelector('[data-testid=world-status]').textContent.includes('Patient unavailable')",
                    'World Model cannot bypass missing source-read grant')
            assert cd.evaluate("!document.querySelector('[data-testid=world-model-result]')")
            cd.evaluate("document.querySelector('[data-testid=records-nav]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=load-records]'))",
                    'return to records after a denied source-model read')
            credentials[0]['actions'].append('source_read')
            credentials[0]['actions'].remove('source_original_read');write_grants()
            cd.evaluate("document.querySelector('[data-testid=load-records]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=view-original]'))",
                'receipt reference is independent from original-text right')
            cd.evaluate("document.querySelector('[data-testid=view-original]').click()")
            cd.wait("document.querySelector('[data-testid=original-status]').textContent.includes('Patient unavailable')",
                'separate original-source grant denial')
            assert cd.evaluate("!document.querySelector('[data-testid=original-report]')")
            credentials[0]['actions'].append('source_original_read');write_grants()
            cd.evaluate("document.querySelector('[data-testid=view-original]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=original-report]'))",
                'original text re-authorized after independent grant')
            # Verify source-rich Records UI visually at standard and narrow width.
            records_out=Path(os.environ.get('OI_WEB_ARTIFACT_DIR',ROOT/'apps/web/.evidence'))
            records_out.mkdir(parents=True,exist_ok=True)
            cd.command('Emulation.setDeviceMetricsOverride',
                {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
            screen=cd.command('Page.captureScreenshot',{'format':'png'})
            (records_out/'h1-records-desktop.png').write_bytes(base64.b64decode(screen['data']))
            cd.command('Emulation.setDeviceMetricsOverride',
                {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
            cd.wait('window.innerWidth===390','Records narrow width')
            assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            screen=cd.command('Page.captureScreenshot',{'format':'png'})
            (records_out/'h1-records-mobile.png').write_bytes(base64.b64decode(screen['data']))
            cd.command('Emulation.setDeviceMetricsOverride',
                {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})

            credentials[0]['actions'].remove('record_request_read');write_grants()
            cd.evaluate("document.querySelector('[data-testid=load-records]').click()")
            cd.wait("document.querySelector('[data-testid=records-status]').textContent.includes('Patient unavailable')",
                'separate request-read grant denied')
            assert cd.evaluate("!document.querySelector('[data-testid=record-requests]') && !document.querySelector('[data-testid=original-report]')")
            credentials[0]['actions'].append('record_request_read');write_grants()
            status,revoked=post(root+'/case-bindings/CASE-ALPHA/revoke',{
                'synthetic':True,'reason':'Fictional identity mapping intentionally withdrawn'})
            assert status==200 and revoked['case_id']=='CASE-ALPHA'
            cd.evaluate("document.querySelector('[data-testid=load-records]').click()")
            cd.wait("document.querySelector('[data-testid=record-requests]')?.textContent.includes('binding withdrawn')",
                'revoked case binding hides original while retaining operational receipt history')
            assert cd.evaluate("!document.querySelector('[data-testid=view-original]') && !document.querySelector('[data-testid=original-report]')")
            assert sid not in cd.evaluate('document.querySelector("[data-testid=record-requests]").textContent')
            cd.evaluate("document.querySelectorAll('.rail nav button')[0].click()")
            cd.wait("Boolean(document.querySelector('#patient-id'))",
                'return to Overview without changing selected patient')

            cd.command('Accessibility.enable');tree=cd.command('Accessibility.getFullAXTree')['nodes']
            assert any(n.get('role',{}).get('value')=='main' for n in tree)
            assert any(n.get('role',{}).get('value')=='navigation' for n in tree)
            out=Path(os.environ.get('OI_WEB_ARTIFACT_DIR',ROOT/'apps/web/.evidence'));out.mkdir(parents=True,exist_ok=True)
            cd.command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
            cd.evaluate("document.querySelector('.create-panel').open=false")
            image=cd.command('Page.captureScreenshot',{'format':'png'});(out/'h1-desktop.png').write_bytes(base64.b64decode(image['data']))
            cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
            cd.wait('window.innerWidth===390','mobile width')
            assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
            image=cd.command('Page.captureScreenshot',{'format':'png'});(out/'h1-mobile.png').write_bytes(base64.b64decode(image['data']))
            credentials[0]['patient_ids']=[];write_grants();read()
            cd.wait("!document.querySelector('[data-testid=patient-card]') && document.querySelector('[data-testid=status]').textContent.includes('Patient unavailable')",'revoked read removes prior view')
            credentials[0]['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();write_grants();read()
            cd.wait("Boolean(document.querySelector('#credential'))",'expired credential clears session')
            credentials[1]['patient_ids']=[pid];write_grants();connect(1);value('#patient-id',pid);read()
            cd.wait("document.querySelector('[data-testid=status]').textContent.includes('Patient unavailable')",'cross-organization read denied')
            cd.command('Page.reload');cd.wait("Boolean(document.querySelector('#credential'))",'reload forgets credential')
            assert cd.evaluate("document.querySelector('#credential').value==='' && document.querySelector('#patient-id').value==='' && localStorage.length===0 && sessionStorage.length===0")
            print('PASS: React/Vite -> actual FastAPI/PostgreSQL 16; create/retry, independent record/source/original reads, exact source/receipt, grant withdrawal, case-binding revocation, revoked view clearing, expiry, cross-organization denial, memory-only credential, reload, accessibility landmarks and 390px layout. Fictional records only; not clinical authorization.')
        finally:
            if cd:cd.close()
            for process in (browser,web,api):
                if not process:continue
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait(timeout=5)
if __name__=='__main__':main()
