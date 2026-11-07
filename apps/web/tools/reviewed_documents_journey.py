"""Actual fictional PDF -> H1 Records -> correction/history/original browser proof."""
import base64
import hashlib
import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pdf_fixtures import text_pdf
from question_review_journey import QuestionReviewChecks

CASE='CASE-WEB-REVIEWED'


def exercise(cd,patient_id,directory,token,credentials,write_grants,artifacts,restart_api):
    credentials[0]['actions']=sorted(set(credentials[0]['actions'])|{
        'source_import','source_read','source_original_read','case_binding_create','case_binding_read',
        'composer_context_read','question_create','question_read','review_queue_read','evidence_read','evidence_link'})
    write_grants()
    root='/v1/patients/'+patient_id
    def operator(path,body=None):
        req=Request('http://127.0.0.1:8000'+root+path,data=None if body is None else json.dumps(body).encode(),
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(req,timeout=15) as r:return json.load(r)
    operator('/case-bindings',dict(synthetic=True,case_id=CASE,source_organization='FICT-ORIGIN',source_system='FICT-PDF',source_subject_ref='FICT-PDF-SUBJECT',review_ref='FICT-REVIEW'))
    source_path='/cases/'+CASE+'/sources'
    original=(f'OI-SYNTHETIC-REPORT/1\nPatient: {CASE}\nDocument: PDF-CONTEXT\nType: pathology\n'
        'Event-Date: 2026-01-01\nIssued-At: 2026-01-02\nSpecimen: FICT-CONTEXT\n'
        'Finding: marker|not-reported|Independently fictional structured source beside a reviewed original.\n')
    source=operator(source_path,dict(synthetic=True,original_text=original))
    structured_sources=operator(source_path)['sources']
    # Use the existing structured source, never the manual PDF selections, for
    # this independently fictional question and its nonterminal review inbox.
    case_path='/cases/'+CASE
    preflight=operator(case_path+'/composer/source-preflight',dict(synthetic=True,
        expected_source_snapshot_sha256=operator(case_path+'/world-model')['snapshot_fingerprint'],
        source_id=source['source_id'],source_line=8,
        question='Which original wording still needs independent verification beside this fictional PDF?'))
    question=operator(case_path+'/questions',dict(synthetic=True,request_key='WEB-DOCUMENT-REVIEW-QUESTION',
        question=preflight['question'],source_id=preflight['selected_source']['source_id'],
        source_line=preflight['selected_source']['line'],
        expected_source_snapshot_sha256=preflight['source_snapshot_sha256'],
        expected_preflight_sha256=preflight['preflight_sha256']))
    question_id=question['question_id']
    returns_before=operator(case_path+'/review-queue')['receipts']
    assert returns_before==[], 'This fictional case begins without verification returns'
    prefix='/cases/'+CASE+'/documents'
    cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith('Records')).click()")
    cd.wait("Boolean(document.querySelector('[data-testid=load-cases]'))",'Records')
    cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
    cd.wait("[...document.querySelectorAll('[data-testid=case-row]')].some(e=>e.textContent.includes('CASE-WEB-REVIEWED'))",'reviewed case')
    cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes('CASE-WEB-REVIEWED')).querySelector('[data-testid=load-sources]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=reviewed-documents]'))",'reviewed intake')
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=record-import-disclosure]')) && Boolean(document.querySelector('#source-filter'))"), 'Structured intake and source reading coexist with reviewed originals'
    review=QuestionReviewChecks(cd,patient_id,CASE,question_id,source['source_id'])
    retained_reason='Please verify this fictional source wording while I inspect the separately preserved PDF.'

    def fresh_review():
        review.navigate('Review')
        prior=cd.evaluate("document.querySelector('[data-testid=review-access-receipt]')?.textContent??null")
        review.refresh()
        cd.wait("Boolean(document.querySelector('[data-testid=review-access-receipt]')) && "
                "document.querySelector('[data-testid=review-access-receipt]').textContent!=="+json.dumps(prior)
                +' && Boolean(document.querySelector('+json.dumps(review.item())+'))',
                'fresh actual review authority for the document case')
        assert cd.evaluate('document.querySelector('+json.dumps(review.item())+').dataset.sourceId')==source['source_id']

    def reason_value():
        return cd.evaluate('document.querySelector('+json.dumps(review.item())
                           +")?.querySelector('[data-testid=review-reason]')?.value??null")

    fresh_review()
    review.reason_value(question_id,retained_reason)
    review.navigate('Records')
    def toggle(opened):
        cd.evaluate("document.querySelector('[data-testid=reviewed-document-disclosure] > summary').focus()")
        assert cd.evaluate("document.activeElement===document.querySelector('[data-testid=reviewed-document-disclosure] > summary')"), 'Document disclosure summary receives keyboard focus'
        cd.command('Input.dispatchKeyEvent',{'type':'rawKeyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent',{'type':'char','text':'\r','key':'Enter','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.wait("document.querySelector('[data-testid=reviewed-document-disclosure]').open==="+str(opened).lower(),'native keyboard toggles reviewed originals')
    assert cd.evaluate("!document.querySelector('[data-testid=reviewed-document-disclosure]').open && !document.querySelector('[data-testid=reviewed-file]').checkVisibility()"), 'Reviewed intake starts closed'
    toggle(True)
    assert cd.evaluate("document.querySelector('[data-testid=reviewed-file]').checkVisibility()"), 'Reviewed file input is actually visible'
    pasted = 'Fictional pasted record — α\nSecond line  '
    cd.evaluate("""(()=>{window.__pasteFetch=window.fetch;window.__pasteRequests=0;window.fetch=(...args)=>{window.__pasteRequests++;return window.__pasteFetch(...args)};
      const field=document.querySelector('[data-testid=reviewed-paste]');
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(field,"""+json.dumps(pasted)+""");
      field.dispatchEvent(new Event('input',{bubbles:true}));})()""")
    assert cd.evaluate('window.__pasteRequests')==0
    cd.evaluate("document.querySelector('[data-testid=preview-pasted]').click()")
    cd.wait("document.querySelector('[data-testid=reviewed-preview]')?.textContent.includes("+json.dumps(hashlib.sha256(pasted.encode()).hexdigest())+")", 'exact pasted UTF-8 original preview')
    assert cd.evaluate('window.__pasteRequests')==1
    assert cd.evaluate("!document.querySelector('[data-testid=document-confirm]').checked")
    cd.evaluate('window.fetch=window.__pasteFetch;delete window.__pasteFetch;delete window.__pasteRequests')
    def click(label):
        cd.evaluate("(()=>{const button=[...document.querySelectorAll('[data-testid=reviewed-documents] button')].find(e=>e.textContent==="+json.dumps(label)+");if(!button?.checkVisibility())throw new Error('Reviewed action is hidden');button.click()})()")
    def value(selector,text):
        cd.evaluate("(()=>{const e=document.querySelector("+json.dumps(selector)+");Object.getOwnPropertyDescriptor(e.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(e,"+json.dumps(text)+");e.dispatchEvent(new Event('input',{bubbles:true}));})()")
    def upload(raw):
        path=directory/'fictional-reviewed.pdf';path.write_bytes(raw)
        doc=cd.command('DOM.getDocument');node=cd.command('DOM.querySelector',{'nodeId':doc['root']['nodeId'],'selector':'[data-testid=reviewed-file]'})
        cd.command('DOM.setFileInputFiles',{'nodeId':node['nodeId'],'files':[str(path)]})
        cd.wait("!document.querySelector('[data-testid=preview-reviewed]').disabled",'local file selected')
        before=operator(prefix)['documents']
        # Replace one identity field after a real authorized preview response.
        # No mismatched text or save control may appear before an explicit retry.
        cd.evaluate("""(() => {
          const fetchOriginal=window.fetch;
          window.fetch=async(input,init)=>{
            const path=new URL(typeof input==='string'?input:input.url,location.href).pathname;
            if(!path.endsWith('/documents/preview'))return fetchOriginal(input,init);
            window.fetch=fetchOriginal;
            const response=await fetchOriginal(input,init);
            const body=await response.json();
            if(response.status!==200||body.filename!=='fictional-reviewed.pdf')throw Error('Expected real preview');
            return new Response(JSON.stringify({...body,sha256:'0'.repeat(64)}),{
              status:response.status,headers:{'Content-Type':'application/json'}});
          };
        })()""")
        cd.evaluate("document.querySelector('[data-testid=preview-reviewed]').click()")
        cd.wait("document.querySelector('[data-testid=reviewed-status]').textContent.includes('does not match')",
                'mismatched PDF response withheld from review')
        assert cd.evaluate("!document.querySelector('[data-testid=reviewed-preview]') && !document.querySelector('[data-testid=save-reviewed]')")
        assert operator(prefix)['documents']==before
        cd.evaluate("document.querySelector('[data-testid=preview-reviewed]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=reviewed-preview]'))",'server frozen preview')
        assert operator(prefix)['documents']==before,'Preview persisted a source'
        value('[data-testid=document-id]','WEB-PDF');value('[data-testid=document-event]','2026-01-01');value('[data-testid=document-issued]','2026-01-02')
    assert operator(prefix)['documents']==[], 'Preview leaves the case document list empty'
    value('[data-testid=document-id]','WEB-PASTE');value('[data-testid=document-event]','2026-01-01');value('[data-testid=document-issued]','2026-01-02')
    click('Select line 1');click('Add exact passage')
    cd.evaluate("document.querySelector('[data-testid=document-confirm]').click()" )
    cd.evaluate("document.querySelector('[data-testid=save-reviewed]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=reviewed-receipt]'))",'confirmed paste saved')
    pasted_doc,=operator(prefix)['documents']
    with urlopen(Request('http://127.0.0.1:8000'+root+prefix+'/'+pasted_doc['source_id']+'/original',
                         headers={'Authorization':'Bearer '+token}),timeout=10) as original_response:
        assert original_response.read()==pasted.encode()
    raw=text_pdf([['Independently fictional page one'],['Marker pending.','Second selected passage.']])
    upload(raw)
    click('Select line 2 · page 2');click('Add exact passage')
    assert cd.evaluate("""document.querySelector('[data-testid=reviewed-preview] fieldset li')
        .textContent.includes('Page 2, page line 1 (extraction line 2)')""")
    cd.evaluate("document.querySelector('[data-testid=document-confirm]').click()")
    value('[data-testid=document-issued]','2026-01-03')
    assert cd.evaluate("""!document.querySelector('[data-testid=document-confirm]').checked
        && document.querySelector('[data-testid=save-reviewed]').disabled"""), 'Edited metadata requires a fresh confirmation'
    value('[data-testid=document-issued]','2026-01-02')
    cd.evaluate("document.querySelector('[data-testid=document-confirm]').click()")
    before_toggle=operator(prefix)['documents']
    cd.evaluate("window.__reviewedFile=document.querySelector('[data-testid=reviewed-file]').files[0];window.__reviewedPreview=document.querySelector('[data-testid=reviewed-preview]');window.__reviewedFetch=window.fetch;window.__reviewedRequests=0;window.fetch=(...args)=>{window.__reviewedRequests++;return window.__reviewedFetch(...args)}")
    try:
        toggle(False)
        assert cd.evaluate("!document.querySelector('[data-testid=reviewed-file]').checkVisibility()"), 'Collapsed intake is hidden'
        toggle(True)
        cd.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
        assert cd.evaluate("document.querySelector('[data-testid=reviewed-file]').files[0]===window.__reviewedFile && document.querySelector('[data-testid=reviewed-preview]')===window.__reviewedPreview"), 'Disclosure preserves the selected File and mounted preview'
        assert cd.evaluate("document.querySelector('[data-testid=document-confirm]').checked && document.querySelector('[data-testid=document-id]').value==='WEB-PDF' && document.querySelector('[data-testid=reviewed-preview]').textContent.includes('Marker pending.') && !document.querySelector('[data-testid=save-reviewed]').disabled"), 'Disclosure preserves manual selection, metadata and explicit confirmation'
        assert cd.evaluate("window.__reviewedRequests===0"), 'Disclosure must not request or persist anything'
        assert operator(prefix)['documents']==before_toggle, 'Disclosure persisted a source'
    finally:
        cd.evaluate("window.fetch=window.__reviewedFetch;delete window.__reviewedFetch;delete window.__reviewedRequests;delete window.__reviewedFile;delete window.__reviewedPreview")
    cd.evaluate("document.querySelector('[data-testid=save-reviewed]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=reviewed-receipt]'))",'durable original receipt')
    listing=operator(prefix)['documents'];assert len(listing)==2;first=next(row['source_id'] for row in listing if row['document_id']=='WEB-PDF')
    click('Inspect saved original and selection history')
    cd.wait("document.querySelector('[data-testid=reviewed-preview]')?.textContent.includes('Preserved selection history (1)')",'initial review')
    initial_document=operator(prefix+'/'+first)
    initial_revision=initial_document['revisions'][0]
    initial_key=initial_revision['findings'][0]['key']
    cd.evaluate("""document.querySelector('section[aria-label="Draft a passage question"] button').click()""")
    cd.wait("Boolean(document.querySelector('[data-testid=passage-question-draft]'))",'fresh saved PDF passage opens question draft')
    value('[data-testid=passage-question-draft]','What would resolve this pending fictional result?')
    assert cd.evaluate("""document.querySelector('section[aria-label="Draft a passage question"] blockquote').textContent""")==initial_revision['findings'][0]['quote']
    cd.evaluate("""(()=>{const original=window.fetch;window.__manualQuestionWrites=[];window.fetch=async(input,init)=>{
      const tracked=String(input).endsWith('/questions')&&init?.method==='POST';
      if(tracked)window.__manualQuestionWrites.push(init.body);
      const response=await original(input,init);
      if(tracked&&window.__manualQuestionWrites.length===1&&response.ok)throw Error('Fictional lost response');
      return response;};window.__restoreQuestionFetch=()=>{window.fetch=original};})()""")
    click('Save passage question')
    cd.wait("document.querySelector('[data-testid=save-passage-question]')?.textContent==='Retry exact save'&&!document.querySelector('[data-testid=save-passage-question]').disabled",'question save recovery offered')
    click('Refresh reviewed documents')
    cd.wait("!document.querySelector('[data-testid=passage-question-draft]')",'question panel unmounted')
    cd.wait("""[...document.querySelectorAll('button')].some(b=>b.textContent==='WEB-PDF · v1 · current'&&!b.disabled)""",'refreshed document list ready')
    click('WEB-PDF · v1 · current')
    cd.wait("""[...document.querySelectorAll('button')].some(b=>b.textContent==='Retry exact save'&&!b.disabled)""",'recovery after reopening original')
    click('Retry exact save')
    cd.wait("""document.querySelector('section[aria-label="Draft a passage question"]')?.textContent.includes('Question saved.')""",'question write recovered')
    attempts=cd.evaluate('window.__manualQuestionWrites')
    assert len(attempts)==2 and attempts[0]==attempts[1]
    cd.evaluate('window.__restoreQuestionFetch()')
    click('Open saved passage questions')
    cd.wait("document.querySelector('[data-testid=saved-passage-questions]')?.textContent.includes('What would resolve this pending fictional result?')",'saved question reopened')
    value('[data-testid=passage-evidence-query]','continuity')
    click('Search evidence catalog')
    cd.wait("document.querySelector('[data-testid=saved-passage-questions]')?.textContent.includes('FICT-RECORD-CONTINUITY@1')",'question-scoped catalog search')
    cd.evaluate("""(()=>{const original=window.fetch;window.__citationWrites=[];window.fetch=async(input,init)=>{
      const response=await original(input,init);
      if(String(input).endsWith('/evidence-links')&&init?.method==='POST'){
        window.__citationWrites.push({status:response.status,body:await response.clone().json(),command:JSON.parse(init.body)});
        if(window.__citationWrites.length===1&&response.status===201)throw Error('Fictional lost citation response');
      }
      return response;};window.__restoreCitationFetch=()=>{window.fetch=original};})()""")
    click('Save citation FICT-RECORD-CONTINUITY@1')
    try:
        cd.wait("[...document.querySelectorAll('button')].some(b=>b.textContent==='Retry exact citation save'&&!b.disabled)",'citation retry offered')
        assert cd.evaluate('window.__citationWrites[0].status')==201
        click('Refresh reviewed documents')
        cd.wait("[...document.querySelectorAll('button')].some(b=>b.textContent==='WEB-PDF · v1 · current'&&!b.disabled)",'citation original reopened')
        click('WEB-PDF · v1 · current')
        cd.wait("[...document.querySelectorAll('button')].some(b=>b.textContent==='Open saved passage questions'&&!b.disabled)",'passage question history available')
        click('Open saved passage questions')
        cd.wait("[...document.querySelectorAll('button')].some(b=>b.textContent==='Retry exact citation save'&&!b.disabled)",'citation retry survives remount')
        click('Retry exact citation save')
        cd.wait("document.querySelector('[data-testid=saved-passage-questions]')?.textContent.includes('Citation saved.')",'passage citation saved')
        writes=cd.evaluate('window.__citationWrites')
        assert len(writes)==2 and writes[0]['command']==writes[1]['command']
        assert writes[1]['status']==200 and writes[1]['body']=={**writes[0]['body'],'duplicate':True}
    except Exception:
        print('CITATION FAILURE',cd.evaluate("({writes:window.__citationWrites,visible:document.querySelector('[data-testid=saved-passage-questions]')?.textContent})"))
        raise
    finally:
        cd.evaluate('window.__restoreCitationFetch()')
    click('Open saved passage citations')
    cd.wait("document.querySelector('[data-testid=passage-citations]')?.textContent.includes('FICT-RECORD-CONTINUITY@1 · available')",'saved citation reopened')
    # Evidence access may be revoked while document access remains valid.
    # A denied *new* search must invalidate older on-screen citation metadata.
    # The source owner is unchanged; this is an information-display boundary.
    credentials[0]['actions'].remove('evidence_read');write_grants()
    click('Search evidence catalog')
    cd.wait("document.querySelector('[data-testid=saved-passage-questions]')?.textContent.includes('Evidence search unavailable.')",
            'denied citation search reported')
    assert cd.evaluate("!document.querySelector('[data-testid=passage-citations]')"), (
        'Evidence denial must hide earlier saved-citation metadata')
    assert cd.evaluate("!document.querySelector('[data-testid=saved-passage-questions]')?.textContent.includes('FICT-RECORD-CONTINUITY@1')"), (
        'A denied metadata search must not retain an earlier citation in the visible panel')
    credentials[0]['actions'].append('evidence_read');write_grants()
    click('Open saved passage citations')
    cd.wait("document.querySelector('[data-testid=passage-citations]')?.textContent.includes('FICT-RECORD-CONTINUITY@1 · available')",
            'a fresh authorized read restores the original citation')
    original_question,=operator(prefix+'/'+first+'/questions')['questions']
    assert original_question['selection']['anchor']['annotation_revision_id']==initial_revision['revision_id']

    assert not cd.evaluate("Boolean(document.querySelector('[data-testid=passage-question-draft]'))")
    selection_path=prefix+'/'+first+'/selections/'+initial_revision['revision_id']+'/'+initial_key
    initial_selection=operator(selection_path)
    assert initial_selection['anchor']['quote']=='Marker pending.'
    assert (initial_selection['anchor']['line'],initial_selection['anchor']['page'])==(2,2)
    assert initial_selection['anchor']['original_sha256']==hashlib.sha256(raw).hexdigest()
    assert initial_selection['anchor']['extraction_sha256']==initial_document['preview']['extraction_sha256']
    assert initial_selection['anchor']['classification_origin']=='user_selected'
    assert initial_selection['selection_state']=='current_unreviewed_selection'
    cd.evaluate("""document.querySelector('section[aria-label="Draft a passage question"] button').click()""")
    cd.wait("Boolean(document.querySelector('[data-testid=passage-question-draft]'))",'select passage before correction')
    value('[data-testid=passage-question-draft]','Does this fictional passage need correction?')
    cd.evaluate("""(()=>{const original=window.fetch;window.fetch=(input,init)=>{
      if(String(input).endsWith('/questions')&&init?.method==='POST'){window.fetch=original;throw Error('Dropped before sending')}
      return original(input,init);};})()""")
    click('Save passage question')
    cd.wait("document.querySelector('[data-testid=save-passage-question]')?.textContent==='Retry exact save'&&!document.querySelector('[data-testid=save-passage-question]').disabled",'uncommitted pending request')
    click('Remove finding-one');click('Select line 3 · page 2');click('Add exact passage')
    value('[data-testid=document-reason]','Correct the selected fictional passage')
    cd.evaluate("document.querySelector('[data-testid=document-confirm]').click()")
    value('[data-testid=document-reason]','Correct the second fictional passage on page two')
    assert cd.evaluate("document.querySelector('[data-testid=save-reviewed]').disabled"), 'Editing the correction reason invalidates confirmation'
    cd.evaluate("document.querySelector('[data-testid=document-confirm]').click();document.querySelector('[data-testid=save-reviewed]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=reviewed-receipt]'))",'correction receipt')
    click('Inspect saved original and selection history')
    cd.wait("document.querySelector('[data-testid=reviewed-preview]')?.textContent.includes('Preserved selection history (2)')",'preserved correction history')
    history=cd.evaluate("document.querySelector('[data-testid=reviewed-preview] details').textContent")
    assert 'Page 2, page line 1 (extraction line 2)' in history and 'Page 2, page line 2 (extraction line 3)' in history
    assert operator(source_path)['sources']==structured_sources, 'Manual selections must not enter the structured source index'
    cd.wait("""[...document.querySelectorAll('button')].some(b=>b.textContent==='Retry exact save'&&!b.disabled)""",'pending intent retained on corrected version')
    click('Retry exact save')
    cd.wait("""document.querySelector('section[aria-label="Draft a passage question"]')?.textContent.includes('Save refused.')""",'stale uncommitted retry rejected')
    assert cd.evaluate("""[...document.querySelectorAll('button')].some(b=>b.textContent.startsWith('Draft a question about')&&!b.disabled)""")
    saved=operator(prefix+'/'+first);assert saved['revisions'][0]['findings'][0]['line']==2
    assert saved['revisions'][1]['findings'][0]['line']==3
    historical_selection=operator(selection_path)
    assert historical_selection['anchor']==initial_selection['anchor']
    assert historical_selection['anchor_sha256']==initial_selection['anchor_sha256']
    assert historical_selection['selection_state']=='selection_reassessment_required'
    current_revision=saved['revisions'][1]
    current_selection_path=prefix+'/'+first+'/selections/'+current_revision['revision_id']+'/'+current_revision['findings'][0]['key']
    current_selection=operator(current_selection_path)
    assert current_selection['anchor']['quote']=='Second selected passage.'
    assert (current_selection['anchor']['line'],current_selection['anchor']['page'])==(3,2)
    assert current_selection['selection_state']=='current_unreviewed_selection'
    destination=artifacts/'reviewed-document-downloads';destination.mkdir(parents=True,exist_ok=True)
    cd.command('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(destination)})
    cd.evaluate("document.querySelector('[data-testid=download-reviewed]').click()")
    path=destination/'fictional-reviewed.pdf';deadline=time.monotonic()+10
    while not path.exists() and time.monotonic()<deadline:time.sleep(.1)
    assert path.read_bytes()==raw,'Browser download changed original PDF bytes'
    cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
    assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    cd.evaluate("document.querySelector('[data-testid=reviewed-preview]').scrollIntoView({block:'start'})")
    image=cd.command('Page.captureScreenshot',{'format':'png'});(artifacts/'h1-reviewed-document-mobile.png').write_bytes(base64.b64decode(image['data']))
    restart_api()
    assert operator(prefix+'/'+first)['revisions']==saved['revisions']
    restored_question,=operator(prefix+'/'+first+'/questions')['questions']
    assert restored_question['question_id']==original_question['question_id']
    assert restored_question['selection']['anchor']==original_question['selection']['anchor']
    assert restored_question['selection']['selection_state']=='selection_reassessment_required'
    restored_selection=operator(selection_path)
    assert restored_selection['anchor']==initial_selection['anchor']
    assert restored_selection['anchor_sha256']==initial_selection['anchor_sha256']
    assert restored_selection['access_receipt_id']!=initial_selection['access_receipt_id']
    review.navigate('Review')
    assert reason_value()==retained_reason, \
        'Inspecting and correcting a separate document must preserve the exact unsent verification reason'
    assert operator(case_path+'/review-queue')['receipts']==returns_before, 'Document work must not submit a return'

    # Hold delivery of one completed, unchanged real inbox response. A later
    # document denial must invalidate it, not merely hide the mounted panel.
    review_path=root+case_path+'/review-queue'
    cd.evaluate("""(() => {
      if(window.__oiDocumentReviewHold)throw Error('Document/review observer already installed');
      const original=window.fetch;
      const hold={original,seen:false,waiting:false,released:false,abortedAtRelease:null,
        release:null,status:null,receipt:null,questionIds:[],returnWrites:0};
      window.__oiDocumentReviewHold=hold;
      window.fetch=async(input,init)=>{
        const path=new URL(typeof input==='string'?input:input.url,location.href).pathname;
        const method=init?.method??'GET';
        if(method==='POST'&&path.endsWith('/return-for-verification'))hold.returnWrites++;
        const response=await original(input,init);
        if(!hold.seen&&method==='GET'&&path==="""+json.dumps(review_path)+"""){
          hold.seen=true;
          const body=await response.clone().json();
          hold.status=response.status;hold.receipt=body.access_receipt_id;
          hold.questionIds=(body.items??[]).map(item=>item.question_id);
          hold.waiting=true;
          return new Promise(resolve=>{hold.release=()=>{
            hold.release=null;hold.waiting=false;hold.released=true;
            hold.abortedAtRelease=Boolean(init?.signal?.aborted);resolve(response);
          };});
        }
        return response;
      };
      return true;
    })()""")
    try:
        cd.evaluate("document.querySelector('[data-testid=load-review-queue]').click()")
        cd.wait('window.__oiDocumentReviewHold.waiting', 'completed real review response held before document denial')
        assert cd.evaluate('window.__oiDocumentReviewHold.status')==200
        assert cd.evaluate('window.__oiDocumentReviewHold.questionIds')==[question_id]
        held_review_receipt=cd.evaluate('window.__oiDocumentReviewHold.receipt')
        assert held_review_receipt.startswith('ACCESS-')
        review.navigate('Records')
        toggle(True)
        click('Refresh reviewed documents')
        cd.wait("[...document.querySelectorAll('[data-testid=reviewed-documents] button')]"
                ".some(e=>e.textContent==='WEB-PDF · v1 · current')",'saved PDF available before denial')
        click('WEB-PDF · v1 · current')
        cd.wait("Boolean(document.querySelector('[data-testid=download-reviewed]'))",'saved PDF reopened after Review')
        credentials[0]['actions'].remove('source_original_read');write_grants()
        try:
            operator(selection_path)
            raise AssertionError('A passage hash cannot substitute for original-read authority')
        except HTTPError as denied:
            assert denied.code==404
            assert b'Marker pending.' not in denied.read()
            denied.close()
        before=list(destination.iterdir());cd.evaluate("document.querySelector('[data-testid=download-reviewed]').click()")
        cd.wait("!document.querySelector('[data-testid=download-reviewed]')",'revoked original cleared')
        cd.wait("!document.querySelector('[data-testid=source-index]') && document.querySelector('[data-testid=records-status]').textContent.includes('Document access unavailable')",'document denial clears the shared Records scope')
        assert cd.evaluate("!document.querySelector('[data-testid=reviewed-file]') && !document.querySelector('[data-testid=source-statement]')"), 'Denied scope unmounts local File and server quotations'
        assert list(destination.iterdir())==before,'Denied original created a download'
        review.navigate('Review')
        assert reason_value() is None, 'Document denial removes the old reason field'
        assert cd.evaluate("!document.querySelector('[data-testid=review-queue-result]')")
        cd.evaluate('window.__oiDocumentReviewHold.release()')
        cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        assert cd.evaluate('window.__oiDocumentReviewHold.released && !window.__oiDocumentReviewHold.abortedAtRelease'), \
            'The old response must be rejected by scope invalidation, not an expired fetch timeout'
        assert reason_value() is None and cd.evaluate("!document.querySelector('[data-testid=review-queue-result]')"), \
            'A late authorized inbox response cannot restore a document-denied scope'
        assert cd.evaluate('window.__oiDocumentReviewHold.returnWrites')==0, 'Navigation and denial cannot send a verification return'
    finally:
        cd.evaluate("""(() => {const hold=window.__oiDocumentReviewHold;if(hold){
          window.fetch=hold.original;hold.release?.();delete window.__oiDocumentReviewHold;
        }})()""")
    review.navigate('Records')
    credentials[0]['actions'].append('source_original_read');write_grants()
    cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
    cd.wait("document.querySelector('[data-testid=records-status]').textContent==='Select an active case to check its original source metadata.'",'explicit case permission reload')
    cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes('CASE-WEB-REVIEWED')).querySelector('[data-testid=load-sources]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=reviewed-document-disclosure]')) && Boolean(document.querySelector('#source-filter'))",'reauthorized structured source and empty document intake')
    assert cd.evaluate("!document.querySelector('[data-testid=reviewed-document-disclosure]').open && !document.querySelector('[data-testid=reviewed-preview]') && document.querySelector('[data-testid=reviewed-file]').files.length===0"), 'Fresh scope cannot restore the old file or preview'
    fresh_review()
    assert reason_value()!=retained_reason, 'Fresh authority cannot resurrect the reason cleared by document denial'
    recovered_reason='A new fictional reason after independent case and review authorization.'
    review.reason_value(question_id,recovered_reason)
    review.navigate('Records')
    review.navigate('Review')
    assert reason_value()==recovered_reason, 'Fresh authorized Review permits new typing and preserves it on navigation'
    assert operator(case_path+'/review-queue')['receipts']==returns_before, 'Unsent reasons must leave return history unchanged'
    review.navigate('Records')
    toggle(True)
    credentials[0]['actions'].remove('source_read');write_grants()
    click('Refresh reviewed documents')
    cd.wait("!document.querySelector('[data-testid=source-index]') && document.querySelector('[data-testid=records-status]').textContent.includes('Document access unavailable')",'denied document listing withdraws shared source authority')
    assert cd.evaluate("!document.querySelector('[data-testid=reviewed-file]') && !document.querySelector('[data-testid=source-statement]')"), 'Document-list denial clears both local intent and earlier server source text'
    credentials[0]['actions'].append('source_read');write_grants()
    assert operator(prefix+'/'+first)['revisions']==saved['revisions'], 'Denial and reauthorization must not mutate saved selections'
    (artifacts/'document-selection-workflow.json').write_text(json.dumps(dict(
        initial=initial_selection,historical=historical_selection,current=current_selection,
        restored=restored_selection,original_permission_denial=True,clinical_approval=False),indent=2))
    print('PASS DOCUMENT SELECTION REFERENCE: actual UI-authored PDF selections resolve through source-owned HTTP to exact original/extraction/revision/page/line; correction preserves historical anchor hash; restart preserves identity with fresh authority; original-read denial withholds passage. No canonical question or report is created from manual selections.')
    receipt=dict(patient_id=patient_id,case_id=CASE,source_id=first,original_sha256=hashlib.sha256(raw).hexdigest(),
        extraction_sha256=saved['preview']['extraction_sha256'],revision_ids=[r['revision_id'] for r in saved['revisions']],
        physical_page=2,selected_lines=[2,3],actual_download_equal=True,preview_did_not_persist=True,
        substituted_preview_withheld=True,physical_locations_in_history=True,edit_requires_reconfirmation=True,
        keyboard_disclosure=True,collapsed_state_preserved=True,disclosure_requests=0,structured_intake_coexists=True,manual_selections_excluded_from_structured_index=True,
        restart_preserved_revisions=True,revocation_created_no_download=True,denial_cleared_shared_records=True,
        reauthorization_did_not_restore_local_file=True,document_list_denial_cleared_source_text=True,
        review_question_id=question_id,review_question_source_id=source['source_id'],
        review_reason_survived_document_work=True,document_denial_cleared_review_reason=True,
        late_review_access_receipt_id=held_review_receipt,late_review_response_rejected=True,
        reauthorization_did_not_restore_review_reason=True,new_review_reason_editable=True,
        verification_return_history_unchanged=True,clinical_approval=False)
    (artifacts/'reviewed-document-workflow.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS REVIEWED DOCUMENT: actual PDF upload/preview, original custody, page-two selections, immutable correction, exact binary browser download, restart, original/list denial clears shared Records and local intent, explicit reauthorization starts empty, and 390px layout. Fictional only.')
    print('PASS DOCUMENT REVIEW CONTINUITY: exact unsent reason survives document inspection/correction; actual original denial clears it and rejects a held real inbox response; fresh case/inbox authority permits new text without resurrecting old text or writing a return.')
