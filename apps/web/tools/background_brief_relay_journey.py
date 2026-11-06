"""Exercise a real interrupted relay and a second fictional patient in the browser fixture."""
import json
import signal
import subprocess
import sys

from sqlalchemy import create_engine, text
from browser_journey import wait_for


def queue(api, case_path, question, key):
    status, receipt = api(case_path + '/questions/' + question['question_id'] + '/runs', {
        'synthetic': True, 'request_key': key, 'source_snapshot_contract': question['source_snapshot_contract'],
        'expected_source_snapshot_sha256': question['source_snapshot_sha256'],
        'expected_preflight_sha256': question['preflight_sha256']})
    assert status == 201 and receipt['run']['state'] == 'queued'
    return receipt['run']['run_id']


def seed_control(api, credential, write_grants, original, primary_case):
    code, patient = api('/v1/patients', {'synthetic': True, 'request_key': 'RELAY-CONTROL-PATIENT'})
    assert code == 201
    patient_id = patient['patient_id']
    credential['patient_ids'].append(patient_id)
    write_grants()
    patient_path = '/v1/patients/' + patient_id
    case = 'CASE-RELAY-CONTROL'
    code, _ = api(patient_path + '/case-bindings', {
        'synthetic': True, 'case_id': case, 'source_organization': 'ORG-INSTITUTION',
        'source_system': 'SYS-SYNTH', 'source_subject_ref': 'SUBJECT-RELAY-CONTROL', 'review_ref': 'REVIEW-SYNTH'})
    assert code == 201
    path = patient_path + '/cases/' + case
    code, source = api(path + '/sources', {'synthetic': True, 'original_text': original.replace(primary_case, case)})
    assert code == 201
    _, world = api(path + '/world-model')
    question = 'Which reported detail in this fictional control case requires verification?'
    _, preflight = api(path + '/composer/source-preflight', {
        'synthetic': True, 'expected_source_snapshot_sha256': world['snapshot_fingerprint'],
        'source_id': source['source_id'], 'source_line': 8, 'question': question})
    code, saved = api(path + '/questions', {
        'synthetic': True, 'request_key': 'RELAY-CONTROL-QUESTION', 'question': question,
        'source_id': source['source_id'], 'source_line': 8, 'expected_source_snapshot_sha256': world['snapshot_fingerprint'],
        'expected_preflight_sha256': preflight['preflight_sha256']})
    assert code == 201
    run = queue(api, path, {**preflight, 'question_id': saved['question_id']}, 'RELAY-CONTROL-RUN')
    return patient_id, case, path + '/questions/' + saved['question_id'] + '/runs/' + run


def recover_amendment(api, patient, case, question_id, original, amendment, credential, write_grants, worker_env):
    path = f'/v1/patients/{patient}/cases/{case}'
    _, history = api(path + '/questions')
    question = next(q for q in history['questions'] if q['question_id'] == question_id)
    affected = queue(api, path, question, 'RELAY-BEFORE-AMENDMENT')
    control, other_case, control_run = seed_control(api, credential, write_grants, original, case)

    def command(module, patient_id, case_id):
        return [sys.executable, '-m', module, '--once', '--patient', patient_id, '--case', case_id]

    def once(args):
        proc = subprocess.run(args, env=worker_env, capture_output=True, text=True, timeout=30, check=True)
        return json.loads(proc.stdout)

    relay = command('oi_api.event_worker', patient, case)
    database = create_engine(worker_env['OI_API_DATABASE_URL'], hide_parameters=True)
    try:
        # Only the amendment may be outstanding when the relay is killed.
        for _ in range(100):
            prior = once(relay)
            if prior['status'] == 'idle':
                break
            assert prior['status'] == 'delivered' and prior['invalidated_count'] == 0
        else:
            raise AssertionError('Prior source events did not drain')
        code, amended = api(path + '/sources', {'synthetic': True, 'original_text': amendment})
        assert code == 201 and amended['version'] == 2
        delivery = text("""
            SELECT d.delivery_id, d.state, d.attempt_count, d.lease_expires_at <= clock_timestamp() AS expired
            FROM coordination.source_event_deliveries d
            JOIN coordination.source_event_outbox o ON o.event_id=d.event_id
            WHERE o.source_id=:source AND d.patient_id=:patient AND d.actor=:actor
        """)
        scope = {'source': amended['source_id'], 'patient': patient, 'actor': credential['actor']}

        def read_delivery():
            with database.connect() as conn:
                return conn.execute(delivery, scope).mappings().one_or_none()

        # Hold only the affected run. Claim commits independently, then the real
        # worker blocks on this row before it can publish its first effect.
        with database.begin() as lock:
            assert lock.execute(text('SELECT run_id FROM investigation.composer_tool_runs '
                                     'WHERE run_id=:run FOR UPDATE'), {'run': affected}).scalar_one() == affected
            child = subprocess.Popen(relay + ['--lease-seconds', '3'], env=worker_env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                claimed = wait_for(read_delivery, 'durable amendment delivery claim')
                assert claimed['state'] == 'running' and claimed['attempt_count'] == 1
                assert child.poll() is None
            finally:
                child.kill()
                child.communicate(timeout=10)
            assert child.returncode == -signal.SIGKILL
        assert api(path + '/questions/' + question_id + '/runs/' + affected)[1]['state'] == 'queued'
        # The unaffected patient can complete while the first relay is down.
        assert api(control_run)[1]['state'] == 'queued'
        assert once(command('oi_api.worker', control, other_case)) == {'status': 'completed', 'attempt_count': 1}
        control_before = api(control_run)[1]
        assert control_before['state'] == 'completed'
        wait_for(lambda: read_delivery()['expired'], 'database-clock expiry of killed relay lease')
        assert once(relay) == {'status': 'delivered', 'attempt_count': 2, 'invalidated_count': 1}
        code, replay = api(path + '/sources', {'synthetic': True, 'original_text': amendment})
        assert code == 200 and replay['duplicate'] and replay['source_id'] == amended['source_id']
        assert once(relay) == {'status': 'idle'}
        with database.connect() as conn:
            receipt = conn.execute(text('SELECT attempt_count,invalidated_count FROM investigation.composer_source_event_receipts '
                                        'WHERE delivery_id=:id'), {'id': claimed['delivery_id']}).all()
            assert [tuple(row) for row in receipt] == [(2, 1)]
            transitions = conn.execute(text('SELECT state FROM investigation.composer_tool_run_events '
                                            'WHERE run_id=:run ORDER BY revision'), {'run': affected}).scalars().all()
            assert transitions == ['queued', 'stale']
        assert api(control_run)[1] == control_before
        result = api(control_run + '/result')[1]
        assert result['brief']['patient_id'] == control and result['result_sha256'] == control_before['result_sha256']
        return amended, affected
    finally:
        database.dispose()
        credential['patient_ids'].remove(control)
        write_grants()
