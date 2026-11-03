"""Actual fictional PDF -> H1 Records -> correction/history/original browser proof."""
import base64
import hashlib
import json
import time
from urllib.request import Request, urlopen
from pdf_fixtures import text_pdf

CASE='CASE-WEB-REVIEWED'


def exercise(cd,patient_id,directory,token,credentials,write_grants,artifacts,restart_api):
    credentials[0]['actions']=sorted(set(credentials[0]['actions'])|{'source_import','source_read','source_original_read','case_binding_create','case_binding_read'})
    write_grants()
    root='/v1/patients/'+patient_id
    def operator(path,body=None):
        req=Request('http://127.0.0.1:8000'+root+path,data=None if body is None else json.dumps(body).encode(),
                    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(req,timeout=15) as r:return json.load(r)
    operator('/case-bindings',dict(synthetic=True,case_id=CASE,source_organization='FICT-ORIGIN',source_system='FICT-PDF',source_subject_ref='FICT-PDF-SUBJECT',review_ref='FICT-REVIEW'))
    prefix='/cases/'+CASE+'/documents'
    cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith('Records')).click()")
    cd.wait("Boolean(document.querySelector('[data-testid=load-cases]'))",'Records')
    cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
    cd.wait("[...document.querySelectorAll('[data-testid=case-row]')].some(e=>e.textContent.includes('CASE-WEB-REVIEWED'))",'reviewed case')
    cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes('CASE-WEB-REVIEWED')).querySelector('[data-testid=load-sources]').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=reviewed-documents]'))",'reviewed intake')
    def click(label):
        cd.evaluate("[...document.querySelectorAll('[data-testid=reviewed-documents] button')].find(e=>e.textContent==="+json.dumps(label)+").click()")
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
    cd.evaluate("document.querySelector('[data-testid=document-confirm]').click();document.querySelector('[data-testid=save-reviewed]').click()")
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
    image=cd.command('Page.captureScreenshot',{'format':'png'});(artifacts/'h1-reviewed-document-mobile.png').write_bytes(base64.b64decode(image['data']))
    restart_api()
    assert operator(prefix+'/'+first)['revisions']==saved['revisions']
    credentials[0]['actions'].remove('source_original_read');write_grants()
    before=list(destination.iterdir());cd.evaluate("document.querySelector('[data-testid=download-reviewed]').click()")
    cd.wait("!document.querySelector('[data-testid=download-reviewed]')",'revoked original cleared')
    assert list(destination.iterdir())==before,'Denied original created a download'
    credentials[0]['actions'].append('source_original_read');write_grants()
    receipt=dict(patient_id=patient_id,case_id=CASE,source_id=first,original_sha256=hashlib.sha256(raw).hexdigest(),
        extraction_sha256=saved['preview']['extraction_sha256'],revision_ids=[r['revision_id'] for r in saved['revisions']],
        physical_page=2,selected_lines=[2,3],actual_download_equal=True,preview_did_not_persist=True,
        restart_preserved_revisions=True,revocation_created_no_download=True,clinical_approval=False)
    (artifacts/'reviewed-document-workflow.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS REVIEWED DOCUMENT: actual PDF upload/preview, original custody, page-two selections, immutable correction, exact binary browser download, restart, independent original denial and 390px layout. Fictional only.')
