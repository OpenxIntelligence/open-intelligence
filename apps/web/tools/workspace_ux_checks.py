"""User-visible frontend checks over the real H1 browser/API journey.

No HTTP fixture, alternate permission service or copied clinical business logic.
The browser_journey caller supplies an actual persisted fictional patient.
"""
import base64
import json
import os
from pathlib import Path


def navigate(cd, section):
    cd.evaluate("(()=>{const b=document.querySelector(" + json.dumps(
        '.primary-nav [data-section="' + section + '"]') + ");const d=b.closest('details');if(d&&!d.open)d.querySelector('summary').click();})()")
    cd.evaluate("document.querySelector(" + json.dumps(
        '.primary-nav [data-section="' + section + '"]') + ").click()")
    cd.wait("document.querySelector('#workspace-title')===document.activeElement",
            'destination change places focus at the workspace title')


def set_value(cd, selector, value):
    cd.evaluate(f"""(()=>{{const e=document.querySelector({json.dumps(selector)});
      Object.getOwnPropertyDescriptor(e.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype,'value').set.call(e,{json.dumps(value)});
      e.dispatchEvent(new Event(e.tagName==='SELECT'?'change':'input',{{bubbles:true}}));}})()""")


def capture(cd, name):
    target=Path(os.environ.get('OI_WEB_ARTIFACT_DIR',Path(__file__).resolve().parents[1]/'.evidence'))
    target.mkdir(parents=True,exist_ok=True)
    image=cd.command('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
    (target/name).write_bytes(base64.b64decode(image['data']))


def check_workspace_navigation(cd, patient_id):
    # Catches loss of identity on non-Overview destinations and accidental API
    # calls/state changes from a purely presentational reading preference.
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=patient-context]'))"), 'Selected patient needs a persistent chart header'
    assert patient_id in cd.evaluate("document.querySelector('[data-testid=patient-context]').textContent")
    assert cd.evaluate("Boolean(document.querySelector('nav[aria-label=\"Patient chart\"]'))")
    original=cd.evaluate("document.querySelector('#patient-id').value")
    set_value(cd,'#patient-id','PAT-UNSUBMITTED-DRAFT')
    before=cd.evaluate("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname.startsWith('/v1/')).length")
    set_value(cd,'#reading-view','clinical')
    cd.wait("document.querySelector('.app')?.dataset.view==='clinical'",'clinical reading layout')
    assert cd.evaluate("document.querySelector('#patient-id').value==='PAT-UNSUBMITTED-DRAFT'")
    assert patient_id in cd.evaluate("document.querySelector('[data-testid=patient-context]').textContent")
    navigate(cd,'Records')
    assert patient_id in cd.evaluate("document.querySelector('[data-testid=patient-context]').textContent")
    set_value(cd,'#reading-view','patient')
    cd.wait("document.querySelector('.app')?.dataset.view==='patient'",'patient reading layout')
    navigate(cd,'Journey')
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=unconnected-workflow]'))")
    assert patient_id in cd.evaluate("document.querySelector('[data-testid=patient-context]').textContent")
    navigate(cd,'Overview')
    assert cd.evaluate("document.querySelector('#patient-id').value==='PAT-UNSUBMITTED-DRAFT'")
    after=cd.evaluate("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname.startsWith('/v1/')).length")
    assert before==after,'Reading/layout navigation must not request or alter patient records'
    set_value(cd,'#patient-id',original)


