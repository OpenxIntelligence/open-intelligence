"""Actual React/HTTP/PostgreSQL human evidence workflow; fictional authored inputs.

The observer only records actual responses. One deliberate lost response occurs
after the real server commits, to verify exact recovery through the visible UI.
No patient/evidence/report response is fabricated or substituted.
"""
import base64
import hashlib
import json
from pathlib import Path

from browser_journey import wait_for


SUPPORT = (
    'OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVD-VIOLET-SUPPORT\n'
    'Title: Independently invented violet worksheet\nIssued-At: 2026-01-14\n'
    'Rights: original-synthetic\n'
    'Statement: In this invented worksheet, café 🧪 labels matched the violet pattern; '
    '<script>literal</script> is authored text, not a clinical finding.\n'
)
COUNTER = (
    'OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVD-VIOLET-COUNTER\n'
    'Title: Independently invented counterexample worksheet\nIssued-At: 2026-01-15\n'
    'Rights: original-synthetic\n'
    'Statement: A separate invented worksheet contradicted the violet pattern; '
    'the entry was absent in this authored example.\n'
)
AMENDED_SUPPORT = (
    'OI-SYNTHETIC-EVIDENCE/1\nEvidence: EVD-VIOLET-SUPPORT\n'
    'Title: Corrected independently invented violet worksheet\nIssued-At: 2026-01-16\n'
    'Rights: original-synthetic\nAmends: EVD-VIOLET-SUPPORT@1\n'
    'Statement: The corrected invented worksheet records café 🧪 labels as uncertain; '
    'its earlier violet pattern requires fresh human comparison.\n'
)

_OBSERVE = r"""() => {
  const fetch=window.fetch, create=URL.createObjectURL;
  const state={responses:[],blobs:0,loseAssessment:false};
  state.restore=()=>{window.fetch=fetch;URL.createObjectURL=create;delete window.__oiEvidenceChecks;};
  URL.createObjectURL=function(blob){state.blobs++;return create.call(this,blob);};
  window.fetch=async(input,init)=>{
    const path=new URL(input instanceof Request?input.url:input,location.href).pathname;
    const method=init?.method??'GET';
    const result=await fetch.call(window,input,init);
    if(/\/questions\/QUESTION-[0-9A-F]{32}\/evidence(?:[/-]|$)/.test(path)){
      const payload=await result.clone().json();
      state.responses.push({path,method,status:result.status,payload});
      if(state.loseAssessment&&method==='POST'&&path.endsWith('/evidence-assessments')&&result.ok){
        state.loseAssessment=false;throw new TypeError('Simulated loss after actual evidence commit');
      }
    }
    return result;
  };
  window.__oiEvidenceChecks=state;
  return true;
}"""


