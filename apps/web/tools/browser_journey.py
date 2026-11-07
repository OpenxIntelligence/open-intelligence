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
from urllib.request import Request,urlopen
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
        subprocess.run([sys.executable,'-m','oi_api.evidence_catalog'],env=env,cwd=ROOT,check=True)
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
            # Add only operator-controlled fictional grants; no UI self-authorization.
            credentials[0]['actions'].extend(['case_binding_create','case_binding_read','source_import','source_read',
                                               'record_request_create','record_request_receive','record_request_read'])
            write_grants()
            def add_synthetic(path,payload):
                url='http://127.0.0.1:8000'+path
                operation=Request(url,data=json.dumps(payload).encode('utf-8'),
                    headers={'Authorization':'Bearer '+tokens[0],'Content-Type':'application/json',
                             'Accept':'application/json'},method='POST')
                with urlopen(operation,timeout=10) as response:
                    return response.status,json.load(response)
            root='/v1/patients/'+pid
            case='CASE-ALPHA'
            status,mapping=add_synthetic(root+'/case-bindings',{
                'synthetic':True,'case_id':case,'source_organization':'ORG-INSTITUTION',
                'source_system':'SYS-SYNTH','source_subject_ref':'SUBJECT-ALPHA','review_ref':'REVIEW-SYNTH'})
            assert status==201 and mapping['case_id']==case and not mapping['source_identity_verified']
            original=(
                'OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-ONE\n'
                'Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n'
                'Specimen: SPECIMEN-ONE\n'
                'Finding: marker|not-reported|Fictional café <script>literal</script>.\n'
            )
            requests_path = root + '/record-requests?case_id=' + case
            status, missing = add_synthetic(requests_path, {
                'synthetic': True, 'request_key': 'INITIAL-PATHOLOGY-REQUEST', 'kind': 'pathology',
                'record_label': 'Initial pathology report', 'source_organization': 'Fictional institution',
            })
            assert status == 201 and missing['duplicate'] is False
            status,receipt=add_synthetic(root+'/cases/'+case+'/sources',{
                'synthetic':True,'original_text':original})
            assert status==201 and receipt['result']=='imported'
            original_id=receipt['source_id']
            status, acquired = add_synthetic(root + '/record-requests/' + missing['request_id'] + '/receive', {
                'synthetic': True, 'case_id': case, 'source_id': original_id,
            })
            assert status == 201 and acquired['source_id'] == original_id and acquired['version'] == 1
            cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')).find(b=>b.textContent.includes('Records')).click()")
            cd.wait("Boolean(document.querySelector('[data-testid=records-workspace]'))",'actual read-only Records screen')
            assert pid in cd.evaluate("document.querySelector('[data-testid=records-patient]').textContent")
            cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
            cd.wait("document.querySelectorAll('[data-testid=case-row]').length===1",'canonical scoped case binding')
            cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
            cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1",'persisted original version in React')
            assert cd.evaluate("document.querySelector('[data-testid=source-index]').textContent").find(original_id)>=0
            assert cd.evaluate("document.querySelector('[data-testid=source-statement]').textContent.includes('<script>literal</script>')")
            assert cd.evaluate("document.querySelectorAll('[data-testid=source-statement] script').length===0")
            assert cd.evaluate("document.querySelector('[data-testid=source-index]').textContent.includes('not established')")
            # Read the real PG source-derived World Model, no generated clinical facts.
            cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')).find(b=>b.textContent.includes('Journey')).click()")
            cd.wait("Boolean(document.querySelector('[data-testid=world-workspace]'))",'source-only Journey screen')
            cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=world-projection]'))",'PG-backed world model initial source')
            assert cd.evaluate("document.querySelector('[data-testid=world-current]').textContent==='1'")
            assert cd.evaluate("document.querySelector('[data-testid=world-history-count]').textContent==='0'")
            assert cd.evaluate("document.querySelector('[data-testid=world-unresolved-count]').textContent==='1'")
            assert cd.evaluate("document.querySelector('[data-testid=world-reported-state]').textContent==='not-reported'")
            assert cd.evaluate("document.querySelector('[data-testid=world-statement]').textContent.includes('<script>literal</script>')")
            assert cd.evaluate("document.querySelectorAll('[data-testid=world-statement] script').length===0")
            assert cd.evaluate("document.querySelector('[data-testid=world-no-approval]').textContent.includes('Composer execution: unavailable')")
            initial_world_fingerprint=cd.evaluate("document.querySelector('[data-testid=world-fingerprint]').textContent")
            assert len(initial_world_fingerprint)==64
            from world_model_race_journey import exercise as exercise_world_model_races
            exercise_world_model_races(cd,patient_id=pid,case_id=case,source_id=original_id,
                original=original,fingerprint=initial_world_fingerprint,
                credentials=credentials,write_grants=write_grants)
            from source_questions_journey import exercise as exercise_source_questions
            from question_review_journey import exercise as exercise_question_review
            from followthrough_journey import exercise as exercise_followthrough, exercise_case_switch
            from question_metadata_journey import exercise as exercise_question_evidence
            from connected_question_review_journey import exercise as exercise_connected_question_review
            with exercise_source_questions(cd,original_id,credentials,write_grants) as questions, \
                 exercise_question_review(cd,pid,case,questions.original_question_id,original_id,
                     credentials,write_grants) as reviews, \
                 exercise_followthrough(cd,pid,case,questions.original_question_id,original_id,
                     credentials,write_grants) as followthrough, \
                 exercise_question_evidence(cd,pid,case,questions.original_question_id,original_id,
                     credentials,write_grants) as evidence:
                cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')).find(b=>b.textContent.includes('Records')).click()")
                amended=(
                    'OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-ONE\n'
                    'Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-12\n'
                    'Specimen: SPECIMEN-ONE\nAmends: DOC-ONE@1\n'
                    'Finding: marker|negative|Amended fictional marker is reported negative.\n'
                )
                status,new_receipt=add_synthetic(root+'/cases/'+case+'/sources',{
                    'synthetic':True,'original_text':amended})
                assert status==201 and new_receipt['version']==2
                questions.after_amendment(new_receipt['source_id'])
                reviews.after_amendment()
                followthrough.after_amendment(new_receipt['source_id'])
                cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
                cd.wait("document.querySelectorAll('[data-testid=source-version]').length===2",'versioned amendment history')
                assert cd.evaluate("document.querySelector('[data-testid=source-index]').textContent.includes('superseded')")
                assert cd.evaluate("document.querySelector('[data-testid=source-index]').textContent.includes('Amended fictional marker is reported negative.')")
                assert cd.evaluate("document.querySelectorAll('[data-testid=source-statement]').length===1")
                from reading_convergence_journey import exercise as exercise_reading
                assert cd.evaluate("Boolean(document.querySelector('[data-testid=reviewed-document-disclosure]')) && !document.querySelector('[data-testid=reviewed-document-disclosure]').open"), 'Reviewed originals start collapsed beside the structured import'
                assert cd.evaluate("!document.querySelector('[data-testid=reviewed-file]').checkVisibility()"), 'Closed reviewed intake preserves the reading-first workspace'
                exercise_reading(cd,credentials,write_grants)
                # The new Records action must recheck the canonical source before
                # offering a question draft; no implicit question save or Composer call.
                cd.evaluate("""(() => {
                  window.__oiSourceHandoffCalls=[];
                  window.__oiSourceHandoffFetch=window.fetch;
                  window.fetch=(input,init)=>{
                    const url=String(input),method=init?.method||'GET';
                    if(url.includes('/v1/'))window.__oiSourceHandoffCalls.push([method,url]);
                    return window.__oiSourceHandoffFetch(input,init);
                  };
                })()""")
                assert cd.evaluate("document.querySelectorAll('.source-row.current [data-testid=ask-source-question]').length===1")
                assert cd.evaluate("!document.querySelector('.source-row.superseded [data-testid=ask-source-question]')")
                cd.evaluate("document.querySelector('[data-testid=ask-source-question]').focus()")
                cd.command('Input.dispatchKeyEvent', {'type':'rawKeyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
                cd.command('Input.dispatchKeyEvent', {'type':'char','text':'\r','key':'Enter','windowsVirtualKeyCode':13})
                cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
                cd.wait("document.querySelector('[data-testid=question-draft-editor]')?.textContent.includes("
                        +json.dumps(new_receipt['source_id'])+")", 'source-to-question handoff after fresh authorization')
                assert cd.evaluate("document.querySelector('[data-testid=world-projection]')?.textContent.includes("
                                   +json.dumps('Amended fictional marker is reported negative.')+")")
                checks=cd.evaluate("window.__oiSourceHandoffCalls")
                assert len([c for c in checks if c[0]=='GET' and c[1].endswith('/world-model')])==1, checks
                assert not any(c[0]=='POST' or '/composer/' in c[1] for c in checks), checks
                assert cd.evaluate("document.querySelector('[data-testid=question-draft-editor]').textContent.includes('line 9')")
                cd.evaluate("document.querySelector('[data-testid=discard-question-draft]').click()")
                cd.wait("!document.querySelector('[data-testid=question-draft-editor]')",
                        'question remains unsaved and may be explicitly discarded')
                cd.evaluate("window.fetch=window.__oiSourceHandoffFetch;delete window.__oiSourceHandoffFetch;delete window.__oiSourceHandoffCalls")
                cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')).find(b=>b.textContent.includes('Journey')).click()")
                cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
                cd.wait("document.querySelector('[data-testid=world-history-count]')?.textContent==='1'",'world model retains superseded source')
                assert cd.evaluate("document.querySelector('[data-testid=world-current]').textContent==='1'")
                assert cd.evaluate("document.querySelector('[data-testid=world-unresolved-count]').textContent==='0'")
                assert cd.evaluate("document.querySelector('[data-testid=world-reported-state]').textContent==='negative'")
                assert cd.evaluate("document.querySelector('[data-testid=world-fingerprint]').textContent") != initial_world_fingerprint
                assert cd.evaluate(f"document.querySelector('[data-testid=world-projection]').textContent.includes({json.dumps(original_id)})")
                questions.finish(new_receipt['source_id'],credentials,write_grants,
                    Path(os.environ.get('OI_WEB_ARTIFACT_DIR',ROOT/'apps/web/.evidence')))
                # Actual brief responses identify the three already-persisted
                # questions independently of Review's projection and sort order.
                saved_questions = cd.evaluate("""Object.fromEntries(window.__oiBriefChecks.reads
                    .filter(r=>r.status===200).map(r=>[r.question.question_id,
                      {question:r.question.question,source_id:r.selected_source.source_id}]))""")
                assert len(saved_questions) == 3
                assert saved_questions[questions.original_question_id]['source_id'] == original_id
                # The receipt and the question now both refer to the same prior
                # original. Read the actual persisted receipt after the amendment.
                prior_actions = credentials[0]['actions'][:]
                credentials[0]['actions'] = sorted(set(prior_actions) | {
                    'record_request_read', 'patient_read', 'case_binding_read', 'source_read'})
                write_grants()
                try:
                    req = Request('http://127.0.0.1:8000' + requests_path,
                                  headers={'Authorization': 'Bearer ' + tokens[0]})
                    with urlopen(req, timeout=5) as response:
                        stored, = json.load(response)['requests']
                    assert stored['request_id'] == missing['request_id']
                    assert stored['receipt_status'] == 'source_superseded_reconciliation_required'
                    assert stored['source_reference']['source_id'] == saved_questions[questions.original_question_id]['source_id']
                    assert stored['source_reference']['version'] == 1
                    print('PASS CONNECTED ACQUISITION: the missing-record request, source question, '
                          'review return, evidence link and follow-through use the same original across amendment.')
                finally:
                    credentials[0]['actions'] = prior_actions
                    write_grants()

                current_questions = {qid:value for qid,value in saved_questions.items()
                                     if value['source_id'] == new_receipt['source_id']}
                assert len(current_questions) == 2
                authored_ids = [qid for qid,value in current_questions.items() if value['question'] ==
                    'Which original fictional report and line support this recorded marker status?']
                assert len(authored_ids) == 1
                authored_question_id = authored_ids[0]
                replacement_question_id, = set(current_questions) - {authored_question_id}
                reviews.finish(new_receipt['source_id'],credentials,write_grants,
                    Path(os.environ.get('OI_WEB_ARTIFACT_DIR',ROOT/'apps/web/.evidence')),
                    replacement_question_id=replacement_question_id,
                    authored_question_id=authored_question_id)
                followthrough.finish(new_receipt['source_id'],credentials,write_grants,
                    Path(os.environ.get('OI_WEB_ARTIFACT_DIR',ROOT/'apps/web/.evidence')),
                    current_question_id=authored_question_id)
                evidence.finish(credentials,write_grants,
                    Path(os.environ.get('OI_WEB_ARTIFACT_DIR',ROOT/'apps/web/.evidence')),
                    current_question_id=authored_question_id)
                # Add one reviewed manual record before the connected question is
                # created so its source membership is already part of that question's
                # canonical World Model snapshot. Manual selections remain separate
                # from source-authored observations.
                manual_record=b'\xef\xbb\xbfIndependently fictional record\r\nManual context marker pending.\r\n'
                manual_sha=hashlib.sha256(manual_record).hexdigest()
                status,manual_document_receipt=add_synthetic(root+'/cases/'+case+'/documents',{
                    'synthetic':True,'filename':'fictional-manual-context.txt',
                    'original_base64':base64.b64encode(manual_record).decode('ascii'),
                    'confirmed_case_id':case,'expected_sha256':manual_sha,
                    'metadata':{'document_id':'DOC-MANUAL-BROWSER','kind':'pathology',
                        'event_date':'2026-01-12','issued_at':'2026-01-12',
                        'manual_transcription_confirmed':True},
                    'findings':[{'key':'manual-marker','state':'pending',
                        'quote':'Manual context marker pending.','line':2}]})
                assert status==201 and manual_document_receipt['duplicate'] is False
                manual_document={'document_id':'DOC-MANUAL-BROWSER','selection_key':'manual-marker',
                                 'quote':'Manual context marker pending.',
                                 'source_id':manual_document_receipt['source_id'],
                                 'annotation_revision_id':manual_document_receipt['annotation_revision_id']}
                # Add the fourth question only after both three-question checks.
                connected_question = exercise_connected_question_review(cd,pid,case,new_receipt['source_id'],amended,
                    credentials,write_grants,questions)
                def restart_api():
                    nonlocal api
                    os.killpg(api.pid, signal.SIGTERM)
                    api.wait(timeout=10)
                    api=subprocess.Popen([sys.executable,'-m','oi_api'],env=env,cwd=ROOT,
                        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
                    wait_for(lambda:json.load(urlopen('http://127.0.0.1:8000/health/ready',timeout=2))['status']=='ready',
                             'restarted PostgreSQL-backed evidence API',30)
                from authored_evidence_journey import exercise as exercise_evidence
                from evidence_continuity_journey import exercise as exercise_evidence_continuity
                exercise_evidence(cd,pid,case,connected_question['question_id'],new_receipt['source_id'],
                    credentials,write_grants,directory,questions.artifacts,restart_api,add_synthetic,
                    on_report=lambda report,path,body:exercise_evidence_continuity(cd,pid,case,
                        connected_question['question_id'],new_receipt['source_id'],credentials,
                        write_grants,questions.artifacts,report,path,body),
                    manual_document=manual_document)
            # Current source metadata access is independent from the historical original bytes.
            # World Model recheck must clear the old view after source-read grant withdrawal.
            credentials[0]['actions'].remove('source_read');write_grants()
            cd.evaluate("document.querySelector('[data-testid=world-load]').click()")
            cd.wait("document.querySelector('[data-testid=world-status]').textContent.includes('unavailable or revoked')",'World Model permission revocation')
            assert cd.evaluate("!document.querySelector('[data-testid=world-projection]')")
            cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')).find(b=>b.textContent.includes('Records')).click()")
            # Read rights must be checked afresh; a denied refresh discards earlier findings.
            # The World Model denial cleared the cached cases and originals. Recheck the
            # independent mapping grant before deliberately retrying the still-denied source read.
            assert not cd.evaluate("Boolean(document.querySelector('[data-testid=source-index], [data-testid=server-original], [data-testid=load-sources]'))")
            cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
            cd.wait("Boolean(document.querySelector('[data-testid=load-sources]'))", 'fresh authorized case mapping')
            cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
            cd.wait("document.querySelector('[data-testid=records-status]').textContent.includes('Sources unavailable')",'revoked source permission erases stale view')
            assert cd.evaluate("!document.querySelector('[data-testid=source-index]')")
            credentials[0]['actions'].append('source_read');write_grants()
            cd.evaluate("Array.from(document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')).find(b=>b.textContent.includes('Overview')).click()")
            cd.wait("Boolean(document.querySelector('[data-testid=patient-card]'))",'return to patient identity after governed records inspection')
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
            from record_intake_journey import exercise
            exercise(cd,pid,directory,tokens[0],credentials,write_grants,out)
            exercise_case_switch(cd,pid,case,'CASE-WEB-INTAKE',credentials,write_grants,out,
                current_question_id=connected_question['question_id'])
            # Review boundaries exercise the two existing cases before the
            # document journey deliberately creates its third fictional case.
            from connected_question_review_journey import exercise_draft_boundaries
            exercise_draft_boundaries(cd,pid,case,'CASE-WEB-INTAKE',connected_question['question_id'],
                credentials,write_grants,connect,out)
            from reviewed_documents_journey import exercise as exercise_reviewed_documents
            exercise_reviewed_documents(cd,pid,directory,tokens[0],credentials,write_grants,out,restart_api)
            from question_manual_passages_journey import exercise as exercise_question_manual_passages
            exercise_question_manual_passages(cd,pid,tokens[0],credentials,write_grants,out)
            cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith('Overview')).click()")
            cd.wait("Boolean(document.querySelector('#patient-id'))",'Overview restored after reviewed document journey')
            from image_evidence_journey import exercise as exercise_image_evidence
            exercise_image_evidence(cd,pid,tokens[0],credentials,write_grants,directory,out,restart_api)
            from laboratory_fhir_journey import exercise as exercise_laboratory
            exercise_laboratory(cd,pid,directory,tokens[0],credentials,write_grants,out)
            from institution_identity_journey import exercise as exercise_institutions
            exercise_institutions(cd,pid,directory,tokens[0],credentials,write_grants,out)
            from oncology_episode_journey import exercise as exercise_episodes
            exercise_episodes(cd,pid,tokens[0],credentials,write_grants,out)
            credentials[0]['patient_ids']=[];write_grants();read()
            cd.wait("!document.querySelector('[data-testid=patient-card]') && document.querySelector('[data-testid=status]').textContent.includes('Patient unavailable')",'revoked read removes prior view')
            credentials[0]['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();write_grants();read()
            cd.wait("Boolean(document.querySelector('#credential'))",'expired credential clears session')
            credentials[1]['patient_ids']=[pid];write_grants();connect(1);value('#patient-id',pid);read()
            cd.wait("document.querySelector('[data-testid=status]').textContent.includes('Patient unavailable')",'cross-organization read denied')
            cd.command('Page.reload');cd.wait("Boolean(document.querySelector('#credential'))",'reload forgets credential')
            assert cd.evaluate("document.querySelector('#credential').value==='' && document.querySelector('#patient-id').value==='' && localStorage.length===0 && sessionStorage.length===0")
            from reading_convergence_journey import exercise_session_reset
            exercise_session_reset(cd,pid,case,tokens[0],credentials,write_grants)
            print('PASS: React/Vite -> actual FastAPI/PostgreSQL 16; identity/create/retry; exact case/source read, immutable amendment history, unreviewed quoted text and rights revocation; cross-organization isolation, credential expiry/reload, keyboard landmarks and mobile layout. Independently fictional records only; no clinical workflow or production identity claim.')
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
