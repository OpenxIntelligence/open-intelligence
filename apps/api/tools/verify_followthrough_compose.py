"""Actual HTTP, PostgreSQL restart and backup/restore proof for question tasks.

Uses the existing Compose topology, canonical source/question APIs and authored
review fixture. No database, HTTP response, clinical data or authority is mocked.
The restored database is also served through the real API before its binding is
revoked, so recovery is checked beyond a successful pg_restore exit code.
"""
from datetime import datetime, timedelta, timezone
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

from verify_reviews_compose import AMENDED, CASE, ORIGINAL, SOURCE_CONTRACT


ROOT = Path(__file__).resolve().parents[3]
BASE = 'http://127.0.0.1:8000'
TASK_CONTRACT = 'oi.pg-question-followthrough/1'
RESTORED = 'oi_api_test_followthrough_restore'
ANCHORS = ('question_id', 'source_id', 'source_line', 'source_sha256', 'source_version',
           'source_snapshot_contract', 'source_snapshot_sha256', 'preflight_sha256')


def main():
    project = 'oi-h1-followthrough-proof-' + uuid.uuid4().hex[:12]
    compose = ['docker', 'compose', '--project-name', project,
               '--file', str(ROOT / 'apps/api/compose.yaml'),
               '--file', str(ROOT / 'apps/api/compose.synthetic-access.yaml')]
    with tempfile.TemporaryDirectory(prefix='oi-synthetic-followthrough-access-') as directory:
        access = Path(directory)
        access.chmod(0o755)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=directory)
        token = secrets.token_urlsafe(32)
        actions = ['patient_create', 'patient_read', 'case_binding_create', 'case_binding_read',
                   'case_binding_revoke', 'source_import', 'source_read', 'composer_context_read',
                   'question_create', 'question_read', 'followthrough_create',
                   'followthrough_read', 'followthrough_update', 'evidence_read', 'evidence_link']
        credential = {
            'token_sha256': hashlib.sha256(token.encode()).hexdigest(),
            'actor': 'ACTOR-FOLLOWTHROUGH-PROOF', 'organization': 'ORG-FOLLOWTHROUGH-PROOF',
            'purpose': 'operations', 'actions': list(actions), 'patient_ids': [],
            'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }

        def save_access():
            pending = access / 'access.new'
            pending.write_text(json.dumps({'version': 'oi.synthetic-access/1',
                                           'credentials': [credential]}), encoding='utf-8')
            pending.chmod(0o644)
            pending.replace(access / 'access.json')

        def command(args, *, check=True, **kwargs):
            return subprocess.run(compose + args, cwd=ROOT, env=env,
                                  check=check, timeout=180, **kwargs)

        def query(sql, database='oi_api_synthetic'):
            result = command(['exec', '-T', 'db', 'psql', '-X', '-U', 'oi_api', '-d', database,
                              '-v', 'ON_ERROR_STOP=1', '-At', '-c', sql], capture_output=True, text=True)
            return json.loads(result.stdout)

        def request(path, body=None, *, authenticated=True):
            headers = {'Authorization': 'Bearer ' + token} if authenticated else {}
            if body is not None:
                headers['Content-Type'] = 'application/json'
            req = Request(BASE + path, headers=headers,
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
                    raise RuntimeError('Synthetic follow-through API did not become ready')
                time.sleep(0.25)

        def snapshot(database='oi_api_synthetic'):
            return query("""
                SELECT json_build_object(
                  'tasks', (SELECT COALESCE(json_agg(t ORDER BY t.task_id),'[]'::json)
                    FROM coordination.question_followthrough_tasks t),
                  'task_events', (SELECT COALESCE(json_agg(e ORDER BY e.task_id,e.revision),'[]'::json)
                    FROM coordination.question_followthrough_events e),
                  'questions', (SELECT COALESCE(json_agg(q ORDER BY q.question_id),'[]'::json)
                    FROM investigation.source_questions q),
                  'evidence_catalog', (SELECT COALESCE(json_agg(m ORDER BY m.record_id,m.version),'[]'::json)
                    FROM investigation.evidence_catalog_records m),
                  'evidence_rights', (SELECT COALESCE(json_agg(r ORDER BY r.record_id,r.version,r.revision),'[]'::json)
                    FROM investigation.evidence_rights_decisions r),
                  'evidence_links', (SELECT COALESCE(json_agg(l ORDER BY l.link_id),'[]'::json)
                    FROM investigation.question_evidence_links l),
                  'sources', (SELECT json_agg(s ORDER BY s.document_id,s.version)
                    FROM (SELECT source_id,case_id,document_id,version,sha256,
                      encode(sha256(raw),'hex') AS raw_sha256,octet_length(raw) AS byte_length,
                      state,supersedes_id FROM clinical_source.source_versions) s),
                  'assertions', (SELECT json_agg(a ORDER BY a.assertion_id)
                    FROM clinical_source.assertions a),
                  'bindings', (SELECT json_agg(b ORDER BY b.case_id)
                    FROM coordination.patient_case_bindings b),
                  'patients', (SELECT json_agg(p ORDER BY p.patient_id)
                    FROM identity.identity_patients p),
                  'events', (SELECT json_agg(e ORDER BY e.id)
                    FROM identity.identity_domain_events e),
                  'revision', (SELECT version_num FROM public.alembic_version))
            """, database)

        def read_tasks():
            status, value = request(prefix + '/followthrough')
            assert status == 200, 'Task history unavailable'
            assert value['contract'] == TASK_CONTRACT
            assert (value['patient_id'], value['case_id']) == (patient, CASE)
            assert value['synthetic'] is True
            assert value['clinical_approval'] is value['external_notification_sent'] is False
            assert value['evaluated_on'] == datetime.now(timezone.utc).date().isoformat()
            assert value['access_receipt_id'].startswith('ACCESS-')
            uuid.UUID(value['access_receipt_id'].removeprefix('ACCESS-'))
            return value

        def save_question(source_id):
            status, world = request(prefix + '/world-model')
            assert status == 200 and world['contract'] == SOURCE_CONTRACT
            proposal = {'synthetic': True, 'source_id': source_id, 'source_line': 8,
                        'question': 'Which fictional source details still require verification?',
                        'expected_source_snapshot_sha256': world['snapshot_fingerprint']}
            status, preflight = request(prefix + '/composer/source-preflight', proposal)
            assert status == 200 and preflight['source_snapshot_contract'] == SOURCE_CONTRACT
            status, receipt = request(prefix + '/questions', {
                **proposal, 'request_key': 'FOLLOWTHROUGH-COMPOSE-QUESTION',
                'expected_preflight_sha256': preflight['preflight_sha256']})
            assert status == 201 and receipt['duplicate'] is False
            status, history = request(prefix + '/questions')
            assert status == 200 and len(history['questions']) == 1
            question = history['questions'][0]
            assert question['question_id'] == receipt['question_id']
            assert question['source_context_state'] == 'current_unreviewed_question'
            return question

        writes = []

        def write_once(path, body, expected_revision):
            status, receipt = request(path, body)
            assert status == 201 and receipt['duplicate'] is False
            assert receipt['revision'] == expected_revision
            assert receipt['question_id'] == question['question_id']
            for field, marker in (('task_id', 'TASK-'), ('event_id', 'TASK-EVENT-')):
                assert receipt[field].startswith(marker)
                uuid.UUID(receipt[field].removeprefix(marker))
            before = snapshot()
            assert request(path, body) == (200, {**receipt, 'duplicate': True})
            after = snapshot()
            assert after['tasks'] == before['tasks'] and after['task_events'] == before['task_events']
            writes.append((path, body, {**receipt, 'duplicate': True}))
            return receipt

        def create_task(key, title):
            body = {'synthetic': True, 'request_key': key, 'title': title,
                    'detail': 'Collect the existing fictional source references.', 'owner_label': '',
                    'due_date': (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
                    'review_trigger': 'When another source arrives',
                    'reason': 'Recorded for the fictional discussion.',
                    'source_snapshot_contract': question['source_snapshot_contract'],
                    'expected_source_snapshot_sha256': question['source_snapshot_sha256'],
                    'expected_preflight_sha256': question['preflight_sha256']}
            return write_once(prefix + '/questions/' + question['question_id'] + '/followthrough', body, 1)

        def transition(task_id, status, revision, owner=''):
            return write_once(prefix + '/followthrough/' + task_id + '/transitions', {
                'synthetic': True, 'request_key': 'TASK-' + task_id[-10:] + '-REV-' + str(revision),
                'expected_revision': revision - 1, 'status': status, 'owner_label': owner,
                'reason': 'Recorded fictional work status: ' + status + '.',
            }, revision)

        def assert_history(database='oi_api_synthetic'):
            value = read_tasks()
            assert len(value['tasks']) == 3
            for row in value['tasks']:
                old = original_tasks[row['task_id']]
                for field in (*ANCHORS, 'created_at', 'title', 'detail', 'due_date', 'review_trigger',
                              'owner_label', 'status', 'revision', 'history'):
                    assert row[field] == old[field], 'Recovery changed ' + field
                assert row['source_context_state'] == 'source_reassessment_required'
                assert row['needs_recheck'] is (row['task_id'] == open_task)
                assert row['is_overdue'] is (row['task_id'] == open_task)
                assert row['is_due_soon'] is False and row['clinical_approval'] is False
                assert all(event['actor_label'] == credential['actor'] for event in row['history'])
            # Replays remain exact even after revision changes, amendment and restoration.
            before = snapshot(database)
            for path, body, receipt in writes:
                assert request(path, body) == (200, receipt)
            # Original citation identity survives revocation, source amendment,
            # API/DB restart and actual restore. Metadata stays withheld.
            status, citations = request(evidence_path)
            assert status == 200 and citations['contract'] == 'oi.pg-question-evidence-links/1'
            assert citations['source_context_state'] == 'source_reassessment_required'
            assert citations['links'] == redacted_citations
            assert all(item['record'] is None and item['status'] == 'rights_restricted'
                       for item in citations['links'])
            assert request(evidence_path, evidence_body) == (200, {**evidence_receipt, 'duplicate': True})
            after = snapshot(database)
            assert after['tasks'] == before['tasks'] and after['task_events'] == before['task_events']
            assert len(after['tasks']) == 3 and len(after['task_events']) == 9
            assert len(after['questions']) == 1
            assert len(after['evidence_catalog']) == 2 and len(after['evidence_rights']) == 3
            assert len(after['evidence_links']) == 1
            assert len([e for e in after['events'] if e['event_type'] == 'evidence.citation.linked']) == 1
            business = [event for event in after['events']
                        if event['event_type'].startswith('coordination.followthrough.')]
            assert len(business) == 9, 'Replay duplicated a task business event'
            assert after['revision'] == SCHEMA_REVISION
            for row, raw in zip(after['sources'], (ORIGINAL, AMENDED)):
                assert row['sha256'] == row['raw_sha256'] == hashlib.sha256(raw.encode('utf-8')).hexdigest()
            encoded = json.dumps(after['events'], ensure_ascii=False)
            assert token not in encoded and 'Independently fictional café marker' not in encoded
            return after

        save_access()
        try:
            command(['config', '--quiet'])
            command(['up', '--build', '--detach', 'api'])
            ready()
            command(['exec', '-T', 'api', 'python', '-m', 'oi_api.evidence_catalog'])
            status, created = request('/v1/patients', {
                'synthetic': True, 'request_key': 'CREATE-FOLLOWTHROUGH-COMPOSE-PROOF'})
            assert status == 201 and created['duplicate'] is False
            patient = created['patient_id']
            credential['patient_ids'] = [patient]
            save_access()
            patient_path = '/v1/patients/' + patient
            status, bound = request(patient_path + '/case-bindings', {
                'synthetic': True, 'case_id': CASE, 'source_organization': 'ORG-SYNTHETIC-REVIEW',
                'source_system': 'SYS-SYNTHETIC-REVIEW', 'source_subject_ref': 'SUBJECT-REVIEW',
                'review_ref': 'REVIEW-SYNTHETIC-COMPOSE'})
            assert status == 201 and bound['patient_id'] == patient
            prefix = patient_path + '/cases/' + CASE
            status, source = request(prefix + '/sources', {'synthetic': True, 'original_text': ORIGINAL})
            assert status == 201 and source['version'] == 1
            question = save_question(source['source_id'])
            evidence_path = prefix + '/questions/' + question['question_id'] + '/evidence-links'
            status, search = request(prefix + '/questions/' + question['question_id'] + '/evidence-search',
                                     {'synthetic': True, 'query': 'continuity'})
            assert status == 200 and len(search['records']) == 1
            metadata = search['records'][0]
            assert metadata['citation'] == 'FICT-RECORD-CONTINUITY@1'
            assert metadata['availability'] == 'metadata_only' and search['content_appraised'] is False
            evidence_body = {
                'synthetic': True, 'request_key': 'EVIDENCE-COMPOSE-LINK', 'citation': metadata['citation'],
                'expected_metadata_sha256': metadata['metadata_sha256'],
                'source_snapshot_contract': question['source_snapshot_contract'],
                'expected_source_snapshot_sha256': question['source_snapshot_sha256'],
                'expected_preflight_sha256': question['preflight_sha256'],
            }
            status, evidence_receipt = request(evidence_path, evidence_body)
            assert status == 201 and evidence_receipt['duplicate'] is False
            assert request(evidence_path)[1]['links'][0]['record'] == metadata
            # Operator-only original fixture governance port; no UI can grant
            # itself rights. Real biomedical content is not enabled here.
            command(['exec', '-T', 'api', 'python', '-c', '''
from oi_api.config import Settings
from oi_api.database import Database
from oi_api.evidence_catalog import append_rights_decision
from open_intelligence.postgres_registry import PostgresPatientRegistry
database = Database(Settings.from_env())
try:
    with database.registry_connection() as connection:
        append_rights_decision(PostgresPatientRegistry(connection, lambda *args: False),
            'FICT-RECORD-CONTINUITY', '1', permissions={'metadata': {'store': 'allowed', 'display': 'allowed'}},
            revoked=True, superseded=False, recorded_by='FIXTURE-RESTORE-REVIEWER',
            reason='Original fictional rights revocation for recovery verification')
finally:
    database.close()
'''])
            redacted_citations = request(evidence_path)[1]['links']
            assert redacted_citations[0]['record'] is None
            assert metadata['title'] not in json.dumps(redacted_citations)
            done = create_task('FOLLOWTHROUGH-COMPOSE-DONE', 'Prepare the fictional source discussion')['task_id']
            before = snapshot()
            path, body, _ = writes[0]
            assert request(path, {**body, 'title': 'Changed fictional intent with the same key'})[0] == 409
            assert request(prefix + '/followthrough/' + done + '/transitions', {
                'synthetic': True, 'request_key': 'PREMATURE-COMPLETION', 'expected_revision': 1,
                'status': 'completed', 'reason': 'Attempted completion before acknowledgment.'})[0] == 409
            assert snapshot() == before, 'Rejected writes changed history or emitted an access receipt'
            transition(done, 'assigned', 2, 'Fictional coordinator')
            transition(done, 'acknowledged', 3)
            transition(done, 'completed', 4)
            open_task = create_task('FOLLOWTHROUGH-COMPOSE-OPEN', 'Revisit the fictional source amendment')['task_id']
            deferred = create_task('FOLLOWTHROUGH-COMPOSE-DEFERRED', 'Arrange a later fictional records discussion')['task_id']
            transition(deferred, 'deferred', 2)
            transition(deferred, 'assigned', 3, 'Fictional later coordinator')
            transition(deferred, 'deferred', 4)
            original_tasks = {row['task_id']: row for row in read_tasks()['tasks']}
            assert {row['status'] for row in original_tasks.values()} == {'created', 'completed', 'deferred'}
            for row in original_tasks.values():
                assert all(row[field] == question[field] for field in ANCHORS)
                assert row['source_context_state'] == 'current_unreviewed_question'
                assert row['needs_recheck'] is False
            status, amendment = request(prefix + '/sources', {'synthetic': True, 'original_text': AMENDED})
            assert status == 201 and amendment['version'] == 2
            before = snapshot()
            assert request(writes[0][0], {**writes[0][1], 'request_key': 'STALE-NEW-TASK'})[0] == 409
            assert snapshot() == before, 'New work from stale context changed history'
            first, second = read_tasks(), read_tasks()
            assert first['access_receipt_id'] != second['access_receipt_id']
            assert first['tasks'] == second['tasks']
            assert_history()

            for missing in ('followthrough_read', 'followthrough_update', 'question_read', 'source_read'):
                credential['actions'] = [action for action in actions if action != missing]
                save_access()
                before = snapshot()
                if missing != 'followthrough_update':
                    status, denied = request(prefix + '/followthrough')
                    assert status == 404 and 'tasks' not in denied and 'access_receipt_id' not in denied
                if missing != 'followthrough_read':
                    assert request(writes[1][0], writes[1][1])[0] == 404
                assert snapshot() == before, 'Denied access changed durable state'
            credential['actions'] = list(actions)
            save_access()

            for service in ('api', 'db'):
                before = assert_history()
                command(['restart', service])
                ready()
                assert snapshot() == before, 'Restart changed source/question/task/event history'
                assert_history()
                print('Canonical task receipts, original anchors and full history survived ' + service + ' restart')

            before = assert_history()
            dump = command(['exec', '-T', 'db', 'pg_dump', '-U', 'oi_api', '-d',
                            'oi_api_synthetic', '--format=custom'], capture_output=True).stdout
            command(['exec', '-T', 'db', 'createdb', '-U', 'oi_api', RESTORED])
            command(['exec', '-T', 'db', 'pg_restore', '-U', 'oi_api', '-d', RESTORED,
                     '--exit-on-error', '--no-owner'], input=dump)
            assert snapshot(RESTORED) == before, 'Dump/restore changed original bytes, provenance or task history'
            override = access / 'restored-compose.yaml'
            override.write_text(json.dumps({'services': {'api': {'environment': {
                'OI_API_DATABASE_URL': 'postgresql+pg8000://oi_api:oi_h1_synthetic_only@db:5432/' + RESTORED,
            }}}}), encoding='utf-8')
            compose.extend(['--file', str(override)])
            command(['up', '--detach', '--no-deps', '--force-recreate', 'api'])
            ready()
            assert_history(RESTORED)
            print('Restored PostgreSQL database served the same tasks and exact retry receipts through real HTTP')

            status, revoked = request(patient_path + '/case-bindings/' + CASE + '/revoke', {
                'synthetic': True, 'reason': 'Withdraw the independently fictional restored task binding'})
            assert status == 200 and revoked['duplicate'] is False
            before = snapshot(RESTORED)
            assert request(prefix + '/followthrough')[0] == 404
            assert request(writes[1][0], writes[1][1])[0] == 404
            assert request(evidence_path)[0] == 404
            assert request(evidence_path, evidence_body)[0] == 404
            assert snapshot(RESTORED) == before
            assert before['bindings'][0]['status'] == 'revoked'
            print('PASS FOLLOWTHROUGH COMPOSE: actual canonical HTTP lifecycle, acknowledgment gate, '
                  'exact retry identity, immutable provenance after source amendment, independent rights, '
                  'API/DB restarts, actual pg_dump/pg_restore, restored HTTP reads/replays and binding revocation; '
                  'three synthetic tasks and nine durable task events; no clinical approval.')
            print('PASS EVIDENCE RECOVERY: fictional metadata, immutable citation, exact retry and append-only '
                  'rights revocation survived API/DB restarts and actual pg_dump/pg_restore; restored HTTP '
                  'withheld revoked title/URL and denied the revoked patient binding; no clinical appraisal.')
        except Exception:
            command(['logs', '--no-color', '--tail', '80'], check=False)
            raise
        finally:
            command(['down', '--volumes'])


if __name__ == '__main__':
    main()
