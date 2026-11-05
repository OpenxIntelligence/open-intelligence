"""Actual browser -> canonical question -> manual context -> preserved report.

Fixtures are independently authored; no patient-derived or biomedical content.
Only the deliberate lost response is injected. All writes/grants remain real.
"""
import base64
import hashlib
import json
from urllib.request import Request, urlopen

from browser_journey import wait_for
from pdf_fixtures import text_pdf

CASE='CASE-WEB-MANUAL-CONTEXT'


def exercise(cd,patient_id,token,credentials,write_grants,artifacts):
    actions=list(credentials[0]['actions'])
    credentials[0]['actions']=sorted(set(actions)|{
        'patient_read','case_binding_create','case_binding_read','source_import','source_read','source_original_read',
        'composer_context_read','question_create','question_read','authored_evidence_read','authored_evidence_import',
        'authored_evidence_assess','evidence_report_export',
        'review_queue_read','review_return','followthrough_read','followthrough_create'})
    write_grants()
    root='/v1/patients/'+patient_id
    def operator(path,body=None):
        req=Request('http://127.0.0.1:8000'+root+path,data=None if body is None else json.dumps(body).encode(),
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(req,timeout=15) as response:return json.load(response)
    def click(selector):
        cd.evaluate('document.querySelector('+json.dumps(selector)+').click()')
    def navigate(label):
        cd.evaluate("[...document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')].find(b=>b.textContent.includes("+json.dumps(label)+')).click()')
    operator('/case-bindings',dict(synthetic=True,case_id=CASE,source_organization='FICT-ORIGIN',source_system='FICT-MANUAL',source_subject_ref='FICT-MANUAL-SUBJECT',review_ref='FICT-MANUAL-REVIEW'))
    path='/cases/'+CASE
    document_path=path+'/documents'
    fixtures=[('MANUAL-TEXT','manual-text.txt',b'Independently fictional note\nA fictional violet label is pending.\n'),
              ('MANUAL-PDF','manual-page.pdf',text_pdf([['Independently fictional page one'],['A fictional violet label is pending.']]))]
    docs=[]
    for document_id,filename,raw in fixtures:
        upload=dict(synthetic=True,filename=filename,original_base64=base64.b64encode(raw).decode())
        preview=operator(document_path+'/preview',upload)
        doc=operator(document_path,upload|dict(confirmed_case_id=CASE,expected_sha256=preview['sha256'],
            expected_extraction_sha256=preview.get('extraction_sha256'),
            metadata=dict(document_id=document_id,kind='pathology',event_date='2026-01-01',issued_at='2026-01-02',manual_transcription_confirmed=True),
            findings=[dict(key='violet',state='pending',quote='A fictional violet label is pending.',line=2)]))
        docs.append((doc,preview))
    source=operator(path+'/sources',dict(synthetic=True,original_text=(f'OI-SYNTHETIC-REPORT/1\nPatient: {CASE}\nDocument: MANUAL-PRIMARY\nType: pathology\nEvent-Date: 2026-01-01\nIssued-At: 2026-01-02\nSpecimen: FICT-MANUAL\nFinding: violet|pending|The independently invented violet context remains unresolved.\n')))
    world=operator(path+'/world-model')
    preflight=operator(path+'/composer/source-preflight',dict(synthetic=True,source_id=source['source_id'],source_line=8,
        question='Which fictional violet wording needs independent verification?',expected_source_snapshot_sha256=world['snapshot_fingerprint']))
    question=operator(path+'/questions',dict(synthetic=True,request_key='MANUAL-WEB-QUESTION',source_id=source['source_id'],source_line=8,
        question=preflight['question'],expected_source_snapshot_sha256=world['snapshot_fingerprint'],expected_preflight_sha256=preflight['preflight_sha256']))
    question_id=question['question_id'];qpath=path+'/questions/'+question_id
    other_text='Which separate fictional amber question needs verification?'
    other_preflight=operator(path+'/composer/source-preflight',dict(synthetic=True,source_id=source['source_id'],source_line=8,
        question=other_text,expected_source_snapshot_sha256=world['snapshot_fingerprint']))
    other_question=operator(path+'/questions',dict(synthetic=True,request_key='MANUAL-WEB-OTHER-QUESTION',source_id=source['source_id'],source_line=8,
        question=other_text,expected_source_snapshot_sha256=world['snapshot_fingerprint'],expected_preflight_sha256=other_preflight['preflight_sha256']))
    evidence=operator(qpath+'/evidence',dict(synthetic=True,request_key='MANUAL-WEB-EVIDENCE',content_item='abstract',
        original_text='OI-SYNTHETIC-EVIDENCE/1\nEvidence: MANUAL-CONTEXT-COMPARISON\nTitle: Independently fictional manual context example\nIssued-At: 2026-01-03\nRights: original-synthetic\nStatement: A separate fictional worksheet leaves the invented violet label uncertain.\n',
        permissions={item:{'store':'allowed','display':'allowed','redistribute':'allowed'} for item in ('metadata','abstract')}))
    packet=operator(qpath+'/evidence');ev=packet['evidence'][0]
    assessment=operator(qpath+'/evidence-assessments',dict(synthetic=True,request_key='MANUAL-WEB-ASSESSMENT',evidence_id=evidence['evidence_id'],
        evidence_sha256=ev['sha256'],rights_sha256=ev['rights_sha256'],expected_source_snapshot_sha256=world['snapshot_fingerprint'],
        expected_preflight_sha256=preflight['preflight_sha256'],quote='invented violet label uncertain',relation='unknown',applicability='unknown',
        rationale='This authored example requires independent source and relevance verification.'))
    cd.evaluate("""(()=>{const original=window.fetch;window.__manualJourney={reads:[],posts:[],taskWrites:0,allWrites:0,lose:true,restore:()=>{window.fetch=original;}};
        window.fetch=async(input,init)=>{const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
        if(['POST','PUT','PATCH','DELETE'].includes(init?.method))window.__manualJourney.allWrites++;
        if(path.endsWith('/followthrough')&&init?.method==='POST')window.__manualJourney.taskWrites++;
        const response=await original.call(window,input,init);
        if(path.endsWith('/manual-passages')){const body=await response.clone().json();
            if(init?.method==='POST'){window.__manualJourney.posts.push({body:String(init.body),status:response.status,response:body});
                if(window.__manualJourney.lose&&response.status===201){window.__manualJourney.lose=false;throw TypeError('Deliberately lost actual committed passage response');}}
            else window.__manualJourney.reads.push({status:response.status,body});}
        return response;};})()""")
    def open_workspace():
        navigate('Records');click('[data-testid=load-cases]')
        cd.wait("[...document.querySelectorAll('[data-testid=case-row]')].some(r=>r.textContent.includes("+json.dumps(CASE)+'))','manual context case')
        cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(r=>r.textContent.includes("+json.dumps(CASE)+")).querySelector('[data-testid=load-sources]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=source-index]'))",'source authority for manual context')
        navigate('Investigations')
        cd.evaluate("[...document.querySelectorAll('.world-cases li')].find(r=>r.textContent.includes("+json.dumps(CASE)+")).querySelector('[data-testid=world-load]').click()")
        cd.wait("document.querySelector('[data-testid=world-projection]')?.textContent.includes("+json.dumps(CASE)+')','manual question world context')
        click('[data-testid=load-source-questions]')
        row='.question-items li[data-question-id="'+question_id+'"]'
        cd.wait('Boolean(document.querySelector('+json.dumps(row)+'))','manual question visible')
        click(row+' [data-testid=authored-evidence-open]')
        cd.wait("document.querySelector('[data-testid=manual-context-status]')?.textContent.includes('inspected') || document.querySelector('[data-testid=manual-context-status]')?.textContent.includes('restored') || Boolean(document.querySelector('[data-testid=manual-context-retry]'))",'fresh manual context or scoped recovery')
    try:
        open_workspace()
        from followthrough_journey import fill
        row='.question-items li[data-question-id="'+question_id+'"]'
        click(row+' [data-testid=followthrough-open-create]')
        cd.wait('Boolean(document.querySelector('+json.dumps(row+' [data-testid=followthrough-title]')+'))','manual question follow-up draft')
        draft_title='Unsent fictional manual-passage follow-up'
        fill(cd,row+' [data-testid=followthrough-title]',draft_title)
        click('[data-testid=manual-context-documents]')
        cd.wait("document.querySelectorAll('[data-testid=manual-context-document]').length===2",'saved text and PDF choices')
        for document_id,_,_ in fixtures:
            cd.evaluate("[...document.querySelectorAll('[data-testid=manual-context-document]')].find(b=>b.textContent.includes("+json.dumps(document_id)+')).click()')
            cd.wait("document.querySelector('[data-testid=question-manual-passages] legend')?.textContent.includes("+json.dumps(document_id)+')','exact saved document selection')
            click('[data-testid=manual-context-add]')
            cd.wait("document.querySelector('[data-testid=manual-context-status]')?.textContent.includes('selected locally')",'exact passage resolved under authority')
        assert cd.evaluate("document.querySelectorAll('[data-testid=manual-context-selected] blockquote').length")==2
        # Unsent passage choices survive navigation and fresh authority checks;
        # neither navigation nor refresh is a passage write.
        assert cd.evaluate('window.__manualJourney.posts.length')==0
        navigate('Overview')
        agenda='[data-testid=second-opinion-agenda-item][data-question-id="'+question_id+'"]'
        cd.wait('Boolean(document.querySelector('+json.dumps(agenda+' [data-testid=second-opinion-resume-passages]')+'))','unsent passage reminder on exact Overview question')
        assert cd.evaluate("document.querySelector('[data-testid=second-opinion-passage-drafts]').textContent.includes('not yet attached')")
        cd.evaluate('document.querySelector('+json.dumps(agenda)+').scrollIntoView()')
        screenshot=cd.command('Page.captureScreenshot',{'format':'png'})
        (artifacts/'manual-context-resume-agenda.png').write_bytes(base64.b64decode(screenshot['data']))
        click(agenda+' [data-testid=second-opinion-resume-passages]')
        cd.wait("document.querySelectorAll('[data-testid=manual-context-selected] blockquote').length===2 && "
                "document.querySelector('[data-testid=manual-context-status]')?.textContent.includes('restored')",'unsent text and PDF choices reauthorized')
        cd.wait("document.activeElement?.id==='manual-context-heading'",'resume action focuses the freshly opened passage panel')
        assert cd.evaluate('document.querySelector('+json.dumps(row+' [data-testid=question-unsent-passages]')+').textContent.includes("not yet attached")')
        click('[data-testid=evidence-refresh]')
        cd.wait("document.querySelectorAll('[data-testid=manual-context-selected] blockquote').length===2 && "
                "Boolean(document.querySelector('[data-testid=manual-context-unsaved]'))",'evidence refresh retains unsent passage choices')
        open_workspace()
        cd.wait("document.querySelectorAll('[data-testid=manual-context-selected] blockquote').length===2 && "
                "Boolean(document.querySelector('[data-testid=manual-context-unsaved]'))",'case, source and world refresh retains reauthorized unsent passages')
        assert cd.evaluate('window.__manualJourney.posts.length')==0
        click('[data-testid=manual-context-save]')
        cd.wait("Boolean(document.querySelector('[data-testid=manual-context-retry]'))",'lost committed response retains exact intent')
        navigate('Overview')
        agenda='[data-testid=second-opinion-agenda-item][data-question-id="'+question_id+'"]'
        cd.wait('Boolean(document.querySelector('+json.dumps(agenda)+'))','same canonical question in preparation')
        assert cd.evaluate('document.querySelector('+json.dumps(agenda)+').textContent.includes('+json.dumps(preflight['question'])+')')
        click('[data-testid=continuity-followthrough-refresh]')
        cd.wait('Boolean(document.querySelector('+json.dumps(agenda+' [data-testid=second-opinion-question-work-empty]')+'))','independently authorized empty task history')
        assert not cd.evaluate("document.querySelector('[data-testid=second-opinion-preparation]').textContent.includes("+json.dumps(draft_title)+')')
        assert cd.evaluate("document.querySelector('[data-testid=second-opinion-context-scope]').textContent.includes('separate freshness check')")
        assert cd.evaluate('window.__manualJourney.taskWrites')==0
        screenshot=cd.command('Page.captureScreenshot',{'format':'png'})
        (artifacts/'manual-context-preparation.png').write_bytes(base64.b64decode(screenshot['data']))
        navigate('Investigations')
        cd.wait('Boolean(document.querySelector('+json.dumps(row)+'))','saved question after preparation')
        click(row+' [data-testid=authored-evidence-open]')
        cd.wait("Boolean(document.querySelector('[data-testid=manual-context-retry]'))",'navigation retains exact pending passage command')
        assert cd.evaluate('document.querySelector('+json.dumps(row+' [data-testid=followthrough-title]')+').value')==draft_title
        click('[data-testid=evidence-refresh]')
        cd.wait("Boolean(document.querySelector('[data-testid=manual-context-retry]'))",'ordinary evidence refresh retains the exact uncertain passage intent')
        credentials[0]['actions'].remove('question_create');write_grants()
        click('[data-testid=manual-context-retry]')
        cd.wait("!document.querySelector('[data-testid=question-manual-passages]')",'denied retry clears disclosure without resolving the old write')
        credentials[0]['actions'].append('question_create');write_grants()
        open_workspace()
        assert cd.evaluate("Boolean(document.querySelector('[data-testid=manual-context-retry]'))"), 'Fresh authority must retain the exact uncertain command'
        click('[data-testid=manual-context-retry]')
        cd.wait("document.querySelectorAll('[data-testid=manual-context-selected] blockquote').length===2 && !document.querySelector('[data-testid=manual-context-retry]')",'same-context retry recovered')
        posts=cd.evaluate('window.__manualJourney.posts')
        assert [p['status'] for p in posts]==[201,404,200] and len({p['body'] for p in posts})==1
        assert posts[0]['response']['revision_id']==posts[2]['response']['revision_id']
        saved_context=operator(qpath+'/manual-passages')
        assert saved_context['revision']==1 and len(saved_context['passages'])==2
        assert {p['anchor']['page'] for p in saved_context['passages']}=={None,2}
        assert len(operator(path+'/sources')['source_reported_assertions'])==1
        cd.wait("!document.querySelector('[data-testid=evidence-report-select]').disabled",'comparison available after passage save')
        click('[data-testid=evidence-report-select]')
        cd.wait("!document.querySelector('[data-testid=evidence-report-prepare]').disabled",'report bound to inspected manual context')
        click('[data-testid=manual-context-selected] li button')
        cd.wait("Boolean(document.querySelector('[data-testid=manual-context-unsaved]')) && document.querySelector('[data-testid=evidence-report-prepare]').disabled",'unsaved removal cannot silently enter report preparation')
        assert len(operator(qpath+'/manual-passages')['passages'])==2
        cd.evaluate("[...document.querySelectorAll('[data-testid=question-manual-passages] button')].find(b=>b.textContent==='Refresh attached passages').click()")
        cd.wait("document.querySelectorAll('[data-testid=manual-context-selected] blockquote').length===1 && "
                "Boolean(document.querySelector('[data-testid=manual-context-unsaved]'))",'unsent removal retained through fresh context checks')
        click('[data-testid=manual-context-discard]')
        cd.wait("!document.querySelector('[data-testid=evidence-report-prepare]').disabled && document.querySelectorAll('[data-testid=manual-context-selected] blockquote').length===2",'explicit discard restores saved report binding')
        click('[data-testid=evidence-report-prepare]')
        cd.wait("Boolean(document.querySelector('[data-testid=evidence-report-open]'))",'preserved manual report')
        packet=operator(qpath+'/evidence');report_id=packet['reports'][0]['report_id']
        click('[data-testid=evidence-report-open]')
        cd.wait("Boolean(document.querySelector('[data-testid=evidence-report-preview]'))",'manual report readable')
        report=operator(qpath+'/evidence-reports/'+report_id)
        assert report['snapshot']['manual_passages']=={k:v for k,v in saved_context.items() if k!='access_receipt_id'}
        assert 'physical page 2' in report['body'] and 'ADDITIONAL MANUAL RECORD CONTEXT' in report['body']
        # Positive control for the post-revocation leak check below: while
        # source_original_read is still granted, the exact manual quotation
        # is present in the authorized evidence-report body (renderer emits
        # 'Exact manual quotation: "<quote>"' per selected passage). Without
        # this, the absence check after revocation would pass even for an
        # invented literal the projections never carried.
        denied_quote='A fictional violet label is pending.'
        assert denied_quote in report['body'], (
            'Positive control failed: authorized report body does not carry the manual quotation')
        destination=artifacts/'manual-context-report-download';destination.mkdir(parents=True,exist_ok=True)
        cd.command('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(destination.resolve())})
        click('[data-testid=evidence-report-download]')
        wait_for(lambda:any(p.is_file() and not p.name.endswith('.crdownload') for p in destination.iterdir()),'actual manual report download')
        download=next(p for p in destination.iterdir() if p.is_file() and not p.name.endswith('.crdownload')).read_bytes()
        assert download.partition(b'--- BEGIN PRESERVED REPORT BODY ---\n')[2]==report['body'].encode()
        # A preserved manual-context report must connect to the SAME question's
        # governed Review and operational follow-through, without promoting a
        # user-selected passage to a source assertion or clinical decision.
        queue=operator(path+'/review-queue')
        review_item=next(item for item in queue['items'] if item['question_id']==question_id)
        assert review_item['queue_fingerprint'] and review_item['review_state']=='awaiting_independent_verification'
        review_receipt=operator(qpath+'/return-for-verification',dict(
            synthetic=True,request_key='MANUAL-WEB-RETURN',
            expected_queue_fingerprint=review_item['queue_fingerprint'],
            reason='Independently verify the fictional violet wording before any decision.'))
        assert review_receipt['question_id']==question_id and review_receipt['duplicate'] is False
        returned=next(item for item in operator(path+'/review-queue')['items']
                      if item['question_id']==question_id)
        assert returned['current_return_receipt_id']==review_receipt['receipt_id']
        assert returned['review_state']=='returned_for_independent_verification'
        assert returned['clinical_approval'] is False and returned['reviewer_identity_verified'] is False
        task_command=dict(synthetic=True,request_key='MANUAL-WEB-FOLLOWTHROUGH',
            title='Verify fictional violet source wording',
            detail='Revisit the fictional question and its preserved manual-context report.',
            owner_label='',review_trigger='After independent fictional source verification',
            reason='Track an accountable next step without claiming a clinical decision.',
            source_snapshot_contract='oi.pg-source-world-model/1',
            expected_source_snapshot_sha256=world['snapshot_fingerprint'],
            expected_preflight_sha256=preflight['preflight_sha256'])
        task_receipt=operator(qpath+'/followthrough',task_command)
        task_retry=operator(qpath+'/followthrough',task_command)
        assert task_retry['duplicate'] is True and task_retry['task_id']==task_receipt['task_id']
        assert task_retry['event_id']==task_receipt['event_id']
        task=next(item for item in operator(path+'/followthrough')['tasks']
                  if item['task_id']==task_receipt['task_id'])
        assert task['question_id']==question_id and task['source_id']==source['source_id']
        assert task['status']=='created' and task['revision']==1 and task['clinical_approval'] is False
        assert task['source_snapshot_sha256']==world['snapshot_fingerprint']
        doc,preview=docs[1]
        operator(document_path+'/'+doc['source_id']+'/annotations',dict(synthetic=True,request_key='MANUAL-WEB-CORRECTION',
            expected_revision_id=doc['annotation_revision_id'],confirmed_case_id=CASE,expected_sha256=preview['sha256'],
            expected_extraction_sha256=preview['extraction_sha256'],reason='Choose narrower exact wording',
            findings=[dict(key='violet',state='indeterminate',quote='pending.',line=2)]))
        click('[data-testid=evidence-refresh]')
        cd.wait("document.querySelector('[data-testid=manual-context-status]')?.textContent.includes('changed')",'manual correction invalidates report preparation')
        assert cd.evaluate("document.querySelector('[data-testid=evidence-report-prepare]').disabled")
        historical=operator(qpath+'/evidence-reports/'+report_id)
        assert historical['state']=='historical_reassessment_required' and historical['body']==report['body'] and historical['snapshot']==report['snapshot']
        # Manual correction affects the report, not the primary structured
        # question's Review receipt or the independently recorded task history.
        # This checks truthful separation; task-level manual-dependency
        # reassessment is a future product contract, not silently inferred here.
        after_task=next(item for item in operator(path+'/followthrough')['tasks']
                        if item['task_id']==task_receipt['task_id'])
        assert after_task['history']==task['history'] and after_task['question_id']==question_id
        after_review=next(item for item in operator(path+'/review-queue')['items']
                          if item['question_id']==question_id)
        assert after_review['current_return_receipt_id']==review_receipt['receipt_id']
        assert after_review['clinical_approval'] is False
        screenshot=cd.command('Page.captureScreenshot',{'format':'png'})
        (artifacts/'manual-context-reassessment.png').write_bytes(base64.b64decode(screenshot['data']))
        # Both actions use real, separately scoped reads. The second question has
        # no attachments or report; it must never inherit the first question's.
        navigation_posts=len(cd.evaluate('window.__manualJourney.posts'))
        navigation_writes=cd.evaluate('window.__manualJourney.allWrites')
        for target_id,target_text,expected_passages in ((other_question['question_id'],other_text,0),(question_id,preflight['question'],2)):
            navigate('Overview')
            target='[data-testid=second-opinion-agenda-item][data-question-id="'+target_id+'"]'
            action=target+' [data-testid=second-opinion-open-question]'
            cd.wait('Boolean(document.querySelector('+json.dumps(action)+'))','saved-question inspection action')
            assert cd.evaluate('document.querySelector('+json.dumps(target)+').dataset.sourceContext')=='current_unreviewed_question'
            assert cd.evaluate("document.querySelector('[data-testid=second-opinion-context-scope]').textContent.includes('separate freshness check')")
            if target_id==question_id:
                cd.evaluate('document.querySelector('+json.dumps(action)+').scrollIntoView({block:"center"})')
                screenshot=cd.command('Page.captureScreenshot',{'format':'png'})
                (artifacts/'manual-context-corrected-agenda.png').write_bytes(base64.b64decode(screenshot['data']))
            prior_reads=len(cd.evaluate('window.__manualJourney.reads'))
            click(action)
            cd.wait("document.activeElement?.id==='manual-context-heading'",'saved-question action focuses attached records')
            cd.wait("document.querySelector('[data-testid=evidence-panel] .evidence-question')?.textContent==="+json.dumps(target_text),'exact saved question inspected')
            fresh='window.__manualJourney.reads.slice('+str(prior_reads)+').filter(r=>r.status===200 && r.body.question_id==='+json.dumps(target_id)+')'
            cd.wait(fresh+'.length>0','new authorized passage read after agenda action')
            latest=cd.evaluate(fresh+'.at(-1)')
            assert latest['status']==200 and latest['body']['question_id']==target_id
            assert len(latest['body']['passages'])==expected_passages
            if expected_passages==0:
                assert not cd.evaluate("Boolean(document.querySelector('[data-testid=evidence-report-open]'))")
            else:
                cd.wait("document.querySelector('[data-testid=manual-context-status]')?.textContent.includes('changed')",'corrected attached passage remains stale after Overview return')
                click('[data-testid=evidence-report-select]')
                assert cd.evaluate("document.querySelector('[data-testid=evidence-report-prepare]').disabled")
                click('[data-testid=evidence-report-open]')
                cd.wait("Boolean(document.querySelector('[data-testid=evidence-report-preview]'))",'same preserved historical report reopened')
                reopened=operator(qpath+'/evidence-reports/'+report_id)
                assert reopened['state']=='historical_reassessment_required' and reopened['body']==report['body'] and reopened['snapshot']==report['snapshot']
        assert len(cd.evaluate('window.__manualJourney.posts'))==navigation_posts
        assert cd.evaluate('window.__manualJourney.allWrites')==navigation_writes
        assert cd.evaluate('window.__manualJourney.taskWrites')==0
        credentials[0]['actions'].remove('source_original_read');write_grants()
        cd.evaluate("[...document.querySelectorAll('[data-testid=question-manual-passages] button')].find(b=>b.textContent==='Refresh attached passages').click()")
        cd.wait("!document.querySelector('[data-testid=question-manual-passages]') && !document.querySelector('[data-testid=evidence-report-preview]')",'revoked original-read clears shared manual report disclosure')
        # Distinct Review/task grants still work when a supplementary original
        # is withheld. They must not carry the denied manual quotation.
        scoped_tasks=operator(path+'/followthrough')['tasks']
        scoped_reviews=operator(path+'/review-queue')['items']
        assert next(item for item in scoped_tasks
                    if item['task_id']==task_receipt['task_id'])['clinical_approval'] is False
        assert next(item for item in scoped_reviews
                    if item['question_id']==question_id)['current_return_receipt_id']==review_receipt['receipt_id']
        # Independently authorized workflow metadata must not disclose an
        # exact quotation whose document-original permission was revoked.
        # denied_quote is defined above with its positive control (present
        # in the authorized report body while granted), so this absence
        # check compares against a real held quotation.
        assert denied_quote not in json.dumps(scoped_tasks,ensure_ascii=False), (
            'Task metadata leaked the revoked manual-document quotation')
        assert denied_quote not in json.dumps(scoped_reviews,ensure_ascii=False), (
            'Review metadata leaked the revoked manual-document quotation')
        (artifacts/'question-manual-context-workflow.json').write_text(json.dumps(dict(
            patient_id=patient_id,case_id=CASE,question_id=question_id,context=saved_context,
            report_id=report_id,report_body_sha256=report['body_sha256'],historical_state=historical['state'],
            exact_retry=True,download_bytes_equal=True,revoked_original_read_withholds=True,
            recovery_survives_refresh_and_denial=True,unsaved_removal_blocks_report=True,
            same_question_review_receipt_id=review_receipt['receipt_id'],
            same_question_followthrough_task_id=task_receipt['task_id'],
            task_exact_retry_one_record=True,manual_correction_preserves_task_history=True,
            independently_authorized_review_and_task_survive_original_denial=True,
            preparation_navigation_preserves_retry=True,unsent_task_excluded_from_agenda=True,
            unsent_passage_navigation_reauthorized=True,unsent_passage_refresh_preserved=True,
            overview_exact_question_resume=True,overview_resume_focuses_passages=True,
            agenda_inspects_each_exact_saved_question=True,corrected_passage_overview_return_verified=True,
            saved_question_navigation_passage_writes=0,saved_question_navigation_writes=0,
            unsent_passage_case_source_world_refresh_preserved=True,
            unsent_removal_refresh_preserved=True,unsent_navigation_passage_writes=0,
            navigation_task_writes=cd.evaluate('window.__manualJourney.taskWrites'),
            structured_assertion_count=1,clinical_approval=False),indent=2))
        print('PASS QUESTION MANUAL CONTEXT + HANDOFF: actual text/PDF selection, one canonical question, exact retry, immutable report/download, independent Review return and task, correction invalidation and original-read denial')
    finally:
        cd.evaluate('window.__manualJourney?.restore()')
        credentials[0]['actions']=actions;write_grants()
