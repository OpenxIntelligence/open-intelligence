"""One process owner for the confined, synthetic retained-store experiment."""
from __future__ import annotations

import argparse
from hashlib import file_digest
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

from open_intelligence.store import InvalidInput
from tools.imaging.network_confinement import (
    capture_network_evidence, network_evidence_is_confined,
)
from tools.imaging.pacsnode_lifecycle_evaluation import (
    acceptance_exit_code, run_lifecycle_evaluation,
)


def _digest(path: Path) -> str:
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def wait_for_confined_backend(process: subprocess.Popen, parent_namespace: str) -> dict:
    """HTTP is startup polling only; require both actual owned confined sockets."""
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise InvalidInput('Backend exited before confined readiness')
        connection = http.client.HTTPConnection('127.0.0.1', 18042, timeout=2)
        try:
            connection.request('GET', '/health')
            healthy = connection.getresponse().status == 200
            evidence = capture_network_evidence(process.pid, parent_namespace)
            if healthy and network_evidence_is_confined(evidence):
                return evidence
        except (OSError, ValueError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        time.sleep(0.25)
    raise InvalidInput('Both confined backend listeners did not become ready')


def _listeners_absent() -> bool:
    for port in (18042, 11112):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return False
        except ConnectionRefusedError:
            continue
        except OSError:
            # A timeout/routing failure is not evidence that a listener closed.
            return False
    return True


class PacsProcess:
    """Keep one unchanged binary/configuration/directory through orderly restarts."""

    def __init__(self, binary: Path, run_directory: Path, parent_namespace: str,
                 log_directory: Path, *, stop_timeout: float = 10.0):
        self.binary = Path(binary).resolve(strict=True)
        self.run_directory = Path(run_directory).resolve(strict=True)
        self.config = self.run_directory / 'config.toml'
        if (not self.binary.is_file() or not os.access(self.binary, os.X_OK)
                or not self.config.is_file() or not 0 < stop_timeout <= 30):
            raise InvalidInput('Invalid bounded backend process configuration')
        self.parent_namespace = parent_namespace
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.stop_timeout = stop_timeout
        self.binary_sha256 = _digest(self.binary)
        self.config_sha256 = _digest(self.config)
        self.process = None
        self.last_evidence = None
        self._log = None
        self._starts = 0

    def _unchanged(self) -> None:
        if (_digest(self.binary) != self.binary_sha256
                or _digest(self.config) != self.config_sha256):
            raise InvalidInput('Binary or configuration changed during retained-store test')

    def start(self) -> dict:
        if self.process is not None:
            raise InvalidInput('A backend process is already owned')
        self._unchanged()
        self._starts += 1
        self._log = (self.log_directory / f'backend-{self._starts}.log').open('wb')
        try:
            self.process = subprocess.Popen(
                [str(self.binary)], cwd=self.run_directory, stdin=subprocess.DEVNULL,
                stdout=self._log, stderr=subprocess.STDOUT)
            observed = wait_for_confined_backend(self.process, self.parent_namespace)
            if (not network_evidence_is_confined(observed)
                    or observed['server_pid'] != self.process.pid):
                raise InvalidInput('Readiness evidence does not identify the owned process')
            self.last_evidence = observed
            return observed
        except Exception:
            self.close()
            raise

    def _stop(self, *, require_graceful: bool) -> int | None:
        process = self.process
        if process is None:
            if require_graceful:
                raise InvalidInput('No running backend to restart')
            return None
        was_running = process.poll() is None
        forced = False
        try:
            if was_running:
                process.send_signal(signal.SIGINT)
            try:
                code = process.wait(timeout=self.stop_timeout)
            except subprocess.TimeoutExpired:
                forced = True
                process.kill()
                code = process.wait(timeout=5)
            if require_graceful and (not was_running or forced or code != 0):
                raise InvalidInput('Backend did not exit successfully after SIGINT')
            return code
        finally:
            # A failed post-kill wait still owns an unreaped child. Preserve
            # both handle and log so a later cleanup can retry safely.
            if process.returncode is not None:
                self.process = None
                if self._log is not None:
                    self._log.close()
                    self._log = None

    def restart(self) -> dict:
        self._unchanged()
        if self.process is None or self.process.poll() is not None:
            raise InvalidInput('Cannot restart an absent or already exited backend')
        before = wait_for_confined_backend(self.process, self.parent_namespace)
        if (not network_evidence_is_confined(before)
                or before['server_pid'] != self.process.pid):
            raise InvalidInput('Pre-stop network evidence changed')
        exit_code = self._stop(require_graceful=True)
        absent = _listeners_absent()
        if not absent:
            raise InvalidInput('Old listeners remain reachable after process exit')
        after = self.start()
        same_namespace = all(before[key] == after[key] for key in (
            'parent_namespace', 'probe_namespace', 'server_namespace', 'expected_ports'))
        distinct_process = ((before['server_pid'], before['server_start_ticks'])
                            != (after['server_pid'], after['server_start_ticks']))
        if not same_namespace or not distinct_process:
            self.close()
            raise InvalidInput('Restart did not retain confinement with a new process')
        return {
            'restart_verified': True, 'stop_signal': 'SIGINT',
            'stop_exit_code': exit_code, 'old_process_reaped_before_start': True,
            'old_listeners_absent': absent, 'binary_sha256': self.binary_sha256,
            'config_sha256': self.config_sha256, 'same_run_directory': True,
            'run_directory': str(self.run_directory),
            'sqlite_path': str(self.run_directory / 'data' / 'pacsnode.db'),
            'before': before, 'after': after,
        }

    def close(self) -> None:
        self._stop(require_graceful=False)
        if self._log is not None:
            self._log.close()
            self._log = None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--run-directory', type=Path, required=True)
    parser.add_argument('--parent-namespace', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--immutable-write-checks', action='store_true',
                        help='Require concurrent immutable writes and post-conflict restart')
    args = parser.parse_args()
    result = {'kind': 'oi.pacs-lifecycle/1', 'classification': 'HOLD_NOT_APPROVED',
              'evaluation_completed': False, 'lifecycle_acceptance_passed': False,
              'backend_adoption_approved': False, 'real_patient_data_used': False,
              'phases': {}, 'acceptance_blockers': ['lifecycle_evaluation_incomplete']}
    owner, stage = None, 'process_start'
    try:
        # The outer runner creates config once in an empty directory. Reject
        # reuse at experiment start, but retain ALL data for each restart.
        if {p.name for p in args.run_directory.iterdir()} != {'config.toml'}:
            raise InvalidInput('Live lifecycle requires a fresh configured run directory')
        owner = PacsProcess(args.binary, args.run_directory, args.parent_namespace,
                            args.run_directory / 'process-logs')
        before = owner.start()
        stage = 'lifecycle_protocol'
        result = run_lifecycle_evaluation(
            'http://127.0.0.1:18042', args.run_directory / 'oi-source', owner.restart,
            immutable_write_checks=args.immutable_write_checks)
        result['evaluation_network_boundary'] = {'before': before}
        stage = 'network_after'
        after = wait_for_confined_backend(owner.process, args.parent_namespace)
        result['evaluation_network_boundary']['after'] = after
        restarts = result.get('restart_observations', [])
        result['process_restarts_verified'] = (
            len(restarts) == (3 if args.immutable_write_checks else 2) and all(
                r.get('restart_verified') is True and r.get('stop_exit_code') == 0
                and r.get('stop_signal') == 'SIGINT'
                and r.get('old_process_reaped_before_start') is True
                and r.get('old_listeners_absent') is True
                and r.get('binary_sha256') == owner.binary_sha256
                and r.get('config_sha256') == owner.config_sha256
                and network_evidence_is_confined(r.get('before'))
                and network_evidence_is_confined(r.get('after'))
                for r in restarts))
        result['evaluation_network_namespace_confined'] = (
            network_evidence_is_confined(before) and network_evidence_is_confined(after)
            and before['probe_namespace'] == after['probe_namespace']
            and result['process_restarts_verified'])
        result['binary_sha256'] = owner.binary_sha256
        result['config_sha256'] = owner.config_sha256
        if result['evaluation_completed'] and not result['evaluation_network_namespace_confined']:
            raise InvalidInput('Lifecycle confinement or process evidence is incomplete')
    except Exception as error:
        # No vendor body, exception message, command output or DICOM bytes here.
        result.update(evaluation_completed=False, lifecycle_acceptance_passed=False,
                      evaluation_network_namespace_confined=False)
        if 'failure_stage' in result:
            result['followup_failure'] = {'stage': stage, 'type': type(error).__name__}
        else:
            result.update(failure_stage=stage, failure_type=type(error).__name__)
        if 'lifecycle_evaluation_incomplete' not in result['acceptance_blockers']:
            result['acceptance_blockers'].append('lifecycle_evaluation_incomplete')
    finally:
        if owner is not None:
            try:
                owner.close()
            except Exception as error:
                # Cleanup failure must not prevent saving earlier evidence.
                result.update(evaluation_completed=False, lifecycle_acceptance_passed=False,
                              cleanup_failure_type=type(error).__name__)
                result.setdefault('failure_stage', 'process_cleanup')
                result.setdefault('failure_type', type(error).__name__)
                if 'lifecycle_evaluation_incomplete' not in result['acceptance_blockers']:
                    result['acceptance_blockers'].append('lifecycle_evaluation_incomplete')
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    except OSError:
        print('HOLD: lifecycle receipt could not be saved', file=sys.stderr)
        return 1
    code = acceptance_exit_code(result)
    print('Lifecycle receipt saved; acceptance exit code:', code,
          '; backend adoption remains HOLD_NOT_APPROVED')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
