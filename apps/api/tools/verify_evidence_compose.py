"""Actual disposable HTTP, restart and dump/restore proof for H1 case evidence.

Uses independently authored fictional originals only. Rights declarations are
fixture facts, not publisher clearance or clinical evidence. No model is called.
"""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import uuid

from oi_api.contracts import SCHEMA_REVISION

ROOT = Path(__file__).resolve().parents[3]
CASE = 'CASE-EVIDENCE-RECOVERY'
SOURCE = (
    'OI-SYNTHETIC-REPORT/1\nPatient: CASE-EVIDENCE-RECOVERY\nDocument: DOC-INK\n'
    'Type: pathology\nEvent-Date: 2026-02-02\nIssued-At: 2026-02-03\n'
    'Specimen: SPECIMEN-INK\nFinding: ink|pending|The independently invented ink label is pending.\n'
)
SOURCE_AMENDMENT = SOURCE.replace('Issued-At: 2026-02-03', 'Issued-At: 2026-02-04') \
    .replace('Finding: ink|pending|The independently invented ink label is pending.',
             'Amends: DOC-INK@1\nFinding: ink|indeterminate|The invented ink label remains indeterminate.')
MANUAL_RECORD = b'\xef\xbb\xbfIndependently fictional record\r\nMarker pending.\r\nSecond passage.\r\n'


def evidence(key, statement, *, amends=None):
    return (f'OI-SYNTHETIC-EVIDENCE/1\nEvidence: {key}\n'
            f'Title: Independently authored worksheet {key}\nIssued-At: 2026-02-05\n'
            'Rights: original-synthetic\n' + (f'Amends: {key}@{amends}\n' if amends else '')
            + f'Statement: {statement}\n')


def permissions(item, *, redistribute='allowed'):
    return {'metadata': {'store': 'allowed', 'display': 'allowed', 'redistribute': redistribute},
            item: {'store': 'allowed', 'display': 'allowed', 'redistribute': redistribute}}


