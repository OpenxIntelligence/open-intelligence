"""Live Chromium proof: two different authorized actors inspect the same amended Observation."""
from datetime import datetime
import base64
import hashlib
import json
import re
import secrets

from followthrough_journey import click, fill, navigate, select_case


def exercise(cd, patient, case, task, original, latest, token, credentials, write_grants,
             open_recorded_task, task_at_revision, artifacts):
    tid, qid, ref = (task[k] for k in ('task_id', 'question_id', 'observation_reference'))
    task_card = f'[data-testid=followthrough-task][data-task-id="{tid}"]'
    case_path = f'/v1/patients/{patient}/cases/{case}'
    detail = f'{case_path}/followthrough/{tid}/laboratory-amendment-review'
    inbox = case_path + '/laboratory-amendment-requests'
    transition = f'{case_path}/followthrough/{tid}/transitions'
    request_reason = 'Please compare the transcription of the fictional original with its amendment.'
    response_reason = 'I checked the source-reported numbers on both versions of this fictional result.'
    requester = credentials[0]
    reviewer_token = secrets.token_urlsafe(32)
    reviewer = dict(actor='ACTOR-LAB-TRANSCRIPTION-REVIEWER', organization=requester['organization'],
                    purpose='operations', patient_ids=[patient], expires_at=requester['expires_at'],
                    token_sha256=hashlib.sha256(reviewer_token.encode()).hexdigest(),
                    actions=['patient_read', 'case_binding_read', 'source_read', 'source_original_read',
                             'question_read', 'followthrough_read', 'review_queue_read'])
    assert all(reviewer['actor'] != c['actor'] for c in credentials)
    credentials.append(reviewer)
    # Pass through every real response. Retain only these paths and their fictional JSON;
    # neither credential values nor request/response headers are collected.
    cd.evaluate("""(paths => {
      const previous = window.fetch, packets = [];
      window.__amendmentProof = {packets, restore() {window.fetch = previous; delete window.__amendmentProof;}};
      window.fetch = async (input, init) => {
        const response = await previous.call(window, input, init);
        const path = new URL(input instanceof Request ? input.url : input, location.href).pathname;
        if (paths.includes(path)) packets.push({path, method: init?.method ?? input?.method ?? 'GET',
          status: response.status, result: await response.clone().json()});
        return response;
      };
    })(""" + json.dumps([detail, inbox, transition]) + ')')

    def test_id(name):
        return f'[data-testid=amendment-{name}]'

    def call(selector, path, method, status):
        packets = 'window.__amendmentProof.packets'
        offset = cd.evaluate(packets + '.length')
        click(cd, selector)
        packet = cd.wait(f'{packets}.slice({offset}).find(r => r.method === {json.dumps(method)} '
                         f'&& r.path === {json.dumps(path)})', f'{method} {path.rsplit("/", 1)[-1]} from browser')
        assert packet['status'] == status, (method, path, packet)
        return packet['result']

    def text_of(name):
        return 'document.querySelector(' + json.dumps(test_id(name)) + ')?.innerText'

    def connect(bearer):
        # Disconnect through the UI rather than reusing the previous principal or substituting fetch credentials.
        cd.evaluate('[...document.querySelectorAll("nav button")].find(b=>b.textContent.startsWith("Overview")).click()')
        cd.wait('[...document.querySelectorAll("button")].some(b=>b.textContent==="Disconnect and clear")', 'disconnect control')
        cd.evaluate('[...document.querySelectorAll("button")].find(b=>b.textContent==="Disconnect and clear").click()')
        cd.wait('Boolean(document.querySelector("#credential"))', 'disconnected credential cleared')
        assert not cd.evaluate('Boolean(document.querySelector("[data-testid=patient-card]"))')
        fill(cd, '#credential', bearer)
        cd.evaluate('document.querySelector("#credential").form.requestSubmit()')
        cd.wait('!document.querySelector("#credential") && !document.querySelector("#patient-id").disabled',
                'new credential connected')
        fill(cd, '#patient-id', patient)
        cd.evaluate('document.querySelector("#patient-id").form.requestSubmit()')
        cd.wait('document.querySelector("[data-testid=patient-card]")?.innerText.includes(' + json.dumps(patient) + ')',
                'same patient reopened under new authority')
        navigate(cd, 'Journey')
        click(cd, '[data-testid=world-load-cases]')
        select_case(cd, case)

    def compare(packet):
        assert (packet['contract'], packet['patient_id'], packet['case_id'], packet['task_id'], packet['question_id'],
                packet['observation_reference'], packet['clinical_approval']) == (
                    'oi.laboratory-amendment-review/1', patient, case, tid, qid, ref, False)
        for side, (source, raw) in (('original', original), ('latest', latest)):
            report = packet[side]
            assert (report['source_id'], report['document_id'], report['version'], report['sha256']) == (
                source['source_id'], source['document_id'], source['version'], hashlib.sha256(raw).hexdigest())
            stored = report['observation']
            literal, = [e['resource'] for e in json.loads(raw)['entry'] if
                        e['resource']['resourceType'] + '/' + e['resource']['id'] == ref]
            value, code = literal['valueQuantity'], literal['code']['coding'][0]['code']
            assert (stored['value_text'], stored['unit_code'], stored['loinc_code'], stored['status'],
                    stored['absent_reason'], stored['specimen_reference']) == (
                        str(value['value']), value['code'], code, 'reported_value', None, 'Specimen/FICT-WEB-SPEC')
            for field, source_field in [('issued_at', 'issued'), ('effective_at', 'effectiveDateTime')]:
                assert datetime.fromisoformat(stored[field]) == datetime.fromisoformat(literal[source_field])
            rendered = cd.wait(text_of('comparison-' + side), side + ' report shown')
            assert all(v in rendered for v in (source['source_id'], report['sha256'], code, stored['specimen_reference'])), rendered
            assert re.search(r'(?<![\w.])' + re.escape(stored['value_text']) + r'\s+'
                             + re.escape(stored['unit_code']) + r'(?!\w)', rendered), rendered
        assert packet['original']['sha256'] != packet['latest']['sha256']

    def open_inbox(request_id):
        navigate(cd, 'Review')
        pending = call(test_id('inbox-load'), inbox, 'GET', 200)
        assert (pending['contract'], pending['patient_id'], pending['case_id'], pending['clinical_approval']) == (
            'oi.laboratory-amendment-inbox/1', patient, case, False)
        assert pending['requests'] == [dict(request_id=request_id, task_id=tid, question_id=qid,
                                           latest_source_id=latest[0]['source_id'])]
        packet = call(test_id('inbox-open'), detail, 'GET', 200)
        compare(packet)
        assert len(packet['entries']) == 1 and packet['entries'][0]['entry_id'] == request_id
        return packet['entries'][0]

    def respond(status):
        selector = json.dumps(test_id('response-disposition'))
        cd.wait('Boolean(document.querySelector(' + selector + ')?.querySelector("option[value=transcription_checked]"))',
                'transcription disposition offered')
        cd.evaluate('(() => {const e=document.querySelector(' + selector + ');e.value="transcription_checked";'
                    'e.dispatchEvent(new Event("change",{bubbles:true}));})()')
        fill(cd, test_id('response-reason'), response_reason)
        return call(test_id('response-submit'), detail, 'POST', status)

    try:
        write_grants()
        opener = task_card + ' ' + test_id('review-open')
        initial = call(opener, detail, 'GET', 200)
        compare(initial)
        assert initial['entries'] == []
        fill(cd, test_id('request-reason'), request_reason)
        saved = call(test_id('request-submit'), detail, 'POST', 201)
        request_id = saved['request_id']
        assert saved == dict(entry_id=request_id, request_id=request_id, duplicate=False)
        assert re.fullmatch(r'VERIFY-[0-9A-F]{32}', request_id)
        cd.wait(f'{text_of("review-history")}?.includes({json.dumps(request_reason)})',
                'request appears in the requester’s protected history')

        connect(reviewer_token)
        requested = open_inbox(request_id)
        assert requested['actor'] == requester['actor'] and requested['reason'] == request_reason
        denied = respond(404)
        assert set(denied) == {'detail'} and all(v not in str(denied) for v in (tid, qid, ref, request_id))
        cd.wait('!document.querySelector("[data-testid=amendment-response-submit]") && '
                '!document.querySelector("[data-testid=amendment-review-history]")',
                'refused response clears protected detail')
        reviewer['actions'].append('review_return')
        write_grants()
        connect(reviewer_token)
        assert open_inbox(request_id) == requested, 'refused response must leave the exact request pending'
        saved_response = respond(201)
        response_id = saved_response['entry_id']
        assert re.fullmatch(r'VERIFY-[0-9A-F]{32}', response_id) and response_id != request_id
        assert saved_response == dict(entry_id=response_id, request_id=request_id, duplicate=False)
        cd.wait(f'{text_of("review-history")}?.includes({json.dumps(response_reason)})',
                'reviewer independently reads back the response before connection changes')
        assert call(test_id('inbox-load'), inbox, 'GET', 200)['requests'] == []

        connect(token)
        open_recorded_task()
        reopened = call(opener, detail, 'GET', 200)
        compare(reopened)
        first, reply = reopened['entries']
        assert first == requested and first['action'] == 'request' and reply['action'] == 'respond'
        assert (reply['actor'], reply['request_id'], reply['entry_id'], reply['reason'], reply['disposition']) == (
            reviewer['actor'], request_id, response_id, response_reason, 'transcription_checked')
        for event in (first, reply):
            assert (event['original_source_id'], event['latest_source_id'], event['latest_sha256']) == (
                original[0]['source_id'], latest[0]['source_id'], latest[0]['sha256'])
        cd.wait(f'{text_of("review-history")}?.includes({json.dumps(response_reason)})',
                'requesting actor sees the distinct reviewer’s response on the original task')
        assert task_at_revision(3) == task
        viewport = cd.evaluate('({width:innerWidth,height:innerHeight})')
        for width, height in ((1440, 1100), (390, 844)):
            cd.command('Emulation.setDeviceMetricsOverride', {
                'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
            cd.evaluate('document.querySelector("[data-testid=amendment-review-panel]").scrollIntoView()')
            assert cd.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), 'amendment view overflows'
            (artifacts / f'laboratory-amendment-review-{width}.png').write_bytes(base64.b64decode(
                cd.command('Page.captureScreenshot', {'format': 'png'})['data']))
        cd.command('Emulation.setDeviceMetricsOverride', {**viewport, 'deviceScaleFactor': 1, 'mobile': False})
        transitions = cd.evaluate('window.__amendmentProof.packets.filter(r=>r.path===' + json.dumps(transition) + ')')
        assert transitions == [] and task['needs_recheck'] and task['status'] == 'acknowledged'
        (artifacts / 'laboratory-amendment-human-review.json').write_text(json.dumps({
            'synthetic': True, 'patient_id': patient, 'case_id': case, 'task_id': tid, 'question_id': qid,
            'observation_reference': ref, 'original': reopened['original'], 'latest': reopened['latest'],
            'entries_reopened_by_requester': reopened['entries'], 'request': saved, 'response': saved_response,
            'http': [{k: p[k] for k in ('method', 'path', 'status')} for p in cd.evaluate('window.__amendmentProof.packets')],
            'task_history': task['history'], 'revision': task['revision'], 'status': task['status'],
            'source_context_state': task['source_context_state'], 'needs_recheck': task['needs_recheck'],
            'clinical_approval': reopened['clinical_approval'], 'task_transitions': transitions,
        }, indent=2) + '\n')
        print('PASS LAB AMENDMENT REVIEW: two authorized actors compared the original and amended values; '
              'response permission was independently denied and restored. The task remains acknowledged and stale.')
    finally:
        credentials.remove(reviewer)
        write_grants()
        cd.evaluate('window.__amendmentProof.restore()')
