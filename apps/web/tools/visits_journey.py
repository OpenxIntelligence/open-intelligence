"""Exercise the Visits workspace with an independently fictional patient and real HTTP."""
import base64
import json


def exercise_visits(cd, credentials, write_grants, patient_id, operator, artifacts):
    previous = list(credentials[0]['actions'])
    credentials[0]['actions'] = sorted(set(previous) | {
        'encounter.read', 'encounter.schedule', 'encounter.transition', 'note.read', 'note.write'})
    write_grants()

    def button(name, scope='.visits'):
        return ('[...document.querySelectorAll(' + json.dumps(scope + ' button') +
                ')].find(b=>b.textContent===' + json.dumps(name) + ')')

    def click(name, scope='.visits'):
        target = button(name, scope)
        cd.wait(target + ' && !(' + target + ').disabled', name)
        cd.evaluate('(' + target + ').click()')

    def value(selector, text, element='HTMLInputElement'):
        cd.evaluate('(()=>{const e=document.querySelector(' + json.dumps(selector) +
                    ');Object.getOwnPropertyDescriptor(' + element + ".prototype,'value').set.call(e," +
                    json.dumps(text) + ");e.dispatchEvent(new Event('input',{bubbles:true}));})()")

    def body_is(text):
        cd.wait('document.querySelector(".visit-body")?.textContent===' + json.dumps(text), text)

    note_a = 'Independently fictional first visit draft.'
    note_b = 'Independent concurrent version of the fictional draft.'
    note_c = 'Fictional revised visit draft retained for comparison.'
    try:
        click('Visits', 'nav')
        cd.wait('document.querySelector(".visit-empty")', 'authorized empty visit list')
        click('Schedule a visit')
        value('#visit-date', '2026-11-05')
        click('Save scheduled visit')
        click('Start visit')
        click('Confirm status change')
        click('Write a draft note')
        value('#visit-note-body', note_a, 'HTMLTextAreaElement')
        click('Save draft version')
        body_is(note_a)
        cd.wait('document.querySelector("#visits-title")===document.activeElement', 'focus returned to saved note')
        click('Revise draft')
        value('#visit-note-body', note_c, 'HTMLTextAreaElement')
        key = cd.evaluate('document.querySelector(".visit-original dd").textContent')
        # The visit list was empty before scheduling this one visit. Resolve its
        # real DB ID from the UI rather than assuming an auto-increment value.
        visit_id = cd.evaluate('document.querySelector(".visits").dataset.visitId')
        _, receipt = operator('/v1/patients/' + patient_id + '/encounters/' + visit_id +
                              '/notes/' + key + '/versions', {
            'synthetic': True, 'request_key': 'CONCURRENT-VISIT-NOTE-02',
            'expected_version': 1, 'body': note_b, 'note_kind': 'progress'})
        assert receipt['version'] == 2
        click('Save draft version')
        click('Compare with current version')
        body_is(note_b)
        assert cd.evaluate('document.querySelector("#visit-note-body").value') == note_c
        click('Save draft version')
        body_is(note_c)
        click('Previous version')
        body_is(note_b)
        click('Previous version')
        body_is(note_a)
        assert not cd.evaluate(button('Revise draft') + ' !== undefined')
        click('Next version')
        body_is(note_b)
        cd.command('Emulation.setDeviceMetricsOverride', {'width': 360, 'height': 740,
                   'deviceScaleFactor': 1, 'mobile': True})
        cd.wait('document.documentElement.scrollWidth <= innerWidth + 1', 'mobile reflow of immutable note')
        cd.evaluate('document.querySelector("#visits-title").scrollIntoView({block:"start"})')
        (artifacts / 'visits-note-mobile.png').write_bytes(base64.b64decode(
            cd.command('Page.captureScreenshot', {'format': 'png'})['data']))
        cd.command('Emulation.clearDeviceMetricsOverride')
        # Withdrawing note.read must remove the earlier version and note text.
        credentials[0]['actions'].remove('note.read')
        write_grants()
        click('Next version')
        cd.wait('document.querySelector(".visits [role=alert]") && !document.querySelector(".visit-original")',
                'denied note read clears earlier version')
        assert note_b not in cd.evaluate('document.body.innerText')
        click('Reload visit list')
        cd.wait('document.querySelector(".visit-row")', 'authorized visit list still available')
        cd.evaluate('document.querySelector(".visit-row").click()')
        cd.wait('document.querySelector(".visit-notes")?.textContent.includes("Note access is unavailable")',
                'visit and note grants remain independent')
        click('Complete visit')
        click('Confirm status change')
        cd.wait('document.querySelector(".visit-subtitle .visit-status")?.textContent==="Completed"',
                'completed status returned by the server')
        click('Back to visit list')
        cd.wait('document.querySelector(".visit-row .visit-status")?.textContent==="Completed"', 'persisted completed visit')
        (artifacts / 'visits-list-desktop.png').write_bytes(base64.b64decode(
            cd.command('Page.captureScreenshot', {'format': 'png'})['data']))
        print('PASS VISITS: schedule, status transitions, three immutable note versions, conflict comparison, focus, mobile reflow and revoked note access.')
    finally:
        credentials[0]['actions'] = previous
        write_grants()
        click('Overview', 'nav')