def exercise(cd, patient_id, case_id, question_id, source_id, credentials,
             write_grants, directory, artifacts, restart_api):
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    directory = Path(directory)
    previous_actions = list(credentials[0]['actions'])
    credentials[0]['actions'] = sorted(set(previous_actions) | {
        'patient_read', 'source_read', 'question_read', 'authored_evidence_read',
        'authored_evidence_import', 'authored_evidence_assess', 'authored_evidence_withdraw',
        'authored_evidence_original_read', 'evidence_report_export'})
    write_grants()
    cd.evaluate('(' + _OBSERVE + ')()')
    scope = f'/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}'
    row = f'.question-items li[data-question-id="{question_id}"]'

    def click(selector):
        cd.evaluate('document.querySelector(' + json.dumps(selector) + ').click()')

    def value(selector, text):
        cd.evaluate("""(()=>{const e=document.querySelector(""" + json.dumps(selector) + """);
          const proto=e instanceof HTMLTextAreaElement?HTMLTextAreaElement.prototype:
            e instanceof HTMLSelectElement?HTMLSelectElement.prototype:HTMLInputElement.prototype;
          Object.getOwnPropertyDescriptor(proto,'value').set.call(e,""" + json.dumps(text) + """);
          e.dispatchEvent(new Event(e instanceof HTMLSelectElement?'change':'input',{bubbles:true}));})()""")

    def navigate(section):
        cd.evaluate("[...document.querySelectorAll('nav[aria-label=\"Patient workspace\"] button')]"
                    '.find(e=>e.textContent.includes(' + json.dumps(section) + ')).click()')

    def responses():
        return cd.evaluate('window.__oiEvidenceChecks.responses')

    def last(suffix, method='GET', status=200):
        matches = [r for r in responses() if r['path'] == scope + suffix
                   and r['method'] == method and r['status'] == status]
        assert matches, f'No actual {status} {method} {suffix} response'
        return matches[-1]['payload']

    def inspect():
        navigate('Investigations')
        click('[data-testid=load-source-questions]')
        cd.wait('Boolean(document.querySelector(' + json.dumps(row) + '))', 'saved question for evidence')
        prior = len(responses())
        click(row + ' [data-testid=evidence-open]')
        cd.wait('window.__oiEvidenceChecks.responses.length>' + str(prior)
                + " && Boolean(document.querySelector('[data-testid=evidence-panel]'))",
                'fresh case-owned evidence packet')
        packet = last('/evidence')
        assert packet['question']['question_id'] == question_id
        assert (packet['patient_id'], packet['case_id']) == (patient_id, case_id)
        assert packet['question']['source_id'] == source_id
        assert packet['human_review_state'] == 'not_performed'
        assert packet['clinical_approval'] is packet['model_executed'] is False
        return packet

    def upload(text, item, filename):
        path = directory / filename
        path.write_text(text, encoding='utf-8')
        assert path.read_bytes() == text.encode('utf-8')
        value('[data-testid=evidence-content-item]', item)
        if not cd.evaluate("document.querySelector('[data-testid=evidence-fictional]').checked"):
            click('[data-testid=evidence-fictional]')
        root = cd.command('DOM.getDocument')['root']['nodeId']
        node = cd.command('DOM.querySelector', {'nodeId': root,
                          'selector': '[data-testid=evidence-file]'})['nodeId']
        cd.command('DOM.setFileInputFiles', {'nodeId': node, 'files': [str(path.resolve())]})
        cd.wait("!document.querySelector('[data-testid=evidence-import]').disabled",
                'literal authored evidence upload ready')
        before = len(responses())
        click('[data-testid=evidence-import]')
        cd.wait('window.__oiEvidenceChecks.responses.length>' + str(before)
                + ' && window.__oiEvidenceChecks.responses.slice(' + str(before)
                + ").some(r=>r.method==='POST'&&r.path.endsWith('/evidence')&&r.status===201)",
                'actual evidence import completed')
        imported = last('/evidence', 'POST', 201)
        eid = imported['evidence_id']
        cd.wait('Boolean(document.querySelector(' + json.dumps(
            f'[data-testid=evidence-version][data-evidence-id="{eid}"]') + '))',
            'imported version shown from fresh packet')
        packet = last('/evidence')
        evidence = next(e for e in packet['evidence'] if e['evidence_id'] == eid)
        assert evidence['sha256'] == hashlib.sha256(text.encode('utf-8')).hexdigest()
        assert evidence['content_item'] == item and evidence['state'] == 'current'
        statement_line, statement = next((i, s.removeprefix('Statement: '))
            for i, s in enumerate(text.splitlines(), 1) if s.startswith('Statement: '))
        assert evidence['statement_line'] == statement_line and evidence['statement'] == statement
        return evidence

    def assess(evidence, relation, quote, rationale, *, lose_response=False):
        click(f'[data-testid=evidence-version][data-evidence-id="{evidence["evidence_id"]}"] [data-testid=evidence-select]')
        value('[data-testid=evidence-quote]', quote)
        value('[data-testid=evidence-relation]', relation)
        value('[data-testid=evidence-applicability]', 'limited')
        value('[data-testid=evidence-rationale]', rationale)
        before = len(responses())
        if lose_response:
            cd.evaluate('window.__oiEvidenceChecks.loseAssessment=true')
        click('[data-testid=evidence-assess]')
        if lose_response:
            cd.wait("Boolean(document.querySelector('[data-testid=evidence-write-retry]'))",
                    'uncertain committed assessment exposes exact recovery')
            first = last('/evidence-assessments', 'POST', 201)
            click('[data-testid=evidence-write-retry]')
            cd.wait("window.__oiEvidenceChecks.responses.some(r=>r.path.endsWith('/evidence-assessments')&&r.status===200)",
                    'same intention recovered without another assessment')
            recovered = last('/evidence-assessments', 'POST', 200)
            assert recovered == {**first, 'duplicate': True}
            assessment_id = first['assessment_id']
        else:
            cd.wait('window.__oiEvidenceChecks.responses.slice(' + str(before)
                    + ").some(r=>r.path.endsWith('/evidence-assessments')&&r.status===201)",
                    'new authored assessment receipt')
            assessment_id = last('/evidence-assessments', 'POST', 201)['assessment_id']
        cd.wait('Boolean(document.querySelector(' + json.dumps(
            f'[data-testid=evidence-assessment][data-assessment-id="{assessment_id}"]') + '))',
            'persisted authored comparison in current packet')
        packet = last('/evidence')
        assessment = next(a for a in packet['assessments'] if a['assessment_id'] == assessment_id)
        assert assessment['quote'] == quote and assessment['relation'] == relation
        assert assessment['rationale'] == rationale and assessment['state'] == 'current_unreviewed'
        assert evidence['statement'][assessment['quote_start']:assessment['quote_start'] + len(quote)] == quote
        return assessment

    def report(assessment_ids):
        # Selection is explicit, never automatically selected by relation.
        for aid in assessment_ids:
            selector = f'[data-testid=evidence-assessment][data-assessment-id="{aid}"] [data-testid=evidence-report-select]'
            if not cd.evaluate('document.querySelector(' + json.dumps(selector) + ').checked'):
                click(selector)
        before = len(responses())
        click('[data-testid=evidence-report-prepare]')
        cd.wait('window.__oiEvidenceChecks.responses.length>' + str(before)
                + " && window.__oiEvidenceChecks.responses.slice(" + str(before)
                + ").some(r=>r.path.endsWith('/evidence-reports')&&r.status===201)", 'immutable report created')
        report_id = last('/evidence-reports', 'POST', 201)['report_id']
        open_report(report_id)
        prepared = last('/evidence-reports/' + report_id)
        assert prepared['state'] == 'current_unreviewed'
        assert prepared['snapshot']['question']['question_id'] == question_id
        assert prepared['snapshot']['selected_source']['source_id'] == source_id
        assert {c['assessment']['assessment_id'] for c in prepared['snapshot']['comparisons']} == set(assessment_ids)
        assert hashlib.sha256(prepared['body'].encode('utf-8')).hexdigest() == prepared['body_sha256']
        assert prepared['clinical_approval'] is prepared['model_executed'] is False
        return prepared

    def open_report(report_id):
        selector = f'[data-testid=evidence-report-row][data-report-id="{report_id}"] [data-testid=evidence-report-open]'
        cd.wait('Boolean(document.querySelector(' + json.dumps(selector) + '))', 'stored report history')
        before = len(responses())
        click(selector)
        cd.wait('window.__oiEvidenceChecks.responses.length>' + str(before)
                + " && Boolean(document.querySelector('[data-testid=evidence-report-preview]'))",
                'fresh authorized report inspection')

    def download(report_value):
        destination = artifacts / 'evidence-report-downloads' / report_value['report_id']
        destination.mkdir(parents=True, exist_ok=True)
        cd.command('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(destination.resolve())})
        before = len(responses())
        click('[data-testid=evidence-report-download]')
        cd.wait('window.__oiEvidenceChecks.responses.length>' + str(before), 'fresh report download authorization')
        wait_for(lambda: len([p for p in destination.iterdir() if p.is_file() and not p.name.endswith('.crdownload')]) == 1
                 and not list(destination.glob('*.crdownload')), 'actual evidence report download')
        path = next(destination.iterdir())
        actual = path.read_bytes()
        fresh = last('/evidence-reports/' + report_value['report_id'])
        assert actual == fresh['body'].encode('utf-8') == report_value['body'].encode('utf-8')
        assert fresh['access_receipt_id'] != report_value['access_receipt_id']
        return path, actual

    try:
        initial = inspect()
        assert not initial['evidence'] and not initial['assessments'] and not initial['reports']
        support = upload(SUPPORT, 'abstract', 'authored-violet-support.txt')
        originals = artifacts / 'evidence-original-downloads'
        originals.mkdir(parents=True, exist_ok=True)
        cd.command('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(originals.resolve())})
        click(f'[data-testid=evidence-version][data-evidence-id="{support["evidence_id"]}"] [data-testid=evidence-original-download]')
        wait_for(lambda: len(list(originals.iterdir())) == 1 and not list(originals.glob('*.crdownload')),
                 'actual original evidence file download')
        original_path = next(originals.iterdir())
        assert original_path.read_bytes() == SUPPORT.encode('utf-8')
        original_response = last('/evidence/' + support['evidence_id'] + '/original')
        assert original_response['sha256'] == support['sha256']
        support_assessment = assess(support, 'supports', 'café 🧪 labels matched the violet pattern',
            'This authored fictional phrase is proposed as support, with no clinical appraisal.', lose_response=True)
        counter = upload(COUNTER, 'api_output', 'authored-violet-counter.txt')
        counter_assessment = assess(counter, 'contradicts', 'the entry was absent in this authored example',
            'This independently invented counterexample is retained as a contradictory human proposal.')
        first_report = report([support_assessment['assessment_id'], counter_assessment['assessment_id']])
        downloaded_path, downloaded = download(first_report)
        assert support['evidence_id'] in first_report['body'] and counter['evidence_id'] in first_report['body']
        assert cd.evaluate("document.querySelectorAll('[data-testid=evidence-report-body] script').length===0")

        # A cached preview cannot authorize a fresh export after grant withdrawal.
        credentials[0]['actions'].remove('evidence_report_export'); write_grants()
        blobs = cd.evaluate('window.__oiEvidenceChecks.blobs')
        before = len(responses())
        click('[data-testid=evidence-report-download]')
        cd.wait('window.__oiEvidenceChecks.responses.length>' + str(before)
                + ' && window.__oiEvidenceChecks.responses.at(-1).status===404', 'report export grant withdrawn')
        cd.wait("!document.querySelector('[data-testid=evidence-report-body]')", 'denied fresh export clears old body')
        assert cd.evaluate('window.__oiEvidenceChecks.blobs') == blobs
        assert downloaded_path.read_bytes() == downloaded
        credentials[0]['actions'].append('evidence_report_export'); write_grants()
        inspect()
        open_report(first_report['report_id'])

        # Navigation must invalidate disclosed report content. It cannot reappear late.
        navigate('Overview')
        assert not cd.evaluate("Boolean(document.querySelector('[data-testid=evidence-report-body]'))")
        inspect()
        restart_api()
        inspect()
        open_report(first_report['report_id'])
        restarted = last('/evidence-reports/' + first_report['report_id'])
        for key in ('body', 'body_sha256', 'snapshot', 'snapshot_sha256', 'prepared_at'):
            assert restarted[key] == first_report[key]

        corrected = upload(AMENDED_SUPPORT, 'abstract', 'authored-violet-support-amendment.txt')
        assert corrected['version'] == 2
        packet = last('/evidence')
        old = next(a for a in packet['assessments'] if a['assessment_id'] == support_assessment['assessment_id'])
        assert old['state'] == 'reassessment_required'
        open_report(first_report['report_id'])
        historical = last('/evidence-reports/' + first_report['report_id'])
        assert historical['state'] == 'historical_reassessment_required'
        assert historical['body'] == first_report['body'] and downloaded_path.read_bytes() == downloaded
        corrected_assessment = assess(corrected, 'unknown', 'café 🧪 labels as uncertain',
            'The correction requires a new explicit human proposal; no conclusion is carried forward.')
        second_report = report([corrected_assessment['assessment_id'], counter_assessment['assessment_id']])
        second_path, second_bytes = download(second_report)

        cd.command('Emulation.setDeviceMetricsOverride', {'width': 390, 'height': 844,
                   'deviceScaleFactor': 1, 'mobile': False})
        cd.wait('window.innerWidth===390', 'evidence narrow viewport')
        assert cd.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1'), 'Evidence panel overflows 390px'
        cd.evaluate("document.querySelector('[data-testid=evidence-report-preview]').scrollIntoView()")
        shot = cd.command('Page.captureScreenshot', {'format': 'png'})
        (artifacts / 'h1-evidence-report-mobile.png').write_bytes(base64.b64decode(shot['data']))

        click(f'[data-testid=evidence-version][data-evidence-id="{corrected["evidence_id"]}"] [data-testid=evidence-select]')
        cd.evaluate("document.querySelector('[data-testid=evidence-withdraw-reason]').closest('details').open=true")
        value('[data-testid=evidence-withdraw-reason]', 'Withdraw this independently fictional evidence family for verification.')
        click('[data-testid=evidence-withdraw]')
        cd.wait("window.__oiEvidenceChecks.responses.some(r=>r.path.endsWith('/withdraw')&&r.status===201)",
                'withdrawal preserves history while removing content rights')
        inspect()
        for report_value in (first_report, second_report):
            inspect()
            open_report(report_value['report_id'])
            withheld = last('/evidence-reports/' + report_value['report_id'])
            assert withheld['state'] == 'content_withheld' and withheld['body'] is withheld['snapshot'] is None
            assert withheld['body_sha256'] == report_value['body_sha256']
            assert not cd.evaluate("Boolean(document.querySelector('[data-testid=evidence-report-body]'))")
        assert downloaded_path.read_bytes() == downloaded and second_path.read_bytes() == second_bytes
        assert cd.evaluate('localStorage.length===0 && sessionStorage.length===0')
        receipt = {
            'contract': 'oi.h1-question-evidence-browser-acceptance/1', 'patient_id': patient_id,
            'case_id': case_id, 'question_id': question_id, 'source_id': source_id,
            'original_download_relative_path': str(original_path.relative_to(artifacts)),
            'original_download_sha256': support['sha256'],
            'evidence': [support, counter, corrected],
            'assessments': [support_assessment, counter_assessment, corrected_assessment],
            'reports': [{**{k: v for k, v in r.items() if k not in {'body', 'snapshot'}},
                         'download_relative_path': str(p.relative_to(artifacts)), 'download_bytes': len(b)}
                        for r, p, b in ((first_report, downloaded_path, downloaded),
                                        (second_report, second_path, second_bytes))],
            'actual_api_restart_preserved_report': True,
            'lost_response_exact_retry_recovered_once': True,
            'fresh_export_revocation_no_blob': True,
            'evidence_amendment_requires_reassessment': True,
            'withdrawal_withholds_historical_reports': True,
            'original_downloads_unchanged': True, 'clinical_approval': False, 'model_executed': False,
        }
        (artifacts / 'question-evidence-workflow.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('PASS QUESTION EVIDENCE: actual authored abstract/API-output imports, supporting and contradictory '
              'human proposals, lost-response exact recovery, immutable report and fresh downloaded bytes, '
              'separate export revocation, API restart, amendment/reassessment, historical content withdrawal '
              'and 390px layout. Independently fictional only; no clinical approval or model execution.')
    finally:
        cd.evaluate('window.__oiEvidenceChecks.restore()')
        credentials[0]['actions'] = previous_actions
        write_grants()
        navigate('Journey')
        click('[data-testid=world-load]')
        cd.wait("Boolean(document.querySelector('[data-testid=world-projection]'))", 'return to current source workflow')
