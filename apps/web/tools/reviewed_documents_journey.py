"""Actual fictional PDF -> H1 Records -> correction/history/original browser proof."""
import base64
import hashlib
import json
import time
from urllib.request import Request, urlopen
from pdf_fixtures import text_pdf
from question_review_journey import QuestionReviewChecks

CASE='CASE-WEB-REVIEWED'


def exercise(cd,patient_id,directory,token,credentials,write_grants,artifacts,restart_api):
    credentials[0]['actions']=sorted(set(credentials[0]['actions'])|{
        'source_import','source_read','source_original_read','case_binding_create','case_binding_read',
        'composer_context_read','question_create','question_read','review_queue_read'})
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
        cd.evaluate("document.querySelector('[data-testid=preview-reviewed]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=reviewed-preview]'))",'server frozen preview')
        assert operator(prefix)['documents']==before,'Preview persisted a source'
        value('[data-testid=document-id]','WEB-PDF');value('[data-testid=document-event]','2026-01-01');value('[data-testid=document-issued]','2026-01-02')
    raw=text_pdf([['Independently fictional page one'],['Marker pending.','Second selected passage.']])
    upload(raw)
    click('Select line 2 · page 2');click('Add exact passage')
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
    listing=operator(prefix)['documents'];assert len(listing)==1;first=listing[0]['source_id']
    click('Inspect saved original and selection history')
    cd.wait("document.querySelector('[data-testid=reviewed-preview]')?.textContent.includes('Preserved selection history (1)')",'initial review')
    click('Remove finding-one');click('Select line 3 · page 2');click('Add exact passage')
    value('[data-testid=document-reason]','Correct the selected fictional passage')
    cd.evaluate("document.querySelector('[data-testid=document-confirm]').click();document.querySelector('[data-testid=save-reviewed]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=reviewed-receipt]'))",'correction receipt')
    click('Inspect saved original and selection history')
    cd.wait("document.querySelector('[data-testid=reviewed-preview]')?.textContent.includes('Preserved selection history (2)')",'preserved correction history')
    assert operator(source_path)['sources']==structured_sources, 'Manual selections must not enter the structured source index'
    saved=operator(prefix+'/'+first);assert saved['revisions'][0]['findings'][0]['line']==2
    assert saved['revisions'][1]['findings'][0]['line']==3
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
    receipt=dict(patient_id=patient_id,case_id=CASE,source_id=first,original_sha256=hashlib.sha256(raw).hexdigest(),
        extraction_sha256=saved['preview']['extraction_sha256'],revision_ids=[r['revision_id'] for r in saved['revisions']],
        physical_page=2,selected_lines=[2,3],actual_download_equal=True,preview_did_not_persist=True,
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