def main():
    project = 'oi-h1-evidence-proof-' + uuid.uuid4().hex[:12]
    compose = ['docker', 'compose', '--project-name', project,
               '--file', str(ROOT / 'apps/api/compose.yaml'),
               '--file', str(ROOT / 'apps/api/compose.synthetic-access.yaml')]
    with tempfile.TemporaryDirectory(prefix='oi-evidence-access-') as directory:
        access = Path(directory)
        access.chmod(0o755)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=directory)
        token = secrets.token_urlsafe(32)
        actions = ['patient_create', 'patient_read', 'case_binding_create', 'case_binding_read',
                   'case_binding_revoke', 'source_import', 'source_read', 'source_original_read', 'composer_context_read',
                   'question_create', 'question_read', 'authored_evidence_read', 'authored_evidence_import',
                   'authored_evidence_assess', 'authored_evidence_withdraw', 'authored_evidence_original_read', 'evidence_report_export',
                   'evidence_read', 'evidence_link', 'followthrough_read', 'followthrough_create']
        credential = {'token_sha256': hashlib.sha256(token.encode()).hexdigest(),
                      'actor': 'ACTOR-EVIDENCE-RECOVERY', 'organization': 'ORG-EVIDENCE-RECOVERY',
                      'purpose': 'operations', 'actions': list(actions), 'patient_ids': [],
                      'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}

        def save_access():
            pending = access / 'next.json'
            pending.write_text(json.dumps({'version': 'oi.synthetic-access/1', 'credentials': [credential]}))
            pending.chmod(0o644)
            pending.replace(access / 'access.json')

        def command(args, *, check=True, **kwargs):
            return subprocess.run(compose + args, cwd=ROOT, env=env, check=check, timeout=180, **kwargs)

        def query(sql, database='oi_api_synthetic'):
            result = command(['exec', '-T', 'db', 'psql', '-X', '-U', 'oi_api', '-d', database,
                              '-v', 'ON_ERROR_STOP=1', '-At', '-c', sql], capture_output=True, text=True)
            return json.loads(result.stdout)

        def snapshot(database='oi_api_synthetic'):
            # Complete logical records, not a count-only restore assertion.
            tables = ['identity.identity_patients', 'coordination.patient_case_bindings',
                      'clinical_source.source_versions', 'clinical_source.assertions',
                      'clinical_source.document_intakes', 'clinical_source.annotation_revisions',
                      'investigation.source_questions', 'investigation.question_passage_revisions',
                      'investigation.case_evidence_versions',
                      'investigation.case_evidence_withdrawals', 'investigation.question_evidence_assessments',
                      'investigation.question_evidence_reports', 'investigation.evidence_commands',
                      'investigation.evidence_command_origins',
                      'investigation.evidence_catalog_records', 'investigation.evidence_rights_decisions',
                      'investigation.question_evidence_links', 'coordination.question_followthrough_tasks',
                      'coordination.question_followthrough_events',
                      'coordination.source_event_outbox', 'coordination.source_event_deliveries',
                      'coordination.source_event_delivery_events',
                      'investigation.composer_source_event_receipts',
                      'identity.identity_domain_events', 'public.alembic_version']
            result = {table: query('SELECT COALESCE(json_agg(row ORDER BY row::text),\'[]\'::json) '
                                  'FROM (SELECT to_jsonb(t) AS row FROM ' + table + ' t) v', database)
                      for table in tables}
            result['sequence_state'] = query("""
                SELECT COALESCE(json_agg(row ORDER BY row::text),'[]'::json)
                FROM (SELECT to_jsonb(s) AS row FROM (
                    SELECT schemaname,sequencename,start_value,min_value,max_value,
                           increment_by,cycle,cache_size,last_value
                    FROM pg_sequences WHERE schemaname IN ('identity','clinical_source','investigation','coordination')
                ) s) v
            """, database)
            return result

        def request(path, body=None, *, authenticated=True):
            headers = {'Authorization': 'Bearer ' + token} if authenticated else {}
            if body is not None:
                headers['Content-Type'] = 'application/json'
            req = Request('http://127.0.0.1:8000' + path, headers=headers,
                          data=None if body is None else json.dumps(body).encode('utf-8'))
            try:
                response = build_opener(ProxyHandler({})).open(req, timeout=5)
            except HTTPError as exc:
                response = exc
            with response:
                assert response.headers.get('Cache-Control') == 'no-store'
                return response.status, json.load(response)

        def ready():
            deadline = time.monotonic() + 45
            while True:
                try:
                    status, value = request('/health/ready', authenticated=False)
                    if status == 200 and value['status'] == 'ready':
                        return
                except (OSError, URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Synthetic evidence API did not become ready')
                time.sleep(0.25)

        def serve_database(database):
            # Recreate the actual API, retaining its image, credentials mount,
            # security options and network. Do not run a new migration/seed.
            override = access / 'restore.compose.json'
            override.write_text(json.dumps({'services': {'api': {'environment': {
                'OI_API_DATABASE_URL': 'postgresql+pg8000://oi_api:oi_h1_synthetic_only@db:5432/' + database,
            }}}}))
            if str(override) not in compose:
                compose.extend(['--file', str(override)])
            command(['up', '--no-deps', '--force-recreate', '--detach', 'api'])
            ready()
            # A denial-only checkpoint cannot prove target identity by emitting
            # an access event. Query through this API container's normal engine.
            result = command(['exec', '-T', 'api', 'python', '-c',
                'from oi_api.config import Settings\n'
                'from oi_api.database import make_engine\n'
                'from sqlalchemy import text\n'
                'engine = make_engine(Settings.from_env())\n'
                'try:\n'
                '    with engine.connect() as connection:\n'
                '        print(connection.execute(text("SELECT current_database()")).scalar_one())\n'
                'finally:\n'
                '    engine.dispose()\n'], capture_output=True, text=True)
            assert result.stdout.strip() == database, 'Recreated API connected to the wrong database'

        def restore(source_database, restored_database):
            before = snapshot(source_database)
            dump = command(['exec', '-T', 'db', 'pg_dump', '-U', 'oi_api', '-d',
                            source_database, '--format=custom'], capture_output=True).stdout
            command(['exec', '-T', 'db', 'createdb', '-U', 'oi_api', restored_database])
            command(['exec', '-T', 'db', 'pg_restore', '-U', 'oi_api', '-d', restored_database,
                     '--exit-on-error', '--no-owner'], input=dump)
            assert snapshot(restored_database) == before, 'Restore changed complete history or sequences'
            serve_database(restored_database)
            assert snapshot(restored_database) == before, 'API startup changed restored history'
            return before

        def assert_restored_reads(before, database, receipt_ids, *, expect_metadata=True, expect_manual=False):
            after = snapshot(database)
            # Reads and exact retries may append access events only. The source
            # copy must stay completely unchanged, including sequence state.
            assert snapshot() == before, 'Restored HTTP unexpectedly touched the original database'
            for table in before.keys() - {'identity.identity_domain_events', 'sequence_state'}:
                assert after[table] == before[table], 'Restored read/retry changed ' + table
            event_sequence = ('identity', 'identity_domain_events_id_seq')
            for state in (before, after):
                assert sum((s['schemaname'], s['sequencename']) == event_sequence
                           for s in state['sequence_state']) == 1
            def non_access_sequences(state):
                return [s for s in state['sequence_state']
                        if (s['schemaname'], s['sequencename']) != event_sequence]
            assert non_access_sequences(after) == non_access_sequences(before), \
                'Restored read/retry consumed a business-object sequence'
            old = {row['id']: row for row in before['identity.identity_domain_events']}
            current = {row['id']: row for row in after['identity.identity_domain_events']}
            assert all(current.get(key) == row for key, row in old.items()), 'Historical event changed'
            fresh = [row for key, row in current.items() if key not in old]
            assert fresh, 'No restored access event: API may still target the original database'
            assert len(receipt_ids) == len(set(receipt_ids)), 'Reused an access receipt'
            # Each actual read response must be attested in the restored copy.
            for receipt_id in receipt_ids:
                assert receipt_id in json.dumps(fresh), 'Returned receipt missing from restored database'
                assert receipt_id not in json.dumps(list(old.values())), 'Returned an old access receipt'
            metadata_reads = [row for row in fresh if row['event_type'] == 'evidence.links.read_authorized']
            assert len(metadata_reads) == (1 if expect_metadata else 0), 'Unexpected restored metadata-link audit count'
            if expect_metadata:
                assert metadata_reads[0]['patient_id'] == patient
                assert metadata_reads[0]['metadata_json'] == {
                    'question_id': question_id, 'case_id': CASE,
                    'actor': credential['actor'], 'link_count': 1,
                }, 'Metadata read audit changed its canonical scope'
            manual_reads = [row for row in fresh if row['event_type'] in (
                'investigation.report_manual_context_access_prepared', 'investigation.question_passages_access_prepared')]
            assert bool(manual_reads) is expect_manual, 'Unexpected restored manual-context audit state'
            for event in manual_reads:
                assert event['patient_id'] == patient
                assert event['metadata_json']['question_id'] == question_id
                assert event['metadata_json']['case_id'] == CASE
                assert event['metadata_json']['reference_count'] == len(passage_command['references'])
                expected_refs = json.dumps(passage_command['references'], sort_keys=True, ensure_ascii=False, separators=(',', ':'))
                assert event['metadata_json']['references_sha256'] == hashlib.sha256(expected_refs.encode()).hexdigest()
            assert all(row['event_type'] in ('source.read_authorized', 'evidence.links.read_authorized',
                                             'investigation.report_manual_context_access_prepared',
                                             'investigation.question_passages_access_prepared')
                       for row in fresh), 'Exact retry unexpectedly emitted a new business event'
            return len(fresh)

        save_access()
        try:
            command(['config', '--quiet'])
            command(['up', '--build', '--detach', 'api'])
            ready()
            command(['exec', '-T', 'api', 'python', '-m', 'oi_api.evidence_catalog'])
            status, created = request('/v1/patients', {'synthetic': True, 'request_key': 'EVIDENCE-PATIENT'})
            assert status == 201
            patient = created['patient_id']
            credential['patient_ids'] = [patient]
            save_access()
            patient_path = '/v1/patients/' + patient
            status, _ = request(patient_path + '/case-bindings', {
                'synthetic': True, 'case_id': CASE, 'source_organization': 'ORG-FICTIONAL-EVIDENCE',
                'source_system': 'SYS-FICTIONAL-EVIDENCE', 'source_subject_ref': 'SUBJECT-INK',
                'review_ref': 'REVIEW-INK'})
            assert status == 201
            prefix = patient_path + '/cases/' + CASE
            status, source = request(prefix + '/sources', {'synthetic': True, 'original_text': SOURCE})
            assert status == 201
            manual_upload = {'synthetic': True, 'filename': 'fictional-manual.txt',
                             'original_base64': base64.b64encode(MANUAL_RECORD).decode()}
            status, manual_preview = request(prefix + '/documents/preview', manual_upload)
            assert status == 200
            manual_payload = manual_upload | {
                'confirmed_case_id': CASE, 'expected_sha256': manual_preview['sha256'],
                'metadata': {'document_id': 'DOC-MANUAL-CONTEXT', 'kind': 'pathology',
                             'event_date': '2026-02-01', 'issued_at': '2026-02-01',
                             'manual_transcription_confirmed': True},
                'findings': [{'key': 'marker', 'state': 'pending',
                              'quote': 'Marker pending.', 'line': 2}]}
            status, manual_document = request(prefix + '/documents', manual_payload)
            assert status == 201
            status, world = request(prefix + '/world-model')
            assert status == 200
            proposal = {'synthetic': True, 'source_id': source['source_id'], 'source_line': 8,
                        'question': 'Which invented ink statement and authored counterexample require verification?',
                        'expected_source_snapshot_sha256': world['snapshot_fingerprint']}
            status, preflight = request(prefix + '/composer/source-preflight', proposal)
            assert status == 200
            status, saved = request(prefix + '/questions', {**proposal, 'request_key': 'EVIDENCE-QUESTION',
                'expected_preflight_sha256': preflight['preflight_sha256']})
            assert status == 201
            question_id = saved['question_id']
            url = prefix + '/questions/' + question_id

            # Reuse the existing fictional catalog and task owners on this very
            # question. A saved metadata identity never imports a quotation or
            # grants the independently authored content/report permissions.
            status, search = request(url + '/evidence-search', {'synthetic': True, 'query': 'continuity'})
            assert status == 200 and len(search['records']) == 1
            metadata = search['records'][0]
            assert metadata['citation'] == 'FICT-RECORD-CONTINUITY@1'
            assert metadata['availability'] == 'metadata_only' and search['content_appraised'] is False
            context = {'source_snapshot_contract': 'oi.pg-source-world-model/1',
                       'expected_source_snapshot_sha256': world['snapshot_fingerprint'],
                       'expected_preflight_sha256': preflight['preflight_sha256']}
            citation_intent = {'synthetic': True, 'request_key': 'EVIDENCE-CONTINUITY-CITATION',
                               'citation': metadata['citation'],
                               'expected_metadata_sha256': metadata['metadata_sha256'], **context}
            status, citation_receipt = request(url + '/evidence-links', citation_intent)
            assert status == 201 and citation_receipt['duplicate'] is False
            task_intent = {'synthetic': True, 'request_key': 'EVIDENCE-CONTINUITY-TASK', **context,
                           'title': 'Revisit the independently authored comparison', 'detail': '',
                           'owner_label': '', 'due_date': None,
                           'review_trigger': 'When the fictional source changes',
                           'reason': 'Retain the preparation task alongside the report.'}
            status, task_receipt = request(url + '/followthrough', task_intent)
            assert status == 201 and task_receipt['duplicate'] is False

            def assert_continuity(receipt_ids, *, stale=False):
                status, linked = request(url + '/evidence-links')
                assert status == 200 and linked['question_id'] == question_id
                assert len(linked['links']) == 1
                assert linked['links'][0]['link_id'] == citation_receipt['link_id']
                assert linked['links'][0]['record'] == metadata
                expected = 'source_reassessment_required' if stale else 'current_unreviewed_question'
                assert linked['source_context_state'] == expected
                receipt_ids.append(linked['source_access_receipt_id'])
                status, tasks = request(prefix + '/followthrough')
                assert status == 200 and len(tasks['tasks']) == 1
                task = tasks['tasks'][0]
                assert task['task_id'] == task_receipt['task_id'] and task['question_id'] == question_id
                assert task['source_id'] == source['source_id']
                assert task['revision'] == 1 and task['status'] == 'created'
                assert task['source_context_state'] == expected and task['needs_recheck'] is stale
                assert task['clinical_approval'] is False
                receipt_ids.append(tasks['access_receipt_id'])
                assert request(url + '/evidence-links', citation_intent) == (200, {**citation_receipt, 'duplicate': True})
                assert request(url + '/followthrough', task_intent) == (200, {**task_receipt, 'duplicate': True})

            def packet():
                status, result = request(url + '/evidence')
                assert status == 200, result
                assert result['question']['question_id'] == question_id
                assert result['clinical_approval'] is result['model_executed'] is False
                return result

            def import_evidence(text, item, key, rights=None):
                intent = {'synthetic': True, 'request_key': key, 'original_text': text,
                          'content_item': item, 'permissions': rights or permissions(item)}
                status, result = request(url + '/evidence', intent)
                assert status == 201, result
                assert request(url + '/evidence', intent) == (200, {**result, 'duplicate': True})
                current = next(e for e in packet()['evidence'] if e['evidence_id'] == result['evidence_id'])
                assert current['sha256'] == hashlib.sha256(text.encode()).hexdigest()
                status, original = request(url + '/evidence/' + result['evidence_id'] + '/original')
                assert status == 200 and original['original_text'].encode() == text.encode()
                return current

            def assess(row, relation, key):
                intent = {'synthetic': True, 'request_key': key, 'evidence_id': row['evidence_id'],
                          'evidence_sha256': row['sha256'], 'rights_sha256': row['rights_sha256'],
                          'expected_source_snapshot_sha256': world['snapshot_fingerprint'],
                          'expected_preflight_sha256': preflight['preflight_sha256'],
                          'quote': row['statement'], 'relation': relation, 'applicability': 'limited',
                          'rationale': 'This is a human-authored fictional comparison, with no clinical appraisal.'}
                status, result = request(url + '/evidence-assessments', intent)
                assert status == 201, result
                duplicate = {**result, 'duplicate': True}
                assert request(url + '/evidence-assessments', intent) == (200, duplicate)
                return result['assessment_id'], intent, duplicate

            report_commands = []
            manual_context = None

            def make_report(ids, key):
                intent = {'synthetic': True, 'request_key': key, 'assessment_ids': ids,
                          'expected_packet_sha256': packet()['packet_sha256']}
                if manual_context is not None:
                    intent['expected_manual_context_sha256'] = manual_context['context_sha256']
                status, result = request(url + '/evidence-reports', intent)
                assert status == 201, result
                assert request(url + '/evidence-reports', intent) == (200, {**result, 'duplicate': True})
                report_commands.append((intent, {**result, 'duplicate': True}))
                status, report = request(url + '/evidence-reports/' + result['report_id'])
                assert status == 200 and report['state'] == 'current_unreviewed'
                assert report['body_sha256'] == hashlib.sha256(report['body'].encode()).hexdigest()
                assert report['snapshot']['selected_source']['source_id'] == source['source_id']
                assert {c['assessment']['assessment_id'] for c in report['snapshot']['comparisons']} == set(ids)
                return report

            support_text = evidence('INK-SUPPORT', 'This invented café 🧪 worksheet proposes support for the pending ink example.')
            counter_text = evidence('INK-COUNTER', 'An independently invented worksheet contradicts the pending ink example.')
            support = import_evidence(support_text, 'abstract', 'IMPORT-SUPPORT')
            counter = import_evidence(counter_text, 'api_output', 'IMPORT-COUNTER')
            a1 = assess(support, 'supports', 'ASSESS-SUPPORT')
            a2 = assess(counter, 'contradicts', 'ASSESS-COUNTER')
            first = make_report([a1[0], a2[0]], 'REPORT-ORIGINAL')

            # Missing export authority neither returns old content nor writes an event.
            credential['actions'].remove('evidence_report_export'); save_access()
            before = snapshot()
            status, denied = request(url + '/evidence-reports/' + first['report_id'])
            assert status == 404 and 'body' not in denied and snapshot() == before
            credential['actions'] = list(actions); save_access()

            # Every original and report survives both actual process and DB restart.
            for service in ('api', 'db'):
                before = snapshot()
                command(['restart', service]); ready()
                assert snapshot() == before, 'Restart changed complete evidence/source/report history'
                status, reread = request(url + '/evidence-reports/' + first['report_id'])
                assert status == 200
                for field in ('report_id', 'body', 'body_sha256', 'snapshot', 'snapshot_sha256', 'prepared_at'):
                    assert reread[field] == first[field]
                assert_continuity([])
                print('Canonical evidence, authored comparisons and report survived ' + service + ' restart')

            # Row equality is insufficient: serve a readable backup through the
            # real HTTP API and prove its access receipts exist only in the copy.
            readable_database = 'oi_api_test_evidence_readable_restore'
            readable_before = restore('oi_api_synthetic', readable_database)
            readable_receipts = []
            for row, text in ((support, support_text), (counter, counter_text)):
                status, original = request(url + '/evidence/' + row['evidence_id'] + '/original')
                assert status == 200 and original['original_text'].encode() == text.encode()
                assert (original['patient_id'], original['case_id'], original['evidence_id'], original['sha256']) == \
                    (patient, CASE, row['evidence_id'], row['sha256'])
                readable_receipts.append(original['access_receipt_id'])
            status, recovered = request(url + '/evidence-reports/' + first['report_id'])
            assert status == 200 and recovered['state'] == 'current_unreviewed'
            for field in ('report_id', 'body', 'body_sha256', 'snapshot', 'snapshot_sha256', 'prepared_at'):
                assert recovered[field] == first[field], 'Restored report changed ' + field
            readable_receipts.append(recovered['access_receipt_id'])
            for _, intent, duplicate in (a1, a2):
                assert request(url + '/evidence-assessments', intent) == (200, duplicate)
            assert request(url + '/evidence-reports', report_commands[0][0]) == (200, report_commands[0][1])
            assert_continuity(readable_receipts)
            readable_access_count = assert_restored_reads(readable_before, readable_database, readable_receipts)
            serve_database('oi_api_synthetic')
            assert snapshot() == readable_before
            print('PASS RESTORED READABLE HTTP: exact originals/report/retries; restored-only access receipts')

            # Attach a source-owned manual record passage only after the legacy report
            # has proven its own restore contract. New reports now freeze renderer-v3
            # context while the older report remains byte-identical history.
            selection_path = (prefix + '/documents/' + manual_document['source_id'] + '/selections/' +
                              manual_document['annotation_revision_id'] + '/marker')
            status, manual_selection = request(selection_path)
            assert status == 200 and manual_selection['anchor']['quote'] == 'Marker pending.'
            passage_path = url + '/manual-passages'
            status, empty_manual = request(passage_path)
            assert status == 200 and empty_manual['revision_id'] is None
            passage_command = {
                'synthetic': True, 'request_key': 'RECOVERY-MANUAL-PASSAGE',
                'expected_context_sha256': empty_manual['context_sha256'],
                'references': [{
                    'source_id': manual_document['source_id'],
                    'annotation_revision_id': manual_document['annotation_revision_id'],
                    'selection_key': 'marker',
                    'anchor_sha256': manual_selection['anchor_sha256']}],
            }
            status, passage_receipt = request(passage_path, passage_command)
            assert status == 201 and passage_receipt['duplicate'] is False
            status, manual_context = request(passage_path)
            assert status == 200 and manual_context['state'] == 'current_unreviewed'
            assert manual_context['passages'][0]['anchor'] == manual_selection['anchor']
            manual_report = make_report([a1[0], a2[0]], 'REPORT-MANUAL-CONTEXT')
            assert manual_report['snapshot']['manual_passages']['context_sha256'] == manual_context['context_sha256']
            assert 'ADDITIONAL MANUAL RECORD CONTEXT' in manual_report['body']
            assert 'Marker pending.' in manual_report['body']

            manual_database = 'oi_api_test_manual_context_restore'
            manual_before = restore('oi_api_synthetic', manual_database)
            status, restored_manual_report = request(url + '/evidence-reports/' + manual_report['report_id'])
            assert status == 200 and restored_manual_report['state'] == 'current_unreviewed'
            for field in ('report_id', 'body', 'body_sha256', 'snapshot', 'snapshot_sha256', 'prepared_at'):
                assert restored_manual_report[field] == manual_report[field], 'Restored manual report changed ' + field
            manual_receipts = [restored_manual_report['access_receipt_id']]
            status, restored_manual = request(passage_path)
            assert status == 200 and {k:v for k,v in restored_manual.items() if k != 'access_receipt_id'} == {
                k:v for k,v in manual_context.items() if k != 'access_receipt_id'}
            manual_receipts.append(restored_manual['access_receipt_id'])
            assert request(passage_path, passage_command) == (200, passage_receipt | {'duplicate': True})
            assert request(url + '/evidence-reports', report_commands[-1][0]) == (200, report_commands[-1][1])
            credential['actions'].remove('source_original_read'); save_access()
            denied_before = snapshot(manual_database)
            assert request(passage_path)[0] == 404
            assert request(url + '/evidence-reports/' + manual_report['report_id'])[0] == 404
            assert snapshot(manual_database) == denied_before
            credential['actions'] = list(actions); save_access()
            manual_access_count = assert_restored_reads(manual_before, manual_database, manual_receipts,
                                                       expect_metadata=False, expect_manual=True)
            serve_database('oi_api_synthetic')
            assert snapshot() == manual_before
            print('PASS RESTORED MANUAL CONTEXT: exact passage revision/report bytes/retry and restored-only authority')

            amended = import_evidence(evidence('INK-SUPPORT',
                'The corrected invented café 🧪 worksheet leaves the ink example uncertain.', amends=1),
                'abstract', 'IMPORT-SUPPORT-V2')
            assert amended['version'] == 2
            current = packet()
            assert next(a for a in current['assessments'] if a['assessment_id'] == a1[0])['state'] == 'reassessment_required'
            status, historical = request(url + '/evidence-reports/' + first['report_id'])
            assert status == 200 and historical['state'] == 'historical_reassessment_required'
            assert historical['body'] == first['body'] and historical['snapshot'] == first['snapshot']
            assert request(url + '/evidence-assessments', a1[1]) == (200, a1[2])
            before = snapshot()
            status, _ = request(url + '/evidence-reports', {'synthetic': True, 'request_key': 'REPORT-STALE',
                'assessment_ids': [a1[0], a2[0]], 'expected_packet_sha256': current['packet_sha256']})
            assert status == 409 and snapshot() == before
            a3 = assess(amended, 'unknown', 'ASSESS-SUPPORT-V2')
            second = make_report([a3[0], a2[0]], 'REPORT-REASSESSED')

            status, corrected_manual = request(prefix + '/documents/' + manual_document['source_id'] + '/annotations', {
                'synthetic': True, 'request_key': 'RECOVERY-MANUAL-CORRECTION',
                'expected_revision_id': manual_document['annotation_revision_id'],
                'confirmed_case_id': CASE, 'expected_sha256': manual_preview['sha256'],
                'reason': 'Preserve a narrower exact passage',
                'findings': [{'key': 'marker', 'state': 'pending', 'quote': 'pending.', 'line': 2}]})
            assert status == 201, corrected_manual
            status, historical_manual = request(passage_path)
            assert status == 200 and historical_manual['state'] == 'reassessment_required'
            assert historical_manual['passages'][0]['anchor'] == manual_selection['anchor']
            status, manual_history = request(url + '/evidence-reports/' + second['report_id'])
            assert status == 200 and manual_history['state'] == 'historical_reassessment_required'
            assert manual_history['body'] == second['body'] and manual_history['snapshot'] == second['snapshot']
            current_manual_packet = packet()
            denied_before = snapshot()
            assert request(url + '/evidence-reports', {
                'synthetic': True, 'request_key': 'STALE-MANUAL-REPORT',
                'expected_packet_sha256': current_manual_packet['packet_sha256'],
                'expected_manual_context_sha256': historical_manual['context_sha256'],
                'assessment_ids': [a3[0], a2[0]]})[0] == 409
            assert snapshot() == denied_before, 'Stale manual report attempt changed persisted state'

            # A changed text class never donates permission to old abstract quotations.
            changed = import_evidence(evidence('INK-SUPPORT',
                'A new authored API-shaped fixture records uncertainty for the invented ink example.', amends=2),
                'api_output', 'IMPORT-SUPPORT-V3')
            for prior in (first, second):
                status, withheld = request(url + '/evidence-reports/' + prior['report_id'])
                assert status == 200 and withheld['state'] == 'content_withheld'
                assert withheld['body'] is withheld['snapshot'] is None
                assert withheld['body_sha256'] == prior['body_sha256']

            # Test class-specific rights before any withdrawal can mask them.
            rights_database = 'oi_api_test_evidence_rights_restore'
            rights_before = restore('oi_api_synthetic', rights_database)
            rights_receipts = []
            status, restored_manual_history = request(passage_path)
            assert status == 200 and restored_manual_history['state'] == 'reassessment_required'
            assert restored_manual_history['passages'][0]['anchor'] == manual_selection['anchor']
            assert request(passage_path, passage_command) == (200, passage_receipt | {'duplicate': True})
            rights_receipts.append(restored_manual_history['access_receipt_id'])
            status, latest_original = request(url + '/evidence/' + changed['evidence_id'] + '/original')
            assert status == 200 and hashlib.sha256(latest_original['original_text'].encode()).hexdigest() == changed['sha256']
            rights_receipts.append(latest_original['access_receipt_id'])
            for prior in (first, second):
                status, withheld = request(url + '/evidence-reports/' + prior['report_id'])
                assert status == 200 and withheld['state'] == 'content_withheld'
                assert withheld['body'] is withheld['snapshot'] is None
                assert withheld['body_sha256'] == prior['body_sha256']
                rights_receipts.append(withheld['access_receipt_id'])
            denied_before = snapshot(rights_database)
            assert request(url + '/evidence/' + support['evidence_id'] + '/original')[0] == 404
            assert snapshot(rights_database) == denied_before
            assert_continuity(rights_receipts)
            rights_access_count = assert_restored_reads(rights_before, rights_database, rights_receipts, expect_manual=True)
            serve_database('oi_api_synthetic')
            assert snapshot() == rights_before
            withdrawal = {'synthetic': True, 'request_key': 'WITHDRAW-SUPPORT',
                          'reason': 'Withdraw the independently fictional evidence family for verification.'}
            withdraw_url = url + '/evidence/' + changed['evidence_id'] + '/withdraw'
            status, withdrawn = request(withdraw_url, withdrawal)
            assert status == 201
            assert request(withdraw_url, withdrawal) == (200, {**withdrawn, 'duplicate': True})
            assert request(url + '/evidence/' + support['evidence_id'] + '/original')[0] == 404

            status, _ = request(prefix + '/sources', {'synthetic': True, 'original_text': SOURCE_AMENDMENT})
            assert status == 201
            assert packet()['question']['source_context_state'] == 'source_reassessment_required'
            assert request(url + '/evidence-assessments', a2[1]) == (200, a2[2])
            before = snapshot()
            assert request(url + '/evidence-assessments', {**a2[1], 'request_key': 'STALE-NEW-ASSESSMENT'})[0] == 409
            assert snapshot() == before

            # Backup contains exact originals, complete immutable snapshots and receipts.
            before = snapshot()
            assert before['public.alembic_version'] == [{'version_num': SCHEMA_REVISION}]
            encoded_events = json.dumps(before['identity.identity_domain_events'], ensure_ascii=False)
            assert token not in encoded_events and 'invented café' not in encoded_events
            restored = 'oi_api_test_evidence_restore'
            assert restore('oi_api_synthetic', restored) == before
            withheld_receipts = []
            restored_packet = packet()
            assert restored_packet['question']['source_context_state'] == 'source_reassessment_required'
            withdrawn_rows = [e for e in restored_packet['evidence'] if e['evidence_key'] == 'INK-SUPPORT']
            assert len(withdrawn_rows) == 3
            assert all(e['state'] == 'withdrawn' and e['title'] is e['statement'] is None for e in withdrawn_rows)
            withheld_receipts.append(restored_packet['access_receipt_id'])
            for prior in (first, second):
                status, withheld = request(url + '/evidence-reports/' + prior['report_id'])
                assert status == 200 and withheld['state'] == 'content_withheld'
                assert withheld['body'] is withheld['snapshot'] is None
                for field in ('report_id', 'prepared_at', 'body_sha256', 'snapshot_sha256'):
                    assert withheld[field] == prior[field]
                withheld_receipts.append(withheld['access_receipt_id'])
            status, original = request(url + '/evidence/' + counter['evidence_id'] + '/original')
            assert status == 200 and original['original_text'] == counter_text
            withheld_receipts.append(original['access_receipt_id'])
            for _, intent, duplicate in (a1, a2, a3):
                assert request(url + '/evidence-assessments', intent) == (200, duplicate)
            for intent, duplicate in report_commands:
                assert request(url + '/evidence-reports', intent) == (200, duplicate)
            assert request(withdraw_url, withdrawal) == (200, {**withdrawn, 'duplicate': True})
            assert_continuity(withheld_receipts, stale=True)
            withheld_access_count = assert_restored_reads(before, restored, withheld_receipts)

            # Rights and independent action grants still apply after recovery;
            # denied/stale requests cannot write receipts, events or new rows.
            denied_before = snapshot(restored)
            assert request(url + '/evidence/' + support['evidence_id'] + '/original')[0] == 404
            # Latest api_output was readable at the rights-only checkpoint.
            # Its denial here therefore requires the restored withdrawal.
            assert request(url + '/evidence/' + changed['evidence_id'] + '/original')[0] == 404
            assert request(url + '/evidence-assessments', {**a2[1], 'request_key': 'RESTORED-STALE-ASSESSMENT'})[0] == 409
            assert snapshot(restored) == denied_before
            credential['actions'].remove('evidence_report_export'); save_access()
            status, denied = request(url + '/evidence-reports/' + first['report_id'])
            assert status == 404 and 'body' not in denied
            assert request(url + '/evidence-reports', report_commands[0][0])[0] == 404
            assert snapshot(restored) == denied_before
            credential['actions'] = list(actions); save_access()

            # Persist revocation in the recovered copy, then restore that copy
            # again: an active fixture credential cannot revive its case binding.
            status, revoked = request(patient_path + '/case-bindings/' + CASE + '/revoke', {
                'synthetic': True, 'reason': 'Revoke the independently fictional recovered binding.'})
            assert status == 200 and revoked['duplicate'] is False
            revoked_database = 'oi_api_test_evidence_revoked_restore'
            revoked_before = restore(restored, revoked_database)
            assert revoked_before['coordination.patient_case_bindings'][0]['status'] == 'revoked'
            for path, intent in ((url + '/evidence', None),
                                 (url + '/evidence/' + counter['evidence_id'] + '/original', None),
                                 (url + '/evidence-reports/' + first['report_id'], None),
                                 (url + '/evidence-assessments', a2[1]),
                                 (url + '/evidence-reports', report_commands[0][0]),
                                 (url + '/evidence-links', None),
                                 (url + '/evidence-links', citation_intent),
                                 (prefix + '/followthrough', None),
                                 (url + '/followthrough', task_intent)):
                status, denied = request(path, intent)
                assert status == 404 and not ({'body', 'snapshot', 'original_text', 'access_receipt_id'} & denied.keys())
            assert snapshot(revoked_database) == revoked_before, 'Denied restored binding caused effects'
            assert snapshot(restored) == revoked_before, 'Revoked restore touched its source database'
            assert snapshot() == before, 'Restored verification changed original database'
            receipt = {'contract': 'oi.h1-evidence-recovery-acceptance/3', 'patient_id': patient,
                       'case_id': CASE, 'question_id': question_id, 'source_id': source['source_id'],
                       'evidence_ids': [e['evidence_id'] for e in (support, counter, amended, changed)],
                       'assessment_ids': [a1[0], a2[0], a3[0]],
                       'reports': [{k: r[k] for k in ('report_id', 'prepared_at', 'body_sha256', 'snapshot_sha256')}
                                   for r in (first, second)],
                       'complete_table_row_counts': {k: len(v) for k, v in before.items()},
                       'schema_revision': SCHEMA_REVISION, 'api_restart': True, 'database_restart': True,
                       'complete_dump_restore_equal': True, 'rights_class_change_withholds_history': True,
                       'withdrawal_preserves_history': True, 'source_amendment_rejects_new_stale_assessment': True,
                       'restored_readable_http': True, 'restored_withheld_http': True,
                       'restored_rights_class_change_withholds_history': True,
                       'restored_withdrawal_denies_previously_readable_original': True,
                       'api_database_target_verified': True, 'business_sequences_unchanged_on_retry': True,
                       'restored_exact_retry_identity': True, 'restored_independent_export_denial': True,
                       'restored_revoked_binding_denial': True, 'original_database_unchanged': True,
                       'citation_link_id': citation_receipt['link_id'], 'followthrough_task_id': task_receipt['task_id'],
                       'restored_same_question_citation_report_and_task': True,
                       'restored_manual_context_and_exact_retry': True,
                       'restored_manual_anchor': manual_selection['anchor'],
                       'manual_annotation_correction_preserves_report_bytes': True,
                       'restored_independent_original_read_denial': True,
                       'restored_manual_access_events': manual_access_count,
                       'authored_withholding_does_not_grant_or_revoke_metadata': True,
                       'restored_readable_access_events': readable_access_count,
                       'restored_rights_access_events': rights_access_count,
                       'restored_withheld_access_events': withheld_access_count,
                       'clinical_approval': False, 'model_executed': False}
            if destination := os.environ.get('OI_EVIDENCE_ACCEPTANCE_FILE'):
                path = Path(destination); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
            print('PASS EVIDENCE RECOVERY: actual HTTP case evidence, immutable originals/comparisons/report, '
                  'content-specific rights, exact retry after evidence/source amendment, historical withholding, '
                  'API/DB restart, complete dump/restore equality and actual restored HTTP; '
                  'readable/withheld reports, same-key recovery, independent grants and restored revoked binding; '
                  'original database unchanged; no clinical/model execution.')
        except Exception:
            command(['logs', '--no-color', '--tail', '80'], check=False)
            raise
        finally:
            command(['down', '--volumes'])


if __name__ == '__main__':
    main()
