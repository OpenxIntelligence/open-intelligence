"""Exercise browser file selection against canonical source API; only authored fiction.

Imported from the original identity journey after its separate patient grant.
Fixtures grant actions and bind case outside the UI; the application cannot grant itself access.
"""
import base64
import hashlib
import json
from urllib.request import Request, urlopen

CASE = 'CASE-WEB-INTAKE'
ORIGINAL = (f'OI-SYNTHETIC-REPORT/1\nPatient: {CASE}\nDocument: WEB-PATH\nType: pathology\n'
            'Event-Date: 2026-01-02\nIssued-At: 2026-01-03\nSpecimen: WEB-SPEC\n'
            'Finding: marker|not-reported|Authored fictional café <script>literal</script>; assay not tested.\n').encode('utf-8')
AMENDED = ORIGINAL.replace(b'Issued-At: 2026-01-03', b'Issued-At: 2026-01-04').replace(
    b'Finding:', b'Amends: WEB-PATH@1\nFinding:', 1).replace(b'not-reported|', b'negative|').replace(
    b'assay not tested', b'amended fictional negative assay')


def exercise(cd, patient_id, directory, token, credentials, write_grants, screenshots):
    credentials[0]['actions'] = sorted(set(credentials[0]['actions']) | {'case_binding_create', 'case_binding_read', 'source_import', 'source_read', 'source_original_read'})
    write_grants()

    def operator(path, payload=None):
        req = Request('http://127.0.0.1:8000/v1/patients/'+patient_id+path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urlopen(req, timeout=5) as response:
            return json.load(response)

    operator('/case-bindings', {'synthetic':True,'case_id':CASE,'source_organization':'FICT-ORIGIN',
              'source_system':'FICT-TEXT','source_subject_ref':'FICT-SUBJECT','review_ref':'FICT-REVIEW'})
    index_path='/cases/'+CASE+'/sources'

    def records():
        cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith('Records')).click()")
        cd.wait("Boolean(document.querySelector('[data-testid=load-cases]'))", 'existing Records workspace')
        cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=load-sources]'))", 'authorized case mapping')
        cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes('CASE-WEB-INTAKE')).querySelector('[data-testid=load-sources]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=source-index]'))", 'authorized source index')

    records()
    assert len(operator(index_path)['sources']) == 0
    assert cd.evaluate("document.querySelector('[data-testid=record-import-disclosure]').open"), 'An empty case starts with import expanded'
    cd.command('DOM.enable')

    def toggle_import():
        cd.evaluate("document.querySelector('[data-testid=record-import-disclosure]>summary').focus()")
        cd.command('Input.dispatchKeyEvent', {'type':'rawKeyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent', {'type':'char','key':'Enter','text':'\r','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})

    def upload(raw, name, expected, source_count):
        if not cd.evaluate("document.querySelector('[data-testid=record-import-disclosure]').open"):
            toggle_import()
            cd.wait("document.querySelector('[data-testid=record-import-disclosure]').open", 'keyboard opens import')
        original_count=len(operator(index_path)['sources'])
        filename=directory/name;filename.write_bytes(raw)
        document=cd.command('DOM.getDocument')
        node=cd.command('DOM.querySelector',{'nodeId':document['root']['nodeId'],'selector':'#original-file'})
        cd.command('DOM.setFileInputFiles',{'nodeId':node['nodeId'],'files':[str(filename)]})
        cd.wait("Boolean(document.querySelector('[data-testid=local-original]'))", 'explicit local original preview')
        assert cd.evaluate("document.querySelector('[data-testid=local-original]').textContent")==raw.decode()
        assert cd.evaluate("document.querySelectorAll('[data-testid=local-original] script').length===0")
        # Selecting a file does not write; only the subsequent explicit submission does.
        assert len(operator(index_path)['sources']) == original_count
        if name == 'original.txt':
            viewport=cd.evaluate('({width:innerWidth,height:innerHeight})')
            cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
            cd.evaluate("document.querySelector('[data-testid=local-original]').style.fontSize='32px';document.querySelector('#original-file').focus()")
            def key(name,code):
                cd.command('Input.dispatchKeyEvent',{'type':'rawKeyDown','key':name,'code':name,'windowsVirtualKeyCode':code})
                cd.command('Input.dispatchKeyEvent',{'type':'keyUp','key':name,'code':name,'windowsVirtualKeyCode':code})
            key('Tab',9)
            cd.wait("document.activeElement===document.querySelector('[data-testid=local-original]')", 'Tab reaches local preview before confirmation')
            assert cd.evaluate("document.activeElement.scrollHeight>document.activeElement.clientHeight"), 'Enlarged preview exercises overflow'
            key('PageDown',34)
            cd.wait("document.querySelector('[data-testid=local-original]').scrollTop>0", 'keyboard scrolls selected file before import')
            cd.wait("(()=>{const r=document.activeElement.getBoundingClientRect();const h=document.querySelector('.topbar');return r.bottom<=innerHeight&&r.top>=(h.dataset.sticky==='false'?0:h.getBoundingClientRect().bottom)})()", 'entire preview is visible below patient context')
            assert cd.evaluate("!document.querySelector('#original-confirm').checked && document.querySelector('[data-testid=import-original]').disabled"), 'Reading is not confirmation'
            assert len(operator(index_path)['sources']) == original_count, 'Keyboard inspection must not import'
            (screenshots/'local-preview-keyboard-390.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
            key('Tab',9)
            assert cd.evaluate("document.activeElement===document.querySelector('#original-confirm') && !document.activeElement.checked"), 'Tab exits reader to an unchecked confirmation'
            assert cd.evaluate("document.querySelector('[data-testid=local-original]').textContent")==raw.decode(), 'Keyboard reading preserves exact local bytes'
            cd.evaluate("document.querySelector('[data-testid=local-original]').style.removeProperty('font-size')")
            cd.command('Emulation.setDeviceMetricsOverride',{**viewport,'deviceScaleFactor':1,'mobile':False})
            print('PASS LOCAL PREVIEW KEYBOARD: actual selected file, native Tab and PageDown, visible enlarged reader, unchecked confirmation, no implicit import, exact bytes preserved.')
        cd.evaluate("document.querySelector('#original-confirm').click()")
        toggle_import()
        cd.wait("!document.querySelector('[data-testid=record-import-disclosure]').open", 'keyboard collapses import with a selection')
        assert cd.evaluate("document.activeElement===document.querySelector('[data-testid=record-import-disclosure]>summary')"), 'Focus remains on the visible disclosure'
        assert len(operator(index_path)['sources']) == original_count, 'Collapse must not import'
        toggle_import()
        cd.wait("document.querySelector('[data-testid=record-import-disclosure]').open", 'keyboard restores import')
        assert cd.evaluate("document.querySelector('[data-testid=local-original]').textContent")==raw.decode(), 'Exact preview survives collapse'
        assert cd.evaluate("document.querySelector('#original-confirm').checked"), 'Confirmation survives collapse'
        assert cd.evaluate("document.querySelector('#original-file').files[0].name")==name, 'Selected File survives collapse'
        assert len(operator(index_path)['sources']) == original_count, 'Reopen must not import'
        if name == 'original.txt':
            viewport=cd.evaluate('({width:innerWidth,height:innerHeight})')
            cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
            cd.evaluate("document.querySelector('[data-testid=record-import-disclosure]>summary').scrollIntoView({block:'start'})")
            cd.wait('document.documentElement.scrollWidth<=innerWidth+1', 'expanded import stays within narrow viewport')
            (screenshots/'import-expanded-390.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
            cd.command('Emulation.setDeviceMetricsOverride',{**viewport,'deviceScaleFactor':1,'mobile':False})


        cd.evaluate("document.querySelector('[data-testid=import-original]').click()")
        cd.wait("document.querySelector('[data-testid=import-receipt]')?.dataset.result==="+json.dumps(expected)+
                " && Boolean(document.querySelector('[data-testid=source-index]'))", 'confirmed '+expected+' receipt')
        assert len(operator(index_path)['sources'])==source_count
        cd.wait(f"document.querySelectorAll('[data-testid=source-version]').length==={source_count}", 'refreshed source metadata')

    def original(version, text):
        cd.evaluate(f"[...document.querySelectorAll('[data-testid=open-original]')].find(e=>e.textContent==='Inspect original v{version}').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=server-original]'))", 'independently authorized original read')
        assert cd.evaluate("document.querySelector('[data-testid=server-original]').textContent")==text.decode()
        assert cd.evaluate("document.querySelectorAll('[data-testid=server-original] script').length===0")

    upload(ORIGINAL,'original.txt','imported',1)
    first=operator(index_path)['sources'][0]
    assert first['sha256']==hashlib.sha256(ORIGINAL).hexdigest()
    original(1,ORIGINAL)
    upload(ORIGINAL,'duplicate.txt','duplicate',1)
    upload(AMENDED,'amended.txt','imported',2)
    index=operator(index_path)
    old=next(s for s in index['sources'] if s['version']==1)
    new=next(s for s in index['sources'] if s['version']==2)
    assert old['state']=='superseded' and old['sha256']==first['sha256']
    assert new['state']=='current' and new['sha256']==hashlib.sha256(AMENDED).hexdigest()
    assert new['supersedes_id']==old['source_id']
    original(1,ORIGINAL)
    original(2,AMENDED)
    assert cd.evaluate("document.querySelector('[data-testid=source-index]').textContent.includes('not established')")
    upload(ORIGINAL.replace(CASE.encode(),b'CASE-FOREIGN'),'foreign.txt','quarantined',2)
    assert len(operator(index_path)['source_reported_assertions'])==1
    original(2,AMENDED)
    cd.command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1200,'deviceScaleFactor':1,'mobile':False})
    cd.evaluate("document.querySelector('[data-testid=opened-original]').scrollIntoView({block:'center'})")
    image=cd.command('Page.captureScreenshot',{'format':'png'})
    (screenshots/'h1-records-desktop.png').write_bytes(base64.b64decode(image['data']))
    cd.command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
    cd.wait('window.innerWidth===390','records mobile viewport')
    assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    image=cd.command('Page.captureScreenshot',{'format':'png'})
    (screenshots/'h1-records-mobile.png').write_bytes(base64.b64decode(image['data']))
    # List grant must not confer original-text authority; previously read text must disappear.
    credentials[0]['actions'].remove('source_original_read');write_grants()
    cd.evaluate("[...document.querySelectorAll('[data-testid=open-original]')].find(e=>e.textContent==='Inspect original v2').click()")
    cd.wait("!document.querySelector('[data-testid=server-original]') && document.querySelector('[data-testid=records-status]').textContent.includes('permission denied')",'raw text denied after original-read withdrawal')
    assert len(operator(index_path)['sources'])==2
    # Current source/mapping access is independently rechecked, not inferred from prior successful load.
    credentials[0]['actions'].remove('source_read');write_grants()
    cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes('CASE-WEB-INTAKE')).querySelector('[data-testid=load-sources]').click()")
    cd.wait("!document.querySelector('[data-testid=source-index]')",'source metadata cleared on denied recheck')
    cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent==='Overview').click()")
    cd.wait("Boolean(document.querySelector('[data-testid=patient-card]'))",'original identity journey preserved')
    print('PASS IMPORT DISCLOSURE: empty case starts open; native keyboard collapse/reopen preserves exact selected File, preview and confirmation; zero implicit imports; original duplicate/amendment/quarantine and denial checks retained.')
    print('PASS RECORDS: actual disk file preview with zero auto-upload; exact UTF-8/hash import; duplicate; amendment and old original; foreign-case quarantine; independent original-read denial and source-read clearing; no clinical approval; 390px containment.')