def check_source_presentation(cd, patient_id, versions):
    # Catches filtering becoming a clinical conclusion, losing literal quotes,
    # or failing to retain source version/line associations and recovery.
    assert patient_id in cd.evaluate("document.querySelector('[data-testid=patient-context]').textContent")
    assert cd.evaluate("document.querySelectorAll('[data-testid=source-version]').length")==versions
    assert cd.evaluate("document.querySelector('[data-testid=status]').getClientRects().length===0"), 'A completed identity-read message must not contradict loaded source records'
    count=cd.evaluate("document.querySelectorAll('[data-testid=source-statement]').length")
    set_value(cd,'#source-filter','no-record-can-match-this-query')
    cd.wait("Boolean(document.querySelector('[data-testid=source-no-match]'))",'filter has an explicit no-match state')
    assert cd.evaluate("document.querySelectorAll('[data-testid=source-version]').length===0")
    cd.evaluate("document.querySelector('[data-testid=clear-source-filters]').focus()")
    assert cd.evaluate("document.activeElement?.dataset.testid==='clear-source-filters'"),'Clear button must own focus before keyboard activation'
    cd.command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'text':'\r'})
    cd.command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length==="+str(versions),'clear filters restores loaded history')
    presentation_failures=[]
    if not cd.evaluate("document.activeElement?.id==='source-filter'"):
        presentation_failures.append('Clearing filters must return keyboard focus to the source filter')
    before=cd.evaluate("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname.startsWith('/v1/')).length")
    navigate(cd,'Overview')
    if cd.evaluate("document.querySelector('[data-testid=status]').getClientRects().length!==0"):
        presentation_failures.append('Overview must not claim no records are loaded while retaining source records')
    navigate(cd,'Records')
    assert cd.evaluate("document.querySelectorAll('[data-testid=source-version]').length")==versions
    after=cd.evaluate("performance.getEntriesByType('resource').filter(r=>new URL(r.name).pathname.startsWith('/v1/')).length")
    assert before==after,'Returning to loaded records must not issue a new request'
    assert not presentation_failures, '; '.join(presentation_failures)
    assert cd.evaluate("document.querySelectorAll('[data-testid=source-statement]').length")==count
    assert cd.evaluate("[...document.querySelectorAll('[data-testid=source-statement]')].every(e=>e.closest('[data-testid=source-version]'))")
    details=cd.evaluate("document.querySelector('details.source-provenance')?.open")
    assert details is False
    cd.evaluate("document.querySelector('details.source-provenance summary').click()")
    assert cd.evaluate("document.querySelector('details.source-provenance').open")
    assert cd.evaluate("document.querySelector('details.source-provenance').textContent.includes('SHA-256')")
    cd.evaluate("document.querySelector('details.source-provenance summary').click()")
    set_value(cd,'#reading-view','clinical')
    cd.wait("document.querySelector('.app')?.dataset.view==='clinical'",'clinical chart source layout')
    assert cd.evaluate("document.querySelectorAll('[data-testid=source-version]').length")==versions
    if versions>1:
        assert cd.evaluate("document.querySelector('[data-testid=source-version]').classList.contains('current')"),'Current source versions should be encountered before historical versions'
        set_value(cd,'#source-state','superseded')
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1",'historical version remains independently inspectable')
        assert cd.evaluate("document.querySelectorAll('[data-testid=source-statement]').length===0"),'Current quotations must not be attributed to an older version'
        set_value(cd,'#source-state','all')
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length==="+str(versions),'all versions restored')
    assert cd.evaluate("Boolean(document.querySelector('[data-testid=refresh-sources]'))")
    cd.command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
    cd.evaluate('window.scrollTo(0,0)')
    capture(cd,'ux-clinical-records.png')
    cd.evaluate("document.querySelector('#sources-heading').scrollIntoView({block:'start'})")
    assert cd.evaluate("document.querySelector('[data-testid=patient-context]').getBoundingClientRect().top>=0")
    capture(cd,'ux-source-reading-desktop.png')
    set_value(cd,'#reading-view','patient')
    cd.wait("document.querySelector('.app')?.dataset.view==='patient'",'patient source layout')
    cd.evaluate('window.scrollTo(0,0)')
    capture(cd,'ux-patient-records.png')
    for width in (320,390,768,1440):
        cd.command('Emulation.setDeviceMetricsOverride',{'width':width,'height':900,'deviceScaleFactor':1,'mobile':False})
        cd.wait('window.innerWidth==='+str(width),'responsive viewport')
        assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'),f'{width}px layout overflows'
        context=cd.evaluate("(()=>{const r=document.querySelector('[data-testid=patient-context]').getBoundingClientRect();return {top:r.top,bottom:r.bottom}})()")
        assert context['top']>=0 and context['bottom']<900,'Patient identity must fit in the first viewport'
        if width==390:
            capture(cd,'ux-patient-records-mobile.png')
            cd.evaluate("document.querySelector('#sources-heading').scrollIntoView({block:'start'})")
            assert cd.evaluate("document.querySelector('[data-testid=patient-context]').getBoundingClientRect().top>=0")
            capture(cd,'ux-source-reading-mobile.png')
            cd.evaluate('window.scrollTo(0,0)')
        # Start from another control: focusing an already focused input after
        # the observer manually scrolls the page does not perform focus scroll.
        cd.evaluate("document.querySelector('#source-state').focus({preventScroll:true});document.querySelector('#source-filter').focus()")
        focus_geometry=cd.evaluate("(()=>{const f=document.querySelector('#source-filter').getBoundingClientRect();const h=document.querySelector('.context-surface').getBoundingClientRect();return {top:f.top,bottom:f.bottom,headerBottom:h.bottom,height:window.innerHeight}})()")
        assert focus_geometry['top']>=focus_geometry['headerBottom'] and focus_geometry['bottom']<=focus_geometry['height'],f'{width}px focused filter is obscured: {focus_geometry}'
        cd.evaluate('window.scrollTo(0,0)')
    # Exercise the native keyboard target instead of inferring access from CSS.
    cd.evaluate("document.querySelector('.skip').focus()")
    cd.command('Input.dispatchKeyEvent',{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
    cd.command('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
    cd.wait("document.activeElement?.id==='main'",'skip link reaches the main content')
    assert cd.evaluate("document.querySelector('#source-filter').getBoundingClientRect().height>=44")


def check_case_switch(cd, add_synthetic, root):
    # Real API fixtures exercise a second loaded case, upper-bound accepted
    # case/document IDs, source-organization length and source quotation length.
    case='CASE-'+('B'*35)
    document='DOC-'+('L'*36)
    quotation=('Fictional second-case source wording. '*40)[:1199]+'!'
    status,_=add_synthetic(root+'/case-bindings',{
        'synthetic':True,'case_id':case,'source_organization':'ORG-'+('L'*124),
        'source_system':'SYS-SYNTH','source_subject_ref':'SUBJECT-BETA','review_ref':'REVIEW-SYNTH'})
    assert status==201
    status,_=add_synthetic(root+'/cases/'+case+'/sources',{'synthetic':True,'original_text':
        'OI-SYNTHETIC-REPORT/1\nPatient: '+case+'\nDocument: '+document+'\n'
        'Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n'
        'Finding: marker|not-reported|'+quotation+'\n'})
    assert status==201
    set_value(cd,'#reading-view','clinical')
    cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
    cd.wait("document.querySelectorAll('[data-testid=case-row]').length===2",'second real authorized case')
    def inspect(case_id, count):
        selector='button[aria-label="Inspect source versions for '+case_id+'"]'
        cd.evaluate('document.querySelector('+json.dumps(selector)+').click()')
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length==="+str(count),'selected case source versions')
    inspect('CASE-ALPHA',2)
    set_value(cd,'#source-filter','no-record-can-match-this-query')
    cd.wait("Boolean(document.querySelector('[data-testid=source-no-match]'))",'first-case filter is active before switching')
    inspect(case,1)
    assert cd.evaluate("document.querySelector('#source-filter').value==='' && document.querySelector('#source-state').value==='all'"),'Filters must reset on a different case response'
    assert cd.evaluate("document.querySelector('[data-testid=source-statement]').textContent")==quotation
    assert not cd.evaluate("document.querySelector('[data-testid=source-index]').textContent.includes('Amended fictional marker')"),'Previous case quotation must leave the selected source view'
    cd.command('Emulation.setDeviceMetricsOverride',{'width':320,'height':900,'deviceScaleFactor':1,'mobile':False})
    cd.wait('window.innerWidth===320','long-source mobile viewport')
    overflow=cd.evaluate("[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>window.innerWidth+1).map(e=>({tag:e.tagName,class:e.className,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width})).slice(0,12)")
    assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'),f'Long source content must reflow at 320px: {overflow}'
    cd.evaluate("document.querySelector('#sources-heading').scrollIntoView({block:'start'})")
    capture(cd,'ux-long-source-mobile.png')
    set_value(cd,'#source-state','superseded')
    cd.wait("Boolean(document.querySelector('[data-testid=source-no-match]'))",'second-case filter is active before returning')
    inspect('CASE-ALPHA',2)
    assert cd.evaluate("document.querySelector('#source-state').value==='all' && document.querySelectorAll('[data-testid=source-statement]').length===1")
    assert not cd.evaluate('document.querySelector("[data-testid=source-index]").textContent.includes('+json.dumps(document)+')')
    cd.command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
    set_value(cd,'#reading-view','patient')


def check_cleared_context(cd):
    assert cd.evaluate("!document.querySelector('[data-testid=patient-context]')")
    assert cd.evaluate("!document.querySelector('[data-testid=source-index]')")
    assert cd.evaluate("document.querySelectorAll('[data-testid=source-version], [data-testid=source-statement]').length===0")
