"""Persistent loopback-only fictional H1 demo. No real account or patient use.

up explicitly renews one operator-controlled synthetic grant for 12 hours.
stop retains the database volume. This tool never deletes a volume or resets data.
"""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import uuid

ROOT = Path(__file__).resolve().parents[1]
CASE = 'CASE-DEMO'
BASE = 'http://127.0.0.1:8000'
ACTIONS = ['patient_create', 'patient_read', 'case_binding_create', 'case_binding_read',
           'source_import', 'source_read', 'source_original_read', 'composer_context_read',
           'question_create', 'question_read', 'review_queue_read', 'review_return',
           'source_brief_export', 'review_packet_read', 'followthrough_read',
           'followthrough_create', 'followthrough_update', 'evidence_read', 'evidence_link',
           'authored_evidence_read', 'authored_evidence_import', 'authored_evidence_assess',
           'authored_evidence_original_read', 'evidence_report_export']


def write_json(path, value, mode=0o600):
    pending = path.with_suffix('.next')
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    pending.chmod(mode)
    pending.replace(path)


def load_or_create(directory):
    path = directory / 'state.json'
    if path.exists():
        state = json.loads(path.read_text())
        if (not isinstance(state, dict) or state.get('version') != 'oi.local-fictional-demo/1'
                or not re.fullmatch(r'oi-demo-[a-f0-9]{16}', state.get('project', ''))
                or not re.fullmatch(r'[A-Za-z0-9_-]{43}', state.get('token', ''))
                or not re.fullmatch(r'DEMO-[A-F0-9]{32}', state.get('request_key', ''))
                or state.get('patient_id') is not None and not re.fullmatch(r'PAT-[A-F0-9]{32}', state['patient_id'])):
            raise ValueError('Invalid demo state; refusing replacement')
        return state
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Demo directory is not empty and has no owned state')
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    state = {'version': 'oi.local-fictional-demo/1', 'project': 'oi-demo-' + uuid.uuid4().hex[:16],
             'request_key': 'DEMO-' + uuid.uuid4().hex.upper(),
             'token': secrets.token_urlsafe(32), 'patient_id': None, 'source_id': None}
    write_json(path, state)
    return state


def access_document(state, patients):
    return {'version': 'oi.synthetic-access/1', 'credentials': [{
        'token_sha256': hashlib.sha256(state['token'].encode()).hexdigest(),
        'actor': 'ACTOR-FICTIONAL-DEMO', 'organization': 'ORG-FICTIONAL-DEMO',
        'purpose': 'operations', 'actions': ACTIONS, 'patient_ids': patients,
        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()}]}


def compose_command(state):
    return ['docker', 'compose', '--project-name', state['project'],
            '--file', str(ROOT / 'apps/api/compose.yaml'),
            '--file', str(ROOT / 'apps/api/compose.synthetic-access.yaml')]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(path, token=None, body=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(BASE + path, headers=headers,
                  data=None if body is None else json.dumps(body).encode())
    with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=5) as response:
        return json.load(response)


def up(directory, state):
    access = directory / 'access'
    access.mkdir(exist_ok=True)
    access.chmod(0o755)  # The unprivileged API sees only credential hashes.

    def grant():
        write_json(access / 'access.json', access_document(state,
                   [state['patient_id']] if state['patient_id'] else []), 0o644)

    grant()
    env = dict(os.environ, OI_API_ACCESS_DIRECTORY=str(access.resolve()))
    command = compose_command(state)
    subprocess.run(command + ['up', '--build', '--detach', 'api'], cwd=ROOT, env=env, check=True)
    # Verify that requests will reach this owned Compose service, not a different
    # process sharing an assumed port. Docker itself rejects an occupied port.
    container = subprocess.check_output(command + ['ps', '--quiet', 'api'], cwd=ROOT, env=env, text=True).strip()
    inspected, = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))
    if (inspected['Config']['Labels'].get('com.docker.compose.project') != state['project']
            or inspected['NetworkSettings']['Ports'].get('8000/tcp') != [{'HostIp': '127.0.0.1', 'HostPort': '8000'}]):
        raise ValueError('Demo API ownership or loopback binding does not match')
    deadline = time.monotonic() + 60
    while True:
        try:
            if request('/health/ready')['status'] == 'ready':
                break
        except (OSError, URLError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('Demo API readiness timed out; state and volume retained')
        time.sleep(0.25)
    receipt = request('/v1/patients', state['token'],
                      {'synthetic': True, 'request_key': state['request_key']})
    patient = receipt['patient_id']
    if state['patient_id'] is not None and patient != state['patient_id']:
        raise ValueError('Patient identity changed; refusing to rebind the saved demonstration')
    state['patient_id'] = patient
    write_json(directory / 'state.json', state)
    grant()
    root = '/v1/patients/' + patient
    request(root + '/case-bindings', state['token'], {
        'synthetic': True, 'case_id': CASE, 'source_organization': 'ORG-FICTIONAL-LAB',
        'source_system': 'SYS-FICTIONAL-DEMO', 'source_subject_ref': 'FICTIONAL-PATIENT-A',
        'review_ref': 'REVIEW-FICTIONAL-DEMO'})
    sources = root + '/cases/' + CASE + '/sources'
    # A restart must not overwrite an amended source or resurrect missing data.
    if state['source_id'] is None:
        result = request(sources, state['token'], {'synthetic': True,
            'original_text': (ROOT / 'examples/synthetic/h1-demo-report.txt').read_text()})
        if result['result'] not in ('imported', 'duplicate'):
            raise ValueError('Fictional source was not accepted')
        state['source_id'] = result['source_id']
        write_json(directory / 'state.json', state)
    index = request(sources, state['token'])
    if not any(row['source_id'] == state['source_id'] for row in index['sources']):
        raise ValueError('Saved demo original is missing; refusing a silent reset')
    print('Fictional demo ready; database and patient identity retained.')
    print('Patient ID:', patient)
    print('Obtain the local fixture token with: python tools/h1_demo.py credentials --state-dir', directory)
    print('Start the built UI: npm --prefix apps/web run preview')
    print('Open http://127.0.0.1:4173 and follow docs/H1_DEMO.md')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['up', 'stop', 'credentials'])
    parser.add_argument('--state-dir', type=Path, default=ROOT / '.local/h1-demo')
    parser.add_argument('--fictional-only', action='store_true')
    args = parser.parse_args(argv)
    if args.command == 'up' and not args.fictional_only:
        parser.error('up requires --fictional-only; never use actual patient data')
    directory = args.state_dir.resolve()
    if args.command != 'up' and not (directory / 'state.json').is_file():
        parser.error('No existing demo state')
    state = load_or_create(directory)
    with (directory / 'operator.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.command == 'up':
            up(directory, state)
        elif args.command == 'credentials':
            print('Synthetic fixture token:', state['token'])
            print('Patient ID:', state['patient_id'])
        else:
            env = dict(os.environ, OI_API_ACCESS_DIRECTORY=str(directory / 'access'))
            subprocess.run(compose_command(state) + ['stop'], cwd=ROOT, env=env, check=True)
            print('Demo stopped. Database volume and local state retained.')


if __name__ == '__main__':
    main()
