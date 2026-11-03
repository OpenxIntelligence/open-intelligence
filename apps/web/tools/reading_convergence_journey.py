"""Presentation acceptance over actual H1 responses; no HTTP fixtures or mocks."""
import base64
import json
import os
from pathlib import Path


def exercise(cd):
    out = Path(os.environ.get('OI_WEB_ARTIFACT_DIR', 'apps/web/.evidence'))
    out.mkdir(parents=True, exist_ok=True)

    def navigate(section):
        cd.evaluate("[...document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')].find(e=>e.textContent.startsWith(" + json.dumps(section) + ")).click()")
        cd.wait("document.querySelector('h1')===document.activeElement", 'navigation focuses the workspace heading')

    def value(selector, text):
        cd.evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e," + json.dumps(text) + ");e.dispatchEvent(new Event('input',{bubbles:true}));})()")

    def select(selector, text):
        cd.evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");e.value=" + json.dumps(text) + ";e.dispatchEvent(new Event('change',{bubbles:true}));})()")

    def key(name, code):
        cd.command('Input.dispatchKeyEvent', {'type': 'keyDown', 'key': name, 'code': name, 'windowsVirtualKeyCode': code})
        cd.command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': name, 'code': name, 'windowsVirtualKeyCode': code})

    cd.command('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})
    cd.evaluate("document.querySelector('#sources-heading').scrollIntoView()")
    (out/'reading-before-or-after.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
    assert cd.evaluate("Boolean(document.querySelector('#source-filter'))"), 'Loaded source versions need a response-scoped filter'
    assert cd.evaluate("Boolean(document.querySelector('#reading-view'))"), 'Patient and clinical reading layouts must share the existing session'
    assert cd.evaluate("document.querySelector('[data-testid=readiness]').getAttribute('role')==='status'"), 'Readiness needs noninterrupting status semantics'
    cd.evaluate("window.__readingFetch=window.fetch;window.__readingRequests=0;window.fetch=(input,init)=>{if(String(input).includes('/v1/'))window.__readingRequests++;return window.__readingFetch(input,init)}")
    try:
        value('#source-filter', 'DOC-ONE')
        select('#source-state', 'current')
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1", 'current version filter')
        row = cd.evaluate("document.querySelector('[data-testid=source-version]').textContent")
        assert 'v2' in row and 'Amended fictional marker' in row
        assert cd.evaluate("document.querySelector('[data-testid=source-version] [data-testid=source-statement]')!==null"), 'Quotation must stay beside its original version'
        navigate('Overview')
        assert cd.evaluate("!document.querySelector('[data-testid=patient-card]').textContent.includes('No clinical record or conclusion has been loaded')"), 'Overview must not contradict loaded sources'
        select('#reading-view', 'clinical')
        navigate('Records')
        assert cd.evaluate("document.querySelector('#source-filter').value==='DOC-ONE' && document.querySelector('#source-state').value==='current'"), 'Navigation and reading layout retain the same response filters'
        assert cd.evaluate('window.__readingRequests===0'), 'Reading preferences and local filters must not request or mutate records'
        select('#source-state', 'superseded')
        cd.wait("document.querySelector('[data-testid=source-version]')?.textContent.includes('v1')", 'historical version retained')
        assert cd.evaluate("!document.querySelector('[data-testid=source-version] [data-testid=source-statement]')"), 'Current quotation must not be attached to a historical source'
        value('#source-filter', 'NO-MATCH-FICTIONAL')
        cd.wait("Boolean(document.querySelector('[data-testid=source-no-match]'))", 'explicit no-match recovery')
        cd.evaluate("document.querySelector('[data-testid=clear-source-filters]').focus()")
        key('Enter', 13)
        cd.wait("document.activeElement===document.querySelector('#source-filter')", 'clear filters returns focus to the filter')
        assert cd.evaluate("document.querySelectorAll('[data-testid=source-version]').length===2")
        cd.evaluate("document.querySelector('[data-testid=source-verify] summary').focus()")
        key('Enter', 13)
        cd.wait("document.querySelector('[data-testid=source-verify]').open", 'native keyboard opens provenance')
        key('Enter', 13)
        cd.wait("!document.querySelector('[data-testid=source-verify]').open", 'native keyboard closes provenance')
        value('#source-filter', 'DOC-ONE')
        select('#source-state', 'current')
        cd.evaluate("document.querySelector('[data-testid=load-sources]').click()")
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length===2", 'fresh source response resets filters')
        assert cd.evaluate("document.querySelector('#source-filter').value==='' && document.querySelector('#source-state').value==='all'")
        for view in ('patient', 'clinical'):
            select('#reading-view', view)
            for width in (320,390,768,1280):
                cd.command('Emulation.setDeviceMetricsOverride', {'width':width,'height':900,'deviceScaleFactor':1,'mobile':False})
                cd.evaluate("document.querySelector('#source-filter').focus()")
                cd.wait('document.documentElement.scrollWidth<=innerWidth+1', 'source workspace reflows at ' + str(width))
                cd.wait("(()=>{const h=document.querySelector('.topbar').getBoundingClientRect();const f=document.activeElement.getBoundingClientRect();return f.top>=h.bottom && f.bottom<=innerHeight})()", 'filter focus clears patient header')
                (out/f'reading-{view}-{width}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        cd.command('Emulation.setDeviceMetricsOverride', {'width':320,'height':256,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate("document.querySelector('#source-filter').focus();document.querySelector('#source-filter').scrollIntoView({block:'center'})")
        cd.wait("(()=>{const h=document.querySelector('.topbar');const r=document.activeElement.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&(h.dataset.sticky==='false'||r.top>=h.getBoundingClientRect().bottom)})()", 'short viewport focus unobscured')
        select('#reading-view', 'patient')
        cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate("const s=document.createElement('style');s.id='reading-large-text';s.textContent='body *{font-size:200%!important;line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}';document.head.append(s)")
        # Use inherited-size doubling, rather than compounding 200% at every nested element.
        cd.evaluate("document.querySelector('#reading-large-text').remove();window.__readingSizes=[...document.body.querySelectorAll('*')].map(e=>[e,getComputedStyle(e).fontSize]);for(const [e,s] of window.__readingSizes){e.style.setProperty('font-size',(parseFloat(s)*2)+'px');e.style.setProperty('line-height','1.5');e.style.setProperty('letter-spacing','.12em');e.style.setProperty('word-spacing','.16em')}")
        cd.wait('document.documentElement.scrollWidth<=innerWidth+1', 'doubled text and spacing containment')
        (out/'reading-large-text-390.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        cd.evaluate("for(const [e] of window.__readingSizes){for(const p of ['font-size','line-height','letter-spacing','word-spacing'])e.style.removeProperty(p)};delete window.__readingSizes")
        print('PASS READING CONVERGENCE: actual source response; current/historical filter; source-adjacent quotations; retained reading state with no requests; refresh reset; keyboard provenance and focus recovery; 320/390/768/1280 layouts and doubled-text/short-height checks.')
    finally:
        cd.evaluate("if(window.__readingFetch){window.fetch=window.__readingFetch;delete window.__readingFetch;delete window.__readingRequests}")
        cd.command('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})
