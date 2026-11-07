"""Actual Records review and three-institution custody with fictional originals."""
import base64
import hashlib
import json
from urllib.request import Request, urlopen
from laboratory_fhir_journey import fictional_bundle, SUBJECT
from followthrough_journey import fill, click

CASE='CASE-WEB-INSTITUTIONS'


def exercise(cd, patient, directory, token, credentials, write_grants, artifacts):
    credentials[0]['actions']=sorted(set(credentials[0]['actions'])|{
        'case_binding_create','case_binding_read','source_import','source_read','source_original_read','composer_context_read'})
    write_grants()
    root='/v1/patients/'+patient
    def operator(path,payload=None):
        req=Request('http://127.0.0.1:8000'+root+path,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(req,timeout=10) as response:return json.load(response)
    operator('/case-bindings',{'synthetic':True,'case_id':CASE,'source_organization':'FICT-INSTITUTION-ONE',
        'source_system':'FICT-INSTITUTION-SYSTEM','source_subject_ref':SUBJECT,'review_ref':'FICT-INSTITUTION-PRIMARY'})
    def navigate(name):
        cd.evaluate('[...document.querySelectorAll("nav button")].find(e=>e.textContent.startsWith('+json.dumps(name)+')).click()')
    navigate('Overview');fill(cd,'#patient-id',patient)
    cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
    cd.wait("document.querySelector('[data-testid=patient-card]')?.textContent.includes("+json.dumps(patient)+")",'institution patient')
    navigate('Records');click(cd,'[data-testid=load-cases]')
    cd.wait('[...document.querySelectorAll("[data-testid=case-row]")].some(e=>e.textContent.includes('+json.dumps(CASE)+'))','institution case')
    cd.evaluate('[...document.querySelectorAll("[data-testid=case-row]")].find(e=>e.textContent.includes('+json.dumps(CASE)+')).querySelector("[data-testid=load-sources]").click()')
    cd.wait('document.querySelector("[data-testid=source-index]")?.textContent.includes('+json.dumps(CASE)+')','institution sources')
    cd.evaluate('document.querySelector("[data-testid=record-import-disclosure]").open=true;document.querySelector("[data-testid=institution-identities]").open=true')
    panel='[data-testid=institution-identities]'
    def action(label):
        expression='[...document.querySelectorAll('+json.dumps(panel+' button')+')].find(e=>e.textContent==='+json.dumps(label)+')'
        cd.wait(expression+' && !'+expression+'.disabled','enabled '+label)
        cd.evaluate(expression+'.click()')
    def refresh():
        action('Refresh identities')
        cd.wait('document.querySelector("[data-testid=institution-status]")?.textContent.startsWith("Current institution")','fresh institution list')
    def propose(org,subject):
        fill(cd,'[data-testid=institution-org]',org);fill(cd,'[data-testid=institution-system]','FICT-INSTITUTION-SYSTEM')
        fill(cd,'[data-testid=institution-subject]',subject);click(cd,'[data-testid=institution-propose]')
        cd.wait('document.querySelector("[data-testid=institution-status]")?.textContent.startsWith("Identity decision saved")','quarantined proposal saved')
        refresh()
        row=next(x for x in operator('/cases/'+CASE+'/institution-identities')['identities']
                 if x['source_organization']==org and x['source_subject_ref']==subject)
        assert row['status']=='quarantined';return row['identity_id']
    def decide(identity,label):
        fill(cd,'[data-testid=institution-review]','FICT-EXPLICIT-REVIEW')
        selector='[data-identity="'+identity+'"]'
        expression='[...document.querySelectorAll('+json.dumps(selector+' button')+')].find(e=>e.textContent==='+json.dumps(label)+')'
        cd.evaluate(expression+'.click()')
    def import_file(raw,identity=None,previous=None):
        refresh()
        if identity:
            cd.evaluate("(()=>{const e=document.querySelector('[data-testid=institution-select]');e.value="+json.dumps(identity)+";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        filename=directory/'fictional-institution-lab.json';filename.write_bytes(raw)
        cd.command('DOM.enable');document=cd.command('DOM.getDocument')
        node=cd.command('DOM.querySelector',{'nodeId':document['root']['nodeId'],'selector':'[data-testid=laboratory-file]'})
        cd.command('DOM.setFileInputFiles',{'nodeId':node['nodeId'],'files':[str(filename)]})
        cd.wait('document.querySelector("[data-testid=laboratory-local-original]")?.textContent==='+json.dumps(raw.decode()),'institution original inspected')
        if previous:
            cd.evaluate("(()=>{const e=document.querySelector('[data-testid=laboratory-predecessor]');e.value="+json.dumps(previous)+";e.dispatchEvent(new Event('change',{bubbles:true}));})()")
        click(cd,'[data-testid=laboratory-confirm]');click(cd,'[data-testid=laboratory-import]')
        cd.wait('document.querySelector("[data-testid=laboratory-status]")?.textContent.startsWith("Laboratory original saved")','institution original saved')
        cd.wait('!document.querySelector("[data-testid=load-cases]").disabled','source refresh completed')
        rows=operator('/cases/'+CASE+'/sources')['sources']
        return next(x for x in rows if x['sha256']==hashlib.sha256(raw).hexdigest() and x['state']=='current'
                    and (x['document_id'].startswith('F-') if identity else not x['document_id'].startswith('F-')))
    # Institution names and local resource numbers are authored test values only.
    first=import_file(fictional_bundle())
    imported=[first];identities=[]
    for suffix in ('TWO','THREE'):
        identity=propose('FICT-INSTITUTION-'+suffix,SUBJECT)
        decide(identity,'Link to this case')
        cd.wait('document.querySelector("[data-testid=institution-status]")?.textContent.startsWith("Identity decision saved")','explicit institution linked')
        # Distinct raw issued timestamps, identical local report and subject numbers.
        raw=fictional_bundle().replace(b'2026-04-04T12:00:00Z',('2026-04-0'+('6' if suffix=='TWO' else '7')+'T12:00:00Z').encode())
        imported.append(import_file(raw,identity));identities.append(identity)
    assert len({row['document_id'] for row in operator('/cases/'+CASE+'/sources')['sources']})==3
    conflict=propose('FICT-INSTITUTION-TWO','FICT-WRONG-PATIENT')
    decide(conflict,'Link to this case')
    cd.wait('document.querySelector("[data-testid=institution-status]")?.textContent.includes("remains unresolved")','ambiguous identity denied')
    action('Dismiss request recovery');refresh()
    assert next(row for row in operator('/cases/'+CASE+'/institution-identities')['identities'] if row['identity_id']==conflict)['status']=='quarantined'
    decide(conflict,'Reject match')
    cd.wait('document.querySelector("[data-testid=institution-status]")?.textContent.startsWith("Identity decision saved")','ambiguous match rejected')
    refresh()
    # Open the exact additional-institution source through the real Records reader.
    selected=imported[-1]
    cd.evaluate('[...document.querySelectorAll("[data-testid=source-version]")].find(e=>e.querySelector("[data-testid=source-verify] dl>div:first-child code").textContent==='+json.dumps(selected['source_id'])+').querySelector("[data-testid=open-original]").click()')
    cd.wait('Boolean(document.querySelector("[data-testid=server-original]"))','qualified source original')
    assert hashlib.sha256(cd.evaluate('document.querySelector("[data-testid=server-original]").textContent').encode()).hexdigest()==selected['sha256']
    cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
    cd.evaluate('document.querySelector("[data-testid=institution-identities]").scrollIntoView({block:"start"})')
    assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    (artifacts/'institution-identities-mobile.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
    credentials[0]['purpose']='research';write_grants();action('Refresh identities')
    cd.wait('!document.querySelector("[data-testid=source-index]")','purpose change clears institutional identity and source data')
    credentials[0]['purpose']='operations';write_grants();navigate('Overview')
    (artifacts/'institution-identities.json').write_text(json.dumps({'patient_id':patient,'case_id':CASE,
        'sources':imported,'linked_identities':identities,'rejected_identity':conflict,
        'same_local_report_number_separate_custody':True,'purpose_denial':True,'synthetic':True},indent=2)+'\n')
    print('PASS INSTITUTIONS: actual Records proposals, explicit links, three qualified originals with equal local IDs, ambiguous match quarantine/rejection, exact original and purpose-denial clearing.')
