"""Operator suspension through the real React/API/PostgreSQL application.

Only response delivery is fault-injected, after a real committed HTTP response.
The existing registry owns status, revision and the durable retry receipt.
"""
import base64
import json
import os
from urllib.error import HTTPError

from sqlalchemy import create_engine, text

from followthrough_journey import click, fill


def exercise(cd, token, credentials, write_grants, api, restart_api, artifacts):
    credential = credentials[0]
    saved_actions = list(credential['actions'])
    saved_patients = list(credential['patient_ids'])
    database = create_engine(os.environ['OI_API_DATABASE_URL'], hide_parameters=True)

    def nav(section):
        cd.evaluate("[...document.querySelectorAll('nav button')].find(e=>e.textContent.startsWith("
                    + json.dumps(section) + ")).click()")

    def open_patient(patient_id):
        nav('Overview')
        fill(cd, '#patient-id', patient_id)
        cd.evaluate("document.querySelector('#patient-id').form.requestSubmit()")
        cd.wait("document.querySelector('[data-testid=patient-card]')?.textContent.includes("
                + json.dumps(patient_id) + ")", 'fresh canonical patient identity')

    def seed(label):
        status, patient = api('/v1/patients', {
            'synthetic': True, 'request_key': 'SUSPENSION-BROWSER-' + label})
        assert status == 201
        patient_id = patient['patient_id']
        credential['patient_ids'].append(patient_id)
        write_grants()
        case = 'CASE-SUSPENSION-' + label
        root = '/v1/patients/' + patient_id
        status, _ = api(root + '/case-bindings', {
            'synthetic': True, 'case_id': case, 'source_organization': 'ORG-FICTIONAL-SUSPENSION',
            'source_system': 'SYS-SYNTH', 'source_subject_ref': 'SUBJECT-' + label,
            'review_ref': 'REVIEW-SYNTH'})
        assert status == 201
        original = (
            'OI-SYNTHETIC-REPORT/1\nPatient: ' + case + '\nDocument: DOC-SUSPENSION-' + label + '\n'
            'Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n'
            'Specimen: SPECIMEN-' + label + '\n'
            'Finding: marker|pending|Independently fictional suspension ' + label.lower() + ' marker.\n')
        status, source = api(root + '/cases/' + case + '/sources', {
            'synthetic': True, 'original_text': original})
        assert status == 201
        return patient_id, case, source['source_id']

    def load_sources(case):
        nav('Records')
        click(cd, '[data-testid=load-cases]')
        cd.wait("Boolean(document.querySelector('[data-testid=case-row]'))", 'authorized source case')
        cd.evaluate("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.textContent.includes("
                    + json.dumps(case) + ")).querySelector('[data-testid=load-sources]').click()")
        cd.wait("Boolean(document.querySelector('[data-testid=source-index]'))", 'actual original source history')

    def phase(expected):
        cd.wait("document.querySelector('[data-testid=suspension-status]')?.dataset.phase==="
                + json.dumps(expected), 'suspension phase ' + expected)

    def open_confirmation():
        nav('Overview')
        cd.evaluate("document.querySelector('[data-testid=patient-suspension-panel]').open=true")
        assert cd.evaluate("document.querySelector('[data-testid=suspension-submit]').disabled")
        click(cd, '[data-testid=suspension-confirm]')

    def registry_state(patient_id):
        with database.connect() as connection:
            patient = connection.execute(text(
                'SELECT status,revision FROM identity.identity_patients WHERE patient_id=:patient'),
                {'patient': patient_id}).one()
            events = connection.execute(text(
                "SELECT metadata_json FROM identity.identity_domain_events "
                "WHERE patient_id=:patient AND event_type='identity.patient.suspended' ORDER BY id"),
                {'patient': patient_id}).scalars().all()
        return tuple(patient), events

    def source_denied(path):
        try:
            api(path)
        except HTTPError as error:
            assert error.code == 404
            return error.code
        raise AssertionError('Suspended patient source access was unexpectedly allowed')

    try:
        credential['actions'] = list(dict.fromkeys(saved_actions + [
            'patient_create', 'patient_read', 'case_binding_create', 'case_binding_read',
            'source_import', 'source_read', 'source_original_read']))
        credential['actions'] = [action for action in credential['actions'] if action != 'patient_suspend']
        write_grants()
        victim, case, source_id = seed('TARGET')
        control, control_case, control_source = seed('CONTROL')
        control_path = f'/v1/patients/{control}/cases/{control_case}/sources/{control_source}'
        control_before = api(control_path)[1]
        assert registry_state(victim) == (('active', 1), [])

        # The preceding session-reset journey deliberately disconnected.
        fill(cd, '#credential', token)
        cd.evaluate("document.querySelector('#credential').form.requestSubmit()")
        cd.wait("!document.querySelector('#credential')", 'synthetic operator credential connected')
        open_patient(victim)
        load_sources(case)
        assert cd.evaluate("document.querySelector('[data-testid=source-statement]').textContent.includes('suspension target marker')")

        cd.evaluate(r"""(() => {
          const actualFetch=window.fetch;
          const state={writes:[],loseNext:false,restore:()=>{
            window.fetch=actualFetch;delete window.__oiSuspensionChecks;
          }};
          window.__oiSuspensionChecks=state;
          window.fetch=async(input,init)=>{
            const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
            const response=await actualFetch.call(window,input,init);
            if(!path.endsWith('/suspensions'))return response;
            const payload=await response.clone().json();
            state.writes.push({path,rawBody:init.body,body:JSON.parse(init.body),status:response.status,payload});
            if(state.loseNext&&response.status===200){state.loseNext=false;
              throw new TypeError('Synthetic response delivery lost after committed suspension');}
            return response;
          };
        })()""")

        # Being allowed to read the patient does not grant administrative suspension.
        open_confirmation()
        click(cd, '[data-testid=suspension-submit]')
        phase('rejected')
        denied = cd.evaluate('window.__oiSuspensionChecks.writes.at(-1)')
        assert denied['status'] == 404
        assert registry_state(victim) == (('active', 1), [])

        credential['actions'].append('patient_suspend')
        write_grants()
        open_patient(victim)
        load_sources(case)
        open_confirmation()
        cd.evaluate('window.__oiSuspensionChecks.loseNext=true')
        click(cd, '[data-testid=suspension-submit]')
        phase('unknown')
        committed = cd.evaluate('window.__oiSuspensionChecks.writes.at(-1)')
        assert committed['status'] == 200
        assert committed['body']['synthetic'] is True and committed['body']['expected_revision'] == 1
        assert set(committed['body']) == {'synthetic', 'request_key', 'expected_revision'}
        assert committed['payload'] == {'patient_id': victim, 'status': 'suspended', 'revision': 2}
        before_retry = registry_state(victim)
        assert before_retry[0] == ('suspended', 2) and len(before_retry[1]) == 1
        assert before_retry[1][0]['request_key'] == committed['body']['request_key']
        assert cd.evaluate("document.querySelector('#patient-id').disabled")
        # Navigation cannot resurrect the cached original while the outcome is unknown.
        nav('Records')
        assert cd.evaluate("!document.querySelector('[data-testid=source-index], [data-testid=server-original]')")
        nav('Overview')
        assert cd.evaluate("document.querySelector('[data-testid=patient-suspension-panel]').open"), 'Recovery must remain visible after navigation'

        # A real API restart proves retry uses PostgreSQL receipt history.
        restart_api()
        click(cd, '[data-testid=suspension-retry]')
        phase('confirmed')
        recovered = cd.evaluate('window.__oiSuspensionChecks.writes.at(-1)')
        assert recovered['status'] == 200 and recovered['payload'] == committed['payload']
        assert recovered['rawBody'] == committed['rawBody']
        assert registry_state(victim) == before_retry
        assert cd.evaluate("document.querySelector('[data-testid=patient-card]').textContent.includes('suspended')")
        assert cd.evaluate("document.querySelector('[data-testid=patient-suspension-panel]').textContent.includes('Registry revision 2')")
        assert cd.evaluate("!document.querySelector('[data-testid=patient-suspension-panel]').textContent.includes('Registry revision 1')")
        assert cd.evaluate("!document.querySelector('[data-testid=suspension-submit]') || document.querySelector('[data-testid=suspension-submit]').disabled")
        victim_root = '/v1/patients/' + victim
        denied_sources = source_denied(victim_root + '/cases/' + case + '/sources/' + source_id)
        denied_bindings = source_denied(victim_root + '/case-bindings')
        assert api(victim_root)[1]['status'] == 'suspended'
        nav('Records')
        assert cd.evaluate("!document.querySelector('[data-testid=source-index], [data-testid=server-original]')")

        # The independent fictional control remains usable in the same workspace.
        control_after = api(control_path)[1]
        assert control_after['access_receipt_id'] != control_before['access_receipt_id']
        assert {key: value for key, value in control_after.items() if key != 'access_receipt_id'} == {
            key: value for key, value in control_before.items() if key != 'access_receipt_id'}
        open_patient(control)
        load_sources(control_case)
        assert cd.evaluate("document.querySelector('[data-testid=source-statement]').textContent.includes('suspension control marker')")
        assert registry_state(control) == (('active', 1), [])
        open_patient(victim)
        cd.evaluate("document.querySelector('[data-testid=patient-suspension-panel]').open=true")
        cd.command('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1100, 'deviceScaleFactor': 1, 'mobile': False})
        cd.evaluate("document.querySelector('[data-testid=patient-suspension-panel]').scrollIntoView({block:'center'})")
        screenshot = cd.command('Page.captureScreenshot', {'format': 'png'})
        (artifacts / 'patient-suspension.png').write_bytes(base64.b64decode(screenshot['data']))
        (artifacts / 'patient-suspension.json').write_text(json.dumps({
            'synthetic': True, 'patient_id': victim, 'control_patient_id': control,
            'denied_suspension_status': denied['status'], 'receipt': recovered['payload'],
            'api_restarted_before_retry': True, 'identical_retry_body': True,
            'suspension_events': len(before_retry[1]), 'denied_source_status': denied_sources,
            'denied_case_bindings_status': denied_bindings, 'control_original_unchanged': True,
            'clinical_approval': False}, indent=2) + '\n')
        print('PASS PATIENT SUSPENSION: independent permission; real commit with lost response; '
              'API restart and identical retry; one durable event; cached records cleared; '
              'source access denied; separate fictional patient unchanged.')
    finally:
        cd.evaluate('window.__oiSuspensionChecks?.restore()')
        credential['actions'] = saved_actions
        credential['patient_ids'] = saved_patients
        write_grants()
        database.dispose()
