"""Real browser and HTTP acceptance for one independently fictional patient's visit."""
import base64
import hashlib
import json
from urllib.request import Request, urlopen


VISIT = 'VISIT-CHART-WEB'
NOTE = 'NOTE-CHART-WEB'
FIRST = 'Fictional chart draft: check <sample> at the next visit.'
SECOND = 'Fictional revised chart draft: the sample label is pending.'
CONCURRENT = 'Fictional concurrent draft saved from another session.'
LOCAL_EDIT = 'Fictional operator edit retained for comparison.'
UNSAVED = 'Fictional duplicate-note draft that must never be stored.'


def exercise(cd, patient_id, token, credentials, write_grants, case, source_id, original, artifacts):
    previous = list(credentials[0]['actions'])
    actions = {'encounter.read', 'encounter.schedule', 'encounter.transition', 'note.read',
               'note.write', 'encounter.source.link', 'source_original_read'}
    url = 'http://127.0.0.1:8000/v1/patients/' + patient_id + '/encounters'

    def operator(path='', payload=None):
        req = Request(url + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=8) as response:
            return json.load(response)

    def element(testid):
        return 'document.querySelector(' + json.dumps(f'[data-testid="{testid}"]') + ')'

    def row_button(row, match, button):
        return ('[...document.querySelectorAll(' + json.dumps(f'[data-testid="{row}"]') + ')]'
                '.find(r=>r.textContent.includes(' + json.dumps(match) + '))?.querySelector('
                + json.dumps(f'[data-testid="{button}"]') + ')')

    def press(expression, label):
        cd.wait(f'Boolean({expression}) && !{expression}.matches(":disabled")', label)
        cd.evaluate(expression + '.click()')

    def click(testid):
        press(element(testid), testid)

    def fill(testid, value):
        field = element(testid)
        cd.wait(f'Boolean({field}) && !{field}.matches(":disabled")', testid)
        # React tracks input/textarea values; dispatch a normal change for selects.
        js = '''((node, value) => {
            const select = node instanceof HTMLSelectElement;
            if (select && !Array.from(node.options).some(option => option.value === value))
                throw Error('Choice missing from ' + node.dataset.testid);
            Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node), 'value').set.call(node, value);
            node.dispatchEvent(new Event(select ? 'change' : 'input', {bubbles:true}));
        })'''
        cd.evaluate(f'{js}({field},{json.dumps(value)})')

    def navigate(name):
        press('[...document.querySelectorAll(\'nav[aria-label="Patient workspace"] button\')]'
              '.find(b=>b.textContent.startsWith(' + json.dumps(name) + '))', name)

    open_visit = row_button('encounter-row', VISIT, 'encounter-open')
    open_history = row_button('encounter-note-row', NOTE, 'encounter-history-open')
    versions = 'Array.from(document.querySelectorAll("[data-testid=encounter-version-row] pre"), v=>v.textContent)'

    def history(*bodies):
        cd.wait(f'JSON.stringify({versions}) === JSON.stringify({json.dumps(bodies)})',
                'exact original and later draft texts in version order')

    try:
        credentials[0]['actions'] = sorted(set(previous) | actions)
        write_grants()
        navigate('Records')
        click('records-open-visits')
        cd.wait("document.querySelector('h1').textContent==='Visits'", 'chart opens as its own workspace destination')
        click('encounter-load')
        click('encounter-schedule-open')
        cd.wait(element('encounter-schedule-date')+'?.form.querySelector("h3")===document.activeElement', 'schedule form receives keyboard focus')
        # Accept an automatically generated reference and confirm cancellation requires a separate action.
        fill('encounter-schedule-date', '2026-05-03')
        click('encounter-schedule')
        cd.wait('Boolean('+element('encounter-open')+')', 'visit with generated reference visible')
        generated, = [v for v in operator()['encounters'] if v['service_date']=='2026-05-03']
        assert generated['external_key'].startswith('VISIT-')
        press(row_button('encounter-row', generated['external_key'], 'encounter-open'), 'open generated visit')
        click('encounter-cancel')
        assert [v for v in operator()['encounters'] if v['id']==generated['id']][0]['status']=='scheduled'
        keep='[...document.querySelectorAll("button")].find(b=>b.textContent==="Keep visit")'
        press(keep, 'keep visit without changing status')
        click('encounter-schedule-open')
        fill('encounter-schedule-key', VISIT)
        fill('encounter-schedule-kind', 'outpatient')
        fill('encounter-schedule-date', '2026-05-04')
        click('encounter-schedule')
        fill('visit-search', 'nonexistent')
        cd.wait("document.body.textContent.includes('No loaded visits match')", 'empty filtered view')
        fill('visit-search', '')
        fill('visit-status-filter', 'completed')
        assert not cd.evaluate('Boolean('+open_visit+')')
        fill('visit-status-filter', 'all')
        press(open_visit, 'new persisted visit')
        cd.wait("document.activeElement.id==='selected-visit-heading'", 'selected visit receives focus')
        click('encounter-start')
        cd.wait(f'Boolean({element("encounter-complete")})', 'in-progress visit permits completion')
        visit, = [v for v in operator()['encounters'] if v['external_key'] == VISIT]
        assert (visit['patient_id'], visit['status'], visit['revision']) == (patient_id, 'in_progress', 2)
        visit_id = visit['id']

        # Link the existing source explicitly; read it through the same original owner as Records.
        click('visit-inspect-records')
        cd.wait("document.querySelector('h1').textContent==='Records'", 'selected visit handed to Records')
        click('load-cases')
        press(row_button('case-row', case, 'load-sources'), 'original case in Records')
        # Navigation focuses the mounted section without reading or writing a record.
        cd.evaluate("document.querySelector('.page-contents summary').click()")
        link='document.querySelector('+json.dumps('.page-contents a[href="#visit-records-heading"]')+')'
        press(link,'Visit records in page contents')
        cd.wait("document.activeElement.id==='visit-records-heading' && !document.querySelector('.page-contents details').open",
                'contents navigation focuses the real current heading')
        click('visit-records-handoff')
        cd.wait(f'{element("encounter-link-visit")}?.value==="{visit_id}"', 'independently checked visit retained in Records')
        fill('encounter-link-source', source_id)
        click('encounter-link-save')
        click('encounter-links-read')
        click('encounter-link-original')
        cd.wait(f'{element("server-original")}?.textContent === {json.dumps(original)}',
                'exact linked source version recovered from its canonical owner')
        navigate('Overview')
        navigate('Visits')
        click('encounter-load')
        press(open_visit, 'reopened visit from persisted list')
        click('encounter-notes-load')
        click('encounter-note-new')
        fill('encounter-note-body', 'Fictional note with an automatic reference.')
        click('encounter-note-save')
        cd.wait('Boolean('+element('encounter-note-row')+')', 'saved note with generated reference')
        assert operator(f'/{visit_id}/notes')['notes'][0]['note_key'].startswith('NOTE-')
        click('encounter-note-new')
        fill('encounter-note-key', NOTE)
        fill('encounter-note-kind', 'consultation')
        fill('encounter-note-facility', 'FICTIONAL-FACILITY')
        fill('encounter-note-department', 'FICTIONAL-DEPARTMENT')
        fill('encounter-note-body', FIRST)
        navigate('Journey')
        cd.wait("document.querySelector('dialog[open] button')===document.activeElement", 'unsaved note guard focuses Keep editing')
        assert cd.evaluate("document.querySelector('h1').textContent")== 'Visits'
        cd.command('Input.dispatchKeyEvent', {'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
        cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
        cd.wait("!document.querySelector('dialog[open]')", 'Escape keeps the form open')
        assert cd.evaluate(element('encounter-note-body')+'.value')==FIRST
        click('encounter-note-save')
        press(open_history, 'read stored note')
        history(FIRST)
        click('encounter-note-edit')
        fill('encounter-note-body', SECOND)
        click('encounter-note-save')
        press(open_history, 'read both saved versions')
        history(FIRST, SECOND)

        # Hold the actual browser editor on v2 while a second HTTP command commits v3.
        click('encounter-note-edit')
        fill('encounter-note-body', LOCAL_EDIT)
        path = f'/{visit_id}/notes/{NOTE}/versions'
        winner = operator(path, {'synthetic': True, 'request_key': 'CHART-WEB-CONCURRENT',
                                 'expected_version': 2, 'body': CONCURRENT,
                                 'facility_id': 'FICTIONAL-NEW-FACILITY', 'note_kind': 'progress'})
        assert winner['version'] == 3
        click('encounter-note-save')
        cd.wait(f'Boolean({element("encounter-conflict")})', 'stale edit refused')
        assert cd.evaluate(element('encounter-note-body') + '.value') == LOCAL_EDIT
        click('encounter-conflict-refresh')
        history(FIRST, SECOND, CONCURRENT)
        click('encounter-conflict-rebase')
        assert cd.evaluate(element('encounter-note-body') + '.value') == LOCAL_EDIT
        assert cd.evaluate(element('encounter-note-facility') + '.value') == 'FICTIONAL-NEW-FACILITY'
        assert cd.evaluate(element('encounter-note-kind') + '.value') == 'progress'
        click('encounter-note-save')
        press(open_history, 'read explicitly rebased draft')
        history(FIRST, SECOND, CONCURRENT, LOCAL_EDIT)
        for width in (1280,360):
            cd.command('Emulation.setDeviceMetricsOverride',{'width':width,'height':800,'deviceScaleFactor':1,'mobile':width==360})
            cd.wait('document.documentElement.scrollWidth<=innerWidth+1','visit chart reflow at width '+str(width))
            cd.evaluate('document.querySelector("[aria-label=\\"Saved note history\\"]").scrollIntoView()')
            (artifacts / ('visits-history-'+str(width)+'.png')).write_bytes(base64.b64decode(
                cd.command('Page.captureScreenshot',{'format':'png'})['data']))
        cd.command('Emulation.clearDeviceMetricsOverride')
        saved = operator(path)['versions']
        assert [(v['version'], v['body'], v['facility_id'], v['note_kind']) for v in saved] == [
            (1, FIRST, 'FICTIONAL-FACILITY', 'consultation'), (2, SECOND, 'FICTIONAL-FACILITY', 'consultation'),
            (3, CONCURRENT, 'FICTIONAL-NEW-FACILITY', 'progress'), (4, LOCAL_EDIT, 'FICTIONAL-NEW-FACILITY', 'progress')]
        assert [v['supersedes_id'] for v in saved] == [None, *(v['id'] for v in saved[:-1])]
        for v in saved:
            assert v['sha256'] == hashlib.sha256(v['body'].encode()).hexdigest()
            assert (v['status'], v['department_id']) == ('draft', 'FICTIONAL-DEPARTMENT')

        # A new draft with an existing key cannot replace the stored note. Keep this
        # unsaved form alongside verified history when withdrawing the read grant.
        click('encounter-note-new')
        fill('encounter-note-key', NOTE)
        fill('encounter-note-body', UNSAVED)
        click('encounter-note-save')
        click('encounter-conflict-refresh')
        history(FIRST, SECOND, CONCURRENT, LOCAL_EDIT)
        assert cd.evaluate(element('encounter-note-body') + '.value') == UNSAVED
        credentials[0]['actions'].remove('note.read')
        write_grants()
        click('encounter-conflict-refresh')
        cd.wait(f'Boolean({element("visits-no-patient")})', 'denied read clears patient workspace')
        assert not cd.evaluate(f'Boolean({element("encounter-chart")} || {element("server-original")})')
        remaining = cd.evaluate('document.body.textContent + Array.from(document.querySelectorAll("input,textarea"), n=>n.value).join(" ")')
        assert all(body not in remaining for body in (FIRST, SECOND, CONCURRENT, LOCAL_EDIT, UNSAVED))
    finally:
        credentials[0]['actions'] = previous
        write_grants()

    # Preserve the original harness session and selected patient for its source journey.
    navigate('Overview')
    field = 'document.querySelector("#patient-id")'
    cd.evaluate('((e,v)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,"value").set.call(e,v);'
                'e.dispatchEvent(new Event("input",{bubbles:true}));})(' + field + ',' + json.dumps(patient_id) + ')')
    cd.evaluate(field + '.form.requestSubmit()')
    cd.wait(f'{element("patient-card")}?.textContent.includes({json.dumps(patient_id)})', 'same patient reopened')
    (artifacts / 'encounter-chart.json').write_text(json.dumps({
        'synthetic': True, 'encounter_id': visit_id, 'visit_revision': visit['revision'],
        'note_versions': [v['version'] for v in saved], 'note_sha256': [v['sha256'] for v in saved],
        'linked_source_id': source_id, 'original_verified': True, 'stale_edit_refused': True,
        'rebased_attribution_verified': True, 'denied_history_cleared': True,
    }, indent=2) + '\n')
    print('PASS ENCOUNTER CHART: visit scheduled and started, linked original opened, immutable draft versions read, concurrent update preserved, denied history and unsaved editor removed.')
