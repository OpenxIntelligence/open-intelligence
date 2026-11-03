"""One real canonical question retains independent metadata and report operations.

Runs inside the two original browser observers. Every response comes from the
actual API; fictional metadata remains metadata, never an appraised quotation.
"""
import hashlib
import json
from pathlib import Path

from followthrough_journey import click, fill


def exercise(cd, patient_id, case_id, question_id, source_id, credentials,
             write_grants, artifacts, report, downloaded_path, downloaded):
    row = f'.question-items li[data-question-id="{question_id}"]'
    scope = f'/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}'
    citation = 'FICT-TRIAL-PREPARATION@1'
    previous_actions = list(credentials[0]['actions'])
    assert {'evidence_read', 'evidence_link', 'authored_evidence_read', 'evidence_report_export'} <= set(previous_actions)
    assert report['question_id'] == question_id
    assert report['snapshot']['selected_source']['source_id'] == source_id
    assert downloaded_path.read_bytes() == downloaded == report['body'].encode('utf-8')

    def metadata(kind):
        return cd.evaluate('window.__oiMetadataEvidenceChecks.' + kind)

    def authored():
        return cd.evaluate('window.__oiAuthoredEvidenceChecks.responses')

    def control(name):
        return row + ' [data-testid=' + name + ']'

    def history(*, allowed=True):
        count = len(metadata('reads'))
        click(cd, control('metadata-evidence-open'))
        cd.wait('window.__oiMetadataEvidenceChecks.reads.length>' + str(count),
                'real same-question metadata history response')
        observed = metadata('reads')[-1]
        assert observed['path'] == scope + '/evidence-links'
        if allowed:
            assert observed['status'] == 200
            cd.wait('Boolean(document.querySelector(' + json.dumps(control('evidence-saved-links')) + '))',
                    'authorized citation history displayed beside the same question')
            payload = observed['payload']
            assert (payload['patient_id'], payload['case_id'], payload['question_id']) == (patient_id, case_id, question_id)
            assert payload['model_executed'] is payload['clinical_approval'] is payload['content_appraised'] is False
            return payload
        assert observed['status'] in (403, 404)
        cd.wait('!document.querySelector(' + json.dumps(control('evidence-saved-links')) + ')',
                'independent metadata denial clears its history')
        return observed

    def reopen_report():
        selector = f'[data-testid=evidence-report-row][data-report-id="{report["report_id"]}"] [data-testid=evidence-report-open]'
        count = len(authored())
        click(cd, selector)
        cd.wait('window.__oiAuthoredEvidenceChecks.responses.length>' + str(count)
                + " && Boolean(document.querySelector('[data-testid=evidence-report-body]'))",
                'fresh independently authorized authored report')
        response = [r for r in authored() if r['path'] == scope + '/evidence-reports/' + report['report_id']][-1]
        assert response['status'] == 200
        current = response['payload']
        assert current['body'] == report['body']
        assert current['snapshot_sha256'] == report['snapshot_sha256']
        assert current['question_id'] == question_id
        assert current['clinical_approval'] is current['model_executed'] is False
        return current

    try:
        initial = history()
        assert initial['links'] == []
        fill(cd, control('evidence-query'), 'preparation')
        count = len(metadata('searches'))
        click(cd, control('evidence-search'))
        cd.wait('window.__oiMetadataEvidenceChecks.searches.length>' + str(count)
                + ' && Boolean(document.querySelector(' + json.dumps(control('evidence-result')) + '))',
                'actual second fictional catalog item found for the report question')
        search = metadata('searches')[-1]
        assert search['path'] == scope + '/evidence-search'
        assert search['status'] == 200 and search['body'] == {'synthetic': True, 'query': 'preparation'}
        found, = search['payload']['records']
        assert found['citation'] == citation and found['availability'] == 'metadata_only'
        assert search['payload']['question_id'] == question_id
        cd.evaluate('document.querySelector(' + json.dumps(control('evidence-result')) + ').open=true')
        count = len(metadata('writes'))
        click(cd, control('evidence-save'))
        cd.wait('window.__oiMetadataEvidenceChecks.writes.length>' + str(count)
                + ' && Boolean(document.querySelector(' + json.dumps(control('evidence-saved-link')) + '))',
                'same-question canonical citation persisted without changing the authored report')
        saved = metadata('writes')[-1]
        assert saved['status'] == 201 and saved['path'] == scope + '/evidence-links'
        assert saved['payload']['citation'] == citation
        assert saved['body']['expected_source_snapshot_sha256'] == report['snapshot']['question']['source_snapshot_sha256']
        assert saved['body']['expected_preflight_sha256'] == report['snapshot']['question']['preflight_sha256']
        linked = history()
        link, = linked['links']
        assert link['link_id'] == saved['payload']['link_id']
        assert link['record']['metadata_sha256'] == found['metadata_sha256']
        assert cd.evaluate("document.querySelector('[data-testid=evidence-report-body]')?.textContent") == report['body']

        # Metadata and quoted content have independent grants. A metadata-only
        # denial cannot grant or suppress the separately authorized export.
        credentials[0]['actions'].remove('evidence_read')
        write_grants()
        denied_metadata = history(allowed=False)
        fresh_report = reopen_report()
        assert fresh_report['access_receipt_id'] != report['access_receipt_id']
        credentials[0]['actions'].append('evidence_read')
        credentials[0]['actions'].remove('evidence_report_export')
        write_grants()
        count = len(authored())
        blobs = cd.evaluate('window.__oiAuthoredEvidenceChecks.blobs')
        click(cd, '[data-testid=evidence-report-download]')
        cd.wait('window.__oiAuthoredEvidenceChecks.responses.length>' + str(count)
                + " && !document.querySelector('[data-testid=evidence-report-body]')",
                'denied authored export clears its cached body')
        denied_report = [r for r in authored() if r['path'] == scope + '/evidence-reports/' + report['report_id']][-1]
        assert denied_report['status'] in (403, 404)
        assert cd.evaluate('window.__oiAuthoredEvidenceChecks.blobs') == blobs
        assert history()['links'][0]['link_id'] == link['link_id']
        assert not cd.evaluate("Boolean(document.querySelector('[data-testid=evidence-report-body]'))")

        # Re-establish only the original fixture grants and inspect real fresh
        # bytes; no cached preview is used to bypass either denied operation.
        credentials[0]['actions'] = previous_actions
        write_grants()
        count = len(authored())
        click(cd, control('authored-evidence-open'))
        cd.wait('window.__oiAuthoredEvidenceChecks.responses.length>' + str(count)
                + " && Boolean(document.querySelector('[data-testid=evidence-panel]'))",
                'authored inspection restored under its original independent fixture grants')
        reopened = reopen_report()
        assert history()['links'][0]['link_id'] == link['link_id']
        assert downloaded_path.read_bytes() == downloaded
        receipt = {
            'contract': 'oi.h1-evidence-continuity-browser/2',
            'patient_id': patient_id, 'case_id': case_id, 'question_id': question_id,
            'source_id': source_id, 'source_snapshot_sha256': saved['body']['expected_source_snapshot_sha256'],
            'preflight_sha256': saved['body']['expected_preflight_sha256'],
            'metadata_link': saved['payload'], 'metadata_sha256': found['metadata_sha256'],
            'metadata_access_receipt_id': linked['source_access_receipt_id'],
            'report_id': report['report_id'], 'report_body_sha256': report['body_sha256'],
            'download_sha256': hashlib.sha256(downloaded).hexdigest(),
            'report_snapshot_sha256': report['snapshot_sha256'],
            'fresh_report_access_receipt_id': reopened['access_receipt_id'],
            'metadata_denial_status': denied_metadata['status'], 'report_denial_status': denied_report['status'],
            'metadata_does_not_authorize_content': True, 'report_does_not_appraise_metadata': True,
            'denied_export_created_no_blob': True, 'existing_download_unchanged': True,
            'synthetic': True, 'clinical_approval': False, 'model_executed': False,
        }
        (Path(artifacts) / 'h1-evidence-continuity-receipt.json').write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('PASS EVIDENCE CONTINUITY: one actual canonical question retains its source, fictional metadata '
              'citation and authored immutable report; independent metadata-read and report-export denial '
              'leave no cross-grant substitute or cached download. No model or clinical approval.')
    finally:
        credentials[0]['actions'] = previous_actions
        write_grants()
