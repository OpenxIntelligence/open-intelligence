"""Presentation acceptance over actual H1 responses; no HTTP fixtures or mocks."""
import base64
import json
import os
from pathlib import Path


def exercise(cd, credentials, write_grants):
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
        cd.command('Input.dispatchKeyEvent', {'type': 'rawKeyDown', 'key': name, 'code': name, 'windowsVirtualKeyCode': code})
        if name == 'Enter':
            cd.command('Input.dispatchKeyEvent', {'type': 'char', 'text': '\r', 'key': name, 'windowsVirtualKeyCode': code})
        cd.command('Input.dispatchKeyEvent', {'type': 'keyUp', 'key': name, 'code': name, 'windowsVirtualKeyCode': code})

    cd.command('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})
    cd.evaluate("document.querySelector('#sources-heading').scrollIntoView()")
    (out/'reading-before-or-after.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
    assert cd.evaluate("!document.querySelector('[data-testid=record-import-disclosure]')?.open && Boolean(document.querySelector('[data-testid=record-import-disclosure]'))"), 'Loaded records start with the import form collapsed'
    assert cd.evaluate("!document.querySelector('#original-file').checkVisibility()"), 'Closed import does not compete with source reading'
    assert cd.evaluate("Boolean(document.querySelector('#source-filter'))"), 'Loaded source versions need a response-scoped filter'
    assert cd.evaluate("Boolean(document.querySelector('#reading-view'))"), 'Patient and clinical reading layouts must share the existing session'
    assert cd.evaluate("document.querySelector('[data-testid=readiness]').getAttribute('role')==='status'"), 'Readiness needs noninterrupting status semantics'
    # Inspect Chromium's computed names, not just the presence of ARIA attributes.
    cd.command('Accessibility.enable', {})
    ax = cd.command('Accessibility.getFullAXTree', {})['nodes']
    names = [n.get('name', {}).get('value', '') for n in ax
             if not n.get('ignored') and n.get('role', {}).get('value') == 'button']
    assert 'Inspect original v1: DOC-ONE' in names
    assert 'Inspect original v2: DOC-ONE' in names
    expected_questions = cd.evaluate("[...document.querySelectorAll('[data-testid=source-finding]')].filter(e=>e.querySelector('[data-testid=ask-source-question]')).map(e=>{const heading=e.closest('[data-testid=source-version]').querySelector('h4').textContent;const [doc,version]=heading.split(' · v');const line=e.querySelector('p').textContent.match(/line (\\d+)/)[1];return 'Ask about this statement: '+doc+', version '+version+', line '+line+', '+e.querySelector('strong').textContent})")
    assert expected_questions, 'Actual loaded quotations must expose question controls'
    assert all(name in names for name in expected_questions), 'Computed button names must identify the exact visible quotation'
    assert 'Ask about this statement' not in names, 'Repeated unqualified quotation controls must be disambiguated'
    (out/'source-action-accessibility.json').write_text(json.dumps({'originals': [n for n in names if n.startswith('Inspect original')], 'questions': expected_questions}, indent=2))
    cd.command('Accessibility.disable', {})
    print('PASS SOURCE ACTION NAMES: Chromium computed names retain visible labels and identify document, original version and exact quotation line/key.')
    previous_original_actions = list(credentials[0]['actions'])
    credentials[0]['actions'] = sorted(set(previous_original_actions) | {'source_original_read'})
    write_grants()
    try:
        # Follow the actual separately authorized original read, then return to its trigger.
        for width, version in ((1280, 2), (390, 1)):
            cd.command('Emulation.setDeviceMetricsOverride', {'width':width,'height':900,'deviceScaleFactor':1,'mobile':False})
            cd.evaluate("window.__originalOpener=[...document.querySelectorAll('[data-testid=open-original]')].find(e=>e.textContent==='Inspect original v"+str(version)+"');window.__originalOpener.focus()")
            key('Enter',13)
            cd.wait("document.activeElement===document.querySelector('#opened-original')", 'verified original receives keyboard focus')
            assert cd.evaluate("document.querySelector('#opened-original').textContent.endsWith('v"+str(version)+"')")
            cd.wait("(()=>{const r=document.activeElement.getBoundingClientRect();const h=document.querySelector('.topbar');return r.top>=0&&r.bottom<=innerHeight&&(h.dataset.sticky==='false'||r.top>=h.getBoundingClientRect().bottom)})()", 'original heading is visible below patient context')
            (out/f'original-focus-{width}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
            key('Tab',9)
            assert cd.evaluate("document.activeElement===document.querySelector('[data-testid=close-original]')"), 'Tab from original heading reaches its close action'
            key('Enter',13)
            cd.wait("!document.querySelector('[data-testid=opened-original]')&&document.activeElement===window.__originalOpener", 'close returns to exact source-version button')
        # If a local filter removes the opener, return to the source heading, not a detached node.
        cd.evaluate("window.__originalOpener.focus()")
        key('Enter',13)
        cd.wait("document.activeElement===document.querySelector('#opened-original')", 'second historical read')
        value('#source-filter','NO-MATCH-FOCUS')
        cd.wait("Boolean(document.querySelector('[data-testid=source-no-match]'))", 'opener filtered out')
        cd.evaluate("document.querySelector('[data-testid=close-original]').focus()")
        key('Enter',13)
        cd.wait("document.activeElement===document.querySelector('#sources-heading')", 'filtered opener uses visible source-heading fallback')
        assert cd.evaluate("document.querySelector('#source-filter').value==='NO-MATCH-FOCUS'"), 'Closing originals must not rewrite local filters'
        cd.evaluate("document.querySelector('[data-testid=clear-source-filters]').click()")
        # Returning to the section must retain its ordinary navigation focus.
        cd.evaluate("document.querySelector('[data-testid=open-original]').click()")
        cd.wait("document.activeElement===document.querySelector('#opened-original')", 'current original before navigation')
        navigate('Overview');navigate('Records')
        assert cd.evaluate("document.activeElement===document.querySelector('h1')"), 'An earlier read cannot steal section navigation focus'
        cd.evaluate("document.querySelector('[data-testid=close-original]').click()")
        cd.wait("document.activeElement===document.querySelector('#sources-heading')", 'navigation discards stale return target')
        cd.evaluate('delete window.__originalOpener')
        cd.command('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})
        print('PASS ORIGINAL FOCUS: actual current/historical original read focuses visible heading; native keyboard close restores exact opener; filtered-out opener falls back without clearing filters; navigation does not replay old focus.')
    finally:
        credentials[0]['actions'] = previous_original_actions
        write_grants()
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
        assert cd.evaluate("document.activeElement.dataset.testid==='clear-source-filters'")
        key('Enter', 13)
        cd.wait("document.querySelectorAll('[data-testid=source-version]').length===2", 'keyboard clear restores loaded versions')
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
                cd.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
                # Re-enter focus after resizing; focus() on the same focused input does not scroll.
                cd.evaluate("document.querySelector('#source-state').focus({preventScroll:true});document.querySelector('#source-filter').focus()")
                cd.wait('document.documentElement.scrollWidth<=innerWidth+1', 'source workspace reflows at ' + str(width))
                cd.wait("(()=>{const h=document.querySelector('.topbar').getBoundingClientRect();const f=document.activeElement.getBoundingClientRect();return f.top>=h.bottom && f.bottom<=innerHeight})()", 'filter focus clears patient header at '+str(width))
                (out/f'reading-{view}-{width}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
                if width in (390,1280):
                    cd.evaluate("document.querySelector('.source-quotes').scrollIntoView({block:'center'})")
                    (out/f'quotation-{view}-{width}.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        cd.command('Emulation.setDeviceMetricsOverride', {'width':320,'height':256,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
        cd.evaluate("document.querySelector('#source-state').focus({preventScroll:true});document.querySelector('#source-filter').focus()")
        print('SHORT FOCUS',cd.evaluate("(()=>{const h=document.querySelector('.topbar');const r=document.activeElement.getBoundingClientRect();return {top:r.top,bottom:r.bottom,sticky:h.dataset.sticky,headerBottom:h.getBoundingClientRect().bottom,height:innerHeight}})()"))
        cd.wait("(()=>{const h=document.querySelector('.topbar');const r=document.activeElement.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&(h.dataset.sticky==='false'||r.top>=h.getBoundingClientRect().bottom)})()", 'short viewport focus unobscured')
        select('#reading-view', 'patient')
        cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        # Use inherited-size doubling, rather than compounding 200% at every nested element.
        cd.evaluate("window.__readingSizes=[...document.body.querySelectorAll('*')].map(e=>[e,getComputedStyle(e).fontSize]);for(const [e,s] of window.__readingSizes){e.style.setProperty('font-size',(parseFloat(s)*2)+'px');e.style.setProperty('line-height','1.5');e.style.setProperty('letter-spacing','.12em');e.style.setProperty('word-spacing','.16em')}")
        cd.wait('document.documentElement.scrollWidth<=innerWidth+1', 'doubled text and spacing containment')
        (out/'reading-large-text-390.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        cd.evaluate("for(const [e] of window.__readingSizes){for(const p of ['font-size','line-height','letter-spacing','word-spacing'])e.style.removeProperty(p)};delete window.__readingSizes")
        print('PASS READING CONVERGENCE: actual source response; current/historical filter; source-adjacent quotations; retained reading state with no requests; refresh reset; keyboard provenance and focus recovery; 320/390/768/1280 layouts and doubled-text/short-height checks.')
    finally:
        cd.evaluate("if(window.__readingFetch){window.fetch=window.__readingFetch;delete window.__readingFetch;delete window.__readingRequests}")
        cd.command('Emulation.setDeviceMetricsOverride', {'width':1280,'height':1000,'deviceScaleFactor':1,'mobile':False})


def exercise_session_reset(cd, patient_id, case_id, token, credentials, write_grants):
    """Real reconnect and authority recheck; UI-only filters cannot outlive their read."""
    from datetime import datetime, timedelta, timezone
    def value(selector, text):
        cd.evaluate("(()=>{const e=document.querySelector(" + json.dumps(selector) + ");Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e," + json.dumps(text) + ");e.dispatchEvent(new Event('input',{bubbles:true}));})()")
    def nav(section):
        cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith("+json.dumps(section)+")).click()")
    def open_sources():
        nav('Records')
        cd.wait("Boolean(document.querySelector('[data-testid=load-cases]')) && !document.querySelector('[data-testid=load-cases]').disabled", 'case refresh is available after the prior read finishes')
        cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=case-row]')) && document.querySelector('[data-testid=records-status]').textContent==='Select an active case to check its original source metadata.'", 'restored completed case access')
        cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes("+json.dumps(case_id)+")).querySelector('[data-testid=load-sources]').click()")
        cd.wait("Boolean(document.querySelector('#source-filter'))", 'restored actual source response')
    def connect():
        value('#credential', token)
        cd.evaluate("document.querySelector('#credential').form.requestSubmit()")
        value('#patient-id', patient_id)
        cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
        cd.wait("Boolean(document.querySelector('[data-testid=patient-card]'))", 'restored original patient')
    credentials[0]['patient_ids'] = [patient_id]
    credentials[0]['expires_at'] = (datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
    if 'source_read' not in credentials[0]['actions']:
        credentials[0]['actions'].append('source_read')
    write_grants()
    connect(); open_sources()
    value('#source-filter', 'DOC-ONE')
    cd.evaluate("const e=document.querySelector('#source-state');e.value='current';e.dispatchEvent(new Event('change',{bubbles:true}))")
    cd.wait("document.querySelectorAll('[data-testid=source-version]').length===1", 'active filter before disconnect')
    nav('Overview')
    cd.evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent==='Disconnect and clear').click()")
    cd.wait("Boolean(document.querySelector('#credential'))", 'explicit disconnect')
    assert cd.evaluate("!document.querySelector('[data-testid=workspace-identity]').textContent.includes("+json.dumps(patient_id)+")")
    connect(); open_sources()
    assert cd.evaluate("document.querySelector('#source-filter').value==='' && document.querySelector('#source-state').value==='all' && document.querySelectorAll('[data-testid=source-version]').length===2"), 'Reconnect must not restore a previous response filter'
    value('#source-filter', 'DOC-ONE')
    credentials[0]['actions'].remove('source_read');write_grants()
    cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes("+json.dumps(case_id)+")).querySelector('[data-testid=load-sources]').click()")
    # Starting any read clears the source index. That loading state is not proof
    # of denial: wait for the actual non-success response before restoring grants.
    cd.wait("document.querySelector('[data-testid=records-status]')?.textContent==='Sources unavailable, denied or mapping revoked. Reload case permissions.' && !document.querySelector('[data-testid=load-cases]').disabled", 'completed denied source read')
    cd.wait("!document.querySelector('[data-testid=source-index]')", 'denied source read removes filtered quotations and provenance')
    assert cd.evaluate("!document.querySelector('#source-filter') && !document.querySelector('[data-testid=source-statement]')")
    credentials[0]['actions'].append('source_read');write_grants()
    open_sources()
    assert cd.evaluate("document.querySelector('#source-filter').value==='' && document.querySelector('#source-state').value==='all'"), 'Reauthorization must begin with the new response filters'
    nav('Overview')
    cd.evaluate("[...document.querySelectorAll('button')].find(e=>e.textContent==='Disconnect and clear').click()")
    print('PASS READING SESSION BOUNDARY: actual reconnect resets filters; denied source read removes quotations and provenance; reauthorization starts fresh; patient context clears on disconnect.')
