"""Real React -> FastAPI -> PostgreSQL record acquisition; independent fictional data."""
import base64
import json
from pathlib import Path
from urllib.request import Request, urlopen


def exercise(cd, patient_id, token, credentials, write_grants, screenshots):
    root = '/v1/patients/' + patient_id
    case_id = 'CASE-ACQUISITION'
    credentials[0]['actions'] = list(dict.fromkeys(credentials[0]['actions'] + [
        'source_read', 'source_original_read', 'source_import', 'case_binding_read',
        'case_binding_create', 'record_request_read', 'record_request_create',
        'record_request_receive', 'record_request_cancel']))
    write_grants()

    def operator(path, payload=None):
        req = Request('http://127.0.0.1:8000' + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                      method='GET' if payload is None else 'POST')
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    def navigate(name):
        cd.evaluate('[...document.querySelectorAll(\'nav[aria-label="Patient workspace"] button\')].find(b=>b.textContent.includes(' + json.dumps(name) + ')).click()')

    def value(selector, text, select=False):
        prototype = 'HTMLSelectElement' if select else 'HTMLInputElement'
        event = 'change' if select else 'input'
        cd.evaluate(f"(()=>{{const e=document.querySelector({json.dumps(selector)});Object.getOwnPropertyDescriptor({prototype}.prototype,'value').set.call(e,{json.dumps(text)});e.dispatchEvent(new Event('{event}',{{bubbles:true}}));}})()")

    def refresh():
        cd.evaluate("document.querySelector('[data-testid=load-record-requests]').click()")
        cd.wait("!!document.querySelector('[data-testid=record-request-list]')", 'current request history')

    def create(label):
        cd.evaluate("document.querySelector('.acquisition-create').open=true")
        value('[data-testid=request-kind]', 'pathology', True)
        value('[data-testid=request-label]', label)
        value('[data-testid=request-provider]', 'Fictional pathology service')
        cd.evaluate("(()=>{const c=document.querySelector('[data-testid=request-create-confirm]');if(!c.checked)c.click();document.querySelector('[data-testid=request-create-form]').requestSubmit()})()")
        cd.wait("document.querySelector('[data-testid=acquisition-write]')?.dataset.state==='confirmed' && !!document.querySelector('[data-testid=record-request-list]')", 'persistent tracked need')
        rows = operator(root + '/record-requests')['requests']
        matched = [r for r in rows if r['record_label'] == label]
        assert len(matched) == 1 and not matched[0]['external_request_sent']
        return matched[0]['request_id']

    operator(root + '/case-bindings', {'synthetic': True, 'case_id': case_id,
        'source_organization': 'FICT-LAB', 'source_system': 'FICT-RECORDS',
        'source_subject_ref': 'FICT-ACQUISITION', 'review_ref': 'FICT-REFERENCE'})
    navigate('Records')
    cd.wait("!!document.querySelector('[data-testid=record-acquisition]')", 'connected acquisition panel')
    refresh()
    assert 'not every record' in cd.evaluate("document.querySelector('[data-testid=acquisition-counts]').textContent")
    # In-progress draft survives task navigation, without additional storage.
    cd.evaluate("document.querySelector('.acquisition-create').open=true")
    value('[data-testid=request-label]', 'Unsent fictional draft')
    navigate('Journey'); navigate('Records')
    cd.wait("document.querySelector('[data-testid=request-label]')?.value==='Unsent fictional draft'", 'draft preserved across navigation')
    request_id = create('Fictional pathology original required')
    second_id = create('Fictional duplicate tracking to cancel')
    second = '[data-request-id="' + second_id + '"]'
    cd.evaluate(f"document.querySelector({json.dumps(second+' .acquisition-actions')}).open=true")
    value(second + ' [data-testid=request-cancel-reason]', 'Duplicate request is no longer needed')
    cd.evaluate(f"document.querySelector({json.dumps(second+' [data-testid=request-cancel]')}).click()")
    cd.wait(f"document.querySelector({json.dumps(second)})?.dataset.state==='cancelled'", 'real persisted cancellation')

    # Import an original through the current canonical source owner, then link through React.
    original = ('OI-SYNTHETIC-REPORT/1\nPatient: CASE-ACQUISITION\nDocument: DOC-ACQUISITION\n'
        'Type: pathology\nEvent-Date: 2026-02-10\nIssued-At: 2026-02-11\nSpecimen: SPECIMEN-ACQ\n'
        'Finding: review|pending|Independently fictional report; review remains pending.\n')
    source = operator(root + '/cases/' + case_id + '/sources', {'synthetic': True, 'original_text': original})
    cd.evaluate("document.querySelector('[data-testid=load-cases]').click()")
    cd.wait("document.querySelectorAll('[data-testid=case-row]').length>=3", 'existing and acquisition cases')
    cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(r=>r.textContent.includes('CASE-ACQUISITION')).querySelector('[data-testid=load-sources]').click()")
    cd.wait("document.querySelector('[data-testid=source-index]')?.textContent.includes('DOC-ACQUISITION')", 'original source available')
    refresh()
    row = '[data-request-id="' + request_id + '"]'
    cd.evaluate(f"document.querySelector({json.dumps(row+' .acquisition-actions')}).open=true")
    value(row + ' [data-testid=request-source]', source['source_id'], True)
    cd.evaluate(f"document.querySelector({json.dumps(row+' [data-testid=request-receive-confirm]')}).click();document.querySelector({json.dumps(row+' [data-testid=request-receive]')}).click()")
    cd.wait(f"document.querySelector({json.dumps(row)})?.dataset.state==='received'", 'original received, no clinical approval')
    received = next(r for r in operator(root + '/record-requests')['requests'] if r['request_id'] == request_id)
    assert received['source_reference']['source_id'] == source['source_id']
    assert received['receipt_status'] == 'source_current_unreviewed'
    assert 'not clinically reviewed' in cd.evaluate(f"document.querySelector({json.dumps(row)}).textContent")
    assert not cd.evaluate(f"document.querySelector({json.dumps(row+' [data-testid=request-cancel]')})")

    amended = original.replace('Issued-At: 2026-02-11', 'Issued-At: 2026-02-12\nAmends: DOC-ACQUISITION@1').replace('pending|Independently', 'indeterminate|Amended independently')
    operator(root + '/cases/' + case_id + '/sources', {'synthetic': True, 'original_text': amended})
    refresh()
    cd.wait(f"document.querySelector({json.dumps(row+' [data-testid=request-state]')})?.textContent.includes('reassessment')", 'amended source keeps historical receipt')
    historical = next(r for r in operator(root + '/record-requests')['requests'] if r['request_id'] == request_id)
    assert historical['source_reference']['source_id'] == source['source_id'] and historical['source_reference']['version'] == 1

    # Request read alone may expose receipt state, not source identifiers.
    credentials[0]['actions'].remove('source_read'); write_grants(); refresh()
    assert 'Source reference' in cd.evaluate(f"document.querySelector({json.dumps(row)}).textContent")
    assert source['source_id'] not in cd.evaluate(f"document.querySelector({json.dumps(row)}).textContent")
    credentials[0]['actions'].append('source_read'); write_grants(); refresh()
    cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
    cd.evaluate("document.querySelector('[data-testid=record-acquisition]').scrollIntoView({block:'start'})")
    screenshots.mkdir(parents=True, exist_ok=True)
    (screenshots/'h1-record-acquisition-desktop.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
    cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
    cd.wait('window.innerWidth===390', 'narrow resized desktop viewport')
    assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    (screenshots/'h1-record-acquisition-narrow.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot',{'format':'png'})['data']))
    credentials[0]['actions'].remove('record_request_read'); write_grants()
    cd.evaluate("document.querySelector('[data-testid=load-record-requests]').click()")
    cd.wait("!document.querySelector('[data-testid=record-request-list]') && document.querySelector('[data-testid=acquisition-status]').textContent.includes('unknown')", 'denied request read clears prior list')
    credentials[0]['actions'].append('record_request_read'); write_grants()
    navigate('Overview')
    print('PASS ACQUISITION: actual React/FastAPI/PostgreSQL create, cancellation, exact original receipt, amendment history, permission redaction and denial, draft continuity and resized viewport; no provider contacted or clinical review claimed.')
