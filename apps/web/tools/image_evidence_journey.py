"""Real source-image UI joined to one canonical question, citation, task and report.

Image import is explicitly operator-controlled HTTP fixture setup. The browser
lists exact originals, downloads exact DICOM bytes, and renders only the bounded
non-diagnostic synthetic CT preview. It does not upload or clinically interpret
pixels. The existing pathology journey and all its acceptance assertions remain intact.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from browser_journey import wait_for
from followthrough_journey import (FollowthroughChecks, click, fill, navigate,
                                  select_case, _OBSERVE as TASK_OBSERVER)
from question_metadata_journey import _OBSERVE as METADATA_OBSERVER
from source_questions_journey import SourceQuestionChecks
from authored_evidence_journey import exercise as exercise_authored_evidence
from evidence_continuity_journey import exercise as exercise_evidence_continuity

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'apps/api/tests'))
from dicom_integrity_fixture import dicom_bytes

CASE = 'CASE-IMAGE-CONTINUITY'
REPORT = (
    'OI-SYNTHETIC-REPORT/1\nPatient: ' + CASE + '\nDocument: DOC-IMAGE-CONTINUITY\n'
    'Type: imaging\nEvent-Date: 2026-02-10\nIssued-At: 2026-02-11\n'
    'Finding: image|not-assessed|Independently authored engineering image; no clinical finding.\n'
)
AMENDED = REPORT.replace('Issued-At: 2026-02-11\n',
    'Issued-At: 2026-02-12\nAmends: DOC-IMAGE-CONTINUITY@1\n').replace(
    'no clinical finding.', 'amended fictional source wording; no clinical finding.')

OBSERVER = r"""(scope) => {
 if(window.__oiImageContinuityChecks)throw Error('Image observer already installed');
 const actualFetch=window.fetch,create=URL.createObjectURL;
 const state={responses:[],blobs:0,holdOriginal:false,held:false,release:null,released:0};
 state.restore=()=>{state.release?.();window.fetch=actualFetch;URL.createObjectURL=create;delete window.__oiImageContinuityChecks;};
 URL.createObjectURL=function(blob){state.blobs++;return create.call(URL,blob);};
 window.fetch=async(input,init)=>{
  const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
  const method=(init?.method??'GET').toUpperCase();
  const response=await actualFetch.call(window,input,init);
  if(!path.startsWith(scope))return response;
  const type=response.headers.get('Content-Type')??'';
  const observed={path,method,status:response.status};
  if(type==='application/dicom'&&response.ok){
   const raw=await response.clone().arrayBuffer();
   observed.byte_count=raw.byteLength;
   observed.sha256=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(x=>x.toString(16).padStart(2,'0')).join('');
   observed.access_receipt_id=response.headers.get('X-OI-Access-Receipt');
  }else if(type.startsWith('application/json'))observed.payload=await response.clone().json();
  state.responses.push(observed);
  if(state.holdOriginal&&response.ok&&type==='application/dicom'){
   state.holdOriginal=false;state.held=true;await new Promise(resolve=>state.release=resolve);
   state.held=false;state.release=null;state.released++;
  }
  return response;
 };
 window.__oiImageContinuityChecks=state;return true;
}"""


def exercise(cd, patient_id, token, credentials, write_grants, directory, artifacts, restart_api):
    artifacts = Path(artifacts) / 'image-evidence'
    artifacts.mkdir(parents=True, exist_ok=True)
    previous_actions = list(credentials[0]['actions'])
    case_path = f'/v1/patients/{patient_id}/cases/{CASE}'
    original = dicom_bytes(patient_id='SUBJECT-IMAGE', issuer='ORG-INSTITUTION/SYS-SYNTH',
        study_uid='2.25.33001', series_uid='2.25.33002', sop_uid='2.25.33003', study_date='20260210')
    original_sha = hashlib.sha256(original).hexdigest()
    downloads = []
    continuity = {}

    def operator(path, body=None, *, raw=None):
        # Fixture authority stays outside the application. Never log this header.
        headers = {'Authorization': 'Bearer ' + token}
        data = None
        if raw is not None:
            data = raw
            headers['Content-Type'] = 'application/dicom'
        elif body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        try:
            response = urlopen(Request('http://127.0.0.1:8000' + path, data=data, headers=headers), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            value = response.read()
            return response.status, value if response.headers.get_content_type() == 'application/dicom' else json.loads(value)

    def observed():
        return cd.evaluate('window.__oiImageContinuityChecks.responses')

    def latest(path, status=200):
        results = [entry for entry in observed() if entry['path'] == path and entry['status'] == status]
        assert results, f'No observed actual {status} response: {path}'
        return results[-1]

    def source_row(source_id):
        return ("[...document.querySelectorAll('[data-testid=source-version]')].find(e=>e.querySelector("
                "'[data-testid=source-verify] code')?.textContent===" + json.dumps(source_id) + ')')

    def press_enter():
        cd.command('Input.dispatchKeyEvent', {'type':'rawKeyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent', {'type':'char','key':'Enter','text':'\r','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})

    def source_click(source_id, test_id, *, keyboard=False):
        expression = source_row(source_id) + '.querySelector(' + json.dumps('[data-testid=' + test_id + ']') + ')'
        cd.wait('(()=>{const e=' + expression + ";return Boolean(e)&&!e.matches(':disabled');})()", 'enabled source control ' + test_id)
        if keyboard:
            cd.evaluate(expression + '.focus()')
            press_enter()
        else:
            cd.evaluate(expression + '.click()')

    def records(source_id, section='Records'):
        navigate(cd, section)
        click(cd, '[data-testid=load-cases]')
        row = ("[...document.querySelectorAll('[data-testid=case-row]')].find(e=>e.querySelector('code')?.textContent==="
               + json.dumps(CASE) + ')')
        cd.wait('Boolean(' + row + ')', 'independent canonical imaging case')
        expression = row + ".querySelector('[data-testid=load-sources]')"
        cd.wait('!(' + expression + ").matches(':disabled')", 'authorized source versions enabled')
        cd.evaluate(expression + '.click()')
        cd.wait('Boolean(' + source_row(source_id) + ')', 'exact imaging source version in existing Records')

    def inspect_images(source_id, *, expected_count=1, keyboard=False):
        before = len(observed())
        source_click(source_id, 'source-images-open', keyboard=keyboard)
        path = case_path + '/sources/' + source_id + '/images'
        cd.wait("window.__oiImageContinuityChecks.responses.slice(" + str(before) + ").some(row => "
                + "row.path === " + json.dumps(path) + " && row.method === 'GET' && row.status === 200 "
                + "&& row.payload?.access_receipt_id && row.payload.access_receipt_id === "
                + "document.querySelector('[data-testid=source-images-receipt]')?.textContent)",
                'fresh report-specific image index receipt rendered in Records')
        rendered_receipt = cd.evaluate("document.querySelector('[data-testid=source-images-receipt]').textContent")
        payload = next(row['payload'] for row in observed()[before:]
                       if row['path'] == path and row['method'] == 'GET' and row['status'] == 200
                       and row['payload']['access_receipt_id'] == rendered_receipt)
        assert (payload['patient_id'], payload['case_id'], payload['source_id']) == (patient_id, CASE, source_id)
        assert payload['synthetic'] is True and payload['source_identity_verified'] is False
        assert len(payload['images']) == expected_count
        assert cd.evaluate("document.querySelectorAll('[data-testid=source-image-row]').length") == expected_count
        displayed = cd.evaluate("""Array.from(document.querySelectorAll('[data-testid=source-image-row]'), row => [
            row.closest('[data-testid=source-image-study]').dataset.studyUid,
            row.closest('[data-testid=source-image-series]').dataset.seriesUid,
            row.closest('[data-testid=source-image-series]').querySelector('summary').textContent.split(' ')[0],
            row.dataset.imageId])""")
        assert sorted(displayed) == sorted([item['study_uid'], item['series_uid'], item['modality'], item['image_id']]
                                           for item in payload['images'])
        return payload

    def download_image(source_id, label, *, denied=False, selected_id=None, expected_original=None):
        selected_id = selected_id or image_id
        expected_original = original if expected_original is None else expected_original
        expected_sha = hashlib.sha256(expected_original).hexdigest()
        destination = artifacts / 'image-original-downloads' / label
        destination.mkdir(parents=True, exist_ok=True)
        cd.command('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(destination.resolve())})
        before = len(observed())
        blobs = cd.evaluate('window.__oiImageContinuityChecks.blobs')
        click(cd, '[data-image-id="' + selected_id + '"] [data-testid=source-image-download]')
        path = case_path + '/sources/' + source_id + '/images/' + selected_id
        cd.wait('window.__oiImageContinuityChecks.responses.length>' + str(before), 'fresh actual original image HTTP read')
        if denied:
            read = latest(path, 404)
            cd.wait("document.querySelector('[data-testid=source-image-download-status]')?.textContent.includes('unavailable or permission denied')", 'fresh original denial displayed')
            assert cd.evaluate('window.__oiImageContinuityChecks.blobs') == blobs
            assert not list(destination.iterdir())
            assert not cd.evaluate("Boolean(document.querySelector('[data-testid=source-image-download-receipt]'))")
            return read
        wait_for(lambda: len(list(destination.glob('*.dcm'))) == 1 and not list(destination.glob('*.crdownload')),
                 'actual original DICOM browser download')
        path_on_disk, = destination.glob('*.dcm')
        assert path_on_disk.read_bytes() == expected_original
        read = latest(path)
        assert read['sha256'] == expected_sha and read['byte_count'] == len(expected_original)
        cd.wait("document.querySelector('[data-testid=source-image-download-receipt]')?.textContent.includes("
                + json.dumps(read['access_receipt_id']) + ')', 'fresh image download receipt rendered')
        downloads.append({'source_id': source_id, 'image_id': selected_id, 'path': str(path_on_disk.relative_to(artifacts)),
                          'sha256': expected_sha, 'byte_count': len(expected_original), 'access_receipt_id': read['access_receipt_id']})
        return read

    def question_workspace(question_id):
        navigate(cd, 'Investigations')
        select_case(cd, CASE)
        click(cd, '[data-testid=load-source-questions]')
        row = f'.question-items li[data-question-id="{question_id}"]'
        cd.wait('Boolean(document.querySelector(' + json.dumps(row) + '))', 'same imaging question restored')
        return row

    def reopen_report(question_id, report_id):
        row = question_workspace(question_id)
        click(cd, row + ' [data-testid=authored-evidence-open]')
        report_row = f'[data-testid=evidence-report-row][data-report-id="{report_id}"] [data-testid=evidence-report-open]'
        click(cd, report_row)
        cd.wait("Boolean(document.querySelector('[data-testid=evidence-report-body]'))", 'independently authorized same-question report')
        return latest(case_path + '/questions/' + question_id + '/evidence-reports/' + report_id)['payload']

    try:
        credentials[0]['actions'] = sorted(set(previous_actions) | {
            'patient_read', 'case_binding_create', 'case_binding_read', 'source_import', 'source_read',
            'source_original_read', 'image_import', 'image_read', 'image_original_read', 'composer_context_read',
            'question_create', 'question_read', 'review_packet_read', 'source_brief_export',
            'followthrough_read', 'followthrough_create', 'followthrough_update', 'evidence_read', 'evidence_link'})
        write_grants()
        status, mapping = operator(f'/v1/patients/{patient_id}/case-bindings', {'synthetic': True, 'case_id': CASE,
            'source_organization': 'ORG-INSTITUTION', 'source_system': 'SYS-SYNTH',
            'source_subject_ref': 'SUBJECT-IMAGE', 'review_ref': 'REVIEW-IMAGE-FICTIONAL'})
        assert status == 201 and mapping['case_id'] == CASE and mapping['source_identity_verified'] is False
        status, imported = operator(case_path + '/sources', {'synthetic': True, 'original_text': REPORT})
        assert status == 201 and imported['result'] == 'imported'
        source_id = imported['source_id']
        status, stored = operator(case_path + '/sources/' + source_id + '/images', raw=original)
        assert status == 201 and stored['result'] == 'imported' and stored['sha256'] == original_sha
        assert stored['source_identity_verified'] is stored['clinical_interpretation'] is False
        image_id = stored['image_id']
        cd.evaluate('(' + OBSERVER + ')(' + json.dumps(case_path) + ')')
        cd.evaluate('(' + METADATA_OBSERVER + ')()')
        cd.evaluate('(' + TASK_OBSERVER + ')()')

        records(source_id, 'Imaging')
        assert cd.evaluate("document.querySelector('h1').textContent==='Imaging'")
        initial_index = inspect_images(source_id)
        assert initial_index['images'][0]['image_id'] == image_id
        initial_download = download_image(source_id, 'initial')
        click(cd, '[data-testid=source-image-preview-open]')
        cd.wait("(()=>{const e=document.querySelector('[data-testid=source-image-preview]');return Boolean(e)&&e.complete&&e.naturalWidth===2&&e.naturalHeight===2;})()",
                'bounded non-diagnostic image preview rendered')
        warning = cd.evaluate("document.querySelector('[data-testid=source-image-preview-panel]').textContent")
        assert 'Not for diagnosis.' in warning and 'does not apply diagnostic windowing' in warning
        preview_receipt = cd.evaluate("document.querySelector('[data-testid=source-image-preview-receipt]').textContent")
        assert preview_receipt.startswith('ACCESS-') and len(preview_receipt) == 39
        continuity['preview_access_receipt_id'] = preview_receipt
        cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate("document.querySelector('[data-testid=source-image-preview-panel]').scrollIntoView({block:'center'})")
        (artifacts / 'image-preview-desktop.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        click(cd, '[data-testid=source-image-preview-close]')
        cd.wait("!document.querySelector('[data-testid=source-image-preview-panel]') && document.activeElement.dataset.testid==='source-image-preview-open'", 'closing the preview removes the pixels and restores focus to the opening action')
        cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        cd.evaluate("document.querySelector('[data-testid=source-images-inspection]').scrollIntoView({block:'center'})")
        (artifacts / 'image-original-desktop.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))
        source_click(source_id, 'source-images-close', keyboard=True)
        cd.wait("!document.querySelector('[data-testid=source-images-inspection]')", 'native keyboard closes image disclosure')
        assert cd.evaluate('document.activeElement===' + source_row(source_id) + ".querySelector('[data-testid=source-images-open]')"), 'closing returns focus to the same source opener'
        reopened_index = inspect_images(source_id, keyboard=True)
        assert reopened_index['access_receipt_id'] != initial_index['access_receipt_id']

        # Hold an actual authorized response, then leave the source workspace.
        # A valid server receipt must not restore a discarded browser download.
        cd.evaluate('window.__oiImageContinuityChecks.holdOriginal=true')
        blobs = cd.evaluate('window.__oiImageContinuityChecks.blobs')
        click(cd, '[data-testid=source-image-download]')
        cd.wait('window.__oiImageContinuityChecks.held', 'actual original response held before browser delivery')
        navigate(cd, 'Overview')
        cd.evaluate('window.__oiImageContinuityChecks.release()')
        cd.wait('window.__oiImageContinuityChecks.released===1', 'original response released into departed scope')
        cd.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))')
        assert cd.evaluate('window.__oiImageContinuityChecks.blobs') == blobs
        assert not cd.evaluate("Boolean(document.querySelector('[data-testid=source-image-download-receipt]'))")

        records(source_id)
        before_posts = len([r for r in observed() if r['method'] == 'POST'])
        source_click(source_id, 'ask-source-question')
        cd.wait("Boolean(document.querySelector('[data-testid=question-draft]'))", 'existing exact-source handoff for imaging report')
        assert len([r for r in observed() if r['method'] == 'POST']) == before_posts
        fill(cd, '[data-testid=question-draft]', 'Which exact fictional imaging source and original should be discussed before interpreting this entry?')
        click(cd, '[data-testid=prepare-custom-question]')
        cd.wait("document.querySelector('[data-testid=composer-context]')?.textContent.includes(" + json.dumps(source_id) + ')', 'explicit imaging source preflight')
        questions = SourceQuestionChecks(cd, source_id)
        question_id = questions.save()
        questions.history(question_id)
        scope = case_path + '/questions/' + question_id
        task_checks = FollowthroughChecks(cd, patient_id, CASE, question_id, source_id)

        def report_continuity(report, path, body):
            # Reuse the existing separate citation/report rights and exact-file checks.
            exercise_evidence_continuity(cd, patient_id, CASE, question_id, source_id,
                credentials, write_grants, artifacts, report, path, body)
            task_id = task_checks.create('Discuss the fictional source and its original image')
            task = next(row for row in task_checks.projection()['tasks'] if row['task_id'] == task_id)
            assert task['question_id'] == question_id and task['source_id'] == source_id
            assert task['source_snapshot_sha256'] == report['snapshot']['question']['source_snapshot_sha256']
            continuity.update(question_id=question_id, source_id=source_id, task_id=task_id,
                              report_id=report['report_id'], report_body_sha256=report['body_sha256'],
                              report_snapshot_sha256=report['snapshot_sha256'])

            credentials[0]['actions'].remove('image_original_read');write_grants()
            records(source_id);inspect_images(source_id)
            denied = download_image(source_id, 'denied-original', denied=True)
            fresh = reopen_report(question_id, report['report_id'])
            assert fresh['body'] == report['body'] and fresh['snapshot_sha256'] == report['snapshot_sha256']
            row = f'.question-items li[data-question-id="{question_id}"]'
            click(cd, row + ' [data-testid=metadata-evidence-open]')
            cd.wait('Boolean(document.querySelector(' + json.dumps(row + ' [data-testid=evidence-saved-link]') + '))', 'metadata still independent of original-image denial')
            assert latest(scope + '/evidence-links')['payload']['links'][0]['citation'] == 'FICT-TRIAL-PREPARATION@1'
            continuity['image_original_denial_status'] = denied['status']
            credentials[0]['actions'].append('image_original_read')
            credentials[0]['actions'].remove('evidence_report_export');write_grants()
            prior = len(observed());blobs_before = cd.evaluate('window.__oiImageContinuityChecks.blobs')
            click(cd, '[data-testid=evidence-report-download]')
            cd.wait('window.__oiImageContinuityChecks.responses.length>' + str(prior)
                    + " && !document.querySelector('[data-testid=evidence-report-body]')", 'fresh report denial before independent image download')
            assert latest(scope + '/evidence-reports/' + report['report_id'], 404)['status'] == 404
            assert cd.evaluate('window.__oiImageContinuityChecks.blobs') == blobs_before
            records(source_id);inspect_images(source_id);download_image(source_id, 'report-export-denied')
            credentials[0]['actions'].append('evidence_report_export');write_grants()
            fresh = reopen_report(question_id, report['report_id'])
            assert fresh['body'] == report['body'] and path.read_bytes() == body
            task_checks.refresh(expected_count=1)
            cd.command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
            cd.evaluate("document.querySelector('[data-testid=evidence-report-preview]').scrollIntoView({block:'center'})")
            (artifacts / 'image-question-report-desktop.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))

        exercise_authored_evidence(cd, patient_id, CASE, question_id, source_id, credentials,
            write_grants, directory, artifacts, restart_api, operator, on_report=report_continuity)
        authored = json.loads((artifacts / 'question-evidence-workflow.json').read_text())
        assert authored['question_id'] == question_id and authored['source_id'] == source_id
        assert authored['historical_download_carries_fresh_status_and_receipt'] is True
        first, historical, replacement = authored['reports']
        assert first['report_id'] == historical['report_id'] == continuity['report_id']
        assert first['body_sha256'] == historical['body_sha256']
        assert first['download_sha256'] != historical['download_sha256']
        # The inherited authored journey really restarted the API. Original image
        # permission is still independent of its later evidence withdrawal.
        records(source_id);inspect_images(source_id);download_image(source_id, 'after-api-restart-and-evidence-withdrawal')

        status, corrected = operator(case_path + '/sources', {'synthetic': True, 'original_text': AMENDED})
        assert status == 201 and corrected['version'] == 2
        current_source = corrected['source_id']
        assert current_source != source_id
        assert operator(case_path + '/sources/' + source_id + '/images/' + image_id)[0] == 404
        assert operator(case_path + '/sources/' + current_source + '/images/' + image_id)[0] == 404
        records(current_source);inspect_images(current_source, expected_count=0)
        for selected_source, expected_state in ((source_id, 'superseded'), (current_source, 'current')):
            selected = cd.evaluate('(()=>{const row=' + source_row(selected_source)
                + ";return row?{source_id:row.querySelector('[data-testid=source-verify] code')?.textContent,"
                  "state:row.querySelector('.record-state')?.textContent}:null;})()")
            assert selected == {'source_id': selected_source, 'state': expected_state}
        assert cd.evaluate('!(' + source_row(source_id) + ").querySelector('[data-testid=source-images-open]')")
        row = question_workspace(question_id)
        cd.wait('document.querySelector(' + json.dumps(row) + ")?.textContent.includes('Source changed — reassessment required')", 'old imaging question requires reassessment')
        task_projection = task_checks.refresh(expected_count=1)
        task, = task_projection['tasks']
        assert task['task_id'] == continuity['task_id'] and task['question_id'] == question_id
        assert task['source_id'] == source_id and task['needs_recheck'] is True
        click(cd, row + ' [data-testid=metadata-evidence-open]')
        cd.wait('Boolean(document.querySelector(' + json.dumps(row + ' [data-testid=evidence-saved-link]') + '))', 'amended-source citation keeps its original question')
        metadata = latest(scope + '/evidence-links')['payload']
        assert metadata['source_context_state'] == 'source_reassessment_required'

        # Relink only by the existing explicit source-image import operation.
        # It neither rewrites the old question nor creates a replacement report.
        status, relinked = operator(case_path + '/sources/' + current_source + '/images', raw=original)
        assert status == 201 and relinked['result'] == 'linked' and relinked['image_id'] == image_id
        records(current_source);inspect_images(current_source);download_image(current_source, 'explicit-current-source-relink')
        # The browser must nest a mixed-modality study and a separate study
        # from the same authorized report without inferring an acquisition order.
        for study, series, sop, modality in (('2.25.33001', '2.25.33004', '2.25.33005', 'MR'),
                                             ('2.25.33006', '2.25.33007', '2.25.33008', 'CT')):
            added = dicom_bytes(modality=modality, patient_id='SUBJECT-IMAGE', issuer='ORG-INSTITUTION/SYS-SYNTH',
                             study_uid=study, series_uid=series, sop_uid=sop, study_date='20260210')
            status, imported = operator(case_path + '/sources/' + current_source + '/images', raw=added)
            assert status == 201
            if modality == 'MR':
                mr_id, mr_original = imported['image_id'], added
        source_click(current_source, 'source-images-close')
        mixed = inspect_images(current_source, expected_count=3)
        assert len({row['study_uid'] for row in mixed['images']}) == 2
        assert {row['modality'] for row in mixed['images'] if row['study_uid'] == '2.25.33001'} == {'CT', 'MR'}
        assert cd.evaluate("document.querySelectorAll('[data-testid=source-image-study]').length") == 2
        assert cd.evaluate("document.querySelectorAll('[data-testid=source-image-series]').length") == 3
        mr_row = '[data-image-id="' + mr_id + '"]'
        assert cd.evaluate("!document.querySelector(" + json.dumps(mr_row + ' [data-testid=source-image-preview-open]') + ")")
        assert cd.evaluate("document.querySelector(" + json.dumps(mr_row + ' [data-testid=source-image-preview-unavailable]') + ").textContent.includes('MR preview is unavailable')")
        download_image(current_source, 'mr-original', selected_id=mr_id, expected_original=mr_original)
        before_toggle = len(observed())
        summary = "document.querySelector(" + json.dumps(mr_row) + ").closest('details[data-testid=source-image-series]').querySelector('summary')"
        cd.evaluate(summary + '.focus()')
        cd.command('Input.dispatchKeyEvent', {'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.wait("!(" + summary + ").parentElement.open", 'keyboard collapses the exact MR series')
        cd.command('Input.dispatchKeyEvent', {'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.command('Input.dispatchKeyEvent', {'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
        cd.wait("(" + summary + ").parentElement.open", 'keyboard reopens the exact MR series')
        assert len(observed()) == before_toggle, 'Grouping disclosure must not fetch or write'
        cd.command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
        cd.wait('document.documentElement.scrollWidth<=innerWidth+1', 'image inspector stays within narrow browser viewport')
        cd.evaluate("document.querySelector('[data-testid=source-images-inspection]').scrollIntoView({block:'start'})")
        (artifacts / 'image-original-narrow.png').write_bytes(base64.b64decode(cd.command('Page.captureScreenshot', {'format':'png'})['data']))

        for download in downloads:
            assert hashlib.sha256((artifacts / download['path']).read_bytes()).hexdigest() == download['sha256']
        assert len({entry['access_receipt_id'] for entry in downloads}) == len(downloads)
        for report in authored['reports']:
            retained = (artifacts / report['download_relative_path']).read_bytes()
            assert hashlib.sha256(retained).hexdigest() == report['download_sha256']
        receipt = {'contract':'oi.h1-image-evidence-browser/1', 'patient_id':patient_id, 'case_id':CASE,
            **continuity, 'image_id':image_id, 'image_sha256':original_sha, 'image_byte_count':len(original),
            'initial_image_index_access_receipt_id':initial_index['access_receipt_id'],
            'image_downloads':downloads, 'metadata_link':metadata['links'][0],
            'task_after_source_amendment':task, 'replacement_source_id':current_source,
            'report_downloads':authored['reports'], 'image_import_is_operator_http_fixture_setup':True,
            'late_original_after_navigation_created_no_download':True,
            'keyboard_open_close_retains_source_focus':True,
            'image_and_report_permissions_remain_independent':True,
            'evidence_amendment_preserves_body_with_fresh_historical_cover':True,
            'source_amendment_requires_explicit_image_relink_and_question_task_reassessment':True,
            'api_restart_preserves_original_image_and_report_history':True,
            'non_diagnostic_preview_rendered_from_fresh_authorized_original':True,
            'diagnostic_windowing_applied':False, 'mixed_ct_mr_study_series_verified':True,
            'mr_original_downloaded_with_fresh_receipt':True, 'mr_preview_withheld':True,
            'retained_downloads_unchanged':True, 'synthetic':True, 'pixels_interpreted':False,
            'clinical_approval':False, 'model_executed':False}
        (artifacts / 'image-evidence-continuity.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('PASS IMAGE EVIDENCE CONTINUITY: actual source-image UI download, exact canonical imaging question, '
              'metadata citation, recorded task and authored comparison/report; independent image/report denial, '
              'late original suppression, actual API restart, preserved historical report cover and explicit '
              'source-amendment image relink. Original/report bytes retained. Fictional custody only; no pixel interpretation.')
    finally:
        for name in ('__oiFollowthroughChecks','__oiMetadataEvidenceChecks','__oiImageContinuityChecks'):
            cd.evaluate('window.' + name + '?.restore()')
        credentials[0]['actions'] = previous_actions
        write_grants()
        navigate(cd, 'Overview')
